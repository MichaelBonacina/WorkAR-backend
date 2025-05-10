import argparse
import time
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import fal_client # type: ignore
from PIL import Image

# Relative imports for the new structure
from models.model_utils import (
    logger, sanitize_for_logging, 
    ObjectPoint, ImageInfo, 
    draw_bounding_boxes, save_json_results, looks_like_base64
)
# BaseImageUtilModel is inherited via OpenVocabBBoxDetectionModel
from models.fal_base import FALModel
from .open_vocab_bbox_model import OpenVocabBBoxDetectionModel, OpenVocabBBoxDetectionResponse

# --- Moondream Specific Data Class ---
@dataclass
class MoondreamResponse(OpenVocabBBoxDetectionResponse):
    image: Optional[ImageInfo] = None # Specific field for Moondream

# --- Moondream Specific Model ---
class Moondream(OpenVocabBBoxDetectionModel, FALModel):
    """Moondream model implementation using FAL API."""
    FAL_ENDPOINT = "fal-ai/moondream2/object-detection"

    def __init__(self, max_retries: int = 3):
        OpenVocabBBoxDetectionModel.__init__(self, max_retries) 
        FALModel.__init__(self, max_retries=self.max_retries)
        logger.info(f"Moondream model initialized. FAL Endpoint: '{self.FAL_ENDPOINT}', Max retries: {self.max_retries}.")

    def __call__(self, image_input: Any, object_name: str) -> MoondreamResponse:
        logger.info(f"Moondream processing image for object: '{object_name}'.")
        if not object_name or not isinstance(object_name, str):
            logger.error(f"Invalid object_name: '{object_name}'. Must be a non-empty string.")
            raise ValueError("object_name must be a non-empty string")
        
        pil_image = self._validate_image(image_input) 
        resized_image = self._resize_image(pil_image)
        base64_image = self._encode_image_to_base64(resized_image)
        
        arguments = {
            "image_url": base64_image, 
            "object": object_name
        }
        
        def on_moondream_queue_update(update: Any):
            if isinstance(update, fal_client.InProgress):
                for log_entry in getattr(update, 'logs', []): 
                    logger.info(f"Moondream API (fal-ai/moondream2) update: {sanitize_for_logging(log_entry)}")
        
        result_api = None
        try:
            result_api = fal_client.subscribe(
                self.FAL_ENDPOINT,
                arguments=arguments,
                with_logs=True,
                on_queue_update=on_moondream_queue_update
            )
        except Exception as e: 
            logger.error(f"Unexpected error during Moondream __call__ for object '{object_name}': {e}", exc_info=True)
            traceback.print_exc()
            raise RuntimeError(f"Unexpected error in Moondream processing for '{object_name}': {e}") from e

        objects_list: List[ObjectPoint] = []
        if result_api and "objects" in result_api and isinstance(result_api.get("objects"), list):
            for obj_data in result_api["objects"]:
                if isinstance(obj_data, dict):
                    objects_list.append(ObjectPoint(
                        x_min=obj_data.get("x_min", 0.0),
                        y_min=obj_data.get("y_min", 0.0),
                        x_max=obj_data.get("x_max", 0.0),
                        y_max=obj_data.get("y_max", 0.0)
                    ))
                else:
                    logger.warning(f"Unexpected object data format in Moondream response: {sanitize_for_logging(obj_data)}")
        elif result_api and "objects" in result_api:
             logger.warning(f"Moondream 'objects' field received but is not a list: {sanitize_for_logging(result_api.get('objects'))}")

        image_info_data: Optional[ImageInfo] = None
        if result_api and "image" in result_api and isinstance(result_api.get("image"), dict):
            img_data_dict = result_api["image"]
            image_info_data = ImageInfo(
                url=img_data_dict.get("url", ""),
                content_type=img_data_dict.get("content_type", ""),
                file_name=img_data_dict.get("file_name", ""),
                file_size=img_data_dict.get("file_size", 0),
                width=img_data_dict.get("width", 0),
                height=img_data_dict.get("height", 0)
            )
        elif result_api and "image" in result_api:
            logger.warning(f"Moondream 'image' field received but is not a dict: {sanitize_for_logging(result_api.get('image'))}")

        logger.info(f"Moondream successfully processed. Detected {len(objects_list)} instances of '{object_name}'.")
        return MoondreamResponse(
            objects=objects_list,
            image=image_info_data,
            raw_response=result_api if result_api else {}
        )

# --- Main CLI Function ---
def main_cli(): # Renamed to avoid conflict if this file is imported elsewhere
    parser = argparse.ArgumentParser(description="Moondream Object Detection CLI")
    parser.add_argument("image_path", help="Path to the input image")
    parser.add_argument("object_name", help="Name of the object to detect")
    parser.add_argument("--output", default="moondream_output.png", help="Path to save visualization output (PNG)")
    parser.add_argument("--json-output", default="moondream_results.json", help="Path to save JSON results")
    parser.add_argument("--point-size", type=int, default=10, help="Size of visualized points")
    parser.add_argument("--point-color", default="red", help="Color of visualized points")
    parser.add_argument("--retries", type=int, default=3, help="Maximum number of API retries for FAL calls")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose (DEBUG level) logging")
    parser.add_argument("--fake-image", action="store_true", help="Use a 1x1 pixel fake image instead of loading from file")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG) # Ensure logger from model_utils is affected
        logger.info("Verbose logging enabled.")
    
    original_image: Optional[Image.Image] = None
    try:
        if args.fake_image:
            logger.info("Using 1x1 pixel fake image")
            original_image = Image.new('RGB', (1, 1), color='white')
            image_path = "fake_image.png"
            original_image.save(image_path)
        else:
            try:
                image_path_obj = Path(args.image_path)
                if not image_path_obj.exists():
                    logger.error(f"Input image file not found: {image_path_obj}")
                    return 1
                original_image = Image.open(image_path_obj)
                image_path = args.image_path
                logger.info(f"Loaded input image '{args.image_path}' of size {original_image.size}, mode {original_image.mode}")
            except Exception as e:
                logger.error(f"Failed to load input image '{args.image_path}': {e}")
                traceback.print_exc()
                return 1
        
        model = Moondream(max_retries=args.retries)
        
        logger.info(f"Starting Moondream processing for object '{args.object_name}'...")
        start_time = time.time()
        response = model(image_path, args.object_name)
        end_time = time.time()
        
        latency = end_time - start_time
        logger.info(f"Moondream processing completed in {latency:.2f} seconds.")
        
        logger.info(f"Detected {len(response.objects)} instances of '{args.object_name}':")
        for i, obj in enumerate(response.objects):
            logger.info(f"  Object {i+1}: x_min={obj.x_min:.4f}, y_min={obj.y_min:.4f}, x_max={obj.x_max:.4f}, y_max={obj.y_max:.4f}")
        
        if original_image:
            output_viz_path = Path(args.output)
            # Convert ObjectPoint instances to dictionaries with bounding box keys
            objects_as_dicts = [
                {
                    "x_min": obj.x_min,
                    "y_min": obj.y_min,
                    "x_max": obj.x_max,
                    "y_max": obj.y_max
                }
                for obj in response.objects
            ]

            draw_bounding_boxes(
                original_image, 
                objects_as_dicts, 
                output_path=str(output_viz_path),
                label=args.object_name
            )
            logger.info(f"Visualization saved to: {output_viz_path.resolve()}") # Use resolve for canonical path
        else:
            logger.warning("Original image not available for visualization.")

        output_json_path = Path(args.json_output)
        # Prepare data for save_json_results, including a summary of raw_response
        json_data_to_save = {
            "objects": [{"x_min": obj.x_min, "y_min": obj.y_min, "x_max": obj.x_max, "y_max": obj.y_max} for obj in response.objects],
            "image_info": None,
            "raw_response_summary": { # Example: include some non-sensitive parts or a flag
                k: v for k,v in response.raw_response.items() 
                if k not in ['objects', 'image'] and not isinstance(v, str) or not looks_like_base64(v) #簡易フィルタ
            }
        }
        if response.image:
            json_data_to_save["image_info"] = {
                "url": response.image.url,
                "content_type": response.image.content_type,
                "file_name": response.image.file_name,
                "file_size": response.image.file_size,
                "width": response.image.width,
                "height": response.image.height
            }
        save_json_results(json_data_to_save, str(output_json_path))
        logger.info(f"JSON results saved to: {output_json_path.resolve()}")

        print("\n=== Moondream Output Files ===")
        if original_image: print(f"Visualization: {Path(args.output).resolve()}")
        print(f"JSON Results:  {Path(args.json_output).resolve()}")
        print("==============================\n")
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        return 130 
    except Exception as e:
        logger.error(f"An critical error occurred in main execution: {e}", exc_info=args.verbose)
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    # This allows the script to be run directly for the CLI
    # Note: `logger` here refers to the logger from `model_utils` due to the import.
    # If `model_utils.logger.setLevel` is called in `main_cli`, it affects the shared logger.
    exit_code = main_cli()
    logger.info(f"Application finished with exit code {exit_code}.")
    time.sleep(0.1) 
    exit(exit_code) 
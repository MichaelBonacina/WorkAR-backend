import argparse
import time
import traceback
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import replicate
from PIL import Image

# Relative imports for the new structure
from models.model_utils import (
    logger, sanitize_for_logging, 
    ObjectPoint, # ImageInfo might not be directly used in OWLv2Response but is a common type
    draw_bounding_boxes, save_json_results, looks_like_base64
)
# BaseImageUtilModel is inherited via OpenVocabBBoxDetectionModel
from .open_vocab_bbox_model import OpenVocabBBoxDetectionModel, OpenVocabBBoxDetectionResponse

# --- OWLv2 Specific Data Class ---
@dataclass
class OWLv2Response(OpenVocabBBoxDetectionResponse):
    timings: Dict[str, float] = field(default_factory=dict)

# --- OWLv2 Specific Model ---
class OWLv2(OpenVocabBBoxDetectionModel):
    """OWLv2 model implementation using Replicate API."""
    REPLICATE_DEPLOYMENT = "andreemic/owlv2"

    def __init__(self, max_retries: int = 3):
        OpenVocabBBoxDetectionModel.__init__(self, max_retries)
        if not os.environ.get("REPLICATE_API_TOKEN"):
            logger.warning("REPLICATE_API_TOKEN not found in environment variables. OWLv2 model may not work.")
        logger.info(f"OWLv2 model initialized. Replicate Deployment: '{self.REPLICATE_DEPLOYMENT}', Max retries: {self.max_retries}.")

    def __call__(self, image_input: Any, object_name: str) -> OWLv2Response:
        total_start_time = time.time()
        logger.info(f"OWLv2 processing image for object: '{object_name}'.")
        if not object_name or not isinstance(object_name, str):
            logger.error(f"Invalid object_name: '{object_name}'. Must be a non-empty string.")
            raise ValueError("object_name must be a non-empty string")
        
        timings_data = {}
        
        validation_start = time.time()
        pil_image = self._validate_image(image_input)
        validation_end = time.time()
        timings_data["image_validation"] = validation_end - validation_start
        
        resize_start = time.time()
        resized_image = self._resize_image(pil_image)
        resize_end = time.time()
        timings_data["image_resizing"] = resize_end - resize_start
        
        original_width, original_height = pil_image.size
        resized_width, resized_height = resized_image.size
        
        encode_start = time.time()
        base64_image = self._encode_image_to_base64(resized_image)
        encode_end = time.time()
        timings_data["base64_encoding"] = encode_end - encode_start
        
        input_data = {
            "image": base64_image,
            "query": object_name
        }
        
        retry_count = 0
        api_result = None
        
        api_start = time.time()
        while retry_count < self.max_retries:
            try:
                deployment = replicate.deployments.get(self.REPLICATE_DEPLOYMENT)
                prediction = deployment.predictions.create(input=input_data)
                prediction.wait()
                api_result = prediction.output
                break
            except Exception as e:
                retry_count += 1
                logger.warning(f"Attempt {retry_count}/{self.max_retries} failed: {e}")
                if retry_count >= self.max_retries:
                    logger.error(f"Failed to process with OWLv2 after {self.max_retries} attempts: {e}", exc_info=True)
                    traceback.print_exc()
                    raise RuntimeError(f"Failed to process with OWLv2 after {self.max_retries} attempts: {e}") from e
                time.sleep(1)  # Wait before retrying
        api_end = time.time()
        timings_data["api_call"] = api_end - api_start
        
        if not api_result:
            logger.error("No result returned from OWLv2 API.")
            raise RuntimeError("No result returned from OWLv2 API.")
            
        post_processing_start = time.time()
        objects_list: List[ObjectPoint] = []
        
        if isinstance(api_result, list):
            for detection in api_result:
                if isinstance(detection, dict) and "bbox" in detection:
                    bbox = detection["bbox"]
                    if len(bbox) == 4:
                        objects_list.append(ObjectPoint(
                            x_min=float(bbox[0]) / resized_width,
                            y_min=float(bbox[1]) / resized_height,
                            x_max=float(bbox[2]) / resized_width,
                            y_max=float(bbox[3]) / resized_height
                        ))
        elif isinstance(api_result, dict):
            if "json_data" in api_result and isinstance(api_result["json_data"], dict) and "objects" in api_result["json_data"]:
                for detection in api_result["json_data"]["objects"]:
                    if isinstance(detection, dict) and "bbox" in detection:
                        bbox = detection["bbox"]
                        if len(bbox) == 4:
                            objects_list.append(ObjectPoint(
                                x_min=float(bbox[0]) / resized_width,
                                y_min=float(bbox[1]) / resized_height,
                                x_max=float(bbox[2]) / resized_width,
                                y_max=float(bbox[3]) / resized_height
                            ))
            elif "detections" in api_result:
                for detection in api_result["detections"]:
                    if isinstance(detection, dict) and "bbox" in detection:
                        bbox = detection["bbox"]
                        if len(bbox) == 4:
                            objects_list.append(ObjectPoint(
                                x_min=float(bbox[0]) / resized_width,
                                y_min=float(bbox[1]) / resized_height,
                                x_max=float(bbox[2]) / resized_width,
                                y_max=float(bbox[3]) / resized_height
                            ))
        post_processing_end = time.time()
        timings_data["post_processing"] = post_processing_end - post_processing_start
        
        total_end_time = time.time()
        timings_data["total"] = total_end_time - total_start_time
        
        logger.info(f"OWLv2 execution times (seconds):")
        for step, duration in timings_data.items():
            logger.info(f"  {step.replace('_', ' ').title()}: {duration:.4f}s")
        
        logger.info(f"OWLv2 successfully processed. Detected {len(objects_list)} instances of '{object_name}'.")
        return OWLv2Response(
            objects=objects_list,
            raw_response=api_result if api_result else {},
            timings=timings_data
        )

# --- Main CLI Function ---
def main_cli():
    parser = argparse.ArgumentParser(description="OWLv2 Object Detection CLI")
    parser.add_argument("image_path", help="Path to the input image")
    parser.add_argument("object_name", help="Name of the object to detect")
    parser.add_argument("--output", default="owlv2_output.png", help="Path to save visualization output (PNG)")
    parser.add_argument("--json-output", default="owlv2_results.json", help="Path to save JSON results")
    parser.add_argument("--point-size", type=int, default=10, help="Size of visualized points")
    parser.add_argument("--point-color", default="red", help="Color of visualized points")
    parser.add_argument("--retries", type=int, default=3, help="Maximum number of API retries")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose (DEBUG level) logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel("DEBUG")
        logger.info("Verbose logging enabled.")
    
    original_image: Optional[Image.Image] = None
    try:
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
        
        model = OWLv2(max_retries=args.retries)
        
        logger.info(f"Starting OWLv2 processing for object '{args.object_name}'...")
        response = model(image_path, args.object_name)
        
        # Print performance summary
        print("\n=== Performance Summary ===")
        for step, duration in response.timings.items():
            print(f"{step.replace('_', ' ').title()}: {duration:.4f}s")
        print("==========================\n")
        
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
            logger.info(f"Visualization saved to: {output_viz_path.resolve()}")
        else:
            logger.warning("Original image not available for visualization.")

        output_json_path = Path(args.json_output)
        json_data_to_save = {
            "objects": [{"x_min": obj.x_min, "y_min": obj.y_min, "x_max": obj.x_max, "y_max": obj.y_max} for obj in response.objects],
            "raw_response_summary": {
                k: v for k, v in response.raw_response.items() 
                if not isinstance(v, str) or not looks_like_base64(v)
            },
            "performance": response.timings
        }
        save_json_results(json_data_to_save, str(output_json_path))
        logger.info(f"JSON results saved to: {output_json_path.resolve()}")

        print("\n=== OWLv2 Output Files ===")
        if original_image: print(f"Visualization: {Path(args.output).resolve()}")
        print(f"JSON Results:  {Path(args.json_output).resolve()}")
        print("==============================\n")
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        return 130 
    except Exception as e:
        logger.error(f"A critical error occurred in main execution: {e}", exc_info=args.verbose)
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main_cli()
    logger.info(f"Application finished with exit code {exit_code}.")
    time.sleep(0.1) 
    exit(exit_code) 

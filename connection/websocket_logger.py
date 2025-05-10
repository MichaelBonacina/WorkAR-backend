"""
WebSocket logging utilities for debug/analysis purposes.

This module provides functions to log WebSocket communications to disk,
including images, messages, and processing calls.
"""

import os
import json
import shutil
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import io
import base64
from PIL import Image, ImageDraw, ImageFont

from models.image_processing_base import BaseImageUtilModel

class WebSocketLogger:
    """Handles logging of WebSocket communications to disk for debugging."""
    
    def __init__(self, base_dir: str = "websocket_logs"):
        """
        Initialize the WebSocket logger.
        
        Args:
            base_dir: Base directory for all WebSocket logs
        """
        self.base_dir = Path(base_dir)
        self.incoming_dir = self.base_dir / "incoming_messages"
        self.outgoing_dir = self.base_dir / "outgoing_messages"
        self.analysis_dir = self.base_dir / "analysis_calls"
        self._initialize_directories()
        self.image_utils = BaseImageUtilModel()
        
    def _initialize_directories(self) -> None:
        """Create or clear the log directories."""
        # Clear existing logs if present
        if self.base_dir.exists():
            try:
                shutil.rmtree(self.base_dir)
                logging.info(f"Cleared existing WebSocket logs at {self.base_dir}")
            except Exception as e:
                logging.error(f"Error clearing WebSocket logs: {e}")
        
        # Create directories
        for directory in [self.incoming_dir, self.outgoing_dir, self.analysis_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"Initialized WebSocket logging directories at {self.base_dir}")
    
    def _get_timestamp(self) -> str:
        """Get a formatted timestamp for filenames."""
        return time.strftime("%Y%m%d_%H%M%S_%f")[:-3]
    
    def _visualize_object_detection(self, image_path: str, objects: List[Dict[str, Any]], 
                                   output_path: str) -> bool:
        """
        Create a visualization of detected objects with bounding boxes.
        
        Args:
            image_path: Path to the source image
            objects: List of detected objects with bounding boxes
            output_path: Path to save the visualization
            
        Returns:
            bool: True if visualization was successful
        """
        try:
            # Use the image validation function from BaseImageUtilModel
            try:
                img = self.image_utils._validate_image(image_path)
            except Exception as e:
                logging.error(f"Source image validation failed: {e}")
                return False
                
            # Resize large images for better visualization
            img = self.image_utils._resize_image(img, max_size=1024)
            
            draw = ImageDraw.Draw(img)
            
            # Draw bounding boxes and labels
            for obj in objects:
                if "bbox" not in obj or not obj["bbox"]:
                    continue
                    
                title = obj.get("title", "unknown")
                bbox = obj["bbox"]
                
                # Get image dimensions
                img_width, img_height = img.size
                
                # Convert normalized coordinates to pixel coordinates
                x_min = int(bbox["x_min"] * img_width)
                y_min = int(bbox["y_min"] * img_height)
                x_max = int(bbox["x_max"] * img_width)
                y_max = int(bbox["y_max"] * img_height)
                
                # Draw rectangle with a 3-pixel width line
                draw.rectangle([x_min, y_min, x_max, y_max], outline="red", width=3)
                
                # Draw object name above the box
                draw.text((x_min, y_min - 15), title, fill="red")
                
                # Draw center point if available
                if "coordinates" in obj and obj["coordinates"]:
                    center_x = int(obj["coordinates"]["x"] * img_width)
                    center_y = int(obj["coordinates"]["y"] * img_height)
                    # Draw a small cross at the center point
                    draw.line([(center_x - 5, center_y), (center_x + 5, center_y)], fill="blue", width=2)
                    draw.line([(center_x, center_y - 5), (center_x, center_y + 5)], fill="blue", width=2)
            
            # Add timestamp
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            draw.text((10, 10), f"Detection Log: {timestamp}", fill="white", stroke_width=2, stroke_fill="black")
            
            # Save the visualization - leverage BaseImageUtilModel's handling of image modes
            img_bytes = io.BytesIO()
            
            # Convert to RGB mode if the image has an alpha channel (RGBA)
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                
            img.save(img_bytes, format="JPEG", quality=95, optimize=True)
            img_bytes.seek(0)
            
            with open(output_path, 'wb') as f:
                f.write(img_bytes.getvalue())
                
            logging.info(f"Created object detection visualization: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error creating visualization: {e}")
            return False
    
    def log_incoming_image(self, image_data: bytes, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Log an incoming image and its metadata.
        
        Args:
            image_data: Raw image bytes
            metadata: Optional metadata associated with the image
            
        Returns:
            str: Path to the saved image file
        """
        timestamp = self._get_timestamp()
        
        # Save the image
        image_path = self.incoming_dir / f"{timestamp}_incoming_image.jpg"
        try:
            with open(image_path, "wb") as f:
                f.write(image_data)
        except Exception as e:
            logging.error(f"Error saving incoming image log: {e}")
            return ""
            
        # Save metadata if provided
        if metadata:
            metadata_path = self.incoming_dir / f"{timestamp}_incoming_message.json"
            try:
                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)
            except Exception as e:
                logging.error(f"Error saving incoming message metadata: {e}")
                
        return str(image_path)
    
    def log_incoming_message(self, message: Dict[str, Any]) -> str:
        """
        Log an incoming JSON message.
        
        Args:
            message: Message data to log
            
        Returns:
            str: Path to the saved message file
        """
        timestamp = self._get_timestamp()
        message_path = self.incoming_dir / f"{timestamp}_incoming_message.json"
        
        try:
            with open(message_path, "w") as f:
                json.dump(message, f, indent=2)
            return str(message_path)
        except Exception as e:
            logging.error(f"Error saving incoming message log: {e}")
            return ""
    
    def log_outgoing_message(self, message: Union[str, Dict[str, Any]]) -> str:
        """
        Log an outgoing message.
        
        Args:
            message: The message being sent (string or dict)
            
        Returns:
            str: Path to the saved message file
        """
        timestamp = self._get_timestamp()
        message_path = self.outgoing_dir / f"{timestamp}.json"
        
        try:
            # Convert string to dict if possible
            if isinstance(message, str):
                try:
                    message_data = json.loads(message)
                except json.JSONDecodeError:
                    message_data = {"raw_message": message}
            else:
                message_data = message
                
            with open(message_path, "w") as f:
                json.dump(message_data, f, indent=2)
            return str(message_path)
        except Exception as e:
            logging.error(f"Error saving outgoing message log: {e}")
            return ""
    
    def log_process_frame_call(self, task_state: Any, video_state: Any, 
                               allow_visualization: bool = True,
                               result: Optional[str] = None) -> str:
        """
        Log a processFrame call.
        
        Args:
            task_state: Current task state
            video_state: Current video state
            allow_visualization: Whether visualization is enabled
            result: Optional result of the processing
            
        Returns:
            str: Path to the saved call log
        """
        timestamp = self._get_timestamp()
        log_dir = self.analysis_dir / f"{timestamp}_processFrame"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log basic call info
        info = {
            "timestamp": timestamp,
            "allow_visualization": allow_visualization,
            "task_name": task_state.task.name if task_state and task_state.task else "None",
            "current_step": task_state.index + 1 if task_state else 0,
            "images_count": len(video_state.get_images()) if video_state else 0,
            "images": video_state.get_images() if video_state else []
        }
        
        try:
            with open(log_dir / "call_info.json", "w") as f:
                json.dump(info, f, indent=2)
                
            # Log result if provided
            if result is not None:
                with open(log_dir / "result.json", "w") as f:
                    json.dump({"result": result}, f, indent=2)
                    
            return str(log_dir)
        except Exception as e:
            logging.error(f"Error saving processFrame call log: {e}")
            return ""
            
    def log_add_object_coordinates_call(self, frame: str, camera_pose: Dict[str, Any],
                                        allow_visualization: bool = True, 
                                        objects: Optional[list] = None,
                                        result: Optional[Dict[str, Any]] = None) -> str:
        """
        Log an addObjectCoordinates call.
        
        Args:
            frame: Path to the frame being processed
            camera_pose: Camera pose data
            allow_visualization: Whether visualization is enabled
            objects: Object detection results if available
            result: Optional result of the addObjectCoordinates call
            
        Returns:
            str: Path to the saved call log
        """
        timestamp = self._get_timestamp()
        log_dir = self.analysis_dir / f"{timestamp}_addObjectCoordinates"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log basic call info
        info = {
            "timestamp": timestamp,
            "frame": frame,
            "camera_pose": camera_pose,
            "allow_visualization": allow_visualization
        }
        
        try:
            # Save call info
            with open(log_dir / "call_info.json", "w") as f:
                json.dump(info, f, indent=2)
                
            # Copy the input frame if it exists
            input_frame_path = None
            if os.path.exists(frame):
                input_frame_path = log_dir / "input_frame.jpg"
                shutil.copy(frame, input_frame_path)
                
            # Log detected objects if available
            result_objects = None
            if objects:
                with open(log_dir / "detected_objects.json", "w") as f:
                    json.dump(objects, f, indent=2)
                result_objects = objects
            
            # Log the result if provided
            if result:
                with open(log_dir / "result.json", "w") as f:
                    json.dump(result, f, indent=2)
                
                # Get objects from result if not provided separately
                if not result_objects and "objects" in result and result["objects"]:
                    result_objects = result["objects"]
                    
            # Create visualization if we have both a frame and objects
            if input_frame_path and result_objects and allow_visualization:
                vis_path = log_dir / "visualization.jpg"
                self._visualize_object_detection(
                    image_path=str(input_frame_path),
                    objects=result_objects,
                    output_path=str(vis_path)
                )
                logging.info(f"Created visualization for object detection at {vis_path}")
                    
            return str(log_dir)
        except Exception as e:
            logging.error(f"Error saving addObjectCoordinates call log: {e}")
            return ""

# Global instance for easy access
websocket_logger = WebSocketLogger() 
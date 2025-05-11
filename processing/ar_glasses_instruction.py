from typing import List, Optional, Dict, Any, Union, Tuple
from dataclasses import dataclass
import concurrent.futures
import traceback
from PIL import Image, ImageDraw, ImageFile
from models.owlv2 import OWLv2
from models.open_vocab_bbox_model import OpenVocabBBoxDetectionModel
from processing.task_status import TaskStatus
from tasks.Step import Step
import logging
from connection.message_queue import log_message
import os
import uuid
from pathlib import Path
import datetime

@dataclass
class ObjectInfo:
    """
    Information about a detected object in the frame.
    
    Attributes:
        title: The name/title of the object
        coordinates: Optional coordinates as {x, y} normalized positions (0.0-1.0)
        bbox: Optional bounding box coordinates (x_min, y_min, x_max, y_max) normalized (0.0-1.0)
    """
    title: str
    coordinates: Optional[Dict[str, float]] = None
    bbox: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization."""
        result = {"title": self.title}
        
        if self.coordinates is not None:
            result["coordinates"] = self.coordinates
            
        if self.bbox is not None:
            result["bbox"] = self.bbox
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ObjectInfo':
        """Create an ObjectInfo from a dictionary representation."""
        title = data.get("title", "")
        
        coordinates = None
        coords_data = data.get("coordinates")
        if isinstance(coords_data, dict) and "x" in coords_data and "y" in coords_data:
            coordinates = coords_data
        
        bbox = data.get("bbox")
        
        return cls(title=title, coordinates=coordinates, bbox=bbox)

@dataclass
class ARGlassesInstruction:
    """
    A structured result from frame analysis to provide instructions to AR glasses.
    
    Attributes:
        current_task_status: The status of the task execution - 'executing_task', 'completed_task', 'derailed', or 'error'
        objects: List of objects that need attention (only for 'derailed' status)
        action: Description of the required action (only for 'derailed' status)
        message: Additional information or error message
        raw_response: The original raw response from the AI model
        coordinates_relative_to_camera_pose: Camera position and rotation at the time of object detection

    Example JSON:
    {
        "current_task_status": "derailed",
        "objects": [
            {
                "title": "coffee cup",
                "coordinates": {"x": 0.5234, "y": 0.6789},
                "bbox": {
                    "x_min": 0.4123,
                    "y_min": 0.5678,
                    "x_max": 0.6345,
                    "y_max": 0.7890
                }
            }
        ],
        "action": "Pick up the coffee cup",
        "message": "Found coffee cup in frame",
        "coordinates_relative_to_camera_pose": {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
        }
    }
    """
    current_task_status: TaskStatus
    objects: Optional[List[ObjectInfo]] = None
    action: Optional[str] = None
    message: Optional[str] = None
    raw_response: Optional[str] = None
    coordinates_relative_to_camera_pose: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization."""
        result = {
            "current_task_status": self.current_task_status
        }
        
        if self.objects is not None:
            result["objects"] = [obj.to_dict() for obj in self.objects]
            
        if self.action is not None:
            result["action"] = self.action
            
        if self.message is not None:
            result["message"] = self.message
            
        if self.coordinates_relative_to_camera_pose is not None:
            result["coordinates_relative_to_camera_pose"] = self.coordinates_relative_to_camera_pose
            
        return result
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization (alias for to_dict)."""
        return self.to_dict()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ARGlassesInstruction':
        """Create an ARGlassesInstruction from a dictionary representation."""
        current_task_status = data.get("current_task_status", "error")
        
        objects = None
        objects_data = data.get("objects")
        if objects_data is None:
            objects_data = data.get("focus_objects")

        if isinstance(objects_data, list):
            objects = [
                ObjectInfo.from_dict(obj) if isinstance(obj, dict) else 
                ObjectInfo(title=obj) if isinstance(obj, str) else
                ObjectInfo(title="unknown")
                for obj in objects_data
            ]
        
        action = data.get("action")
        message = data.get("message")
        raw_response = data.get("raw_response")
        coordinates_relative_to_camera_pose = data.get("coordinates_relative_to_camera_pose")
        
        return cls(
            current_task_status=current_task_status,
            objects=objects,
            action=action,
            message=message,
            raw_response=raw_response,
            coordinates_relative_to_camera_pose=coordinates_relative_to_camera_pose
        )

    @classmethod
    def from_step(cls, current_task_status: TaskStatus, step: Step) -> 'ARGlassesInstruction':
        """Create an ARGlassesInstruction from a Step object."""
        objects_string_array = step.get_focus_objects()
        action_str = step.get_action()

        processed_objects = [ObjectInfo(title=obj) for obj in objects_string_array]

        return ARGlassesInstruction(
            current_task_status=current_task_status,
            objects=processed_objects,
            action=action_str
        )
        
    def addObjectCoordinates(self, frame: Union[str, Image.Image], 
                            bbox_detection_model: Optional[OpenVocabBBoxDetectionModel] = None,
                            camera_pose: Optional[Dict[str, Any]] = None,
                            allow_visualization: bool = True) -> bool:
        """
        Enhances this ARGlassesInstruction by detecting coordinates of focus objects.
        
        Args:
            frame: Either a PIL Image object or a path to an image file
            bbox_detection_model: Optional detection model instance; if None, OWLv2 will be created
            camera_pose: Optional camera position and rotation information
            allow_visualization: Flag to control whether to create and send visualizations
            
        Returns:
            bool: True if coordinates were found for at least one object, False otherwise
        """
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        
        # Store camera pose information if provided
        if camera_pose is not None:
            self.coordinates_relative_to_camera_pose = camera_pose

        # Early return if no focus objects to process
        if not self.objects:
            log_message("info", "No objects to detect coordinates for", "object_detection")
            return False
        
        # Log the classes we're searching for
        object_names = [obj.title for obj in self.objects]
        log_message("info", f"Searching for objects: {', '.join(object_names)}", "object_detection")
            
        # Create a new OWLv2 model if one wasn't provided
        model = bbox_detection_model if bbox_detection_model else OWLv2()
        
        # Make sure we have a PIL image
        pil_image = None
        image_path = None
        if isinstance(frame, str):
            image_path = frame
            try:
                pil_image = Image.open(frame)
                log_message("info", f"Processing image from path: {frame}", "object_detection")
            except Exception as e:
                print(f"Error opening image file: {e}")
                traceback.print_exc()
                log_message("error", f"Error opening image file: {str(e)}", "object_detection")
                self.message = f"Error detecting object coordinates: {str(e)}"
                return False
        elif isinstance(frame, Image.Image):
            pil_image = frame
            # Save a temporary copy for visualization
            tmp_dir = os.path.join(os.getcwd(), "media", "tmp_frames")
            os.makedirs(tmp_dir, exist_ok=True)
            image_path = os.path.join(tmp_dir, f"temp_{uuid.uuid4()}.jpg")
            pil_image.save(image_path)
            log_message("info", "Processing image from PIL object", "object_detection")
            # Make sure the image is fully loaded into memory so copies don't rely on a shared file pointer
            try:
                pil_image.load()  # type: ignore[attr-defined]
            except Exception as e:
                log_message("warning", f"Could not fully load PIL image before processing: {e}", "object_detection")
        else:
            log_message("error", "Invalid frame format - must be PIL Image or path to image file", "object_detection")
            self.message = "Invalid frame format - must be PIL Image or path to image file"
            return False
        
        found_any_coordinates = False
            
        # Use ThreadPoolExecutor to process objects in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Create a function to process a single object
            def process_object(obj: ObjectInfo) -> Tuple[ObjectInfo, bool]:
                found_coords = False
                try:
                    # Call the model to detect the object
                    image_for_thread = pil_image.copy()
                    detection_response = model(image_for_thread, obj.title)
                    
                    # Process the detected objects - find the best match if multiple
                    if detection_response.objects:
                        # Get all bounding boxes
                        bboxes = [
                            {
                                "x_min": obj_point.x_min,
                                "y_min": obj_point.y_min,
                                "x_max": obj_point.x_max,
                                "y_max": obj_point.y_max
                            }
                            for obj_point in detection_response.objects
                        ]
                        
                        # For now, use the first detected object's coordinates
                        best_bbox = bboxes[0]
                        
                        # Calculate center point from the bbox
                        center_x = (best_bbox["x_min"] + best_bbox["x_max"]) / 2.0
                        center_y = (best_bbox["y_min"] + best_bbox["y_max"]) / 2.0
                        
                        # Round to 4 decimal places for cleaner output
                        center_x = round(center_x, 4)
                        center_y = round(center_y, 4)
                        
                        print(f"Detected {obj.title} at center ({center_x}, {center_y}), bbox: {best_bbox}")
                        log_message("info", f"Detected {obj.title} at center ({center_x}, {center_y})", "object_detection")
                        
                        # Update the object with coordinates and bbox
                        obj.coordinates = {"x": center_x, "y": center_y}
                        obj.bbox = best_bbox
                        found_coords = True
                        
                    else:
                        log_message("warning", f"Could not detect {obj.title} in image", "object_detection")
                        
                except Exception as e:
                    print(f"Error detecting coordinates for object '{obj.title}': {e}")
                    traceback.print_exc()
                    log_message("error", f"Error detecting {obj.title}: {str(e)}", "object_detection")
                    # Don't modify the object if there was an error
                    pass
                    
                return obj, found_coords
                
            # Process all objects in parallel
            future_to_obj = {
                executor.submit(process_object, obj): obj 
                for obj in self.objects
            }
            
            # Collect the results
            for future in concurrent.futures.as_completed(future_to_obj):
                _, found_coords = future.result()
                if found_coords:
                    found_any_coordinates = True
        
        # After all processing, visualize the results on the image
        try:
            # Skip visualization if not allowed (to reduce GUI load)
            if not allow_visualization:
                return found_any_coordinates
                
            # Create a copy for visualization
            vis_image = pil_image.copy()
            draw = ImageDraw.Draw(vis_image)
            
            # Keep track of detected objects for logging
            detected_count = 0
            
            # Draw bounding boxes for each detected object
            for obj in self.objects:
                if obj.bbox:
                    detected_count += 1
                    # Get image dimensions
                    img_width, img_height = vis_image.size
                    
                    # Convert normalized coordinates to pixel coordinates
                    x_min = int(obj.bbox["x_min"] * img_width)
                    y_min = int(obj.bbox["y_min"] * img_height)
                    x_max = int(obj.bbox["x_max"] * img_width)
                    y_max = int(obj.bbox["y_max"] * img_height)
                    
                    # Draw rectangle with a 3-pixel width line
                    draw.rectangle([x_min, y_min, x_max, y_max], outline="red", width=3)
                    
                    # Draw object name above the box
                    draw.text((x_min, y_min - 15), obj.title, fill="red")
            
            # Save the visualization
            vis_path = str(Path(image_path).with_name(f"vis_{Path(image_path).name}"))
            
            # Convert to RGB mode if the image has an alpha channel (RGBA)
            if vis_image.mode == 'RGBA':
                vis_image = vis_image.convert('RGB')
                
            vis_image.save(vis_path)
            
            # Log the visualization
            from connection.message_queue import image_received
            log_message("info", f"Detected {detected_count} of {len(self.objects)} objects", "object_detection")
            
            # Create a mock metadata dict for image_received
            metadata = {
                "width": vis_image.width,
                "height": vis_image.height,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "visualization": True,
                "objects_detected": [obj.title for obj in self.objects if obj.bbox]
            }
            image_received(vis_path, metadata, "object_detection")
            
        except Exception as e:
            print(f"Error creating visualization: {e}")
            traceback.print_exc()
            log_message("error", f"Error creating visualization: {str(e)}", "object_detection")
            
        return found_any_coordinates

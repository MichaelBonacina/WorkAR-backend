#!/usr/bin/env python
"""
Object Detection Test Script for WorkAR

This script demonstrates how to use the FrameAnalysisResult with object detection.
It creates a mock analysis result and adds object coordinates using Moondream.
"""

import argparse
import json
import os
from pathlib import Path
from PIL import Image
import sys
from PIL import ImageDraw

# Add the project root to the path so we can import the modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from processing.processFrame import processFrame, FrameAnalysisResult, ObjectInfo
from models.moondream import Moondream
from models.model_utils import draw_bounding_boxes

def main():
    parser = argparse.ArgumentParser(description="Test WorkAR's object detection")
    parser.add_argument("image_path", help="Path to the input image")
    parser.add_argument("--objects", type=str, default="bottle,cup,keyboard", 
                        help="Comma-separated list of objects to detect")
    parser.add_argument("--output", default="detected_objects.png", 
                        help="Output path for the image with detected objects")
    parser.add_argument("--result-json", default="analysis_result.json",
                        help="Path to save the analysis result as JSON")
    
    args = parser.parse_args()
    
    # Create a list of objects to look for
    object_list = [obj.strip() for obj in args.objects.split(",")]
    
    # Create a mock FrameAnalysisResult
    mock_result = FrameAnalysisResult(
        status="derailed",
        focus_objects=[ObjectInfo(title=obj) for obj in object_list],
        action=f"Use the {object_list[0]} properly according to the instructions"
    )
    
    print(f"Created mock result with objects: {object_list}")
    
    # Create Moondream model
    model = Moondream()
    print("Initialized Moondream model")
    
    # Process the image to add object coordinates
    try:
        image_path = args.image_path
        print(f"Looking for objects in image: {image_path}")
        
        # Run object detection using the instance method
        enhanced_result = mock_result.addObjectCoordinates(
            frame=image_path,
            bbox_detection_model=model
        )
        
        # Print the results
        print("\nDetection Results:")
        for obj in enhanced_result.objects:
            if obj.coordinates and obj.bbox:
                # Verify that coordinates match the center of the bbox
                expected_x = round((obj.bbox["x_min"] + obj.bbox["x_max"]) / 2.0, 4)
                expected_y = round((obj.bbox["y_min"] + obj.bbox["y_max"]) / 2.0, 4)
                actual_x = obj.coordinates["x"]
                actual_y = obj.coordinates["y"]
                
                # Check if coordinates match the center of bbox
                coords_match = (expected_x == actual_x and expected_y == actual_y)
                
                print(f"✓ {obj.title}: Found at center coordinates ({actual_x}, {actual_y})")
                print(f"  Bounding box: x_min={obj.bbox['x_min']}, y_min={obj.bbox['y_min']}, "
                      f"x_max={obj.bbox['x_max']}, y_max={obj.bbox['y_max']}")
                print(f"  Coordinates are at center of bbox: {coords_match}")
            elif obj.coordinates:
                print(f"✓ {obj.title}: Found at coordinates {obj.coordinates} (no bounding box)")
            else:
                print(f"✗ {obj.title}: Not found in the image")
        
        # Save the result to JSON
        with open(args.result_json, 'w') as f:
            json.dump(enhanced_result.to_dict(), f, indent=2)
        print(f"\nSaved result to: {args.result_json}")
        
        # Draw bounding boxes on the image
        try:
            # Open the image
            img = Image.open(image_path)
            
            # Collect all bounding boxes that were found
            bboxes = []
            labels = []
            
            for obj in enhanced_result.objects:
                if obj.bbox:
                    bboxes.append(obj.bbox)
                    labels.append(obj.title)
            
            if bboxes:
                # Draw the bounding boxes 
                img_with_boxes = draw_bounding_boxes(img, bboxes, output_path=None, labels=labels, return_image=True)
                
                # Draw center points on the same image
                draw = ImageDraw.Draw(img_with_boxes)
                
                # Draw a small circle at the center point of each object
                for obj in enhanced_result.objects:
                    if obj.coordinates:
                        # Get coordinates from the dictionary
                        x = obj.coordinates["x"]
                        y = obj.coordinates["y"]
                        # Convert normalized coordinates to pixel coordinates
                        pixel_x = int(x * img.width)
                        pixel_y = int(y * img.height)
                        
                        # Draw a small red circle at the center
                        radius = max(5, min(img.width, img.height) // 100)  # Adjust radius based on image size
                        draw.ellipse(
                            [(pixel_x - radius, pixel_y - radius), 
                             (pixel_x + radius, pixel_y + radius)], 
                            fill='red'
                        )
                
                # Save the image with both bounding boxes and center points
                img_with_boxes.save(args.output)
                print(f"Saved image with bounding boxes and center points to: {args.output}")
            else:
                print("No bounding boxes were found for any objects.")
                
        except Exception as e:
            print(f"Error drawing bounding boxes: {e}")
            
    except Exception as e:
        print(f"Error processing image: {e}")

if __name__ == "__main__":
    main() 
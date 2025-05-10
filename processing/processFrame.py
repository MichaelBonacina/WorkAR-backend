from typing import TYPE_CHECKING, Literal
import json
import traceback
from states.VideoState import VideoState
from models.openai import OpenAI
from processing.ar_glasses_instruction import ARGlassesInstruction, ObjectInfo
from processing.task_status import TaskStatus
from connection.message_queue import log_message, image_received
from PIL import Image, ImageDraw, ImageFont
import os
import uuid
import datetime

if TYPE_CHECKING:
    from states.TaskState import TaskState # Forward reference for TaskState

class processFrame:
    """A class to process video frames in conjunction with task and video states."""

    @staticmethod
    def processFrame(task_state: 'TaskState', video_state: VideoState, allow_visualization: bool = True) -> TaskStatus:
        """
        Processes a frame based on the current task and video state by constructing
        a prompt for an AI model and returning a simple status string.

        Args:
            task_state: The current state of the task.
            video_state: The current state of the video (e.g., recent frames).
            allow_visualization: Flag to control whether to create and send visualizations

        Returns:
            TaskStatus: A literal status string - 'executing_task', 'completed_task', 'derailed', or 'error'
        """
        previous_step = task_state.getPreviousStep()
        current_step = task_state.getCurrentStep()
        next_step = task_state.getNextStep()
        
        is_first_step = task_state.index == 0
        
        # Log that we're starting frame processing
        log_message("info", f"Processing frame for task: {task_state.task.name}", "frame_processor")
        log_message("info", f"Current step: {current_step.to_human_readable()}", "frame_processor")

        # 1. Construct the introductory part of the prompt
        prompt_intro = """Analyze the following sequence of video frames to determine the user's progress on their current task.

You are an AI assistant helping to monitor an Augmented Reality (AR) guided task sequence. I'll provide:
1. The previous, current, and next steps in the task sequence
2. Up to three recent video frames (current moment, 1 second ago, and 2 seconds ago)

Your job is to analyze whether the user is:
- Correctly executing the current task
- Has completed the current task and ready to move to the next
- Has become derailed or is performing the wrong action
"""

        # 2. Add previous, current, and next task information
        if is_first_step:
            prompt_tasks = f"""
TASK CONTEXT:
- This is the first step of the human's goal
- Current step: {current_step.to_human_readable()}
- Next step: {next_step.to_human_readable()}
"""
        else:
            prompt_tasks = f"""
TASK CONTEXT:
- Previous step: {previous_step.to_human_readable()}
- Current step: {current_step.to_human_readable()}
- Next step: {next_step.to_human_readable()}
"""

        # 3. Add the required response format instructions
        prompt_format_instructions = """
RESPONSE FORMAT:
Return a JSON object with the following structure based on your analysis:

If the user is correctly working on the current task:
{
    "status": "executing_task"
}

If the user has completed the current task and should proceed to the next step:
{
    "status": "completed_task"
}

If the user is doing something incorrect or unrelated to the current task:
{
    "status": "derailed",
    "focus_objects": ["object1", "object2"],  
    "action": "precise action description with these objects"
}

In all cases, the status field is required. The focus_objects and action fields are only required for "derailed" status.
"""

        # Combine all parts of the prompt
        prompt_text = f"{prompt_intro}\n{prompt_tasks}\n{prompt_format_instructions}"

        # Get image paths from video_state
        # Assuming get_images() returns a list of paths, newest last.
        # We'll take up to the 3 most recent images as suggested by the prompt ("current", "1s ago", "2s ago")
        all_image_paths = video_state.get_images()
        
        # Log how many images we have
        log_message("info", f"Processing {len(all_image_paths)} images from video state", "frame_processor")
        
        # Ensure we only pass paths that exist or handle appropriately in OpenAI.frameAnalysis
        # OpenAI.frameAnalysis takes a list of paths; if empty, it sends a text-only prompt.
        image_paths_to_send = all_image_paths[-3:] if all_image_paths else []
        
        # Log the most recent image to the GUI
        if image_paths_to_send and allow_visualization:
            latest_image_path = image_paths_to_send[-1]
            
            try:
                # Load the image for visualization
                img = Image.open(latest_image_path)
                
                # Create a visualization with task info
                vis_img = img.copy()
                draw = ImageDraw.Draw(vis_img)
                
                # Add a text overlay with task information
                text = f"Task: {task_state.task.name}\nStep {task_state.index + 1}: {current_step.get_action()}"
                
                # Add semi-transparent overlay at top
                overlay_height = 60
                draw.rectangle([(0, 0), (vis_img.width, overlay_height)], fill=(0, 0, 0, 128))
                
                # Add text
                try:
                    # Try to use a system font
                    font = ImageFont.truetype("Arial", 16)
                except:
                    # Fall back to default font
                    font = ImageFont.load_default()
                    
                draw.text((10, 10), text, fill=(255, 255, 255), font=font)
                
                # Save the visualization
                tmp_dir = os.path.join(os.getcwd(), "media", "tmp_frames")
                os.makedirs(tmp_dir, exist_ok=True)
                vis_path = os.path.join(tmp_dir, f"frame_process_{uuid.uuid4()}.jpg")
                vis_img.save(vis_path)
                
                # Log the visualization to the GUI
                metadata = {
                    "width": vis_img.width,
                    "height": vis_img.height,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "visualization": True,
                    "task_name": task_state.task.name,
                    "step_number": task_state.index + 1,
                    "step_action": current_step.get_action()
                }
                image_received(vis_path, metadata, "frame_processor")
                
            except Exception as e:
                print(f"Error creating frame visualization: {e}")
                traceback.print_exc()
                log_message("error", f"Error creating frame visualization: {str(e)}", "frame_processor")

        try:
            # Call OpenAI for analysis
            response_str = OpenAI.frameAnalysis(prompt=prompt_text, image_paths=image_paths_to_send)
            
            # Parse the response string to extract JSON
            try:
                # Try to parse the entire response as JSON
                response_data = json.loads(response_str)
                
                # Get the status
                status = response_data.get("status", "error")
                
                # Log the result
                log_message("info", f"Frame processing result: {status}", "frame_processor")
                
                # If status is "derailed", log the focus objects and action
                if status == "derailed" and "focus_objects" in response_data:
                    focus_objects = response_data.get("focus_objects", [])
                    action = response_data.get("action", "")
                    log_message("warning", f"User is derailed. Focus on: {', '.join(focus_objects)}", "frame_processor")
                    log_message("warning", f"Suggested action: {action}", "frame_processor")
                
                # Create visualization of latest frame with result
                if image_paths_to_send and allow_visualization:
                    try:
                        # Load the image
                        img = Image.open(image_paths_to_send[-1])
                        
                        # Create visualization
                        vis_img = img.copy()
                        draw = ImageDraw.Draw(vis_img)
                        
                        # Add a colored overlay at bottom based on status
                        overlay_height = 80
                        overlay_y = vis_img.height - overlay_height
                        
                        # Color based on status
                        if status == "executing_task":
                            color = (0, 128, 0, 180)  # Green
                            text = "Status: EXECUTING TASK"
                        elif status == "completed_task":
                            color = (0, 0, 255, 180)  # Blue
                            text = "Status: COMPLETED TASK"
                        elif status == "derailed":
                            color = (255, 0, 0, 180)  # Red
                            text = "Status: DERAILED"
                            # Add additional info for derailed status
                            if "focus_objects" in response_data:
                                focus_objects = response_data.get("focus_objects", [])
                                text += f"\nFocus on: {', '.join(focus_objects)}"
                        else:
                            color = (128, 128, 128, 180)  # Gray
                            text = "Status: ERROR"
                            
                        # Draw overlay
                        draw.rectangle([(0, overlay_y), (vis_img.width, vis_img.height)], fill=color)
                        
                        # Add text
                        try:
                            font = ImageFont.truetype("Arial", 16)
                        except:
                            font = ImageFont.load_default()
                            
                        draw.text((10, overlay_y + 10), text, fill=(255, 255, 255), font=font)
                        
                        # Save visualization
                        vis_result_path = os.path.join(tmp_dir, f"result_{uuid.uuid4()}.jpg")
                        vis_img.save(vis_result_path)
                        
                        # Log visualization to GUI
                        result_metadata = {
                            "width": vis_img.width,
                            "height": vis_img.height,
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "visualization": True,
                            "status": status
                        }
                        image_received(vis_result_path, result_metadata, "frame_processor")
                        
                    except Exception as e:
                        print(f"Error creating result visualization: {e}")
                        traceback.print_exc()
                        log_message("error", f"Error creating result visualization: {str(e)}", "frame_processor")
                
                # Return the status
                return status
                
            except json.JSONDecodeError:
                # If the response isn't valid JSON, try to extract JSON from the text
                import re
                json_match = re.search(r'{.*}', response_str, re.DOTALL)
                if json_match:
                    try:
                        json_str = json_match.group(0)
                        response_data = json.loads(json_str)
                        
                        # Get and log the status
                        status = response_data.get("status", "error")
                        log_message("info", f"Frame processing result: {status}", "frame_processor")
                        
                        # Return the status
                        return status
                        
                    except json.JSONDecodeError:
                        # If we still can't parse the JSON, return an error
                        print("Error: Failed to parse JSON from extracted text")
                        traceback.print_exc()
                        log_message("error", "Failed to parse JSON from response", "frame_processor")
                        return "error"
                else:
                    # No JSON-like structure found
                    print("Error: No JSON-like structure found in response")
                    log_message("error", "No JSON structure found in response", "frame_processor")
                    return "error"
            
        except RuntimeError as e:
            # Log the error or handle it as per application requirements
            error_msg = f"Error during OpenAI frame analysis: {e}"
            print(error_msg)
            traceback.print_exc()
            log_message("error", error_msg, "frame_processor")
            
            return "error"
            
        except Exception as e:
            error_msg = f"An unexpected error occurred in processFrame: {e}"
            print(error_msg)
            traceback.print_exc()
            log_message("error", error_msg, "frame_processor")
            
            return "error"

    @staticmethod
    def handle_analysis_result(result: TaskStatus, task_state: 'TaskState') -> None:
        """
        Example method showing how to handle the string status returned by processFrame.
        
        Args:
            result: The status string from processFrame
            task_state: The current task state that might need to be updated
        """
        if result == "completed_task":
            # If task is completed, we might want to advance to the next step
            task_state.moveToNextStep()
            print(f"Task completed! Moving to next step: {task_state.getCurrentStep()}")
        
        elif result == "executing_task":
            # User is correctly executing the current task, no action needed
            print(f"User is correctly executing: {task_state.getCurrentStep()}")
        
        elif result == "derailed":
            # User is doing something wrong, log the issue
            print(f"User is derailed from task: {task_state.getCurrentStep()}")
        
        elif result == "error":
            # Handle errors
            print("Error in processing frame")

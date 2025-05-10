from typing import TYPE_CHECKING
from states.VideoState import VideoState
from models.openai import OpenAI # Added import for OpenAI

if TYPE_CHECKING:
    from states.TaskState import TaskState # Forward reference for TaskState

class processFrame:
    """A class to process video frames in conjunction with task and video states."""

    @staticmethod
    def processFrame(task_state: 'TaskState', video_state: VideoState) -> str:
        """
        Processes a frame based on the current task and video state by constructing
        a prompt for an AI model and returning the model's analysis.

        Args:
            task_state: The current state of the task.
            video_state: The current state of the video (e.g., recent frames).

        Returns:
            A string representing the AI's analysis of the frame based on the task.
        """
        previous_step = task_state.getPreviousStep()
        current_step = task_state.getCurrentStep()
        next_step = task_state.getNextStep()

        # 1. Construct the introductory part of the prompt
        prompt_intro = "I will send you a list of previous tasks as well as the current task and the next task. Additionally I will send you the current live video frame plus the video frame from one second ago and two seconds ago. Your job is to tell me whether the person has completed the current task or is doing something wrong or something else entirely instead of the current task."

        # 2. Add previous, current, and next task information
        prompt_tasks = f"""
                        Previous tasks: {str(previous_step)}
                        Current task: {str(current_step)}
                        Next task: {str(next_step)}
                        """

        # 3. Add the required response format instructions
        prompt_format_instructions = """
                        I need your answer to follow this format in case the person is doing the current task:
                        {
                            "status": "working"
                        }
                        If the person completed the current task:
                        {
                            "status": "completed"
                        }
                        If the person is doing something wrong or something else that they shouldn't be doing based off of the supposed current task. Please also add the focus objects (the objects the need to manipulate) and what to do with them
                        {
                            "status": "derailed"
                            "focus_objects": ["bottle opener", "desk"],  
                            "action": "place bottle opener on desk"
                        }
                        """

        # Combine all parts of the prompt
        prompt_text = f"{prompt_intro}\n{prompt_tasks}\n{prompt_format_instructions}"

        # Get image paths from video_state
        # Assuming get_images() returns a list of paths, newest last.
        # We'll take up to the 3 most recent images as suggested by the prompt ("current", "1s ago", "2s ago")
        all_image_paths = video_state.get_images()
        # Ensure we only pass paths that exist or handle appropriately in OpenAI.frameAnalysis
        # OpenAI.frameAnalysis takes a list of paths; if empty, it sends a text-only prompt.
        image_paths_to_send = all_image_paths[-3:] if all_image_paths else []


        try:
            # Call OpenAI for analysis
            analysis_result = OpenAI.frameAnalysis(prompt=prompt_text, image_paths=image_paths_to_send)
            return analysis_result
        except RuntimeError as e:
            # Log the error or handle it as per application requirements
            print(f"Error during OpenAI frame analysis: {e}")
            # You might want to return a specific error message or re-raise
            return f'{{"status": "error", "message": "Failed to analyze frame: {str(e)}"}}'
        except Exception as e:
            print(f"An unexpected error occurred in processFrame: {e}")
            return f'{{"status": "error", "message": "Unexpected error in frame processing: {str(e)}"}}'

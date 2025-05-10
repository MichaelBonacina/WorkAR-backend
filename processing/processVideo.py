from tasks.Task import Task
from models.gemini import Gemini # Import Gemini class
import json # For parsing JSON response
import os # For getting basename of video file

class processVideo:
    @staticmethod
    def processVideo(video_file: str) -> Task:
        """Processes a video file using Gemini API and returns a Task object."""
        print(f"Processing video file: {video_file}")

        prompt = ("""
                    I need a step by step guide of what was done in this video.
                    Here is an example task list for making a iced chai latte. Please return valid json:
                    {
                        "steps": [
                        {
                            "focus_objects": ["ice bag", "cup"],
                            "action": "fill ice into cup"
                        },
                        {
                            "focus_objects": ["milk", "cup"],
                            "action": "pour milk into cup"
                        },
                        {
                            "focus_objects": ["syrup", "cup"],
                            "action": "pour syrup into cup"
                        }
                        ]
                    }"""
        )

        task_name_base = os.path.basename(video_file)
        analysis_result = None # Define in broader scope for use in except blocks

        try:
            print(f"Calling Gemini API for video: {video_file}")
            analysis_result = Gemini.videoAnalysis(prompt=prompt, video_file=video_file)

            if isinstance(analysis_result, dict) and 'error' in analysis_result:
                error_msg = str(analysis_result['error'])
                print(f"Error from Gemini API: {error_msg}")
                error_step = {"action": "API Error", "focus_objects": [error_msg]}
                task_object = Task(name=f"{task_name_base} - API Error", task_list=[error_step])
                return task_object
            
            if not isinstance(analysis_result, str):
                error_msg = f"Expected string, got {type(analysis_result)}"
                print(f"Unexpected response type from Gemini API: {type(analysis_result)}")
                error_step = {"action": "Unexpected API Response", "focus_objects": [error_msg]}
                task_object = Task(name=f"{task_name_base} - API Response Error", task_list=[error_step])
                return task_object

            print("Parsing JSON response from Gemini...")
            # Strip markdown code block if present
            if analysis_result.strip().startswith("```json"):
                analysis_result = analysis_result.strip()[7:] # Remove ```json
                if analysis_result.strip().endswith("```"):
                    analysis_result = analysis_result.strip()[:-3] # Remove ```
            
            parsed_json = json.loads(analysis_result.strip())
            
            if isinstance(parsed_json, dict) and "steps" in parsed_json and isinstance(parsed_json["steps"], list):
                actual_steps_list = parsed_json["steps"]
                task_object = Task(name=task_name_base, task_list=actual_steps_list)
                print(f"Successfully created Task: {task_object.name} with {len(actual_steps_list)} steps.")
            else:
                malformed_response_detail = str(analysis_result)[:200] + ("..." if len(str(analysis_result)) > 200 else "")
                #error_msg = f"Expected '{{"steps": [...]}}' structure, received: {malformed_response_detail}"
                print(f"Unexpected JSON structure from Gemini. {error_msg}")
                error_step = {"action": "Malformed JSON from API", "focus_objects": [error_msg]}
                task_object = Task(name=f"{task_name_base} - Malformed API JSON", task_list=[error_step])
            return task_object

        except json.JSONDecodeError as e:
            error_msg = f"Error decoding JSON from Gemini API: {str(e)}"
            response_snippet = str(analysis_result)[:200] + ("..." if len(str(analysis_result)) > 200 else "")
            print(error_msg)
            print(f"Received (snippet): {response_snippet}")
            error_step = {"action": "JSON Parsing Failed", "focus_objects": [error_msg, f"Response snippet: {response_snippet}"]}
            task_object = Task(name=f"{task_name_base} - JSON Error", task_list=[error_step])
            return task_object
        except Exception as e:
            error_msg = f"An unexpected error occurred in processVideo: {str(e)}"
            print(error_msg)
            error_step = {"action": "Unexpected Processing Error", "focus_objects": [error_msg]}
            task_object = Task(name=f"{task_name_base} - Unexpected Error", task_list=[error_step])
            return task_object

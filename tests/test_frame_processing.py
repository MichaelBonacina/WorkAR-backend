import sys
import os

# Add the project root to sys.path to allow for imports
# Assumes the tests directory is directly under the project root (AR3)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from processing.processFrame import processFrame
from states.VideoState import VideoState
from states.TaskState import TaskState
from tasks.Task import Task
from tasks.Step import Step # Though Task can handle dicts, good for clarity if needed
from dotenv import load_dotenv

def test_frame_processing():
    """Tests the processFrame function with a predefined task list and empty video state."""
    load_dotenv() # Ensure environment variables like OPENAI_API_KEY are loaded
    print("Starting frame processing test...")

    # 1. Create VideoState object and add test image
    video_state = VideoState()
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    
    image_path_oldest = os.path.join(desktop_path, "ar-image.png")
    image_path_middle = os.path.join(desktop_path, "ar-image2.png")
    image_path_newest = os.path.join(desktop_path, "ar-image3.png")

    video_state.add_image(image_path_oldest) # Oldest
    video_state.add_image(image_path_middle) # Middle
    video_state.add_image(image_path_newest) # Newest
    
    print(f"Created VideoState: {video_state}")
    print(f"Added oldest image: {image_path_oldest}")
    print(f"Added middle image: {image_path_middle}")
    print(f"Added newest image: {image_path_newest}")

    # 2. Define the task list based on the provided terminal output
    raw_steps_data = [
        {"action": "open bottle with bottle opener", "focus_objects": ["bottle", "bottle opener"]},
        {"action": "place bottle opener on table", "focus_objects": ["bottle opener", "table"]},
        {"action": "pick up glass from table", "focus_objects": ["glass", "table"]},
        {"action": "pour liquid from bottle into glass", "focus_objects": ["bottle", "glass"]},
        {"action": "place bottle on table", "focus_objects": ["bottle", "table"]},
        {"action": "pick up bottle cap from table", "focus_objects": ["bottle cap", "table"]}
    ]
    
    # The Task class constructor can take a list of dictionaries directly
    task_object = Task(name="Bottle Opening Task", task_list=raw_steps_data)
    print(f"Created Task: {task_object.name} with {len(task_object.task_list)} steps.")

    # 3. Create a TaskState object
    # Let's assume we start at the first step (index 0)
    task_state = TaskState(task=task_object, index=0)
    print(f"Created TaskState at index {task_state.index} for task '{task_state.task.name}'")
    print(f"Current step for test: {task_state.getCurrentStep()}")

    # 4. Call processFrame.processFrame()
    print("\nCalling processFrame.processFrame()...")
    try:
        analysis_result = processFrame.processFrame(task_state, video_state)
        
        # 5. Print the return from processFrame
        print("\n--- Analysis Result from processFrame ---")
        print(analysis_result)
        print("--- End of Analysis Result ---")

    except RuntimeError as e:
        print(f"\nRuntimeError during frame processing test: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during test: {e}")

    print("\nFrame processing test finished.")

if __name__ == "__main__":
    test_frame_processing()

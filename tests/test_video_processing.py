import sys
import os
from dotenv import load_dotenv

# Add the project root to sys.path to allow for imports from processing and tasks
# Assumes the tests directory is directly under the project root (AR3)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from processing.processVideo import processVideo
from tasks.Task import Task # Though not directly used here, good to ensure it can be found if processVideo returns it

def test_video_processing():
    """
    Tests the processVideo function with a video from the user's desktop.
    """
    load_dotenv()
    print("Starting video processing test...")
    
    # Construct the path to the video on the desktop
    # User's workspace is /Users/michaelbonacina/Desktop/AR3
    # Desktop path should be /Users/michaelbonacina/Desktop/
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    video_file_path = os.path.join(desktop_path, "video1.MOV")

    print(f"Attempting to process video: {video_file_path}")

    if not os.path.exists(video_file_path):
        print(f"ERROR: Video file not found at {video_file_path}")
        print("Please ensure 'video1.MOV' exists on your Desktop.")
        # Create a dummy error Task object to simulate what processVideo might return on error
        error_task = Task(name="File Not Found Error", task_list=[{
            "action": "File Access Error",
            "focus_objects": [f"Video file not found at {video_file_path}"]
        }])
        print("\nResulting Task Object (Error Simulation):")
        print(error_task)
        return

    try:
        # Call the processVideo method
        # This assumes GOOGLE_API_KEY is set in your environment
        print("\nEnsure your GOOGLE_API_KEY environment variable is set before running.")
        resulting_task = processVideo.processVideo(video_file_path)

        print("\nVideo processing finished.")
        print("Resulting Task Object:")
        print(resulting_task) # The __repr__ of Task should print its contents

        if resulting_task and resulting_task.task_list:
            print("\nIndividual Steps:")
            for i, step in enumerate(resulting_task.task_list):
                print(f"  Step {i+1}:")
                action = step.get_action()
                focus_objects = step.get_focus_objects()
                print(f"    Action: {action}")
                print(f"    Focus Objects: {focus_objects}")
        else:
            print("  No steps found in the task or task is None.")
            
    except Exception as e:
        print(f"\nAn error occurred during the test execution: {e}")
        # Create a dummy error Task object
        error_task = Task(name="Test Execution Error", task_list=[{
            "action": "Test Script Error",
            "focus_objects": [str(e)]
        }])
        print("\nResulting Task Object (Test Error):")
        print(error_task)

if __name__ == "__main__":
    test_video_processing() 
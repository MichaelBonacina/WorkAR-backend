import sys
import os
from dotenv import load_dotenv

# Add the project root to sys.path to allow for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from processing.processVideo import processVideo
from processing.processFrame import processFrame
from tasks.Task import Task
from states.TaskState import TaskState
from states.VideoState import VideoState

def test_end2end():
    """
    Performs an end-to-end test:
    1. Processes a video to get a Task object.
    2. Uses this Task to create a TaskState.
    3. Creates a VideoState with predefined images.
    4. Calls processFrame with these states.
    """
    load_dotenv() # Load OPENAI_API_KEY and GOOGLE_API_KEY
    print("Starting end-to-end test...")

    # --- Part 1: Video Processing (similar to test_video_processing.py) ---
    print("\n--- Stage 1: Video Processing ---")
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    video_file_path = os.path.join(desktop_path, "video1.MOV")

    print(f"Attempting to process video: {video_file_path}")

    resulting_task: Task = None # Initialize to None

    if not os.path.exists(video_file_path):
        print(f"ERROR: Video file not found at {video_file_path}. Cannot proceed with end-to-end test.")
        # Create a dummy error Task object to allow the test structure to complete if needed for other checks
        # but for an e2e test, this usually means failure.
        resulting_task = Task(name="File Not Found Error", task_list=[{
            "action": "File Access Error",
            "focus_objects": [f"Video file not found at {video_file_path}"]
        }])
        print("Resulting Task Object (Error Simulation from Video Processing):")
        print(resulting_task)
        print("End-to-end test cannot fully complete due to missing video file.")
        return # Exit if video file is not found

    try:
        print("\nEnsure your GOOGLE_API_KEY environment variable is set for video processing.")
        resulting_task = processVideo.processVideo(video_file_path)

        print("\nVideo processing finished.")
        print("Resulting Task Object from video processing:")
        print(resulting_task) # The __repr__ of Task should print its contents

        if resulting_task and resulting_task.task_list:
            print("\nIndividual Steps from Video Processing:")
            for i, step in enumerate(resulting_task.task_list):
                print(f"  Step {i+1}:")
                action = step.get_action()
                focus_objects = step.get_focus_objects()
                print(f"    Action: {action}")
                print(f"    Focus Objects: {focus_objects}")
        else:
            print("  No steps found in the task from video processing or task is None.")
            print("End-to-end test cannot proceed to frame processing without a valid task.")
            return # Exit if no valid task
            
    except Exception as e:
        print(f"\nAn error occurred during the video processing stage: {e}")
        # Create a dummy error Task object
        resulting_task = Task(name="Video Processing Error", task_list=[{
            "action": "Video Processing Script Error",
            "focus_objects": [str(e)]
        }])
        print("Resulting Task Object (Error from Video Processing):")
        print(resulting_task)
        print("End-to-end test cannot proceed to frame processing due to video processing error.")
        return # Exit on video processing error

    # --- Part 2: Frame Processing (using the Task from Part 1 and VideoState from test_frame_processing.py) ---
    if not (resulting_task and resulting_task.task_list): # Double check, though prior returns should catch this
        print("Skipping frame processing as no valid task was generated from video processing.")
        print("\nEnd-to-end test concluded (partially due to video processing issues).")
        return

    print("\n--- Stage 2: Frame Processing ---")
    
    # 1. Create TaskState from the video processing result
    task_state = TaskState(task=resulting_task, index=0) # Start with the first step
    print(f"Created TaskState at index {task_state.index} for task '{task_state.task.name}'")
    print(f"Current step for frame processing: {task_state.getCurrentStep()}")

    # 2. Create VideoState with predefined images (as in test_frame_processing.py)
    video_state = VideoState()
    image_path_oldest = os.path.join(desktop_path, "ar-image.png")
    image_path_middle = os.path.join(desktop_path, "ar-image2.png")
    image_path_newest = os.path.join(desktop_path, "ar-image3.png")

    # Check if images exist before adding
    images_to_add = []
    if os.path.exists(image_path_oldest):
        images_to_add.append(image_path_oldest)
    else:
        print(f"WARNING: Image not found: {image_path_oldest}")
    if os.path.exists(image_path_middle):
        images_to_add.append(image_path_middle)
    else:
        print(f"WARNING: Image not found: {image_path_middle}")
    if os.path.exists(image_path_newest):
        images_to_add.append(image_path_newest)
    else:
        print(f"WARNING: Image not found: {image_path_newest}")
    
    if not images_to_add or len(images_to_add) < 3:
         print(f"ERROR: One or more required images for frame processing not found on Desktop.")
         print(f"Please ensure 'ar-image.png', 'ar-image2.png', and 'ar-image3.png' exist on your Desktop.")
         print("End-to-end test cannot fully complete due to missing image files for frame processing.")
         return

    for img_path in images_to_add:
        video_state.add_image(img_path)
        print(f"Added image to VideoState: {img_path}")
    print(f"Created VideoState with {len(video_state.get_images())} image(s).")

    # 3. Call processFrame.processFrame()
    print("\nCalling processFrame.processFrame()...")
    print("Ensure your OPENAI_API_KEY environment variable is set for frame processing.")
    try:
        frame_analysis_result = processFrame.processFrame(task_state, video_state)
        
        # 4. Print the return from processFrame
        print("\n--- Analysis Result from processFrame ---")
        print(frame_analysis_result)
        print("--- End of Frame Analysis Result ---")

    except RuntimeError as e:
        print(f"\nRuntimeError during frame processing stage: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during frame processing stage: {e}")

    print("\nEnd-to-end test finished.")


import asyncio
import websockets
import json
import os
import uuid
from states.VideoState import VideoState
from states.TaskState import TaskState
from tasks.Task import Task
from processing.processFrame import processFrame

# --- Global State (Simplified for single active task/user) ---
# This state will be shared by all WebSocket connections.
current_task_object: Task = None
current_task_state: TaskState = None
video_state = VideoState()  # Global video state, new frames will be added here

# Directory to store temporary frames received via WebSocket
# This will be made an absolute path by main.py
TEMP_FRAMES_DIR_NAME = "tmp_frames"
# Fallback if not set by main.py, though main.py should be the source of truth for paths
APP_ROOT_PATH = os.getcwd() 

connected_clients = set()

def _get_temp_frames_abs_dir():
    # Prioritize path set by main.py if available (e.g., via a global config module or passed in)
    # For this structure, we rely on APP_ROOT_PATH being correctly set.
    media_root = os.path.join(APP_ROOT_PATH, "media")
    return os.path.join(media_root, TEMP_FRAMES_DIR_NAME)

def ensure_temp_frames_dir_exists():
    temp_dir = _get_temp_frames_abs_dir()
    if not os.path.exists(temp_dir):
        try:
            os.makedirs(temp_dir, exist_ok=True)
            print(f"Created temporary frames directory: {temp_dir}")
        except OSError as e:
            print(f"Error creating temporary frames directory {temp_dir}: {e}")
            return None
    return temp_dir

# Called by instructionUpload.py to set the current task
def set_active_task_for_websocket(task: Task, initial_index: int = 0):
    global current_task_object, current_task_state, video_state
    current_task_object = task
    if current_task_object and current_task_object.task_list: # Ensure task has steps
        current_task_state = TaskState(task=current_task_object, index=initial_index)
        # Reset video_state for the new task to ensure fresh frames are used
        video_state = VideoState()
        print(f"WebSocket Server: Active task set - '{current_task_object.name}', Step {initial_index + 1}. VideoState reset.")
    else:
        current_task_object = None # Ensure it's None if task is invalid
        current_task_state = None
        print("WebSocket Server: Cleared active task (task was invalid or had no steps).")

async def new_frame_handler(websocket, path):
    connected_clients.add(websocket)
    client_addr = websocket.remote_address
    print(f"Client connected: {client_addr}. Total clients: {len(connected_clients)}")

    temp_frames_abs_dir = ensure_temp_frames_dir_exists()
    if not temp_frames_abs_dir:
        print(f"CRITICAL: Temp frames directory missing for {client_addr}. Closing connection.")
        await websocket.close(code=1011, reason="Server configuration error for frame storage.")
        connected_clients.remove(websocket)
        return

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                if not current_task_state:
                    print(f"Frame received from {client_addr}, but no active task. Discarding.")
                    await websocket.send(json.dumps({"error": "No active task set. Please upload and process a video first.", "status": "no_task"}))
                    continue

                unique_filename = f"{uuid.uuid4()}.png"
                image_file_path = os.path.join(temp_frames_abs_dir, unique_filename)

                try:
                    with open(image_file_path, "wb") as f:
                        f.write(message)
                    # print(f"Frame from {client_addr} saved: {image_file_path}")

                    video_state.add_image(image_file_path)
                    # print(f"VideoState updated. Current images for task '{current_task_state.task.name}': {len(video_state.get_images())}")
                    
                    # Call processFrame (from processing.processFrame)
                    analysis_result_str = processFrame.processFrame(current_task_state, video_state)
                    # print(f"Sent to {client_addr}: {analysis_result_str}")
                    await websocket.send(analysis_result_str)

                except Exception as e:
                    print(f"Error processing frame from {client_addr}: {e}")
                    await websocket.send(json.dumps({"error": f"Server error processing frame: {str(e)}"}))
            
            elif isinstance(message, str):
                print(f"Received text message from {client_addr}: {message}. Ignoring, expecting image bytes.")
                # You could add logic here to handle control messages if needed.
                # e.g., if message == 'ping': await websocket.send('pong')

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Client {client_addr} connection closed (Error): {e}")
    except websockets.exceptions.ConnectionClosedOK:
        print(f"Client {client_addr} connection closed (OK).")
    except Exception as e:
        print(f"Unhandled WebSocket error for {client_addr}: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"Client disconnected: {client_addr}. Total clients: {len(connected_clients)}")
        # Consider cleanup of temp files related to this specific client if using session-based storage

async def start_websocket_server_async(host='localhost', port=8765, app_root_override=None):
    global APP_ROOT_PATH
    if app_root_override:
        APP_ROOT_PATH = app_root_override
    else: # Ensure APP_ROOT_PATH is based on this file's location if not overridden
        APP_ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ensure_temp_frames_dir_exists() # Attempt creation at startup

    server = await websockets.serve(new_frame_handler, host, port)
    print(f"WebSocket server started on ws://{host}:{port}")
    print(f"Temporary frames will be stored in: {os.path.join(APP_ROOT_PATH, 'media', TEMP_FRAMES_DIR_NAME)}")
    await server.wait_closed()

# This part is for standalone testing if needed, not directly used by main.py
if __name__ == "__main__":
    print("Starting WebSocket server directly for testing...")
    # Set APP_ROOT_PATH correctly for standalone execution
    # Assumes this script is in AR3/connection/websocket.py, so project root is AR3/
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_for_standalone = os.path.dirname(current_file_dir)
    
    # Create a dummy task for testing
    raw_steps_data = [
        {"action": "Test Step 1: Identify Object", "focus_objects": ["any object"]},
        {"action": "Test Step 2: Describe Object", "focus_objects": ["identified object"]},
    ]
    test_task = Task(name="WebSocket Standalone Test Task", task_list=raw_steps_data)
    set_active_task_for_websocket(test_task)
    
    asyncio.run(start_websocket_server_async(app_root_override=project_root_for_standalone))

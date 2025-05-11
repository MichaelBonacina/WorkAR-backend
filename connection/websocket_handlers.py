"""
WebSocket handlers and state management for real-time frame processing.

This module handles incoming WebSocket connections, processes image frames,
and maintains task state for the AR application.
"""

import json
import os
import uuid
import logging
import traceback
import websockets
import glob
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Union, Tuple
from websockets.server import WebSocketServerProtocol
from processing.ar_glasses_instruction import ARGlassesInstruction
from states.VideoState import VideoState
from states.TaskState import TaskState
from tasks.Task import Task
from processing.processFrame import processFrame
from models.owlv2 import OWLv2
from models.open_vocab_bbox_model import OpenVocabBBoxDetectionModel
from connection.message_queue import message_queue, log_message, image_received, state_changed
from connection.websocket_logger import websocket_logger
import asyncio
import time

# Note: Logging is configured in websocket.py with level from WEBSOCKET_LOG_LEVEL env var

# --- Global State (Simplified for single active task/user) ---
# This state will be shared by all WebSocket connections.
current_task_object: Task = None  # Currently active task
current_task_state: TaskState = None  # Current state including step index
video_state = VideoState()  # Global video state for frame storage

# Directory to store temporary frames received via WebSocket
TEMP_FRAMES_DIR_NAME = "tmp_frames"
# Fallback if not set by main.py
APP_ROOT_PATH = os.getcwd() 

# Set to track all connected clients
connected_clients: Set[WebSocketServerProtocol] = set()

# Create a single OWLv2 model instance to be reused (using the abstract type for type hinting)
bbox_model: OpenVocabBBoxDetectionModel = OWLv2()

# Global flag to track if a frame is currently being processed
is_processing_frame = False # Global flag to track if a frame is currently being processed

# Create a lock for frame processing to prevent race conditions
processing_lock = asyncio.Lock()

def _get_temp_frames_abs_dir() -> str:
    """
    Determines the absolute path to the temporary frames directory.
    
    Returns:
        str: Absolute path to the temporary frames directory
    """
    media_root = os.path.join(APP_ROOT_PATH, "media")
    return os.path.join(media_root, TEMP_FRAMES_DIR_NAME)

def cleanup_client_temp_files(client_frames: List[str]) -> int:
    """
    Removes temporary files associated with a specific client.
    
    Args:
        client_frames: List of file paths to remove
        
    Returns:
        int: Number of files removed
    """
    count = 0
    global video_state
    
    # Only remove files that are not still in use by video_state
    active_images = set(video_state.get_images())
    files_to_remove = [f for f in client_frames if f not in active_images]
    
    for file_path in files_to_remove:
        try:
            Path(file_path).unlink(missing_ok=True)
            count += 1
        except Exception as e:
            logging.error(f"Error removing temporary file {file_path}: {e}")
            log_message("error", f"Error removing temporary file {file_path}: {e}")
    
    if count > 0:
        logging.info(f"Cleaned up {count} temporary frame files")
        log_message("info", f"Cleaned up {count} temporary frame files")
    
    skipped = len(client_frames) - count
    if skipped > 0:
        logging.info(f"Skipped removing {skipped} files still in use by video_state")
        log_message("info", f"Skipped removing {skipped} files still in use by video_state")
    
    return count

def ensure_temp_frames_dir_exists() -> Optional[str]:
    """
    Creates the temporary frames directory if it doesn't exist.
    
    Returns:
        str or None: Path to the temporary frames directory if successful, None otherwise
    """
    temp_dir = _get_temp_frames_abs_dir()
    if not os.path.exists(temp_dir):
        try:
            os.makedirs(temp_dir, exist_ok=True)
            logging.info(f"Created temporary frames directory: {temp_dir}")
            log_message("info", f"Created temporary frames directory: {temp_dir}")
        except OSError as e:
            logging.error(f"Error creating temporary frames directory {temp_dir}: {e}")
            log_message("error", f"Error creating temporary frames directory {temp_dir}: {e}")
            traceback.print_exc()
            return None
    return temp_dir

def set_active_task_for_websocket(task: Task, initial_index: int = 0) -> None:
    """
    Sets the active task for the WebSocket server.
    
    Called by instructionUpload.py to set the active task and initialize task state.
    
    Args:
        task: The Task object containing instruction steps
        initial_index: Starting step index (default: 0)
    """
    global current_task_object, current_task_state, video_state
    current_task_object = task
    if current_task_object and current_task_object.task_list: # Ensure task has steps
        current_task_state = TaskState(task=current_task_object, index=initial_index)
        # Reset video_state for the new task to ensure fresh frames are used
        video_state = VideoState()
        logging.info(f"WebSocket Server: Active task set - '{current_task_object.name}', Step {initial_index + 1}. VideoState reset.")
        
        # Send task state update to GUI
        if current_task_state:
            # Get current step
            current_step = current_task_state.getCurrentStep()
            
            # Publish task state change
            state_changed("task", {
                "task_name": current_task_object.name,
                "current_step": initial_index + 1,
                "total_steps": len(current_task_object.task_list) if current_task_object.task_list else 0,
                "status": "active",
                "step_action": current_step.get_action() if current_step else "None",
                "focus_objects": current_step.get_focus_objects() if current_step else []
            })
            
            log_message("info", f"Task set: {current_task_object.name}, starting at step {initial_index + 1}")
    else:
        current_task_object = None # Ensure it's None if task is invalid
        current_task_state = None
        logging.info("WebSocket Server: Cleared active task (task was invalid or had no steps).")
        log_message("warning", "Cleared active task (task was invalid or had no steps)")

async def log_and_send(websocket: WebSocketServerProtocol, 
                      message: Union[str, Dict[str, Any]], 
                      client_addr: Optional[tuple] = None) -> None:
    """
    Logs an outgoing message in a pretty format and sends it to the client.
    
    Args:
        websocket: The WebSocket connection to send the message to
        message: The message to send (either a string or object to be converted to JSON)
        client_addr: Optional client address for logging
    """
    # Check if the WebSocket is closed before trying to send
    if websocket.state == websockets.protocol.State.CLOSED:
        logging.warning(f"Cannot send message to {client_addr}: WebSocket is closed")
        return
    
    if not isinstance(message, str):
        message = json.dumps(message)
    
    # Try to parse JSON for pretty printing in logs
    try:
        parsed = json.loads(message)
        # Pretty print with 2-space indent for logs
        pretty_json = json.dumps(parsed, indent=2)
        
        # For logging, truncate very large messages
        message_content = pretty_json
        if len(message_content) > 1000:
            # Truncate long messages while preserving the beginning and end
            message_content = f"{message_content[:400]}...[truncated {len(message_content)-800} chars]...{message_content[-400:]}"
        
        client_info = f" to {client_addr}" if client_addr else ""
        logging.debug(f"⟹ Sending message{client_info}:\n{message_content}")
        
        # Log to GUI using message queue
        log_message("info", f"Sending message to client{client_info}", "server")
        
        # Log to file system for debugging
        websocket_logger.log_outgoing_message(parsed)
    except:
        # Fallback if not valid JSON or other error
        logging.debug(f"⟹ Sending message to {client_addr}: [non-JSON data, len={len(message)}]")
        log_message("info", f"Sending message to client {client_addr}: [non-JSON data, len={len(message)}]", "server")
    
    # Send the original (non-pretty) message to the client
    await websocket.send(message)

async def process_frame_with_metadata(
    websocket: WebSocketServerProtocol, 
    image_data: bytes, 
    metadata: Dict[str, Any], 
    client_addr: tuple, 
    temp_frames_abs_dir: str, 
    client_frames: List[str],
    image_file_path: str,
    allow_visualization: bool = True
) -> bool:
    """
    Process a frame with its associated metadata.
    
    Args:
        websocket: The WebSocket connection
        image_data: Binary image data (JPG)
        metadata: JSON metadata associated with the image
        client_addr: Client address for logging
        temp_frames_abs_dir: Directory to store temporary frames
        client_frames: List to track client frame paths
        image_file_path: Path to the saved image file
        allow_visualization: Flag to control visualization output
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    global current_task_state, video_state
    
    # Log incoming metadata in a pretty format
    pretty_metadata = json.dumps(metadata, indent=2)
    logging.info(f"⟸ Received metadata from {client_addr}:\n{pretty_metadata}")
    
    # Log to GUI
    log_message("info", f"Received metadata from {client_addr}", "client")
    
    try:
        # Skip processing if no active task
        if not current_task_state:
            logging.warning(f"Frame received from {client_addr}, but no active task. Discarding.")
            log_message("warning", f"Frame received, but no active task. Discarding.", "server")
            await log_and_send(
                websocket, 
                {"error": "No active task set. Please upload and process a video first.", "status": "no_task"},
                client_addr
            )
            return False

        # Log metadata information
        timestamp = metadata.get("timestamp", "unknown")
        width = metadata.get("width", 0)
        height = metadata.get("height", 0)
        camera_pose = metadata.get("camera_pose", {})
        
        logging.info(f"Frame metadata: timestamp={timestamp}, dimensions={width}x{height}, camera_pose={camera_pose}")
        
        # Store current frame count before adding new image
        frame_count_before = len(video_state.get_images())
        
        # Add to video state
        video_state.add_image(image_file_path)
        logging.debug(f"VideoState updated. Current images for task '{current_task_state.task.name}': {len(video_state.get_images())}")
        
        # Publish video state change to GUI
        state_changed("video", {
            "images": video_state.get_images()
        })
        
        # Check if this is the first frame (frame_count_before was 0)
        if frame_count_before == 0:
            try:
                logging.info("First frame received, sending the first step instruction")
                log_message("info", "First frame received, sending the first step instruction", "server")
                # Create instruction from the first step
                first_step = current_task_state.getCurrentStep()
                first_instruction = ARGlassesInstruction.from_step('executing_task', first_step)
                
                # Add object coordinates to instruction
                found_any_coordinates = first_instruction.addObjectCoordinates(
                    frame=image_file_path,
                    bbox_detection_model=bbox_model,
                    camera_pose=camera_pose,
                    allow_visualization=allow_visualization
                )

                # Log the call with results
                websocket_logger.log_add_object_coordinates_call(
                    frame=image_file_path,
                    camera_pose=camera_pose,
                    allow_visualization=allow_visualization,
                    objects=[obj.to_dict() for obj in first_instruction.objects] if first_instruction.objects else None,
                    result=first_instruction.to_dict()
                )
                
                # Send the instruction to the client
                await log_and_send(websocket, first_instruction.to_json(), client_addr)
                
                # Return early without regular processing
                return True
                
            except Exception as e:
                logging.error(f"Error processing first frame from {client_addr}: {e}")
                log_message("error", f"Error processing first frame: {e}", "server")
                traceback.print_exc()
                # Fall through to regular processing
        
        # Log the processFrame call for debugging (this pre-operation log is redundant)
        # websocket_logger.log_process_frame_call(
        #     task_state=current_task_state,
        #     video_state=video_state,
        #     allow_visualization=allow_visualization
        # )
        
        # Process the frame and send results
        current_status = processFrame.processFrame(current_task_state, video_state, allow_visualization)
        logging.info(f"Current status: {current_status}")
        log_message("info", f"Frame processing result: {current_status}", "server")
        
        # Log the process frame result
        websocket_logger.log_process_frame_call(
            task_state=current_task_state,
            video_state=video_state,
            allow_visualization=allow_visualization,
            result=current_status
        )
        
        # Update task state in GUI
        if current_task_state:
            current_step = current_task_state.getCurrentStep()
            state_changed("task", {
                "task_name": current_task_state.task.name,
                "current_step": current_task_state.index + 1,
                "total_steps": len(current_task_state.task.task_list),
                "status": current_status,
                "step_action": current_step.get_action() if current_step else "None",
                "focus_objects": current_step.get_focus_objects() if current_step else []
            })
        
        if current_status == "derailed":
            try:
                # Get the most recent image path
                latest_image = video_state.get_images()[-1] if video_state.get_images() else None
                if latest_image:
                    instruction = ARGlassesInstruction.from_step('derailed', current_task_state.getCurrentStep())
                    
                    # Add object coordinates
                    found_any_coordinates = instruction.addObjectCoordinates(
                        frame=latest_image, 
                        bbox_detection_model=bbox_model,
                        camera_pose=camera_pose,
                        allow_visualization=allow_visualization
                    )

                    if not found_any_coordinates:
                        logging.warning("No object coordinates found for the derailed frame. Skipping instruction.")
                        log_message("warning", "No object coordinates found for the derailed frame. Skipping instruction.", "server")
                        return True
                    
                    # Log with results
                    websocket_logger.log_add_object_coordinates_call(
                        frame=latest_image,
                        camera_pose=camera_pose,
                        allow_visualization=allow_visualization,
                        objects=[obj.to_dict() for obj in instruction.objects] if instruction.objects else None,
                        result=instruction.to_dict()
                    )
                    
                    await log_and_send(websocket, instruction.to_json(), client_addr)
            except Exception as e:
                logging.error(f"Error finding object coordinates: {e}")
                log_message("error", f"Error finding object coordinates: {e}", "server")
                traceback.print_exc()
        
        elif current_status == "executing_task":
            logging.info("User is correctly executing the current task")
            log_message("info", "User is correctly executing the current task", "server")
            # Create an instruction to inform user they're on the right track
            instruction = ARGlassesInstruction.from_step(
                step=current_task_state.getCurrentStep(),
                current_task_status=current_status
            )
            await log_and_send(websocket, instruction.to_json(), client_addr)
            
        elif current_status == "completed_task":
            logging.info("User has completed the current task. Sending them the next task.")
            log_message("info", "User has completed the current task. Moving to next step.", "server")
            # shift index to next step
            next_step = current_task_state.moveToNextStep()

            # build the next step json
            next_instruction = ARGlassesInstruction.from_step('completed_task', next_step)
            
            # Get the most recent image path to detect object coordinates
            try:
                latest_image = video_state.get_images()[-1] if video_state.get_images() else None
                if latest_image:
                    # Add object coordinates to the next instruction
                    next_instruction = next_instruction.addObjectCoordinates(
                        frame=latest_image,
                        bbox_detection_model=bbox_model,
                        camera_pose=camera_pose,
                        allow_visualization=allow_visualization
                    )
                    
                    # Log with results
                    websocket_logger.log_add_object_coordinates_call(
                        frame=latest_image,
                        camera_pose=camera_pose,
                        allow_visualization=allow_visualization,
                        objects=[obj.to_dict() for obj in next_instruction.objects] if next_instruction.objects else None,
                        result=next_instruction.to_dict()
                    )
                    
                    logging.info(f"Added object coordinates for next step with {len(next_instruction.objects) if next_instruction.objects else 0} objects")
            except Exception as e:
                logging.error(f"Error finding object coordinates for next step: {e}")
                log_message("error", f"Error finding object coordinates for next step: {e}", "server")
                traceback.print_exc()
                
            # Send to client
            await log_and_send(websocket, next_instruction.to_json(), client_addr)
            
            # Update task state in GUI after step change
            if current_task_state:
                current_step = current_task_state.getCurrentStep()
                state_changed("task", {
                    "task_name": current_task_state.task.name,
                    "current_step": current_task_state.index + 1,
                    "total_steps": len(current_task_state.task.task_list),
                    "status": "active",  # Reset status for new step
                    "step_action": current_step.get_action() if current_step else "None",
                    "focus_objects": current_step.get_focus_objects() if current_step else []
                })
            
        elif current_status == "error":
            logging.error("Error occurred during frame processing")
            log_message("error", "Error occurred during frame processing", "server")
            # Create an error instruction 
            instruction = ARGlassesInstruction(
                current_task_status=current_status,
                message="An error occurred during processing"
            )
            await log_and_send(websocket, instruction.to_json(), client_addr)
            
        else:
            logging.warning(f"Unknown task status: {current_status}")
            log_message("warning", f"Unknown task status: {current_status}", "server")
            # Create an instruction for unknown status
            instruction = ARGlassesInstruction(
                current_task_status="error",
                message=f"Unknown task status: {current_status}"
            )
            await log_and_send(websocket, instruction.to_json(), client_addr)

        return True

    except Exception as e:
        logging.error(f"Error processing frame from {client_addr}: {e}")
        log_message("error", f"Error processing frame: {str(e)}", "server")
        traceback.print_exc()
        await log_and_send(
            websocket, 
            {"error": f"Server error processing frame: {str(e)}"},
            client_addr
        )
        return False

async def new_frame_handler(websocket: WebSocketServerProtocol, path: Optional[str] = None) -> None:
    """
    WebSocket connection handler that processes incoming image frames with metadata.
    
    Expects a pattern of:
    1. JSON metadata message
    2. Binary JPG image data
    
    Args:
        websocket: The WebSocket connection object
        path: The connection path (unused but was required by older websockets versions)
    """
    connected_clients.add(websocket)
    client_addr = websocket.remote_address
    client_frames: List[str] = []  # Track frames for this client
    logging.info(f"Client connected: {client_addr}. Total clients: {len(connected_clients)}")
    log_message("info", f"Client connected: {client_addr}. Total clients: {len(connected_clients)}", "server")
    
    # Update server state for GUI
    state_changed("server", {
        "connected_clients": len(connected_clients),
        "client_addresses": [str(client.remote_address) for client in connected_clients]
    })

    # Ensure temp directory exists
    temp_frames_abs_dir = ensure_temp_frames_dir_exists()
    if not temp_frames_abs_dir:
        logging.critical(f"CRITICAL: Temp frames directory missing for {client_addr}. Closing connection.")
        log_message("error", f"CRITICAL: Temp frames directory missing. Closing connection.", "server")
        await websocket.close(code=1011, reason="Server configuration error for frame storage.")
        connected_clients.remove(websocket)
        
        # Update server state for GUI
        state_changed("server", {
            "connected_clients": len(connected_clients),
            "client_addresses": [str(client.remote_address) for client in connected_clients]
        })
        return
    
    # Track the expected message type (metadata or image)
    expecting_metadata = True
    current_metadata: Optional[Dict[str, Any]] = None
    
    try:
        # Process messages from this connection
        async for message in websocket:
            if expecting_metadata and isinstance(message, str):
                # First message should be metadata JSON
                try:
                    current_metadata = json.loads(message)
                    # Pretty print metadata for logging
                    pretty_metadata = json.dumps(current_metadata, indent=2)
                    expecting_metadata = False  # Next message should be image data
                    
                    # Log incoming message to file system
                    websocket_logger.log_incoming_message(current_metadata)
                    
                except json.JSONDecodeError as e:
                    logging.error(f"⟸ Invalid metadata JSON from {client_addr}: {e}")
                    log_message("error", f"Invalid metadata JSON: {e}", "client")
                    await log_and_send(
                        websocket, 
                        {"error": "Invalid metadata format. Expected valid JSON."},
                        client_addr
                    )
                    expecting_metadata = True  # Reset, expecting metadata again
                    current_metadata = None
                    
            elif not expecting_metadata and isinstance(message, bytes):
                # Second message should be binary image data
                # Log the image data size immediately
                logging.info(f"⟸ Received image data from {client_addr}: {len(message)/1024:.1f} KB")
                log_message("info", f"Received image data: {len(message)/1024:.1f} KB", "client")
                
                # Generate unique filename and save the image immediately
                unique_filename = f"{uuid.uuid4()}.jpg"
                image_file_path = os.path.join(temp_frames_abs_dir, unique_filename)
                
                try:
                    # Save image immediately
                    with open(image_file_path, "wb") as f:
                        f.write(message)
                    client_frames.append(image_file_path)  # Track this frame for later cleanup
                    
                    # Log incoming image to file system
                    websocket_logger.log_incoming_image(message, current_metadata)
                    
                    # Notify GUI about the received image immediately
                    image_received(image_file_path, current_metadata, str(client_addr))
                    
                    logging.info(f"Image from {client_addr} immediately saved: {image_file_path}")
                    
                    # Give the GUI event loop a chance to process the queue and update display
                    # by delaying the processing slightly
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logging.error(f"Error saving image from {client_addr}: {e}")
                    log_message("error", f"Error saving image: {e}", "server")
                    expecting_metadata = True
                    current_metadata = None
                    continue
                
                # Check if the lock is already held (processor is busy)
                if processing_lock.locked():
                    logging.info(f"⟸ Processor busy, dropping frame from {client_addr}")
                    log_message("warning", f"Processor busy, dropping frame", "server")
                    expecting_metadata = True  # Reset, expecting metadata again
                    current_metadata = None
                    continue

                # Create a copy of the metadata and other values needed for processing
                metadata_copy = current_metadata.copy() if current_metadata else {}
                
                # Reset state for next frame before processing begins
                expecting_metadata = True
                current_metadata = None
                
                # Process the frame while holding the lock
                async with processing_lock:
                    await process_frame_with_metadata(
                        websocket,
                        message,
                        metadata_copy,
                        client_addr,
                        temp_frames_abs_dir,
                        client_frames,
                        image_file_path,
                        True  # Always allow visualization
                    )
                    
            else:
                # Handle unexpected message type
                if expecting_metadata:
                    if isinstance(message, bytes):
                        logging.warning(f"Received binary data from {client_addr} when expecting metadata JSON. Ignoring.")
                        log_message("warning", "Received binary data when expecting metadata JSON", "client")
                    # String message was handled above
                else:
                    if isinstance(message, str):
                        logging.warning(f"Received text from {client_addr} when expecting image data. Ignoring.")
                        log_message("warning", "Received text when expecting image data", "client")
                        expecting_metadata = True  # Reset, expecting metadata again
                        current_metadata = None

    except websockets.exceptions.ConnectionClosedError as e:
        logging.info(f"Client {client_addr} connection closed (Error): {e}")
        log_message("info", f"Client connection closed (Error): {e}", "server")
    except websockets.exceptions.ConnectionClosedOK:
        logging.info(f"Client {client_addr} connection closed (OK).")
        log_message("info", "Client connection closed (OK)", "server")
    except Exception as e:
        logging.error(f"Unhandled WebSocket error for {client_addr}: {e}")
        log_message("error", f"Unhandled WebSocket error: {e}", "server")
        traceback.print_exc()
    finally:
        # Clean up client connection
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        
        # Update server state for GUI
        state_changed("server", {
            "connected_clients": len(connected_clients),
            "client_addresses": [str(client.remote_address) for client in connected_clients]
        })
        
        # Clean up temp files for this client
        cleanup_client_temp_files(client_frames)
        
        logging.info(f"Client disconnected: {client_addr}. Total clients: {len(connected_clients)}")
        log_message("info", f"Client disconnected: {client_addr}. Total clients: {len(connected_clients)}", "server")
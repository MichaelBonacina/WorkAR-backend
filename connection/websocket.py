"""
WebSocket server for AR application.

This module configures and starts the WebSocket server, handling 
environment variables and path resolution. The actual connection and 
frame processing logic is in websocket_handlers.py.
"""

import asyncio
import websockets
import os
import logging
import shutil
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging with configurable level
log_level_name = os.getenv('WEBSOCKET_LOG_LEVEL', 'INFO')
log_level = getattr(logging, log_level_name.upper(), logging.INFO)
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m-%d %H:%M:%S',
    level=log_level
)
logging.info(f"Logging level set to: {logging.getLevelName(log_level)}")

from connection.websocket_handlers import (
    new_frame_handler, 
    set_active_task_for_websocket,
    ensure_temp_frames_dir_exists,
    APP_ROOT_PATH as handlers_app_root_path
)

# Import the WebSocket logger (will be initialized later)
from connection.websocket_logger import websocket_logger

# Import GUI components
from connection.gui_app import get_gui_instance, run_gui_with_async
from connection.message_queue import log_message

# Max message size for WebSocket (configurable via .env)
MAX_MESSAGE_SIZE = int(os.getenv('WEBSOCKET_MAX_SIZE', 1024 * 1024 * 1))  # Default: 1MB in bytes

# Directory for temporary frames - will be updated in start_websocket_server_async
APP_ROOT_PATH = os.getcwd()

async def start_websocket_server_async(host='0.0.0.0', port=8765, app_root_override=None, launch_gui=True):
    """
    Configures and starts the WebSocket server.
    
    Args:
        host: Hostname to bind the server (default: '0.0.0.0', override with WEBSOCKET_HOST)
        port: Port to bind the server (default: 8765, override with WEBSOCKET_PORT)
        app_root_override: Optional path override for the application root directory
        launch_gui: Whether to launch the GUI (default: True)
        
    Returns:
        None: The function runs until the server is stopped
    """
    global APP_ROOT_PATH
    
    # Allow host and port to be configured through environment variables
    host = os.getenv('WEBSOCKET_HOST', host)
    port = int(os.getenv('WEBSOCKET_PORT', port))
    
    # Set APP_ROOT_PATH for both this module and the handlers module
    if app_root_override:
        APP_ROOT_PATH = app_root_override
        # Update APP_ROOT_PATH in handlers
        handlers_app_root_path = app_root_override
    else: 
        # Ensure APP_ROOT_PATH is based on this file's location if not overridden
        APP_ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Update APP_ROOT_PATH in handlers
        handlers_app_root_path = APP_ROOT_PATH

    # Initialize websocket logger with base directory in the app root
    websocket_logs_path = os.path.join(APP_ROOT_PATH, "websocket_logs")
    # Re-initialize the logger with the correct path
    websocket_logger._base_dir = Path(websocket_logs_path)
    websocket_logger._incoming_dir = websocket_logger._base_dir / "incoming_messages"
    websocket_logger._outgoing_dir = websocket_logger._base_dir / "outgoing_messages"
    websocket_logger._analysis_dir = websocket_logger._base_dir / "analysis_calls"
    websocket_logger._initialize_directories()
    
    logging.info(f"WebSocket debug logs will be saved to: {websocket_logs_path}")
    log_message("info", f"WebSocket debug logs will be saved to: {websocket_logs_path}", "server")

    # Create temporary directories if they don't exist
    ensure_temp_frames_dir_exists()
    
    # Create task to start the WebSocket server
    server_task = asyncio.create_task(_start_server(host, port))
    
    # Launch GUI if requested
    gui_task = None
    if launch_gui:
        logging.info("Launching GUI...")
        log_message("info", "Launching WebSocket Server GUI", "server")
        
        # Get the GUI instance so it's ready to display
        gui = get_gui_instance()
        
        # Start the GUI in a separate task
        gui_task = asyncio.create_task(run_gui_with_async())
    else:
        logging.info("GUI disabled. Running in headless mode.")
        log_message("info", "Running in headless mode (GUI disabled)", "server")
    
    # Wait for the server (and GUI if launched)
    try:
        await server_task
        if gui_task:
            await gui_task
    except asyncio.CancelledError:
        # Handle graceful shutdown
        logging.info("Shutting down server...")
        log_message("info", "Shutting down server", "server")
        
        # Cancel any pending tasks
        if gui_task and not gui_task.done():
            gui_task.cancel()
            
        # Allow tasks to clean up
        await asyncio.sleep(0.5)

async def _start_server(host, port):
    """
    Internal helper function to start the WebSocket server.
    
    Args:
        host: Hostname to bind the server
        port: Port to bind the server
    """
    # Start the WebSocket server with configured parameters
    server = await websockets.serve(
        new_frame_handler, 
        host, 
        port, 
        max_size=MAX_MESSAGE_SIZE,
        ping_interval=60,  # Send a ping every 60 seconds
        ping_timeout=20    # Wait 20 seconds for a pong response
    )
    
    # Log server information
    websocket_url = f"ws://{host}:{port}"
    logging.info(f"WebSocket server started on {websocket_url}")
    log_message("info", f"WebSocket server started on {websocket_url}", "server")
    
    if host == '0.0.0.0':
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable, just to determine interface IP
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        logging.info(f"Access from other devices via: ws://{local_ip}:{port}")
        log_message("info", f"Access from other devices via: ws://{local_ip}:{port}", "server")
        
    logging.info(f"WebSocket configured with max message size: {MAX_MESSAGE_SIZE/1024/1024:.1f}MB")
    log_message("info", f"WebSocket configured with max message size: {MAX_MESSAGE_SIZE/1024/1024:.1f}MB", "server")
    
    logging.info(f"Temporary frames will be stored in: {os.path.join(APP_ROOT_PATH, 'media', 'tmp_frames')}")
    log_message("info", f"Temporary frames dir: {os.path.join(APP_ROOT_PATH, 'media', 'tmp_frames')}", "server")
    
    # Keep the server running until stopped
    await server.wait_closed()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Start the WebSocket server for AR application')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host to bind the server (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8765,
                        help='Port to bind the server (default: 8765)')
    parser.add_argument('--no-gui', action='store_true',
                        help='Disable the GUI and run in headless mode')
    return parser.parse_args()

# Standalone test mode
if __name__ == "__main__":
    """
    Standalone execution for testing the WebSocket server independently.
    
    This creates a dummy task and starts the server.
    """
    logging.info("Starting WebSocket server directly for testing...")
    
    # Parse command line arguments
    args = parse_args()
    
    # Set correct root path for standalone mode
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_for_standalone = os.path.dirname(current_file_dir)
    
    # Create a dummy task for testing - import Task here to avoid circular imports
    from tasks.Task import Task
    raw_steps_data = [
        {"action": "pick up bottle", "focus_objects": ["bottle"]},
        {"action": "twist bottle open", "focus_objects": ["bottle", "bottle cap"]},
        {"action": "lay down the cap", "focus_objects": ["bottle cap", "table"]},
        {"action": "lay down the bottle", "focus_objects": ["bottle", "table"]}
    ]
    test_task = Task(name="WebSocket Standalone Test Task", task_list=raw_steps_data)
    set_active_task_for_websocket(test_task)
    
    # Run the server with the configured root path and GUI setting from CLI
    try:
        asyncio.run(start_websocket_server_async(
            host=args.host,
            port=args.port,
            app_root_override=project_root_for_standalone,
            launch_gui=not args.no_gui  # Invert the no-gui flag
        ))
    except KeyboardInterrupt:
        logging.info("Server stopped by user (KeyboardInterrupt)")

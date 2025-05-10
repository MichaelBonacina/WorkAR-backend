#!/usr/bin/env python3
"""
Script to run the WebSocket server on port 9000 for testing.
"""

import asyncio
import os
import sys
from tasks.Task import Task
from connection.websocket import set_active_task_for_websocket, start_websocket_server_async

def main():
    # Configure the server
    host = "localhost"
    port = 9000
    
    print(f"Starting WebSocket server for testing on {host}:{port}...")
    
    # Set project root path correctly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create a dummy task for testing
    raw_steps_data = [
        {"action": "Test Step 1: Identify Object", "focus_objects": ["any object"]},
        {"action": "Test Step 2: Describe Object", "focus_objects": ["identified object"]},
    ]
    test_task = Task(name="WebSocket Test Task", task_list=raw_steps_data)
    set_active_task_for_websocket(test_task)
    
    # Create media directory if it doesn't exist
    media_dir = os.path.join(current_dir, "media")
    temp_frames_dir = os.path.join(media_dir, "tmp_frames")
    
    for directory in [media_dir, temp_frames_dir]:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"Created directory: {directory}")
            except OSError as e:
                print(f"Error creating directory {directory}: {e}")
    
    # Run the WebSocket server
    try:
        asyncio.run(start_websocket_server_async(
            host=host, 
            port=port, 
            app_root_override=current_dir
        ))
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
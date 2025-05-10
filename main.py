import os
import asyncio
import threading
import time # Added for the main loop sleep
import logging
from flask import Flask
from connection.instructionUpload import register_instruction_upload_blueprint
from connection.websocket import start_websocket_server_async # Renamed function
from models.langfuse_config import initialize_langfuse

# Set up logging
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m-%d %H:%M:%S',
    level=logging.INFO
)

# Configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 6000
WEBSOCKET_HOST = '0.0.0.0'
WEBSOCKET_PORT = 8765
MEDIA_FOLDER_NAME = 'media'
TEMP_FRAMES_DIR_NAME = "tmp_frames" # From websocket.py

# --- Flask App Setup ---
flask_app = Flask(__name__)

# Determine Project Root and an absolute path for MEDIA_FOLDER
project_root_path = os.path.dirname(os.path.abspath(__file__))
flask_app.config['MEDIA_FOLDER'] = os.path.join(project_root_path, MEDIA_FOLDER_NAME)
flask_app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

register_instruction_upload_blueprint(flask_app)

def run_flask_app():
    print(f"Starting Flask server on http://{FLASK_HOST}:{FLASK_PORT}")
    flask_app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False) # use_reloader=False important for threads

# --- WebSocket Server Setup ---
async def main_websocket_loop_wrapper(app_root_for_ws):
    await start_websocket_server_async(host=WEBSOCKET_HOST, port=WEBSOCKET_PORT, app_root_override=app_root_for_ws)

def run_websocket_server_in_thread(app_root_for_ws):
    print(f"Attempting to start WebSocket server in a new thread on ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main_websocket_loop_wrapper(app_root_for_ws))
    except KeyboardInterrupt:
        print("WebSocket server thread received KeyboardInterrupt.")
    finally:
        if loop.is_running():
            loop.stop() # Request all tasks to complete
        # Wait for all tasks to complete before closing the loop
        # This might require more sophisticated shutdown logic in the websocket server itself
        # For now, a short delay before closing to allow tasks to finish.
        # loop.run_until_complete(asyncio.sleep(1)) 
        loop.close()
        print("WebSocket server event loop closed.")

if __name__ == '__main__':
    print("Starting application...")

    # Initialize Langfuse for monitoring
    langfuse_client = initialize_langfuse()
    if langfuse_client:
        logging.info("Langfuse monitoring initialized successfully")
    else:
        logging.warning("Langfuse monitoring not available - check your environment variables")

    # Create media directory
    media_dir_abs = flask_app.config['MEDIA_FOLDER']
    if not os.path.exists(media_dir_abs):
        try:
            os.makedirs(media_dir_abs)
            print(f"Created media directory: {media_dir_abs}")
        except OSError as e:
            print(f"Error creating media directory {media_dir_abs}: {e}. Exiting.")
            exit(1)

    # Create temporary frames directory inside media directory
    temp_frames_full_path = os.path.join(media_dir_abs, TEMP_FRAMES_DIR_NAME)
    if not os.path.exists(temp_frames_full_path):
        try:
            os.makedirs(temp_frames_full_path)
            print(f"Created temporary frames directory: {temp_frames_full_path}")
        except OSError as e:
            print(f"Error creating temporary frames directory {temp_frames_full_path}: {e}. Exiting.")
            exit(1)

    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    print("Flask app thread started.")

    # Start WebSocket server in its own thread, passing the project_root_path
    websocket_thread = threading.Thread(target=run_websocket_server_in_thread, args=(project_root_path,), daemon=True)
    websocket_thread.start()
    print("WebSocket server thread started.")

    print(f"Application started. Flask on port {FLASK_PORT}, WebSocket on port {WEBSOCKET_PORT}.")
    print(f"Media folder: {media_dir_abs}")
    print(f"Temp frames folder: {temp_frames_full_path}")
    print("Press Ctrl+C to stop both servers.")

    try:
        while True:
            time.sleep(1) # Keep main thread alive and responsive to Ctrl+C
    except KeyboardInterrupt:
        print("Main application received KeyboardInterrupt. Shutting down...")
    finally:
        print("Application shutting down.")
        # Daemon threads will exit automatically when the main program exits.

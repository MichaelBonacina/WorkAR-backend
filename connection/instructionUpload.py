from flask import Blueprint, request, jsonify
import os
import uuid
from werkzeug.utils import secure_filename
from processing.processVideo import processVideo
from connection.websocket import set_active_task_for_websocket

# Define a Blueprint for these routes if you plan to have more connection-related routes
# This helps in organizing the application
instruction_upload_bp = Blueprint('instruction_upload_bp', __name__)

# Configuration for file uploads
MEDIA_FOLDER = 'media' # This will be relative to the project root where main.py is run
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'} # Define allowed video extensions

app_flask_instance = None # Renamed to avoid conflict if 'app' is used elsewhere

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@instruction_upload_bp.route('/video_upload', methods=['POST'])
def video_upload():
    global app_flask_instance
    if app_flask_instance is None:
        return jsonify({"error": "Flask app not properly configured for MEDIA_FOLDER"}), 500
        
    upload_folder = app_flask_instance.config.get('MEDIA_FOLDER', MEDIA_FOLDER)
    if not os.path.exists(upload_folder):
        try:
            os.makedirs(upload_folder)
        except OSError as e:
            print(f"Error creating directory {upload_folder}: {e}")
            return jsonify({"error": f"Could not create media directory: {e}"}), 500

    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        # Generate a unique filename to prevent overwrites and for easier management
        # Keep the original extension
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        try:
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            print(f"Video '{unique_filename}' saved. Processing for task generation...")
            # processVideo returns a Task object or a Task object with error details
            task_object = processVideo.processVideo(file_path)

            response_message = ""
            task_name_for_response = "N/A"
            num_steps_for_response = 0

            if task_object and task_object.task_list and not any("Error" in step.get_action() for step in task_object.task_list):
                set_active_task_for_websocket(task_object) # Set the task for WebSocket processing
                response_message = "Video uploaded & processed. Task generated and activated."
                task_name_for_response = task_object.name
                num_steps_for_response = len(task_object.task_list)
                print(f"Task '{task_object.name}' activated for WebSocket processing.")
            else:
                set_active_task_for_websocket(None) # Clear any previous task if current one is invalid
                error_detail = str(task_object.task_list[0]) if task_object and task_object.task_list else "Unknown processing error."
                response_message = f"Video uploaded. Processing failed to generate a valid task: {error_detail}"
                print(f"Video processing for {unique_filename} did not yield a valid task. Detail: {error_detail}")
            
            return jsonify({
                "message": response_message,
                "filename": unique_filename,
                "stored_path": file_path,
                "task_name": task_name_for_response,
                "num_steps": num_steps_for_response
            }), 201 # 201 Created, even if task generation had issues, file is stored.

        except Exception as e:
            print(f"Error saving/processing file {unique_filename}: {e}")
            set_active_task_for_websocket(None) # Clear active task on error
            return jsonify({"error": f"Could not save or process file: {str(e)}"}), 500
    else:
        return jsonify({"error": "File type not allowed"}), 400

# Function to set the app object, to be called from main.py
# This is one way to handle app context for blueprints or shared config like MEDIA_FOLDER path
def register_instruction_upload_blueprint(flask_app_instance_from_main):
    global app_flask_instance
    app_flask_instance = flask_app_instance_from_main
    # Ensure MEDIA_FOLDER is configured in the Flask app
    # If main.py creates an absolute path for MEDIA_FOLDER, it should be set here.
    if 'MEDIA_FOLDER' not in app_flask_instance.config:
        # If not set by main.py, construct it based on app.root_path
        # However, it's better if main.py explicitly sets app.config['MEDIA_FOLDER']
        app_flask_instance.config['MEDIA_FOLDER'] = os.path.join(app_flask_instance.root_path, MEDIA_FOLDER)
    
    flask_app_instance_from_main.register_blueprint(instruction_upload_bp)
    print(f"Registered video_upload endpoint. Media will be stored in: {app_flask_instance.config['MEDIA_FOLDER']}")

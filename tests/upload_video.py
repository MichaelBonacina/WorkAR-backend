import os
import requests # For making HTTP requests

# Define the target URL for the video upload endpoint
# Ensure this matches the FLASK_PORT in your main.py (currently 6000)
UPLOAD_URL = "http://localhost:6000/video_upload"
VIDEO_FILENAME = "video1.MOV"

def upload_video():
    """Uploads 'video1.MOV' from the user's desktop to the /video_upload endpoint."""
    print(f"Attempting to upload {VIDEO_FILENAME} to {UPLOAD_URL}...")

    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    video_file_path = os.path.join(desktop_path, VIDEO_FILENAME)

    if not os.path.exists(video_file_path):
        print(f"ERROR: Video file not found at {video_file_path}")
        print("Please ensure 'video1.MOV' exists on your Desktop.")
        return False

    try:
        with open(video_file_path, 'rb') as f:
            files = {'file': (VIDEO_FILENAME, f, 'video/quicktime')} # Adjust mime type if needed
            response = requests.post(UPLOAD_URL, files=files, timeout=120) # Added timeout
        
        print(f"Upload attempt finished. Status Code: {response.status_code}")
        try:
            response_json = response.json()
            print("Server Response (JSON):")
            print(response_json)
            if response.status_code == 201 and response_json.get("message"):
                print(f"Success: {response_json.get('message')}")
                return True
            else:
                print(f"Upload failed or server returned an error: {response_json.get('error', 'No error message provided.')}")
                return False
        except requests.exceptions.JSONDecodeError:
            print("Server Response (Non-JSON):")
            print(response.text)
            print("Upload may have failed or server returned non-JSON error.")
            return False

    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: Could not connect to the server at {UPLOAD_URL}. Ensure the server is running.")
        print(f"Details: {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: The request to {UPLOAD_URL} timed out.")
        print(f"Details: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during upload: {e}")
        return False

if __name__ == '__main__':
    print("--- Running Video Upload Test Standalone ---")
    upload_video()
    print("--- Video Upload Test Finished ---")

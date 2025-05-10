# Video Upload Server

This is a simple Flask HTTP server that allows users to upload video files.

## Setup

1.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the server

```bash
python connection/instructionUpload.py
```

The server will start on `http://127.0.0.1:5001`.

## Endpoints

### `/upload_video`

*   **Method:** `POST`
*   **Description:** Uploads a video file.
*   **Form Data:**
    *   `file`: The video file to upload (multipart/form-data).
*   **Success Response (201):**
    ```json
    {
        "message": "Video uploaded successfully",
        "filename": "your_video.mp4",
        "path": "uploads/your_video.mp4"
    }
    ```
*   **Error Responses:**
    *   `400 Bad Request`: If no file part is present, no file is selected, or the file type is not allowed.
        ```json
        {"error": "Error message here"}
        ```
    *   `500 Internal Server Error`: If the file could not be saved.
        ```json
        {"error": "Could not save file: Specific error message"}
        ```

## Notes

*   Uploaded videos are saved in the `uploads` directory.
*   The maximum allowed file size is 100MB (configurable in `connection/instructionUpload.py`).
*   Allowed video extensions are: `mp4`, `mov`, `avi`, `mkv`, `webm` (configurable in `connection/instructionUpload.py`). 
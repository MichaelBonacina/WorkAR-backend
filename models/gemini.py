import google.generativeai as genai
import os
import time
from dotenv import load_dotenv
from langfuse.decorators import langfuse_context, observe

class Gemini:
    @staticmethod
    @observe(as_type="generation")
    def videoAnalysis(prompt: str, video_file: str, 
                      initial_poll_interval_seconds: float = 2.0,
                      processing_timeout_seconds: float = 300.0): # 5 minutes timeout
        """Analyzes a video file based on a given prompt using Gemini API with improved polling."""
        load_dotenv()
        try:
            # Configure the API key from environment variable
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                return {"error": "GOOGLE_API_KEY environment variable not set."}
            genai.configure(api_key=api_key)

            print(f"Uploading video file: {video_file}...")
            # Upload the video file
            video_file_uploaded = genai.upload_file(path=video_file)
            print(f"Uploaded file '{video_file_uploaded.name}'.")

            start_time = time.time()
            current_poll_interval = initial_poll_interval_seconds

            while video_file_uploaded.state.name == "PROCESSING":
                if time.time() - start_time > processing_timeout_seconds:
                    print(f"Video processing timed out after {processing_timeout_seconds} seconds.")
                    # Attempt to delete the timed-out upload
                    try:
                        genai.delete_file(video_file_uploaded.name)
                        print(f"Cleaned up timed-out upload: {video_file_uploaded.name}")
                    except Exception as e_del_timeout:
                        print(f"Error cleaning up timed-out upload {video_file_uploaded.name}: {e_del_timeout}")
                    
                    # Update Langfuse with error
                    langfuse_context.update_current_observation(
                        status="error",
                        error=f"Video processing timed out for {video_file} after {processing_timeout_seconds} seconds."
                    )
                    return {"error": f"Video processing timed out for {video_file} after {processing_timeout_seconds} seconds."}

                time.sleep(current_poll_interval)
                video_file_uploaded = genai.get_file(video_file_uploaded.name)
                
            
            if video_file_uploaded.state.name == "FAILED":
                print(f"Video processing failed: {video_file_uploaded.uri}")
                # Attempt to delete the failed upload if it exists
                try:
                    genai.delete_file(video_file_uploaded.name)
                    print(f"Cleaned up failed upload: {video_file_uploaded.name}")
                except Exception as e_del_failed:
                    print(f"Error cleaning up failed upload {video_file_uploaded.name}: {e_del_failed}")
                
                # Update Langfuse with error
                langfuse_context.update_current_observation(
                    status="error",
                    error=f"Video processing failed for {video_file}."
                )
                return {"error": f"Video processing failed for {video_file}."}
            
            print("Video processed. Generating content with Gemini...")

            model = genai.GenerativeModel(model_name="gemini-2.5-pro-preview-05-06") 

            # Make the API call
            response = model.generate_content([prompt, video_file_uploaded])
            print("gemini response: ", response)
            
            # Track usage metrics in Langfuse
            langfuse_context.update_current_observation(
                input=prompt,
                output=response.text,
                model="gemini-2.5-pro-preview-05-06",
                usage_details={
                    "input": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and hasattr(response.usage_metadata, 'prompt_token_count') else None,
                    "output": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and hasattr(response.usage_metadata, 'candidates_token_count') else None,
                    "total": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') and hasattr(response.usage_metadata, 'total_token_count') else None
                }
            )
            
            # Clean up the uploaded file
            try:
                genai.delete_file(video_file_uploaded.name)
                print(f"Successfully deleted uploaded file: {video_file_uploaded.name}")
            except Exception as e_del_success:
                print(f"Error deleting file {video_file_uploaded.name} after successful processing: {e_del_success}")

            return response.text

        except Exception as e:
            print(f"An error occurred during video analysis: {e}")
            # Attempt to clean up if video_file_uploaded object exists and has a name
            if 'video_file_uploaded' in locals() and hasattr(video_file_uploaded, 'name') and video_file_uploaded.name:
                try:
                    # Check file state before attempting deletion in a general catch-all
                    # to avoid trying to delete an already deleted or non-existent file.
                    file_meta = genai.get_file(video_file_uploaded.name)
                    if file_meta and file_meta.state.name != "DELETED":
                         genai.delete_file(video_file_uploaded.name)
                         print(f"Cleaned up file {video_file_uploaded.name} after error.")
                except Exception as e_cleanup:
                    print(f"Error during cleanup for {video_file_uploaded.name} after an exception: {e_cleanup}. It might have been already deleted or never fully created.")
            
            # Update Langfuse with error
            langfuse_context.update_current_observation(
                status="error",
                error=str(e)
            )
            return {"error": str(e)}

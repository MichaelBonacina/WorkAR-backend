import os
import base64
import logging
from typing import List, Dict, Union
from dotenv import load_dotenv

# Use the Langfuse openai wrapper instead of the regular openai
from langfuse.openai import openai

# Load environment variables
load_dotenv()

class OpenAI:
    @staticmethod
    def _encode_image_to_base64(image_path: str) -> str:
        """Encodes an image file to a base64 string."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            print(f"Error: Image file not found at {image_path}")
            raise
        except Exception as e:
            print(f"Error encoding image {image_path}: {e}")
            raise

    @staticmethod
    def frameAnalysis(prompt: str, image_paths: List[str]) -> str:
        """
        Sends a prompt and a list of image paths to gpt-4-mini for processing.
        Uses the Langfuse OpenAI wrapper for automatic monitoring.

        Args:
            prompt: The text prompt to send to the model.
            image_paths: A list of file paths to the images.

        Returns:
            The text response from the model.
            
        Raises:
            RuntimeError: If the OpenAI API key is not set or if the API call fails.
        """
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable not set.")

        # Create OpenAI client using Langfuse wrapper
        client = openai.OpenAI(api_key=api_key)

        # Prepare message content with text prompt
        messages_content = [{"type": "text", "text": prompt}]
        
        # Add images to message content
        for image_path in image_paths:
            try:
                base64_image = OpenAI._encode_image_to_base64(image_path)
                # Determine image type from file extension
                image_type = os.path.splitext(image_path)[1].lower()
                if image_type in ['.jpg', '.jpeg']:
                    mime_type = 'image/jpeg'
                elif image_type == '.png':
                    mime_type = 'image/png'
                else:
                    raise ValueError(f"Unsupported image type: {image_type}. Only jpg, jpeg and png are supported.")
                
                messages_content.append({
                    "type": "image_url", 
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}",
                        "detail": "high"
                    }
                })
            except Exception as e:
                print(f"Skipping image {image_path} due to encoding error: {e}")
                raise RuntimeError(f"Failed to encode image {image_path}") from e

        try:
            # Make the API call - tracing is automatic with the Langfuse openai wrapper
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": messages_content
                    }
                ],
                max_tokens=10000  # Adjust as needed
            )
            
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                return response.choices[0].message.content
            else:
                raise RuntimeError("Failed to get a valid response from OpenAI API.")

        except openai.APIConnectionError as e:
            print(f"OpenAI API Connection Error: {e}")
            raise RuntimeError(f"OpenAI API Connection Error: {e}") from e
        except openai.RateLimitError as e:
            print(f"OpenAI API Rate Limit Error: {e}")
            raise RuntimeError(f"OpenAI API Rate Limit Error: {e}") from e
        except openai.APIStatusError as e:
            print(f"OpenAI API Status Error: {e}")
            raise RuntimeError(f"OpenAI API Status Error: {e}") from e
        except Exception as e:
            print(f"An unexpected error occurred while calling OpenAI API: {e}")
            raise RuntimeError(f"An unexpected error occurred: {e}") from e

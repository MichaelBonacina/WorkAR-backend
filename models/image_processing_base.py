import base64
import io
from pathlib import Path
from typing import Any
from PIL import Image

# Assuming model_utils.py is in the same directory or accessible in PYTHONPATH
from .model_utils import logger, truncate_base64 

class BaseImageUtilModel:
    """Utility class for common image processing tasks."""

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        logger.debug(f"Encoding image of mode {image.mode} and size {image.size} to base64.")
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3]) 
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=95, optimize=True, subsampling=0)
        base64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        # Prepend the base64 header for JPEG images
        base64_str = f"data:image/jpeg;base64,{base64_str}"
        logger.debug(f"Encoded image to base64: {truncate_base64(base64_str)}")
        return base64_str

    def _resize_image(self, image: Image.Image, max_size: int = 512) -> Image.Image:
        logger.debug(f"Resizing image of size {image.size} with max_size {max_size}.")
        width, height = image.size
        if width <= max_size and height <= max_size:
            return image
        
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
            
        resized_img = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.debug(f"Image resized to {resized_img.size}.")
        return resized_img

    def _validate_image(self, image_input: Any) -> Image.Image:
        logger.debug(f"Validating image input of type {type(image_input)}.")
        if isinstance(image_input, Image.Image):
            return image_input
        
        if isinstance(image_input, (str, Path)):
            try:
                img = Image.open(image_input)
                logger.debug(f"Image loaded from path {image_input}, size {img.size}, mode {img.mode}.")
                return img
            except FileNotFoundError:
                logger.error(f"Image file not found at path: {image_input}")
                raise
            except Exception as e:
                logger.error(f"Could not open or read image file {image_input}: {e}")
                raise ValueError(f"Could not open or read image file: {e}") from e
        
        logger.error(f"Invalid image input type: {type(image_input)}. Must be PIL Image or path.")
        raise ValueError("Input must be a PIL Image or a path to an image file.") 
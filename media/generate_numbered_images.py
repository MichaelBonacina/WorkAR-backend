#!/usr/bin/env python3
"""
Script to generate numbered images in a subfolder of the media directory.
Each image will have its corresponding number drawn on it.
"""

import os
import pathlib
from PIL import Image, ImageDraw, ImageFont
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def create_numbered_image(number: int, output_path: pathlib.Path, 
                         size: tuple[int, int] = (800, 600),
                         bg_color: tuple[int, int, int] = (255, 255, 255),
                         text_color: tuple[int, int, int] = (0, 0, 0)) -> None:
    """
    Create an image with a number drawn on it.
    
    Args:
        number: The number to draw on the image
        output_path: Path where the image will be saved
        size: Size of the image (width, height)
        bg_color: Background color of the image (R, G, B)
        text_color: Color of the text (R, G, B)
    """
    # Create a new image with white background
    img = Image.new('RGB', size, color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a system font, fall back to default if not available
    try:
        # Try to find a system font - adjust path as needed for the platform
        font = ImageFont.truetype("Arial", 200)  # Large size for visibility
    except IOError:
        font = ImageFont.load_default()
        logger.warning("Could not load Arial font, using default")
    
    # Get the size of the text
    text = str(number)
    text_width, text_height = draw.textsize(text, font=font) if hasattr(draw, 'textsize') else (300, 200)
    
    # Position the text in the center
    position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
    
    # Draw the text
    draw.text(position, text, font=font, fill=text_color)
    
    # Save the image
    img.save(output_path)
    logger.info(f"Created image {output_path}")

def main():
    # Create a subfolder in the media directory
    media_dir = pathlib.Path("media")
    subfolder_name = "numbered_images"
    output_dir = media_dir / subfolder_name
    
    # Create directory if it doesn't exist
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        logger.info(f"Created directory {output_dir}")
    else:
        logger.info(f"Directory {output_dir} already exists")
    
    # Generate 20 images with numbers from 1 to 20
    num_images = 20
    
    for i in tqdm(range(1, num_images + 1), desc="Generating images"):
        image_path = output_dir / f"number_{i}.png"
        create_numbered_image(i, image_path)
    
    logger.info(f"Successfully generated {num_images} numbered images in {output_dir}")

if __name__ == "__main__":
    main() 
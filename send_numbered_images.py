#!/usr/bin/env python3
"""
Script to send numbered images to the websocket client with a specified delay between calls.
Uses a single websocket connection for all images.
"""

import asyncio
import pathlib
import time
import re
import logging
import argparse
from tqdm import tqdm
import websockets
import os
from PIL import Image
import io
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants from test_websocket_client.py
MAX_IMAGE_SIZE = (512, 512)  # Maximum dimensions for images
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB max file size

def natural_sort_key(s):
    """
    Sort strings containing numbers in natural order.
    E.g. ["number_1.png", "number_2.png", ..., "number_10.png"] instead of 
    ["number_1.png", "number_10.png", "number_2.png", ...]
    """
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', str(s))]

def resize_image_if_needed(image_path):
    """
    Resize an image if it's too large and return the image data.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        bytes: The image data (possibly resized)
    """
    # Open the image
    with Image.open(image_path) as img:
        # First check file size
        img_size = os.path.getsize(image_path)
        if img_size > MAX_FILE_SIZE or img.width > MAX_IMAGE_SIZE[0] or img.height > MAX_IMAGE_SIZE[1]:
            logger.info(f"Original image size: {img.width}x{img.height}, {img_size/1024:.1f} KB")
            # Keep aspect ratio
            img.thumbnail(MAX_IMAGE_SIZE)
            
            # Save to memory
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG', optimize=True)
            img_data = img_byte_arr.getvalue()
            logger.info(f"Resized to: {img.width}x{img.height}, {len(img_data)/1024:.1f} KB")
            return img_data, img.width, img.height
        else:
            # Image is small enough, just read it
            with open(image_path, 'rb') as f:
                return f.read(), img.width, img.height

async def send_images_over_single_connection(image_files, host: str, port: int, delay: float = 1.0, wait_for_response: bool = True):
    """
    Send all images over a single websocket connection with delay between them.
    
    Args:
        image_files: List of image files to send
        host: WebSocket server host
        port: WebSocket server port
        delay: Delay in seconds between sending images
        wait_for_response: Whether to wait for server response before sending next image
    """
    websocket_uri = f"ws://{host}:{port}"
    logger.info(f"Connecting to {websocket_uri}...")
    
    try:
        async with websockets.connect(websocket_uri) as websocket:
            logger.info(f"Connected to {websocket_uri}")
            
            for i, image_file in enumerate(tqdm(image_files, desc="Sending images")):
                start_time = time.time()
                
                # Get the image data
                image_data, width, height = resize_image_if_needed(image_file)
                
                # Create metadata message
                metadata = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "width": width,
                    "height": height,
                    "image_number": i + 1,
                    "total_images": len(image_files),
                    "camera_pose": {
                        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
                    }
                }
                
                # Send metadata first
                logger.info(f"Sending metadata for image {i+1}/{len(image_files)}: {image_file}")
                await websocket.send(json.dumps(metadata))
                
                # Send the image data as binary
                logger.info(f"Sending image: {image_file} ({len(image_data)/1024:.1f} KB)")
                await websocket.send(image_data)
                
                # Wait for and log the response if requested
                if wait_for_response:
                    response = await websocket.recv()
                    logger.info(f"Received response: {response}")
                
                # Calculate remaining time to wait based on elapsed time
                elapsed_time = time.time() - start_time
                remaining_delay = max(0, delay - elapsed_time)
                
                # Wait before sending the next image (unless it's the last one)
                if i < len(image_files) - 1 and remaining_delay > 0:
                    logger.info(f"Waiting {remaining_delay:.2f} second(s) before sending next image...")
                    await asyncio.sleep(remaining_delay)
            
            # If we didn't wait for responses during the loop, collect them now
            if not wait_for_response:
                logger.info("Collecting server responses...")
                for _ in range(len(image_files)):
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        logger.info(f"Received response: {response}")
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for server response")
                        break
                    
            logger.info("All images have been sent")
    except Exception as e:
        logger.error(f"Error during websocket communication: {e}")

async def main_async(args):
    # Path to the directory with numbered images
    image_dir = pathlib.Path(args.directory)
    
    # Check if directory exists
    if not image_dir.exists() or not image_dir.is_dir():
        logger.error(f"Directory not found: {image_dir}")
        return
    
    # Get all PNG files in the directory
    image_files = list(image_dir.glob("*.png"))
    
    # Sort files by number
    image_files.sort(key=natural_sort_key)
    
    logger.info(f"Found {len(image_files)} images to send")
    
    # Send all images over a single connection
    await send_images_over_single_connection(image_files, args.host, args.port, args.delay, args.wait_for_response)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Send numbered images to the websocket client with delay")
    parser.add_argument("--host", default="localhost", help="WebSocket server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket server port (default: 8765)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between sending images (default: 1.0)")
    parser.add_argument("--directory", type=str, default="media/numbered_images", 
                        help="Directory containing the numbered images (default: media/numbered_images)")
    parser.add_argument("--wait-for-response", action="store_true", default=False,
                        help="Wait for server response before sending next image (default: False)")
    
    args = parser.parse_args()
    
    # Run the async main function
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main() 
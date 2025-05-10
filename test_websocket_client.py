#!/usr/bin/env python3
"""
Test script for WebSocket client to send image data to the server.
"""

import asyncio
import websockets
import argparse
import os
from PIL import Image
import io
import json
from datetime import datetime

MAX_IMAGE_SIZE = (512, 512)  # Maximum dimensions for images
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB max file size

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
            print(f"Original image size: {img.width}x{img.height}, {img_size/1024:.1f} KB")
            # Keep aspect ratio
            img.thumbnail(MAX_IMAGE_SIZE)
            
            # Save to memory
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG', optimize=True)
            img_data = img_byte_arr.getvalue()
            print(f"Resized to: {img.width}x{img.height}, {len(img_data)/1024:.1f} KB")
            return img_data, img.width, img.height
        else:
            # Image is small enough, just read it
            with open(image_path, 'rb') as f:
                return f.read(), img.width, img.height

async def send_image(websocket_uri, image_path):
    """
    Send an image to the WebSocket server and receive the response.
    
    Args:
        websocket_uri: The WebSocket URI (ws://host:port)
        image_path: Path to the image file to send
    """
    try:
        # Get the image data (resized if needed)
        image_data, width, height = resize_image_if_needed(image_path)
        
        print(f"Connecting to {websocket_uri}...")
        async with websockets.connect(websocket_uri) as websocket:
            print(f"Connected to {websocket_uri}")
            
            # Create metadata message
            metadata = {
                "timestamp": datetime.utcnow().isoformat(),
                "width": width,
                "height": height,
                "camera_pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
                }
            }
            
            # Send metadata first
            print("Sending metadata...")
            await websocket.send(json.dumps(metadata))
            
            # Send the image data as binary
            print(f"Sending image: {image_path} ({len(image_data)/1024:.1f} KB)")
            await websocket.send(image_data)
            
            # Wait for and print the response
            response = await websocket.recv()
            print(f"Received response: {response}")
            
    except Exception as e:
        print(f"Error: {e}")

async def send_test_image(websocket_uri):
    """
    Create a test image and send it to the WebSocket server.
    
    Args:
        websocket_uri: The WebSocket URI (ws://host:port)
    """
    # Create a simple test image
    img = Image.new('RGB', (640, 480), color='red')
    
    # Save to a BytesIO object
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    print(f"Connecting to {websocket_uri}...")
    async with websockets.connect(websocket_uri) as websocket:
        print(f"Connected to {websocket_uri}")
        
        # Create metadata message
        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "width": 640,
            "height": 480,
            "camera_pose": {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            }
        }
        
        # Send metadata first
        print("Sending metadata...")
        await websocket.send(json.dumps(metadata))
        
        # Send the image data as binary
        print(f"Sending test image ({len(img_byte_arr)/1024:.1f} KB)")
        await websocket.send(img_byte_arr)
        
        # Wait for and print the response
        response = await websocket.recv()
        print(f"Received response: {response}")

def main():
    parser = argparse.ArgumentParser(description="WebSocket client for sending images")
    parser.add_argument("--host", default="localhost", help="WebSocket server host")
    parser.add_argument("--port", type=int, default=9000, help="WebSocket server port")
    parser.add_argument("--image", help="Path to image file to send (if not specified, a test image will be created)")
    
    args = parser.parse_args()
    websocket_uri = f"ws://{args.host}:{args.port}"
    
    if args.image:
        if not os.path.exists(args.image):
            print(f"Error: Image file not found: {args.image}")
            return
        asyncio.run(send_image(websocket_uri, args.image))
    else:
        asyncio.run(send_test_image(websocket_uri))

if __name__ == "__main__":
    main()
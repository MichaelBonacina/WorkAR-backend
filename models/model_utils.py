import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from PIL import Image, ImageDraw

# --- Global Logging Configuration & Utilities ---
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def truncate_base64(base64_str: str, max_length: int = 50) -> str:
    if not base64_str: return ""
    if len(base64_str) <= max_length: return base64_str
    return f"{base64_str[:max_length]}... (truncated, total length: {len(base64_str)})"

def looks_like_base64(s: str, min_length: int = 100) -> bool:
    if not isinstance(s, str): return False
    base64_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    if len(s) >= min_length and set(s[:min_length]).issubset(base64_chars):
        return True
    return False

def sanitize_for_logging(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: sanitize_for_logging(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_logging(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_for_logging(i) for i in obj)
    elif isinstance(obj, str):
        return truncate_base64(obj) if looks_like_base64(obj) else obj
    return obj

class Base64TruncateFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg:
            record.msg = sanitize_for_logging(record.msg)
        if record.args: # type: ignore
            record.args = sanitize_for_logging(record.args) # type: ignore
        return True
logger.addFilter(Base64TruncateFilter())

# --- Generic Data Classes ---
@dataclass
class ObjectPoint:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: Optional[float] = None

@dataclass
class ImageInfo:
    url: str
    content_type: str
    file_name: str
    file_size: int
    width: int
    height: int

# --- Visualization and Saving Utilities ---
def draw_bounding_boxes(image: Image.Image, objects: List[Dict[str, float]], 
                     output_path: Optional[str] = "output_visualization.png", 
                     label: str = "", 
                     labels: Optional[List[str]] = None,
                     return_image: bool = False) -> Optional[Image.Image]:
    """Visualizes detected objects as bounding boxes with a transparent overlay.

    Args:
        image: The input image on which to draw.
        objects: A list of dictionaries containing bounding box coordinates.
        output_path: The path to save the output image with visualizations. If None, the image is not saved.
        label: Optional label to display for each bounding box.
        labels: Optional list of labels for each object (overrides the label parameter).
        return_image: If True, returns the modified image.

    Returns:
        The modified image if return_image is True, otherwise None.
    """
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy, "RGBA")
    width, height = image.size
    
    try:
        # Try to import a font, fallback to default if not available
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("Arial", 18)
        except IOError:
            font = ImageFont.load_default()
    except ImportError:
        font = None

    # Define colors for different objects (to create variety)
    colors = [
        (255, 0, 0),   # Red
        (0, 255, 0),   # Green
        (0, 0, 255),   # Blue
        (255, 255, 0), # Yellow
        (255, 0, 255), # Magenta
        (0, 255, 255), # Cyan
    ]

    for i, obj in enumerate(objects):
        # Check if coordinates are normalized (0-1) or absolute pixel values
        # If any coordinate is > 1.0, assume absolute pixel coordinates
        is_normalized = all(0 <= obj[key] <= 1.0 for key in ["x_min", "y_min", "x_max", "y_max"])
        
        if is_normalized:
            # Convert normalized coordinates to pixel values
            x_min = int(obj["x_min"] * width)
            y_min = int(obj["y_min"] * height)
            x_max = int(obj["x_max"] * width)
            y_max = int(obj["y_max"] * height)
        else:
            # Already in pixel coordinates
            x_min = int(obj["x_min"])
            y_min = int(obj["y_min"])
            x_max = int(obj["x_max"])
            y_max = int(obj["y_max"])

        # Get a color based on the object index
        color_rgb = colors[i % len(colors)]
        
        # Draw only the outline (no fill)
        draw.rectangle(
            [(x_min, y_min), (x_max, y_max)],
            outline=color_rgb,  # Solid color for outline
            width=3
        )
        
        # Add a more visible colored label
        if labels and i < len(labels):
            text = labels[i]
        elif label:
            text = f"{label} {i+1}"
        else:
            text = f"Object {i+1}"
            
        text_width = font.getsize(text)[0] if hasattr(font, 'getsize') else 100
        text_height = font.getsize(text)[1] if hasattr(font, 'getsize') else 20
        
        # Draw label background with high transparency
        draw.rectangle(
            [(x_min, y_min - text_height - 4), (x_min + text_width + 10, y_min)],
            fill=color_rgb + (180,)  # Semi-transparent background
        )
        
        # Draw white text
        draw.text((x_min + 6, y_min - text_height - 2), text, fill="white", font=font)

    # Save the image if an output path is provided
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        img_copy.save(output_file)
        logger.debug(f"Visualization saved to {output_file.absolute()}")
    
    # Return the modified image if requested
    if return_image:
        return img_copy
    return None

def save_json_results(data: Dict[str, Any], output_path: str = "output_results.json") -> None:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=sanitize_for_logging)
    logger.debug(f"JSON results saved to {output_file.absolute()}") 
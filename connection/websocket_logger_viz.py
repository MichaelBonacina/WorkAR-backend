#!/usr/bin/env python3
"""
WebSocket Logger Visualization Tool.

This module provides a PyQt5 GUI for visualizing the latest WebSocket logs 
created by the WebSocketLogger. It reads log files from the filesystem and 
displays the most recent items.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import logging

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QScrollArea, QTextEdit, QGroupBox
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer, QSize

class LogWatcher:
    """Watches the log directories and identifies the latest relevant files."""
    
    def __init__(self, base_dir: str = "websocket_logs"):
        """
        Initialize the log watcher.
        
        Args:
            base_dir: Base directory for WebSocket logs
        """
        self.base_dir = Path(base_dir)
        self.incoming_dir = self.base_dir / "incoming_messages"
        self.outgoing_dir = self.base_dir / "outgoing_messages"
        self.analysis_dir = self.base_dir / "analysis_calls"

    def _get_latest_file(self, directory: Path, patterns: Union[str, List[str]]) -> Optional[Path]:
        """
        Get the latest file in a directory matching a pattern, by filename.
        Assumes filenames start with a sortable timestamp (YYYYMMDD_HHMMSS_fff).
        """
        if not directory.exists():
            return None
        
        all_files = []
        if isinstance(patterns, str):
            patterns = [patterns]
        
        for pattern in patterns:
            all_files.extend(list(directory.glob(pattern)))
            
        if not all_files:
            return None
            
        # Sort by filename in descending order to get the latest
        all_files.sort(key=lambda p: p.name, reverse=True)
        return all_files[0]

    def get_latest_log_items(self) -> Dict[str, Optional[Path]]:
        """
        Get the paths to the latest relevant log items.
        
        Returns:
            A dictionary containing paths to the latest items:
            - "latest_incoming_image": Path to the latest incoming image.
            - "latest_outgoing_message": Path to the latest outgoing JSON message.
            - "latest_analysis_visualization": Path to the latest analysis visualization.jpg.
        """
        latest_items = {
            "latest_incoming_image": None,
            "latest_outgoing_message": None,
            "latest_analysis_visualization": None,
        }

        # Latest incoming image
        image_patterns = ["*.jpg", "*.jpeg", "*.png"]
        latest_items["latest_incoming_image"] = self._get_latest_file(self.incoming_dir, image_patterns)

        # Latest outgoing message
        latest_items["latest_outgoing_message"] = self._get_latest_file(self.outgoing_dir, "*.json")

        # Latest analysis visualization
        if self.analysis_dir.exists():
            analysis_subdirs = sorted(
                [d for d in self.analysis_dir.iterdir() if d.is_dir()],
                key=lambda p: p.name,
                reverse=True
            )
            for subdir in analysis_subdirs:
                vis_file = subdir / "visualization.jpg"
                if vis_file.exists():
                    latest_items["latest_analysis_visualization"] = vis_file
                    break 
        
        return latest_items

    def load_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load and parse a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Parsed JSON data or None if file cannot be parsed
        """
        if not file_path or not file_path.exists():
            return None
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading JSON file {file_path}: {e}")
            return None

class WebSocketLoggerViewer(QMainWindow):
    """Main application window for WebSocket log visualization."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("WebSocket Logger Visualizer - Latest Items")
        self.resize(1000, 700)
        
        self.log_watcher = LogWatcher()
        
        # Store current paths to check for changes
        self._current_incoming_image_path: Optional[Path] = None
        self._current_outgoing_message_path: Optional[Path] = None
        self._current_analysis_viz_path: Optional[Path] = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Latest Input Frame Section ---
        input_frame_group = QGroupBox("Latest Input Frame")
        input_frame_layout = QVBoxLayout(input_frame_group)
        self.input_image_label = QLabel("No input frame")
        self.input_image_label.setAlignment(Qt.AlignCenter)
        self.input_image_label.setMinimumSize(300, 200)
        input_frame_layout.addWidget(self.input_image_label)
        main_layout.addWidget(input_frame_group)

        # --- Latest Outgoing Message Section ---
        outgoing_message_group = QGroupBox("Latest Outgoing Message")
        outgoing_message_layout = QVBoxLayout(outgoing_message_group)
        self.outgoing_json_textedit = QTextEdit()
        self.outgoing_json_textedit.setReadOnly(True)
        self.outgoing_json_textedit.setPlaceholderText("No outgoing message")
        self.outgoing_json_textedit.setMinimumHeight(150)
        outgoing_message_layout.addWidget(self.outgoing_json_textedit)
        main_layout.addWidget(outgoing_message_group)

        # --- Latest Analysis Visualization Section ---
        analysis_viz_group = QGroupBox("Latest Analysis Visualization")
        analysis_viz_layout = QVBoxLayout(analysis_viz_group)
        self.analysis_viz_label = QLabel("No analysis visualization")
        self.analysis_viz_label.setAlignment(Qt.AlignCenter)
        self.analysis_viz_label.setMinimumSize(300, 200)
        analysis_viz_layout.addWidget(self.analysis_viz_label)
        main_layout.addWidget(analysis_viz_group)
        
        # Setup update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_displays)
        self.update_timer.start(500)  # 500ms refresh rate
        
        self.refresh_displays() # Initial population

    def _display_image(self, label: QLabel, image_path: Optional[Path], placeholder_text: str):
        if image_path and image_path.exists():
            try:
                pixmap = QPixmap(str(image_path))
                if not pixmap.isNull():
                    # Scale pixmap to fit label while maintaining aspect ratio
                    label_size = label.size()
                    # Subtract some padding if you have margins in the groupbox/layout
                    # This is a simple fit, might need adjustments for perfect centering/scaling
                    scaled_pixmap = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    label.setPixmap(scaled_pixmap)
                else:
                    label.setText(f"Error loading: {image_path.name}")
            except Exception as e:
                logging.error(f"Error displaying image {image_path}: {e}")
                label.setText(f"Error: {e}")
        else:
            label.clear() # Clear previous pixmap
            label.setText(placeholder_text)

    def _display_json(self, text_edit: QTextEdit, json_path: Optional[Path], placeholder_text: str):
        if json_path and json_path.exists():
            data = self.log_watcher.load_json_file(json_path)
            if data:
                try:
                    text_edit.setText(json.dumps(data, indent=2))
                except Exception as e:
                    logging.error(f"Error serializing JSON for display {json_path}: {e}")
                    text_edit.setPlaceholderText(f"Error displaying JSON: {e}")
            else:
                text_edit.setPlaceholderText(f"Could not load: {json_path.name}")
        else:
            text_edit.clear()
            text_edit.setPlaceholderText(placeholder_text)

    def refresh_displays(self):
        latest_items = self.log_watcher.get_latest_log_items()

        new_incoming_image = latest_items.get("latest_incoming_image")
        if new_incoming_image != self._current_incoming_image_path:
            self._current_incoming_image_path = new_incoming_image
            self._display_image(self.input_image_label, new_incoming_image, "No input frame")

        new_outgoing_message = latest_items.get("latest_outgoing_message")
        if new_outgoing_message != self._current_outgoing_message_path:
            self._current_outgoing_message_path = new_outgoing_message
            self._display_json(self.outgoing_json_textedit, new_outgoing_message, "No outgoing message")
            
        new_analysis_viz = latest_items.get("latest_analysis_visualization")
        if new_analysis_viz != self._current_analysis_viz_path:
            self._current_analysis_viz_path = new_analysis_viz
            self._display_image(self.analysis_viz_label, new_analysis_viz, "No analysis visualization")

def main():
    """Start the WebSocket logger visualizer application."""
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    window = WebSocketLoggerViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 
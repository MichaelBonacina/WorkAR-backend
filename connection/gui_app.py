"""
Main GUI application for the WebSocket server.

This module provides the main window and UI components for visualizing
WebSocket server activity, VideoState, and TaskState.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

# PyQt imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QGridLayout, QFrame, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage, QFont

# Import the message queue
from connection.message_queue import message_queue

# Configure logging
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m-%d %H:%M:%S',
    level=logging.INFO
)

class MessageLogWidget(QScrollArea):
    """
    Widget for displaying messages and images from WebSocket clients.
    
    This widget shows a chronological log of messages with timestamps,
    including images received from AR glasses.
    """
    
    def __init__(self, parent=None):
        """Initialize the message log widget."""
        super().__init__(parent)
        
        # Main container widget for the scroll area
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.setSpacing(10)
        
        # Set up scroll area
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.StyledPanel)
        
        # Message count label at the top
        self.message_count_label = QLabel("Messages: 0")
        self.message_count_label.setAlignment(Qt.AlignRight)
        self.layout.addWidget(self.message_count_label)
        
        # Message count
        self.message_count = 0
        
        # Maximum number of messages to keep (to prevent memory issues)
        self.max_messages = 100
        
        # Subscribe to message queue for messages
        message_queue.subscribe("log", self.add_log_message)
        message_queue.subscribe("image_received", self.add_image_message)
        
    def add_log_message(self, message: Dict[str, Any]):
        """
        Add a log message to the display.
        
        Args:
            message: Message dict from the queue
        """
        timestamp = message.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        payload = message.get("payload", {})
        
        level = payload.get("level", "info")
        text = payload.get("message", "")
        source = payload.get("source", "server")
        
        # Create a frame for the message
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        
        # Create header with timestamp and source
        header = QLabel(f"[{timestamp}] {source.upper()}")
        header.setStyleSheet("font-weight: bold;")
        frame_layout.addWidget(header)
        
        # Add message text
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        
        # Set style based on level
        if level == "error":
            text_label.setStyleSheet("color: red;")
        elif level == "warning":
            text_label.setStyleSheet("color: orange;")
            
        frame_layout.addWidget(text_label)
        
        # Add to layout
        self.layout.addWidget(frame)
        
        # Update message count
        self.message_count += 1
        self.message_count_label.setText(f"Messages: {self.message_count}")
        
        # Remove old messages if over the limit
        self._prune_old_messages()
        
        # Scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
    def add_image_message(self, message: Dict[str, Any]):
        """
        Add an image message to the display.
        
        Args:
            message: Message dict from the queue
        """
        timestamp = message.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        payload = message.get("payload", {})
        
        image_path = payload.get("image_path", "")
        client_addr = payload.get("client_addr", "unknown")
        metadata = payload.get("metadata", {})
        
        # Create a frame for the message
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        
        # Create header with timestamp and client address
        header = QLabel(f"[{timestamp}] IMAGE FROM {client_addr}")
        header.setStyleSheet("font-weight: bold;")
        frame_layout.addWidget(header)
        
        # Add image if path exists
        if image_path and os.path.exists(image_path):
            try:
                # Load image and scale to a reasonable size
                pixmap = QPixmap(image_path)
                pixmap = pixmap.scaled(320, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
                # Create image label
                image_label = QLabel()
                image_label.setPixmap(pixmap)
                image_label.setAlignment(Qt.AlignCenter)
                frame_layout.addWidget(image_label)
                
                # Add metadata summary
                width = metadata.get("width", 0)
                height = metadata.get("height", 0)
                timestamp_meta = metadata.get("timestamp", "unknown")
                
                meta_text = f"Size: {width}x{height}, Timestamp: {timestamp_meta}"
                meta_label = QLabel(meta_text)
                meta_label.setWordWrap(True)
                frame_layout.addWidget(meta_label)
                
            except Exception as e:
                error_label = QLabel(f"Error loading image: {e}")
                error_label.setStyleSheet("color: red;")
                frame_layout.addWidget(error_label)
        else:
            # Image not found
            error_label = QLabel(f"Image not found: {image_path}")
            error_label.setStyleSheet("color: red;")
            frame_layout.addWidget(error_label)
        
        # Add to layout
        self.layout.addWidget(frame)
        
        # Update message count
        self.message_count += 1
        self.message_count_label.setText(f"Messages: {self.message_count}")
        
        # Remove old messages if over the limit
        self._prune_old_messages()
        
        # Scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
    
    def _prune_old_messages(self):
        """Remove old messages if over the limit."""
        while self.layout.count() > self.max_messages + 1:  # +1 for the count label
            # Get the second item (first is count label)
            item = self.layout.itemAt(1)
            if item:
                widget = item.widget()
                if widget:
                    # Remove from layout and delete
                    self.layout.removeItem(item)
                    widget.deleteLater()


class VideoStateWidget(QScrollArea):
    """
    Widget for displaying the current state of VideoState.
    
    This widget shows thumbnails of images currently in the VideoState.
    """
    
    def __init__(self, parent=None):
        """Initialize the VideoState widget."""
        super().__init__(parent)
        
        # Main container widget
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        
        # Title
        self.title = QLabel("VideoState")
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.layout.addWidget(self.title)
        
        # Image count
        self.image_count = QLabel("Images: 0")
        self.layout.addWidget(self.image_count)
        
        # Grid for thumbnails
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.layout.addWidget(self.grid_container)
        
        # Spacer at the bottom
        self.layout.addStretch()
        
        # Set widget in scroll area
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.StyledPanel)
        
        # Current images being displayed
        self.current_images = []
        
        # Subscribe to video state changes
        message_queue.subscribe("state_changed", self.handle_state_change)
        
        # Set up timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.request_update)
        self.update_timer.start(1000)  # Update every second
        
    def handle_state_change(self, message: Dict[str, Any]):
        """
        Handle state change notifications.
        
        Args:
            message: Message dict from the queue
        """
        payload = message.get("payload", {})
        state_type = payload.get("state_type")
        
        # Only process video state changes
        if state_type == "video":
            data = payload.get("data", {})
            images = data.get("images", [])
            
            # Update the display
            self.update_images(images)
    
    def request_update(self):
        """Request an update of the video state from handlers."""
        # This will be called by the WebSocket handlers to update the state
        pass
        
    def update_images(self, images: List[str]):
        """
        Update the thumbnail grid with the current images.
        
        Args:
            images: List of image paths
        """
        # Clear grid if the images have changed
        if set(images) != set(self.current_images):
            # Remove all existing widgets
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Update image count
            self.image_count.setText(f"Images: {len(images)}")
            
            # Add new thumbnails
            for idx, image_path in enumerate(images):
                if os.path.exists(image_path):
                    try:
                        # Create frame for image
                        frame = QFrame()
                        frame.setFrameShape(QFrame.StyledPanel)
                        frame_layout = QVBoxLayout(frame)
                        
                        # Load image and create thumbnail
                        pixmap = QPixmap(image_path)
                        pixmap = pixmap.scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        
                        # Image label
                        image_label = QLabel()
                        image_label.setPixmap(pixmap)
                        image_label.setAlignment(Qt.AlignCenter)
                        frame_layout.addWidget(image_label)
                        
                        # File info label
                        file_name = os.path.basename(image_path)
                        timestamp = datetime.fromtimestamp(os.path.getmtime(image_path))
                        time_str = timestamp.strftime("%H:%M:%S")
                        info_label = QLabel(f"{file_name}\n{time_str}")
                        info_label.setAlignment(Qt.AlignCenter)
                        frame_layout.addWidget(info_label)
                        
                        # Add to grid - 3 columns
                        row = idx // 3
                        col = idx % 3
                        self.grid_layout.addWidget(frame, row, col)
                        
                    except Exception as e:
                        logging.error(f"Error loading thumbnail: {e}")
            
            # Save current images
            self.current_images = images.copy()


class TaskStateWidget(QScrollArea):
    """
    Widget for displaying the current TaskState.
    
    This widget shows the current task, step index, and step details.
    """
    
    def __init__(self, parent=None):
        """Initialize the TaskState widget."""
        super().__init__(parent)
        
        # Main container widget
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        
        # Title
        self.title = QLabel("TaskState")
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.layout.addWidget(self.title)
        
        # Task info section
        self.task_frame = QFrame()
        self.task_frame.setFrameShape(QFrame.StyledPanel)
        self.task_layout = QVBoxLayout(self.task_frame)
        
        # Task name and status
        self.task_name = QLabel("Task: None")
        self.task_name.setStyleSheet("font-weight: bold;")
        self.task_layout.addWidget(self.task_name)
        
        self.task_step = QLabel("Current Step: 0 / 0")
        self.task_layout.addWidget(self.task_step)
        
        self.task_status = QLabel("Status: None")
        self.task_layout.addWidget(self.task_status)
        
        # Add task frame to main layout
        self.layout.addWidget(self.task_frame)
        
        # Current step details
        self.step_frame = QFrame()
        self.step_frame.setFrameShape(QFrame.StyledPanel)
        self.step_layout = QVBoxLayout(self.step_frame)
        
        # Step header
        self.step_header = QLabel("Current Step Details")
        self.step_header.setStyleSheet("font-weight: bold;")
        self.step_layout.addWidget(self.step_header)
        
        # Step action
        self.step_action = QLabel("Action: None")
        self.step_layout.addWidget(self.step_action)
        
        # Focus objects
        self.step_objects_label = QLabel("Focus Objects:")
        self.step_layout.addWidget(self.step_objects_label)
        
        self.step_objects = QTextEdit()
        self.step_objects.setReadOnly(True)
        self.step_objects.setMaximumHeight(100)
        self.step_layout.addWidget(self.step_objects)
        
        # Add step frame to main layout
        self.layout.addWidget(self.step_frame)
        
        # Add stretch at the bottom
        self.layout.addStretch()
        
        # Set widget in scroll area
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.StyledPanel)
        
        # Subscribe to task state changes
        message_queue.subscribe("state_changed", self.handle_state_change)
        
        # Set up timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.request_update)
        self.update_timer.start(1000)  # Update every second
    
    def handle_state_change(self, message: Dict[str, Any]):
        """
        Handle state change notifications.
        
        Args:
            message: Message dict from the queue
        """
        payload = message.get("payload", {})
        state_type = payload.get("state_type")
        
        # Only process task state changes
        if state_type == "task":
            data = payload.get("data", {})
            self.update_task_state(data)
    
    def request_update(self):
        """Request an update of the task state from handlers."""
        # This will be called by the WebSocket handlers to update the state
        pass
    
    def update_task_state(self, data: Dict[str, Any]):
        """
        Update the task state display.
        
        Args:
            data: Task state data
        """
        # Update task info
        task_name = data.get("task_name", "None")
        self.task_name.setText(f"Task: {task_name}")
        
        current_step = data.get("current_step", 0)
        total_steps = data.get("total_steps", 0)
        self.task_step.setText(f"Current Step: {current_step} / {total_steps}")
        
        status = data.get("status", "None")
        self.task_status.setText(f"Status: {status}")
        
        # Update step details
        step_action = data.get("step_action", "None")
        self.step_action.setText(f"Action: {step_action}")
        
        # Update focus objects
        focus_objects = data.get("focus_objects", [])
        if focus_objects:
            objects_text = "\n".join([f"• {obj}" for obj in focus_objects])
            self.step_objects.setText(objects_text)
        else:
            self.step_objects.setText("None")


class WebSocketGUI(QMainWindow):
    """
    Main window for the WebSocket server GUI.
    
    This is the main container for all the UI components.
    """
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("WebSocket Server Monitor")
        self.resize(1200, 800)
        
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        
        # Create main horizontal splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)
        
        # Left pane (TaskState and VideoState)
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        
        # Left vertical splitter for TaskState and VideoState
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_layout.addWidget(self.left_splitter)
        
        # Create VideoState widget
        self.video_state_widget = VideoStateWidget()
        self.left_splitter.addWidget(self.video_state_widget)
        
        # Create TaskState widget
        self.task_state_widget = TaskStateWidget()
        self.left_splitter.addWidget(self.task_state_widget)
        
        # Add left pane to main splitter
        self.main_splitter.addWidget(self.left_widget)
        
        # Right pane (Message Log)
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        
        # Create title for right pane
        self.right_title = QLabel("Messages From Quest")
        self.right_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.right_layout.addWidget(self.right_title)
        
        # Create message log widget
        self.message_log = MessageLogWidget()
        self.right_layout.addWidget(self.message_log)
        
        # Add right pane to main splitter
        self.main_splitter.addWidget(self.right_widget)
        
        # Set default splitter sizes (40% left, 60% right)
        self.main_splitter.setSizes([400, 600])
        
        # Set up timer for processing queue messages
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self.process_messages)
        self.message_timer.start(50)  # Check queue every 50ms
    
    def process_messages(self):
        """Process messages from the queue."""
        message_queue.process_messages(limit=20)
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop timers
        self.message_timer.stop()
        self.video_state_widget.update_timer.stop()
        self.task_state_widget.update_timer.stop()
        
        # Accept the close event
        event.accept()


# Create a singleton instance accessor function
_gui_instance = None
_app_instance = None

def get_gui_instance():
    """Get the singleton GUI instance, ensuring QApplication is created first."""
    global _gui_instance, _app_instance
    
    # Create QApplication instance if it doesn't exist
    if _app_instance is None:
        _app_instance = QApplication.instance()
        if _app_instance is None:
            _app_instance = QApplication(sys.argv)
    
    # Create GUI instance if it doesn't exist
    if _gui_instance is None:
        _gui_instance = WebSocketGUI()
    
    return _gui_instance


async def run_gui_with_async():
    """
    Run the GUI application with asyncio integration.
    
    This function sets up the necessary event loop integration between
    PyQt and asyncio, allowing both to run simultaneously.
    """
    def process_qt_events():
        """Process Qt events and reschedule."""
        # Process all pending UI events immediately
        _app_instance.processEvents()
        # Schedule the next processing very soon (5ms)
        loop.call_later(0.005, process_qt_events)
    
    # Get the GUI and app instances (app is created in get_gui_instance if needed)
    gui = get_gui_instance()
    gui.show()
    
    # Get asyncio event loop
    loop = asyncio.get_event_loop()
    
    # Schedule the first call to process_qt_events
    loop.call_soon(process_qt_events)
    
    # Create a future that will be canceled when the application quits
    shutdown_event = asyncio.Event()
    
    # Handle application quit
    _app_instance.aboutToQuit.connect(lambda: shutdown_event.set())
    
    # Wait for the shutdown event
    try:
        await shutdown_event.wait()
    except asyncio.CancelledError:
        # Handle cancelation if needed
        pass
    
    # Clean up
    _app_instance.quit()


if __name__ == "__main__":
    """
    Standalone execution for testing the GUI independently.
    """
    # Set up logging
    logging.info("Starting WebSocket GUI in standalone mode...")
    
    # Run the app with asyncio
    asyncio.run(run_gui_with_async()) 
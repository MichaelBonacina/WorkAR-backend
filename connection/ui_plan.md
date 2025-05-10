# WebSocket Server GUI Implementation Plan

## Overview
This document outlines the plan for adding a GUI to the WebSocket server that displays real-time information about the server state, including:
- Messages and images from AR glasses clients
- Current VideoState visualization
- Current TaskState visualization

## Architecture

### GUI Framework
We'll use **PyQt5** as the GUI framework due to its:
- Cross-platform compatibility
- Robust threading support for async operations
- Rich widget set for complex UIs
- Good integration with Python async code

### Integration Architecture
The GUI will be integrated with the existing WebSocket server using an event-driven approach:

1. The main window will be launched before starting the WebSocket server
2. A message/event queue will connect the WebSocket handlers to the GUI
3. The WebSocket handlers will emit events when:
   - New messages are received
   - Images are processed
   - State changes occur
4. The GUI will consume these events and update the display accordingly

### Components
1. **Main Window** - Overall container for the GUI
2. **Right Pane** - "Messages From Quest" log display
   - Scrollable text area with timestamps
   - Thumbnail image display for received frames
3. **Left Top Pane** - "VideoState" visualization
   - Grid/list of thumbnail images currently in VideoState
   - Timestamps for each image
4. **Left Bottom Pane** - "TaskState" visualization
   - Current task name and step index
   - Current step details
   - Previous/next step preview

## Implementation Plan

### 1. Setup GUI Framework
- [x] Add PyQt5 to requirements.txt
- [x] Create a new file `connection/gui_app.py` for the main GUI application

### 2. Create Message Queue System
- [x] Create a message queue class that will mediate between WebSocket handlers and GUI
- [x] Define message types (text log, image received, state changed)
- [x] Implement queue publish/subscribe methods

#### Message Queue Design Details
The message queue will serve as a bridge between the WebSocket server (running in the asyncio event loop) and the GUI (running in the PyQt event loop):

##### Structure
- Implement a thread-safe queue using Python's `queue.Queue` or a custom implementation
- Use a publisher-subscriber pattern where WebSocket handlers publish events and GUI components subscribe to them
- Create a central `MessageQueue` class in a new file `connection/message_queue.py`

##### Message Types
1. Log messages:
   - Text messages with timestamps
   - Severity levels (info, warning, error)
   - Source identifier (client address, server)

2. Image messages:
   - Image path or data
   - Associated metadata (timestamp, dimensions, etc.)
   - Processing status (received, processed, etc.)

3. State change notifications:
   - VideoState updates (added/removed images)
   - TaskState updates (current step, status changes)
   - Server state (connected clients, processing status)

##### Implementation
```python
# Example message structure
{
    "type": "image_received",  # Message type
    "timestamp": "2023-05-01 14:30:22.123",  # When the event occurred
    "payload": {
        "image_path": "/path/to/image.jpg",
        "metadata": { ... },  # Original metadata from client
        "client_addr": "192.168.1.5:8080"
    }
}
```

##### Cross-Thread Communication
- Use PyQt's signals and slots mechanism to safely move data between threads
- Define a custom signal: `new_message_signal = pyqtSignal(dict)`
- Register signal handlers in GUI components to process queue messages
- Implement a timer in the GUI thread that periodically checks for new messages
- Use `QTimer.singleShot()` for non-blocking message processing

##### Queue Management
- Implement maximum queue size to prevent memory issues (configurable)
- Add policy for handling queue overflow (drop oldest, block, etc.)
- Store image references rather than image data in the queue
- Add message filtering capabilities for subscribers

### 3. Create Main Window
- [x] Design the main window layout with splitters for panes
- [x] Implement window initialization and PyQt event loop integration with asyncio

### 4. Implement Right Pane (Message Log)
- [x] Create a custom widget for the message log
- [x] Implement text and image rendering in the log
- [x] Add auto-scrolling to keep most recent messages visible

### 5. Implement Left Top Pane (VideoState)
- [x] Create a custom widget for displaying the VideoState
- [x] Implement thumbnail grid view of images in VideoState
- [x] Add refresh mechanism when VideoState changes

### 6. Implement Left Bottom Pane (TaskState)
- [x] Create a custom widget for displaying the TaskState
- [x] Show current task name, step index, and step details
- [x] Display focus objects and any detected coordinates

### 7. Modify WebSocket Handlers
- [x] Update `websocket_handlers.py` to emit events to the message queue
- [x] Add hooks in key processing points to publish state changes
- [x] Ensure all incoming/outgoing messages are published to the queue

### 8. Update WebSocket Server Launch
- [x] Modify `websocket.py` to initialize and launch the GUI before starting the server
- [x] Update standalone test mode to include GUI initialization

### 9. Add Graceful Shutdown
- [x] Implement proper shutdown sequence for both GUI and WebSocket server
- [x] Ensure all resources are properly released

## Technical Considerations

### Threading Model
- WebSocket server runs in asyncio event loop
- PyQt has its own event loop
- Need to ensure proper integration between these two event loops:
  - [x] Use QEventLoop with asyncio integration
  - [x] Implement thread-safe queue for cross-thread communication

### Performance
- [x] Implement efficient image loading/scaling for thumbnails
- [x] Limit message history to prevent memory growth
- [x] Use lazy loading for image rendering in logs

### Error Handling
- [x] Add robust error handling in GUI components
- [x] Ensure GUI doesn't crash when WebSocket encounters errors
- [x] Log GUI-specific errors appropriately

## Timeline Estimate
1. Setup and architecture: 1 day
2. Main window and message queue: 1 day
3. Right pane implementation: 1 day
4. Left panes implementation: 1-2 days
5. Integration with WebSocket handlers: 1 day
6. Testing and refinement: 1-2 days

Total estimated time: 6-8 days of development effort

"""
Message queue system for communication between WebSocket server and GUI.

This module provides a thread-safe message queue that allows the WebSocket handlers
to send messages and images to the GUI components across different thread contexts.
"""

import queue
import json
import logging
import datetime
from typing import Dict, Any, List, Callable, Optional, Set, Union

# Configure logging
logging.basicConfig(
    format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%m-%d %H:%M:%S',
    level=logging.INFO
)

class MessageQueue:
    """
    Thread-safe message queue for communication between WebSocket handlers and GUI.
    
    Implements a publisher-subscriber pattern where WebSocket handlers publish
    events and GUI components subscribe to them.
    """
    _instance = None  # Singleton instance
    
    def __new__(cls):
        """Ensure singleton pattern for MessageQueue."""
        if cls._instance is None:
            cls._instance = super(MessageQueue, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the message queue if not already initialized."""
        if not self._initialized:
            # Main message queue
            self._queue = queue.Queue(maxsize=1000)  # Limit queue size to prevent memory issues
            
            # Subscribers dict: message_type -> list of callbacks
            self._subscribers: Dict[str, List[Callable]] = {}
            
            # Set of all message types we've seen (for introspection/debugging)
            self._known_message_types: Set[str] = set()
            
            self._initialized = True
            logging.info("MessageQueue initialized")
    
    def publish(self, msg_type: str, payload: Dict[str, Any] = None) -> bool:
        """
        Publish a message to the queue.
        
        Args:
            msg_type: Type of message (e.g., "log", "image_received", "state_changed")
            payload: Dictionary containing message data
            
        Returns:
            bool: True if message was published, False if queue was full
        """
        if payload is None:
            payload = {}
        
        # Create message with timestamp and type
        message = {
            "type": msg_type,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "payload": payload
        }
        
        # Add to known message types
        self._known_message_types.add(msg_type)
        
        # Try to add to queue, non-blocking
        try:
            self._queue.put_nowait(message)
            return True
        except queue.Full:
            logging.warning(f"Message queue full, dropping message of type: {msg_type}")
            return False
    
    def subscribe(self, msg_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe to a specific message type.
        
        Args:
            msg_type: Type of message to subscribe to
            callback: Function to call when a message of this type is processed
        """
        if msg_type not in self._subscribers:
            self._subscribers[msg_type] = []
        
        if callback not in self._subscribers[msg_type]:
            self._subscribers[msg_type].append(callback)
            logging.debug(f"Added subscriber for message type: {msg_type}")
    
    def unsubscribe(self, msg_type: str, callback: Callable) -> bool:
        """
        Unsubscribe from a specific message type.
        
        Args:
            msg_type: Type of message to unsubscribe from
            callback: Function to remove from subscribers
            
        Returns:
            bool: True if the callback was removed, False if it wasn't found
        """
        if msg_type in self._subscribers and callback in self._subscribers[msg_type]:
            self._subscribers[msg_type].remove(callback)
            logging.debug(f"Removed subscriber for message type: {msg_type}")
            return True
        return False
    
    def process_messages(self, limit: int = 20) -> int:
        """
        Process pending messages in the queue and dispatch to subscribers.
        
        This should be called periodically from the GUI thread.
        
        Args:
            limit: Maximum number of messages to process in one call
            
        Returns:
            int: Number of messages processed
        """
        count = 0
        
        # Collect messages to process in a batch
        messages_to_process = []
        
        # Get up to limit messages (non-blocking)
        for _ in range(limit):
            try:
                message = self._queue.get_nowait()
                messages_to_process.append(message)
            except queue.Empty:
                break
        
        # Group messages by type for batch processing
        message_by_type = {}
        for message in messages_to_process:
            msg_type = message.get("type", "unknown")
            if msg_type not in message_by_type:
                message_by_type[msg_type] = []
            message_by_type[msg_type].append(message)
            
            # Mark message as done in queue immediately
            self._queue.task_done()
            count += 1
        
        # Process messages by type (reduces context switching overhead)
        for msg_type, messages in message_by_type.items():
            # Dispatch to subscribers for this message type
            if msg_type in self._subscribers:
                for callback in self._subscribers[msg_type]:
                    try:
                        # For log messages, process them in batches to reduce UI updates
                        if msg_type == "log" and len(messages) > 5:
                            # Just process the first and last few messages if there are many
                            batch_size = min(3, len(messages) // 2)
                            for message in messages[:batch_size] + messages[-batch_size:]:
                                callback(message)
                        else:
                            # Process all messages individually for other types
                            for message in messages:
                                callback(message)
                    except Exception as e:
                        logging.error(f"Error in subscriber callback for {msg_type}: {e}")
        
        # Also dispatch to "all" subscribers
        if "all" in self._subscribers and messages_to_process:
            for callback in self._subscribers["all"]:
                try:
                    for message in messages_to_process:
                        callback(message)
                except Exception as e:
                    logging.error(f"Error in 'all' subscriber callback: {e}")
        
        return count
    
    def get_queue_size(self) -> int:
        """
        Get current number of messages in the queue.
        
        Returns:
            int: Queue size
        """
        return self._queue.qsize()
    
    def get_known_message_types(self) -> Set[str]:
        """
        Get all message types that have been published.
        
        Returns:
            set: Set of known message types
        """
        return self._known_message_types.copy()


# Create singleton instance
message_queue = MessageQueue()


# Convenience functions for publishing common message types

def log_message(level: str, message: str, source: str = "server") -> bool:
    """
    Log a text message to the queue.
    
    Args:
        level: Log level (info, warning, error)
        message: Text message
        source: Source identifier
        
    Returns:
        bool: True if message was published
    """
    return message_queue.publish("log", {
        "level": level,
        "message": message,
        "source": source
    })

def image_received(image_path: str, metadata: Dict[str, Any], client_addr: str) -> bool:
    """
    Notify that an image was received from a client.
    
    Args:
        image_path: Path to the saved image
        metadata: Image metadata
        client_addr: Client address
        
    Returns:
        bool: True if message was published
    """
    return message_queue.publish("image_received", {
        "image_path": image_path,
        "metadata": metadata,
        "client_addr": client_addr
    })

def state_changed(state_type: str, data: Dict[str, Any]) -> bool:
    """
    Notify of a state change (VideoState, TaskState).
    
    Args:
        state_type: Type of state that changed (video, task, server)
        data: State data
        
    Returns:
        bool: True if message was published
    """
    return message_queue.publish("state_changed", {
        "state_type": state_type,
        "data": data
    }) 
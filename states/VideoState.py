import collections

class VideoState:
    """Manages a list of the last ten images, removing the oldest when full."""
    def __init__(self):
        """Initializes the VideoState with a deque to hold up to ten images."""
        self.images = collections.deque(maxlen=10)

    def add_image(self, image):
        """
        Adds a new image to the state.
        If there are already ten images, the oldest one is automatically removed.
        """
        self.images.append(image)

    def get_images(self):
        """
        Returns the list of currently stored images.
        """
        return list(self.images)

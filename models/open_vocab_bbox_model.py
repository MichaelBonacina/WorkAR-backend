from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PIL import Image

from .image_processing_base import BaseImageUtilModel
from .model_utils import ImageInfo, ObjectPoint, logger


@dataclass
class OpenVocabBBoxDetectionResponse:
    """Base response for open-vocabulary bounding box detection models."""
    objects: List[ObjectPoint]
    raw_response: Dict[str, Any] = field(default_factory=dict)


class OpenVocabBBoxDetectionModel(BaseImageUtilModel, ABC):
    """
    Abstract base class for open-vocabulary bounding box detection models.

    These models can detect arbitrary objects in an image based on a textual query.
    """

    def __init__(self, max_retries: int = 3):
        # BaseImageUtilModel does not have an __init__, so no super() call for it here.
        self.max_retries = max_retries
        # Concrete classes should log their specific initialization details.

    @abstractmethod
    def __call__(self, image_input: Any, object_name: str) -> OpenVocabBBoxDetectionResponse:
        """
        Processes an image to detect occurrences of a specified object.

        Args:
            image_input: The input image. This can be a file path (str or Path),
                         or a PIL Image object.
            object_name: The name of the object to detect in the image (textual query).

        Returns:
            An OpenVocabBBoxDetectionResponse containing the detected objects and
            raw API response. Concrete implementations will return subclasses of
            this response type if they have additional fields.
        """
        pass

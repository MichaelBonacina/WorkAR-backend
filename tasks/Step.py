from typing import List, Dict, Any

class Step:
    """Represents a single step in a task, with an action and focus objects.
    
    JSON Format:
    ```json
    {
        "action": "pick up",
        "focus_objects": ["hammer", "nail"]
    }
    ```
    """
    def __init__(self, action: str, focus_objects: List[str]):
        """
        Initializes a Step object.

        Args:
            action: The action to be performed in this step.
            focus_objects: A list of strings representing the objects of focus for this action.
        """
        self._action: str = action
        self._focus_objects: List[str] = focus_objects

    def get_action(self) -> str:
        """Returns the action of the step."""
        return self._action

    def set_action(self, action: str) -> None:
        """Sets the action of the step."""
        self._action = action

    def get_focus_objects(self) -> List[str]:
        """Returns the list of focus objects for the step."""
        return self._focus_objects

    def set_focus_objects(self, focus_objects: List[str]) -> None:
        """Sets the list of focus objects for the step."""
        self._focus_objects = focus_objects

    def to_json(self) -> Dict[str, Any]:
        """
        Converts the Step to a JSON-serializable dictionary.
        
        Returns:
            A dictionary with the following structure:
            {
                "action": str,         # The action to be performed
                "focus_objects": list  # List of strings representing objects of focus
            }
        """
        return {
            "action": self._action,
            "focus_objects": self._focus_objects
        }

    def to_human_readable(self) -> str:
        """
        Returns a human-readable representation of the step.
        
        Returns:
            A string describing the action and focus objects in a more reader-friendly format.
        """
        if self._action == "none":
            return "No action required"
        
        if not self._focus_objects:
            return f"{self._action}"
        elif len(self._focus_objects) == 1:
            return f"{self._action} (object: {self._focus_objects[0]})"
        else:
            # Format as "action object1, object2, and object3"
            objects_text = ", ".join(self._focus_objects[:-1]) + f", and {self._focus_objects[-1]}"
            return f"{self._action} (objects: {objects_text})"

    def __repr__(self) -> str:
        return f"Step(action='{self._action}', focus_objects={self._focus_objects})"

from typing import List

class Step:
    """Represents a single step in a task, with an action and focus objects."""
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

    def __repr__(self) -> str:
        return f"Step(action='{self._action}', focus_objects={self._focus_objects})"

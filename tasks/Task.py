from typing import List, Union
from tasks.Step import Step # Import Step class

class Task:
    # todo: accept only steps, not dicts
    def __init__(self, name: str, task_list: List[Union[Step, dict]] = None):
        self._name = name
        # Initialize _task_list before using the setter for the None case or empty list
        if task_list is None:
            self._task_list: List[Step] = []
        else:
            # Use the setter for validation and conversion if task_list is provided
            self.task_list = task_list

    @property
    def name(self) -> str:
        """Gets the name of the task."""
        return self._name

    @name.setter
    def name(self, value: str):
        """Sets the name of the task."""
        if not isinstance(value, str):
            raise TypeError("Name must be a string")
        self._name = value

    @property
    def task_list(self) -> List[Step]:
        """Gets the list of task steps."""
        return self._task_list

    @task_list.setter
    def task_list(self, value: List[Union[Step, dict]]):
        """Sets the list of task steps, converting dicts to Step objects after validation."""
        if value is None:
            self._task_list = []
            return

        if not isinstance(value, list):
            raise TypeError("task_list must be a list or None.")
        
        validated_steps: List[Step] = []
        for item in value:
            if isinstance(item, Step):
                validated_steps.append(item)
            elif isinstance(item, dict):
                # Validate dictionary structure before creating a Step object
                if 'focus_objects' not in item:
                    raise ValueError(f"Step dictionary is missing 'focus_objects' key: {item}")
                if not isinstance(item['focus_objects'], list):
                    raise TypeError(f"'focus_objects' in a step must be a list. Found: {type(item['focus_objects'])} in {item}")
                for obj in item['focus_objects']:
                    if not isinstance(obj, str):
                        raise TypeError(f"Each item in 'focus_objects' must be a string. Found: {type(obj)} in {item['focus_objects']}")
                
                if 'action' not in item:
                    raise ValueError(f"Step dictionary is missing 'action' key: {item}")
                if not isinstance(item['action'], str):
                    raise TypeError(f"'action' in a step must be a string. Found: {type(item['action'])} in {item}")
                
                validated_steps.append(Step(action=item['action'], focus_objects=item['focus_objects']))
            else:
                raise TypeError(f"Each item in task_list must be a Step object or a dictionary. Found: {type(item)}")
        
        self._task_list = validated_steps

    def getStep(self, index: int) -> Step:
        """Returns the Step object at the specified index in the task list."""
        if not isinstance(index, int):
            raise TypeError("Index must be an integer.")
        if index < 0 or index >= len(self._task_list):
            return Step(action="none", focus_objects=[])
        return self._task_list[index]

    def __repr__(self):
        return f"Task(name='{self.name}', task_list={self.task_list})"


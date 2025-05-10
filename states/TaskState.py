from tasks.Task import Task
from tasks.Step import Step

class TaskState:
    def __init__(self, task: Task, index: int):
        if not isinstance(task, Task):
            raise TypeError("task must be an instance of Task")
        self._task = task
        
        if not isinstance(index, int):
            raise TypeError("index must be an integer")
        self._index = index

    @property
    def task(self) -> Task:
        """Gets the Task object."""
        return self._task

    @task.setter
    def task(self, value: Task):
        """Sets the Task object."""
        if not isinstance(value, Task):
            raise TypeError("task must be an instance of Task")
        self._task = value

    @property
    def index(self) -> int:
        """Gets the index."""
        return self._index

    @index.setter
    def index(self, value: int):
        """Sets the index."""
        if not isinstance(value, int):
            raise TypeError("index must be an integer")
        self._index = value
    
    def getCurrentStep(self) -> Step:
        """Returns the Step object from the task at the current index."""
        return self._task.getStep(self._index)

    def getPreviousStep(self) -> Step:
        """Returns the Step object from the task at the current index - 1.
           Returns a default Step if the index is out of bounds.
        """
        return self._task.getStep(self._index - 1)

    def getNextStep(self) -> Step:
        """Returns the Step object from the task at the current index + 1.
           Returns a default Step if the index is out of bounds.
        """
        return self._task.getStep(self._index + 1)

    def __repr__(self):
        return f"TaskState(task={self.task}, index={self.index})"

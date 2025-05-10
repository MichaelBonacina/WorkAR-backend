from tasks.Task import Task
from tasks.Step import Step

class TaskState:
    """Represents the state of a Task at a specific step index.
    
    This class maintains a reference to a Task object and keeps track of the 
    current step index within that task.
    
    Attributes:
        _task: The Task object being tracked.
        _index: The current step index within the task.
    """
    
    def __init__(self, task: Task, index: int):
        """Initializes a new TaskState instance.
        
        Args:
            task: A Task object to track.
            index: The initial step index.
        
        Raises:
            TypeError: If task is not a Task instance or index is not an integer.
        """
        if not isinstance(task, Task):
            raise TypeError("task must be an instance of Task")
        self._task = task
        
        if not isinstance(index, int):
            raise TypeError("index must be an integer")
        self._index = index

    @property
    def task(self) -> Task:
        """Gets the Task object.
        
        Returns:
            The Task object being tracked.
        """
        return self._task

    @task.setter
    def task(self, value: Task):
        """Sets the Task object.
        
        Args:
            value: A Task object to track.
            
        Raises:
            TypeError: If value is not a Task instance.
        """
        if not isinstance(value, Task):
            raise TypeError("task must be an instance of Task")
        self._task = value

    @property
    def index(self) -> int:
        """Gets the current step index.
        
        Returns:
            The current step index within the task.
        """
        return self._index

    @index.setter
    def index(self, value: int):
        """Sets the current step index.
        
        Args:
            value: The new step index.
            
        Raises:
            TypeError: If value is not an integer.
        """
        if not isinstance(value, int):
            raise TypeError("index must be an integer")
        self._index = value
    
    def getCurrentStep(self) -> Step:
        """Returns the Step object at the current index.
        
        Returns:
            The Step object from the task at the current index.
        """
        return self._task.getStep(self._index)

    def getPreviousStep(self) -> Step:
        """Returns the Step object at the previous index.
        
        Returns:
            The Step object from the task at the current index - 1,
            or a default Step if the index is out of bounds.
        """
        return self._task.getStep(self._index - 1)

    def getNextStep(self) -> Step:
        """Returns the Step object at the next index.
        
        Returns:
            The Step object from the task at the current index + 1,
            or a default Step if the index is out of bounds.
        """
        return self._task.getStep(self._index + 1)
    
    def moveToNextStep(self) -> Step:
        """Increments the current index and returns the new current step.
        
        Returns:
            The Step object from the task at the newly incremented index,
            or None if there are no more steps (end of task).
        """
        self._index += 1
        
        # Check if we've reached the end of steps
        if self._index >= len(self._task.task_list):
            return None
            
        return self.getCurrentStep()

    def __repr__(self):
        """Returns a string representation of the TaskState.
        
        Returns:
            A string representation showing the task and index.
        """
        return f"TaskState(task={self.task}, index={self.index})"

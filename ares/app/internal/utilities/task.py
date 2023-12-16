from uuid import uuid4
import datetime

from app.utils.loggers import base_logger as logger


class TaskStorage():
    tasks = {}

class Task(TaskStorage):
    def __init__(self, task_type: str, progress_type: str, task_name: str) -> None:
        """ Creates a new task and adds it to the tasks dict.

        Args:
            task_type (str): Source type of the task (e.g. "download-video")
            progress_type (str): Type of progress (either "percent" or "boolean")
        """
        
        super().__init__()
        self.task_id = str(uuid4())
        self.task_type = task_type
        self.progress_type = progress_type
        
        super().tasks[self.task_id] = {
            "progress": {
                "status": "in-progress",
                "type": progress_type,
                "value": 0 if progress_type == "percent" else None,
                "failures": []
            },
            "objects_ids": {},
            "type": task_type,
            "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": task_name,
            "callback": None
        }

    def update_task_progress(self, progress: float):
        """ Updates the progress of a task.

        Args:
            progress (float): Progress value 

        Raises:
            ValueError: Progress cannot be greater than 100%
            ValueError: Progress cannot be updated for boolean progress type
        """
        
        if (self.progress_type == "percent") and (progress > 100):
            raise ValueError("Progress cannot be greater than 100%")
        elif (self.progress_type == "boolean"):
            raise ValueError("Progress cannot be updated for boolean progress type")
        
        super().tasks[self.task_id]["progress"]["value"] = round(progress, 2)
        
    def complete_task(self):
        """ Completes a task.
        """
        
        if (self.progress_type == "percent"):
            super().tasks[self.task_id]["progress"]["value"] = 100
        super().tasks[self.task_id]["progress"]["status"] = "completed"
        
    def add_error(self, error: Exception, game_id: str = None):
        """ Adds an error to a task.

        Args:
            error (Exception): Error to add
        """
        
        task_manager.tasks[self.task_id]["progress"]["failures"].append({
            "error": str(error),
            "game_id": game_id
        })
        
    def add_object_id(self, object_name: str, object_id: str):
        """ Adds an object ID to a task.

        Args:
            object_name (str): Name of the object
            object_id (str): ID of the object
        """
        
        task_manager.tasks[self.task_id]["objects_ids"][object_name] = object_id

    def update_task(self, progress: float = None):
        """ Updates the progress of a task and completes it if progress is 100%.

        Args:
            progress (float, optional): Progress value. Defaults to None.
        """
        
        if progress is not None:
            if (progress < 100):
                self.update_task_progress(progress)
            else:
                self.complete_task()   
                
    def toDict(self):
        """ Returns the task as a dict.
        """
        
        return {
            "task_id": self.task_id,
            "task_data": super().tasks[self.task_id],
        }
        
    def set_cancel_callback(self, callback):
        """ Sets the callback to call when the task is cancelled.

        Args:
            callback (function): Callback to call
        """
        
        super().tasks[self.task_id]["callback"] = callback

class TaskManager(TaskStorage):
    def __init__(self) -> None:
        super().__init__()
        
    def create_task(self, task_type: str, progress_type: str, task_name: str) -> Task:
        """ Creates a new task and adds it to the tasks dict.

        Args:
            task_type (str): Source type of the task (e.g. "download-video")
            progress_type (str): Type of progress (either "percent" or "boolean")
            task_name (str): Name of the task
        """
        
        task = Task(task_type, progress_type, task_name)
        
        return task
    
    def get_task(self, task_id: str) -> Task:
        """ Returns a task from the tasks dict.

        Args:
            task_id (str): Task ID
        """
        
        return self.tasks.get(task_id)
    
    def delete_task(self, task_id: str) -> None:
        """ Deletes a task from the tasks dict.

        Args:
            task_id (str): Task ID
        """
        
        logger.info(f"Deleting task {task_id}")
        
        if task_id in self.tasks:
            if self.tasks[task_id]["callback"]:
                self.tasks[task_id]["callback"]()
            del self.tasks[task_id]
        
    def get_tasks(self) -> dict:
        """ Returns all tasks from the tasks dict in a array order by task creation date.
        """
        
        formatted_tasks = []
        for task_id, task in self.tasks.items():
            formatted_tasks.append({
                "task_id": task_id,
                "task_data": task,
            })
            
        formatted_tasks.sort(key=lambda x: x["task_data"]["started_at"], reverse=True)

        return formatted_tasks
    

task_manager = TaskManager()
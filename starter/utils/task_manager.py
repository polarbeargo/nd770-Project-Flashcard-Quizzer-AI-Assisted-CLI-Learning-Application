"""
Task management utility demonstrating basic CRUD operations.

This module shows how to structure a simple data management class
that students can extend with AI assistance.
"""

from typing import List, Dict, Any
from datetime import datetime


class TaskManager:
    """A simple task management system for demonstration purposes."""
    
    def __init__(self):
        self._tasks: List[Dict[str, Any]] = []
        self._next_id = 1
    
    def add_task(self, description: str, priority: str = "medium") -> int:
        """Add a new task and return its ID."""
        task = {
            "id": self._next_id,
            "description": description,
            "priority": priority,
            "completed": False,
            "created_at": datetime.now().isoformat()
        }
        self._tasks.append(task)
        self._next_id += 1
        return task["id"]
    
    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Get a specific task by ID."""
        for task in self._tasks:
            if task["id"] == task_id:
                return task
        raise ValueError(f"Task with ID {task_id} not found")
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks."""
        return self._tasks.copy()
    
    def complete_task(self, task_id: int) -> None:
        """Mark a task as completed."""
        task = self.get_task(task_id)
        task["completed"] = True
        task["completed_at"] = datetime.now().isoformat()
    
    def delete_task(self, task_id: int) -> None:
        """Delete a task by ID."""
        self._tasks = [task for task in self._tasks if task["id"] != task_id]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tasks": self._tasks,
            "next_id": self._next_id
        }
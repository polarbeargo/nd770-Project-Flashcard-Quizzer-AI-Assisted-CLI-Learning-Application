"""
Unit tests for the TaskManager class.

These tests demonstrate proper testing practices and serve as
examples for students to follow when writing their own tests.
"""

import pytest
from datetime import datetime
from utils.task_manager import TaskManager


class TestTaskManager:
    """Test suite for TaskManager functionality."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.task_manager = TaskManager()
    
    def test_add_task_returns_id(self):
        """Test that adding a task returns a valid ID."""
        task_id = self.task_manager.add_task("Test task")
        assert isinstance(task_id, int)
        assert task_id > 0
    
    def test_add_task_with_priority(self):
        """Test adding a task with a specific priority."""
        task_id = self.task_manager.add_task("High priority task", priority="high")
        task = self.task_manager.get_task(task_id)
        assert task["priority"] == "high"
    
    def test_get_task_by_id(self):
        """Test retrieving a task by its ID."""
        task_id = self.task_manager.add_task("Test task")
        task = self.task_manager.get_task(task_id)
        assert task["id"] == task_id
        assert task["description"] == "Test task"
        assert task["completed"] is False
    
    def test_get_nonexistent_task_raises_error(self):
        """Test that getting a non-existent task raises ValueError."""
        with pytest.raises(ValueError, match="Task with ID 999 not found"):
            self.task_manager.get_task(999)
    
    def test_get_all_tasks(self):
        """Test retrieving all tasks."""
        self.task_manager.add_task("Task 1")
        self.task_manager.add_task("Task 2")
        tasks = self.task_manager.get_all_tasks()
        assert len(tasks) == 2
        assert tasks[0]["description"] == "Task 1"
        assert tasks[1]["description"] == "Task 2"
    
    def test_complete_task(self):
        """Test marking a task as completed."""
        task_id = self.task_manager.add_task("Complete me")
        self.task_manager.complete_task(task_id)
        task = self.task_manager.get_task(task_id)
        assert task["completed"] is True
        assert "completed_at" in task
    
    def test_delete_task(self):
        """Test deleting a task."""
        task_id = self.task_manager.add_task("Delete me")
        self.task_manager.delete_task(task_id)
        with pytest.raises(ValueError):
            self.task_manager.get_task(task_id)
    
    def test_to_dict(self):
        """Test converting TaskManager to dictionary."""
        self.task_manager.add_task("Test task")
        data = self.task_manager.to_dict()
        assert "tasks" in data
        assert "next_id" in data
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["description"] == "Test task"
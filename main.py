"""
Main entry point for the AI-assisted development project.

This is a starter template for students to build upon. The example shows
a simple task management system that can be extended with AI assistance.
"""

from utils.task_manager import TaskManager
from utils.file_handler import FileHandler


def main():
    """Main function to demonstrate the application structure."""
    print("Welcome to the AI-Assisted Development Project!")
    print("=" * 50)
    
    # Initialize components
    task_manager = TaskManager()
    file_handler = FileHandler()
    
    # Example usage - students can extend this
    task_manager.add_task("Learn about design patterns")
    task_manager.add_task("Implement new features with AI assistance")
    task_manager.add_task("Write comprehensive tests")
    
    print("\nCurrent tasks:")
    for task in task_manager.get_all_tasks():
        print(f"- {task}")
    
    # Save tasks to file
    file_handler.save_data("tasks.json", task_manager.to_dict())
    print("\nTasks saved to tasks.json")


if __name__ == "__main__":
    main()
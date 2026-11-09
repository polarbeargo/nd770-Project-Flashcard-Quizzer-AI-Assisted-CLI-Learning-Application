"""
File handling utility for data persistence.

This module demonstrates file I/O operations and error handling
patterns that students can learn from and extend.
"""

import json
from pathlib import Path
from typing import Any, Dict


class FileHandler:
    """Handle file operations for data persistence."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def save_data(self, filename: str, data: Dict[str, Any]) -> None:
        """Save data to a JSON file."""
        filepath = self.data_dir / filename
        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
        except (IOError, TypeError) as e:
            raise RuntimeError(f"Failed to save data to {filename}: {e}")

    def load_data(self, filename: str) -> Dict[str, Any]:
        """Load data from a JSON file."""
        filepath = self.data_dir / filename
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except (IOError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to load data from {filename}: {e}")

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in the data directory."""
        return (self.data_dir / filename).exists()

    def delete_file(self, filename: str) -> None:
        """Delete a file from the data directory."""
        filepath = self.data_dir / filename
        if filepath.exists():
            filepath.unlink()

    def list_files(self) -> list[str]:
        """List all files in the data directory."""
        return [f.name for f in self.data_dir.iterdir() if f.is_file()]

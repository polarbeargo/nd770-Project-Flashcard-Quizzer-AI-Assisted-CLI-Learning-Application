"""
Unit tests for the FileHandler class.

These tests demonstrate file I/O testing patterns and proper
cleanup of test artifacts.
"""

import shutil
import tempfile

import pytest

from utils.file_handler import FileHandler


class TestFileHandler:
    """Test suite for FileHandler functionality."""

    def setup_method(self):
        """Set up test fixtures with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.file_handler = FileHandler(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir)

    def test_save_data_creates_file(self):
        """Test that save_data creates a file with correct content."""
        data = {"test": "data", "number": 42}
        self.file_handler.save_data("test.json", data)

        assert self.file_handler.file_exists("test.json")
        loaded_data = self.file_handler.load_data("test.json")
        assert loaded_data == data

    def test_load_nonexistent_file_returns_empty_dict(self):
        """Test that loading a non-existent file returns empty dict."""
        result = self.file_handler.load_data("nonexistent.json")
        assert result == {}

    def test_save_invalid_data_raises_error(self):
        """Test that saving invalid JSON data raises RuntimeError."""
        # Create data that can't be serialized to JSON
        invalid_data = {"function": lambda x: x}
        with pytest.raises(RuntimeError, match="Failed to save data"):
            self.file_handler.save_data("invalid.json", invalid_data)

    def test_file_exists(self):
        """Test file existence checking."""
        assert not self.file_handler.file_exists("test.json")
        self.file_handler.save_data("test.json", {"test": "data"})
        assert self.file_handler.file_exists("test.json")

    def test_delete_file(self):
        """Test file deletion."""
        self.file_handler.save_data("test.json", {"test": "data"})
        assert self.file_handler.file_exists("test.json")

        self.file_handler.delete_file("test.json")
        assert not self.file_handler.file_exists("test.json")

    def test_delete_nonexistent_file_no_error(self):
        """Test that deleting non-existent file doesn't raise error."""
        self.file_handler.delete_file("nonexistent.json")  # Should not raise

    def test_list_files(self):
        """Test listing files in data directory."""
        self.file_handler.save_data("file1.json", {"data": 1})
        self.file_handler.save_data("file2.json", {"data": 2})

        files = self.file_handler.list_files()
        assert len(files) == 2
        assert "file1.json" in files
        assert "file2.json" in files

    @pytest.mark.parametrize(
        "operation",
        [
            lambda handler, filename: handler.save_data(filename, {"outside": True}),
            lambda handler, filename: handler.load_data(filename),
            lambda handler, filename: handler.file_exists(filename),
            lambda handler, filename: handler.delete_file(filename),
        ],
    )
    def test_file_operations_reject_parent_traversal(self, tmp_path, operation):
        handler = FileHandler(str(tmp_path / "data"))
        outside = tmp_path / "outside.json"
        outside.write_text('{"inside": false}', encoding="utf-8")

        with pytest.raises(ValueError, match="within the data directory"):
            operation(handler, "../outside.json")

        assert outside.read_text(encoding="utf-8") == '{"inside": false}'

    @pytest.mark.parametrize(
        "operation",
        [
            lambda handler, filename: handler.save_data(filename, {"outside": True}),
            lambda handler, filename: handler.load_data(filename),
            lambda handler, filename: handler.file_exists(filename),
            lambda handler, filename: handler.delete_file(filename),
        ],
    )
    def test_file_operations_reject_absolute_paths(self, tmp_path, operation):
        handler = FileHandler(str(tmp_path / "data"))
        outside = tmp_path / "outside.json"
        outside.write_text('{"inside": false}', encoding="utf-8")

        with pytest.raises(ValueError, match="within the data directory"):
            operation(handler, str(outside))

        assert outside.read_text(encoding="utf-8") == '{"inside": false}'

    @pytest.mark.parametrize(
        "operation",
        [
            lambda handler, filename: handler.save_data(filename, {"outside": True}),
            lambda handler, filename: handler.load_data(filename),
            lambda handler, filename: handler.file_exists(filename),
            lambda handler, filename: handler.delete_file(filename),
        ],
    )
    def test_file_operations_reject_symlinked_parent_escape(self, tmp_path, operation):
        data_dir = tmp_path / "data"
        handler = FileHandler(str(data_dir))
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside = outside_dir / "outside.json"
        outside.write_text('{"inside": false}', encoding="utf-8")
        try:
            (data_dir / "linked").symlink_to(outside_dir, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            pytest.skip(f"symlinks are unavailable: {exc}")

        with pytest.raises(ValueError, match="within the data directory"):
            operation(handler, "linked/outside.json")

        assert outside.read_text(encoding="utf-8") == '{"inside": false}'

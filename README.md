# AI-Assisted Development Project Starter

This is a Python project template for learning AI-assisted software development. You will build upon this foundation to create a functional application while collaborating with AI coding assistants to apply software engineering best practices including design patterns, separation of concerns, test-driven development, and comprehensive documentation.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Setup Instructions

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

4. **Run tests:**
   ```bash
   python -m pytest
   ```

### 🛠️ Development Tools

#### Code Quality Tools

- **Black**: Code formatter
  ```bash
  black .
  ```

- **isort**: Import organizer
  ```bash
  isort .
  ```

- **flake8**: Linting
  ```bash
  flake8 .
  ```

- **mypy**: Type checking
  ```bash
  mypy .
  ```

- **pytest**: Testing framework
  ```bash
  python -m pytest --cov=. --cov-report=html
  ```

#### Pre-commit Hooks (Optional)

Set up pre-commit hooks for automatic code quality checks:

```bash
pre-commit install
```

## Testing

The project includes comprehensive unit tests demonstrating proper testing practices for AI-assisted development.

### Tests Break Down

**TaskManager Tests (`test_task_manager.py`):**
- `test_add_task_returns_id()` - Verifies task creation returns valid ID
- `test_get_task_by_id()` - Tests task retrieval with proper data structure
- `test_complete_task()` - Validates task completion with timestamps
- `test_delete_task()` - Ensures proper task deletion and error handling
- `test_get_nonexistent_task_raises_error()` - Tests error handling for invalid IDs

**FileHandler Tests (`test_file_handler.py`):**
- `test_save_data_creates_file()` - Verifies JSON file creation and content
- `test_load_nonexistent_file_returns_empty_dict()` - Tests graceful error handling
- `test_file_exists()` - Validates file existence checking
- `test_delete_file()` - Tests file cleanup functionality
- `test_list_files()` - Verifies directory listing capabilities

```bash
# Run all tests
pytest

# Run with coverage report (aim for >80% coverage)
python -m pytest --cov=. --cov-report=html

# Run specific test file with verbose output
python -m pytest tests/test_task_manager.py -v

# Run all quality checks
black . && isort . && flake8 . && mypy . && pytest
```

## Project Instructions

This section contains all the student deliverables for this project.

### Learning Objectives
- **AI Collaboration**: Learn to effectively work with AI assistants to generate, review, and refactor code while maintaining code quality
- **Software Engineering**: Apply design patterns, separation of concerns, and modular architecture
- **Test-Driven Development**: Write and maintain comprehensive unit tests with good coverage
- **Code Quality**: Use linting, formatting, and type checking tools for professional-grade code
- **Documentation**: Document AI interactions and development decisions throughout the process

### AI-Assisted Development Workflow

#### 1. Planning Phase
- Use AI to help break down requirements into smaller, manageable tasks
- Ask for architectural suggestions and design pattern recommendations
- Review the `/ai_guidance/prompting_best_practices.md` for effective prompting techniques
- Use the provided slash commands in `/.claude/commands/` for common tasks

#### 2. Implementation Phase
- Generate initial code with AI assistance using specific, contextual prompts
- Always review and understand AI-generated code before accepting it
- Test AI-generated code thoroughly with various inputs and edge cases
- Refactor for clarity, maintainability, and adherence to project standards

#### 3. Review Phase
- Use AI to help identify potential issues or improvements
- Follow the `/ai_guidance/code_review_checklist.md` for systematic code review
- Ask for code review suggestions and alternative implementations
- Validate that the code follows project conventions and security best practices

#### 4. Documentation Phase
- Document your AI interactions in `/docs/ai_edit_log.md` with specific examples
- Explain your decisions and modifications to AI suggestions
- Complete the final report using `/docs/report_template.md`
- Update this README with new features and learnings

### Assessment Criteria

Your project will be evaluated on:

1. **Functionality**: Does the application work as intended with proper error handling?
2. **Code Quality**: Is the code well-structured, readable, and maintainable?
3. **Testing**: Are there comprehensive unit tests with good coverage (>80%)?
4. **AI Collaboration**: Did you effectively use AI assistance while maintaining code quality?
5. **Documentation**: Are your AI interactions and decisions well-documented?

### Example AI Prompts

- "Help me implement a priority queue for tasks using the strategy pattern"
- "Review this code for potential security vulnerabilities"
- "Suggest improvements to make this code more maintainable"
- "Help me write comprehensive unit tests for this function"

### AI Guidance Resources

- `/ai_guidance/prompting_best_practices.md` - Learn effective AI prompting techniques
- `/ai_guidance/code_review_checklist.md` - Systematic approach to reviewing AI-generated code
- `/.claude/commands/generate-function` - Generate well-structured Python functions
- `/.claude/commands/review-code` - Get comprehensive code reviews
- `/.claude/commands/debug-help` - Debug issues with AI assistance
- `/.claude/commands/refactor-code` - Refactor code with design patterns
- `/docs/design_patterns.md` - Examples of implementing design patterns with AI assistance

### Project Structure

```
starter/
├── main.py                 # Main application entry point
├── utils/                  # Utility modules
│   ├── __init__.py
│   ├── task_manager.py     # Task management functionality
│   └── file_handler.py     # File I/O operations
├── tests/                  # Unit test suite
│   ├── __init__.py
│   ├── test_task_manager.py
│   └── test_file_handler.py
├── docs/                   # Documentation and templates
│   ├── ai_edit_log.md      # AI interaction tracking
│   ├── design_patterns.md  # Design pattern examples
│   └── report_template.md  # Final report template
├── ai_guidance/            # AI prompting best practices
│   ├── prompting_best_practices.md
│   └── code_review_checklist.md
├── .claude/                # Claude-specific configuration
│   ├── CLAUDE.md           # Claude configuration
│   ├── commands/           # Slash commands
│   └── mcp.json           # MCP configuration
├── requirements.txt        # Python dependencies
├── .editorconfig          # Code formatting rules
└── README.md              # This file
```

## Built With

* [Python](https://www.python.org/) - Core programming language
* [pytest](https://docs.pytest.org/) - Testing framework for comprehensive unit tests
* [pytest-cov](https://pytest-cov.readthedocs.io/) - Coverage reporting for tests
* [Black](https://black.readthedocs.io/) - Code formatter for consistent style
* [isort](https://pycqa.github.io/isort/) - Import organizer for clean code structure
* [flake8](https://flake8.pycqa.org/) - Linting tool for code quality
* [mypy](https://mypy.readthedocs.io/) - Static type checker for better code reliability
* [pre-commit](https://pre-commit.com/) - Git hook framework for automated quality checks
* [Claude](https://claude.ai/) - AI assistant for code generation and review

## License

[License](LICENSE.txt)

---

**Remember**: The goal is not just to build a working application, but to learn how to effectively collaborate with AI while maintaining high software engineering standards. Take time to understand the code, ask questions, and document your learning journey!

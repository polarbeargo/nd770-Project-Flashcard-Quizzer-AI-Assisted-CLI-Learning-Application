# Flashcard Quizzer - AI-Assisted CLI Learning Application

A command-line tool that **loads, validates and exports flashcard decks** stored
as JSON. It was built with an AI coding assistant as part of an AI-assisted
software-engineering project; the collaboration process is documented in
[`docs/ai_edit_log.md`](docs/ai_edit_log.md) and the design in
[`docs/architecture.md`](docs/architecture.md).

## ✨ Features

| Feature | Details |
|---------|---------|
| **Two JSON layouts** | Array format `[{"front": "...", "back": "..."}]` and object format `{"title": "...", "cards": [...]}` - detected automatically. |
| **Friendly errors, never tracebacks** | Malformed JSON (with line/column), missing or mistyped fields, empty decks, oversized input, unreachable URLs - each gets a one-line message plus a *hint*. |
| **Strict or lenient validation** | Stop at the first bad card (default) or `--skip-invalid` to drop bad cards with warnings. Exact duplicates are removed unless `--keep-duplicates`. |
| **Configuration management** | Defaults → `--config file.json` → `FLASHCARD_*` env vars → CLI flags. Every value validated up-front. |
| **Export** | JSON, CSV (formula-injection safe) and Markdown, written atomically. Custom exporters plug in via a factory. |
| **Remote decks** | `python main.py validate https://example.com/deck.json` - http(s) only, timeout and size-capped. |
| **Logging** | `--debug` / `--log-file`; the library itself is silent unless you opt in. |
| **Thread-safe & leak-free** | Immutable models, locked LRU cache, observer subscriptions with explicit teardown - all covered by concurrency and `tracemalloc` tests. |

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher (frozen `slots=True` dataclasses are used)
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
   python main.py validate data/samples/python_basics_array.json
   ```

4. **Run tests:**
   ```bash
   python -m pytest
   ```


## 📖 Usage

```bash
# Validate a deck (array or object format is detected automatically)
python main.py validate data/samples/python_basics_array.json
python main.py validate data/samples/design_patterns_object.json

# Print the cards
python main.py show data/samples/design_patterns_object.json --limit 3

# Tolerate bad cards, see what was skipped
python main.py validate data/samples/invalid_missing_fields.json --skip-invalid

# Export to CSV / Markdown / JSON (format inferred from extension, or --format)
python main.py export data/samples/python_basics_array.json deck.csv
python main.py export data/samples/python_basics_array.json deck.md

# Load from the web
python main.py validate https://example.com/deck.json

# Diagnostics
python main.py validate deck.json --debug
python main.py validate deck.json --log-file run.log

# List supported formats
python main.py formats
```

### What errors look like

```text
$ python main.py validate data/samples/invalid_malformed.json
Error: In 'data/samples/invalid_malformed.json': Not valid JSON: Expecting ',' delimiter (line 2, column 29).
  Hint: Look for missing commas, unmatched brackets/braces, trailing commas, or unquoted keys. ...

$ python main.py validate data/samples/invalid_missing_fields.json
Error: In 'data/samples/invalid_missing_fields.json': Card #2 is missing the required 'back' field.
  Hint: Every card needs non-empty string "front" and "back" fields. Optional: "hint" (string) and "tags" (list of strings).
```

Exit codes: `0` success · `1` user-facing problem · `2` unexpected bug (logged) · `130` interrupted.

### Deck file format

```jsonc
// Array format
[
  {"front": "What keyword defines a function?", "back": "def", "tags": ["syntax"]},
  {"front": "What is 3 // 2?", "back": "1", "hint": "Floor division."}
]

// Object format
{
  "title": "Python Basics",
  "cards": [ {"front": "...", "back": "..."} ]
}
```

`front` and `back` are required non-empty strings. `hint` (string) and `tags`
(list of strings) are optional. Unknown keys are ignored.

### Configuration

| Option | Default | Env var | Purpose |
|--------|---------|---------|---------|
| `max_file_bytes` | 10 MiB | `FLASHCARD_MAX_FILE_BYTES` | Reject larger inputs before reading |
| `max_cards` | 10000 | `FLASHCARD_MAX_CARDS` | Reject bigger decks |
| `max_field_length` | 2000 | `FLASHCARD_MAX_FIELD_LENGTH` | Per-field character limit |
| `max_tags` / `max_tag_length` | 20 / 50 | `FLASHCARD_MAX_TAGS` / `FLASHCARD_MAX_TAG_LENGTH` | Tag limits |
| `on_invalid_card` | `raise` | `FLASHCARD_ON_INVALID_CARD` | `raise` or `skip` |
| `dedupe` | `true` | `FLASHCARD_DEDUPE` | Remove exact duplicates |
| `allow_empty` | `false` | `FLASHCARD_ALLOW_EMPTY` | Accept zero-card decks |
| `encoding` | `utf-8` | `FLASHCARD_ENCODING` | File encoding |
| `cache_size` | 8 | `FLASHCARD_CACHE_SIZE` | Parsed-file LRU cache (0 disables) |
| `request_timeout` | 10.0 | `FLASHCARD_REQUEST_TIMEOUT` | HTTP timeout in seconds |

Put the same keys in a JSON file and pass `--config settings.json`.

### Using the library directly

```python
from flashcards import FlashcardLoader, LoaderConfig, FlashcardError, export_deck

loader = FlashcardLoader(LoaderConfig(on_invalid_card="skip"))
try:
    deck = loader.load("data/samples/python_basics_array.json")
except FlashcardError as exc:
    print(exc.user_message())
else:
    print(len(deck), "cards;", deck.skipped, "skipped")
    export_deck(deck, "out.csv")
```

## 🏗️ Architecture

Strategy + Chain of Responsibility (format parsers), Factory (exporters),
Observer (load events), Facade (`FlashcardLoader`) and immutable value objects
(`LoaderConfig`, `Flashcard`, `Deck`). Diagrams, the load pipeline, and the
performance / security / thread-safety decisions are in
[`docs/architecture.md`](docs/architecture.md).

## 🛠️ Development Tools

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

## 🧪 Testing

380 tests, **99 % line + branch coverage** (`fail_under = 90` is enforced in
`pyproject.toml`), and **mutation-tested** so the coverage number means something:
every non-cosmetic mutant of the loader, validator, exporters, remote fetcher
and CLI is killed by at least one test (see *Mutation testing* below).

| File | Covers |
|------|--------|
| `tests/test_models.py` | Immutability, slots, serialisation of `Flashcard`/`Deck` |
| `tests/test_exceptions.py` | Message/hint formatting, hierarchy |
| `tests/test_config.py` | Validation of every option, env/file/mapping loading |
| `tests/test_parsers.py` | Array/object detection, bad layouts, custom strategies |
| `tests/test_validators.py` | Required/optional fields, types, lengths, control chars, Unicode |
| `tests/test_loader.py` | Both formats, every error path, skip/dedupe, LRU cache |
| `tests/test_remote.py` | HTTP fetcher with an injected fake opener (no network) |
| `tests/test_exporters.py` | JSON/CSV/Markdown output, factory, atomic writes, temp cleanup |
| `tests/test_logging_config.py` | Handler idempotency |
| `tests/test_cli.py` | End-to-end CLI: every command, flag and failure mode |
| `tests/test_concurrency.py` | 16-thread loads, event bus races, cache bounds, `tracemalloc` leak check |
| `tests/test_task_manager.py`, `tests/test_file_handler.py` | Original starter utilities |

```bash
# Run all tests
python -m pytest

# Coverage report (terminal + HTML in htmlcov/)
python -m pytest --cov --cov-report=term-missing --cov-report=html

# One file, verbose
python -m pytest tests/test_loader.py -v

# All quality checks
black --check . && isort --check-only . && flake8 . && mypy && python -m pytest --cov
```

### Mutation testing (guarding against "test theater")

High coverage only proves lines were *executed*, not that a test would fail if
the code were wrong. [mutmut](https://mutmut.readthedocs.io/) rewrites the
source one small change at a time (`>` → `>=`, `+= 1` → `= 1`, dropping an
argument, ...) and re-runs the suite; a mutant that *survives* marks a
behaviour no test actually checks.

```bash
pip install mutmut
mutmut run            # configured in pyproject.toml [tool.mutmut]
mutmut results        # list survivors
mutmut show <id>      # diff of one mutant
```

Running this on the first version of the suite exposed four tautological
assertions and ~30 unverified behaviours (boundary conditions, config
propagation, error metadata, log levels) despite 99 % coverage. Tests were
added for each; see `docs/ai_edit_log.md` for the full account. The remaining
survivors are cosmetic (help-text wording, message capitalisation) or
provably equivalent.

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
.
├── main.py                   # CLI: validate / show / export / formats
├── flashcards/               # Library package
│   ├── __init__.py           # Public API
│   ├── models.py             # Flashcard, Deck (frozen, slotted)
│   ├── exceptions.py         # Friendly error hierarchy
│   ├── config.py             # LoaderConfig (file / env / overrides)
│   ├── parsers.py            # Format strategies + registry
│   ├── validators.py         # CardValidator
│   ├── loader.py             # FlashcardLoader facade + LRU cache
│   ├── events.py             # EventBus (observer)
│   ├── exporters.py          # Exporter factory, atomic export
│   ├── remote.py             # HTTP(S) fetch
│   └── logging_config.py     # Opt-in logging
├── utils/                    # Original starter utilities (TaskManager, FileHandler)
├── data/samples/             # Example decks, incl. deliberately broken ones
├── tests/                    # pytest suite (see Testing)
├── docs/
│   ├── architecture.md       # Diagrams + design decisions
│   ├── ai_edit_log.md        # AI interaction log
│   ├── design_patterns.md    # Pattern guide (course material)
│   ├── project_rubric.md     # Assessment rubric
│   └── report_template.md    # Final report template
├── ai_guidance/              # Prompting and review checklists
├── pyproject.toml            # pytest / coverage / black / isort / mypy config
├── .flake8
├── requirements.txt
└── README.md
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

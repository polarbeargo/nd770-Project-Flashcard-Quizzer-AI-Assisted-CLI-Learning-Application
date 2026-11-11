# AI-Assisted Development Project Report

**Student Name:** Not provided  
**Project Title:** Flashcard Quizzer - AI-Assisted CLI Learning Application  
**Date:** November 11, 2026

## Executive Summary

This project is a Python command-line flashcard application. It loads and validates JSON decks, supports sequential, random, or adaptive quizzes, reports feedback and statistics, and exports JSON, CSV, or Markdown. It also supports configuration, logging, and bounded HTTP(S) deck loading. A `flashcards` package contains the core modules; `main.py` wires them to the CLI.

I used GitHub Copilot as an implementation and review assistant. I supplied requirements, examined proposals, ran tests and static checks, and revised code when evidence or project constraints called for it. The latest full validation passed 428 tests with 99.44% coverage.

## Project Overview

### Problem Statement

Studying from small flashcard collections should not require a large platform or fixed data format. A lightweight CLI can make decks easy to create, validate, study, and reuse, while reporting malformed input without exposing tracebacks.

### Solution Approach

The application targets Python 3.10 and later. Its runtime uses the standard library; `requirements.txt` supplies development and documentation tools. The `flashcards` package contains immutable models, JSON parsing and validation, loading, exporters, event handling, remote fetching, logging, and quiz logic. `main.py` uses `argparse` and delegates commands to the package.

The loader supports a card array or an object containing a `cards` array. Validation checks required fields and configured limits. A `FlashcardError` hierarchy lets the CLI present concise errors. Quiz modes implement an abstract `QuizMode`; each session has its own strategy while the deck remains immutable.

### Final Features

- Load array and wrapped-object JSON decks, validate their structure, and report actionable errors.
- Study with sequential, shuffled random, or adaptive mode. Adaptive mode retries cards missed during the current session until correct.
- Compare answers after trimming whitespace and applying Unicode case folding; show immediate feedback and an end-of-session summary.
- Accept `-f/--file`, `-m/--mode`, and `--stats` for quizzes. Type `exit` or press Ctrl+C to finish gracefully.
- Export decks to JSON, CSV, and Markdown; load user-supplied HTTP(S) deck URLs with limits.
- Configure loading behavior and opt into diagnostic logging.

## AI Collaboration Experience

### AI Tools and Workflow

The project log records GitHub Copilot assistance. My workflow was to state behavior and constraints, inspect the code, request a focused change, and validate it with tests and quality tools. I reviewed generated code for correctness, compatibility, maintainability, and edge cases rather than assuming it was correct.

### Valuable Interactions

#### 1. Choosing patterns for the loader
**Context:** Avoid adding design patterns without purpose.  
**AI Prompt:** Design JSON loading with useful patterns.  
**AI Response:** A package with parser strategies, registry, loader facade, observer, and exporter factory.  
**My Changes:** Rejected a Singleton configuration manager in favor of injected immutable configuration. Required the object parser to provide precise missing-`cards` errors.  
**Outcome:** Modular loading without unnecessary global state.

#### 2. Adaptive quiz behavior
**Context:** Prioritize wrong answers while keeping sessions controllable.  
**AI Prompt:** Implement sequential, random, and adaptive modes with a strategy and factory.  
**AI Response:** Per-session strategies and an adaptive retry queue.  
**My Changes:** Defined adaptive as one initial pass followed by retries until correct; added `exit`/Ctrl+C and attempt-based statistics. Documented that history is session-only.  
**Outcome:** Ordering is separated from interaction and independently testable.

#### 3. Verifying tests rather than trusting coverage
**Context:** Coverage alone does not prove tests detect regressions.  
**AI Prompt:** Find weak assertions and untested behavior.  
**AI Response:** Identified vacuous assertions and boundaries; mutation testing challenged detection.  
**My Changes:** Added exact expectations for configuration, errors, duplicates, caching, and CLI output; manually evaluated suspicious survivors.  
**Outcome:** Tests check behavior, not just execution.

#### 4. Handling untrusted input safely
**Context:** Decks are user input, and exported CSV can be opened in spreadsheets.  
**AI Prompt:** Review relevant input/export risks for a local CLI.  
**AI Response:** Add size limits, URL restrictions, validation, CSV formula neutralization, and atomic writes.  
**My Changes:** Declined unnecessary private-network blocking and preserved legitimate newlines.  
**Outcome:** Protections match the threat model.

### Challenges with AI Collaboration

AI suggestions were sometimes broader than needed, especially around patterns and defensive controls. Initial test assumptions also conflicted with fixture sizes; failures exposed this, and I corrected the tests rather than weakening production behavior. AI is useful for drafting and enumerating possibilities, but evidence and a clear threat model determine what to keep.

## Software Engineering Practices

### Testing and Code Quality

Pytest covers parsing, validation, loading, CLI commands, exporters, concurrency-sensitive components, quiz strategies, a full JSON-load-to-quiz-session integration scenario, and file-handler path containment. The latest run passed **428 tests** at **99.44% coverage**, above the 90% threshold. Black, isort, flake8, and mypy also passed in the same validation cycle. Application functions are typed; a narrow mypy exception remains for `Any` returned at the legacy JSON-loading boundary.

### Design Patterns

- **Strategy:** `QuizMode` defines card scheduling behavior; sequential, random, and adaptive implementations can change without rewriting quiz interaction.
- **Factory:** `QuizModeFactory` creates the selected quiz strategy; `ExporterFactory` resolves an output format to an exporter.
- **Strategy and Chain of Responsibility:** JSON parsers recognize layouts; the registry selects one.
- **Observer:** A thread-safe event bus lets the loader publish warnings and load events without owning CLI output or logging.
- **Facade:** `FlashcardLoader` combines reading, parsing, validation, deduplication, and caching behind one API.

### Code Structure

`models.py` holds immutable objects; `loader.py`, `parsers.py`, and `validators.py` handle ingestion; `quiz.py` contains strategies and statistics; `exporters.py` writes output; and `main.py` connects services to `argparse`. Tests are in `tests/`; documentation is in `docs/` and the README.

## Technical Challenges and Solutions

### Bounded, thread-safe caching
**Problem:** Re-parsing unchanged decks is wasteful; unbounded caches retain memory and shared state can race.  
**Solution:** A locked, capacity-limited LRU cache uses path and file metadata for keys and can be disabled.  
**AI Involvement:** AI helped draft the design and tests.  
**Lessons Learned:** Caches need explicit identity, capacity, and concurrency behavior.

### Interactive input and adaptive termination
**Problem:** Adaptive retries need a clear stop path; random ordering complicates reproducibility.  
**Solution:** `exit` and Ctrl+C end a session cleanly; random mode accepts an injected RNG.  
**AI Involvement:** AI drafted the strategies and tests.  
**Lessons Learned:** Session-local state and injectable I/O improve testability.

## Code Quality Analysis

### Metrics

- **Test suite:** 428 passed on the November 11, 2026 full run.
- **Coverage:** 99.44% on that run (configured minimum: 90%).
- **Formatting, lint, and typing:** Black, isort, flake8, and mypy passed on November 11, 2026.
- **Application structure:** Multiple focused modules plus a CLI entry point; no single-file application.

### Self-Assessment

- **Code Readability: 4/5** — responsibilities and user-facing behavior are documented, though the overall project has substantial scope for a CLI.
- **Code Maintainability: 4/5** — immutable models, factories, and per-session strategies support extension; future modes can be added behind the strategy interface.
- **Test Quality: 4/5** — tests assert concrete results across success and failure paths, with mutation testing used to identify gaps.
- **Documentation: 4/5** — setup, usage, architecture, and AI collaboration are documented; future changes should keep command examples synchronized.

## Learning Outcomes and Reflection

I improved my understanding of Python CLI design, abstract strategy interfaces, immutable dataclasses, thread-safe bounded caches, input validation, and measurable test quality. I learned to prompt with constraints and observable outputs, then use test failures and type-checker diagnostics to refine generated code. AI was most helpful for scaffolding, enumerating edge cases, and explaining alternative designs. It was less reliable when requirements were underspecified or when it inferred behaviors that had not been requested.

The most successful practice was validating changes with focused tests, a full coverage run, and separate formatter, lint, and type checks. I am most satisfied that quiz modes are real strategies and ingestion, quiz logic, and CLI interaction remain separate. Future work could add persistent adaptive history after defining storage and reset behavior, plus accessibility controls, configurable retries, and application packaging. Persistent history is not an existing feature.

## Conclusion

AI-assisted development works best when the assistant proposes and the developer decides. Patterns helped when they isolated algorithms or decoupled components, not merely because a rubric named them. Tests, static checks, and review confirmed behavior and filtered unsuitable suggestions. I will continue using explicit requirements, focused changes, independent validation, and honest documentation.

## Appendices

### Appendix A: AI Interaction Log

See [`ai_edit_log.md`](ai_edit_log.md) for the detailed interaction record, prompts, revisions, testing decisions, and lessons learned.

### Appendix B: Code Statistics

The November 11, 2026 full suite run reported 428 passing tests and 99.44% coverage. Black, isort, flake8, and mypy also passed in that validation cycle. Refresh these values after later code or test changes.

### Appendix C: Additional Resources

- Project setup and examples: [`../README.md`](../README.md)
- Architecture and design decisions: [`architecture.md`](architecture.md)
- AI collaboration record: [`ai_edit_log.md`](ai_edit_log.md)
- Python standard library documentation for `argparse`, `json`, and `unittest` concepts used alongside pytest

---

**Report length:** Approximately 1,300 words, excluding headings and metadata.

# AI-Assisted Development Project Report

**Student Name:** Hsin-Wen Chang
**Project Title:** Flashcard Quizzer - AI-Assisted CLI Learning Application  
**Date:** November 12, 2026

## Executive Summary

This Python CLI loads and validates JSON flashcard decks, supports sequential, random, or adaptive quizzes, reports scores, and exports JSON, CSV, or Markdown. It also offers configuration, logging, and bounded HTTP(S) loading.

I used GitHub Copilot as an implementation and review assistant, directing changes with explicit requirements and validating them rather than accepting proposals uncritically. The November 12 validation passed 433 tests with 99.17% coverage.

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

The project log records 11 dated development interactions. I used the provided checklist to review correctness, input validation, security, performance, error handling, readability, and integration, then ran tests and static checks.

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
**My Changes:** Declined unnecessary private-network blocking and preserved legitimate newlines. A later review found and fixed file-path traversal in the original file utility.
**Outcome:** Protections match the threat model; the path fix has traversal, absolute-path, and symlink regression tests.

### Challenges with AI Collaboration

AI suggestions were sometimes broader than needed, especially around patterns and defensive controls. Initial test assumptions also conflicted with fixture sizes; failures exposed this, and I corrected the tests rather than weakening production behavior. AI is useful for drafting and enumerating possibilities, but evidence and a clear threat model determine what to keep.

## Software Engineering Practices

### Testing and Code Quality

Pytest covers parsing, validation, loading, CLI commands, exporters, concurrency-sensitive components, quiz strategies, integration behavior, and file-handler path containment. The latest run passed **433 tests** at **99.17% coverage**, above the 90% threshold. Black, isort, flake8, and mypy also passed. Regression tests now verify byte-based text limits and finite positive timeouts. A fresh mutation run killed 1,530 of 1,902 mutants; 370 survived and 2 were marked suspicious, so those results are not presented as a complete mutation pass.

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

- **Test suite:** 433 passed on the November 12, 2026 full run.
- **Coverage:** 99.17% on that run (configured minimum: 90%).
- **Formatting, lint, and typing:** Black, isort, flake8, and mypy passed on November 12, 2026.
- **Mutation testing:** 1,530 killed; 370 survived; 2 suspicious; 0 timeouts (1,902 total). Survivors are not all triaged.
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

The November 12, 2026 full suite run reported 433 passing tests and 99.17% coverage. Black, isort, flake8, and mypy also passed. The mutation run generated 1,902 mutants (1,530 killed, 370 survived, 2 suspicious, no timeouts); survivors remain to be triaged. Refresh these figures after later code or test changes.

### Appendix C: Additional Resources

- Project setup and examples: [`README.md`](../../README.md)
- Architecture and design decisions: [`architecture.md`](architecture.md)
- AI collaboration record: [`ai_edit_log.md`](ai_edit_log.md)
- Python standard library documentation for `argparse`, `json`, and `unittest` concepts used alongside pytest

---

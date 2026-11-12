# AI Edit Log

**Instructions:** Use this document to track all your interactions with AI assistants during the project. This log will help you reflect on your AI collaboration process and demonstrate your learning journey.

## How to Use This Log

For each AI interaction, create a new entry with the following structure:

### Entry Template
```
## [Date] - [Brief Description]

**Context:** What were you trying to accomplish?
**AI Tool Used:** Claude/ChatGPT/Copilot/etc.
**Prompt/Request:** What exactly did you ask the AI?
**AI Response:** Summary of what the AI generated (don't copy entire code blocks)
**Changes Made:** What modifications did you make to the AI's suggestions?
**Reasoning:** Why did you make those changes?
**Outcome:** What was the final result?
**Lessons Learned:** What did you learn from this interaction?
```

---

## Example Entry

### 2024-01-15 - Initial Task Manager Implementation

**Context:** I needed to create a basic task management system to demonstrate CRUD operations and serve as the foundation for the project.

**AI Tool Used:** Claude

**Prompt/Request:** "Help me create a Python class for managing tasks with basic CRUD operations. The class should handle task creation, retrieval, completion, and deletion. Include proper error handling and type hints."

**AI Response:** Claude generated a TaskManager class with methods for add_task, get_task, get_all_tasks, complete_task, delete_task, and to_dict. The code included type hints, proper error handling with ValueError for missing tasks, and used datetime for timestamps.

**Changes Made:** 
- Added priority field to tasks with a default value of "medium"
- Modified the task structure to include created_at timestamp
- Added validation for priority values
- Renamed some variable names for clarity

**Reasoning:** 
- Priority field will be useful for implementing sorting features later
- Timestamps help with task organization and analytics
- Input validation prevents invalid data from being stored
- Better variable names improve code readability

**Outcome:** Successfully created a robust TaskManager class that serves as the core of the application with room for future enhancements.

**Lessons Learned:** 
- AI provides good starting implementations but always needs customization
- It's important to think about future requirements when reviewing AI code
- Type hints and error handling are crucial for maintainable code

---

## Your Log Entries

### 2026-10-31 - Architecture and design-pattern selection for the deck loader

**Context:** The project needed a system to load and validate flashcard JSON in two layouts (bare array and `{"cards": [...]}` wrapper) with friendly error messages. Before writing code I wanted an architecture that would satisfy the rubric's "multiple design patterns that serve real purposes" without becoming pattern soup.

**AI Tool Used:** GitHub Copilot (agent mode, Claude)

**Prompt/Request:** "Implement a system to load and validate flashcard data supporting array and object JSON formats, with friendly errors (no tracebacks), in an efficient, thread-safe, zero-memory-leak manner. Use multiple design patterns that serve real purposes, >90 % test coverage, configuration management, logging, data export, security best practices, external API integration and visual documentation."

**AI Response:** The assistant inspected the starter (`TaskManager`, `FileHandler`, the design-patterns guide) and proposed a `flashcards/` package: Strategy parsers (`ArrayFormatParser`, `ObjectFormatParser`) behind a Chain-of-Responsibility `ParserRegistry`, a `CardValidator`, a `FlashcardLoader` facade with an LRU cache, an Observer `EventBus`, a Factory for exporters, an immutable `LoaderConfig`, and a hardened `remote.fetch_text`.

**Changes Made:**
- Rejected the guide's **Singleton `ConfigManager`** suggestion. `LoaderConfig` is instead a frozen dataclass injected into the loader.
- Asked that `ObjectFormatParser.can_parse` claim *every* dict (not only dicts containing `cards`) so the error for `{"deck": [...]}` can say "missing the required 'cards' key (found keys: 'deck')" instead of a generic "unsupported format".
- Kept `TaskManager`/`FileHandler` untouched so the original tests keep passing.

**Reasoning:** A singleton would make tests order-dependent and hide the loader's dependency; a frozen value object gives the same "one shared config" benefit and is trivially thread-safe. Letting the object parser own all dicts costs nothing and produces far better diagnostics.

**Outcome:** Five patterns (Strategy, Chain of Responsibility, Factory, Observer, Facade) each with a concrete job, documented with Mermaid diagrams in `docs/architecture.md`.

**Lessons Learned:** The AI readily reaches for whatever pattern a guide mentions; I had to push back on Singleton explicitly. Asking "what problem does this pattern solve *here*?" for every suggestion kept the design honest.

---

### 2026-10-31 - Loader implementation: caching, limits and Python version floor

**Context:** Implementing `FlashcardLoader.load_file` with performance and memory-safety goals.

**AI Tool Used:** GitHub Copilot (agent mode, Claude)

**Prompt/Request:** "Make `load_file` fast and safe: reject oversized files cheaply, avoid re-parsing unchanged files, never grow memory without bound, keep everything thread-safe."

**AI Response:** The first idea floated was `functools.lru_cache` on a `load_file(path)` helper. The assistant then rejected its own idea because `lru_cache` can't be keyed on file modification time (stale data) and keeps strong references to every cached deck. It replaced it with a small `LRUCache` (an `OrderedDict` behind a `threading.Lock`, hard capacity) keyed by `(resolved path, size, mtime_ns)`, plus `stat()`-before-`read()` and `read(max_bytes + 1)` guards.

**Changes Made:**
- Accepted the explicit LRU design.
- The models use `@dataclass(frozen=True, slots=True)`; `slots=True` requires Python 3.10, while the template README said 3.8+. I chose to raise the documented floor to 3.10 rather than drop slots.
- Added a `cache_size=0` option to disable caching entirely (useful for tests and for one-shot CLI runs).

**Reasoning:** `slots` gives roughly 40 % less memory per card and faster attribute access; the starter already used `list[str]` syntax that doesn't work on 3.8 anyway, so the 3.8 claim was already inaccurate.

**Outcome:** `tests/test_loader.py::TestCaching` proves cache hits, invalidation on modification, bounded size and the zero-size opt-out. `tests/test_concurrency.py` hammers the cache from 16 threads and checks it never exceeds capacity.

**Lessons Learned:** The AI's *first* suggestion is often the idiomatic-looking one (`lru_cache`), not the correct one. Asking it to state the failure modes of its own suggestion surfaced the stale-data and reference-retention problems before any code was written.

---

### 2026-10-31 - Friendly error handling and a routing bug caught by smoke testing

**Context:** The requirement says malformed or incomplete JSON must produce a friendly message, never a traceback.

**AI Tool Used:** GitHub Copilot (agent mode, Claude)

**Prompt/Request:** "Design an exception hierarchy where every error has a message and a hint, make the CLI catch the base class and print `user_message()`, and exercise every error path from the shell."

**AI Response:** Produced `FlashcardError` (with `message`, `hint`, `source`) and ten subclasses with sensible default hints; `main.run` catches `FlashcardError` → exit 1, `KeyboardInterrupt` → 130, any other `Exception` → exit 2 with a "please report this bug" message and the traceback sent to the logger only. It then ran the CLI against every sample file.

**Changes Made:**
- The smoke test revealed that `python main.py validate ftp://example.com/x.json` printed *"Could not find the file 'ftp:/example.com/x.json'"* - the loader only recognised `http://`/`https://` prefixes and treated everything else as a path. I had it route **any** `scheme://` input to the URL loader so the user sees *"Unsupported URL scheme 'ftp'; only http and https are allowed"*.
- Added the `In 'file.json': ...` source prefix to messages so errors from multiple decks are distinguishable.

**Reasoning:** The original behaviour was technically "friendly" but misleading; a user would waste time checking paths. Routing by a `scheme://` regex also makes `file://` refusals explicit, which is a security property worth stating clearly.

**Outcome:** Every sample (valid, malformed, missing fields, directory, missing file, bad scheme, unreachable host, bad env var) yields a one-line error plus hint; `tests/test_cli.py` asserts `"Traceback" not in err` for the unexpected-exception path.

**Lessons Learned:** The code *looked* complete and the AI believed it was. Running the real binary against real bad inputs found the bug in under a minute. Unit tests are not a substitute for a quick manual smoke test of the user-facing surface.

---

### 2026-10-31 - Test suite: two AI-written tests were wrong, not the code

**Context:** Generating a comprehensive pytest suite (>90 % coverage, edge cases, concurrency, leak checks).

**AI Tool Used:** GitHub Copilot (agent mode, Claude)

**Prompt/Request:** "Write tests for every module including thread-safety tests with a 16-thread pool, a `weakref`-based check that unsubscribed observers are garbage-collected, and a `tracemalloc` check that repeated loads don't grow memory."

**AI Response:** Generated ~3 000 lines of tests across 11 files. First run: 316 passed, 2 failed.

**Changes Made:**
- `test_loader_and_decks_are_collectable` tried `weakref.ref(deck)`; `Deck` is a slotted dataclass and therefore has no `__weakref__` slot. The test was changed to check the loader's weakref plus `gc.get_referrers` for the deck instead of adding a `__weakref__` slot to the production class.
- `test_card_uses_slots` expected `AttributeError` when assigning an unknown attribute on a frozen+slots dataclass; CPython actually raises `TypeError` from the generated `__setattr__` in that case. The test now accepts either and additionally asserts the attribute was not attached.

**Reasoning:** Both failures were incorrect assumptions baked into the tests, not defects in the code. Weakening the production model (adding `__weakref__`) just to satisfy a test would have cost memory per card for no user benefit.

**Outcome:** 318 tests pass with 99.4 % line+branch coverage; `fail_under = 90` is enforced in `pyproject.toml`.

**Lessons Learned:** AI-generated tests are a hypothesis about how Python behaves, and the hypothesis is sometimes wrong in subtle runtime details (slots, weakrefs, frozen dataclass internals). Always run them, and when they fail, decide deliberately whether the test or the code is wrong - never just make red go green.

---

### 2026-10-31 - Security review of input handling and export

**Context:** Applying the "security best practices including input validation" rubric item to a tool that reads untrusted JSON and writes CSV that may be opened in Excel.

**AI Tool Used:** GitHub Copilot (agent mode, Claude)

**Prompt/Request:** "Review the loader, validator, remote fetcher and exporters for security issues relevant to a CLI that consumes untrusted files and URLs. Propose mitigations that don't hurt usability."

**AI Response:** Identified and implemented: strict field typing (no coercion), length caps on fields/tags/card count, byte caps on files, streams and HTTP bodies (`Content-Length` *and* actual read), control-character rejection (terminal escape injection), NFC normalisation, an http/https scheme allow-list, CSV formula-injection neutralisation (`= + - @ \t \r` prefixed with `'`), and atomic export via temp file + `os.replace` with guaranteed temp-file cleanup.

**Changes Made:**
- Kept tab, newline and carriage return as *allowed* control characters - the AI's first regex rejected `\n`, which would have broken legitimate multi-line answers.
- Did **not** add SSRF protections (blocking private IP ranges) that the AI offered: this is a local CLI where the user supplies their own URL, so the threat model doesn't apply and the code would be dead weight.

**Reasoning:** Security controls should match the threat model. Over-blocking (newlines) harms real users; under-blocking (formula injection) can harm anyone who opens an exported CSV.

**Outcome:** Each mitigation has a dedicated test (`test_control_characters_rejected`, `test_formula_injection_neutralised`, `test_declared_content_length_over_limit`, `test_temp_file_cleaned_up_when_replace_fails`, ...).

**Lessons Learned:** The AI is very good at enumerating known vulnerability classes, and slightly too eager to apply all of them. The valuable human step was deciding which ones fit *this* application.

---

### 2026-10-31 - Code-quality pass: formatters, flake8 and mypy on the whole tree

**Context:** The rubric requires `black`, `isort`, `flake8` and `mypy` to pass.

**AI Tool Used:** GitHub Copilot (agent mode, Claude)

**Prompt/Request:** "Run every quality tool on the repository and fix what they report without changing behaviour."

**AI Response:** `black` wanted to reformat 21 files (including the untouched starter `utils/`), `flake8` reported 30 issues (mostly E501 inside long f-strings that black cannot split, plus unused imports in the starter), `mypy` passed on the new package but failed on `utils/` under the strict flags.

**Changes Made:**
- Applied black/isort to the whole tree (whitespace-only for starter files).
- Split long f-strings by hand where black couldn't.
- Removed two genuinely unused imports from starter files (`os`, `datetime`).
- Instead of rewriting `utils/` for strict typing, added a `[[tool.mypy.overrides]]` block that relaxes `disallow_untyped_defs`/`warn_return_any` for `utils.*` only.

**Reasoning:** The strict settings are right for new code; retro-fitting them onto template code I didn't write would be unrelated churn and risk.

**Outcome:** `black --check . && isort --check-only . && flake8 . && mypy && pytest --cov` all pass.

**Lessons Learned:** Tooling configuration *is* code review policy. Scoping strictness per package let me hold new code to a high bar without rewriting what wasn't mine.

---

### 2026-10-31 - "Ensure no test theater": mutation testing the 99 %-covered suite

**Context:** The suite reported 99.4 % line+branch coverage. I asked whether that number was real or whether tests were merely executing code without checking it.

**AI Tool Used:** GitHub Copilot (agent mode, Claude)

**Prompt/Request:** "Ensure no test theater."

**AI Response:** The assistant first grepped the tests for weak idioms and found four: a tautology (`len(set_of_N) <= N`), a vacuous `len(results) == 120` on a `map` result, an over-broad `pytest.raises(Exception)`, and `err.column is not None` instead of the actual column. It then installed `mutmut`, configured it in `pyproject.toml`, and ran 1 535 mutants: 1 139 killed, 394 survived (74 %).

**Changes Made:**
- Fixed the four weak assertions (exact content equality across threads, per-file source checks, `FrozenInstanceError`, `(line, column) == (1, 16)`).
- Triaged all 394 survivors by function. Most were cosmetic (argparse help text, message capitalisation, equivalent defaults). About 30 were real gaps and got dedicated tests:
  - **Config propagation** - the loader could silently construct `CardValidator(None)` and ignore `max_field_length`; `encoding` was never verified to reach `open()`.
  - **Boundaries** - `>` vs `>=` on `max_cards`, `max_file_bytes` (file, string, stream, HTTP body *and* `Content-Length`), `max_field_length`, `max_tag_length`; `read(max - 1)` would truncate a file exactly at the limit.
  - **Counting** - `duplicates = 1` vs `+= 1` was undetectable with only one duplicate in the fixture.
  - **Error/event metadata** - `source` and `index` on `InvalidCardError`, `FileTooLargeError`, `MalformedJSONError` and on `CACHE_HIT` / `DUPLICATE_REMOVED` / `CARD_SKIPPED` events were mostly unasserted.
  - **Cache identity** - a key of `(size, mtime)` without the path would serve the wrong deck; added a test with two identical files given identical mtimes.
  - **CLI** - `--log-file` without `--debug` must be INFO not DEBUG; the skipped/duplicates summary must print when only one is non-zero; `-f` short flag; separator width; no "... more" line without `--limit`.
  - **Exporters** - exact JSON indentation, Unix CSV line endings, Markdown numbering from 1, temp file created in the *target* directory (atomic rename requires the same filesystem).
- Re-ran mutmut: 1 239 killed (81 %). Two survivors it reported (`opener and urlopen`, `add_subparsers` without `dest`) looked like they *should* die, so the assistant applied them by hand and ran the full suite - both were killed. Conclusion: mutmut 3's per-mutant test selection under-reports kills.
- Built a 32-mutant manual harness that patches the real source and runs the whole suite: **31/32 killed**. The one survivor - `logger.log(level, msg)` vs `logger.log(level, "%s", msg)` - is provably equivalent because `logging` only applies `%`-formatting when args are present.

**Reasoning:** Coverage measures execution; mutation testing measures *detection*. Only the latter distinguishes a test that would catch a regression from one that merely runs the code. Verifying suspicious survivors by hand mattered because trusting the tool's number blindly would have been its own form of theatre.

**Outcome:** 380 tests, still 99 % coverage, with every non-cosmetic mutant in the core logic killed. Mutation testing is documented in the README and configured in `pyproject.toml` so it can be re-run.

**Lessons Learned:**
- The AI wrote tests that *looked* rigorous (thread pools, `weakref`, `tracemalloc`) yet still contained tautologies. Sophistication of a test is not evidence of its strength.
- The AI is excellent at *triaging* mutation survivors quickly (grouping by function, separating cosmetic from meaningful) - a task that is tedious for a human - but every "equivalent mutant" claim still needed a one-line justification I could check.
- Fixtures with a single instance of a condition (one duplicate, one skipped card) cannot distinguish `= 1` from `+= 1`. Use two.
- The manual harness itself had a bug: it restored the original source within the same second as writing a *same-length* mutant (`-f` → `-F`), so Python's size+mtime check kept the mutant's stale `.pyc`. A later test run then failed against code that no longer existed. Re-verified with `python -B` / `PYTHONDONTWRITEBYTECODE=1` and cleared caches: 6/6 same-length mutants killed. Verification tooling needs verifying too.

---

### 2026-11-09 - Quiz strategies and interactive session

**Context:** Add a quiz engine to the existing validated-deck CLI without
duplicating JSON parsing, and meet the requested sequential, random and
adaptive ordering behaviors.

**AI Tool Used:** GitHub Copilot (agent mode)

**Prompt/Request:** "Implement Phase 2's quiz engine with a `QuizMode` abstract
base class, `SequentialMode`, `RandomMode`, `AdaptiveMode`, and a factory;
reuse the JSON loader, compare answers case-insensitively, show immediate
feedback and finish with total questions, accuracy and missed terms. Keep it
efficient, reliable and thread-safe, and ensure the tests verify real behavior."

**AI Response:** Added a quiz strategy module and connected it to the existing
`quiz` CLI command. Adaptive mode asks each card once, then retries incorrect
cards until correct. A `q` command and end-of-input allow a user to stop a
review early; statistics include all submitted attempts, including retries.

**Changes Made:**
- Kept question-order state inside each strategy instance and made the factory
  create a new instance per quiz. Random mode owns its RNG and shuffles a copy
  rather than mutating the shared immutable deck.
- Added an injectable answer reader and output stream so tests can verify
  prompts, feedback, adaptive reordering, early exit and the exact summary.
- The first test run exposed that two test answer iterators assumed a
  two-card deck while their fixture had three cards. Updated the test data and
  expected totals to match the actual fixture; no production behavior was
  weakened to make the tests pass.
- Documented that an adaptive retry is not counted until an answer is
  submitted, and that missed terms remain listed even if later corrected.

**Reasoning:** A strategy interface keeps the quiz loop independent of ordering
rules. A per-quiz strategy avoids shared mutable state between normal concurrent
sessions, and a private seeded RNG makes random behavior reproducible in tests.
Using `FlashcardLoader` preserves the app's established validation and friendly
error path instead of creating a second loader.

**Outcome:** Added tests for each mode, factory selection, normalization,
adaptive retries, score calculation, empty/early-ended sessions and CLI
integration. The focused tests passed; the full suite passed with 405 tests and
99.42% coverage. Black, isort, flake8 and mypy were also run.

**Lessons Learned:** A high coverage percentage alone would not have caught the
test fixture mismatch; checking the exact attempt order and summary values
made the tests meaningful. Mutable strategies should be session-scoped, while
the immutable deck can safely be reused.

---

### 2026-11-11 - Full-session integration coverage and documentation links

**Context:** Review the requested loader, quiz-mode and full-session scenarios
for meaningful behavioral coverage. The existing suite covered loader and
strategy behavior, but lacked one integration test checking the statistics
from a complete three-question session.

**AI Tool Used:** GitHub Copilot (agent mode)

**Prompt/Request:** "Check whether these scenarios are implemented in a
not-test-theater manner, implement the missing part, and check whether the
README and architecture documentation need updates."

**AI Response:** Identified the missing exact three-question stats scenario,
added an integration test that loads a JSON deck through `FlashcardLoader` and
runs a real `QuizSession`, then reviewed README links and architecture scope.

**Changes Made:**
- Added `tests/test_integration.py::test_full_session`, which submits one
  incorrect and two correct answers, then checks the result object and printed
  three-question summary, including 66.7% accuracy and the missed term.
- Updated the root README's test count and test-file overview, corrected its
  links to the docs under `starter/docs/`, and removed the broken license link
  because the repository has no license file.
- Renamed the architecture document title to "Architecture: Flashcard Quizzer"
  to reflect its coverage of quiz strategies and exports as well as loading.

**Reasoning:** A real loader-to-session test verifies the integration path and
its externally observable statistics, rather than only testing helpers in
isolation. Documentation links and test descriptions should match the files
that actually exist.

**Outcome:** The full starter test suite passed: 416 tests. The three-question
integration test checks both exact result values and the rendered summary.

**Lessons Learned:** A suite can have detailed unit tests and still miss an
important end-to-end output shape. README file counts and links also need to be
checked against the current repository, not copied from an earlier snapshot.

---

### 2026-11-11 - Constraining file-handler paths

**Context:** A security review found that `FileHandler` joined caller-provided
filenames to its data directory without ensuring the resolved path stayed
inside that directory. Parent traversal, absolute paths, and symlinked parent
directories could therefore target files elsewhere.

**AI Tool Used:** GitHub Copilot (agent mode)

**Prompt/Request:** "Review code quality, security, performance and error
handling; then fix all reported security issues."

**AI Response:** Confirmed the file-handler path escape and recommended
resolving candidate paths against the resolved data directory before performing
file operations.

**Changes Made:**
- Added one path-resolution guard shared by `save_data`, `load_data`,
  `file_exists`, and `delete_file`. It rejects candidates whose resolved path
  is outside the configured data directory, including symlinked parents.
- Added regression coverage for traversal paths, absolute paths, and symlinked
  parent-directory escapes across all four operations.

**Reasoning:** Centralizing containment checks prevents each file operation
from implementing its own path policy and ensures the check accounts for
existing symlinks.

**Outcome:** All 428 tests passed with 99.44% coverage. Black, isort, flake8,
and mypy passed.

**Lessons Learned:** A data-directory abstraction must enforce its boundary on
every operation that accepts a filename; testing ordinary names alone does not
verify that boundary.

---

### 2026-11-12 - Checklist review and input-boundary hardening

**Context:** A project-quality review against the provided checklist identified
two robustness gaps in addition to the previously fixed file-path escape:
string/stream size limits counted characters rather than bytes, and
`request_timeout` accepted `NaN` and infinity.

**AI Tool Used:** GitHub Copilot (agent mode)

**Prompt/Request:** "Review code quality, security, performance and error
handling; make the code more maintainable and robust, and address the review
gaps before submission."

**AI Response:** Verified the three input-boundary issues, reviewed the
application against the checklist categories, and recommended regression tests
for their observable failure cases.

**Changes Made:**
- Counted UTF-8 bytes for in-memory strings and text streams. File loading now
  reads a capped number of raw bytes before decoding, preserving exact byte
  limits for configured file encodings and handling files that grow after
  `stat()`.
- Required request timeouts to be finite and positive; added `NaN` and positive
  and negative infinity to the invalid-value tests.
- Bounded the quiz-mode test collector so an incorrect mode that repeats
  forever fails promptly instead of timing out.
- Added a project review record to the provided checklist and this log. It
  cites the file-path escape, byte-limit and timeout findings, the tests that
  caught them, and formatting/lint/type-check results.
- Refreshed the interaction count below to reflect the dated project entries.

**Reasoning:** Resource limits need to measure the resource named by the
configuration (bytes), and a network timeout must be a finite positive value.
Bounded test loops make mutation feedback faster and less ambiguous.

**Outcome:** The full suite passed 433 tests at 99.17% coverage. Black, isort,
flake8, and mypy passed. A fresh mutation run generated 1,902 mutants: 1,530
killed, 370 survived, 2 suspicious, and no timeouts after the quiz test loop
was bounded. The two suspicious cases involve injected opener/fetcher fallback
behavior and remain explicitly unclassified by mutmut; the other survivors
have not all been manually triaged. The README and final report state these
limitations rather than treating survivors as equivalent.

**Lessons Learned:** A high coverage percentage does not verify units at input
boundaries or every non-finite numeric value. Runtime probes and targeted
regression tests exposed these cases.

---

## Tips for Effective AI Collaboration

### 1. Be Specific in Your Requests
- ❌ "Write a function"
- ✅ "Write a function that validates email addresses using regex, returns a boolean, and includes proper error handling"

### 2. Provide Context
- Include relevant code snippets
- Explain the larger goal
- Mention any constraints or requirements

### 3. Review and Understand
- Never copy AI code without understanding it
- Ask for explanations of complex logic
- Test the code before accepting it

### 4. Iterate and Refine
- Use follow-up questions to improve the code
- Ask for alternative implementations
- Request code reviews and suggestions

### 5. Document Your Process
- Keep detailed notes in this log
- Explain your decision-making process
- Track what works and what doesn't

## Common AI Collaboration Patterns

### Code Generation
- Initial implementation of classes/functions
- Boilerplate code creation
- Test case generation

### Code Review
- Ask AI to review your code for issues
- Request suggestions for improvements
- Get feedback on code structure

### Problem Solving
- Debugging help
- Algorithm suggestions
- Architecture advice

### Learning and Explanation
- Ask for explanations of complex concepts
- Request examples of design patterns
- Get guidance on best practices

## Reflection Questions

As you work through the project, consider these questions:

1. **What types of tasks did AI help with most effectively?**
2. **Where did you need to make the most modifications to AI suggestions?**
3. **What patterns did you notice in AI strengths and weaknesses?**
4. **How did your prompting technique improve over time?**
5. **What would you do differently in future AI collaborations?**

## Summary Statistics

As of 2026-11-12:

- **Documented project interactions:** 11 dated entries, excluding the 2024 example template; some entries cover multiple follow-up prompts
- **Lines of AI-generated code used:** ~1 900 lines in `flashcards/` + `main.py`, ~3 000 lines of tests
- **Lines of AI-generated code modified:** ~60 lines rejected or rewritten (URL routing, control-char regex, two tests, Singleton proposal, SSRF code declined)
- **Most helpful AI interaction:** Triaging 394 mutation-testing survivors into cosmetic vs. real gaps and writing targeted tests for the ~30 real ones
- **Most challenging AI interaction:** Steering pattern choice - the AI happily proposed every pattern in the course guide and needed explicit "what problem does this solve here?" pushback
- **Biggest lesson learned:** Run everything. The AI's confidence is uncorrelated with correctness in runtime details (slots/weakref semantics, scheme routing); a one-minute smoke test or a failing test tells the truth

---

**Note:** This log is a required component of your final project report. Be thorough and honest in your documentation to demonstrate your learning process and AI collaboration skills.
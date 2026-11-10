"""Tests for quiz strategies, scoring and interactive session behavior."""

from __future__ import annotations

import io
import random

import pytest

from flashcards import (
    AdaptiveMode,
    Deck,
    Flashcard,
    QuizMode,
    QuizModeFactory,
    QuizSession,
    RandomMode,
    SequentialMode,
)


@pytest.fixture
def cards() -> tuple[Flashcard, ...]:
    return (
        Flashcard("Q1", "A1"),
        Flashcard("Q2", "A2"),
        Flashcard("Q3", "A3"),
    )


@pytest.fixture
def deck(cards: tuple[Flashcard, ...]) -> Deck:
    return Deck(cards=cards, title="Test deck")


def collect(mode: QuizMode, cards: tuple[Flashcard, ...]) -> list[Flashcard]:
    mode.start(cards)
    result = []
    while (card := mode.next_card()) is not None:
        result.append(card)
    return result


def test_sequential_mode_returns_cards_once_in_order(cards):
    mode = SequentialMode()
    assert collect(mode, cards) == list(cards)
    assert mode.next_card() is None


def test_sequential_mode_can_be_restarted(cards):
    mode = SequentialMode()
    assert collect(mode, cards) == list(cards)
    assert collect(mode, cards) == list(cards)


def test_random_mode_shuffles_a_copy_and_returns_each_card(cards):
    mode = RandomMode(random.Random(4))
    original = list(cards)
    mode.start(original)
    shuffled = []
    while (card := mode.next_card()) is not None:
        shuffled.append(card)

    assert set(shuffled) == set(cards)
    assert len(shuffled) == len(cards)
    assert original == list(cards)
    assert shuffled != list(cards)


def test_random_mode_is_reproducible_with_seed(cards):
    first = collect(RandomMode(random.Random(9)), cards)
    second = collect(RandomMode(random.Random(9)), cards)
    assert first == second


def test_adaptive_mode_retries_misses_after_initial_pass(cards):
    mode = AdaptiveMode()
    mode.start(cards)

    first = mode.next_card()
    assert first == cards[0]
    mode.record_answer(first, correct=False)

    assert mode.next_card() == cards[1]
    mode.record_answer(cards[1], correct=True)
    assert mode.next_card() == cards[2]
    mode.record_answer(cards[2], correct=True)
    assert mode.next_card() == cards[0]
    mode.record_answer(cards[0], correct=True)
    assert mode.next_card() is None


def test_adaptive_mode_requeues_a_miss_until_correct(cards):
    mode = AdaptiveMode()
    mode.start(cards[:1])

    card = mode.next_card()
    mode.record_answer(card, correct=False)
    assert mode.next_card() == card
    mode.record_answer(card, correct=False)
    assert mode.next_card() == card
    mode.record_answer(card, correct=True)
    assert mode.next_card() is None


def test_adaptive_mode_resets_review_queue_between_quizzes(cards):
    mode = AdaptiveMode()
    mode.start(cards[:1])
    card = mode.next_card()
    mode.record_answer(card, correct=False)

    mode.start(cards[1:2])
    assert mode.next_card() == cards[1]
    assert mode.next_card() is None


@pytest.mark.parametrize(
    ("name", "expected_type"),
    [
        ("sequential", SequentialMode),
        ("random", RandomMode),
        ("adaptive", AdaptiveMode),
        ("  RANDOM  ", RandomMode),
    ],
)
def test_factory_creates_selected_fresh_mode(name, expected_type):
    assert isinstance(QuizModeFactory.create(name), expected_type)
    assert QuizModeFactory.create(name) is not QuizModeFactory.create(name)


def test_factory_random_mode_uses_injected_rng():
    rng = random.Random(12)
    mode = QuizModeFactory.create("random", rng=rng)
    assert isinstance(mode, RandomMode)


def test_factory_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Unknown quiz mode"):
        QuizModeFactory.create("spaced")


def test_factory_lists_supported_modes():
    assert QuizModeFactory.available() == ("sequential", "random", "adaptive")


def test_session_checks_answers_case_insensitively_and_trims_whitespace(deck):
    answers = iter(("  a1 ", "A2", "q"))
    output = io.StringIO()

    result = QuizSession(deck, SequentialMode()).run(
        input_fn=lambda: next(answers), out=output
    )

    assert result.total_questions == 2
    assert result.correct_answers == 2
    assert result.accuracy_percentage == 100
    assert result.missed_terms == ()
    assert "Correct!" in output.getvalue()
    assert "| Total questions answered | 2 |" in output.getvalue()
    assert "| Accuracy | 100.0% |" in output.getvalue()
    assert "| Missed terms | None |" in output.getvalue()


def test_session_counts_attempts_and_reports_misses_with_adaptive_retries(deck):
    answers = iter(("wrong", "a2", "a3", "a1"))
    output = io.StringIO()

    result = QuizSession(deck, AdaptiveMode()).run(
        input_fn=lambda: next(answers), out=output
    )

    assert result.total_questions == 4
    assert result.correct_answers == 3
    assert result.accuracy_percentage == 75
    assert result.missed_terms == ("Q1",)
    text = output.getvalue()
    assert text.count("Question ") == 4
    assert "Incorrect. Correct answer: A1" in text
    assert "| Total questions answered | 4 |" in text
    assert "| Accuracy | 75.0% |" in text
    assert "| Missed terms | Q1 |" in text


def test_session_can_stop_before_attempting_next_question(deck):
    answers = iter(("q",))
    output = io.StringIO()

    result = QuizSession(deck, SequentialMode()).run(
        input_fn=lambda: next(answers), out=output
    )

    assert result.total_questions == 0
    assert result.correct_answers == 0
    assert result.accuracy_percentage == 0
    assert result.missed_terms == ()
    assert "| Total questions answered | 0 |" in output.getvalue()
    assert "| Accuracy | 0.0% |" in output.getvalue()


def test_session_accepts_exit_to_finish(deck):
    answers = iter(("a1", "exit"))
    output = io.StringIO()

    result = QuizSession(deck, SequentialMode()).run(
        input_fn=lambda: next(answers), out=output
    )

    assert result.total_questions == 1
    assert "| Total questions answered | 1 |" in output.getvalue()


def test_session_treats_end_of_input_as_early_finish(deck):
    output = io.StringIO()

    def end_input():
        raise EOFError

    result = QuizSession(deck, SequentialMode()).run(input_fn=end_input, out=output)
    assert result.total_questions == 0
    assert "Quiz summary" in output.getvalue()


def test_session_handles_keyboard_interrupt_and_prints_summary(deck):
    output = io.StringIO()

    def interrupt():
        raise KeyboardInterrupt

    result = QuizSession(deck, SequentialMode()).run(input_fn=interrupt, out=output)
    assert result.total_questions == 0
    assert "Quiz interrupted." in output.getvalue()
    assert "Quiz summary" in output.getvalue()


def test_session_colors_feedback_on_terminal_output(deck, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)

    class TerminalOutput(io.StringIO):
        def isatty(self) -> bool:
            return True

    answers = iter(("a1", "wrong", "a3"))
    output = TerminalOutput()
    QuizSession(deck, SequentialMode()).run(input_fn=lambda: next(answers), out=output)

    assert "\033[32mCorrect!\033[0m" in output.getvalue()
    assert "\033[31mIncorrect. Correct answer: A2\033[0m" in output.getvalue()


def test_session_disables_terminal_colors_when_no_color_is_set(deck, monkeypatch):
    class TerminalOutput(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setenv("NO_COLOR", "")
    output = TerminalOutput()
    QuizSession(deck, SequentialMode()).run(input_fn=lambda: "a1", out=output)
    assert "Correct!" in output.getvalue()
    assert "\033[" not in output.getvalue()


def test_detailed_stats_add_correct_answer_count(deck):
    answers = iter(("a1", "wrong", "a3"))
    output = io.StringIO()

    QuizSession(deck, SequentialMode()).run(
        input_fn=lambda: next(answers), out=output, detailed_stats=True
    )

    assert "| Correct answers | 2 |" in output.getvalue()


def test_session_does_not_schedule_wrong_answer_in_sequential_mode(deck):
    answers = iter(("wrong", "a2", "a3"))
    result = QuizSession(deck, SequentialMode()).run(
        input_fn=lambda: next(answers), out=io.StringIO()
    )
    assert result.total_questions == 3
    assert result.missed_terms == ("Q1",)


def test_session_empty_deck_reports_zero_accuracy():
    deck = Deck(cards=())
    output = io.StringIO()
    result = QuizSession(deck, SequentialMode()).run(
        input_fn=lambda: "unused", out=output
    )
    assert result.total_questions == 0
    assert result.accuracy_percentage == 0
    assert "| Missed terms | None |" in output.getvalue()


def test_duplicate_missed_front_is_reported_once():
    deck = Deck(cards=(Flashcard("Q", "A"), Flashcard("Q", "B")))
    answers = iter(("wrong", "wrong"))
    result = QuizSession(deck, SequentialMode()).run(
        input_fn=lambda: next(answers), out=io.StringIO()
    )
    assert result.missed_terms == ("Q",)

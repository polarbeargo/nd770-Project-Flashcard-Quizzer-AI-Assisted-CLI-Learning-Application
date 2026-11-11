"""Integration tests for loading flashcards and running a quiz session."""

from __future__ import annotations

import io

from flashcards import FlashcardLoader, QuizModeFactory, QuizSession


def test_full_session(write_json):
    path = write_json(
        [
            {"front": "Q1", "back": "A1"},
            {"front": "Q2", "back": "A2"},
            {"front": "Q3", "back": "A3"},
        ]
    )
    deck = FlashcardLoader().load_file(path)
    answers = iter(("wrong", "A2", "A3"))
    output = io.StringIO()

    result = QuizSession(deck, QuizModeFactory.create("sequential")).run(
        input_fn=lambda: next(answers), out=output
    )

    assert result.total_questions == 3
    assert result.correct_answers == 2
    assert result.accuracy_percentage == 200 / 3
    assert result.missed_terms == ("Q1",)

    summary = output.getvalue()
    assert summary.count("Question ") == 3
    assert "| Total questions answered | 3 |" in summary
    assert "| Accuracy | 66.7% |" in summary
    assert "| Missed terms | Q1 |" in summary

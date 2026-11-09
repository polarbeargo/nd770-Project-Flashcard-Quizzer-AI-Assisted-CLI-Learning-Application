"""Interactive quiz strategies and session statistics."""

from __future__ import annotations

import random
import sys
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Optional, Sequence, TextIO

from .models import Deck, Flashcard


class QuizMode(ABC):
    """Strategy interface for choosing the next flashcard."""

    name: str

    @abstractmethod
    def start(self, cards: Sequence[Flashcard]) -> None:
        """Reset the strategy for a new quiz."""

    @abstractmethod
    def next_card(self) -> Optional[Flashcard]:
        """Return the next card, or ``None`` when the strategy is finished."""

    @abstractmethod
    def record_answer(self, card: Flashcard, correct: bool) -> None:
        """Record an answer so the strategy can adjust future questions."""


class SequentialMode(QuizMode):
    """Present each card once in its original order."""

    name = "sequential"

    def __init__(self) -> None:
        self._cards: tuple[Flashcard, ...] = ()
        self._index = 0

    def start(self, cards: Sequence[Flashcard]) -> None:
        self._cards = tuple(cards)
        self._index = 0

    def next_card(self) -> Optional[Flashcard]:
        if self._index >= len(self._cards):
            return None
        card = self._cards[self._index]
        self._index += 1
        return card

    def record_answer(self, card: Flashcard, correct: bool) -> None:
        return None


class RandomMode(QuizMode):
    """Present each card once in a shuffled order."""

    name = "random"

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._cards: tuple[Flashcard, ...] = ()
        self._index = 0

    def start(self, cards: Sequence[Flashcard]) -> None:
        shuffled = list(cards)
        self._rng.shuffle(shuffled)
        self._cards = tuple(shuffled)
        self._index = 0

    def next_card(self) -> Optional[Flashcard]:
        if self._index >= len(self._cards):
            return None
        card = self._cards[self._index]
        self._index += 1
        return card

    def record_answer(self, card: Flashcard, correct: bool) -> None:
        return None


class AdaptiveMode(QuizMode):
    """Present all cards once, then retry misses until they are answered correctly."""

    name = "adaptive"

    def __init__(self) -> None:
        self._cards: tuple[Flashcard, ...] = ()
        self._index = 0
        self._review_queue: Deque[Flashcard] = deque()

    def start(self, cards: Sequence[Flashcard]) -> None:
        self._cards = tuple(cards)
        self._index = 0
        self._review_queue.clear()

    def next_card(self) -> Optional[Flashcard]:
        if self._index < len(self._cards):
            card = self._cards[self._index]
            self._index += 1
            return card
        if self._review_queue:
            return self._review_queue.popleft()
        return None

    def record_answer(self, card: Flashcard, correct: bool) -> None:
        if not correct:
            self._review_queue.append(card)


class QuizModeFactory:
    """Create an independent quiz strategy by its CLI-facing name."""

    @staticmethod
    def available() -> tuple[str, ...]:
        """Return supported mode names in display order."""
        return ("sequential", "random", "adaptive")

    @staticmethod
    def create(name: str, *, rng: Optional[random.Random] = None) -> QuizMode:
        """Create a fresh strategy; ``rng`` makes random mode reproducible."""
        normalized = name.strip().casefold()
        if normalized == "sequential":
            return SequentialMode()
        if normalized == "random":
            return RandomMode(rng)
        if normalized == "adaptive":
            return AdaptiveMode()
        options = ", ".join(QuizModeFactory.available())
        raise ValueError(f"Unknown quiz mode '{name}'. Choose from: {options}.")


@dataclass(frozen=True, slots=True)
class QuizResult:
    """Immutable summary of answers submitted during one quiz session."""

    total_questions: int
    correct_answers: int
    missed_terms: tuple[str, ...]

    @property
    def accuracy_percentage(self) -> float:
        """Return correct answers as a percentage of submitted answers."""
        if self.total_questions == 0:
            return 0.0
        return self.correct_answers * 100.0 / self.total_questions


class QuizSession:
    """Run one quiz with an injected question strategy and I/O functions."""

    def __init__(self, deck: Deck, mode: QuizMode) -> None:
        self._deck = deck
        self._mode = mode

    def run(
        self,
        *,
        input_fn: Optional[Callable[[], str]] = None,
        out: Optional[TextIO] = None,
    ) -> QuizResult:
        """Ask questions until completion or the user enters ``q``."""
        output = out if out is not None else sys.stdout
        read_answer = input_fn if input_fn is not None else input
        self._mode.start(self._deck.cards)
        attempts = 0
        correct_answers = 0
        missed_terms: list[str] = []
        seen_missed_terms: set[str] = set()

        print(
            f"Quiz: {self._deck.title or 'Deck'} "
            f"({len(self._deck)} cards; {self._mode.name} mode)",
            file=output,
        )
        while (card := self._mode.next_card()) is not None:
            print(f"\nQuestion {attempts + 1}: {card.front}", file=output)
            print("Your answer (or 'q' to finish): ", end="", file=output, flush=True)
            try:
                answer = read_answer()
            except EOFError:
                break
            if answer.strip().casefold() == "q":
                break

            is_correct = answer.strip().casefold() == card.back.strip().casefold()
            attempts += 1
            if is_correct:
                correct_answers += 1
                print("Correct!", file=output)
            else:
                print(f"Incorrect. Correct answer: {card.back}", file=output)
                if card.front not in seen_missed_terms:
                    seen_missed_terms.add(card.front)
                    missed_terms.append(card.front)
            self._mode.record_answer(card, is_correct)

        result = QuizResult(
            total_questions=attempts,
            correct_answers=correct_answers,
            missed_terms=tuple(missed_terms),
        )
        self._print_summary(result, output)
        return result

    @staticmethod
    def _print_summary(result: QuizResult, out: TextIO) -> None:
        """Print the required end-of-quiz metrics as a compact table."""
        missed = ", ".join(result.missed_terms) or "None"
        print("\nQuiz summary", file=out)
        print("| Metric | Value |", file=out)
        print("|---|---:|", file=out)
        print(f"| Total questions answered | {result.total_questions} |", file=out)
        print(f"| Accuracy | {result.accuracy_percentage:.1f}% |", file=out)
        print(f"| Missed terms | {missed} |", file=out)

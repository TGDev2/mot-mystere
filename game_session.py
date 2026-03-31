from dataclasses import dataclass, field
import random

from scoring import TIME_LIMIT_SECONDS, get_attempts_for_difficulty


@dataclass
class GuessResult:
    letter: str
    was_valid: bool
    already_guessed: bool
    correct: bool
    status: str


@dataclass
class GameSession:
    category: str
    difficulty: str
    secret_word: str
    attempts_left: int
    time_limit: int = TIME_LIMIT_SECONDS
    time_remaining: int = TIME_LIMIT_SECONDS
    guessed_letters: set[str] = field(default_factory=set)

    @classmethod
    def create(cls, categories, category, difficulty, rng=None):
        if category not in categories:
            raise ValueError("La catégorie demandée est introuvable.")

        words = categories[category]
        if not words:
            raise ValueError("La catégorie ne contient aucun mot.")

        random_source = rng or random
        secret_word = random_source.choice(words).upper()
        attempts_left = get_attempts_for_difficulty(difficulty)
        return cls(
            category=category,
            difficulty=difficulty,
            secret_word=secret_word,
            attempts_left=attempts_left,
            time_limit=TIME_LIMIT_SECONDS,
            time_remaining=TIME_LIMIT_SECONDS,
        )

    @property
    def revealed_word(self):
        letters = [
            char if not char.isalpha() or char in self.guessed_letters else "_"
            for char in self.secret_word
        ]
        return " ".join(letters)

    @property
    def letters_tried(self):
        return sorted(self.guessed_letters)

    @property
    def is_won(self):
        return all(
            (not char.isalpha()) or char in self.guessed_letters
            for char in self.secret_word
        )

    @property
    def is_lost(self):
        return self.attempts_left <= 0 or self.time_remaining <= 0

    @property
    def status(self):
        if self.is_won:
            return "won"
        if self.is_lost:
            return "lost"
        return "in_progress"

    def guess(self, letter):
        normalized_letter = str(letter).strip().upper()

        if self.status != "in_progress":
            return GuessResult(normalized_letter, False, False, False, self.status)

        if len(normalized_letter) != 1 or not normalized_letter.isalpha():
            return GuessResult(normalized_letter, False, False, False, self.status)

        if normalized_letter in self.guessed_letters:
            return GuessResult(
                normalized_letter,
                True,
                True,
                normalized_letter in self.secret_word,
                self.status,
            )

        self.guessed_letters.add(normalized_letter)
        correct = normalized_letter in self.secret_word
        if not correct:
            self.attempts_left -= 1

        return GuessResult(normalized_letter, True, False, correct, self.status)

    def tick(self):
        if self.status != "in_progress":
            return self.status

        if self.time_remaining > 0:
            self.time_remaining -= 1

        return self.status

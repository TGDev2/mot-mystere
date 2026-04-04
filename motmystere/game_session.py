from dataclasses import dataclass, field
import random

from .categories import MIN_WORD_POOL_SIZE, WordProfile, get_supported_difficulties, get_words_for_difficulty
from .scoring import get_attempts_for_difficulty, get_time_limit_for_difficulty


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
    word_profile: WordProfile
    attempts_left: int
    time_limit: int
    time_remaining: int
    guessed_letters: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        categories,
        category,
        difficulty,
        rng=None,
        *,
        recent_words=None,
        allowed_words=None,
        minimum_pool_size=MIN_WORD_POOL_SIZE,
    ):
        available_words = get_available_word_profiles(
            categories,
            category,
            difficulty,
            minimum_pool_size=minimum_pool_size,
        )
        random_source = rng or random
        candidate_pool = build_candidate_pool(
            available_words,
            recent_words=recent_words,
            allowed_words=allowed_words,
        )

        selected_profile = random_source.choice(candidate_pool)
        attempts_left = get_attempts_for_difficulty(difficulty)
        time_limit = get_time_limit_for_difficulty(difficulty)
        return cls(
            category=category,
            difficulty=difficulty,
            secret_word=selected_profile.text,
            word_profile=selected_profile,
            attempts_left=attempts_left,
            time_limit=time_limit,
            time_remaining=time_limit,
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
    def word_complexity(self):
        return self.word_profile.complexity

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


def get_available_word_profiles(categories, category, difficulty, *, minimum_pool_size=MIN_WORD_POOL_SIZE):
    if category not in categories:
        raise ValueError("La categorie demandee est introuvable.")

    words = categories[category]
    if not words:
        raise ValueError("La categorie ne contient aucun mot.")

    supported_difficulties = get_supported_difficulties(words, minimum_pool_size)
    if difficulty not in supported_difficulties:
        available = ", ".join(supported_difficulties) or "aucun"
        raise ValueError(
            f"Le niveau {difficulty} n'est pas disponible pour cette categorie. "
            f"Niveaux disponibles : {available}."
        )

    return get_words_for_difficulty(words, difficulty)


def build_candidate_pool(available_words, *, recent_words=None, allowed_words=None):
    if allowed_words is not None:
        allowed_set = {
            str(word).strip().upper()
            for word in allowed_words
            if str(word).strip()
        }
        candidate_pool = [profile for profile in available_words if profile.text in allowed_set]
        if candidate_pool:
            return candidate_pool

    recent_word_set = {
        str(word).strip().upper()
        for word in (recent_words or ())
        if str(word).strip()
    }
    candidate_pool = [profile for profile in available_words if profile.text not in recent_word_set]
    if candidate_pool:
        return candidate_pool
    return list(available_words)

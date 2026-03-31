from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app_paths import get_resource_directory


BASE_DIR = get_resource_directory()
DIFFICULTY_LEVELS = ("Facile", "Moyen", "Difficile")
EASY_COMPLEXITY_MAX = 27
MEDIUM_COMPLEXITY_MAX = 34
RARE_LETTERS = frozenset("KQWXYZJ")


@dataclass(frozen=True)
class WordProfile:
    text: str
    length: int
    unique_letters: int
    repeated_letters: int
    rare_letters: int
    complexity: int
    difficulty: str


def lire_mots(nom_fichier):
    fichier = Path(nom_fichier)
    if not fichier.is_absolute():
        fichier = Path(BASE_DIR) / fichier

    with fichier.open("r", encoding="utf-8") as handle:
        return [mot.strip().upper() for mot in handle if mot.strip()]


def calculate_word_complexity(word):
    normalized = str(word).strip().upper()
    letters = [char for char in normalized if char.isalpha()]
    unique_letters = len(set(letters))
    repeated_letters = max(0, len(letters) - unique_letters)
    rare_letters = sum(1 for char in letters if char in RARE_LETTERS)
    complexity = (len(letters) * 3) + (unique_letters * 2) + (rare_letters * 3) - repeated_letters
    return {
        "length": len(letters),
        "unique_letters": unique_letters,
        "repeated_letters": repeated_letters,
        "rare_letters": rare_letters,
        "complexity": complexity,
    }


def classify_word_difficulty(complexity):
    complexity = int(complexity)
    if complexity <= EASY_COMPLEXITY_MAX:
        return "Facile"
    if complexity <= MEDIUM_COMPLEXITY_MAX:
        return "Moyen"
    return "Difficile"


def build_word_profile(word):
    metrics = calculate_word_complexity(word)
    return WordProfile(
        text=str(word).strip().upper(),
        length=metrics["length"],
        unique_letters=metrics["unique_letters"],
        repeated_letters=metrics["repeated_letters"],
        rare_letters=metrics["rare_letters"],
        complexity=metrics["complexity"],
        difficulty=classify_word_difficulty(metrics["complexity"]),
    )


@lru_cache(maxsize=None)
def _build_profiles(words):
    return tuple(build_word_profile(word) for word in words)


def get_word_profiles(words):
    return list(_build_profiles(tuple(words)))


def get_words_for_difficulty(words, difficulty):
    if difficulty not in DIFFICULTY_LEVELS:
        raise ValueError(f"Difficulte inconnue: {difficulty}")

    profiles = get_word_profiles(words)
    matching_profiles = [profile for profile in profiles if profile.difficulty == difficulty]
    return matching_profiles or profiles


def get_category_difficulty_breakdown(words):
    counter = Counter(profile.difficulty for profile in get_word_profiles(words))
    return {level: counter.get(level, 0) for level in DIFFICULTY_LEVELS}


def load_categories(base_dir=BASE_DIR):
    categories = {}
    for file in sorted(Path(base_dir).glob("*.txt")):
        categories[file.stem] = lire_mots(file)
    return categories

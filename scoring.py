TIME_LIMIT_SECONDS = 60

DIFFICULTY_CONFIG = {
    "Facile": {"attempts": 10, "base_points": 80},
    "Moyen": {"attempts": 7, "base_points": 140},
    "Difficile": {"attempts": 5, "base_points": 220},
}


def get_attempts_for_difficulty(difficulty):
    try:
        return DIFFICULTY_CONFIG[difficulty]["attempts"]
    except KeyError as exc:
        raise ValueError(f"Difficulté inconnue: {difficulty}") from exc


def build_score_breakdown(difficulty, word_length, attempts_left, time_remaining):
    if difficulty not in DIFFICULTY_CONFIG:
        raise ValueError(f"Difficulté inconnue: {difficulty}")

    base_points = DIFFICULTY_CONFIG[difficulty]["base_points"]
    word_bonus = max(0, int(word_length)) * 6
    attempts_bonus = max(0, int(attempts_left)) * 15
    time_bonus = max(0, int(time_remaining)) * 2
    total = base_points + word_bonus + attempts_bonus + time_bonus

    return {
        "base_points": base_points,
        "word_bonus": word_bonus,
        "attempts_bonus": attempts_bonus,
        "time_bonus": time_bonus,
        "total": total,
    }

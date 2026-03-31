TIME_LIMIT_SECONDS = 60

DIFFICULTY_CONFIG = {
    "Facile": {
        "attempts": 10,
        "time_limit": 75,
        "base_points": 70,
        "attempt_bonus": 8,
        "time_bonus_cap": 35,
    },
    "Moyen": {
        "attempts": 7,
        "time_limit": 60,
        "base_points": 150,
        "attempt_bonus": 12,
        "time_bonus_cap": 55,
    },
    "Difficile": {
        "attempts": 5,
        "time_limit": 45,
        "base_points": 240,
        "attempt_bonus": 18,
        "time_bonus_cap": 75,
    },
}


def _get_difficulty_config(difficulty):
    try:
        return DIFFICULTY_CONFIG[difficulty]
    except KeyError as exc:
        raise ValueError(f"Difficulte inconnue: {difficulty}") from exc


def get_attempts_for_difficulty(difficulty):
    return _get_difficulty_config(difficulty)["attempts"]


def get_time_limit_for_difficulty(difficulty):
    return _get_difficulty_config(difficulty)["time_limit"]


def build_score_breakdown(
    difficulty,
    word_length,
    attempts_left,
    time_remaining,
    *,
    word_complexity=None,
    time_limit=None,
):
    config = _get_difficulty_config(difficulty)

    if time_limit is None:
        time_limit = config["time_limit"]

    if word_complexity is None:
        word_complexity = max(0, int(word_length)) * 5

    base_points = config["base_points"]
    word_bonus = max(0, int(word_length)) * 4
    complexity_bonus = max(0, int(word_complexity)) * 2
    attempts_bonus = max(0, int(attempts_left)) * config["attempt_bonus"]

    capped_time_limit = max(1, int(time_limit))
    clamped_time_remaining = min(capped_time_limit, max(0, int(time_remaining)))
    time_ratio = clamped_time_remaining / capped_time_limit
    time_bonus = int(round(time_ratio * config["time_bonus_cap"]))
    total = base_points + word_bonus + complexity_bonus + attempts_bonus + time_bonus

    return {
        "base_points": base_points,
        "word_bonus": word_bonus,
        "complexity_bonus": complexity_bonus,
        "attempts_bonus": attempts_bonus,
        "time_bonus": time_bonus,
        "time_limit": capped_time_limit,
        "total": total,
    }

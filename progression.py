from categories import DIFFICULTY_LEVELS


SCORE_MILESTONES = (100, 250, 500, 900, 1400, 2100, 3200, 4800, 7000)


def format_category_name(category_key):
    return str(category_key).replace("_", " ").title()


def _as_int(value):
    return int(value or 0)


def _ratio(progress, target):
    if target <= 0:
        return 1.0
    return min(1.0, max(0.0, progress / target))


def _pick_score_target(score_total):
    score_total = max(0, _as_int(score_total))
    for milestone in SCORE_MILESTONES:
        if score_total < milestone:
            previous = 0
            for candidate in SCORE_MILESTONES:
                if candidate >= milestone:
                    break
                previous = candidate
            return previous, milestone

    previous = SCORE_MILESTONES[-1]
    next_target = ((_as_int(score_total) // 1000) + 1) * 1000
    return previous, next_target


def _find_supporting_category(category_availability, difficulty, preferred_category=None):
    if preferred_category in category_availability and difficulty in category_availability[preferred_category]:
        return preferred_category

    for category in sorted(category_availability):
        if difficulty in category_availability[category]:
            return category

    return sorted(category_availability)[0]


def _build_category_goal(category_availability, category_stats):
    categories = sorted(category_availability)
    played_categories = {
        category
        for category, stats in category_stats.items()
        if _as_int(stats.get("games_played")) > 0
    }
    unplayed_categories = [category for category in categories if category not in played_categories]

    if unplayed_categories:
        focus_category = unplayed_categories[0]
        focus_difficulty = category_availability[focus_category][0]
        detail = (
            f"Prochaine decouverte : {format_category_name(focus_category)} "
            f"en {focus_difficulty}."
        )
    else:
        focus_category = min(
            categories,
            key=lambda value: (
                _as_int(category_stats.get(value, {}).get("games_played")),
                _as_int(category_stats.get(value, {}).get("wins")),
                value,
            ),
        )
        focus_difficulty = category_availability[focus_category][0]
        detail = (
            f"Toutes les categories ont deja ete lancees. Consolidez "
            f"{format_category_name(focus_category)}."
        )

    return {
        "key": "category_tour",
        "title": "Tour des categories",
        "progress_text": f"{len(played_categories)}/{len(categories)} categories teste(es)",
        "detail": detail,
        "completed": len(played_categories) == len(categories) and bool(categories),
        "ratio": _ratio(len(played_categories), len(categories)),
        "category": focus_category,
        "difficulty": focus_difficulty,
        "cta_text": f"Jouer {format_category_name(focus_category)}",
    }


def _build_difficulty_goal(category_availability, difficulty_stats):
    available_difficulties = [
        difficulty
        for difficulty in DIFFICULTY_LEVELS
        if any(difficulty in options for options in category_availability.values())
    ]
    validated_difficulties = {
        difficulty
        for difficulty in available_difficulties
        if _as_int(difficulty_stats.get(difficulty, {}).get("wins")) > 0
    }
    pending_difficulties = [
        difficulty for difficulty in available_difficulties if difficulty not in validated_difficulties
    ]

    if pending_difficulties:
        focus_difficulty = pending_difficulties[0]
        detail = f"Prochain palier : gagner une manche en {focus_difficulty}."
    else:
        focus_difficulty = max(
            available_difficulties,
            key=lambda value: (
                _as_int(difficulty_stats.get(value, {}).get("average_score")),
                -_as_int(difficulty_stats.get(value, {}).get("wins")),
                DIFFICULTY_LEVELS.index(value),
            ),
        )
        detail = (
            f"Tous les niveaux sont deja valides. Rejouez en {focus_difficulty} "
            "pour pousser le score."
        )

    focus_category = _find_supporting_category(category_availability, focus_difficulty)

    return {
        "key": "difficulty_passport",
        "title": "Passeport des niveaux",
        "progress_text": (
            f"{len(validated_difficulties)}/{len(available_difficulties)} niveaux valides"
        ),
        "detail": detail,
        "completed": len(validated_difficulties) == len(available_difficulties)
        and bool(available_difficulties),
        "ratio": _ratio(len(validated_difficulties), len(available_difficulties)),
        "category": focus_category,
        "difficulty": focus_difficulty,
        "cta_text": f"Valider {focus_difficulty}",
    }


def _build_score_goal(player, dashboard, category_availability):
    score_total = _as_int(player.get("score_total"))
    previous_target, next_target = _pick_score_target(score_total)
    remaining = max(0, next_target - score_total)
    best_difficulty = dashboard.get("best_difficulty") or {}
    favorite_category = dashboard.get("favorite_category") or {}

    focus_difficulty = best_difficulty.get("difficulty") or DIFFICULTY_LEVELS[0]
    focus_category = _find_supporting_category(
        category_availability,
        focus_difficulty,
        preferred_category=favorite_category.get("category"),
    )
    if focus_difficulty not in category_availability.get(focus_category, ()):
        focus_difficulty = category_availability[focus_category][0]

    return {
        "key": "score_milestone",
        "title": "Cap de score",
        "progress_text": f"{score_total}/{next_target} pts",
        "detail": f"Encore {remaining} pts pour atteindre le prochain cap.",
        "completed": False,
        "ratio": _ratio(score_total - previous_target, next_target - previous_target),
        "category": focus_category,
        "difficulty": focus_difficulty,
        "cta_text": "Jouer pour scorer",
    }


def build_progression_snapshot(player, dashboard, category_availability):
    player = player or {}
    dashboard = dashboard or {}
    category_stats = {
        row["category"]: row for row in dashboard.get("category_stats", ())
    }
    difficulty_stats = {
        row["difficulty"]: row for row in dashboard.get("difficulty_stats", ())
    }

    goals = [
        _build_difficulty_goal(category_availability, difficulty_stats),
        _build_category_goal(category_availability, category_stats),
        _build_score_goal(player, dashboard, category_availability),
    ]
    primary_goal = next((goal for goal in goals if not goal["completed"]), goals[0] if goals else None)

    return {
        "goals": goals,
        "primary_goal": primary_goal,
    }


def get_newly_completed_goals(before_snapshot, after_snapshot):
    before_snapshot = before_snapshot or {}
    after_snapshot = after_snapshot or {}
    before_map = {
        goal["key"]: bool(goal.get("completed"))
        for goal in before_snapshot.get("goals", ())
    }

    return [
        goal
        for goal in after_snapshot.get("goals", ())
        if goal.get("completed") and not before_map.get(goal["key"], False)
    ]

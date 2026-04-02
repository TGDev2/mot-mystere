from categories import DIFFICULTY_LEVELS


SCORE_MILESTONES = (100, 250, 500, 900, 1400, 2100, 3200, 4800, 7000)
VALIDATED_WINS = 1
MASTERED_WINS = 3


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


def _build_mastery_cell(category, difficulty, stats):
    games_played = _as_int(stats.get("games_played"))
    wins = _as_int(stats.get("wins"))
    validation_ratio = _ratio(min(wins, VALIDATED_WINS), VALIDATED_WINS)
    mastery_ratio = _ratio(min(wins, MASTERED_WINS), MASTERED_WINS)

    if wins >= MASTERED_WINS:
        state = "mastered"
        state_label = "Maitrise"
        state_rank = 3
        progress_text = f"{MASTERED_WINS}/{MASTERED_WINS}"
        detail = f"{wins} victoire(s) sur {games_played} partie(s)."
    elif wins >= VALIDATED_WINS:
        state = "validated"
        state_label = "Valide"
        state_rank = 2
        progress_text = f"{min(wins, MASTERED_WINS)}/{MASTERED_WINS}"
        detail = f"{wins} victoire(s) sur {games_played} partie(s)."
    elif games_played > 0:
        state = "in_progress"
        state_label = "A valider"
        state_rank = 1
        progress_text = f"0/{VALIDATED_WINS}"
        detail = f"{games_played} tentative(s) sans victoire."
    else:
        state = "not_started"
        state_label = "Non joue"
        state_rank = 0
        progress_text = f"0/{VALIDATED_WINS}"
        detail = "Aucune partie enregistree."

    return {
        "category": category,
        "difficulty": difficulty,
        "games_played": games_played,
        "wins": wins,
        "state": state,
        "state_label": state_label,
        "state_rank": state_rank,
        "progress_text": progress_text,
        "detail": detail,
        "validation_ratio": validation_ratio,
        "mastery_ratio": mastery_ratio,
    }


def _pick_validation_focus_pair(cells):
    pending_not_started = [
        cell for cell in cells if cell["state"] == "not_started"
    ]
    if pending_not_started:
        return sorted(
            pending_not_started,
            key=lambda cell: (cell["category"], DIFFICULTY_LEVELS.index(cell["difficulty"])),
        )[0]

    pending_in_progress = [
        cell for cell in cells if cell["state"] == "in_progress"
    ]
    if pending_in_progress:
        return sorted(
            pending_in_progress,
            key=lambda cell: (
                -cell["games_played"],
                cell["category"],
                DIFFICULTY_LEVELS.index(cell["difficulty"]),
            ),
        )[0]

    pending_validated = [
        cell for cell in cells if cell["state"] == "validated"
    ]
    if pending_validated:
        return sorted(
            pending_validated,
            key=lambda cell: (
                cell["wins"],
                cell["games_played"],
                cell["category"],
                DIFFICULTY_LEVELS.index(cell["difficulty"]),
            ),
        )[0]

    return None


def _pick_mastery_focus_pair(cells):
    validated_cells = [cell for cell in cells if cell["state"] == "validated"]
    if validated_cells:
        return sorted(
            validated_cells,
            key=lambda cell: (
                cell["wins"],
                cell["games_played"],
                cell["category"],
                DIFFICULTY_LEVELS.index(cell["difficulty"]),
            ),
        )[0]

    return _pick_validation_focus_pair(cells)


def build_mastery_snapshot(category_availability, selection_stats):
    selection_stats = selection_stats or ()
    stats_map = {
        (row["category"], row["difficulty"]): row
        for row in selection_stats
    }

    rows = []
    all_cells = []
    for category in sorted(category_availability):
        row = {
            "category": category,
            "label": format_category_name(category),
            "cells": [],
        }
        for difficulty in DIFFICULTY_LEVELS:
            if difficulty not in category_availability.get(category, ()):
                row["cells"].append(
                    {
                        "category": category,
                        "difficulty": difficulty,
                        "available": False,
                        "state": "unavailable",
                        "state_label": "-",
                        "progress_text": "-",
                        "detail": "Niveau indisponible.",
                    }
                )
                continue

            cell = _build_mastery_cell(
                category,
                difficulty,
                stats_map.get((category, difficulty), {}),
            )
            cell["available"] = True
            row["cells"].append(cell)
            all_cells.append(cell)
        rows.append(row)

    total_pairs = len(all_cells)
    validated_pairs = sum(1 for cell in all_cells if cell["wins"] >= VALIDATED_WINS)
    mastered_pairs = sum(1 for cell in all_cells if cell["wins"] >= MASTERED_WINS)
    focus_pair = _pick_validation_focus_pair(all_cells)
    mastery_focus_pair = _pick_mastery_focus_pair(all_cells)

    return {
        "rows": rows,
        "cells": all_cells,
        "total_pairs": total_pairs,
        "validated_pairs": validated_pairs,
        "mastered_pairs": mastered_pairs,
        "validation_percent": int(round(_ratio(validated_pairs, total_pairs) * 100)),
        "mastery_percent": int(round(_ratio(mastered_pairs, total_pairs) * 100)),
        "pairs_left_to_validate": max(0, total_pairs - validated_pairs),
        "pairs_left_to_master": max(0, total_pairs - mastered_pairs),
        "focus_pair": focus_pair,
        "mastery_focus_pair": mastery_focus_pair,
    }


def _build_validation_goal(mastery):
    focus_pair = mastery.get("focus_pair")
    total_pairs = mastery["total_pairs"]
    validated_pairs = mastery["validated_pairs"]

    if focus_pair is None:
        detail = "Toutes les paires categorie/niveau ont deja ete validees."
        category = None
        difficulty = None
    else:
        detail = (
            f"Prochaine paire a valider : {format_category_name(focus_pair['category'])} "
            f"en {focus_pair['difficulty']}."
        )
        category = focus_pair["category"]
        difficulty = focus_pair["difficulty"]

    return {
        "key": "validation_board",
        "title": "Carte de validation",
        "progress_text": f"{validated_pairs}/{total_pairs} paires validees",
        "detail": detail,
        "completed": validated_pairs == total_pairs and total_pairs > 0,
        "ratio": _ratio(validated_pairs, total_pairs),
        "category": category,
        "difficulty": difficulty,
        "cta_text": "Valider la paire",
    }


def _build_mastery_goal(mastery):
    focus_pair = mastery.get("mastery_focus_pair")
    total_pairs = mastery["total_pairs"]
    mastered_pairs = mastery["mastered_pairs"]

    if focus_pair is None:
        detail = "Toutes les paires categorie/niveau sont deja maitrisees."
        category = None
        difficulty = None
    else:
        detail = (
            f"Prochaine paire a maitriser : {format_category_name(focus_pair['category'])} "
            f"en {focus_pair['difficulty']}."
        )
        category = focus_pair["category"]
        difficulty = focus_pair["difficulty"]

    return {
        "key": "mastery_board",
        "title": "Carte de maitrise",
        "progress_text": f"{mastered_pairs}/{total_pairs} paires maitrisees",
        "detail": detail,
        "completed": mastered_pairs == total_pairs and total_pairs > 0,
        "ratio": _ratio(mastered_pairs, total_pairs),
        "category": category,
        "difficulty": difficulty,
        "cta_text": "Maitriser la paire",
    }


def _build_score_goal(player, dashboard, category_availability, mastery):
    score_total = _as_int(player.get("score_total"))
    previous_target, next_target = _pick_score_target(score_total)
    remaining = max(0, next_target - score_total)
    best_difficulty = dashboard.get("best_difficulty") or {}
    favorite_category = dashboard.get("favorite_category") or {}
    focus_pair = mastery.get("mastery_focus_pair") or mastery.get("focus_pair")

    if focus_pair is not None:
        focus_category = focus_pair["category"]
        focus_difficulty = focus_pair["difficulty"]
    else:
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
    mastery = build_mastery_snapshot(
        category_availability,
        dashboard.get("selection_stats", ()),
    )

    goals = [
        _build_validation_goal(mastery),
        _build_mastery_goal(mastery),
        _build_score_goal(player, dashboard, category_availability, mastery),
    ]
    primary_goal = next((goal for goal in goals if not goal["completed"]), goals[0] if goals else None)

    return {
        "goals": goals,
        "primary_goal": primary_goal,
        "mastery": mastery,
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


def get_newly_reached_mastery_states(before_snapshot, after_snapshot):
    before_snapshot = before_snapshot or {}
    after_snapshot = after_snapshot or {}

    before_map = {
        (cell["category"], cell["difficulty"]): cell
        for cell in before_snapshot.get("mastery", {}).get("cells", ())
        if cell.get("available")
    }

    updates = []
    for cell in after_snapshot.get("mastery", {}).get("cells", ()):
        if not cell.get("available"):
            continue

        before_cell = before_map.get((cell["category"], cell["difficulty"]), {})
        before_wins = _as_int(before_cell.get("wins"))
        after_wins = _as_int(cell.get("wins"))
        if before_wins < VALIDATED_WINS <= after_wins:
            updates.append(
                {
                    "category": cell["category"],
                    "difficulty": cell["difficulty"],
                    "state": "validated",
                    "title": (
                        f"{format_category_name(cell['category'])} / {cell['difficulty']} valide"
                    ),
                }
            )
        if before_wins < MASTERED_WINS <= after_wins:
            updates.append(
                {
                    "category": cell["category"],
                    "difficulty": cell["difficulty"],
                    "state": "mastered",
                    "title": (
                        f"{format_category_name(cell['category'])} / {cell['difficulty']} maitrise"
                    ),
                }
            )

    return updates

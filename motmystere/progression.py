from .categories import DIFFICULTY_LEVELS, format_category_name
from .scoring import get_attempts_for_difficulty, get_time_limit_for_difficulty


SCORE_MILESTONES = (100, 250, 500, 900, 1400, 2100, 3200, 4800, 7000)
VALIDATED_WINS = 1
MASTERED_WINS = 3
RECENT_WINDOW_SIZE = 5
REVIEW_RECENT_GAMES_SCAN = 8
FAILED_WORDS_REVIEW_LIMIT = 3
RECENT_WINDOW_WEIGHTS = (5, 4, 3, 2, 1)
RECENT_WEIGHTING_LABEL = "5-4-3-2-1"
RECENT_DRIVER_THRESHOLD = 60
RECENT_DRIVER_MARGIN = 10
SECONDARY_AXIS_THRESHOLD = 25
LOW_RESOURCE_THRESHOLD = 0.20
LOW_RESOURCE_WIN_THRESHOLD = 0.15
TIME_EXPIRED_POINTS = 10
TIME_LOW_MARGIN_POINTS = 4
TIME_LOW_MARGIN_WIN_POINTS = 3
ERROR_EXPIRED_POINTS = 10
ERROR_LOW_MARGIN_POINTS = 4
ERROR_LOW_MARGIN_WIN_POINTS = 3


def _as_int(value):
    return int(value or 0)


def _ratio(progress, target):
    if target <= 0:
        return 1.0
    return min(1.0, max(0.0, progress / target))


def _safe_ratio(value, total):
    return min(1.0, max(0.0, (float(value or 0) / float(total)))) if total else 0.0


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
    pending_not_started = [cell for cell in cells if cell["state"] == "not_started"]
    if pending_not_started:
        return sorted(
            pending_not_started,
            key=lambda cell: (cell["category"], DIFFICULTY_LEVELS.index(cell["difficulty"])),
        )[0]

    pending_in_progress = [cell for cell in cells if cell["state"] == "in_progress"]
    if pending_in_progress:
        return sorted(
            pending_in_progress,
            key=lambda cell: (
                -cell["games_played"],
                cell["category"],
                DIFFICULTY_LEVELS.index(cell["difficulty"]),
            ),
        )[0]

    pending_validated = [cell for cell in cells if cell["state"] == "validated"]
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
    stats_map = {(row["category"], row["difficulty"]): row for row in selection_stats}

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
        "family": "validation_board",
        "title": "Carte de validation",
        "progress_text": f"{validated_pairs}/{total_pairs} paires validees",
        "detail": detail,
        "completed": validated_pairs == total_pairs and total_pairs > 0,
        "ratio": _ratio(validated_pairs, total_pairs),
        "current_value": validated_pairs,
        "target_value": total_pairs,
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
        "family": "mastery_board",
        "title": "Carte de maitrise",
        "progress_text": f"{mastered_pairs}/{total_pairs} paires maitrisees",
        "detail": detail,
        "completed": mastered_pairs == total_pairs and total_pairs > 0,
        "ratio": _ratio(mastered_pairs, total_pairs),
        "current_value": mastered_pairs,
        "target_value": total_pairs,
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
        "family": "score_milestone",
        "title": "Cap de score",
        "progress_text": f"{score_total}/{next_target} pts",
        "detail": f"Encore {remaining} pts pour atteindre le prochain cap.",
        "completed": False,
        "ratio": _ratio(score_total - previous_target, next_target - previous_target),
        "current_value": score_total,
        "target_value": next_target,
        "category": focus_category,
        "difficulty": focus_difficulty,
        "cta_text": "Jouer pour scorer",
    }


def _build_pair_challenge(mastery):
    focus_pair = mastery.get("focus_pair")
    if focus_pair is not None:
        wins = _as_int(focus_pair.get("wins"))
        target = VALIDATED_WINS
        title = "Defi de validation"
        detail = (
            f"Gagnez une manche sur {format_category_name(focus_pair['category'])} "
            f"en {focus_pair['difficulty']} pour valider cette paire."
        )
        cta_text = "Valider maintenant"
    else:
        focus_pair = mastery.get("mastery_focus_pair")
        if focus_pair is None:
            focus_pair = next((cell for cell in mastery.get("cells", ()) if cell.get("available")), None)

        if focus_pair is None:
            return {
                "key": "challenge_pair_mastery",
                "family": "challenge_pair",
                "title": "Defi de maitrise",
                "progress_text": "Carte complete",
                "detail": "Toutes les paires categorie/niveau sont deja maitrisees.",
                "completed": True,
                "ratio": 1.0,
                "current_value": MASTERED_WINS,
                "target_value": MASTERED_WINS,
                "category": None,
                "difficulty": None,
                "cta_text": "Continuer a jouer",
            }

        wins = _as_int(focus_pair.get("wins"))
        target = MASTERED_WINS
        title = "Defi de maitrise"
        detail = (
            f"Poussez {format_category_name(focus_pair['category'])} en {focus_pair['difficulty']} "
            f"jusqu'a {MASTERED_WINS} victoires pour maitriser la paire."
        )
        cta_text = "Maitriser la paire"

    return {
        "key": f"challenge_pair_{focus_pair['category']}_{focus_pair['difficulty']}_{target}",
        "family": "challenge_pair",
        "title": title,
        "progress_text": f"{min(wins, target)}/{target} victoire(s)",
        "detail": detail,
        "completed": wins >= target,
        "ratio": _ratio(min(wins, target), target),
        "current_value": min(wins, target),
        "target_value": target,
        "category": focus_pair["category"],
        "difficulty": focus_pair["difficulty"],
        "cta_text": cta_text,
    }


def _build_form_challenge(dashboard, category_availability, mastery):
    recent_form = dashboard.get("recent_form") or {}
    favorite_category = dashboard.get("favorite_category") or {}
    best_difficulty = dashboard.get("best_difficulty") or {}
    mastery_focus = mastery.get("mastery_focus_pair") or mastery.get("focus_pair") or {}

    recent_wins = _as_int(recent_form.get("recent_wins"))
    recent_games = _as_int(recent_form.get("recent_games"))
    target = 3 if recent_wins < 3 else 4 if recent_wins < 4 else 5
    difficulty = best_difficulty.get("difficulty") or mastery_focus.get("difficulty") or DIFFICULTY_LEVELS[0]
    preferred_category = favorite_category.get("category") or mastery_focus.get("category")
    category = _find_supporting_category(
        category_availability,
        difficulty,
        preferred_category=preferred_category,
    )

    if recent_games == 0:
        detail = (
            "Lancez une premiere manche puis stabilisez votre rythme jusqu'a "
            f"{target} victoire(s) sur vos 5 dernieres parties."
        )
    else:
        detail = (
            f"Passez a {target} victoire(s) sur vos 5 dernieres parties "
            "pour installer une dynamique solide."
        )

    return {
        "key": f"challenge_recent_form_{target}",
        "family": "challenge_recent_form",
        "title": "Defi de regularite",
        "progress_text": f"{min(recent_wins, target)}/{target} victoire(s) recentes",
        "detail": detail,
        "completed": recent_wins >= target,
        "ratio": _ratio(min(recent_wins, target), target),
        "current_value": min(recent_wins, target),
        "target_value": target,
        "category": category,
        "difficulty": difficulty,
        "cta_text": "Enchainer une victoire",
    }


def _build_score_challenge(player, dashboard, category_availability, mastery):
    score_goal = _build_score_goal(player, dashboard, category_availability, mastery)
    _, next_target = _pick_score_target(_as_int((player or {}).get("score_total")))
    score_goal["key"] = f"challenge_score_{next_target}"
    score_goal["family"] = "challenge_score"
    score_goal["title"] = "Defi de score"
    score_goal["detail"] = (
        f"{score_goal['detail']} Priorite ideale : "
        f"{format_category_name(score_goal['category'])} en {score_goal['difficulty']}."
        if score_goal["category"] and score_goal["difficulty"]
        else score_goal["detail"]
    )
    score_goal["cta_text"] = "Aller chercher le cap"
    return score_goal


def _get_available_cell(mastery, category, difficulty):
    for cell in mastery.get("cells", ()):
        if not cell.get("available"):
            continue
        if cell.get("category") == category and cell.get("difficulty") == difficulty:
            return cell
    return None


def _format_selection(category, difficulty):
    if not category or not difficulty:
        return "le reglage conseille"
    return f"{format_category_name(category)} en {difficulty}"


def _resolve_lower_difficulty(category_availability, category, difficulty):
    available_difficulties = category_availability.get(category, ())
    if not available_difficulties:
        return None
    if difficulty not in available_difficulties:
        return available_difficulties[0]

    difficulty_index = available_difficulties.index(difficulty)
    if difficulty_index <= 0:
        return difficulty
    return available_difficulties[difficulty_index - 1]


def _iter_weighted_recent_games(recent_games):
    recent_games = recent_games or ()
    for index, game in enumerate(recent_games[:RECENT_WINDOW_SIZE]):
        yield index, RECENT_WINDOW_WEIGHTS[index], game


def _build_time_pressure_signal(recent_games, category_availability):
    entries = []
    score = 0

    for index, weight, game in _iter_weighted_recent_games(recent_games):
        try:
            time_limit = get_time_limit_for_difficulty(game.get("difficulty"))
        except ValueError:
            continue

        contribution = 0
        reason = None
        time_ratio = _safe_ratio(
            min(_as_int(game.get("time_remaining")), time_limit),
            max(1, time_limit),
        )
        if game.get("end_reason") == "time":
            contribution = weight * TIME_EXPIRED_POINTS
            reason = "timeout"
        elif bool(game.get("won")) and time_ratio <= LOW_RESOURCE_WIN_THRESHOLD:
            contribution = weight * TIME_LOW_MARGIN_WIN_POINTS
            reason = "tight_win"
        elif time_ratio <= LOW_RESOURCE_THRESHOLD:
            contribution = weight * TIME_LOW_MARGIN_POINTS
            reason = "low_margin"

        if contribution <= 0:
            continue

        entry = {
            "index": index,
            "weight": weight,
            "contribution": contribution,
            "reason": reason,
            "category": game.get("category"),
            "difficulty": game.get("difficulty"),
        }
        entries.append(entry)
        score += contribution

    available_entries = [
        entry
        for entry in entries
        if entry["category"] in category_availability
        and entry["difficulty"] in category_availability[entry["category"]]
    ]

    top_entry = None
    if available_entries:
        top_entry = max(available_entries, key=lambda entry: (entry["contribution"], -entry["index"]))

    return {
        "score": min(100, score),
        "entries": entries,
        "top_entry": top_entry,
    }


def _build_error_pressure_signal(recent_games, category_availability):
    entries = []
    score = 0

    for index, weight, game in _iter_weighted_recent_games(recent_games):
        try:
            attempts_budget = get_attempts_for_difficulty(game.get("difficulty"))
        except ValueError:
            continue

        contribution = 0
        reason = None
        attempts_ratio = _safe_ratio(
            min(_as_int(game.get("attempts_left")), attempts_budget),
            max(1, attempts_budget),
        )
        if game.get("end_reason") == "attempts":
            contribution = weight * ERROR_EXPIRED_POINTS
            reason = "attempts_exhausted"
        elif bool(game.get("won")) and attempts_ratio <= LOW_RESOURCE_WIN_THRESHOLD:
            contribution = weight * ERROR_LOW_MARGIN_WIN_POINTS
            reason = "tight_win"
        elif attempts_ratio <= LOW_RESOURCE_THRESHOLD:
            contribution = weight * ERROR_LOW_MARGIN_POINTS
            reason = "low_margin"

        if contribution <= 0:
            continue

        entry = {
            "index": index,
            "weight": weight,
            "contribution": contribution,
            "reason": reason,
            "category": game.get("category"),
            "difficulty": game.get("difficulty"),
        }
        entries.append(entry)
        score += contribution

    available_entries = [
        entry
        for entry in entries
        if entry["category"] in category_availability
        and entry["difficulty"] in category_availability[entry["category"]]
    ]

    top_entry = None
    if available_entries:
        top_entry = max(available_entries, key=lambda entry: (entry["contribution"], -entry["index"]))

    return {
        "score": min(100, score),
        "entries": entries,
        "top_entry": top_entry,
    }


def _build_mastery_gap_signal(mastery, recent_games):
    focus_pair = mastery.get("focus_pair")
    pair = focus_pair or mastery.get("mastery_focus_pair")
    if pair is None:
        return {
            "score": 0,
            "pair": None,
            "recent_retry_without_win": False,
        }

    if pair["state"] in {"not_started", "in_progress"}:
        score = 70
    elif pair["state"] == "validated":
        score = 45
    else:
        score = 0

    recent_retry_without_win = any(
        game.get("category") == pair["category"]
        and game.get("difficulty") == pair["difficulty"]
        and not bool(game.get("won"))
        for game in (recent_games or ())[:RECENT_WINDOW_SIZE]
    )
    if score and recent_retry_without_win:
        score += 10

    return {
        "score": min(100, score),
        "pair": pair,
        "recent_retry_without_win": recent_retry_without_win,
    }


def _build_mastery_axis_detail(mastery_gap):
    pair = mastery_gap.get("pair")
    if pair is None:
        return "Carte de maitrise complete sur les reglages actuellement disponibles."

    selection_text = _format_selection(pair["category"], pair["difficulty"])
    if pair["state"] in {"not_started", "in_progress"}:
        if mastery_gap.get("recent_retry_without_win"):
            return f"{selection_text} reste la prochaine validation rentable et resiste encore."
        return f"{selection_text} reste la prochaine paire a valider."
    return f"{selection_text} reste la prochaine paire a maitriser."


def _build_recent_axis_detail(signal, axis_key):
    score = signal["score"]
    if score <= 0:
        if axis_key == "time_pressure":
            return "Le temps recent reste sous controle."
        return "Les erreurs recentes restent sous controle."
    if score < SECONDARY_AXIS_THRESHOLD:
        if axis_key == "time_pressure":
            return "Quelques manches recentes se terminent avec peu de marge au chrono."
        return "Quelques manches recentes se terminent avec peu de marge sur les essais."
    if axis_key == "time_pressure":
        return "Le chrono recent commence a peser sur la progression."
    return "Les erreurs recentes commencent a bloquer la progression."


def _build_axis_status(axis_key, dominant_driver, score):
    if axis_key == dominant_driver:
        return "Dominant"
    if score >= SECONDARY_AXIS_THRESHOLD:
        return "Secondaire"
    return "Sous controle"


def _build_mastery_recommendation(mastery_gap):
    pair = mastery_gap.get("pair")
    if pair is None:
        return {
            "driver": "mastery_gap",
            "driver_label": "Maitrise",
            "category": None,
            "difficulty": None,
            "title": "Continuer a varier les manches",
            "detail": "La carte de maitrise est complete sur les reglages disponibles.",
            "cta_text": "Jouer la reco",
        }

    category = pair["category"]
    difficulty = pair["difficulty"]
    selection_text = _format_selection(category, difficulty)

    if pair["state"] in {"not_started", "in_progress"}:
        detail = f"{selection_text} reste la prochaine paire a valider pour debloquer un vrai palier."
        if mastery_gap.get("recent_retry_without_win"):
            detail += " Cette paire a encore resiste recemment, ce qui renforce la priorite."
        title = f"Valider {format_category_name(category)} en {difficulty}"
    else:
        detail = f"{selection_text} reste la paire la plus rentable a pousser jusqu'a la maitrise."
        title = f"Maitriser {format_category_name(category)} en {difficulty}"

    return {
        "driver": "mastery_gap",
        "driver_label": "Maitrise",
        "category": category,
        "difficulty": difficulty,
        "title": title,
        "detail": detail,
        "cta_text": "Jouer la reco",
    }


def _append_mastery_override(detail, driver_label, recommendation, mastery_recommendation):
    same_selection = (
        recommendation.get("category") == mastery_recommendation.get("category")
        and recommendation.get("difficulty") == mastery_recommendation.get("difficulty")
    )
    if same_selection or not mastery_recommendation.get("category") or not mastery_recommendation.get("difficulty"):
        return detail

    mastery_text = _format_selection(
        mastery_recommendation["category"],
        mastery_recommendation["difficulty"],
    )
    return (
        f"{detail} La carte de maitrise reste {mastery_text}, "
        f"mais {driver_label.lower()} est le levier dominant pour l'instant."
    )


def _build_time_recommendation(signal, category_availability, mastery_recommendation):
    top_entry = signal.get("top_entry")
    if top_entry is None:
        return mastery_recommendation

    category = top_entry["category"]
    source_difficulty = top_entry["difficulty"]
    difficulty = _resolve_lower_difficulty(category_availability, category, source_difficulty)
    if difficulty is None:
        return mastery_recommendation

    source_text = _format_selection(category, source_difficulty)
    target_text = _format_selection(category, difficulty)
    if difficulty != source_difficulty:
        detail = f"Le temps recent bloque surtout sur {source_text}. Redescendez sur {target_text} pour retrouver de la marge."
    else:
        detail = f"Le temps recent bloque surtout sur {source_text}. Rejouez ce reglage pour securiser le chrono."

    recommendation = {
        "driver": "time_pressure",
        "driver_label": "Temps",
        "category": category,
        "difficulty": difficulty,
        "title": f"Reprendre {format_category_name(category)} en {difficulty}",
        "detail": detail,
        "cta_text": "Jouer la reco",
    }
    recommendation["detail"] = _append_mastery_override(
        recommendation["detail"],
        recommendation["driver_label"],
        recommendation,
        mastery_recommendation,
    )
    return recommendation


def _build_error_recommendation(signal, mastery, category_availability, mastery_recommendation):
    top_entry = signal.get("top_entry")
    if top_entry is None:
        return mastery_recommendation

    category = top_entry["category"]
    source_difficulty = top_entry["difficulty"]
    source_cell = _get_available_cell(mastery, category, source_difficulty)
    keep_same_difficulty = source_cell is not None and _as_int(source_cell.get("wins")) == 0
    difficulty = source_difficulty if keep_same_difficulty else _resolve_lower_difficulty(
        category_availability,
        category,
        source_difficulty,
    )
    if difficulty is None:
        return mastery_recommendation

    source_text = _format_selection(category, source_difficulty)
    target_text = _format_selection(category, difficulty)
    if keep_same_difficulty:
        detail = (
            f"Les erreurs recentes dominent sur {source_text}. Gardez ce niveau : "
            "la paire n'a pas encore de victoire."
        )
    elif difficulty != source_difficulty:
        detail = f"Les erreurs recentes dominent sur {source_text}. Redescendez sur {target_text} pour retrouver de la precision."
    else:
        detail = f"Les erreurs recentes dominent sur {source_text}. Rejouez ce reglage pour nettoyer les erreurs."

    recommendation = {
        "driver": "error_pressure",
        "driver_label": "Erreurs",
        "category": category,
        "difficulty": difficulty,
        "title": f"Reprendre {format_category_name(category)} en {difficulty}",
        "detail": detail,
        "cta_text": "Jouer la reco",
    }
    recommendation["detail"] = _append_mastery_override(
        recommendation["detail"],
        recommendation["driver_label"],
        recommendation,
        mastery_recommendation,
    )
    return recommendation


def _choose_dominant_driver(time_signal, error_signal):
    if (
        time_signal["score"] >= RECENT_DRIVER_THRESHOLD
        and time_signal["score"] >= error_signal["score"] + RECENT_DRIVER_MARGIN
        and time_signal.get("top_entry") is not None
    ):
        return "time_pressure"
    if (
        error_signal["score"] >= RECENT_DRIVER_THRESHOLD
        and error_signal["score"] >= time_signal["score"] + RECENT_DRIVER_MARGIN
        and error_signal.get("top_entry") is not None
    ):
        return "error_pressure"
    return "mastery_gap"


def _build_learning_profile(mastery, recent_games, category_availability):
    time_signal = _build_time_pressure_signal(recent_games, category_availability)
    error_signal = _build_error_pressure_signal(recent_games, category_availability)
    mastery_gap = _build_mastery_gap_signal(mastery, recent_games)
    dominant_driver = _choose_dominant_driver(time_signal, error_signal)
    mastery_recommendation = _build_mastery_recommendation(mastery_gap)

    if dominant_driver == "time_pressure":
        recommendation = _build_time_recommendation(
            time_signal,
            category_availability,
            mastery_recommendation,
        )
    elif dominant_driver == "error_pressure":
        recommendation = _build_error_recommendation(
            error_signal,
            mastery,
            category_availability,
            mastery_recommendation,
        )
    else:
        recommendation = mastery_recommendation

    axes = (
        {
            "key": "time_pressure",
            "label": "Temps",
            "score": time_signal["score"],
            "status": _build_axis_status("time_pressure", dominant_driver, time_signal["score"]),
            "detail": _build_recent_axis_detail(time_signal, "time_pressure"),
        },
        {
            "key": "error_pressure",
            "label": "Erreurs",
            "score": error_signal["score"],
            "status": _build_axis_status("error_pressure", dominant_driver, error_signal["score"]),
            "detail": _build_recent_axis_detail(error_signal, "error_pressure"),
        },
        {
            "key": "mastery_gap",
            "label": "Maitrise",
            "score": mastery_gap["score"],
            "status": _build_axis_status("mastery_gap", dominant_driver, mastery_gap["score"]),
            "detail": _build_mastery_axis_detail(mastery_gap),
        },
    )

    learning_profile = {
        "dominant_driver": dominant_driver,
        "axes": axes,
        "recent_window_size": RECENT_WINDOW_SIZE,
        "weighting": RECENT_WEIGHTING_LABEL,
    }
    return learning_profile, recommendation, time_signal, error_signal


def _build_failed_words_review_option(recent_games, category_availability):
    targets = []
    seen_targets = set()
    for game in (recent_games or ())[:REVIEW_RECENT_GAMES_SCAN]:
        category = game.get("category")
        difficulty = game.get("difficulty")
        secret_word = str(game.get("secret_word") or "").strip().upper()
        if bool(game.get("won")) or not category or not difficulty or not secret_word:
            continue
        if category not in category_availability or difficulty not in category_availability[category]:
            continue

        target_key = (category, difficulty, secret_word)
        if target_key in seen_targets:
            continue

        seen_targets.add(target_key)
        targets.append(
            {
                "category": category,
                "difficulty": difficulty,
                "secret_word": secret_word,
                "label": _format_selection(category, difficulty),
            }
        )
        if len(targets) >= FAILED_WORDS_REVIEW_LIMIT:
            break

    if not targets:
        return None

    target_count = len(targets)
    first_target = targets[0]
    detail = (
        f"{target_count} mot(s) perdu(s) recemment peuvent etre rejoues hors rotation normale. "
        f"Le premier repart sur {first_target['label']}."
    )
    return {
        "kind": "failed_words",
        "title": "Reviser mes mots rates",
        "detail": detail,
        "cta_text": "Reviser mes mots rates",
        "count": target_count,
        "category": first_target["category"],
        "difficulty": first_target["difficulty"],
        "targets": tuple(targets),
    }


def _build_weak_pair_review_option(dominant_driver, time_signal, error_signal, category_availability):
    if dominant_driver == "time_pressure":
        signal = time_signal
        driver_label = "Temps"
    elif dominant_driver == "error_pressure":
        signal = error_signal
        driver_label = "Erreurs"
    else:
        return None

    top_entry = signal.get("top_entry")
    if top_entry is None:
        return None

    category = top_entry.get("category")
    difficulty = top_entry.get("difficulty")
    if category not in category_availability or difficulty not in category_availability[category]:
        return None

    selection_text = _format_selection(category, difficulty)
    detail = (
        f"{driver_label} reste le signal fragile dominant sur {selection_text}. "
        "Lancez une revision ciblee hors rotation normale pour retrouver de la marge sur cette paire."
    )
    return {
        "kind": "weak_pair",
        "driver": dominant_driver,
        "driver_label": driver_label,
        "category": category,
        "difficulty": difficulty,
        "title": "Travailler mon reglage fragile",
        "detail": detail,
        "cta_text": "Travailler mon reglage fragile",
        "target_value": 2,
        "max_rounds": 3,
    }


def _build_review_options(recent_games, category_availability, dominant_driver, time_signal, error_signal):
    return {
        "failed_words": _build_failed_words_review_option(recent_games, category_availability),
        "weak_pair": _build_weak_pair_review_option(
            dominant_driver,
            time_signal,
            error_signal,
            category_availability,
        ),
    }


def build_progression_snapshot(player, dashboard, category_availability):
    player = player or {}
    dashboard = dashboard or {}
    recent_games = dashboard.get("recent_games", ())
    mastery = build_mastery_snapshot(
        category_availability,
        dashboard.get("selection_stats", ()),
    )

    goals = [
        _build_validation_goal(mastery),
        _build_mastery_goal(mastery),
        _build_score_goal(player, dashboard, category_availability, mastery),
    ]
    challenges = [
        _build_pair_challenge(mastery),
        _build_form_challenge(dashboard, category_availability, mastery),
        _build_score_challenge(player, dashboard, category_availability, mastery),
    ]
    primary_goal = next((goal for goal in goals if not goal["completed"]), goals[0] if goals else None)
    featured_challenge = next(
        (challenge for challenge in challenges if not challenge["completed"]),
        challenges[0] if challenges else None,
    )
    learning_profile, personalized_recommendation, time_signal, error_signal = _build_learning_profile(
        mastery,
        recent_games,
        category_availability,
    )
    review_options = _build_review_options(
        recent_games,
        category_availability,
        learning_profile["dominant_driver"],
        time_signal,
        error_signal,
    )

    return {
        "goals": goals,
        "challenges": challenges,
        "featured_challenge": featured_challenge,
        "primary_goal": primary_goal,
        "mastery": mastery,
        "learning_profile": learning_profile,
        "personalized_recommendation": personalized_recommendation,
        "review_options": review_options,
    }


def get_newly_completed_goals(before_snapshot, after_snapshot):
    before_snapshot = before_snapshot or {}
    after_snapshot = after_snapshot or {}
    before_map = {goal["key"]: bool(goal.get("completed")) for goal in before_snapshot.get("goals", ())}

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
                    "title": f"{format_category_name(cell['category'])} / {cell['difficulty']} valide",
                }
            )
        if before_wins < MASTERED_WINS <= after_wins:
            updates.append(
                {
                    "category": cell["category"],
                    "difficulty": cell["difficulty"],
                    "state": "mastered",
                    "title": f"{format_category_name(cell['category'])} / {cell['difficulty']} maitrise",
                }
            )

    return updates

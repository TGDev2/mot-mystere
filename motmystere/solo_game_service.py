import json
from datetime import datetime

from .database import (
    get_or_create_player,
    get_player_dashboard,
    get_word_rotation_state,
    record_game_result,
    save_word_rotation_state,
)
from .categories import DIFFICULTY_LEVELS, format_category_name
from .game_session import GameSession, get_available_word_profiles
from .progression import (
    LOW_RESOURCE_THRESHOLD,
    build_progression_snapshot,
    get_newly_completed_goals,
    get_newly_reached_mastery_states,
)
from .scoring import build_score_breakdown


EXPLORATION_EMPTY_MESSAGE = (
    "La rotation est suivie par profil local. Rechargez ou lancez un profil pour voir quels reglages "
    "sont encore frais."
)
GUIDED_MODE_LABEL = "Session guidee"
REVIEW_MODE_LABEL = "Revision ciblee"
REVIEW_RESOLUTION_LABELS = {
    "resolved": "Faiblesse resorbee",
    "improved": "En progres",
    "still_fragile": "A retravailler",
}


def prepare_player(name, db_path=None):
    kwargs = {"db_path": db_path} if db_path is not None else {}
    return get_or_create_player(name, **kwargs)


def get_progression_bundle(player, category_availability, db_path=None):
    if player is None:
        return None

    kwargs = {"db_path": db_path} if db_path is not None else {}
    dashboard = get_player_dashboard(player["id"], **kwargs)
    if dashboard is None:
        return None

    snapshot = build_progression_snapshot(dashboard["player"], dashboard, category_availability)
    return {
        "player": dashboard["player"],
        "dashboard": dashboard,
        "snapshot": snapshot,
    }


def _find_mastery_cell(snapshot, category, difficulty):
    mastery = (snapshot or {}).get("mastery") or {}
    for cell in mastery.get("cells", ()):
        if not cell.get("available"):
            continue
        if cell.get("category") == category and cell.get("difficulty") == difficulty:
            return cell
    return None


def _find_snapshot_item(snapshot, family, group_name):
    for item in (snapshot or {}).get(group_name, ()):
        if item.get("family") == family:
            return item
    return None


def _format_guided_progress(metric, current_value, target_value):
    current_value = int(current_value or 0)
    target_value = max(0, int(target_value or 0))
    if metric == "score_total":
        return f"{current_value}/{target_value} pts"
    if metric == "recent_wins":
        return f"{min(current_value, target_value)}/{target_value} victoire(s) recentes"
    return f"{min(current_value, target_value)}/{target_value} victoire(s)"


def _build_guided_objective_title(item, family):
    category = item.get("category")
    difficulty = item.get("difficulty")
    if family in {"validation_board", "challenge_pair"} and category and difficulty:
        return f"Valider {format_category_name(category)} en {difficulty}"
    if family == "mastery_board" and category and difficulty:
        return f"Maitriser {format_category_name(category)} en {difficulty}"
    if family == "challenge_recent_form":
        return "Stabiliser la regularite recente"
    if family in {"score_milestone", "challenge_score"}:
        return f"Atteindre {item.get('target_value', 0)} pts"
    return item.get("title")


def _build_guided_objective_detail(item, family):
    category = item.get("category")
    difficulty = item.get("difficulty")
    target_value = int(item.get("target_value") or 0)
    if family in {"validation_board", "challenge_pair"} and category and difficulty:
        return (
            f"Gagnez sur {format_category_name(category)} en {difficulty} "
            "pour valider cette etape de progression."
        )
    if family == "mastery_board" and category and difficulty:
        return (
            f"Montez a {target_value} victoires sur {format_category_name(category)} "
            f"en {difficulty} pour maitriser la paire."
        )
    if family == "challenge_recent_form":
        return (
            f"Enchainez jusqu'a {target_value} victoire(s) sur vos 5 dernieres parties "
            "en gardant une recommandation lisible apres chaque manche."
        )
    if family in {"score_milestone", "challenge_score"}:
        return f"Cumulez le score necessaire avant de couper la session."
    return item.get("detail")


def build_guided_objective(snapshot, *, source="primary_goal"):
    item = (snapshot or {}).get(source)
    if item is None:
        return None

    family = item.get("family")
    category = item.get("category")
    difficulty = item.get("difficulty")
    current_value = int(item.get("current_value") or 0)
    target_value = int(item.get("target_value") or 0)
    metric = None

    if family == "validation_board":
        if not category or not difficulty:
            return None
        metric = "pair_wins"
        target_value = 1
        cell = _find_mastery_cell(snapshot, category, difficulty) or {}
        current_value = int(cell.get("wins") or 0)
    elif family == "mastery_board":
        if not category or not difficulty:
            return None
        metric = "pair_wins"
        cell = _find_mastery_cell(snapshot, category, difficulty) or {}
        current_value = int(cell.get("wins") or 0)
        target_value = 3
    elif family == "challenge_pair":
        if not category or not difficulty:
            return None
        metric = "pair_wins"
        cell = _find_mastery_cell(snapshot, category, difficulty) or {}
        current_value = int(cell.get("wins") or 0)
    elif family == "challenge_recent_form":
        metric = "recent_wins"
    elif family in {"score_milestone", "challenge_score"}:
        metric = "score_total"
    else:
        return None

    return {
        "source": source,
        "source_key": item["key"],
        "source_family": family,
        "source_title": item["title"],
        "title": _build_guided_objective_title(item, family),
        "detail": _build_guided_objective_detail(item, family),
        "metric": metric,
        "category": category,
        "difficulty": difficulty,
        "target_value": target_value,
        "current_value": current_value,
        "progress_text": _format_guided_progress(metric, current_value, target_value),
        "completed": current_value >= target_value if target_value > 0 else False,
    }


def evaluate_guided_objective(objective, player, dashboard, progression_snapshot):
    if objective is None:
        return None

    metric = objective["metric"]
    current_value = 0
    if metric == "pair_wins":
        cell = _find_mastery_cell(
            progression_snapshot,
            objective.get("category"),
            objective.get("difficulty"),
        ) or {}
        current_value = int(cell.get("wins") or 0)
    elif metric == "recent_wins":
        recent_form = (dashboard or {}).get("recent_form") or {}
        current_value = int(recent_form.get("recent_wins") or 0)
    elif metric == "score_total":
        current_value = int((player or {}).get("score_total") or 0)

    target_value = int(objective.get("target_value") or 0)
    progress_text = _format_guided_progress(metric, current_value, target_value)
    remaining = max(0, target_value - current_value)

    return {
        **objective,
        "current_value": current_value,
        "target_value": target_value,
        "progress_text": progress_text,
        "remaining": remaining,
        "completed": current_value >= target_value if target_value > 0 else False,
    }


def build_guided_recommendation(objective, player, dashboard, progression_snapshot):
    progress = evaluate_guided_objective(objective, player, dashboard, progression_snapshot)
    if progress is None or progress["completed"]:
        return None

    category = progress.get("category")
    difficulty = progress.get("difficulty")
    detail = progress["detail"]
    source_item = None

    if progress["metric"] == "recent_wins":
        source_item = _find_snapshot_item(
            progression_snapshot,
            "challenge_recent_form",
            "challenges",
        )
    elif progress["metric"] == "score_total":
        family = "challenge_score" if progress.get("source") == "featured_challenge" else "score_milestone"
        group_name = "challenges" if family == "challenge_score" else "goals"
        source_item = _find_snapshot_item(progression_snapshot, family, group_name)

    if source_item is not None:
        category = source_item.get("category") or category
        difficulty = source_item.get("difficulty") or difficulty

    if category and difficulty:
        selection_text = f"{format_category_name(category)} en {difficulty}"
    else:
        selection_text = "le reglage conseille"

    if progress["metric"] == "pair_wins":
        detail = (
            f"Encore {progress['remaining']} victoire(s) sur {selection_text} "
            "pour boucler cet objectif de session."
        )
    elif progress["metric"] == "recent_wins":
        detail = (
            f"Encore {progress['remaining']} victoire(s) recentes. "
            f"La reco du moment reste {selection_text}."
        )
    elif progress["metric"] == "score_total":
        detail = (
            f"Encore {progress['remaining']} pts. "
            f"Le meilleur levier actuel reste {selection_text}."
        )

    return {
        "category": category,
        "difficulty": difficulty,
        "title": progress["title"],
        "progress_text": progress["progress_text"],
        "detail": detail,
        "remaining": progress["remaining"],
    }


def _review_target_key(category, difficulty, secret_word):
    return (str(category or "").strip(), str(difficulty or "").strip(), str(secret_word or "").strip().upper())


def _build_review_rotation_note():
    return "Revision hors rotation normale : cette manche ne consomme pas le pool standard."


def _build_review_margin_hint(driver):
    threshold = int(round(LOW_RESOURCE_THRESHOLD * 100))
    if driver == "time_pressure":
        return f"objectif = victoire avec plus de {threshold} % de marge temps"
    return f"objectif = victoire avec plus de {threshold} % de marge essais"


def _filter_review_targets_against_catalog(categories, targets):
    playable_targets = []
    for target in targets:
        category = target.get("category")
        difficulty = target.get("difficulty")
        secret_word = str(target.get("secret_word") or "").strip().upper()
        if not category or not difficulty or not secret_word:
            continue
        try:
            available_profiles = get_available_word_profiles(categories, category, difficulty)
        except ValueError:
            continue
        if any(profile.text == secret_word for profile in available_profiles):
            playable_targets.append(
                {
                    "category": category,
                    "difficulty": difficulty,
                    "secret_word": secret_word,
                    "label": target.get("label") or f"{format_category_name(category)} en {difficulty}",
                }
            )
    return tuple(playable_targets)


def _find_next_failed_word_target(review_session):
    played_keys = {
        _review_target_key(
            round_data.get("category"),
            round_data.get("difficulty"),
            round_data.get("secret_word"),
        )
        for round_data in review_session.get("rounds", ())
    }
    for target in review_session.get("targets", ()):
        if _review_target_key(target.get("category"), target.get("difficulty"), target.get("secret_word")) not in played_keys:
            return target
    return None


def _count_cleaned_failed_word_targets(review_session):
    won_keys = {
        _review_target_key(
            round_data.get("category"),
            round_data.get("difficulty"),
            round_data.get("secret_word"),
        )
        for round_data in review_session.get("rounds", ())
        if bool(round_data.get("won"))
    }
    return sum(
        1
        for target in review_session.get("targets", ())
        if _review_target_key(target.get("category"), target.get("difficulty"), target.get("secret_word")) in won_keys
    )


def _count_qualified_weak_pair_rounds(review_session):
    return sum(1 for round_data in review_session.get("rounds", ()) if bool(round_data.get("qualified")))


def build_review_session_state(review_option, categories):
    if review_option is None:
        return None

    kind = review_option.get("kind")
    base_state = {
        "mode_label": REVIEW_MODE_LABEL,
        "rounds": [],
        "status": "active",
        "resolution_status": None,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }

    if kind == "failed_words":
        targets = _filter_review_targets_against_catalog(categories, review_option.get("targets", ()))
        if not targets:
            return None
        review_session = {
            **base_state,
            "session_kind": "review_failed_words",
            "title": review_option["title"],
            "targets": targets,
            "max_rounds": len(targets),
        }
    elif kind == "weak_pair":
        review_session = {
            **base_state,
            "session_kind": "review_weak_pair",
            "title": review_option["title"],
            "driver": review_option["driver"],
            "driver_label": review_option["driver_label"],
            "category": review_option["category"],
            "difficulty": review_option["difficulty"],
            "target_value": int(review_option.get("target_value") or 0),
            "max_rounds": int(review_option.get("max_rounds") or 0),
        }
    else:
        return None

    progress = evaluate_review_session(review_session)
    review_session["objective_state"] = progress
    review_session["initial_progress_text"] = progress["progress_text"]
    review_session["recommendation"] = build_review_recommendation(review_session)
    return review_session


def evaluate_review_session(review_session):
    if review_session is None:
        return None

    session_kind = review_session.get("session_kind")
    rotation_note = _build_review_rotation_note()

    if session_kind == "review_failed_words":
        targets = review_session.get("targets", ())
        total_targets = len(targets)
        rounds = review_session.get("rounds", ())
        cleaned_targets = _count_cleaned_failed_word_targets(review_session)
        played_count = min(len(rounds), total_targets)
        next_target = _find_next_failed_word_target(review_session)
        completed = total_targets > 0 and next_target is None
        resolution_status = None
        if completed:
            if cleaned_targets == total_targets:
                resolution_status = "resolved"
            elif cleaned_targets > 0:
                resolution_status = "improved"
            else:
                resolution_status = "still_fragile"

        if completed and resolution_status == "resolved":
            detail = "Tous les mots cibles ont ete remportes une fois dans cette revision."
        elif completed and resolution_status == "improved":
            detail = "Une partie des mots cibles a ete nettoyee, mais certains resistent encore."
        elif completed:
            detail = "Les mots cibles ont tous ete rejoues, sans victoire sur cette revision."
        elif next_target is not None:
            remaining = total_targets - played_count
            detail = (
                f"Encore {remaining} mot(s) a rejouer. Prochaine manche sur {next_target['label']}. "
                f"{rotation_note}"
            )
        else:
            detail = rotation_note

        return {
            "session_kind": session_kind,
            "mode_label": review_session.get("mode_label", REVIEW_MODE_LABEL),
            "title": review_session.get("title", "Revision ciblee"),
            "progress_text": f"{cleaned_targets}/{total_targets} mot(s) nettoye(s)",
            "detail": detail,
            "completed": completed,
            "resolution_status": resolution_status,
            "resolution_label": REVIEW_RESOLUTION_LABELS.get(resolution_status),
            "rotation_note": rotation_note,
        }

    if session_kind == "review_weak_pair":
        driver = review_session.get("driver")
        driver_label = review_session.get("driver_label", "Diagnostic")
        category = review_session.get("category")
        difficulty = review_session.get("difficulty")
        selection_text = f"{format_category_name(category)} en {difficulty}"
        target_value = max(0, int(review_session.get("target_value") or 0))
        max_rounds = max(0, int(review_session.get("max_rounds") or 0))
        rounds = review_session.get("rounds", ())
        qualified_rounds = _count_qualified_weak_pair_rounds(review_session)
        completed = (
            (target_value > 0 and qualified_rounds >= target_value)
            or (max_rounds > 0 and len(rounds) >= max_rounds)
        )
        resolution_status = None
        if completed:
            if target_value > 0 and qualified_rounds >= target_value:
                resolution_status = "resolved"
            elif qualified_rounds > 0:
                resolution_status = "improved"
            else:
                resolution_status = "still_fragile"

        if completed and resolution_status == "resolved":
            detail = (
                f"{driver_label} ne domine plus cette revision: {target_value} manche(s) qualifiee(s) "
                f"sur {selection_text}."
            )
        elif completed and resolution_status == "improved":
            detail = (
                f"Le reglage progresse sur {selection_text}, mais la marge reste a stabiliser. "
                f"{rotation_note}"
            )
        elif completed:
            detail = f"La paire fragile {selection_text} a ete rejouee sans manche qualifiee. {rotation_note}"
        else:
            needed = max(0, target_value - qualified_rounds)
            rounds_left = max(0, max_rounds - len(rounds))
            detail = (
                f"Encore {needed} manche(s) qualifiee(s) a obtenir sur {selection_text}; "
                f"{rounds_left} manche(s) max restantes, {_build_review_margin_hint(driver)}. "
                f"{rotation_note}"
            )

        return {
            "session_kind": session_kind,
            "mode_label": review_session.get("mode_label", REVIEW_MODE_LABEL),
            "title": review_session.get("title", "Revision ciblee"),
            "progress_text": f"{qualified_rounds}/{target_value} manche(s) qualifiee(s)",
            "detail": detail,
            "completed": completed,
            "resolution_status": resolution_status,
            "resolution_label": REVIEW_RESOLUTION_LABELS.get(resolution_status),
            "rotation_note": rotation_note,
            "driver_label": driver_label,
        }

    return None


def build_review_recommendation(review_session):
    progress = evaluate_review_session(review_session)
    if progress is None or progress.get("completed"):
        return None

    session_kind = review_session.get("session_kind")
    if session_kind == "review_failed_words":
        next_target = _find_next_failed_word_target(review_session)
        if next_target is None:
            return None
        return {
            "category": next_target["category"],
            "difficulty": next_target["difficulty"],
            "title": "Continuer la revision des mots rates",
            "progress_text": progress["progress_text"],
            "detail": (
                f"Prochaine cible issue des defaites recentes sur {next_target['label']}. "
                "Le mot exact reste force hors rotation normale."
            ),
        }

    if session_kind == "review_weak_pair":
        category = review_session.get("category")
        difficulty = review_session.get("difficulty")
        if not category or not difficulty:
            return None
        return {
            "category": category,
            "difficulty": difficulty,
            "title": review_session.get("title", "Travailler mon reglage fragile"),
            "progress_text": progress["progress_text"],
            "detail": (
                f"Reprendre {format_category_name(category)} en {difficulty}; "
                f"{_build_review_margin_hint(review_session.get('driver'))}."
            ),
        }

    return None


def is_review_round_qualified(review_session, session, reason):
    if review_session is None or review_session.get("session_kind") != "review_weak_pair" or reason != "won":
        return False

    driver = review_session.get("driver")
    if driver == "time_pressure":
        if max(0, int(session.time_limit or 0)) <= 0:
            return False
        return (int(session.time_remaining or 0) / int(session.time_limit or 1)) > LOW_RESOURCE_THRESHOLD
    if driver == "error_pressure":
        if max(0, int(session.attempts_limit or 0)) <= 0:
            return False
        return (int(session.attempts_left or 0) / int(session.attempts_limit or 1)) > LOW_RESOURCE_THRESHOLD
    return False


def _build_pool_signature(available_words):
    normalized_words = [str(word).strip().upper() for word in available_words if str(word).strip()]
    return json.dumps(normalized_words, ensure_ascii=True, separators=(",", ":"))


def _normalize_rotation_words(words, available_words):
    available_word_set = set(available_words)
    return [
        str(word).strip().upper()
        for word in words
        if str(word).strip().upper() in available_word_set
    ]


def _build_fresh_cycle(available_words, last_word):
    fresh_cycle = list(available_words)
    normalized_last_word = str(last_word).strip().upper() if last_word else None
    if normalized_last_word in fresh_cycle and len(fresh_cycle) > 1:
        fresh_cycle = [word for word in fresh_cycle if word != normalized_last_word]
    return fresh_cycle


def _resolve_rotation_window(player_id, category, difficulty, available_profiles, db_path=None):
    kwargs = {"db_path": db_path} if db_path is not None else {}
    state = get_word_rotation_state(player_id, category, difficulty, **kwargs)
    available_words = [profile.text for profile in available_profiles]
    current_signature = _build_pool_signature(available_words)
    last_word = state.get("last_word")
    remaining_words = _normalize_rotation_words(state["remaining_words"], available_words)
    state_is_empty = (
        not remaining_words
        and not last_word
        and not int(state.get("window_size") or 0)
        and not state.get("pool_signature")
    )
    catalog_recalibrated = bool(state.get("pool_signature")) and state["pool_signature"] != current_signature
    fresh_cycle = _build_fresh_cycle(available_words, last_word)

    if catalog_recalibrated:
        candidate_words = list(fresh_cycle)
        return {
            "candidate_words": candidate_words,
            "remaining_words": candidate_words,
            "last_word": last_word,
            "window_size": len(candidate_words),
            "fresh_count": len(candidate_words),
            "restart_pending": False,
            "next_window_size": len(candidate_words),
            "catalog_recalibrated": True,
            "pool_signature": current_signature,
        }

    if state_is_empty:
        return {
            "candidate_words": list(fresh_cycle),
            "remaining_words": list(fresh_cycle),
            "last_word": None,
            "window_size": len(fresh_cycle),
            "fresh_count": len(fresh_cycle),
            "restart_pending": False,
            "next_window_size": len(fresh_cycle),
            "catalog_recalibrated": False,
            "pool_signature": current_signature,
        }

    if remaining_words:
        window_size = max(
            int(state.get("window_size") or 0),
            len(remaining_words),
            len(available_words) if not state.get("pool_signature") else 0,
        )
        return {
            "candidate_words": list(remaining_words),
            "remaining_words": list(remaining_words),
            "last_word": last_word,
            "window_size": window_size,
            "fresh_count": len(remaining_words),
            "restart_pending": False,
            "next_window_size": window_size,
            "catalog_recalibrated": False,
            "pool_signature": current_signature,
        }

    next_window_size = len(fresh_cycle)
    window_size = max(
        int(state.get("window_size") or 0),
        len(available_words) if not state.get("pool_signature") else 0,
        next_window_size,
    )
    return {
        "candidate_words": list(fresh_cycle),
        "remaining_words": [],
        "last_word": last_word,
        "window_size": window_size,
        "fresh_count": 0,
        "restart_pending": True,
        "next_window_size": next_window_size,
        "catalog_recalibrated": False,
        "pool_signature": current_signature,
    }


def _build_exploration_state_label(fresh_count, window_size, restart_pending):
    ratio = (fresh_count / window_size) if window_size > 0 else 0.0
    if restart_pending or ratio <= 0.2:
        return "Cycle imminent"
    if ratio >= 0.7:
        return "Pool largement neuf"
    return "Bientot epuise"


def _build_tracked_pair_snapshot(
    category,
    difficulty,
    rotation_window,
    *,
    display_names=None,
):
    fresh_count = int(rotation_window["fresh_count"])
    window_size = max(0, int(rotation_window["window_size"]))
    restart_pending = bool(rotation_window["restart_pending"])
    next_window_size = max(0, int(rotation_window["next_window_size"]))
    ratio = (fresh_count / window_size) if window_size > 0 else 0.0
    state_label = _build_exploration_state_label(fresh_count, window_size, restart_pending)
    progress_text = f"{fresh_count}/{window_size} mot(s) frais" if window_size else "Aucun mot disponible"
    detail = (
        f"{fresh_count} mot(s) encore frais dans cette rotation."
        if not restart_pending
        else f"Rotation terminee, la prochaine manche relancera {next_window_size} mot(s) frais."
    )
    note = "Pool recalibre sur le catalogue actuel." if rotation_window["catalog_recalibrated"] else ""

    return {
        "category": category,
        "difficulty": difficulty,
        "label": f"{format_category_name(category, display_names)} en {difficulty}",
        "state": "imminent" if state_label == "Cycle imminent" else "fresh" if state_label == "Pool largement neuf" else "warning",
        "state_label": state_label,
        "badge_text": state_label,
        "progress_text": progress_text,
        "detail": detail,
        "ratio": max(0.0, min(1.0, ratio)),
        "fresh_count": fresh_count,
        "window_size": window_size,
        "restart_pending": restart_pending,
        "next_window_size": next_window_size,
        "catalog_recalibrated": bool(rotation_window["catalog_recalibrated"]),
        "note": note,
        "tracked": True,
        "available": True,
    }


def _build_profile_required_snapshot(category, difficulty, *, display_names=None):
    return {
        "category": category,
        "difficulty": difficulty,
        "label": f"{format_category_name(category, display_names)} en {difficulty}",
        "state": "profile_required",
        "state_label": "Profil local requis",
        "badge_text": "Profil local requis",
        "progress_text": "Suivi inactif",
        "detail": EXPLORATION_EMPTY_MESSAGE,
        "ratio": 0.0,
        "fresh_count": 0,
        "window_size": 0,
        "restart_pending": False,
        "next_window_size": 0,
        "catalog_recalibrated": False,
        "note": "",
        "tracked": False,
        "available": True,
    }


def _build_unavailable_snapshot(category, difficulty, *, display_names=None):
    return {
        "category": category,
        "difficulty": difficulty,
        "label": f"{format_category_name(category, display_names)} en {difficulty}",
        "state": "unavailable",
        "state_label": "Indisponible",
        "badge_text": "Indisponible",
        "progress_text": "-",
        "detail": "",
        "ratio": 0.0,
        "fresh_count": 0,
        "window_size": 0,
        "restart_pending": False,
        "next_window_size": 0,
        "catalog_recalibrated": False,
        "note": "",
        "tracked": False,
        "available": False,
    }


def build_catalog_exploration_snapshot(
    player_id,
    categories,
    category_availability,
    display_names=None,
    *,
    selected_category=None,
    selected_difficulty=None,
    db_path=None,
):
    pair_states = {}
    for category in categories:
        available_difficulties = category_availability.get(category, ())
        for difficulty in available_difficulties:
            if player_id is None:
                state = _build_profile_required_snapshot(
                    category,
                    difficulty,
                    display_names=display_names,
                )
            else:
                available_profiles = get_available_word_profiles(categories, category, difficulty)
                rotation_window = _resolve_rotation_window(
                    player_id,
                    category,
                    difficulty,
                    available_profiles,
                    db_path=db_path,
                )
                state = _build_tracked_pair_snapshot(
                    category,
                    difficulty,
                    rotation_window,
                    display_names=display_names,
                )
            pair_states[(category, difficulty)] = state

    rows = []
    for category in categories:
        row_cells = []
        available_difficulties = category_availability.get(category, ())
        for difficulty in DIFFICULTY_LEVELS:
            if difficulty in available_difficulties:
                row_cells.append(pair_states[(category, difficulty)])
            else:
                row_cells.append(
                    _build_unavailable_snapshot(
                        category,
                        difficulty,
                        display_names=display_names,
                    )
                )
        rows.append(
            {
                "category": category,
                "label": format_category_name(category, display_names),
                "cells": tuple(row_cells),
            }
        )

    if selected_category is None or selected_category not in categories:
        selected_category = next(iter(categories), None)
    selected_available_difficulties = category_availability.get(selected_category, ())
    if selected_difficulty not in selected_available_difficulties:
        selected_difficulty = selected_available_difficulties[0] if selected_available_difficulties else None

    selected_state = None
    if selected_category is not None and selected_difficulty is not None:
        selected_state = pair_states.get((selected_category, selected_difficulty))

    return {
        "tracked": player_id is not None,
        "empty_message": EXPLORATION_EMPTY_MESSAGE,
        "selected_state": selected_state,
        "grid": {
            "rows": tuple(rows),
            "tracked": player_id is not None,
        },
    }


def create_session_for_player(
    player_id,
    categories,
    category,
    difficulty,
    *,
    rng=None,
    db_path=None,
):
    available_profiles = get_available_word_profiles(categories, category, difficulty)
    rotation_window = _resolve_rotation_window(
        player_id,
        category,
        difficulty,
        available_profiles,
        db_path=db_path,
    )
    candidate_words = rotation_window["candidate_words"]
    session = GameSession.create(
        categories,
        category,
        difficulty,
        rng=rng,
        allowed_words=candidate_words,
    )

    remaining_words = [word for word in candidate_words if word != session.secret_word]
    kwargs = {"db_path": db_path} if db_path is not None else {}
    save_word_rotation_state(
        player_id,
        category,
        difficulty,
        remaining_words,
        last_word=session.secret_word,
        window_size=rotation_window["window_size"],
        pool_signature=rotation_window["pool_signature"],
        **kwargs,
    )
    return session


def create_review_session(review_session, categories, *, rng=None):
    if review_session is None:
        raise ValueError("Aucune session de revision n'est disponible.")

    session_kind = review_session.get("session_kind")
    if session_kind == "review_failed_words":
        target = _find_next_failed_word_target(review_session)
        if target is None:
            raise ValueError("Tous les mots de revision ont deja ete joues.")

        available_profiles = get_available_word_profiles(
            categories,
            target["category"],
            target["difficulty"],
        )
        if not any(profile.text == target["secret_word"] for profile in available_profiles):
            raise ValueError("Le mot de revision cible n'est plus disponible dans le catalogue actif.")

        return GameSession.create(
            categories,
            target["category"],
            target["difficulty"],
            rng=rng,
            allowed_words=[target["secret_word"]],
        )

    if session_kind == "review_weak_pair":
        category = review_session.get("category")
        difficulty = review_session.get("difficulty")
        recent_words = [
            round_data.get("secret_word")
            for round_data in review_session.get("rounds", ())
            if round_data.get("secret_word")
        ]
        return GameSession.create(
            categories,
            category,
            difficulty,
            rng=rng,
            recent_words=recent_words,
        )

    raise ValueError("Type de session de revision inconnu.")


def resolve_round(player, session, reason, category_availability, db_path=None):
    kwargs = {"db_path": db_path} if db_path is not None else {}
    before_bundle = get_progression_bundle(player, category_availability, db_path=db_path)
    before_snapshot = before_bundle["snapshot"] if before_bundle is not None else None

    won = reason == "won"
    score_earned = 0
    score_summary = "Aucun point gagne sur cette manche."
    breakdown = None

    if won:
        breakdown = build_score_breakdown(
            session.difficulty,
            session.word_profile.length,
            session.attempts_left,
            session.time_remaining,
            word_complexity=session.word_complexity,
            time_limit=session.time_limit,
        )
        score_earned = breakdown["total"]
        score_summary = (
            f"{score_earned} pts : base {breakdown['base_points']}, "
            f"mot {breakdown['word_bonus']}, complexite {breakdown['complexity_bonus']}, "
            f"essais {breakdown['attempts_bonus']}, temps {breakdown['time_bonus']}."
        )

    updated_player = record_game_result(
        player["id"],
        won=won,
        score_earned=score_earned,
        category=session.category,
        difficulty=session.difficulty,
        secret_word=session.secret_word,
        end_reason=reason,
        attempts_left=session.attempts_left,
        time_remaining=session.time_remaining,
        attempts_limit=session.attempts_limit,
        time_limit=session.time_limit,
        word_complexity=session.word_complexity,
        **kwargs,
    )

    after_bundle = get_progression_bundle(updated_player, category_availability, db_path=db_path)
    after_snapshot = after_bundle["snapshot"] if after_bundle is not None else None
    completed_goals = get_newly_completed_goals(before_snapshot, after_snapshot)
    mastery_updates = get_newly_reached_mastery_states(before_snapshot, after_snapshot)

    if reason == "won":
        title = "Victoire"
        result_message = f"Vous avez trouve le mot : {session.secret_word}."
    elif reason == "time":
        title = "Temps ecoule"
        result_message = f"Le temps est termine. Le mot etait : {session.secret_word}."
    else:
        title = "Partie perdue"
        result_message = f"Vous n'avez plus d'essais. Le mot etait : {session.secret_word}."

    return {
        "player": after_bundle["player"] if after_bundle is not None else updated_player,
        "dashboard": after_bundle["dashboard"] if after_bundle is not None else None,
        "progression_snapshot": after_snapshot,
        "completed_goals": completed_goals,
        "mastery_updates": mastery_updates,
        "score_earned": score_earned,
        "score_summary": score_summary,
        "breakdown": breakdown,
        "title": title,
        "result_message": result_message,
    }

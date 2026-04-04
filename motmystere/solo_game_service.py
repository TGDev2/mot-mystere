from .database import (
    get_or_create_player,
    get_player_dashboard,
    get_word_rotation_state,
    record_game_result,
    save_word_rotation_state,
)
from .categories import format_category_name
from .game_session import GameSession, get_available_word_profiles
from .progression import (
    build_progression_snapshot,
    get_newly_completed_goals,
    get_newly_reached_mastery_states,
)
from .scoring import build_score_breakdown


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


def _build_rotation_candidates(player_id, category, difficulty, available_profiles, db_path=None):
    kwargs = {"db_path": db_path} if db_path is not None else {}
    state = get_word_rotation_state(player_id, category, difficulty, **kwargs)
    available_words = [profile.text for profile in available_profiles]
    available_word_set = set(available_words)
    remaining_words = [
        word
        for word in state["remaining_words"]
        if word in available_word_set
    ]

    if remaining_words:
        return remaining_words

    fresh_cycle = list(available_words)
    if state.get("last_word") in fresh_cycle and len(fresh_cycle) > 1:
        fresh_cycle = [word for word in fresh_cycle if word != state["last_word"]]
    return fresh_cycle


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
    candidate_words = _build_rotation_candidates(
        player_id,
        category,
        difficulty,
        available_profiles,
        db_path=db_path,
    )
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
        **kwargs,
    )
    return session


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

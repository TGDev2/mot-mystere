from database import (
    get_or_create_player,
    get_player_dashboard,
    get_word_rotation_state,
    record_game_result,
    save_word_rotation_state,
)
from game_session import GameSession, get_available_word_profiles
from progression import (
    build_progression_snapshot,
    get_newly_completed_goals,
    get_newly_reached_mastery_states,
)
from scoring import build_score_breakdown


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

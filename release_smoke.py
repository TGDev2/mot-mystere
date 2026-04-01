from pathlib import Path

from categories import load_categories
from database import (
    DEFAULT_DB_PATH,
    get_leaderboard_data,
    get_or_create_player,
    get_player_dashboard,
    record_game_result,
    setup_database,
)
from game_session import GameSession
from scoring import build_score_breakdown


class FixedChoice:
    def choice(self, values):
        return values[0]


def _play_winning_round(session):
    for letter in sorted({char for char in session.secret_word if char.isalpha()}):
        session.guess(letter)

    if session.status != "won":
        raise RuntimeError("Le smoke test n'a pas reussi a gagner une manche.")

    return build_score_breakdown(
        session.difficulty,
        session.word_profile.length,
        session.attempts_left,
        session.time_remaining,
        word_complexity=session.word_complexity,
        time_limit=session.time_limit,
    )["total"]


def _play_losing_round(session):
    for letter in "ZXQWVBNMP":
        if letter in session.secret_word:
            continue
        session.guess(letter)
        if session.status == "lost":
            break

    if session.status != "lost":
        raise RuntimeError("Le smoke test n'a pas reussi a perdre une manche.")


def run_release_smoke_test(db_path=DEFAULT_DB_PATH):
    db_path = Path(db_path)
    setup_database(db_path)
    if not db_path.exists():
        raise RuntimeError("La base locale n'a pas ete creee pendant le smoke test.")

    categories = load_categories()
    if not categories:
        raise RuntimeError("Aucune categorie n'est disponible pour le smoke test.")

    category = sorted(categories)[0]
    player = get_or_create_player("Smoke Tester", db_path=db_path)

    winning_session = GameSession.create(categories, category, "Facile", rng=FixedChoice())
    winning_score = _play_winning_round(winning_session)
    record_game_result(
        player["id"],
        won=True,
        score_earned=winning_score,
        category=winning_session.category,
        difficulty=winning_session.difficulty,
        secret_word=winning_session.secret_word,
        end_reason="won",
        attempts_left=winning_session.attempts_left,
        time_remaining=winning_session.time_remaining,
        word_complexity=winning_session.word_complexity,
        db_path=db_path,
    )

    losing_session = GameSession.create(categories, category, "Difficile", rng=FixedChoice())
    _play_losing_round(losing_session)
    updated_player = record_game_result(
        player["id"],
        won=False,
        score_earned=0,
        category=losing_session.category,
        difficulty=losing_session.difficulty,
        secret_word=losing_session.secret_word,
        end_reason="attempts",
        attempts_left=losing_session.attempts_left,
        time_remaining=losing_session.time_remaining,
        word_complexity=losing_session.word_complexity,
        db_path=db_path,
    )

    dashboard = get_player_dashboard(player["id"], db_path=db_path)
    leaderboard = get_leaderboard_data(db_path=db_path)

    if dashboard is None:
        raise RuntimeError("Le profil joueur est introuvable apres le smoke test.")
    if dashboard["overview"]["games_recorded"] < 2:
        raise RuntimeError("Le smoke test n'a pas enregistre les manches attendues.")
    if len(dashboard["recent_games"]) < 2:
        raise RuntimeError("L'historique recent n'a pas ete alimente.")
    if not leaderboard or leaderboard[0]["id"] != updated_player["id"]:
        raise RuntimeError("Le classement n'a pas ete mis a jour correctement.")

    return {
        "player_name": updated_player["name"],
        "games_played": updated_player["games_played"],
        "score_total": updated_player["score_total"],
        "leaderboard_size": len(leaderboard),
        "database_path": str(db_path),
    }


if __name__ == "__main__":
    result = run_release_smoke_test()
    print(
        "Smoke test OK - "
        f"{result['games_played']} parties, "
        f"{result['score_total']} pts, "
        f"db={result['database_path']}"
    )

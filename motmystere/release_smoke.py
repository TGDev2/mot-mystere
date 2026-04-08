import os
from pathlib import Path

from .app_paths import get_database_path
from .catalog_service import CatalogService
from .database import (
    get_leaderboard_data,
    get_player_dashboard,
    setup_database,
)
from .solo_game_service import create_session_for_player, prepare_player, resolve_round


class FixedChoice:
    def choice(self, values):
        return values[0]


def get_default_smoke_db_path():
    if os.environ.get("MOTMYSTERE_DB_PATH") or os.environ.get("MOTMYSTERE_DATA_DIR"):
        return Path(get_database_path())
    return Path(__file__).resolve().parents[1] / ".tmp" / "smoke" / "motmystere_smoke_runtime.db"


def _play_winning_round(session):
    for letter in sorted({char for char in session.secret_word if char.isalpha()}):
        session.guess(letter)

    if session.status != "won":
        raise RuntimeError("Le smoke test n'a pas reussi a gagner une manche.")


def _play_losing_round(session):
    for letter in "ZXQWVBNMP":
        if letter in session.secret_word:
            continue
        session.guess(letter)
        if session.status == "lost":
            break

    if session.status != "lost":
        raise RuntimeError("Le smoke test n'a pas reussi a perdre une manche.")


def run_release_smoke_test(db_path=None):
    db_path = Path(db_path or get_default_smoke_db_path())
    if db_path.exists():
        db_path.unlink()
    setup_database(db_path)
    if not db_path.exists():
        raise RuntimeError("La base locale n'a pas ete creee pendant le smoke test.")

    runtime_dir = db_path.parent
    catalog_service = CatalogService(
        pack_dir=runtime_dir / "packs",
        state_path=runtime_dir / "catalog_state.json",
    )
    official_packs = catalog_service.list_official_packs()
    if not official_packs:
        raise RuntimeError("Aucun pack officiel n'est disponible pour le smoke test.")

    imported_catalog, imported_pack = catalog_service.import_pack_from_source(
        official_packs[0].archive_path,
        enabled=True,
    )
    imported_categories = [
        category.category_key
        for category in imported_pack.categories
        if category.status == "active"
    ]
    if not imported_categories:
        raise RuntimeError("Le smoke test n'a pas reussi a charger de categorie issue d'un pack officiel.")

    categories = dict(imported_catalog.categories)
    category_availability = dict(imported_catalog.category_availability)
    category = imported_categories[0]
    player = prepare_player("Smoke Tester", db_path=db_path)

    winning_session = create_session_for_player(
        player["id"],
        categories,
        category,
        "Facile",
        rng=FixedChoice(),
        db_path=db_path,
    )
    _play_winning_round(winning_session)
    winning_outcome = resolve_round(
        player,
        winning_session,
        "won",
        category_availability,
        db_path=db_path,
    )
    player = winning_outcome["player"]

    losing_session = create_session_for_player(
        player["id"],
        categories,
        category,
        "Difficile",
        rng=FixedChoice(),
        db_path=db_path,
    )
    _play_losing_round(losing_session)
    losing_outcome = resolve_round(
        player,
        losing_session,
        "attempts",
        category_availability,
        db_path=db_path,
    )
    updated_player = losing_outcome["player"]

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
        "imported_pack_id": imported_pack.pack_id,
        "played_category": category,
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

from contextlib import closing
from pathlib import Path
import sqlite3


DEFAULT_DB_PATH = Path(__file__).with_name("hangman.db")


def normalize_player_name(name):
    normalized = " ".join(str(name).split())
    if not normalized:
        raise ValueError("Le pseudo ne peut pas être vide.")
    return normalized[:24]


def _connect(db_path=DEFAULT_DB_PATH):
    database_path = Path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(database_path))
    conn.row_factory = sqlite3.Row
    return conn


def setup_database(db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                games_played INTEGER NOT NULL DEFAULT 0,
                games_won INTEGER NOT NULL DEFAULT 0,
                games_lost INTEGER NOT NULL DEFAULT 0,
                score_total INTEGER NOT NULL DEFAULT 0,
                best_score INTEGER NOT NULL DEFAULT 0,
                last_score INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        _migrate_legacy_stats(cursor)
        conn.commit()


def _migrate_legacy_stats(cursor):
    legacy_table = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'stats'"
    ).fetchone()
    player_count = cursor.execute("SELECT COUNT(*) FROM players").fetchone()[0]

    if not legacy_table or player_count > 0:
        return

    rows = cursor.execute(
        "SELECT name, games_played, games_won, games_lost, score FROM stats"
    ).fetchall()

    aggregated = {}
    for row in rows:
        raw_name = row["name"] if row["name"] is not None else ""
        cleaned_name = " ".join(str(raw_name).split())
        if not cleaned_name:
            continue

        key = cleaned_name.casefold()
        if key not in aggregated:
            aggregated[key] = {
                "name": cleaned_name[:24],
                "games_played": 0,
                "games_won": 0,
                "games_lost": 0,
                "score_total": 0,
                "best_score": 0,
                "last_score": 0,
            }

        player = aggregated[key]
        games_played = int(row["games_played"] or 0)
        games_won = int(row["games_won"] or 0)
        games_lost = int(row["games_lost"] or 0)
        score = int(row["score"] or 0)

        player["games_played"] += games_played
        player["games_won"] += games_won
        player["games_lost"] += games_lost
        player["score_total"] += score
        player["best_score"] = max(player["best_score"], score)
        player["last_score"] = max(player["last_score"], score)

    for player in aggregated.values():
        cursor.execute(
            """
            INSERT INTO players (
                name, games_played, games_won, games_lost,
                score_total, best_score, last_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player["name"],
                player["games_played"],
                player["games_won"],
                player["games_lost"],
                player["score_total"],
                player["best_score"],
                player["last_score"],
            ),
        )


def _row_to_player(row):
    if row is None:
        return None

    player = dict(row)
    player["win_rate"] = get_win_rate(player)
    return player


def get_or_create_player(name, db_path=DEFAULT_DB_PATH):
    normalized_name = normalize_player_name(name)
    with closing(_connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO players (name) VALUES (?)", (normalized_name,))
        row = cursor.execute(
            "SELECT * FROM players WHERE name = ? COLLATE NOCASE",
            (normalized_name,),
        ).fetchone()
        conn.commit()
    return _row_to_player(row)


def get_player(player_id, db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn:
        row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    return _row_to_player(row)


def record_game_result(player_id, won, score_earned, db_path=DEFAULT_DB_PATH):
    score_earned = max(0, int(score_earned))
    wins = 1 if won else 0
    losses = 0 if won else 1

    with closing(_connect(db_path)) as conn:
        conn.execute(
            """
            UPDATE players
            SET games_played = games_played + 1,
                games_won = games_won + ?,
                games_lost = games_lost + ?,
                score_total = score_total + ?,
                best_score = CASE
                    WHEN ? > best_score THEN ?
                    ELSE best_score
                END,
                last_score = ?
            WHERE id = ?
            """,
            (wins, losses, score_earned, score_earned, score_earned, score_earned, player_id),
        )
        conn.commit()

    return get_player(player_id, db_path=db_path)


def get_win_rate(player):
    games_played = int(player["games_played"] or 0)
    if games_played == 0:
        return 0.0
    return round((int(player["games_won"]) / games_played) * 100, 1)


def get_leaderboard_data(limit=10, db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                games_played,
                games_won,
                games_lost,
                score_total,
                best_score,
                last_score
            FROM players
            WHERE name <> ''
            ORDER BY score_total DESC, best_score DESC, games_won DESC, name ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_row_to_player(row) for row in rows]

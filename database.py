from contextlib import closing
from pathlib import Path
import sqlite3

from app_paths import get_database_path


DEFAULT_DB_PATH = get_database_path()


def normalize_player_name(name):
    normalized = " ".join(str(name).split())
    if not normalized:
        raise ValueError("Le pseudo ne peut pas etre vide.")
    return normalized[:24]


def _connect(db_path=DEFAULT_DB_PATH):
    database_path = Path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(database_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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

            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                secret_word TEXT NOT NULL,
                won INTEGER NOT NULL,
                end_reason TEXT NOT NULL,
                attempts_left INTEGER NOT NULL DEFAULT 0,
                time_remaining INTEGER NOT NULL DEFAULT 0,
                word_complexity INTEGER NOT NULL DEFAULT 0,
                score_earned INTEGER NOT NULL DEFAULT 0,
                played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_game_history_player_id
            ON game_history (player_id, id DESC);
            """
        )
        _ensure_game_history_columns(cursor)
        _migrate_legacy_stats(cursor)
        conn.commit()


def _ensure_game_history_columns(cursor):
    existing_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(game_history)").fetchall()
    }
    if not existing_columns:
        return

    required_columns = {
        "attempts_left": "INTEGER NOT NULL DEFAULT 0",
        "time_remaining": "INTEGER NOT NULL DEFAULT 0",
        "word_complexity": "INTEGER NOT NULL DEFAULT 0",
        "score_earned": "INTEGER NOT NULL DEFAULT 0",
        "played_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, definition in required_columns.items():
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE game_history ADD COLUMN {column_name} {definition}")


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


def _row_to_history(row):
    if row is None:
        return None

    history = dict(row)
    history["won"] = bool(history["won"])
    return history


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


def record_game_result(
    player_id,
    won,
    score_earned,
    *,
    category=None,
    difficulty=None,
    secret_word=None,
    end_reason=None,
    attempts_left=None,
    time_remaining=None,
    word_complexity=None,
    db_path=DEFAULT_DB_PATH,
):
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

        metadata = (
            category,
            difficulty,
            secret_word,
            end_reason,
            attempts_left,
            time_remaining,
        )
        if all(value is not None for value in metadata):
            conn.execute(
                """
                INSERT INTO game_history (
                    player_id,
                    category,
                    difficulty,
                    secret_word,
                    won,
                    end_reason,
                    attempts_left,
                    time_remaining,
                    word_complexity,
                    score_earned
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    player_id,
                    str(category),
                    str(difficulty),
                    str(secret_word),
                    wins,
                    str(end_reason),
                    max(0, int(attempts_left)),
                    max(0, int(time_remaining)),
                    max(0, int(word_complexity or 0)),
                    score_earned,
                ),
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


def get_recent_games(player_id, limit=8, db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                category,
                difficulty,
                secret_word,
                won,
                end_reason,
                attempts_left,
                time_remaining,
                word_complexity,
                score_earned,
                played_at
            FROM game_history
            WHERE player_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (player_id, limit),
        ).fetchall()

    return [_row_to_history(row) for row in rows]


def get_player_dashboard(player_id, db_path=DEFAULT_DB_PATH):
    player = get_player(player_id, db_path=db_path)
    if player is None:
        return None

    with closing(_connect(db_path)) as conn:
        overview = conn.execute(
            """
            SELECT
                COUNT(*) AS games_recorded,
                COALESCE(ROUND(AVG(score_earned), 1), 0) AS average_score,
                COALESCE(MAX(score_earned), 0) AS peak_round_score
            FROM game_history
            WHERE player_id = ?
            """,
            (player_id,),
        ).fetchone()
        recent_form = conn.execute(
            """
            SELECT
                COUNT(*) AS recent_games,
                COALESCE(SUM(won), 0) AS recent_wins
            FROM (
                SELECT won
                FROM game_history
                WHERE player_id = ?
                ORDER BY id DESC
                LIMIT 5
            )
            """,
            (player_id,),
        ).fetchone()
        best_difficulty = conn.execute(
            """
            SELECT
                difficulty,
                COUNT(*) AS games_played,
                ROUND(AVG(score_earned), 1) AS average_score,
                ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_rate
            FROM game_history
            WHERE player_id = ?
            GROUP BY difficulty
            ORDER BY average_score DESC, win_rate DESC, games_played DESC, difficulty ASC
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()
        favorite_category = conn.execute(
            """
            SELECT
                category,
                COUNT(*) AS games_played,
                ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_rate
            FROM game_history
            WHERE player_id = ?
            GROUP BY category
            ORDER BY games_played DESC, win_rate DESC, category ASC
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()
        weakest_category = conn.execute(
            """
            SELECT
                category,
                COUNT(*) AS games_played,
                COALESCE(SUM(won), 0) AS wins,
                ROUND(AVG(score_earned), 1) AS average_score,
                ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_rate
            FROM game_history
            WHERE player_id = ?
            GROUP BY category
            ORDER BY win_rate ASC, games_played DESC, average_score ASC, category ASC
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()
        category_stats = conn.execute(
            """
            SELECT
                category,
                COUNT(*) AS games_played,
                COALESCE(SUM(won), 0) AS wins,
                ROUND(AVG(score_earned), 1) AS average_score,
                ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_rate
            FROM game_history
            WHERE player_id = ?
            GROUP BY category
            ORDER BY games_played DESC, wins DESC, category ASC
            """,
            (player_id,),
        ).fetchall()
        difficulty_stats = conn.execute(
            """
            SELECT
                difficulty,
                COUNT(*) AS games_played,
                COALESCE(SUM(won), 0) AS wins,
                ROUND(AVG(score_earned), 1) AS average_score,
                ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_rate
            FROM game_history
            WHERE player_id = ?
            GROUP BY difficulty
            ORDER BY games_played DESC, wins DESC, difficulty ASC
            """,
            (player_id,),
        ).fetchall()

    return {
        "player": player,
        "overview": dict(overview),
        "recent_form": dict(recent_form),
        "best_difficulty": dict(best_difficulty) if best_difficulty else None,
        "favorite_category": dict(favorite_category) if favorite_category else None,
        "weakest_category": dict(weakest_category) if weakest_category else None,
        "category_stats": [dict(row) for row in category_stats],
        "difficulty_stats": [dict(row) for row in difficulty_stats],
        "recent_games": get_recent_games(player_id, db_path=db_path),
    }

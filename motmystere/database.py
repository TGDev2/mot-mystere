from contextlib import closing
import json
from pathlib import Path
import sqlite3

from .app_paths import get_database_path
from .scoring import get_attempts_for_difficulty, get_time_limit_for_difficulty


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
                attempts_limit INTEGER NOT NULL DEFAULT 0,
                time_limit INTEGER NOT NULL DEFAULT 0,
                word_complexity INTEGER NOT NULL DEFAULT 0,
                score_earned INTEGER NOT NULL DEFAULT 0,
                played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_game_history_player_id
            ON game_history (player_id, id DESC);

            CREATE TABLE IF NOT EXISTS word_rotation (
                player_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                remaining_words TEXT NOT NULL DEFAULT '[]',
                last_word TEXT,
                window_size INTEGER NOT NULL DEFAULT 0,
                pool_signature TEXT,
                PRIMARY KEY (player_id, category, difficulty),
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );
            """
        )
        _ensure_game_history_columns(cursor)
        _backfill_game_history_limits(cursor)
        _ensure_word_rotation_columns(cursor)
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
        "attempts_limit": "INTEGER NOT NULL DEFAULT 0",
        "time_limit": "INTEGER NOT NULL DEFAULT 0",
        "word_complexity": "INTEGER NOT NULL DEFAULT 0",
        "score_earned": "INTEGER NOT NULL DEFAULT 0",
        "played_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, definition in required_columns.items():
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE game_history ADD COLUMN {column_name} {definition}")


def _backfill_game_history_limits(cursor):
    existing_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(game_history)").fetchall()
    }
    if not existing_columns or "difficulty" not in existing_columns:
        return

    for difficulty in ("Facile", "Moyen", "Difficile"):
        cursor.execute(
            """
            UPDATE game_history
            SET attempts_limit = ?
            WHERE difficulty = ? AND COALESCE(attempts_limit, 0) <= 0
            """,
            (get_attempts_for_difficulty(difficulty), difficulty),
        )
        cursor.execute(
            """
            UPDATE game_history
            SET time_limit = ?
            WHERE difficulty = ? AND COALESCE(time_limit, 0) <= 0
            """,
            (get_time_limit_for_difficulty(difficulty), difficulty),
        )


def _ensure_word_rotation_columns(cursor):
    existing_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(word_rotation)").fetchall()
    }
    if not existing_columns:
        return

    required_columns = {
        "window_size": "INTEGER NOT NULL DEFAULT 0",
        "pool_signature": "TEXT",
    }

    for column_name, definition in required_columns.items():
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE word_rotation ADD COLUMN {column_name} {definition}")


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


def _row_to_recent_player(row):
    player = _row_to_player(row)
    if player is None:
        return None

    player.update(
        {
            "last_played_at": row["last_played_at"],
            "last_category": row["last_category"],
            "last_difficulty": row["last_difficulty"],
            "last_won": bool(row["last_won"]) if row["last_won"] is not None else None,
            "last_round_score": int(row["last_round_score"] or 0),
        }
    )
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


def _resolve_attempt_limit(difficulty, attempts_limit):
    if attempts_limit is not None:
        return max(0, int(attempts_limit))
    try:
        return get_attempts_for_difficulty(difficulty)
    except (TypeError, ValueError):
        return 0


def _resolve_time_limit(difficulty, time_limit):
    if time_limit is not None:
        return max(0, int(time_limit))
    try:
        return get_time_limit_for_difficulty(difficulty)
    except (TypeError, ValueError):
        return 0


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
    attempts_limit=None,
    time_limit=None,
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
                    attempts_limit,
                    time_limit,
                    word_complexity,
                    score_earned
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    _resolve_attempt_limit(difficulty, attempts_limit),
                    _resolve_time_limit(difficulty, time_limit),
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


def get_recent_players(limit=6, db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.name,
                p.games_played,
                p.games_won,
                p.games_lost,
                p.score_total,
                p.best_score,
                p.last_score,
                latest.played_at AS last_played_at,
                latest.category AS last_category,
                latest.difficulty AS last_difficulty,
                latest.won AS last_won,
                latest.score_earned AS last_round_score
            FROM players p
            LEFT JOIN (
                SELECT
                    gh.player_id,
                    gh.played_at,
                    gh.category,
                    gh.difficulty,
                    gh.won,
                    gh.score_earned
                FROM game_history gh
                INNER JOIN (
                    SELECT player_id, MAX(id) AS latest_game_id
                    FROM game_history
                    GROUP BY player_id
                ) latest_ids
                    ON latest_ids.player_id = gh.player_id
                    AND latest_ids.latest_game_id = gh.id
            ) latest
                ON latest.player_id = p.id
            WHERE p.name <> ''
            ORDER BY
                CASE WHEN latest.played_at IS NULL THEN 1 ELSE 0 END,
                latest.played_at DESC,
                p.games_played DESC,
                p.score_total DESC,
                p.name ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_row_to_recent_player(row) for row in rows]


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


def get_word_rotation_state(player_id, category, difficulty, db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            """
            SELECT remaining_words, last_word, window_size, pool_signature
            FROM word_rotation
            WHERE player_id = ? AND category = ? AND difficulty = ?
            """,
            (player_id, str(category), str(difficulty)),
        ).fetchone()

    if row is None:
        return {
            "remaining_words": [],
            "last_word": None,
            "window_size": 0,
            "pool_signature": None,
        }

    try:
        remaining_words = json.loads(row["remaining_words"] or "[]")
    except json.JSONDecodeError:
        remaining_words = []

    return {
        "remaining_words": [str(word).strip().upper() for word in remaining_words if str(word).strip()],
        "last_word": str(row["last_word"]).strip().upper() if row["last_word"] else None,
        "window_size": max(0, int(row["window_size"] or 0)),
        "pool_signature": str(row["pool_signature"]).strip() if row["pool_signature"] else None,
    }


def save_word_rotation_state(
    player_id,
    category,
    difficulty,
    remaining_words,
    *,
    last_word=None,
    window_size=0,
    pool_signature=None,
    db_path=DEFAULT_DB_PATH,
):
    normalized_words = [
        str(word).strip().upper()
        for word in remaining_words
        if str(word).strip()
    ]
    normalized_last_word = str(last_word).strip().upper() if last_word else None
    normalized_window_size = max(0, int(window_size or 0))
    normalized_pool_signature = str(pool_signature).strip() if pool_signature else None

    with closing(_connect(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO word_rotation (
                player_id, category, difficulty, remaining_words, last_word, window_size, pool_signature
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, category, difficulty)
            DO UPDATE SET
                remaining_words = excluded.remaining_words,
                last_word = excluded.last_word,
                window_size = excluded.window_size,
                pool_signature = excluded.pool_signature
            """,
            (
                player_id,
                str(category),
                str(difficulty),
                json.dumps(normalized_words),
                normalized_last_word,
                normalized_window_size,
                normalized_pool_signature,
            ),
        )
        conn.commit()


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
        selection_stats = conn.execute(
            """
            SELECT
                category,
                difficulty,
                COUNT(*) AS games_played,
                COALESCE(SUM(won), 0) AS wins,
                ROUND(AVG(score_earned), 1) AS average_score,
                ROUND(SUM(won) * 100.0 / COUNT(*), 1) AS win_rate
            FROM game_history
            WHERE player_id = ?
            GROUP BY category, difficulty
            ORDER BY category ASC, difficulty ASC
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
        "selection_stats": [dict(row) for row in selection_stats],
        "recent_games": get_recent_games(player_id, db_path=db_path),
    }


def get_difficulty_calibration_rows(active_pairs, db_path=DEFAULT_DB_PATH):
    normalized_pairs = []
    seen_pairs = set()
    for category, difficulty in active_pairs:
        normalized_pair = (str(category).strip(), str(difficulty).strip())
        if not normalized_pair[0] or not normalized_pair[1] or normalized_pair in seen_pairs:
            continue
        seen_pairs.add(normalized_pair)
        normalized_pairs.append(normalized_pair)

    if not normalized_pairs:
        return []

    pair_placeholders = ", ".join("(?, ?)" for _ in normalized_pairs)
    params = [item for pair in normalized_pairs for item in pair]
    query = f"""
        WITH active_pairs(category, difficulty) AS (
            VALUES {pair_placeholders}
        ),
        pair_games AS (
            SELECT gh.*
            FROM game_history gh
            INNER JOIN active_pairs ap
                ON ap.category = gh.category
                AND ap.difficulty = gh.difficulty
        ),
        pair_player_counts AS (
            SELECT
                category,
                difficulty,
                player_id,
                COUNT(*) AS player_games
            FROM pair_games
            GROUP BY category, difficulty, player_id
        ),
        dominant_counts AS (
            SELECT
                category,
                difficulty,
                MAX(player_games) AS dominant_player_games
            FROM pair_player_counts
            GROUP BY category, difficulty
        )
        SELECT
            ap.category,
            ap.difficulty,
            COUNT(pg.id) AS games_played,
            COALESCE(SUM(pg.won), 0) AS wins,
            COUNT(DISTINCT pg.player_id) AS distinct_players,
            COALESCE(
                ROUND(MAX(dc.dominant_player_games) * 1.0 / NULLIF(COUNT(pg.id), 0), 4),
                0.0
            ) AS dominant_player_share,
            COALESCE(
                ROUND(AVG(CASE WHEN pg.end_reason = 'time' THEN 1.0 ELSE 0.0 END), 4),
                0.0
            ) AS timeout_rate,
            COALESCE(
                ROUND(AVG(CASE WHEN pg.end_reason = 'attempts' THEN 1.0 ELSE 0.0 END), 4),
                0.0
            ) AS attempt_fail_rate,
            ROUND(
                AVG(
                    CASE
                        WHEN pg.won = 1 AND COALESCE(pg.time_limit, 0) > 0
                            THEN pg.time_remaining * 1.0 / pg.time_limit
                        ELSE NULL
                    END
                ),
                4
            ) AS avg_time_margin_on_wins,
            ROUND(
                AVG(
                    CASE
                        WHEN pg.won = 1 AND COALESCE(pg.attempts_limit, 0) > 0
                            THEN pg.attempts_left * 1.0 / pg.attempts_limit
                        ELSE NULL
                    END
                ),
                4
            ) AS avg_attempt_margin_on_wins,
            COALESCE(ROUND(AVG(pg.score_earned), 1), 0.0) AS avg_score,
            COALESCE(ROUND(AVG(pg.word_complexity), 1), 0.0) AS avg_complexity,
            MAX(pg.played_at) AS last_played_at
        FROM active_pairs ap
        LEFT JOIN pair_games pg
            ON pg.category = ap.category
            AND pg.difficulty = ap.difficulty
        LEFT JOIN dominant_counts dc
            ON dc.category = ap.category
            AND dc.difficulty = ap.difficulty
        GROUP BY ap.category, ap.difficulty
        ORDER BY ap.category ASC, ap.difficulty ASC
    """

    with closing(_connect(db_path)) as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]

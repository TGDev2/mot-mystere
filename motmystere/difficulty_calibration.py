from .categories import CATEGORY_KEY_SEPARATOR, CORE_PACK_ID, DIFFICULTY_LEVELS, format_category_name
from .database import get_difficulty_calibration_rows


TARGET_WIN_RATE_BANDS = {
    "Facile": (0.68, 0.88),
    "Moyen": (0.45, 0.70),
    "Difficile": (0.22, 0.48),
}
SMOOTHING_PSEUDO_GAMES = 6
MIN_GAMES_FOR_SIGNAL = 8
MIN_GAMES_FOR_REVIEW = 15
WATCH_MARGIN = 0.08
REVIEW_MARGIN = 0.12
HARD_SIGNAL_TIMEOUT_RATE = 0.25
HARD_SIGNAL_ATTEMPT_FAIL_RATE = 0.25
EASY_SIGNAL_MARGIN_FLOOR = 0.35
REVIEW_CONFIDENCE_MIN_PLAYERS = 2
REVIEW_CONFIDENCE_MIN_GAMES = 25
REVIEW_CONFIDENCE_MAX_DOMINANT_SHARE = 0.70
WIN_MARGIN_FLOORS = {
    "Facile": {"time": 0.20, "attempts": 0.25},
    "Moyen": {"time": 0.12, "attempts": 0.15},
    "Difficile": {"time": 0.05, "attempts": 0.10},
}
STATUS_RANK = {
    "stable": 1,
    "insufficient_data": 2,
    "watch": 3,
    "review": 4,
}
STATUS_LABELS = {
    "review": "A revoir",
    "watch": "A surveiller",
    "stable": "Stable",
    "insufficient_data": "Pas assez de donnees",
}


def _format_ratio(value):
    if value is None:
        return "-"
    return f"{round(float(value) * 100, 1):g}%"


def _safe_ratio(value, total):
    return float(value or 0) / float(total) if total else 0.0


def _split_category_key(category_key):
    category_key = str(category_key)
    if CATEGORY_KEY_SEPARATOR not in category_key:
        return CORE_PACK_ID, category_key
    return category_key.split(CATEGORY_KEY_SEPARATOR, 1)


def _strip_pack_prefix(label, pack_label):
    label = str(label or "").strip()
    prefix = f"{pack_label} / "
    if pack_label and label.startswith(prefix):
        return label[len(prefix):]
    return label


def _build_category_metadata(catalog):
    metadata = {}
    for pack_summary in getattr(catalog, "pack_summaries", ()):
        for category_summary in getattr(pack_summary, "categories", ()):
            display_label = str(category_summary.label or "").strip() or format_category_name(
                category_summary.category_key,
                getattr(catalog, "display_names", None),
            )
            metadata[category_summary.category_key] = {
                "pack_id": pack_summary.pack_id,
                "pack_label": pack_summary.label,
                "category_key": category_summary.category_key,
                "label": display_label,
                "category_label": _strip_pack_prefix(display_label, pack_summary.label),
            }
    return metadata


def _build_active_pairs(catalog):
    active_pairs = []
    category_availability = getattr(catalog, "category_availability", {})
    for category in sorted(category_availability):
        supported = set(category_availability.get(category, ()))
        for difficulty in DIFFICULTY_LEVELS:
            if difficulty in supported:
                active_pairs.append((category, difficulty))
    return active_pairs


def _build_pair_metadata(category, metadata_by_key, display_names):
    metadata = metadata_by_key.get(category)
    if metadata is not None:
        return metadata

    pack_id, _category_id = _split_category_key(category)
    label = format_category_name(category, display_names)
    pack_label = "Catalogue integre" if pack_id == CORE_PACK_ID else format_category_name(pack_id)
    return {
        "pack_id": pack_id,
        "pack_label": pack_label,
        "category_key": category,
        "label": label,
        "category_label": _strip_pack_prefix(label, pack_label),
    }


def _get_target_band(difficulty):
    return TARGET_WIN_RATE_BANDS[difficulty]


def _get_smoothed_win_rate(wins, games_played, difficulty):
    lower, upper = _get_target_band(difficulty)
    midpoint = (lower + upper) / 2
    pseudo_wins = midpoint * SMOOTHING_PSEUDO_GAMES
    return (float(wins) + pseudo_wins) / float(games_played + SMOOTHING_PSEUDO_GAMES)


def _get_direction(smoothed_win_rate, target_lower, target_upper):
    if smoothed_win_rate < target_lower:
        return "plus dur"
    if smoothed_win_rate > target_upper:
        return "plus facile"
    return "dans la cible"


def _get_distance_to_band(smoothed_win_rate, target_lower, target_upper):
    if smoothed_win_rate < target_lower:
        return target_lower - smoothed_win_rate
    if smoothed_win_rate > target_upper:
        return smoothed_win_rate - target_upper
    return 0.0


def _has_hard_signal(row, difficulty):
    floors = WIN_MARGIN_FLOORS[difficulty]
    avg_time_margin = row.get("avg_time_margin_on_wins")
    avg_attempt_margin = row.get("avg_attempt_margin_on_wins")
    return (
        float(row.get("timeout_rate") or 0.0) >= HARD_SIGNAL_TIMEOUT_RATE
        or float(row.get("attempt_fail_rate") or 0.0) >= HARD_SIGNAL_ATTEMPT_FAIL_RATE
        or (avg_time_margin is not None and float(avg_time_margin) < floors["time"])
        or (avg_attempt_margin is not None and float(avg_attempt_margin) < floors["attempts"])
    )


def _has_easy_signal(row):
    avg_time_margin = row.get("avg_time_margin_on_wins")
    avg_attempt_margin = row.get("avg_attempt_margin_on_wins")
    return (
        avg_time_margin is not None
        and avg_attempt_margin is not None
        and float(avg_time_margin) >= EASY_SIGNAL_MARGIN_FLOOR
        and float(avg_attempt_margin) >= EASY_SIGNAL_MARGIN_FLOOR
    )


def _has_review_confidence(row):
    games_played = int(row.get("games_played") or 0)
    distinct_players = int(row.get("distinct_players") or 0)
    dominant_player_share = float(row.get("dominant_player_share") or 0.0)
    return (
        (distinct_players >= REVIEW_CONFIDENCE_MIN_PLAYERS or games_played >= REVIEW_CONFIDENCE_MIN_GAMES)
        and dominant_player_share <= REVIEW_CONFIDENCE_MAX_DOMINANT_SHARE
    )


def _build_insufficient_reason(row):
    games_played = int(row.get("games_played") or 0)
    if games_played <= 0:
        return "Aucune partie observee sur cette paire active."
    return (
        f"Echantillon encore trop faible: {games_played}/{MIN_GAMES_FOR_SIGNAL} parties."
    )


def _build_reason(row, difficulty, status, direction, target_text, smoothed_text):
    games_played = int(row.get("games_played") or 0)
    timeout_rate = float(row.get("timeout_rate") or 0.0)
    attempt_fail_rate = float(row.get("attempt_fail_rate") or 0.0)
    avg_time_margin = row.get("avg_time_margin_on_wins")
    avg_attempt_margin = row.get("avg_attempt_margin_on_wins")
    review_confidence = _has_review_confidence(row)
    hard_signal = _has_hard_signal(row, difficulty)
    easy_signal = _has_easy_signal(row)

    if status == "insufficient_data":
        return _build_insufficient_reason(row)

    if direction == "dans la cible":
        return f"Taux lisse {smoothed_text} dans la cible {target_text}."

    reasons = [f"Taux lisse {smoothed_text} hors cible {target_text}."]
    if direction == "plus dur":
        pressure_parts = []
        if timeout_rate >= HARD_SIGNAL_TIMEOUT_RATE:
            pressure_parts.append(f"temps { _format_ratio(timeout_rate) }")
        if attempt_fail_rate >= HARD_SIGNAL_ATTEMPT_FAIL_RATE:
            pressure_parts.append(f"essais { _format_ratio(attempt_fail_rate) }")
        if avg_time_margin is not None and float(avg_time_margin) < WIN_MARGIN_FLOORS[difficulty]["time"]:
            pressure_parts.append(f"marge temps victoire { _format_ratio(avg_time_margin) }")
        if avg_attempt_margin is not None and float(avg_attempt_margin) < WIN_MARGIN_FLOORS[difficulty]["attempts"]:
            pressure_parts.append(f"marge essais victoire { _format_ratio(avg_attempt_margin) }")
        if pressure_parts:
            reasons.append("Pression visible: " + ", ".join(pressure_parts) + ".")
        if games_played >= MIN_GAMES_FOR_REVIEW and not hard_signal:
            reasons.append("Le signal de pression reste incomplet pour conclure a une vraie derive.")
    else:
        comfort_parts = []
        if avg_time_margin is not None:
            comfort_parts.append(f"marge temps victoire { _format_ratio(avg_time_margin) }")
        if avg_attempt_margin is not None:
            comfort_parts.append(f"marge essais victoire { _format_ratio(avg_attempt_margin) }")
        if comfort_parts:
            reasons.append("Confort observe: " + ", ".join(comfort_parts) + ".")
        if games_played >= MIN_GAMES_FOR_REVIEW and not easy_signal:
            reasons.append("Le confort observe reste insuffisant pour conclure a une paire vraiment trop facile.")

    if status == "watch" and games_played >= MIN_GAMES_FOR_REVIEW and not review_confidence:
        reasons.append("Confiance limitee: l'echantillon reste trop concentre ou trop peu diversifie.")

    return " ".join(reasons)


def _build_manual_suggestion(direction, status):
    if status == "insufficient_data":
        return "Attendre plus de parties reelles avant de recalibrer cette paire."
    if status == "stable":
        return "Aucune correction prioritaire. Laisser vivre la paire et surveiller la suite."
    if direction == "plus dur":
        return (
            "Verifier la repartition des mots de cette paire: descendre certains mots vers le niveau "
            "inferieur ou enrichir le pool avec des mots moins exigeants."
        )
    if direction == "plus facile":
        return (
            "Verifier la repartition des mots de cette paire: remonter certains mots vers le niveau "
            "superieur ou enrichir le pool avec des mots plus exigeants."
        )
    return "Pas d'action immediate recommandee."


def _evaluate_pair(row, metadata):
    difficulty = row["difficulty"]
    games_played = int(row.get("games_played") or 0)
    wins = int(row.get("wins") or 0)
    target_lower, target_upper = _get_target_band(difficulty)
    raw_win_rate = _safe_ratio(wins, games_played) if games_played else None
    smoothed_win_rate = _get_smoothed_win_rate(wins, games_played, difficulty)
    direction = _get_direction(smoothed_win_rate, target_lower, target_upper)
    distance_to_band = _get_distance_to_band(smoothed_win_rate, target_lower, target_upper)
    hard_signal = _has_hard_signal(row, difficulty)
    easy_signal = _has_easy_signal(row)
    coherent_signal = hard_signal or easy_signal
    review_confidence = _has_review_confidence(row)

    if games_played < MIN_GAMES_FOR_SIGNAL:
        status = "insufficient_data"
    elif (
        direction != "dans la cible"
        and distance_to_band >= REVIEW_MARGIN
        and games_played >= MIN_GAMES_FOR_REVIEW
        and coherent_signal
        and review_confidence
    ):
        status = "review"
    elif direction != "dans la cible" and distance_to_band >= WATCH_MARGIN:
        status = "watch"
    else:
        status = "stable"

    target_text = f"{_format_ratio(target_lower)}-{_format_ratio(target_upper)}"
    observed_text = _format_ratio(raw_win_rate)
    smoothed_text = _format_ratio(smoothed_win_rate)

    return {
        "category": row["category"],
        "difficulty": difficulty,
        "label": metadata["label"],
        "pack_id": metadata["pack_id"],
        "pack_label": metadata["pack_label"],
        "category_label": metadata["category_label"],
        "status": status,
        "status_label": STATUS_LABELS[status],
        "direction": direction,
        "games_played": games_played,
        "wins": wins,
        "distinct_players": int(row.get("distinct_players") or 0),
        "dominant_player_share": float(row.get("dominant_player_share") or 0.0),
        "raw_win_rate": raw_win_rate,
        "smoothed_win_rate": smoothed_win_rate,
        "target_lower": target_lower,
        "target_upper": target_upper,
        "distance_to_band": distance_to_band,
        "timeout_rate": float(row.get("timeout_rate") or 0.0),
        "attempt_fail_rate": float(row.get("attempt_fail_rate") or 0.0),
        "avg_time_margin_on_wins": row.get("avg_time_margin_on_wins"),
        "avg_attempt_margin_on_wins": row.get("avg_attempt_margin_on_wins"),
        "avg_score": float(row.get("avg_score") or 0.0),
        "avg_complexity": float(row.get("avg_complexity") or 0.0),
        "last_played_at": row.get("last_played_at"),
        "target_text": target_text,
        "observed_text": observed_text,
        "smoothed_text": smoothed_text,
        "observed_vs_target": f"{smoothed_text} vs {target_text}",
        "confidence_sufficient": review_confidence,
        "hard_signal": hard_signal,
        "easy_signal": easy_signal,
        "reason": _build_reason(row, difficulty, status, direction, target_text, smoothed_text),
        "manual_suggestion": _build_manual_suggestion(direction, status),
    }


def _pair_sort_key(pair):
    return (
        -STATUS_RANK[pair["status"]],
        -float(pair.get("distance_to_band") or 0.0),
        -int(pair.get("games_played") or 0),
        pair["label"],
        pair["difficulty"],
    )


def _build_section(title, key, pairs, description):
    return {
        "key": key,
        "title": title,
        "description": description,
        "pairs": tuple(sorted(pairs, key=_pair_sort_key)),
    }


def _build_rollups(items, *, key_name, label_name):
    groups = {}
    for item in items:
        groups.setdefault(
            item[key_name],
            {
                "key": item[key_name],
                "label": item[label_name],
                "pairs": 0,
                "review_count": 0,
                "watch_count": 0,
                "stable_count": 0,
                "insufficient_data_count": 0,
                "status": "stable",
            },
        )
        group = groups[item[key_name]]
        group["pairs"] += 1
        group[f"{item['status']}_count"] += 1
        if STATUS_RANK[item["status"]] > STATUS_RANK[group["status"]]:
            group["status"] = item["status"]

    rollups = []
    for group in groups.values():
        group["status_label"] = STATUS_LABELS[group["status"]]
        group["signal_count"] = group["review_count"] + group["watch_count"]
        group["detail"] = (
            f"{group['review_count']} a revoir, {group['watch_count']} a surveiller, "
            f"{group['insufficient_data_count']} sans recul, {group['stable_count']} stable(s)."
        )
        rollups.append(group)

    return tuple(
        sorted(
            rollups,
            key=lambda group: (
                -STATUS_RANK[group["status"]],
                -group["signal_count"],
                group["label"],
            ),
        )
    )


def _build_policy_lines():
    return (
        "Bandes cibles: Facile 68%-88%, Moyen 45%-70%, Difficile 22%-48%.",
        f"Lissage: {SMOOTHING_PSEUDO_GAMES} pseudo-parties centrees sur le milieu de la bande cible.",
        f"Pas assez de donnees sous {MIN_GAMES_FOR_SIGNAL} parties.",
        f"A surveiller si le taux lisse sort de sa bande de {int(WATCH_MARGIN * 100)} points ou plus.",
        (
            f"A revoir si l'ecart atteint {int(REVIEW_MARGIN * 100)} points, avec au moins "
            f"{MIN_GAMES_FOR_REVIEW} parties, un signal coherent et une confiance suffisante."
        ),
        (
            "Signal plus dur: temps >= 25%, essais >= 25%, ou marges de victoire sous les planchers "
            "du niveau."
        ),
        "Signal plus facile: marges moyennes sur victoire >= 35% sur le temps et les essais.",
        "Confiance pour A revoir: au moins 2 joueurs distincts ou 25 parties, et aucun joueur au-dessus de 70%.",
    )


def get_difficulty_calibration_bundle(catalog, db_path=None):
    active_pairs = _build_active_pairs(catalog)
    kwargs = {"db_path": db_path} if db_path is not None else {}
    rows = get_difficulty_calibration_rows(active_pairs, **kwargs)
    metadata_by_key = _build_category_metadata(catalog)
    display_names = getattr(catalog, "display_names", {})
    evaluated_pairs = [
        _evaluate_pair(
            row,
            _build_pair_metadata(row["category"], metadata_by_key, display_names),
        )
        for row in rows
    ]

    review_pairs = [pair for pair in evaluated_pairs if pair["status"] == "review"]
    watch_pairs = [pair for pair in evaluated_pairs if pair["status"] == "watch"]
    stable_pairs = [pair for pair in evaluated_pairs if pair["status"] == "stable"]
    insufficient_pairs = [pair for pair in evaluated_pairs if pair["status"] == "insufficient_data"]
    latest_observation_at = max(
        (pair["last_played_at"] for pair in evaluated_pairs if pair.get("last_played_at")),
        default=None,
    )

    return {
        "summary": {
            "active_pair_count": len(evaluated_pairs),
            "review_count": len(review_pairs),
            "watch_count": len(watch_pairs),
            "stable_count": len(stable_pairs),
            "insufficient_data_count": len(insufficient_pairs),
            "signal_count": len(review_pairs) + len(watch_pairs),
            "latest_observation_at": latest_observation_at,
        },
        "sections": (
            _build_section(
                "Paires a revoir",
                "review",
                review_pairs,
                "Les signaux reelles s'ecartent nettement de la promesse et merite une correction catalogue.",
            ),
            _build_section(
                "Paires a surveiller",
                "watch",
                watch_pairs,
                "Un ecart devient visible, mais le diagnostic reste trop jeune ou trop fragile pour recalibrer vite.",
            ),
            _build_section(
                "Paires stables",
                "stable",
                stable_pairs,
                "Les observations restent compatibles avec la promesse actuelle.",
            ),
            _build_section(
                "Pas assez de donnees",
                "insufficient_data",
                insufficient_pairs,
                "Le cadre de lecture est deja le meme, mais l'echantillon reste trop faible pour conclure.",
            ),
        ),
        "pairs": tuple(sorted(evaluated_pairs, key=_pair_sort_key)),
        "pack_rollups": _build_rollups(evaluated_pairs, key_name="pack_id", label_name="pack_label"),
        "category_rollups": _build_rollups(
            evaluated_pairs,
            key_name="category",
            label_name="label",
        ),
        "policy": {
            "target_win_rate_bands": TARGET_WIN_RATE_BANDS,
            "smoothing_pseudo_games": SMOOTHING_PSEUDO_GAMES,
            "minimum_games_for_signal": MIN_GAMES_FOR_SIGNAL,
            "minimum_games_for_review": MIN_GAMES_FOR_REVIEW,
            "watch_margin": WATCH_MARGIN,
            "review_margin": REVIEW_MARGIN,
            "lines": _build_policy_lines(),
        },
    }

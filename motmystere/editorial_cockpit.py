from .catalog_service import CatalogServiceError
from .categories import CORE_PACK_ID, DIFFICULTY_LEVELS
from .difficulty_calibration import get_difficulty_calibration_bundle


COVERAGE_TARGET_TOTAL_WORDS = 45
COVERAGE_TARGET_PER_DIFFICULTY = 15

ACTION_LABELS = {
    "disable": "Desactiver",
    "enrich": "Enrichir",
    "recalibrate": "Recalibrer",
    "keep": "Laisser",
}
ACTION_DESCRIPTIONS = {
    "disable": "Aucun niveau jouable fiable ou pack a couper avant publication.",
    "enrich": "La categorie reste jouable mais ne tient pas encore la profondeur editoriale cible.",
    "recalibrate": "La profondeur est suffisante mais le signal reelle contredit la promesse de difficulte.",
    "keep": "Aucune correction prioritaire, simplement conserver la lecture actuelle.",
}
ACTION_RANK = {
    "keep": 1,
    "recalibrate": 2,
    "enrich": 3,
    "disable": 4,
}

PLAYABILITY_LABELS = {
    "active": "Actif",
    "disabled": "Desactive",
    "invalid": "Invalide",
    "readonly": "Lecture seule",
    "not_installed": "Non installe",
}

COVERAGE_LABELS = {
    "sufficient": "Cible tenue",
    "limited": "Sous cible",
    "unknown": "Non evalue",
}

CALIBRATION_LABELS = {
    "review": "A revoir",
    "watch": "A surveiller",
    "insufficient_data": "Pas assez de donnees",
    "stable": "Stable",
    "inactive": "Inactif",
    "not_installed": "Non installe",
    "unavailable": "Absent",
}
CALIBRATION_RANK = {
    "unavailable": 0,
    "inactive": 1,
    "not_installed": 1,
    "stable": 2,
    "insufficient_data": 3,
    "watch": 4,
    "review": 5,
}


def _dedupe(items):
    seen = set()
    result = []
    for item in items:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _build_pair_lookup(pairs):
    lookup = {}
    for pair in pairs:
        lookup.setdefault(pair["category"], {})[pair["difficulty"]] = pair
    return lookup


def _build_breakdown(category_summary):
    return {
        "Facile": int(getattr(category_summary, "easy_word_count", 0) or 0),
        "Moyen": int(getattr(category_summary, "medium_word_count", 0) or 0),
        "Difficile": int(getattr(category_summary, "hard_word_count", 0) or 0),
    }


def _coverage_gaps(total_words, breakdown):
    total_gap = max(0, COVERAGE_TARGET_TOTAL_WORDS - int(total_words or 0))
    per_level_gaps = {
        difficulty: max(0, COVERAGE_TARGET_PER_DIFFICULTY - int(breakdown.get(difficulty, 0) or 0))
        for difficulty in DIFFICULTY_LEVELS
    }
    return total_gap, per_level_gaps


def _pick_worst_status(statuses):
    statuses = [status for status in statuses if status]
    if not statuses:
        return "inactive"
    return max(statuses, key=lambda status: CALIBRATION_RANK.get(status, 0))


def _format_short_ratio(pair):
    smoothed = pair.get("smoothed_text")
    target = pair.get("target_text")
    if smoothed and target:
        return f"{smoothed} vs {target}"
    return ""


def _build_difficulty_cells(category_summary, pair_lookup, *, official_preview=False):
    breakdown = _build_breakdown(category_summary)
    cells = []
    calibration_statuses = []
    review_pairs = []
    watch_pairs = []
    insufficient_pairs = []
    max_distance = 0.0

    for difficulty in DIFFICULTY_LEVELS:
        word_count = breakdown[difficulty]
        pair = pair_lookup.get(difficulty)

        if word_count <= 0:
            calibration_status = "unavailable"
            calibration_reason = "Niveau absent du pool."
        elif official_preview:
            calibration_status = "not_installed"
            calibration_reason = "Aucune calibration reelle avant installation."
        elif category_summary.status != "active":
            calibration_status = "inactive"
            calibration_reason = "Niveau non actif dans le catalogue."
        elif pair is None:
            calibration_status = "inactive"
            calibration_reason = "Aucune paire active relevee."
        else:
            calibration_status = pair["status"]
            calibration_reason = pair["reason"]
            max_distance = max(max_distance, float(pair.get("distance_to_band") or 0.0))
            calibration_statuses.append(calibration_status)
            if calibration_status == "review":
                review_pairs.append(pair)
            elif calibration_status == "watch":
                watch_pairs.append(pair)
            elif calibration_status == "insufficient_data":
                insufficient_pairs.append(pair)

        cells.append(
            {
                "difficulty": difficulty,
                "word_count": word_count,
                "target_word_count": COVERAGE_TARGET_PER_DIFFICULTY,
                "meets_target": word_count >= COVERAGE_TARGET_PER_DIFFICULTY,
                "available": word_count > 0,
                "coverage_text": f"{word_count}/{COVERAGE_TARGET_PER_DIFFICULTY}",
                "calibration_status": calibration_status,
                "calibration_label": CALIBRATION_LABELS[calibration_status],
                "calibration_reason": calibration_reason,
            }
        )

    overall_status = "not_installed" if official_preview else _pick_worst_status(calibration_statuses)

    return {
        "cells": tuple(cells),
        "overall_status": overall_status,
        "review_pairs": tuple(review_pairs),
        "watch_pairs": tuple(watch_pairs),
        "insufficient_pairs": tuple(insufficient_pairs),
        "max_distance_to_band": max_distance,
    }


def _build_category_reasons(
    category_summary,
    *,
    playability_status,
    total_words,
    breakdown,
    coverage_ready,
    missing_levels,
    below_target_levels,
    calibration_rollup,
    official_preview,
):
    reasons = []

    if playability_status == "invalid":
        reasons.append("Categorie invalide ou sans niveau jouable fiable.")
    elif playability_status == "disabled":
        reasons.append("Categorie installee mais desactivee dans le catalogue actif.")
    elif official_preview:
        reasons.append("Categorie inspectee hors catalogue actif.")

    if not coverage_ready:
        if total_words < COVERAGE_TARGET_TOTAL_WORDS:
            reasons.append(
                f"Profondeur globale sous cible: {total_words}/{COVERAGE_TARGET_TOTAL_WORDS} mots."
            )
        if missing_levels:
            reasons.append("Niveaux absents: " + ", ".join(missing_levels) + ".")
        if below_target_levels:
            level_text = ", ".join(
                f"{difficulty} {breakdown[difficulty]}/{COVERAGE_TARGET_PER_DIFFICULTY}"
                for difficulty in below_target_levels
            )
            reasons.append("Niveaux sous cible: " + level_text + ".")

    calibration_status = calibration_rollup["overall_status"]
    if calibration_status == "review" and calibration_rollup["review_pairs"]:
        pair = sorted(
            calibration_rollup["review_pairs"],
            key=lambda item: (-float(item.get("distance_to_band") or 0.0), item["difficulty"]),
        )[0]
        ratio_text = _format_short_ratio(pair)
        if ratio_text:
            reasons.append(f"{pair['difficulty']} a revoir: {ratio_text}.")
        else:
            reasons.append(f"{pair['difficulty']} a revoir.")
    elif calibration_status == "watch" and calibration_rollup["watch_pairs"]:
        watched = ", ".join(pair["difficulty"] for pair in calibration_rollup["watch_pairs"])
        reasons.append("Signal a surveiller sur: " + watched + ".")
    elif calibration_status == "insufficient_data":
        reasons.append("Lecture calibration ouverte mais encore trop peu de parties reelles.")
    elif calibration_status == "not_installed":
        reasons.append("Calibration reelle indisponible tant que le pack n'est pas installe.")

    return _dedupe(reasons)[:3]


def _build_category_entry(
    pack_label,
    pack_id,
    category_summary,
    pair_lookup,
    *,
    official_preview=False,
):
    total_words = int(getattr(category_summary, "total_words", 0) or 0)
    breakdown = _build_breakdown(category_summary)
    total_gap, per_level_gaps = _coverage_gaps(total_words, breakdown)
    missing_levels = [
        difficulty for difficulty in DIFFICULTY_LEVELS if int(breakdown[difficulty]) <= 0
    ]
    below_target_levels = [
        difficulty
        for difficulty in DIFFICULTY_LEVELS
        if 0 < int(breakdown[difficulty]) < COVERAGE_TARGET_PER_DIFFICULTY
    ]
    coverage_ready = total_gap == 0 and all(gap == 0 for gap in per_level_gaps.values())
    coverage_status = "sufficient" if coverage_ready else "limited"

    if category_summary.status == "invalid" or not category_summary.available_difficulties:
        playability_status = "invalid"
    elif official_preview:
        playability_status = "not_installed"
    elif category_summary.status == "disabled":
        playability_status = "disabled"
    else:
        playability_status = "active"

    calibration_rollup = _build_difficulty_cells(
        category_summary,
        pair_lookup,
        official_preview=official_preview,
    )

    if playability_status == "invalid":
        recommended_action = "disable"
    elif not coverage_ready:
        recommended_action = "enrich"
    elif calibration_rollup["overall_status"] == "review":
        recommended_action = "recalibrate"
    else:
        recommended_action = "keep"

    reasons = _build_category_reasons(
        category_summary,
        playability_status=playability_status,
        total_words=total_words,
        breakdown=breakdown,
        coverage_ready=coverage_ready,
        missing_levels=missing_levels,
        below_target_levels=below_target_levels,
        calibration_rollup=calibration_rollup,
        official_preview=official_preview,
    )

    return {
        "pack_id": pack_id,
        "pack_label": pack_label,
        "category_key": category_summary.category_key,
        "label": category_summary.label,
        "source_path": category_summary.source_path,
        "status": category_summary.status,
        "playability_status": playability_status,
        "playability_label": PLAYABILITY_LABELS[playability_status],
        "coverage_status": coverage_status,
        "coverage_label": COVERAGE_LABELS[coverage_status],
        "calibration_status": calibration_rollup["overall_status"],
        "calibration_label": CALIBRATION_LABELS[calibration_rollup["overall_status"]],
        "recommended_action": recommended_action,
        "recommended_action_label": ACTION_LABELS[recommended_action],
        "severity": ACTION_RANK[recommended_action],
        "reasons": reasons,
        "total_words": total_words,
        "target_total_words": COVERAGE_TARGET_TOTAL_WORDS,
        "difficulty_breakdown": breakdown,
        "available_difficulties": tuple(category_summary.available_difficulties),
        "difficulty_cells": calibration_rollup["cells"],
        "missing_levels": tuple(missing_levels),
        "below_target_levels": tuple(below_target_levels),
        "coverage_gap_total": total_gap + sum(per_level_gaps.values()),
        "review_pair_count": len(calibration_rollup["review_pairs"]),
        "watch_pair_count": len(calibration_rollup["watch_pairs"]),
        "insufficient_pair_count": len(calibration_rollup["insufficient_pairs"]),
        "max_distance_to_band": calibration_rollup["max_distance_to_band"],
    }


def _build_pack_action_summary(categories):
    counts = {}
    for category in categories:
        counts[category["recommended_action"]] = counts.get(category["recommended_action"], 0) + 1
    parts = []
    for action in ("disable", "enrich", "recalibrate"):
        count = counts.get(action, 0)
        if count:
            parts.append(f"{count} categorie(s) a {ACTION_LABELS[action].lower()}")
    if not parts:
        return "Aucune categorie prioritaire dans ce pack."
    return ", ".join(parts) + "."


def _build_pack_reasons(pack_entry, *, raw_reasons=()):
    reasons = [pack_entry["action_summary"]]
    if pack_entry["playability_status"] == "invalid":
        reasons.append("Le pack ne peut pas etre considere comme fiable en l'etat.")
    elif pack_entry["playability_status"] == "disabled":
        reasons.append("Le pack est installe mais hors catalogue actif.")
    elif pack_entry["playability_status"] == "not_installed":
        reasons.append("Pack officiel inspecte sans activation dans l'environnement local.")
    reasons.extend(raw_reasons)
    return _dedupe(reasons)[:3]


def _build_pack_entry(
    pack_summary,
    categories,
    *,
    origin,
    installed,
    official_preview=False,
    description="",
    archive_path="",
    alerts=(),
    blockers=(),
):
    recommended_action = "keep"
    if blockers or pack_summary.status == "invalid":
        recommended_action = "disable"
    elif categories:
        recommended_action = max(
            (category["recommended_action"] for category in categories),
            key=lambda action: ACTION_RANK[action],
        )

    if installed:
        if pack_summary.pack_id == CORE_PACK_ID:
            playability_status = "readonly"
        else:
            playability_status = {
                "active": "active",
                "disabled": "disabled",
                "invalid": "invalid",
            }.get(pack_summary.status, "active")
    else:
        playability_status = "not_installed" if not blockers else "invalid"

    coverage_status = "unknown"
    if categories:
        coverage_status = (
            "sufficient"
            if all(category["coverage_status"] == "sufficient" for category in categories)
            else "limited"
        )

    calibration_status = (
        _pick_worst_status(category["calibration_status"] for category in categories)
        if categories
        else "inactive"
    )
    action_touch_count = sum(
        1 for category in categories if category["recommended_action"] == recommended_action
    )
    attention_count = sum(1 for category in categories if category["recommended_action"] != "keep")
    action_summary = _build_pack_action_summary(categories)
    raw_reasons = list(blockers[:2]) + list(alerts[:1])

    pack_entry = {
        "pack_id": pack_summary.pack_id,
        "label": pack_summary.label,
        "origin": origin,
        "description": description,
        "archive_path": archive_path,
        "source_path": pack_summary.source_path,
        "status": pack_summary.status,
        "installed": bool(installed),
        "declared_enabled": bool(getattr(pack_summary, "declared_enabled", True)),
        "effective_enabled": bool(getattr(pack_summary, "effective_enabled", installed)),
        "category_count": int(getattr(pack_summary, "category_count", 0) or 0),
        "loaded_category_count": int(getattr(pack_summary, "loaded_category_count", 0) or 0),
        "playable_category_count": int(getattr(pack_summary, "playable_category_count", 0) or 0),
        "issue_count": int(getattr(pack_summary, "issue_count", 0) or 0),
        "playability_status": playability_status,
        "playability_label": PLAYABILITY_LABELS[playability_status],
        "coverage_status": coverage_status,
        "coverage_label": COVERAGE_LABELS[coverage_status],
        "calibration_status": calibration_status,
        "calibration_label": CALIBRATION_LABELS[calibration_status],
        "recommended_action": recommended_action,
        "recommended_action_label": ACTION_LABELS[recommended_action],
        "severity": ACTION_RANK[recommended_action],
        "categories": tuple(categories),
        "action_touch_count": action_touch_count,
        "attention_count": attention_count,
        "action_summary": action_summary,
        "installable": not blockers,
        "alerts": tuple(alerts),
        "blockers": tuple(blockers),
    }
    pack_entry["reasons"] = _build_pack_reasons(pack_entry, raw_reasons=raw_reasons)
    return pack_entry


def _build_installed_pack_entry(pack_summary, catalog, pair_lookup):
    categories = []
    for category_summary in pack_summary.categories:
        categories.append(
            _build_category_entry(
                pack_summary.label,
                pack_summary.pack_id,
                category_summary,
                pair_lookup.get(category_summary.category_key, {}),
            )
        )
    return _build_pack_entry(
        pack_summary,
        categories,
        origin=pack_summary.origin,
        installed=True,
    )


def _build_official_pack_entry(pack_info, preview):
    pack_summary = preview.effect_when_enabled
    categories = []
    for category_summary in pack_summary.categories:
        categories.append(
            _build_category_entry(
                pack_summary.label,
                pack_summary.pack_id,
                category_summary,
                {},
                official_preview=True,
            )
        )
    return _build_pack_entry(
        pack_summary,
        categories,
        origin="official",
        installed=False,
        official_preview=True,
        description=pack_info.description,
        archive_path=pack_info.archive_path,
        alerts=preview.alerts,
        blockers=preview.blockers,
    )


def _priority_sort_key(item):
    return (
        -ACTION_RANK[item["recommended_action"]],
        -int(item["coverage_gap_total"]),
        -int(item["review_pair_count"]),
        -float(item.get("max_distance_to_band") or 0.0),
        item["pack_label"],
        item["label"],
    )


def _build_priority_sections(installed_packs, official_packs):
    items = []
    for pack in installed_packs + official_packs:
        for category in pack["categories"]:
            items.append(
                {
                    **category,
                    "priority_key": f"{pack['pack_id']}::{category['category_key']}",
                    "priority_label": category["label"],
                    "pack_action": pack["recommended_action"],
                }
            )

    sections = []
    for action in ("disable", "enrich", "recalibrate", "keep"):
        section_items = [item for item in items if item["recommended_action"] == action]
        sections.append(
            {
                "key": action,
                "title": ACTION_LABELS[action],
                "description": ACTION_DESCRIPTIONS[action],
                "count": len(section_items),
                "items": tuple(sorted(section_items, key=_priority_sort_key)),
            }
        )
    return tuple(sections)


def _build_summary(installed_packs, official_packs, priority_sections, calibration_summary):
    action_counts = {section["key"]: section["count"] for section in priority_sections}
    return {
        "installed_pack_count": len(installed_packs),
        "official_pack_count": len(official_packs),
        "priority_count": sum(
            section["count"] for section in priority_sections if section["key"] != "keep"
        ),
        "action_counts": action_counts,
        "active_pair_count": calibration_summary.get("active_pair_count", 0),
        "latest_observation_at": calibration_summary.get("latest_observation_at"),
        "cards": (
            {
                "key": "disable",
                "title": "A desactiver",
                "value": action_counts.get("disable", 0),
                "detail": "Categories ou packs a couper avant publication.",
            },
            {
                "key": "enrich",
                "title": "A enrichir",
                "value": action_counts.get("enrich", 0),
                "detail": "Couverture reelle sous la cible editoriale retenue.",
            },
            {
                "key": "recalibrate",
                "title": "A recalibrer",
                "value": action_counts.get("recalibrate", 0),
                "detail": "Promesse de difficulte a revoir sur signal reel confirme.",
            },
            {
                "key": "keep",
                "title": "A laisser",
                "value": action_counts.get("keep", 0),
                "detail": "Elements sans correction prioritaire immediate.",
            },
        ),
    }


def _pack_sort_key(pack):
    return (
        -ACTION_RANK[pack["recommended_action"]],
        -int(pack["action_touch_count"]),
        -int(pack["attention_count"]),
        pack["label"],
    )


def get_editorial_cockpit_bundle(catalog, *, catalog_service=None, db_path=None):
    calibration_bundle = get_difficulty_calibration_bundle(catalog, db_path=db_path)
    pair_lookup = _build_pair_lookup(calibration_bundle["pairs"])

    installed_packs = [
        _build_installed_pack_entry(pack_summary, catalog, pair_lookup)
        for pack_summary in catalog.pack_summaries
    ]
    installed_packs = tuple(sorted(installed_packs, key=_pack_sort_key))

    official_packs = []
    official_error = ""
    if catalog_service is not None:
        try:
            official_pack_infos = catalog_service.list_official_packs()
        except CatalogServiceError as exc:
            official_error = str(exc)
        else:
            for official_pack in official_pack_infos:
                if official_pack.installed:
                    continue
                preview = catalog_service.inspect_pack_source(official_pack.archive_path)
                official_packs.append(_build_official_pack_entry(official_pack, preview))
    official_packs = tuple(sorted(official_packs, key=_pack_sort_key))

    priority_sections = _build_priority_sections(list(installed_packs), list(official_packs))
    summary = _build_summary(
        list(installed_packs),
        list(official_packs),
        priority_sections,
        calibration_bundle["summary"],
    )

    return {
        "summary": summary,
        "priority_sections": priority_sections,
        "installed_packs": installed_packs,
        "official_packs": official_packs,
        "official_error": official_error,
        "calibration_policy": calibration_bundle["policy"],
    }

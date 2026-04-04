import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from .app_paths import get_resource_directory, get_word_packs_directory


BASE_DIR = get_resource_directory()
DIFFICULTY_LEVELS = ("Facile", "Moyen", "Difficile")
EASY_COMPLEXITY_MAX = 27
MEDIUM_COMPLEXITY_MAX = 34
RARE_LETTERS = frozenset("KQWXYZJ")
MIN_WORD_POOL_SIZE = 5
CORE_PACK_ID = "core"
PACK_MANIFEST_NAME = "pack.json"
CATEGORY_KEY_SEPARATOR = "::"
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class WordProfile:
    text: str
    length: int
    unique_letters: int
    repeated_letters: int
    rare_letters: int
    complexity: int
    difficulty: str


@dataclass(frozen=True)
class CatalogIssue:
    severity: str
    message: str
    pack_id: str
    source_path: str


@dataclass(frozen=True)
class CategorySummary:
    category_key: str
    label: str
    status: str
    available_difficulties: tuple
    source_path: str


@dataclass(frozen=True)
class PackSummary:
    pack_id: str
    label: str
    origin: str
    status: str
    source_path: str
    category_count: int
    loaded_category_count: int
    declared_enabled: bool = True
    effective_enabled: bool = True
    playable_category_count: int = 0
    issue_count: int = 0
    categories: tuple = ()


@dataclass(frozen=True)
class CategoryCatalog:
    categories: dict
    display_names: dict
    pack_summaries: tuple
    issues: tuple
    local_pack_dir: Path | None = None

    @property
    def category_availability(self):
        availability = {}
        for key, words in self.categories.items():
            supported = get_supported_difficulties(words)
            if supported:
                availability[key] = supported
        return availability

    @property
    def issues_by_pack(self):
        grouped = {}
        for issue in self.issues:
            grouped.setdefault(issue.pack_id, []).append(issue)
        return {pack_id: tuple(values) for pack_id, values in grouped.items()}


@dataclass(frozen=True)
class _WordListLoadResult:
    words: tuple
    duplicate_count: int


def _format_token(value):
    normalized = str(value).replace("-", "_").replace("__", "_")
    return normalized.replace("_", " ").title()


def format_category_name(category_key, display_names=None):
    key = str(category_key).strip()
    if display_names and key in display_names:
        return display_names[key]
    if CATEGORY_KEY_SEPARATOR in key:
        pack_id, category_id = key.split(CATEGORY_KEY_SEPARATOR, 1)
        return f"{_format_token(pack_id)} / {_format_token(category_id)}"
    return _format_token(key)


def _normalize_word(word):
    return unicodedata.normalize("NFKC", str(word)).strip().upper()


def _read_word_list(path):
    words = []
    seen = set()
    duplicate_count = 0

    with Path(path).open("r", encoding="utf-8") as handle:
        for mot in handle:
            normalized = _normalize_word(mot)
            if not normalized:
                continue
            if normalized in seen:
                duplicate_count += 1
                continue
            seen.add(normalized)
            words.append(normalized)

    return _WordListLoadResult(tuple(words), duplicate_count)


def _resolve_word_file(path, *, base_dir=BASE_DIR):
    fichier = Path(path)
    if not fichier.is_absolute():
        fichier = Path(base_dir) / fichier
    return fichier


def lire_mots(nom_fichier):
    fichier = _resolve_word_file(nom_fichier)
    return list(_read_word_list(fichier).words)


def calculate_word_complexity(word):
    normalized = _normalize_word(word)
    letters = [char for char in normalized if char.isalpha()]
    unique_letters = len(set(letters))
    repeated_letters = max(0, len(letters) - unique_letters)
    rare_letters = sum(1 for char in letters if char in RARE_LETTERS)
    complexity = (len(letters) * 3) + (unique_letters * 2) + (rare_letters * 3) - repeated_letters
    return {
        "length": len(letters),
        "unique_letters": unique_letters,
        "repeated_letters": repeated_letters,
        "rare_letters": rare_letters,
        "complexity": complexity,
    }


def classify_word_difficulty(complexity):
    complexity = int(complexity)
    if complexity <= EASY_COMPLEXITY_MAX:
        return "Facile"
    if complexity <= MEDIUM_COMPLEXITY_MAX:
        return "Moyen"
    return "Difficile"


def build_word_profile(word):
    metrics = calculate_word_complexity(word)
    return WordProfile(
        text=_normalize_word(word),
        length=metrics["length"],
        unique_letters=metrics["unique_letters"],
        repeated_letters=metrics["repeated_letters"],
        rare_letters=metrics["rare_letters"],
        complexity=metrics["complexity"],
        difficulty=classify_word_difficulty(metrics["complexity"]),
    )


@lru_cache(maxsize=None)
def _build_profiles(words):
    return tuple(build_word_profile(word) for word in words)


def get_word_profiles(words):
    return list(_build_profiles(tuple(words)))


def get_words_for_difficulty(words, difficulty):
    if difficulty not in DIFFICULTY_LEVELS:
        raise ValueError(f"Difficulte inconnue: {difficulty}")

    profiles = get_word_profiles(words)
    return [profile for profile in profiles if profile.difficulty == difficulty]


def get_category_difficulty_breakdown(words):
    counter = Counter(profile.difficulty for profile in get_word_profiles(words))
    return {level: counter.get(level, 0) for level in DIFFICULTY_LEVELS}


def get_supported_difficulties(words, minimum_pool_size=MIN_WORD_POOL_SIZE):
    breakdown = get_category_difficulty_breakdown(words)
    return tuple(
        level
        for level in DIFFICULTY_LEVELS
        if breakdown.get(level, 0) >= int(minimum_pool_size)
    )


def _normalize_identifier(value):
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return normalized


def _is_valid_identifier(value):
    return bool(IDENTIFIER_PATTERN.match(_normalize_identifier(value)))


def _add_issue(issues, severity, message, pack_id, source_path):
    issues.append(
        CatalogIssue(
            severity=severity,
            message=message,
            pack_id=str(pack_id),
            source_path=str(source_path),
        )
    )


def _build_category_key(pack_id, category_id):
    category_id = _normalize_identifier(category_id)
    if pack_id == CORE_PACK_ID:
        return category_id
    return f"{_normalize_identifier(pack_id)}{CATEGORY_KEY_SEPARATOR}{category_id}"


def _build_display_name(pack_id, pack_label, category_id, category_label=None):
    category_name = str(category_label).strip() if category_label else _format_token(category_id)
    if pack_id == CORE_PACK_ID:
        return category_name
    pack_name = str(pack_label).strip() if pack_label else _format_token(pack_id)
    return f"{pack_name} / {category_name}"


def _normalize_pack_overrides(pack_overrides=None):
    normalized = {}
    for pack_id, override in (pack_overrides or {}).items():
        normalized_pack_id = _normalize_identifier(pack_id)
        if not normalized_pack_id or not isinstance(override, dict):
            continue
        enabled = override.get("enabled")
        if isinstance(enabled, bool):
            normalized[normalized_pack_id] = {"enabled": enabled}
    return normalized


def _resolve_effective_pack_enabled(pack_id, declared_enabled, pack_overrides):
    override = (pack_overrides or {}).get(_normalize_identifier(pack_id), {})
    enabled = override.get("enabled")
    if isinstance(enabled, bool):
        return enabled
    return bool(declared_enabled)


def _create_category_summary(
    pack_id,
    pack_label,
    category_id,
    *,
    category_label=None,
    status="invalid",
    available_difficulties=(),
    source_path="",
):
    return CategorySummary(
        category_key=_build_category_key(pack_id, category_id),
        label=_build_display_name(pack_id, pack_label, category_id, category_label),
        status=status,
        available_difficulties=tuple(available_difficulties),
        source_path=str(source_path),
    )


def _load_core_pack(base_dir, categories, display_names, issues):
    base_dir = Path(base_dir)
    source_files = sorted(base_dir.glob("*.txt"))
    loaded_category_count = 0
    playable_category_count = 0
    category_summaries = []

    for file in source_files:
        category_id = _normalize_identifier(file.stem)
        result = _read_word_list(file)
        supported = get_supported_difficulties(result.words)
        category_summary = _create_category_summary(
            CORE_PACK_ID,
            None,
            category_id,
            status="invalid",
            available_difficulties=supported,
            source_path=file,
        )

        if not supported:
            _add_issue(
                issues,
                "error",
                (
                    f"Categorie integree ignoree: {format_category_name(category_id)} "
                    f"n'atteint aucun niveau jouable ({MIN_WORD_POOL_SIZE} mots minimum)."
                ),
                CORE_PACK_ID,
                file,
            )
            category_summaries.append(category_summary)
            continue

        categories[category_id] = list(result.words)
        display_names[category_id] = _build_display_name(CORE_PACK_ID, None, category_id)
        loaded_category_count += 1
        playable_category_count += 1
        category_summaries.append(replace(category_summary, status="active"))

        if result.duplicate_count:
            _add_issue(
                issues,
                "warning",
                (
                    f"Categorie integree {format_category_name(category_id)}: "
                    f"{result.duplicate_count} doublon(s) ont ete ignores apres normalisation."
                ),
                CORE_PACK_ID,
                file,
            )
        if supported != DIFFICULTY_LEVELS:
            _add_issue(
                issues,
                "warning",
                (
                    f"Categorie integree {format_category_name(category_id)}: "
                    f"niveaux disponibles {', '.join(supported)}."
                ),
                CORE_PACK_ID,
                file,
            )

    status = "active" if loaded_category_count else "invalid"
    if not source_files:
        _add_issue(
            issues,
            "error",
            "Aucune categorie integree n'a ete trouvee dans les ressources du jeu.",
            CORE_PACK_ID,
            base_dir,
        )

    return PackSummary(
        pack_id=CORE_PACK_ID,
        label="Catalogue integre",
        origin="builtin",
        status=status,
        source_path=str(base_dir),
        category_count=len(source_files),
        loaded_category_count=loaded_category_count,
        declared_enabled=True,
        effective_enabled=True,
        playable_category_count=playable_category_count,
        categories=tuple(category_summaries),
    )


def _load_manifest(manifest_path, issues):
    try:
        with Path(manifest_path).open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except json.JSONDecodeError as exc:
        _add_issue(
            issues,
            "error",
            f"Manifest invalide: JSON illisible ({exc.msg}).",
            Path(manifest_path).parent.name,
            manifest_path,
        )
        return None
    except OSError as exc:
        _add_issue(
            issues,
            "error",
            f"Manifest introuvable ou inaccessible: {exc}.",
            Path(manifest_path).parent.name,
            manifest_path,
        )
        return None

    if not isinstance(manifest, dict):
        _add_issue(
            issues,
            "error",
            "Manifest invalide: l'objet racine doit etre un dictionnaire JSON.",
            Path(manifest_path).parent.name,
            manifest_path,
        )
        return None

    return manifest


def _load_local_pack(
    manifest_path,
    seen_pack_ids,
    categories,
    display_names,
    issues,
    *,
    pack_overrides=None,
):
    manifest_path = Path(manifest_path)
    manifest = _load_manifest(manifest_path, issues)
    fallback_pack_id = _normalize_identifier(manifest_path.parent.name)

    if manifest is None:
        return PackSummary(
            pack_id=fallback_pack_id or "pack_invalide",
            label=_format_token(fallback_pack_id or "pack_invalide"),
            origin="local",
            status="invalid",
            source_path=str(manifest_path),
            category_count=0,
            loaded_category_count=0,
            declared_enabled=False,
            effective_enabled=False,
            playable_category_count=0,
        )

    pack_id = _normalize_identifier(manifest.get("id"))
    if not pack_id or not _is_valid_identifier(pack_id):
        _add_issue(
            issues,
            "error",
            "Pack invalide: le champ 'id' est requis (ascii minuscule, chiffres et underscore).",
            fallback_pack_id or "pack_invalide",
            manifest_path,
        )
        return PackSummary(
            pack_id=fallback_pack_id or "pack_invalide",
            label=_format_token(fallback_pack_id or "pack_invalide"),
            origin="local",
            status="invalid",
            source_path=str(manifest_path),
            category_count=0,
            loaded_category_count=0,
            declared_enabled=False,
            effective_enabled=False,
            playable_category_count=0,
        )

    if pack_id in seen_pack_ids:
        _add_issue(
            issues,
            "error",
            f"Pack ignore: l'identifiant '{pack_id}' est deja charge.",
            pack_id,
            manifest_path,
        )
        return PackSummary(
            pack_id=pack_id,
            label=str(manifest.get("label") or _format_token(pack_id)),
            origin="local",
            status="invalid",
            source_path=str(manifest_path),
            category_count=0,
            loaded_category_count=0,
            declared_enabled=False,
            effective_enabled=False,
            playable_category_count=0,
        )

    seen_pack_ids.add(pack_id)
    pack_label = str(manifest.get("label") or _format_token(pack_id)).strip()
    declared_enabled = manifest.get("enabled", True)
    if not isinstance(declared_enabled, bool):
        _add_issue(
            issues,
            "error",
            "Pack invalide: le champ 'enabled' doit etre un booleen.",
            pack_id,
            manifest_path,
        )
        return PackSummary(
            pack_id=pack_id,
            label=pack_label,
            origin="local",
            status="invalid",
            source_path=str(manifest_path),
            category_count=0,
            loaded_category_count=0,
            declared_enabled=False,
            effective_enabled=False,
            playable_category_count=0,
        )

    categories_spec = manifest.get("categories")
    if not isinstance(categories_spec, list) or not categories_spec:
        _add_issue(
            issues,
            "error",
            "Pack invalide: le champ 'categories' doit contenir au moins une categorie.",
            pack_id,
            manifest_path,
        )
        return PackSummary(
            pack_id=pack_id,
            label=pack_label,
            origin="local",
            status="invalid",
            source_path=str(manifest_path),
            category_count=0,
            loaded_category_count=0,
            declared_enabled=declared_enabled,
            effective_enabled=False,
            playable_category_count=0,
        )

    effective_enabled = _resolve_effective_pack_enabled(pack_id, declared_enabled, pack_overrides)

    loaded_category_count = 0
    playable_category_count = 0
    seen_category_ids = set()
    category_summaries = []

    for entry in categories_spec:
        if not isinstance(entry, dict):
            _add_issue(
                issues,
                "error",
                "Categorie ignoree: chaque entree doit etre un objet JSON.",
                pack_id,
                manifest_path,
            )
            continue

        category_id = _normalize_identifier(entry.get("id") or entry.get("key"))
        if not category_id or not _is_valid_identifier(category_id):
            _add_issue(
                issues,
                "error",
                "Categorie ignoree: le champ 'id' (ou 'key') est requis.",
                pack_id,
                manifest_path,
            )
            continue

        if category_id in seen_category_ids:
            _add_issue(
                issues,
                "error",
                f"Categorie ignoree: l'identifiant '{category_id}' est duplique dans le pack.",
                pack_id,
                manifest_path,
            )
            continue
        seen_category_ids.add(category_id)

        category_enabled = entry.get("enabled", True)
        if not isinstance(category_enabled, bool):
            _add_issue(
                issues,
                "error",
                f"Categorie ignoree: le champ 'enabled' de '{category_id}' doit etre un booleen.",
                pack_id,
                manifest_path,
            )
            continue

        source = entry.get("source")
        if not isinstance(source, str) or not source.strip():
            _add_issue(
                issues,
                "error",
                f"Categorie ignoree: '{category_id}' doit declarer un fichier 'source'.",
                pack_id,
                manifest_path,
            )
            category_summaries.append(
                _create_category_summary(
                    pack_id,
                    pack_label,
                    category_id,
                    category_label=entry.get("label"),
                    status="invalid",
                    source_path=manifest_path,
                )
            )
            continue

        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = manifest_path.parent / source_path
        if not source_path.exists():
            _add_issue(
                issues,
                "error",
                f"Categorie ignoree: fichier introuvable pour '{category_id}' ({source}).",
                pack_id,
                manifest_path,
            )
            category_summaries.append(
                _create_category_summary(
                    pack_id,
                    pack_label,
                    category_id,
                    category_label=entry.get("label"),
                    status="invalid",
                    source_path=source_path,
                )
            )
            continue

        result = _read_word_list(source_path)
        supported = get_supported_difficulties(result.words)
        category_key = _build_category_key(pack_id, category_id)
        category_label = _build_display_name(
            pack_id,
            pack_label,
            category_id,
            entry.get("label"),
        )
        if not supported:
            _add_issue(
                issues,
                "error",
                (
                    f"Categorie ignoree: {format_category_name(category_key)} "
                    f"n'atteint aucun niveau jouable ({MIN_WORD_POOL_SIZE} mots minimum)."
                ),
                pack_id,
                source_path,
            )
            category_summaries.append(
                _create_category_summary(
                    pack_id,
                    pack_label,
                    category_id,
                    category_label=entry.get("label"),
                    status="invalid",
                    source_path=source_path,
                )
            )
            continue

        if category_enabled:
            playable_category_count += 1

        category_status = "disabled"
        if category_enabled and effective_enabled:
            category_status = "active"
            categories[category_key] = list(result.words)
            display_names[category_key] = category_label
            loaded_category_count += 1

        category_summaries.append(
            CategorySummary(
                category_key=category_key,
                label=category_label,
                status=category_status,
                available_difficulties=tuple(supported),
                source_path=str(source_path),
            )
        )

        if result.duplicate_count:
            _add_issue(
                issues,
                "warning",
                (
                    f"Categorie {category_label}: "
                    f"{result.duplicate_count} doublon(s) ont ete ignores apres normalisation."
                ),
                pack_id,
                source_path,
            )
        if supported != DIFFICULTY_LEVELS:
            _add_issue(
                issues,
                "warning",
                (
                    f"Categorie {category_label}: "
                    f"niveaux disponibles {', '.join(supported)}."
                ),
                pack_id,
                source_path,
            )

    if playable_category_count:
        status = "active" if effective_enabled else "disabled"
    else:
        status = "disabled" if category_summaries and all(
            category.status == "disabled" for category in category_summaries
        ) else "invalid"

    return PackSummary(
        pack_id=pack_id,
        label=pack_label,
        origin="local",
        status=status,
        source_path=str(manifest_path),
        category_count=len(categories_spec),
        loaded_category_count=loaded_category_count,
        declared_enabled=declared_enabled,
        effective_enabled=effective_enabled,
        playable_category_count=playable_category_count,
        categories=tuple(category_summaries),
    )


def _finalize_pack_summaries(pack_summaries, issues):
    issue_counts = Counter(issue.pack_id for issue in issues)
    return tuple(
        replace(pack_summary, issue_count=issue_counts.get(pack_summary.pack_id, 0))
        for pack_summary in pack_summaries
    )


def load_category_catalog(base_dir=BASE_DIR, *, local_pack_dir=None, pack_overrides=None):
    categories = {}
    display_names = {}
    issues = []
    pack_summaries = []
    seen_pack_ids = {CORE_PACK_ID}
    normalized_overrides = _normalize_pack_overrides(pack_overrides)

    pack_summaries.append(_load_core_pack(base_dir, categories, display_names, issues))

    pack_root = None
    if local_pack_dir is not None:
        pack_root = Path(local_pack_dir)
        if pack_root.exists():
            manifest_paths = sorted(pack_root.glob(f"*/{PACK_MANIFEST_NAME}"))
            for manifest_path in manifest_paths:
                pack_summaries.append(
                    _load_local_pack(
                        manifest_path,
                        seen_pack_ids,
                        categories,
                        display_names,
                        issues,
                        pack_overrides=normalized_overrides,
                    )
                )

    return CategoryCatalog(
        categories=categories,
        display_names=display_names,
        pack_summaries=_finalize_pack_summaries(pack_summaries, issues),
        issues=tuple(issues),
        local_pack_dir=pack_root,
    )


def load_runtime_category_catalog(base_dir=BASE_DIR, *, local_pack_dir=None, pack_overrides=None):
    return load_category_catalog(
        base_dir,
        local_pack_dir=get_word_packs_directory() if local_pack_dir is None else local_pack_dir,
        pack_overrides=pack_overrides,
    )


def inspect_local_pack(manifest_path, *, pack_overrides=None):
    categories = {}
    display_names = {}
    issues = []
    pack_summary = _load_local_pack(
        manifest_path,
        {CORE_PACK_ID},
        categories,
        display_names,
        issues,
        pack_overrides=_normalize_pack_overrides(pack_overrides),
    )
    return CategoryCatalog(
        categories=categories,
        display_names=display_names,
        pack_summaries=_finalize_pack_summaries([pack_summary], issues),
        issues=tuple(issues),
        local_pack_dir=Path(manifest_path).parent.parent,
    )


def load_categories(base_dir=BASE_DIR):
    return load_category_catalog(base_dir).categories

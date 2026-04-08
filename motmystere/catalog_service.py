import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .app_paths import (
    get_catalog_state_path,
    get_official_pack_index_path,
    get_word_packs_directory,
)
from .archive_utils import ArchiveInspectionError, extract_archive_to_staging
from .categories import (
    BASE_DIR,
    CORE_PACK_ID,
    PACK_MANIFEST_NAME,
    CategorySummary,
    PackSummary,
    inspect_local_pack,
    load_runtime_category_catalog,
)


class CatalogServiceError(ValueError):
    pass


def _default_catalog_state():
    return {"pack_overrides": {}}


def _normalize_catalog_state(raw_state):
    state = _default_catalog_state()
    if not isinstance(raw_state, dict):
        return state

    pack_overrides = raw_state.get("pack_overrides")
    if not isinstance(pack_overrides, dict):
        return state

    normalized_overrides = {}
    for pack_id, override in pack_overrides.items():
        if not isinstance(pack_id, str) or not isinstance(override, dict):
            continue
        enabled = override.get("enabled")
        if isinstance(enabled, bool):
            normalized_overrides[pack_id.strip().lower().replace("-", "_").replace(" ", "_")] = {
                "enabled": enabled
            }

    state["pack_overrides"] = normalized_overrides
    return state


def _dedupe_messages(messages):
    seen = set()
    deduped = []
    for message in messages:
        normalized = str(message).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return tuple(deduped)


def _summarize_issues(issues, *, severities=None, limit=None):
    severity_filter = set(severities) if severities is not None else None
    messages = []
    for issue in issues:
        if severity_filter is not None and issue.severity not in severity_filter:
            continue
        messages.append(issue.message)
    deduped = list(_dedupe_messages(messages))
    if limit is not None:
        return tuple(deduped[:limit])
    return tuple(deduped)


def _build_placeholder_pack(source_path, *, source_kind):
    source_path = Path(source_path)
    raw_name = source_path.stem if source_path.is_file() else source_path.name
    normalized_pack_id = str(raw_name or "pack_invalide").strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized_pack_id:
        normalized_pack_id = "pack_invalide"
    label = str(raw_name or "Pack invalide").strip() or "Pack invalide"
    return PackSummary(
        pack_id=normalized_pack_id,
        label=label,
        origin="local",
        status="invalid",
        source_path=str(source_path),
        category_count=0,
        loaded_category_count=0,
        declared_enabled=False,
        effective_enabled=False,
        playable_category_count=0,
        categories=(),
    )


@dataclass(frozen=True)
class OfficialPackInfo:
    pack_id: str
    label: str
    description: str
    archive_name: str
    archive_path: str
    category_labels: tuple
    installed: bool


@dataclass(frozen=True)
class PackImportPreview:
    source_path: str
    source_kind: str
    inspected_pack: PackSummary
    installable: bool
    blockers: tuple
    alerts: tuple
    categories_added: tuple
    playable_after_activation: tuple
    installed_non_playable_categories: tuple
    effect_when_enabled: PackSummary
    effect_when_disabled: PackSummary

    @property
    def pack_id(self):
        return self.inspected_pack.pack_id

    @property
    def pack_label(self):
        return self.inspected_pack.label


@dataclass(frozen=True)
class _PreparedPackSource:
    source_path: Path
    source_kind: str
    pack_root: Path
    manifest_path: Path


class CatalogService:
    def __init__(self, *, base_dir=BASE_DIR, pack_dir=None, state_path=None):
        self.base_dir = Path(base_dir)
        self.pack_dir = Path(pack_dir) if pack_dir is not None else get_word_packs_directory()
        self.state_path = Path(state_path) if state_path is not None else get_catalog_state_path()

    def load_state(self):
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                raw_state = json.load(handle)
        except FileNotFoundError:
            return _default_catalog_state()
        except (json.JSONDecodeError, OSError):
            return _default_catalog_state()

        return _normalize_catalog_state(raw_state)

    def save_state(self, state):
        normalized_state = _normalize_catalog_state(state)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as handle:
            json.dump(normalized_state, handle, ensure_ascii=True, indent=2)
        return normalized_state

    def load_catalog(self):
        state = self.load_state()
        return load_runtime_category_catalog(
            self.base_dir,
            local_pack_dir=self.pack_dir,
            pack_overrides=state["pack_overrides"],
        )

    def list_official_packs(self):
        index_path = get_official_pack_index_path()
        try:
            raw_index = json.loads(index_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ()
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogServiceError(f"Index des packs officiels illisible: {exc}") from exc

        raw_packs = raw_index.get("packs")
        if not isinstance(raw_packs, list):
            raise CatalogServiceError("L'index des packs officiels est invalide.")

        installed_pack_ids = {
            pack.pack_id
            for pack in self.load_catalog().pack_summaries
            if pack.origin == "local"
        }
        official_packs = []
        for raw_pack in raw_packs:
            if not isinstance(raw_pack, dict):
                raise CatalogServiceError("L'index des packs officiels contient une entree invalide.")

            pack_id = str(raw_pack.get("id") or "").strip()
            label = str(raw_pack.get("label") or "").strip()
            archive_name = str(raw_pack.get("archive") or "").strip()
            description = str(raw_pack.get("description") or "").strip()
            raw_categories = raw_pack.get("categories") or ()
            if not pack_id or not label or not archive_name or not isinstance(raw_categories, list):
                raise CatalogServiceError("Une entree de pack officiel est incomplete.")

            archive_path = index_path.parent / archive_name
            if not archive_path.exists():
                raise CatalogServiceError(
                    f"Archive officielle introuvable: {archive_name}."
                )

            category_labels = []
            for raw_category in raw_categories:
                if isinstance(raw_category, dict):
                    category_label = str(raw_category.get("label") or raw_category.get("id") or "").strip()
                else:
                    category_label = str(raw_category or "").strip()
                if category_label:
                    category_labels.append(category_label)

            official_packs.append(
                OfficialPackInfo(
                    pack_id=pack_id,
                    label=label,
                    description=description,
                    archive_name=archive_name,
                    archive_path=str(archive_path),
                    category_labels=tuple(category_labels),
                    installed=pack_id in installed_pack_ids,
                )
            )

        return tuple(official_packs)

    def set_pack_enabled(self, pack_id, enabled):
        catalog = self.load_catalog()
        pack_summary = next((pack for pack in catalog.pack_summaries if pack.pack_id == pack_id), None)

        if pack_summary is None:
            raise CatalogServiceError("Le pack demande est introuvable.")
        if pack_summary.pack_id == CORE_PACK_ID or pack_summary.origin != "local":
            raise CatalogServiceError("Le catalogue integre ne peut pas etre modifie depuis cette vue.")
        if pack_summary.status == "invalid":
            raise CatalogServiceError("Un pack invalide ne peut pas etre active ou desactive.")

        self._persist_pack_enabled_state(
            pack_summary.pack_id,
            declared_enabled=pack_summary.declared_enabled,
            enabled=enabled,
        )

        updated_catalog = self.load_catalog()
        updated_pack = next(pack for pack in updated_catalog.pack_summaries if pack.pack_id == pack_summary.pack_id)
        return updated_catalog, updated_pack

    def inspect_pack_source(self, source_path):
        source_path = Path(source_path).expanduser()
        if not source_path.exists():
            raise CatalogServiceError("La source selectionnee est introuvable.")

        source_kind = self._guess_source_kind(source_path)
        try:
            with self._open_pack_source(source_path) as prepared:
                return self._build_pack_import_preview(prepared)
        except (CatalogServiceError, ArchiveInspectionError) as exc:
            placeholder = _build_placeholder_pack(source_path, source_kind=source_kind)
            return PackImportPreview(
                source_path=str(source_path),
                source_kind=source_kind,
                inspected_pack=placeholder,
                installable=False,
                blockers=(str(exc),),
                alerts=(),
                categories_added=(),
                playable_after_activation=(),
                installed_non_playable_categories=(),
                effect_when_enabled=placeholder,
                effect_when_disabled=placeholder,
            )

    def import_pack_from_source(self, source_path, *, enabled=True):
        source_path = Path(source_path).expanduser()
        if not source_path.exists():
            raise CatalogServiceError("La source selectionnee est introuvable.")

        with self._open_pack_source(source_path) as prepared:
            preview = self._build_pack_import_preview(prepared)
            if not preview.installable:
                detail = " ".join(preview.blockers[:3]) if preview.blockers else "le pack n'est pas exploitable."
                raise CatalogServiceError(f"Import refuse: {detail}".strip())

            destination_dir = self.pack_dir / preview.pack_id
            if destination_dir.exists():
                raise CatalogServiceError(
                    f"Import refuse: le dossier cible '{destination_dir}' existe deja."
                )

            self.pack_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(prepared.pack_root, destination_dir)

        self._persist_pack_enabled_state(
            preview.pack_id,
            declared_enabled=preview.effect_when_enabled.declared_enabled,
            enabled=enabled,
        )

        updated_catalog = self.load_catalog()
        updated_pack = next(pack for pack in updated_catalog.pack_summaries if pack.pack_id == preview.pack_id)
        return updated_catalog, updated_pack

    def import_pack_from_directory(self, source_dir):
        return self.import_pack_from_source(source_dir, enabled=True)

    def _persist_pack_enabled_state(self, pack_id, *, declared_enabled, enabled):
        state = self.load_state()
        pack_overrides = dict(state["pack_overrides"])
        if bool(declared_enabled) == bool(enabled):
            pack_overrides.pop(pack_id, None)
        else:
            pack_overrides[pack_id] = {"enabled": bool(enabled)}
        state["pack_overrides"] = pack_overrides
        self.save_state(state)

    def _guess_source_kind(self, source_path):
        if Path(source_path).is_dir():
            return "directory"
        if Path(source_path).suffix.lower() == ".zip":
            return "zip"
        return "file"

    def _build_pack_import_preview(self, prepared):
        base_inspection = inspect_local_pack(prepared.manifest_path)
        base_pack = base_inspection.pack_summaries[0]
        pack_overrides_enabled = {base_pack.pack_id: {"enabled": True}}
        pack_overrides_disabled = {base_pack.pack_id: {"enabled": False}}

        enabled_inspection = inspect_local_pack(prepared.manifest_path, pack_overrides=pack_overrides_enabled)
        disabled_inspection = inspect_local_pack(prepared.manifest_path, pack_overrides=pack_overrides_disabled)
        enabled_pack = enabled_inspection.pack_summaries[0]
        disabled_pack = disabled_inspection.pack_summaries[0]

        blockers = []
        if enabled_pack.status == "invalid" or enabled_pack.playable_category_count <= 0:
            blocking_messages = _summarize_issues(enabled_inspection.issues, limit=3)
            blockers.extend(blocking_messages or ("Le pack n'est pas exploitable apres inspection.",))

        existing_pack_ids = {pack.pack_id for pack in self.load_catalog().pack_summaries}
        if enabled_pack.pack_id in existing_pack_ids:
            blockers.append(f"Un pack '{enabled_pack.pack_id}' est deja installe.")

        destination_dir = self.pack_dir / enabled_pack.pack_id
        if destination_dir.exists():
            blockers.append(f"Le dossier cible '{destination_dir}' existe deja.")

        alerts = [
            message
            for message in _summarize_issues(enabled_inspection.issues)
            if message not in blockers
        ]
        categories_added = tuple(enabled_pack.categories)
        playable_after_activation = tuple(
            category for category in enabled_pack.categories if category.status == "active"
        )
        installed_non_playable_categories = tuple(
            category for category in enabled_pack.categories if category.status != "active"
        )

        return PackImportPreview(
            source_path=str(prepared.source_path),
            source_kind=prepared.source_kind,
            inspected_pack=enabled_pack,
            installable=not blockers,
            blockers=_dedupe_messages(blockers),
            alerts=_dedupe_messages(alerts),
            categories_added=categories_added,
            playable_after_activation=playable_after_activation,
            installed_non_playable_categories=installed_non_playable_categories,
            effect_when_enabled=enabled_pack,
            effect_when_disabled=disabled_pack,
        )

    def _open_pack_source(self, source_path):
        source_path = Path(source_path).expanduser()
        if source_path.is_dir():
            manifest_path = source_path / PACK_MANIFEST_NAME
            if not manifest_path.exists():
                raise CatalogServiceError("Le dossier selectionne doit contenir un fichier pack.json.")
            return _PreparedPackSourceContext(
                prepared=_PreparedPackSource(
                    source_path=source_path,
                    source_kind="directory",
                    pack_root=source_path,
                    manifest_path=manifest_path,
                )
            )

        if source_path.is_file() and source_path.suffix.lower() == ".zip":
            workspace = self._make_temporary_workspace("motmystere_pack_import_")
            temp_dir = Path(workspace.__enter__())
            try:
                members = extract_archive_to_staging(source_path, temp_dir)
                pack_root, manifest_path = self._resolve_pack_archive_root(temp_dir, members)
                return _PreparedPackSourceContext(
                    prepared=_PreparedPackSource(
                        source_path=source_path,
                        source_kind="zip",
                        pack_root=pack_root,
                        manifest_path=manifest_path,
                    ),
                    workspace=workspace,
                )
            except ArchiveInspectionError as exc:
                workspace.__exit__(None, None, None)
                raise CatalogServiceError(str(exc)) from exc
            except Exception:
                workspace.__exit__(None, None, None)
                raise

        raise CatalogServiceError("La source selectionnee doit etre un dossier de pack ou une archive .zip.")

    def _resolve_pack_archive_root(self, staging_root, members):
        manifest_paths = [path for path in members if path.name == PACK_MANIFEST_NAME]
        if not manifest_paths:
            raise CatalogServiceError("L'archive ne contient pas de pack.json.")
        if len(manifest_paths) > 1:
            raise CatalogServiceError("L'archive contient plusieurs manifests pack.json.")

        manifest_path = manifest_paths[0]
        if manifest_path == PurePosixPath(PACK_MANIFEST_NAME):
            return staging_root, staging_root / PACK_MANIFEST_NAME

        if len(manifest_path.parts) != 2:
            raise CatalogServiceError(
                "L'archive doit contenir pack.json a la racine ou dans un unique dossier racine."
            )

        top_level_root = manifest_path.parts[0]
        if any(path.parts[0] != top_level_root for path in members):
            raise CatalogServiceError(
                "L'archive doit contenir un seul pack et un unique dossier racine."
            )

        pack_root = staging_root / top_level_root
        return pack_root, pack_root / PACK_MANIFEST_NAME

    def _make_temporary_workspace(self, prefix):
        temp_root = self.pack_dir.parent / ".tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        workspace = temp_root / f"{prefix}{uuid.uuid4().hex}"
        workspace.mkdir(parents=True, exist_ok=False)
        return _WorkspaceContext(workspace)


class _PreparedPackSourceContext:
    def __init__(self, *, prepared, workspace=None):
        self.prepared = prepared
        self.workspace = workspace

    def __enter__(self):
        return self.prepared

    def __exit__(self, exc_type, exc, tb):
        if self.workspace is not None:
            self.workspace.__exit__(exc_type, exc, tb)
        return False


class _WorkspaceContext:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        return str(self.path)

    def __exit__(self, exc_type, exc, tb):
        shutil.rmtree(self.path, ignore_errors=True)
        return False

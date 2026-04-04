import json
import shutil
from pathlib import Path

from .app_paths import get_catalog_state_path, get_word_packs_directory
from .categories import (
    BASE_DIR,
    CORE_PACK_ID,
    PACK_MANIFEST_NAME,
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


def _summarize_issues(issues, *, limit=3):
    messages = []
    for issue in issues:
        if issue.message not in messages:
            messages.append(issue.message)
    return messages[:limit]


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

    def set_pack_enabled(self, pack_id, enabled):
        catalog = self.load_catalog()
        pack_summary = next((pack for pack in catalog.pack_summaries if pack.pack_id == pack_id), None)

        if pack_summary is None:
            raise CatalogServiceError("Le pack demande est introuvable.")
        if pack_summary.pack_id == CORE_PACK_ID or pack_summary.origin != "local":
            raise CatalogServiceError("Le catalogue integre ne peut pas etre modifie depuis cette vue.")
        if pack_summary.status == "invalid":
            raise CatalogServiceError("Un pack invalide ne peut pas etre active ou desactive.")

        state = self.load_state()
        pack_overrides = dict(state["pack_overrides"])
        if pack_summary.declared_enabled == bool(enabled):
            pack_overrides.pop(pack_summary.pack_id, None)
        else:
            pack_overrides[pack_summary.pack_id] = {"enabled": bool(enabled)}

        state["pack_overrides"] = pack_overrides
        self.save_state(state)

        updated_catalog = self.load_catalog()
        updated_pack = next(pack for pack in updated_catalog.pack_summaries if pack.pack_id == pack_summary.pack_id)
        return updated_catalog, updated_pack

    def import_pack_from_directory(self, source_dir):
        source_path = Path(source_dir)
        if not source_path.exists() or not source_path.is_dir():
            raise CatalogServiceError("Le dossier selectionne est introuvable.")

        manifest_path = source_path / PACK_MANIFEST_NAME
        if not manifest_path.exists():
            raise CatalogServiceError("Le dossier selectionne doit contenir un fichier pack.json.")

        inspection = inspect_local_pack(manifest_path)
        pack_summary = inspection.pack_summaries[0]
        issues = inspection.issues_by_pack.get(pack_summary.pack_id, inspection.issues)

        if pack_summary.status == "invalid" or pack_summary.playable_category_count <= 0:
            details = " ".join(_summarize_issues(issues))
            raise CatalogServiceError(
                f"Import refuse: le pack n'est pas exploitable. {details}".strip()
            )

        existing_pack_ids = {pack.pack_id for pack in self.load_catalog().pack_summaries}
        if pack_summary.pack_id in existing_pack_ids:
            raise CatalogServiceError(
                f"Import refuse: un pack '{pack_summary.pack_id}' est deja installe."
            )

        destination_dir = self.pack_dir / pack_summary.pack_id
        if destination_dir.exists():
            raise CatalogServiceError(
                f"Import refuse: le dossier cible '{destination_dir}' existe deja."
            )

        self.pack_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_path, destination_dir)

        updated_catalog = self.load_catalog()
        updated_pack = next(pack for pack in updated_catalog.pack_summaries if pack.pack_id == pack_summary.pack_id)
        return updated_catalog, updated_pack

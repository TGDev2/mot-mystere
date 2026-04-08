from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import uuid
import zipfile

from .archive_utils import ArchiveInspectionError, extract_archive_to_staging
from .app_paths import (
    APP_NAME,
    get_backup_directory,
    get_catalog_state_path,
    get_data_directory,
    get_database_path,
    get_word_packs_directory,
)
from .catalog_service import CatalogService
from .categories import BASE_DIR, CORE_PACK_ID
from .database import get_leaderboard_data, get_player_dashboard, get_recent_players, setup_database


DEFAULT_CATALOG_STATE = {"pack_overrides": {}}


class BackupServiceError(ValueError):
    pass


class BackupService:
    BACKUP_FORMAT_VERSION = 1
    MANIFEST_NAME = "manifest.json"
    DATABASE_ARCHIVE_PATH = PurePosixPath("db/hangman.db")
    CATALOG_STATE_ARCHIVE_PATH = PurePosixPath("data/catalog_state.json")
    PACKS_ARCHIVE_ROOT = PurePosixPath("packs")
    EXPECTED_LOGICAL_TARGETS = {
        "database": str(DATABASE_ARCHIVE_PATH),
        "catalog_state": str(CATALOG_STATE_ARCHIVE_PATH),
        "packs": "packs/",
    }
    ALLOWED_ARCHIVE_ROOTS = frozenset(
        {
            MANIFEST_NAME,
            DATABASE_ARCHIVE_PATH.parts[0],
            CATALOG_STATE_ARCHIVE_PATH.parts[0],
            PACKS_ARCHIVE_ROOT.parts[0],
        }
    )

    def __init__(
        self,
        *,
        db_path=None,
        data_dir=None,
        state_path=None,
        packs_dir=None,
        backup_dir=None,
        base_dir=BASE_DIR,
    ):
        self.data_dir = Path(data_dir).expanduser() if data_dir is not None else get_data_directory()
        default_db_path = self.data_dir / "hangman.db" if data_dir is not None else get_database_path()
        default_state_path = (
            self.data_dir / "catalog_state.json" if data_dir is not None else get_catalog_state_path()
        )
        default_packs_dir = self.data_dir / "packs" if data_dir is not None else get_word_packs_directory()

        self.db_path = Path(db_path).expanduser() if db_path is not None else default_db_path
        self.state_path = Path(state_path).expanduser() if state_path is not None else default_state_path
        self.packs_dir = Path(packs_dir).expanduser() if packs_dir is not None else default_packs_dir
        self.backup_dir = (
            Path(backup_dir).expanduser()
            if backup_dir is not None
            else get_backup_directory(self.data_dir)
        )
        self.base_dir = Path(base_dir)

    def build_backup_archive_path(self, *, prefix="motmystere_backup", timestamp=None):
        safe_prefix = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in prefix)
        if not safe_prefix:
            safe_prefix = "motmystere_backup"

        stamp = (
            str(timestamp)
            if timestamp is not None
            else datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        candidate = self.backup_dir / f"{safe_prefix}_{stamp}.zip"
        suffix = 1
        while candidate.exists():
            candidate = self.backup_dir / f"{safe_prefix}_{stamp}_{suffix}.zip"
            suffix += 1
        return candidate

    def has_managed_data(self):
        return (
            self._database_has_content()
            or self._catalog_state_has_content()
            or self._packs_dir_has_content()
        )

    def export_archive(self, destination_path):
        destination = Path(destination_path).expanduser()
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with self._make_temporary_workspace("motmystere_backup_export_") as temp_dir:
                staging_root = Path(temp_dir)
                includes = self._stage_current_environment(staging_root)
                manifest = self._build_manifest(includes)
                (staging_root / self.MANIFEST_NAME).write_text(
                    json.dumps(manifest, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
                self._write_archive_from_staging(staging_root, destination)
        except (OSError, sqlite3.Error, json.JSONDecodeError, ValueError) as exc:
            raise BackupServiceError(
                f"Export impossible: {exc}"
            ) from exc

        return {
            "archive_path": str(destination),
            "includes": dict(includes),
            "logical_targets": dict(self.EXPECTED_LOGICAL_TARGETS),
            "backup_format_version": self.BACKUP_FORMAT_VERSION,
        }

    def import_archive(self, archive_path, *, backup_path=None):
        source_archive = Path(archive_path).expanduser()
        if not source_archive.exists() or not source_archive.is_file():
            raise BackupServiceError("Le fichier de sauvegarde selectionne est introuvable.")

        with self._make_temporary_workspace("motmystere_backup_import_") as temp_dir:
            staging_root = Path(temp_dir)
            manifest = self._extract_archive_to_staging(source_archive, staging_root)
            staged_db_path = staging_root / self.DATABASE_ARCHIVE_PATH
            staged_state_path = staging_root / self.CATALOG_STATE_ARCHIVE_PATH
            staged_packs_dir = staging_root / self.PACKS_ARCHIVE_ROOT

            self._validate_staged_payload(
                manifest,
                staged_db_path=staged_db_path,
                staged_state_path=staged_state_path,
                staged_packs_dir=staged_packs_dir,
            )

            rescue_backup_path = None
            if self.has_managed_data():
                rescue_backup_path = (
                    Path(backup_path).expanduser()
                    if backup_path is not None
                    else self.build_backup_archive_path(prefix="motmystere_pre_restore")
                )
                self.export_archive(rescue_backup_path)

            self._apply_restore(
                staged_db_path=staged_db_path,
                staged_state_path=staged_state_path if staged_state_path.exists() else None,
                staged_packs_dir=staged_packs_dir if self._directory_has_files(staged_packs_dir) else None,
            )

        return {
            "archive_path": str(source_archive),
            "backup_path": str(rescue_backup_path) if rescue_backup_path is not None else None,
            "includes": dict(manifest["includes"]),
            "logical_targets": dict(manifest["logical_targets"]),
            "backup_format_version": int(manifest["backup_format_version"]),
        }

    def _stage_current_environment(self, staging_root):
        includes = {
            "database": True,
            "catalog_state": False,
            "packs": False,
        }

        staged_db_path = staging_root / self.DATABASE_ARCHIVE_PATH
        staged_db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            shutil.copy2(self.db_path, staged_db_path)
        else:
            setup_database(staged_db_path)

        if self.state_path.exists():
            staged_state_path = staging_root / self.CATALOG_STATE_ARCHIVE_PATH
            staged_state_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.state_path, staged_state_path)
            includes["catalog_state"] = True

        if self._directory_has_files(self.packs_dir):
            staged_packs_dir = staging_root / self.PACKS_ARCHIVE_ROOT
            shutil.copytree(self.packs_dir, staged_packs_dir)
            includes["packs"] = True

        return includes

    def _build_manifest(self, includes):
        return {
            "app_name": APP_NAME,
            "backup_format_version": self.BACKUP_FORMAT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "includes": {
                "database": True,
                "catalog_state": bool(includes.get("catalog_state")),
                "packs": bool(includes.get("packs")),
            },
            "logical_targets": dict(self.EXPECTED_LOGICAL_TARGETS),
        }

    def _write_archive_from_staging(self, staging_root, destination):
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging_root.rglob("*")):
                if not path.is_file():
                    continue
                archive.write(path, arcname=path.relative_to(staging_root).as_posix())

    def _extract_archive_to_staging(self, archive_path, staging_root):
        try:
            normalized_names = extract_archive_to_staging(archive_path, staging_root)
            has_manifest = False
            for normalized_name in normalized_names:
                top_level = normalized_name.parts[0]
                if top_level not in self.ALLOWED_ARCHIVE_ROOTS:
                    raise BackupServiceError(
                        f"La sauvegarde contient un contenu inattendu: {normalized_name.as_posix()}."
                    )
                if normalized_name == PurePosixPath(self.MANIFEST_NAME):
                    has_manifest = True
                elif top_level == self.MANIFEST_NAME:
                    raise BackupServiceError("La sauvegarde contient un manifest.json mal place.")

            if not has_manifest:
                raise BackupServiceError("La sauvegarde ne contient pas de manifest.json.")
        except BackupServiceError:
            raise
        except ArchiveInspectionError as exc:
            raise BackupServiceError(str(exc)) from exc

        manifest_path = staging_root / self.MANIFEST_NAME
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupServiceError("Le manifest.json de la sauvegarde est invalide.") from exc

        return self._validate_manifest(manifest)

    def _validate_manifest(self, manifest):
        if not isinstance(manifest, dict):
            raise BackupServiceError("Le manifest.json doit etre un objet JSON.")
        if str(manifest.get("app_name") or "").strip() != APP_NAME:
            raise BackupServiceError("La sauvegarde ne correspond pas a MotMystere.")

        try:
            format_version = int(manifest.get("backup_format_version"))
        except (TypeError, ValueError) as exc:
            raise BackupServiceError("La sauvegarde ne declare pas de version compatible.") from exc
        if format_version != self.BACKUP_FORMAT_VERSION:
            raise BackupServiceError(
                f"Version de sauvegarde non supportee: {format_version}."
            )

        exported_at = str(manifest.get("exported_at") or "").strip()
        if not exported_at:
            raise BackupServiceError("La sauvegarde ne declare pas de date d'export.")

        includes = manifest.get("includes")
        if not isinstance(includes, dict):
            raise BackupServiceError("Le manifest.json doit declarer les contenus exportes.")
        if not isinstance(includes.get("database"), bool):
            raise BackupServiceError("Le manifest.json doit indiquer si la base est incluse.")
        if "catalog_state" in includes and not isinstance(includes.get("catalog_state"), bool):
            raise BackupServiceError("Le manifest.json doit indiquer si l'etat catalogue est inclus.")
        if "packs" in includes and not isinstance(includes.get("packs"), bool):
            raise BackupServiceError("Le manifest.json doit indiquer si les packs sont inclus.")

        normalized_includes = {
            "database": includes.get("database"),
            "catalog_state": bool(includes.get("catalog_state", False)),
            "packs": bool(includes.get("packs", False)),
        }
        if not normalized_includes["database"]:
            raise BackupServiceError("La sauvegarde doit contenir une base de donnees.")

        logical_targets = manifest.get("logical_targets")
        if not isinstance(logical_targets, dict):
            raise BackupServiceError("Le manifest.json doit declarer les cibles logiques.")
        if logical_targets != self.EXPECTED_LOGICAL_TARGETS:
            raise BackupServiceError("La sauvegarde declare des cibles logiques incompatibles.")

        return {
            "app_name": APP_NAME,
            "backup_format_version": format_version,
            "exported_at": exported_at,
            "includes": normalized_includes,
            "logical_targets": dict(logical_targets),
        }

    def _validate_staged_payload(self, manifest, *, staged_db_path, staged_state_path, staged_packs_dir):
        if not staged_db_path.exists():
            raise BackupServiceError("La sauvegarde ne contient pas la base obligatoire.")

        state_exists = staged_state_path.exists()
        packs_exist = self._directory_has_files(staged_packs_dir)
        if manifest["includes"]["catalog_state"] != state_exists:
            raise BackupServiceError("Le manifest.json est incoherent sur l'etat du catalogue.")
        if manifest["includes"]["packs"] != packs_exist:
            raise BackupServiceError("Le manifest.json est incoherent sur les packs locaux.")

        self._validate_staged_database(staged_db_path)
        self._validate_staged_catalog(staged_state_path, staged_packs_dir)

    def _validate_staged_database(self, staged_db_path):
        try:
            setup_database(staged_db_path)
            recent_players = get_recent_players(db_path=staged_db_path)
            get_leaderboard_data(db_path=staged_db_path)
            if recent_players:
                get_player_dashboard(recent_players[0]["id"], db_path=staged_db_path)
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise BackupServiceError(
                f"Base de sauvegarde invalide ou illisible: {exc}"
            ) from exc

    def _validate_staged_catalog(self, staged_state_path, staged_packs_dir):
        if staged_state_path.exists():
            self._validate_catalog_state_payload(staged_state_path)

        service = CatalogService(
            base_dir=self.base_dir,
            pack_dir=staged_packs_dir,
            state_path=staged_state_path,
        )
        catalog = service.load_catalog()
        invalid_local_packs = [
            pack.label
            for pack in catalog.pack_summaries
            if pack.origin == "local" and pack.status == "invalid"
        ]
        if invalid_local_packs:
            labels = ", ".join(sorted(invalid_local_packs))
            raise BackupServiceError(
                f"La sauvegarde contient des packs locaux invalides: {labels}."
            )

        blocking_issues = [
            issue.message
            for issue in catalog.issues
            if issue.pack_id != CORE_PACK_ID
        ]
        if blocking_issues:
            raise BackupServiceError(
                f"La sauvegarde contient un catalogue local incoherent: {blocking_issues[0]}"
            )

    def _validate_catalog_state_payload(self, state_path):
        try:
            raw_state = json.loads(Path(state_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupServiceError("Le fichier catalog_state.json de la sauvegarde est invalide.") from exc

        if not isinstance(raw_state, dict):
            raise BackupServiceError("Le fichier catalog_state.json doit contenir un objet JSON.")

        raw_overrides = raw_state.get("pack_overrides", {})
        if raw_overrides is None:
            raw_overrides = {}
        if not isinstance(raw_overrides, dict):
            raise BackupServiceError("Le fichier catalog_state.json contient des overrides invalides.")

        normalized_overrides = {}
        for raw_pack_id, raw_override in raw_overrides.items():
            if not isinstance(raw_pack_id, str) or not isinstance(raw_override, dict):
                raise BackupServiceError("Le fichier catalog_state.json contient un pack override invalide.")
            enabled = raw_override.get("enabled")
            if not isinstance(enabled, bool):
                raise BackupServiceError("Le fichier catalog_state.json contient un flag enabled invalide.")
            normalized_pack_id = raw_pack_id.strip().lower().replace("-", "_").replace(" ", "_")
            if not normalized_pack_id:
                raise BackupServiceError("Le fichier catalog_state.json contient un pack override vide.")
            normalized_overrides[normalized_pack_id] = {"enabled": enabled}

        return {"pack_overrides": normalized_overrides}

    def _apply_restore(self, *, staged_db_path, staged_state_path, staged_packs_dir):
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged_db_path, self.db_path)

            if staged_state_path is not None:
                self.state_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged_state_path, self.state_path)
            else:
                self._remove_path(self.state_path)

            self._remove_path(self.packs_dir)
            if staged_packs_dir is not None:
                self.packs_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(staged_packs_dir, self.packs_dir)
        except OSError as exc:
            raise BackupServiceError(f"Restauration impossible: {exc}") from exc

    def _database_has_content(self):
        if not self.db_path.exists():
            return False

        try:
            with closing(sqlite3.connect(str(self.db_path))) as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                tracked_tables = {"players", "game_history", "word_rotation", "stats"} & tables
                for table_name in tracked_tables:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                    if int(count or 0) > 0:
                        return True
        except sqlite3.Error:
            return True

        return False

    def _catalog_state_has_content(self):
        if not self.state_path.exists():
            return False

        try:
            return self._validate_catalog_state_payload(self.state_path) != DEFAULT_CATALOG_STATE
        except BackupServiceError:
            return True

    def _packs_dir_has_content(self):
        return self._directory_has_files(self.packs_dir)

    def _directory_has_files(self, directory):
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return False
        for child in path.rglob("*"):
            if child.is_file():
                return True
        return False

    def _remove_path(self, path):
        target = Path(path)
        if not target.exists():
            return
        if target.is_dir():
            shutil.rmtree(target)
            return
        target.unlink()

    def _make_temporary_workspace(self, prefix):
        temp_root = self.backup_dir / ".tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        workspace = temp_root / f"{prefix}{uuid.uuid4().hex}"
        workspace.mkdir(parents=True, exist_ok=False)
        return _WorkspaceContext(workspace)


class _WorkspaceContext:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        return str(self.path)

    def __exit__(self, exc_type, exc, tb):
        shutil.rmtree(self.path, ignore_errors=True)
        return False

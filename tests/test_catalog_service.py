import json
from pathlib import Path
import shutil
import unittest
import uuid
import zipfile

from motmystere.catalog_service import CatalogService, CatalogServiceError
from motmystere.database import (
    get_or_create_player,
    get_player_dashboard,
    get_word_rotation_state,
    record_game_result,
    save_word_rotation_state,
    setup_database,
)


FULL_SPECTRUM_WORDS = [
    "CHAT",
    "LION",
    "OURS",
    "LOUP",
    "VACHE",
    "RUGBY",
    "TAXIS",
    "BANJO",
    "JOKER",
    "YACHT",
    "KAZAKHSTAN",
    "XYLOPHONE",
    "JURASSIQUE",
    "EQUATEUR",
    "CHOCOLATIER",
]
TOO_SMALL_WORD_POOL = ["CHAT", "LION", "OURS", "LOUP"]


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class CatalogServiceTestCase(unittest.TestCase):
    def _make_workspace(self):
        root_dir = _create_runtime_dir("motmystere_catalog_service_")
        self.addCleanup(lambda: shutil.rmtree(root_dir, ignore_errors=True))
        return root_dir

    def _write_words(self, path, words):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(words) + "\n", encoding="utf-8")

    def _write_json(self, path, payload):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _write_zip(self, path, entries):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for arcname, content in entries.items():
                archive.writestr(arcname, content)

    def _build_pack_archive(self, path, *, root_name=None, pack_id="bonus", words=None):
        words = words or FULL_SPECTRUM_WORDS
        manifest = {
            "id": pack_id,
            "label": "Pack Bonus",
            "categories": [
                {
                    "id": "sports",
                    "label": "Sports",
                    "source": "sports.txt",
                }
            ],
        }
        prefix = f"{root_name}/" if root_name else ""
        self._write_zip(
            path,
            {
                f"{prefix}pack.json": json.dumps(manifest, ensure_ascii=True, indent=2),
                f"{prefix}sports.txt": "\n".join(words) + "\n",
            },
        )

    def _build_service(self, root_dir):
        base_dir = root_dir / "base"
        pack_dir = root_dir / "installed_packs"
        state_path = root_dir / "catalog_state.json"
        base_dir.mkdir()
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)
        return CatalogService(
            base_dir=base_dir,
            pack_dir=pack_dir,
            state_path=state_path,
        )

    def test_import_valid_pack_copies_directory_and_reloads_catalog(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)

        source_pack_dir = root_dir / "source_pack"
        source_pack_dir.mkdir()
        self._write_words(source_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            source_pack_dir / "pack.json",
            {
                "id": "bonus",
                "label": "Pack Bonus",
                "categories": [
                    {
                        "id": "sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        catalog, pack_summary = service.import_pack_from_directory(source_pack_dir)

        self.assertEqual(pack_summary.pack_id, "bonus")
        self.assertTrue((root_dir / "installed_packs" / "bonus" / "pack.json").exists())
        self.assertIn("bonus::sports", catalog.categories)

    def test_inspect_zip_preview_reports_effects_before_import(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)
        archive_path = root_dir / "bonus.zip"
        self._build_pack_archive(archive_path)

        preview = service.inspect_pack_source(archive_path)

        self.assertTrue(preview.installable)
        self.assertEqual(preview.source_kind, "zip")
        self.assertEqual(preview.pack_id, "bonus")
        self.assertEqual(len(preview.categories_added), 1)
        self.assertEqual(preview.effect_when_enabled.loaded_category_count, 1)
        self.assertEqual(preview.effect_when_disabled.loaded_category_count, 0)
        self.assertEqual(preview.blockers, ())
        self.assertEqual(preview.alerts, ())

    def test_inspect_zip_with_single_root_directory_is_supported(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)
        archive_path = root_dir / "bonus_nested.zip"
        self._build_pack_archive(archive_path, root_name="bonus")

        preview = service.inspect_pack_source(archive_path)

        self.assertTrue(preview.installable)
        self.assertEqual(preview.pack_label, "Pack Bonus")
        self.assertEqual(preview.effect_when_enabled.loaded_category_count, 1)

    def test_inspect_zip_rejects_archive_without_manifest(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)
        archive_path = root_dir / "missing_manifest.zip"
        self._write_zip(archive_path, {"sports.txt": "\n".join(FULL_SPECTRUM_WORDS) + "\n"})

        preview = service.inspect_pack_source(archive_path)

        self.assertFalse(preview.installable)
        self.assertTrue(any("pack.json" in message for message in preview.blockers))

    def test_inspect_zip_rejects_multiple_manifests(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)
        archive_path = root_dir / "multi_pack.zip"
        self._write_zip(
            archive_path,
            {
                "a/pack.json": json.dumps({"id": "a", "categories": [{"id": "sports", "source": "sports.txt"}]}),
                "a/sports.txt": "\n".join(FULL_SPECTRUM_WORDS) + "\n",
                "b/pack.json": json.dumps({"id": "b", "categories": [{"id": "sports", "source": "sports.txt"}]}),
                "b/sports.txt": "\n".join(FULL_SPECTRUM_WORDS) + "\n",
            },
        )

        preview = service.inspect_pack_source(archive_path)

        self.assertFalse(preview.installable)
        self.assertTrue(any("plusieurs manifests" in message for message in preview.blockers))

    def test_inspect_zip_rejects_path_traversal(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)
        archive_path = root_dir / "malicious.zip"
        self._write_zip(
            archive_path,
            {
                "../pack.json": "{}",
                "sports.txt": "\n".join(FULL_SPECTRUM_WORDS) + "\n",
            },
        )

        preview = service.inspect_pack_source(archive_path)

        self.assertFalse(preview.installable)
        self.assertTrue(any("chemin relatif interdit" in message.lower() for message in preview.blockers))

    def test_preview_rejects_duplicate_pack_id_before_import(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)

        installed_pack_dir = root_dir / "installed_packs" / "bonus"
        installed_pack_dir.mkdir(parents=True)
        self._write_words(installed_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            installed_pack_dir / "pack.json",
            {
                "id": "bonus",
                "categories": [
                    {
                        "id": "sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        archive_path = root_dir / "bonus.zip"
        self._build_pack_archive(archive_path, pack_id="bonus")

        preview = service.inspect_pack_source(archive_path)

        self.assertFalse(preview.installable)
        self.assertTrue(any("deja installe" in message for message in preview.blockers))

    def test_import_rejects_directory_without_manifest(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)

        source_pack_dir = root_dir / "source_pack"
        source_pack_dir.mkdir()

        with self.assertRaises(CatalogServiceError):
            service.import_pack_from_directory(source_pack_dir)

    def test_import_rejects_duplicate_pack_id(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)

        installed_pack_dir = root_dir / "installed_packs" / "bonus"
        installed_pack_dir.mkdir(parents=True)
        self._write_words(installed_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            installed_pack_dir / "pack.json",
            {
                "id": "bonus",
                "categories": [
                    {
                        "id": "sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        archive_path = root_dir / "bonus.zip"
        self._build_pack_archive(archive_path, pack_id="bonus")

        with self.assertRaises(CatalogServiceError):
            service.import_pack_from_source(archive_path)

    def test_import_rejects_pack_without_playable_category(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)

        source_pack_dir = root_dir / "source_pack"
        source_pack_dir.mkdir()
        self._write_words(source_pack_dir / "sports.txt", TOO_SMALL_WORD_POOL)
        self._write_json(
            source_pack_dir / "pack.json",
            {
                "id": "bonus",
                "categories": [
                    {
                        "id": "sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        with self.assertRaises(CatalogServiceError):
            service.import_pack_from_directory(source_pack_dir)

    def test_import_from_source_can_install_without_activation(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)
        archive_path = root_dir / "bonus.zip"
        self._build_pack_archive(archive_path)

        catalog, pack_summary = service.import_pack_from_source(archive_path, enabled=False)

        self.assertEqual(pack_summary.status, "disabled")
        self.assertFalse(pack_summary.effective_enabled)
        self.assertNotIn("bonus::sports", catalog.categories)

        state = json.loads((root_dir / "catalog_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state, {"pack_overrides": {"bonus": {"enabled": False}}})

    def test_import_does_not_mutate_existing_database_content(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)
        db_path = root_dir / "runtime.db"
        setup_database(db_path)
        player = get_or_create_player("Alice", db_path=db_path)
        record_game_result(
            player["id"],
            won=True,
            score_earned=140,
            category="animaux",
            difficulty="Facile",
            secret_word="CHAT",
            end_reason="won",
            attempts_left=8,
            time_remaining=33,
            word_complexity=20,
            db_path=db_path,
        )
        save_word_rotation_state(
            player["id"],
            "animaux",
            "Facile",
            ["LION", "OURS"],
            last_word="CHAT",
            db_path=db_path,
        )

        archive_path = root_dir / "bonus.zip"
        self._build_pack_archive(archive_path)
        service.import_pack_from_source(archive_path, enabled=True)

        dashboard = get_player_dashboard(player["id"], db_path=db_path)
        rotation = get_word_rotation_state(player["id"], "animaux", "Facile", db_path=db_path)

        self.assertEqual(dashboard["overview"]["games_recorded"], 1)
        self.assertEqual(rotation["remaining_words"], ["LION", "OURS"])
        self.assertEqual(rotation["last_word"], "CHAT")

    def test_set_pack_enabled_persists_override_state(self):
        root_dir = self._make_workspace()
        service = self._build_service(root_dir)

        installed_pack_dir = root_dir / "installed_packs" / "bonus"
        installed_pack_dir.mkdir(parents=True)
        self._write_words(installed_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            installed_pack_dir / "pack.json",
            {
                "id": "bonus",
                "categories": [
                    {
                        "id": "sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        catalog, pack_summary = service.set_pack_enabled("bonus", False)

        self.assertEqual(pack_summary.status, "disabled")
        self.assertNotIn("bonus::sports", catalog.categories)

        state = json.loads((root_dir / "catalog_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state, {"pack_overrides": {"bonus": {"enabled": False}}})


if __name__ == "__main__":
    unittest.main()

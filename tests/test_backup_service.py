import json
from pathlib import Path
import shutil
import unittest
import uuid
import zipfile

from motmystere.backup_service import BackupService, BackupServiceError
from motmystere.catalog_service import CatalogService
from motmystere.database import (
    get_leaderboard_data,
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


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class BackupServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = _create_runtime_dir("motmystere_backup_")
        self.addCleanup(shutil.rmtree, self.runtime_dir, True)

    def _write_words(self, path, words):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(words) + "\n", encoding="utf-8")

    def _write_json(self, path, payload):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _make_base_dir(self, root_dir):
        base_dir = root_dir / "base"
        base_dir.mkdir(parents=True, exist_ok=True)
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)
        return base_dir

    def _make_service(self, root_dir):
        base_dir = self._make_base_dir(root_dir)
        return BackupService(
            db_path=root_dir / "db" / "runtime.db",
            data_dir=root_dir / "data",
            backup_dir=root_dir / "backups",
            base_dir=base_dir,
        )

    def _seed_source_environment(self, service):
        setup_database(service.db_path)
        player = get_or_create_player("Alice", db_path=service.db_path)
        record_game_result(
            player["id"],
            won=True,
            score_earned=180,
            category="animaux",
            difficulty="Facile",
            secret_word="CHAT",
            end_reason="won",
            attempts_left=8,
            time_remaining=42,
            word_complexity=20,
            db_path=service.db_path,
        )
        record_game_result(
            player["id"],
            won=False,
            score_earned=0,
            category="animaux",
            difficulty="Moyen",
            secret_word="JOKER",
            end_reason="attempts",
            attempts_left=0,
            time_remaining=11,
            word_complexity=32,
            db_path=service.db_path,
        )
        save_word_rotation_state(
            player["id"],
            "animaux",
            "Facile",
            ["LION", "OURS"],
            last_word="CHAT",
            db_path=service.db_path,
        )

        self._write_json(
            service.state_path,
            {"pack_overrides": {"bonus": {"enabled": False}}},
        )
        pack_dir = service.packs_dir / "bonus"
        self._write_words(pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            pack_dir / "pack.json",
            {
                "id": "bonus",
                "label": "Pack Bonus",
                "categories": [
                    {
                        "id": "sports",
                        "label": "Sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        return player

    def _seed_target_environment(self, service):
        setup_database(service.db_path)
        player = get_or_create_player("Bob", db_path=service.db_path)
        record_game_result(
            player["id"],
            won=True,
            score_earned=95,
            category="animaux",
            difficulty="Facile",
            secret_word="CHAT",
            end_reason="won",
            attempts_left=7,
            time_remaining=30,
            word_complexity=20,
            db_path=service.db_path,
        )
        self._write_json(
            service.state_path,
            {"pack_overrides": {"obsolete": {"enabled": False}}},
        )
        old_pack_dir = service.packs_dir / "obsolete"
        self._write_words(old_pack_dir / "quiz.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            old_pack_dir / "pack.json",
            {
                "id": "obsolete",
                "label": "Pack Obsolete",
                "categories": [
                    {
                        "id": "quiz",
                        "label": "Quiz",
                        "source": "quiz.txt",
                    }
                ],
            },
        )

    def _build_archive(
        self,
        archive_path,
        *,
        db_path,
        state_payload=None,
        pack_entries=None,
        version=1,
        extra_entries=None,
    ):
        pack_entries = dict(pack_entries or {})
        extra_entries = dict(extra_entries or {})
        includes = {
            "database": True,
            "catalog_state": state_payload is not None,
            "packs": bool(pack_entries),
        }
        manifest = {
            "app_name": "MotMystere",
            "backup_format_version": version,
            "exported_at": "2026-04-06T10:00:00+00:00",
            "includes": includes,
            "logical_targets": {
                "database": "db/hangman.db",
                "catalog_state": "data/catalog_state.json",
                "packs": "packs/",
            },
        }

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True, indent=2))
            archive.write(db_path, arcname="db/hangman.db")
            if state_payload is not None:
                archive.writestr(
                    "data/catalog_state.json",
                    json.dumps(state_payload, ensure_ascii=True, indent=2),
                )
            for arcname, content in pack_entries.items():
                archive.writestr(arcname, content)
            for arcname, content in extra_entries.items():
                archive.writestr(arcname, content)

    def test_export_includes_database_catalog_state_and_local_packs(self):
        service = self._make_service(self.runtime_dir / "source")
        self._seed_source_environment(service)

        archive_path = self.runtime_dir / "source_export.zip"
        summary = service.export_archive(archive_path)

        self.assertTrue(archive_path.exists())
        self.assertTrue(summary["includes"]["database"])
        self.assertTrue(summary["includes"]["catalog_state"])
        self.assertTrue(summary["includes"]["packs"])

        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("db/hangman.db", names)
            self.assertIn("data/catalog_state.json", names)
            self.assertIn("packs/bonus/pack.json", names)
            self.assertIn("packs/bonus/sports.txt", names)

            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["backup_format_version"], 1)
            self.assertEqual(manifest["logical_targets"]["database"], "db/hangman.db")
            self.assertTrue(manifest["includes"]["packs"])

    def test_import_round_trip_restores_progression_rotation_and_exact_local_content(self):
        source_service = self._make_service(self.runtime_dir / "source")
        source_player = self._seed_source_environment(source_service)
        export_path = self.runtime_dir / "full_backup.zip"
        source_service.export_archive(export_path)

        target_service = self._make_service(self.runtime_dir / "target")
        self._seed_target_environment(target_service)

        summary = target_service.import_archive(export_path)

        self.assertIsNotNone(summary["backup_path"])
        self.assertTrue(Path(summary["backup_path"]).exists())
        self.assertFalse((target_service.packs_dir / "obsolete").exists())
        self.assertTrue((target_service.packs_dir / "bonus" / "pack.json").exists())

        leaderboard = get_leaderboard_data(db_path=target_service.db_path)
        self.assertEqual([row["name"] for row in leaderboard], ["Alice"])

        dashboard = get_player_dashboard(source_player["id"], db_path=target_service.db_path)
        self.assertIsNotNone(dashboard)
        self.assertEqual(dashboard["overview"]["games_recorded"], 2)
        self.assertEqual(dashboard["recent_games"][0]["difficulty"], "Moyen")

        rotation = get_word_rotation_state(
            source_player["id"],
            "animaux",
            "Facile",
            db_path=target_service.db_path,
        )
        self.assertEqual(rotation["remaining_words"], ["LION", "OURS"])
        self.assertEqual(rotation["last_word"], "CHAT")

        state = json.loads(target_service.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state, {"pack_overrides": {"bonus": {"enabled": False}}})

        catalog = CatalogService(
            base_dir=target_service.base_dir,
            pack_dir=target_service.packs_dir,
            state_path=target_service.state_path,
        ).load_catalog()
        bonus_pack = next(pack for pack in catalog.pack_summaries if pack.pack_id == "bonus")
        self.assertEqual(bonus_pack.status, "disabled")

    def test_import_accepts_compatible_archive_without_optional_files(self):
        source_service = self._make_service(self.runtime_dir / "source")
        setup_database(source_service.db_path)
        player = get_or_create_player("Alice", db_path=source_service.db_path)
        record_game_result(
            player["id"],
            won=True,
            score_earned=110,
            category="animaux",
            difficulty="Facile",
            secret_word="CHAT",
            end_reason="won",
            attempts_left=8,
            time_remaining=50,
            word_complexity=20,
            db_path=source_service.db_path,
        )
        archive_path = self.runtime_dir / "db_only_backup.zip"
        self._build_archive(archive_path, db_path=source_service.db_path)

        target_service = self._make_service(self.runtime_dir / "target")
        self._seed_target_environment(target_service)

        target_service.import_archive(archive_path)

        self.assertFalse(target_service.state_path.exists())
        self.assertFalse(target_service.packs_dir.exists())
        leaderboard = get_leaderboard_data(db_path=target_service.db_path)
        self.assertEqual([row["name"] for row in leaderboard], ["Alice"])

    def test_import_rejects_path_traversal_without_mutating_local_environment(self):
        target_service = self._make_service(self.runtime_dir / "target")
        self._seed_target_environment(target_service)
        original_leaderboard = get_leaderboard_data(db_path=target_service.db_path)

        source_service = self._make_service(self.runtime_dir / "source")
        setup_database(source_service.db_path)
        archive_path = self.runtime_dir / "malicious_backup.zip"
        self._build_archive(
            archive_path,
            db_path=source_service.db_path,
            extra_entries={"../escape.txt": "boom"},
        )

        with self.assertRaises(BackupServiceError):
            target_service.import_archive(archive_path)

        leaderboard = get_leaderboard_data(db_path=target_service.db_path)
        self.assertEqual(leaderboard, original_leaderboard)
        self.assertTrue((target_service.packs_dir / "obsolete" / "pack.json").exists())

    def test_import_rejects_unsupported_backup_version_without_mutation(self):
        target_service = self._make_service(self.runtime_dir / "target")
        self._seed_target_environment(target_service)

        source_service = self._make_service(self.runtime_dir / "source")
        setup_database(source_service.db_path)
        get_or_create_player("Alice", db_path=source_service.db_path)
        archive_path = self.runtime_dir / "unsupported_backup.zip"
        self._build_archive(
            archive_path,
            db_path=source_service.db_path,
            version=99,
        )

        with self.assertRaises(BackupServiceError):
            target_service.import_archive(archive_path)

        leaderboard = get_leaderboard_data(db_path=target_service.db_path)
        self.assertEqual([row["name"] for row in leaderboard], ["Bob"])
        self.assertTrue(target_service.state_path.exists())

    def test_import_rejects_invalid_local_pack_without_mutating_local_environment(self):
        target_service = self._make_service(self.runtime_dir / "target")
        self._seed_target_environment(target_service)

        source_service = self._make_service(self.runtime_dir / "source")
        setup_database(source_service.db_path)
        archive_path = self.runtime_dir / "broken_pack_backup.zip"
        self._build_archive(
            archive_path,
            db_path=source_service.db_path,
            pack_entries={
                "packs/broken/pack.json": json.dumps(
                    {
                        "id": "broken",
                        "label": "Pack Casse",
                        "categories": [
                            {
                                "id": "metiers",
                                "label": "Metiers",
                                "source": "missing.txt",
                            }
                        ],
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
            },
        )

        with self.assertRaises(BackupServiceError):
            target_service.import_archive(archive_path)

        leaderboard = get_leaderboard_data(db_path=target_service.db_path)
        self.assertEqual([row["name"] for row in leaderboard], ["Bob"])
        self.assertTrue((target_service.packs_dir / "obsolete").exists())


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import shutil
import unittest
import uuid

from motmystere.catalog_service import CatalogService, CatalogServiceError


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
        Path(path).write_text("\n".join(words) + "\n", encoding="utf-8")

    def _write_json(self, path, payload):
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

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

        source_pack_dir = root_dir / "source_pack"
        source_pack_dir.mkdir()
        self._write_words(source_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
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

from pathlib import Path
import shutil
import unittest
import uuid

from motmystere.catalog_service import CatalogService
from motmystere.categories import get_category_difficulty_breakdown


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class OfficialPacksTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = _create_runtime_dir("motmystere_official_packs_")
        self.addCleanup(shutil.rmtree, self.runtime_dir, True)
        self.service = CatalogService(
            pack_dir=self.runtime_dir / "packs",
            state_path=self.runtime_dir / "catalog_state.json",
        )

    def test_official_pack_index_exposes_expected_archives(self):
        official_packs = self.service.list_official_packs()

        self.assertEqual([pack.pack_id for pack in official_packs], ["voyage", "culture", "science"])
        self.assertTrue(all(Path(pack.archive_path).exists() for pack in official_packs))

    def test_official_pack_previews_are_installable_and_warning_free(self):
        official_packs = self.service.list_official_packs()

        for official_pack in official_packs:
            preview = self.service.inspect_pack_source(official_pack.archive_path)

            self.assertTrue(preview.installable, msg=f"{official_pack.pack_id} devrait etre installable.")
            self.assertEqual(preview.blockers, (), msg=f"{official_pack.pack_id} ne doit avoir aucun blocage.")
            self.assertEqual(preview.alerts, (), msg=f"{official_pack.pack_id} ne doit avoir aucune alerte.")
            self.assertEqual(
                len(preview.playable_after_activation),
                3,
                msg=f"{official_pack.pack_id} doit exposer trois categories jouables.",
            )

    def test_official_pack_categories_provide_at_least_forty_five_words_and_fifteen_per_level(self):
        official_packs = self.service.list_official_packs()

        for official_pack in official_packs:
            catalog, _pack_summary = self.service.import_pack_from_source(official_pack.archive_path, enabled=True)
            for category_key in sorted(
                key for key in catalog.categories if key.startswith(f"{official_pack.pack_id}::")
            ):
                words = catalog.categories[category_key]
                breakdown = get_category_difficulty_breakdown(words)
                self.assertGreaterEqual(len(words), 45, msg=f"{category_key} doit fournir au moins 45 mots.")
                for difficulty in ("Facile", "Moyen", "Difficile"):
                    self.assertGreaterEqual(
                        breakdown[difficulty],
                        15,
                        msg=f"{category_key} doit fournir au moins 15 mots en {difficulty}.",
                    )

    def test_importing_all_official_packs_raises_catalog_depth_to_eighteen_categories(self):
        official_packs = self.service.list_official_packs()

        catalog = self.service.load_catalog()
        self.assertEqual(len(catalog.categories), 9)

        for official_pack in official_packs:
            catalog, _pack_summary = self.service.import_pack_from_source(official_pack.archive_path, enabled=True)

        self.assertGreaterEqual(len(catalog.categories), 18)
        for pack_id in ("voyage", "culture", "science"):
            self.assertEqual(
                len([key for key in catalog.categories if key.startswith(f"{pack_id}::")]),
                3,
            )


if __name__ == "__main__":
    unittest.main()

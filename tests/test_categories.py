import json
from pathlib import Path
import shutil
import unittest
import uuid

from motmystere.categories import (
    DIFFICULTY_LEVELS,
    build_word_profile,
    format_category_name,
    get_category_difficulty_breakdown,
    get_supported_difficulties,
    get_words_for_difficulty,
    load_category_catalog,
    load_categories,
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
EASY_ONLY_WORDS = ["CHAT", "LION", "OURS", "LOUP", "VACHE"]


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class CategoriesTestCase(unittest.TestCase):
    def setUp(self):
        self.words = ["CHAT", "RUGBY", "KAZAKHSTAN"]

    def test_word_profile_exposes_complexity_and_band(self):
        profile = build_word_profile("KAZAKHSTAN")

        self.assertEqual(profile.difficulty, "Difficile")
        self.assertGreater(profile.complexity, profile.length)

    def test_get_words_for_difficulty_filters_matching_profiles(self):
        medium_profiles = get_words_for_difficulty(self.words, "Moyen")

        self.assertEqual([profile.text for profile in medium_profiles], ["RUGBY"])

    def test_breakdown_counts_each_band(self):
        breakdown = get_category_difficulty_breakdown(self.words)

        self.assertEqual(
            breakdown,
            {"Facile": 1, "Moyen": 1, "Difficile": 1},
        )

    def test_supported_difficulties_require_minimum_pool_size(self):
        supported = get_supported_difficulties(self.words)

        self.assertEqual(supported, ())

    def test_runtime_catalog_merges_builtin_and_local_packs(self):
        root_dir = self._make_workspace()
        base_dir = root_dir / "base"
        packs_dir = root_dir / "packs"
        base_dir.mkdir()
        packs_dir.mkdir()
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)

        voyage_pack_dir = packs_dir / "voyage"
        voyage_pack_dir.mkdir()
        self._write_words(voyage_pack_dir / "capitales.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            voyage_pack_dir / "pack.json",
            {
                "id": "voyage",
                "label": "Pack Voyage",
                "categories": [
                    {
                        "id": "capitales",
                        "label": "Capitales",
                        "source": "capitales.txt",
                    }
                ],
            },
        )

        catalog = load_category_catalog(base_dir=base_dir, local_pack_dir=packs_dir)
        voyage_summary = next(
            pack
            for pack in catalog.pack_summaries
            if pack.pack_id == "voyage"
        )

        self.assertIn("animaux", catalog.categories)
        self.assertIn("voyage::capitales", catalog.categories)
        self.assertEqual(catalog.category_availability["voyage::capitales"], DIFFICULTY_LEVELS)
        self.assertEqual(catalog.display_names["voyage::capitales"], "Pack Voyage / Capitales")
        self.assertEqual(format_category_name("voyage::capitales"), "Voyage / Capitales")
        self.assertEqual(voyage_summary.status, "active")
        self.assertEqual(voyage_summary.loaded_category_count, 1)

    def test_disabled_pack_is_ignored_but_reported(self):
        root_dir = self._make_workspace()
        base_dir = root_dir / "base"
        packs_dir = root_dir / "packs"
        base_dir.mkdir()
        packs_dir.mkdir()
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)

        disabled_pack_dir = packs_dir / "bonus"
        disabled_pack_dir.mkdir()
        self._write_words(disabled_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            disabled_pack_dir / "pack.json",
            {
                "id": "bonus",
                "enabled": False,
                "categories": [
                    {
                        "id": "sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        catalog = load_category_catalog(base_dir=base_dir, local_pack_dir=packs_dir)
        bonus_summary = next(
            pack
            for pack in catalog.pack_summaries
            if pack.pack_id == "bonus"
        )

        self.assertNotIn("bonus::sports", catalog.categories)
        self.assertEqual(bonus_summary.status, "disabled")
        self.assertEqual(bonus_summary.loaded_category_count, 0)

    def test_invalid_pack_is_reported_without_loading_category(self):
        root_dir = self._make_workspace()
        base_dir = root_dir / "base"
        packs_dir = root_dir / "packs"
        base_dir.mkdir()
        packs_dir.mkdir()
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)

        broken_pack_dir = packs_dir / "broken"
        broken_pack_dir.mkdir()
        self._write_json(
            broken_pack_dir / "pack.json",
            {
                "id": "broken",
                "categories": [
                    {
                        "id": "metiers",
                        "source": "absent.txt",
                    }
                ],
            },
        )

        catalog = load_category_catalog(base_dir=base_dir, local_pack_dir=packs_dir)
        broken_summary = next(
            pack
            for pack in catalog.pack_summaries
            if pack.pack_id == "broken"
        )

        self.assertNotIn("broken::metiers", catalog.categories)
        self.assertEqual(broken_summary.status, "invalid")
        self.assertTrue(
            any("fichier introuvable" in issue.message for issue in catalog.issues),
            msg="Le catalogue doit signaler clairement les sources manquantes.",
        )

    def test_incomplete_category_keeps_only_supported_levels(self):
        root_dir = self._make_workspace()
        base_dir = root_dir / "base"
        packs_dir = root_dir / "packs"
        base_dir.mkdir()
        packs_dir.mkdir()
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)

        easy_pack_dir = packs_dir / "facile"
        easy_pack_dir.mkdir()
        self._write_words(easy_pack_dir / "quiz.txt", EASY_ONLY_WORDS)
        self._write_json(
            easy_pack_dir / "pack.json",
            {
                "id": "facile",
                "categories": [
                    {
                        "id": "quiz",
                        "source": "quiz.txt",
                    }
                ],
            },
        )

        catalog = load_category_catalog(base_dir=base_dir, local_pack_dir=packs_dir)

        self.assertEqual(catalog.category_availability["facile::quiz"], ("Facile",))
        self.assertTrue(
            any(
                issue.pack_id == "facile" and "niveaux disponibles Facile" in issue.message
                for issue in catalog.issues
            ),
            msg="Une categorie incomplete doit etre chargee mais signee comme partielle.",
        )

    def test_repository_categories_cover_all_difficulties_for_distribution(self):
        categories = load_categories()

        for category, words in categories.items():
            supported = get_supported_difficulties(words)
            breakdown = get_category_difficulty_breakdown(words)

            self.assertEqual(
                supported,
                DIFFICULTY_LEVELS,
                msg=f"{category} ne couvre plus tous les niveaux garantis.",
            )
            for difficulty in DIFFICULTY_LEVELS:
                self.assertGreaterEqual(
                    breakdown[difficulty],
                    15,
                    msg=f"{category} ne fournit pas encore un pool solide en {difficulty}.",
                )

    def _write_words(self, path, words):
        Path(path).write_text("\n".join(words) + "\n", encoding="utf-8")

    def _write_json(self, path, payload):
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _make_workspace(self):
        root_dir = _create_runtime_dir("motmystere_catalog_")
        self.addCleanup(self._cleanup_workspace, root_dir)
        return root_dir

    def _cleanup_workspace(self, root_dir):
        shutil.rmtree(root_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

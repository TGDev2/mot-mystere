import json
from pathlib import Path
import shutil
import unittest
import uuid

from motmystere.catalog_service import CatalogService
from motmystere.categories import get_words_for_difficulty, lire_mots
from motmystere.database import get_or_create_player, record_game_result, setup_database
from motmystere.editorial_cockpit import get_editorial_cockpit_bundle
from motmystere.scoring import get_attempts_for_difficulty, get_time_limit_for_difficulty


REPO_ROOT = Path(__file__).resolve().parents[1]
ANIMAUX_PATH = REPO_ROOT / "motmystere" / "assets" / "wordlists" / "animaux.txt"
ANIMAUX_WORDS = lire_mots(ANIMAUX_PATH)
EASY_WORDS = [profile.text for profile in get_words_for_difficulty(ANIMAUX_WORDS, "Facile")]
MEDIUM_WORDS = [profile.text for profile in get_words_for_difficulty(ANIMAUX_WORDS, "Moyen")]
HARD_WORDS = [profile.text for profile in get_words_for_difficulty(ANIMAUX_WORDS, "Difficile")]


def _create_runtime_dir(prefix):
    runtime_root = REPO_ROOT / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


def _build_words(easy_count, medium_count, hard_count):
    return (
        EASY_WORDS[:easy_count]
        + MEDIUM_WORDS[:medium_count]
        + HARD_WORDS[:hard_count]
    )


class EditorialCockpitTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = _create_runtime_dir("motmystere_editorial_cockpit_")
        self.addCleanup(shutil.rmtree, self.runtime_dir, True)
        self.base_dir = self.runtime_dir / "base"
        self.pack_dir = self.runtime_dir / "packs"
        self.state_path = self.runtime_dir / "catalog_state.json"
        self.db_path = self.runtime_dir / "runtime.db"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        setup_database(self.db_path)
        self._write_words(self.base_dir / "animaux.txt", _build_words(15, 15, 15))
        self.service = CatalogService(
            base_dir=self.base_dir,
            pack_dir=self.pack_dir,
            state_path=self.state_path,
        )

    def _write_words(self, path, words):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(words) + "\n", encoding="utf-8")

    def _write_json(self, path, payload):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _create_pack(self, pack_id, category_id, words, *, label=None):
        pack_root = self.pack_dir / pack_id
        source_name = f"{category_id}.txt"
        self._write_words(pack_root / source_name, words)
        self._write_json(
            pack_root / "pack.json",
            {
                "id": pack_id,
                "label": label or pack_id.replace("_", " ").title(),
                "categories": [
                    {
                        "id": category_id,
                        "label": category_id.replace("_", " ").title(),
                        "source": source_name,
                    }
                ],
            },
        )

    def _record_review_signal(self, category, difficulty):
        alice = get_or_create_player("Alice", db_path=self.db_path)
        bob = get_or_create_player("Bob", db_path=self.db_path)
        for player_id, rounds in ((alice["id"], 8), (bob["id"], 7)):
            for _ in range(rounds):
                record_game_result(
                    player_id,
                    won=False,
                    score_earned=0,
                    category=category,
                    difficulty=difficulty,
                    secret_word="TEST",
                    end_reason="attempts",
                    attempts_left=0,
                    time_remaining=max(0, get_time_limit_for_difficulty(difficulty) - 10),
                    attempts_limit=get_attempts_for_difficulty(difficulty),
                    time_limit=get_time_limit_for_difficulty(difficulty),
                    word_complexity=20,
                    db_path=self.db_path,
                )

    def _build_bundle(self):
        catalog = self.service.load_catalog()
        return get_editorial_cockpit_bundle(
            catalog,
            catalog_service=self.service,
            db_path=self.db_path,
        )

    def _find_installed_pack(self, bundle, pack_id):
        return next(pack for pack in bundle["installed_packs"] if pack["pack_id"] == pack_id)

    def _find_category(self, bundle, category_key):
        for pack in bundle["installed_packs"] + bundle["official_packs"]:
            for category in pack["categories"]:
                if category["category_key"] == category_key:
                    return category
        raise AssertionError(f"Categorie introuvable: {category_key}")

    def test_bundle_maps_disable_enrich_recalibrate_and_keep_actions(self):
        self._create_pack("zzz_broken", "tiny", _build_words(4, 0, 0), label="Pack Z Broken")
        self._create_pack("aaa_enrich", "thin", _build_words(15, 15, 14), label="Pack A Enrich")
        self._create_pack("review", "space", _build_words(15, 15, 15), label="Pack Review")
        self._create_pack("zzz_keep", "steady", _build_words(15, 15, 15), label="Pack Z Keep")
        self._record_review_signal("review::space", "Facile")

        bundle = self._build_bundle()

        self.assertEqual(
            self._find_category(bundle, "zzz_broken::tiny")["recommended_action"],
            "disable",
        )
        self.assertEqual(
            self._find_category(bundle, "aaa_enrich::thin")["recommended_action"],
            "enrich",
        )
        review_category = self._find_category(bundle, "review::space")
        self.assertEqual(review_category["recommended_action"], "recalibrate")
        self.assertEqual(review_category["calibration_status"], "review")
        self.assertEqual(
            self._find_category(bundle, "zzz_keep::steady")["recommended_action"],
            "keep",
        )

    def test_insufficient_data_stays_out_of_priority_sections(self):
        self._create_pack("zzz_keep", "steady", _build_words(15, 15, 15), label="Pack Z Keep")

        bundle = self._build_bundle()
        keep_category = self._find_category(bundle, "zzz_keep::steady")

        self.assertEqual(keep_category["recommended_action"], "keep")
        self.assertEqual(keep_category["calibration_status"], "insufficient_data")

        urgent_items = {
            item["category_key"]
            for section in bundle["priority_sections"]
            if section["key"] != "keep"
            for item in section["items"]
        }
        self.assertNotIn("zzz_keep::steady", urgent_items)

    def test_official_packs_are_separated_with_non_installed_calibration(self):
        bundle = self._build_bundle()

        self.assertEqual(len(bundle["official_packs"]), 3)
        self.assertEqual(bundle["official_error"], "")
        self.assertTrue(all(pack["playability_status"] == "not_installed" for pack in bundle["official_packs"]))
        self.assertTrue(
            all(
                category["calibration_status"] == "not_installed"
                for pack in bundle["official_packs"]
                for category in pack["categories"]
            )
        )

    def test_pack_rollups_are_sorted_by_gravity_not_pack_name(self):
        self._create_pack("zzz_broken", "tiny", _build_words(4, 0, 0), label="Pack Z Broken")
        self._create_pack("aaa_enrich", "thin", _build_words(15, 15, 14), label="Pack A Enrich")
        self._create_pack("review", "space", _build_words(15, 15, 15), label="Pack Review")
        self._record_review_signal("review::space", "Facile")

        bundle = self._build_bundle()

        self.assertEqual(bundle["installed_packs"][0]["pack_id"], "zzz_broken")
        self.assertEqual(bundle["installed_packs"][1]["pack_id"], "aaa_enrich")
        self.assertEqual(bundle["installed_packs"][2]["pack_id"], "review")


if __name__ == "__main__":
    unittest.main()

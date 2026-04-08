import unittest
from pathlib import Path
import shutil
from types import SimpleNamespace
import uuid

from motmystere.categories import CategorySummary, CORE_PACK_ID, PackSummary
from motmystere.database import get_or_create_player, record_game_result, setup_database
from motmystere.difficulty_calibration import get_difficulty_calibration_bundle
from motmystere.scoring import get_attempts_for_difficulty, get_time_limit_for_difficulty


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


def _build_catalog():
    return SimpleNamespace(
        category_availability={
            "animaux": ("Facile",),
            "bonus::sports": ("Difficile",),
        },
        display_names={
            "animaux": "Animaux",
            "bonus::sports": "Pack Bonus / Sports",
        },
        pack_summaries=(
            PackSummary(
                pack_id=CORE_PACK_ID,
                label="Catalogue integre",
                origin="builtin",
                status="active",
                source_path="builtin",
                category_count=1,
                loaded_category_count=1,
                playable_category_count=1,
                categories=(
                    CategorySummary(
                        category_key="animaux",
                        label="Animaux",
                        status="active",
                        available_difficulties=("Facile",),
                        source_path="builtin",
                    ),
                ),
            ),
            PackSummary(
                pack_id="bonus",
                label="Pack Bonus",
                origin="local",
                status="active",
                source_path="packs/bonus/pack.json",
                category_count=1,
                loaded_category_count=1,
                playable_category_count=1,
                categories=(
                    CategorySummary(
                        category_key="bonus::sports",
                        label="Pack Bonus / Sports",
                        status="active",
                        available_difficulties=("Difficile",),
                        source_path="packs/bonus/sports.txt",
                    ),
                ),
            ),
        ),
    )


class DifficultyCalibrationTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = _create_runtime_dir("motmystere_calibration_")
        self.addCleanup(shutil.rmtree, self.runtime_dir, True)
        self.db_path = self.runtime_dir / "calibration_runtime.db"
        setup_database(self.db_path)
        self.catalog = _build_catalog()

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_player(self, name):
        return get_or_create_player(name, db_path=self.db_path)

    def _record_round(
        self,
        player_id,
        *,
        category,
        difficulty,
        won,
        end_reason,
        attempts_left,
        time_remaining,
        word_complexity,
        score_earned,
    ):
        record_game_result(
            player_id,
            won=won,
            score_earned=score_earned,
            category=category,
            difficulty=difficulty,
            secret_word="TEST",
            end_reason=end_reason,
            attempts_left=attempts_left,
            time_remaining=time_remaining,
            attempts_limit=get_attempts_for_difficulty(difficulty),
            time_limit=get_time_limit_for_difficulty(difficulty),
            word_complexity=word_complexity,
            db_path=self.db_path,
        )

    def _get_pair(self, bundle, category, difficulty):
        return next(
            pair
            for pair in bundle["pairs"]
            if pair["category"] == category and pair["difficulty"] == difficulty
        )

    def test_hard_pair_moves_from_insufficient_to_watch_then_review(self):
        alice = self._create_player("Alice")
        bob = self._create_player("Bob")

        for _ in range(5):
            self._record_round(
                alice["id"],
                category="animaux",
                difficulty="Facile",
                won=False,
                end_reason="attempts",
                attempts_left=0,
                time_remaining=19,
                word_complexity=20,
                score_earned=0,
            )
        for _ in range(2):
            self._record_round(
                alice["id"],
                category="animaux",
                difficulty="Facile",
                won=True,
                end_reason="won",
                attempts_left=1,
                time_remaining=5,
                word_complexity=20,
                score_earned=115,
            )

        first_bundle = get_difficulty_calibration_bundle(self.catalog, db_path=self.db_path)
        first_pair = self._get_pair(first_bundle, "animaux", "Facile")
        self.assertEqual(first_pair["status"], "insufficient_data")

        self._record_round(
            alice["id"],
            category="animaux",
            difficulty="Facile",
            won=False,
            end_reason="attempts",
            attempts_left=0,
            time_remaining=17,
            word_complexity=20,
            score_earned=0,
        )

        second_bundle = get_difficulty_calibration_bundle(self.catalog, db_path=self.db_path)
        second_pair = self._get_pair(second_bundle, "animaux", "Facile")
        self.assertEqual(second_pair["status"], "watch")
        self.assertEqual(second_pair["direction"], "plus dur")

        for _ in range(7):
            self._record_round(
                bob["id"],
                category="animaux",
                difficulty="Facile",
                won=False,
                end_reason="attempts",
                attempts_left=0,
                time_remaining=21,
                word_complexity=20,
                score_earned=0,
            )

        third_bundle = get_difficulty_calibration_bundle(self.catalog, db_path=self.db_path)
        third_pair = self._get_pair(third_bundle, "animaux", "Facile")
        self.assertEqual(third_pair["status"], "review")
        self.assertTrue(third_pair["confidence_sufficient"])

    def test_easy_pair_is_flagged_as_review_when_comfort_is_too_high(self):
        alice = self._create_player("Alice")
        bob = self._create_player("Bob")

        for player_id, rounds in ((alice["id"], 8), (bob["id"], 7)):
            for _ in range(rounds):
                self._record_round(
                    player_id,
                    category="bonus::sports",
                    difficulty="Difficile",
                    won=True,
                    end_reason="won",
                    attempts_left=3,
                    time_remaining=20,
                    word_complexity=42,
                    score_earned=310,
                )

        bundle = get_difficulty_calibration_bundle(self.catalog, db_path=self.db_path)
        pair = self._get_pair(bundle, "bonus::sports", "Difficile")

        self.assertEqual(pair["status"], "review")
        self.assertEqual(pair["direction"], "plus facile")
        self.assertTrue(pair["easy_signal"])

    def test_dominant_single_player_cannot_promote_a_pair_above_watch(self):
        alice = self._create_player("Alice")

        for _ in range(15):
            self._record_round(
                alice["id"],
                category="animaux",
                difficulty="Facile",
                won=False,
                end_reason="attempts",
                attempts_left=0,
                time_remaining=18,
                word_complexity=20,
                score_earned=0,
            )

        bundle = get_difficulty_calibration_bundle(self.catalog, db_path=self.db_path)
        pair = self._get_pair(bundle, "animaux", "Facile")

        self.assertEqual(pair["status"], "watch")
        self.assertFalse(pair["confidence_sufficient"])
        self.assertIn("Confiance limitee", pair["reason"])

    def test_never_played_pair_stays_visible_and_rollups_count_signals(self):
        alice = self._create_player("Alice")
        bob = self._create_player("Bob")

        for player_id, rounds in ((alice["id"], 8), (bob["id"], 7)):
            for _ in range(rounds):
                self._record_round(
                    player_id,
                    category="animaux",
                    difficulty="Facile",
                    won=False,
                    end_reason="attempts",
                    attempts_left=0,
                    time_remaining=20,
                    word_complexity=20,
                    score_earned=0,
                )

        bundle = get_difficulty_calibration_bundle(self.catalog, db_path=self.db_path)
        untouched_pair = self._get_pair(bundle, "bonus::sports", "Difficile")
        core_rollup = next(rollup for rollup in bundle["pack_rollups"] if rollup["key"] == CORE_PACK_ID)
        animal_rollup = next(
            rollup for rollup in bundle["category_rollups"] if rollup["key"] == "animaux"
        )

        self.assertEqual(untouched_pair["status"], "insufficient_data")
        self.assertEqual(untouched_pair["games_played"], 0)
        self.assertEqual(core_rollup["status"], "review")
        self.assertEqual(core_rollup["review_count"], 1)
        self.assertEqual(core_rollup["signal_count"], 1)
        self.assertEqual(animal_rollup["status"], "review")


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from database import setup_database
from solo_game_service import create_session_for_player, prepare_player, resolve_round


class FixedChoice:
    def choice(self, values):
        return values[0]


class SoloGameServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).parent / "service_runtime.db"
        if self.db_path.exists():
            self.db_path.unlink()
        setup_database(self.db_path)
        self.categories = {"animaux": ["CHAT", "LION", "OURS", "LOUP", "VACHE"]}
        self.category_availability = {"animaux": ("Facile",)}
        self.player = prepare_player("Alice", db_path=self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_session_avoids_repeat_until_rotation_is_exhausted(self):
        words = []
        for _ in range(5):
            session = create_session_for_player(
                self.player["id"],
                self.categories,
                "animaux",
                "Facile",
                rng=FixedChoice(),
                db_path=self.db_path,
            )
            words.append(session.secret_word)

        self.assertEqual(words, ["CHAT", "LION", "OURS", "LOUP", "VACHE"])

        next_session = create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )

        self.assertEqual(next_session.secret_word, "CHAT")

    def test_resolve_round_returns_progression_without_ui(self):
        session = create_session_for_player(
            self.player["id"],
            self.categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            db_path=self.db_path,
        )
        for letter in "CHAT":
            session.guess(letter)

        outcome = resolve_round(
            self.player,
            session,
            "won",
            self.category_availability,
            db_path=self.db_path,
        )

        self.assertEqual(outcome["title"], "Victoire")
        self.assertGreater(outcome["score_earned"], 0)
        self.assertEqual(
            outcome["mastery_updates"][0]["title"],
            "Animaux / Facile valide",
        )
        self.assertEqual(
            outcome["progression_snapshot"]["primary_goal"]["key"],
            "mastery_board",
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from game_session import GameSession
from scoring import get_time_limit_for_difficulty


class FixedChoice:
    def choice(self, values):
        return values[0]


class GameSessionTestCase(unittest.TestCase):
    def setUp(self):
        self.categories = {"animaux": ["CHAT", "RUGBY", "KAZAKHSTAN"]}

    def test_selected_difficulty_chooses_matching_word_pool(self):
        session = GameSession.create(
            self.categories,
            "animaux",
            "Moyen",
            rng=FixedChoice(),
            minimum_pool_size=1,
        )

        self.assertEqual(session.secret_word, "RUGBY")
        self.assertEqual(session.word_profile.difficulty, "Moyen")
        self.assertEqual(session.time_limit, get_time_limit_for_difficulty("Moyen"))

    def test_correct_guess_reveals_letter(self):
        session = GameSession.create(self.categories, "animaux", "Facile", minimum_pool_size=1)

        result = session.guess("C")

        self.assertTrue(result.correct)
        self.assertEqual(session.revealed_word, "C _ _ _")
        self.assertEqual(session.attempts_left, 10)

    def test_wrong_guess_consumes_attempt(self):
        session = GameSession.create(self.categories, "animaux", "Facile", minimum_pool_size=1)

        result = session.guess("Z")

        self.assertFalse(result.correct)
        self.assertEqual(session.attempts_left, 9)

    def test_duplicate_guess_does_not_consume_attempt(self):
        session = GameSession.create(self.categories, "animaux", "Facile", minimum_pool_size=1)

        session.guess("Z")
        result = session.guess("Z")

        self.assertTrue(result.already_guessed)
        self.assertEqual(session.attempts_left, 9)

    def test_session_wins_when_all_letters_are_found(self):
        session = GameSession.create(self.categories, "animaux", "Facile", minimum_pool_size=1)

        for letter in "CHAT":
            session.guess(letter)

        self.assertEqual(session.status, "won")

    def test_timer_expiration_loses_the_round(self):
        session = GameSession.create(self.categories, "animaux", "Facile", minimum_pool_size=1)
        session.time_remaining = 1

        status = session.tick()

        self.assertEqual(status, "lost")
        self.assertEqual(session.time_remaining, 0)

    def test_unsupported_difficulty_is_rejected_instead_of_falling_back(self):
        limited_categories = {"animaux": ["CHAT", "LION", "OURS", "LOUP", "VACHE"]}

        with self.assertRaisesRegex(ValueError, "n'est pas disponible"):
            GameSession.create(limited_categories, "animaux", "Moyen")

    def test_recent_words_avoid_immediate_repeat_when_pool_allows(self):
        replay_categories = {"animaux": ["CHAT", "LION", "OURS", "LOUP", "VACHE"]}

        session = GameSession.create(
            replay_categories,
            "animaux",
            "Facile",
            rng=FixedChoice(),
            recent_words=["CHAT"],
        )

        self.assertEqual(session.secret_word, "LION")


if __name__ == "__main__":
    unittest.main()

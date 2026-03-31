import unittest

from game_session import GameSession


class GameSessionTestCase(unittest.TestCase):
    def setUp(self):
        self.categories = {"animaux": ["CHAT"]}

    def test_correct_guess_reveals_letter(self):
        session = GameSession.create(self.categories, "animaux", "Facile")

        result = session.guess("C")

        self.assertTrue(result.correct)
        self.assertEqual(session.revealed_word, "C _ _ _")
        self.assertEqual(session.attempts_left, 10)

    def test_wrong_guess_consumes_attempt(self):
        session = GameSession.create(self.categories, "animaux", "Facile")

        result = session.guess("Z")

        self.assertFalse(result.correct)
        self.assertEqual(session.attempts_left, 9)

    def test_duplicate_guess_does_not_consume_attempt(self):
        session = GameSession.create(self.categories, "animaux", "Facile")

        session.guess("Z")
        result = session.guess("Z")

        self.assertTrue(result.already_guessed)
        self.assertEqual(session.attempts_left, 9)

    def test_session_wins_when_all_letters_are_found(self):
        session = GameSession.create(self.categories, "animaux", "Facile")

        for letter in "CHAT":
            session.guess(letter)

        self.assertEqual(session.status, "won")

    def test_timer_expiration_loses_the_round(self):
        session = GameSession.create(self.categories, "animaux", "Facile")
        session.time_remaining = 1

        status = session.tick()

        self.assertEqual(status, "lost")
        self.assertEqual(session.time_remaining, 0)


if __name__ == "__main__":
    unittest.main()

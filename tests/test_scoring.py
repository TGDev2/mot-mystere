import unittest

from scoring import build_score_breakdown


class ScoringTestCase(unittest.TestCase):
    def test_harder_difficulty_awards_more_points(self):
        easy_score = build_score_breakdown("Facile", 5, 5, 20)["total"]
        hard_score = build_score_breakdown("Difficile", 5, 5, 20)["total"]

        self.assertGreater(hard_score, easy_score)

    def test_more_time_and_attempts_increase_score(self):
        lower_score = build_score_breakdown("Moyen", 6, 1, 5)["total"]
        higher_score = build_score_breakdown("Moyen", 6, 4, 25)["total"]

        self.assertGreater(higher_score, lower_score)


if __name__ == "__main__":
    unittest.main()

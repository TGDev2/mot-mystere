import unittest

from motmystere.scoring import build_score_breakdown, get_time_limit_for_difficulty


class ScoringTestCase(unittest.TestCase):
    def test_harder_difficulty_awards_more_points(self):
        easy_score = build_score_breakdown(
            "Facile",
            5,
            5,
            20,
            word_complexity=20,
            time_limit=get_time_limit_for_difficulty("Facile"),
        )["total"]
        hard_score = build_score_breakdown(
            "Difficile",
            5,
            5,
            20,
            word_complexity=20,
            time_limit=get_time_limit_for_difficulty("Difficile"),
        )["total"]

        self.assertGreater(hard_score, easy_score)

    def test_more_time_and_attempts_increase_score(self):
        lower_score = build_score_breakdown(
            "Moyen",
            6,
            1,
            5,
            word_complexity=24,
            time_limit=get_time_limit_for_difficulty("Moyen"),
        )["total"]
        higher_score = build_score_breakdown(
            "Moyen",
            6,
            4,
            25,
            word_complexity=24,
            time_limit=get_time_limit_for_difficulty("Moyen"),
        )["total"]

        self.assertGreater(higher_score, lower_score)

    def test_more_complex_word_awards_more_points(self):
        simpler_word = build_score_breakdown(
            "Moyen",
            6,
            3,
            20,
            word_complexity=22,
            time_limit=get_time_limit_for_difficulty("Moyen"),
        )["total"]
        harder_word = build_score_breakdown(
            "Moyen",
            6,
            3,
            20,
            word_complexity=35,
            time_limit=get_time_limit_for_difficulty("Moyen"),
        )["total"]

        self.assertGreater(harder_word, simpler_word)


if __name__ == "__main__":
    unittest.main()

import unittest

from categories import (
    DIFFICULTY_LEVELS,
    build_word_profile,
    get_category_difficulty_breakdown,
    get_supported_difficulties,
    get_words_for_difficulty,
    load_categories,
)


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

    def test_repository_categories_cover_all_difficulties_for_distribution(self):
        categories = load_categories()

        for category, words in categories.items():
            self.assertEqual(
                get_supported_difficulties(words),
                DIFFICULTY_LEVELS,
                msg=f"{category} ne couvre plus tous les niveaux garantis.",
            )


if __name__ == "__main__":
    unittest.main()

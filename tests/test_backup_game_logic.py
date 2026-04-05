import unittest
from unittest.mock import patch

from motmystere.game_logic import HangmanApp


class StubVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class StubWindow:
    def __init__(self):
        self.destroyed = False

    def winfo_exists(self):
        return not self.destroyed

    def destroy(self):
        self.destroyed = True


class StubCatalogService:
    def __init__(self, catalog):
        self.catalog = catalog

    def load_catalog(self):
        return self.catalog


class BackupGameLogicTestCase(unittest.TestCase):
    def test_apply_restored_environment_resets_runtime_state_and_rehydrates_recent_player(self):
        app = HangmanApp.__new__(HangmanApp)
        app.session = object()
        app.guided_session = {"status": "active"}
        app.progression_snapshot = {"primary_goal": {"key": "old"}}
        app.catalog_window = StubWindow()
        app.category_var = StubVar("obsolete::quiz")
        app.difficulty_var = StubVar("Difficile")
        app.player_name_var = StubVar("Bob")
        app.progress_var = StubVar("Ancienne progression")
        app.category_availability = {"animaux": ("Facile",)}

        catalog = object()
        app.catalog_service = StubCatalogService(catalog)

        calls = []
        app.cancel_timer = lambda: calls.append(("cancel_timer",))
        app._set_catalog = lambda loaded_catalog: calls.append(("set_catalog", loaded_catalog))
        app._sync_selection_after_catalog_reload = lambda previous_category, previous_difficulty: (
            "Categorie de secours."
        )
        app._load_recent_players = lambda: [{"id": 7}]
        app._apply_progression_bundle = lambda bundle, sync_recent_selection=False: calls.append(
            ("apply_bundle", bundle["player"]["name"], sync_recent_selection)
        )
        app.show_main_menu = lambda banner_message="": calls.append(("show_main_menu", banner_message))

        with patch(
            "motmystere.game_logic.get_progression_bundle",
            return_value={"player": {"name": "Alice"}, "dashboard": {}, "snapshot": {}},
        ):
            app._apply_restored_environment(
                {"backup_path": "C:/tmp/rescue.zip", "includes": {"database": True}}
            )

        self.assertIsNone(app.session)
        self.assertIsNone(app.guided_session)
        self.assertIsNone(app.progression_snapshot)
        self.assertIsNone(app.catalog_window)
        self.assertEqual(
            calls[0:3],
            [
                ("cancel_timer",),
                ("set_catalog", catalog),
                ("apply_bundle", "Alice", True),
            ],
        )
        self.assertIn("Sauvegarde restauree.", calls[-1][1])
        self.assertIn("Sauvegarde de secours creee : rescue.zip.", calls[-1][1])
        self.assertIn("Profil recharge : Alice.", calls[-1][1])
        self.assertIn("Categorie de secours.", calls[-1][1])


if __name__ == "__main__":
    unittest.main()

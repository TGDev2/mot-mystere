import json
from pathlib import Path
import shutil
import unittest
import uuid

from motmystere.game_logic import HangmanApp
from motmystere.categories import load_category_catalog
from motmystere.workflows.catalog import CatalogWorkflow


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


class StubVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _create_runtime_dir(prefix):
    runtime_root = Path(__file__).resolve().parents[1] / ".tmp" / "tests"
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_dir = runtime_root / f"{prefix}{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=False)
    return runtime_dir


class CatalogGameLogicTestCase(unittest.TestCase):
    def _make_workspace(self):
        root_dir = _create_runtime_dir("motmystere_catalog_logic_")
        self.addCleanup(lambda: shutil.rmtree(root_dir, ignore_errors=True))
        return root_dir

    def _write_words(self, path, words):
        Path(path).write_text("\n".join(words) + "\n", encoding="utf-8")

    def _write_json(self, path, payload):
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_reload_catalog_state_falls_back_when_selected_pack_disappears(self):
        root_dir = self._make_workspace()
        base_dir = root_dir / "base"
        packs_dir = root_dir / "packs"
        base_dir.mkdir()
        packs_dir.mkdir()
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)

        bonus_pack_dir = packs_dir / "bonus"
        bonus_pack_dir.mkdir()
        self._write_words(bonus_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            bonus_pack_dir / "pack.json",
            {
                "id": "bonus",
                "label": "Pack Bonus",
                "categories": [
                    {
                        "id": "sports",
                        "label": "Sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        disabled_catalog = load_category_catalog(
            base_dir=base_dir,
            local_pack_dir=packs_dir,
            pack_overrides={"bonus": {"enabled": False}},
        )

        app = HangmanApp.__new__(HangmanApp)
        app.category_var = StubVar("bonus::sports")
        app.category_display_var = StubVar("Pack Bonus / Sports")
        app.difficulty_var = StubVar("Facile")
        app.category_display_names = {}
        app.category_labels = {}
        workflow = CatalogWorkflow(app)

        calls = []
        app.show_main_menu = lambda banner_message="": calls.append(("menu", banner_message))
        app.show_catalog_overlay = lambda banner_message="": calls.append(("catalog", banner_message))

        banner_message = workflow.reload_catalog_state(
            disabled_catalog,
            banner_message="Pack desactive : Pack Bonus.",
            reopen_catalog=True,
        )

        self.assertEqual(app.category_var.get(), "animaux")
        self.assertEqual(app.difficulty_var.get(), "Facile")
        self.assertIn("categorie de secours", banner_message)
        self.assertEqual(
            calls,
            [
                ("menu", banner_message),
                ("catalog", banner_message),
            ],
        )

    def test_reload_catalog_state_keeps_current_selection_when_new_pack_is_added(self):
        root_dir = self._make_workspace()
        base_dir = root_dir / "base"
        packs_dir = root_dir / "packs"
        base_dir.mkdir()
        packs_dir.mkdir()
        self._write_words(base_dir / "animaux.txt", FULL_SPECTRUM_WORDS)

        bonus_pack_dir = packs_dir / "bonus"
        bonus_pack_dir.mkdir()
        self._write_words(bonus_pack_dir / "sports.txt", FULL_SPECTRUM_WORDS)
        self._write_json(
            bonus_pack_dir / "pack.json",
            {
                "id": "bonus",
                "label": "Pack Bonus",
                "categories": [
                    {
                        "id": "sports",
                        "label": "Sports",
                        "source": "sports.txt",
                    }
                ],
            },
        )

        updated_catalog = load_category_catalog(base_dir=base_dir, local_pack_dir=packs_dir)

        app = HangmanApp.__new__(HangmanApp)
        app.category_var = StubVar("animaux")
        app.category_display_var = StubVar("Animaux")
        app.difficulty_var = StubVar("Facile")
        app.category_display_names = {}
        app.category_labels = {}
        workflow = CatalogWorkflow(app)

        calls = []
        app.show_main_menu = lambda banner_message="": calls.append(("menu", banner_message))
        app.show_catalog_overlay = lambda banner_message="": calls.append(("catalog", banner_message))

        banner_message = workflow.reload_catalog_state(
            updated_catalog,
            banner_message="Pack ajoute : Pack Bonus.",
            reopen_catalog=True,
        )

        self.assertEqual(app.category_var.get(), "animaux")
        self.assertEqual(app.difficulty_var.get(), "Facile")
        self.assertEqual(banner_message, "Pack ajoute : Pack Bonus.")
        self.assertEqual(
            calls,
            [
                ("menu", "Pack ajoute : Pack Bonus."),
                ("catalog", "Pack ajoute : Pack Bonus."),
            ],
        )


if __name__ == "__main__":
    unittest.main()

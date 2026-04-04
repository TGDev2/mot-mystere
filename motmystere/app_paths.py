from pathlib import Path
import os
import sys


APP_NAME = "MotMystere"
PACKAGE_DIR = Path(__file__).resolve().parent
WORDLISTS_DIR = PACKAGE_DIR / "assets" / "wordlists"
BUNDLED_WORDLISTS_DIR = Path("motmystere") / "assets" / "wordlists"


def get_resource_directory():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled_dir = Path(sys._MEIPASS) / BUNDLED_WORDLISTS_DIR
        if bundled_dir.exists():
            return bundled_dir
        return Path(sys._MEIPASS)
    return WORDLISTS_DIR


def get_data_directory():
    override = os.environ.get("MOTMYSTERE_DATA_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform.startswith("win"):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME

    return Path.home() / f".{APP_NAME.lower()}"


def get_database_path():
    override = os.environ.get("MOTMYSTERE_DB_PATH")
    if override:
        return Path(override).expanduser()
    return get_data_directory() / "hangman.db"


def get_word_packs_directory():
    return get_data_directory() / "packs"

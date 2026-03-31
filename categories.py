from pathlib import Path


BASE_DIR = Path(__file__).parent


def lire_mots(nom_fichier):
    fichier = Path(nom_fichier)
    with fichier.open("r", encoding="utf-8") as handle:
        return [mot.strip().upper() for mot in handle if mot.strip()]


def load_categories(base_dir=BASE_DIR):
    categories = {}
    for file in sorted(Path(base_dir).glob("*.txt")):
        categories[file.stem] = lire_mots(file)
    return categories

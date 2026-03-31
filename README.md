# MotMystere

MotMystere est un jeu du pendu desktop en Python/Tkinter, centre sur une boucle solo locale, fiable et rejouable. Cette version renforce trois axes du produit :

- une difficulte mieux calibree selon la complexite reelle des mots ;
- une progression joueur plus lisible avec historique et insights ;
- un lancement Windows plus simple avec build executable et donnees locales propres.

## Fonctionnalites

- Parcours solo clair : pseudo, categorie, difficulte, partie, rejouabilite.
- Calibration des manches par niveau de difficulte, longueur, lettres rares et repetition.
- Timer et nombre d'essais differencies selon la difficulte.
- Score persistant aligne sur la difficulte, la complexite du mot, le temps et les essais conserves.
- Profil joueur avec historique recent, niveau le plus rentable, categorie la plus jouee et categorie a travailler.
- Classement local persistant avec score total, meilleur score et taux de victoire.
- Mode multijoueur conserve a titre experimental dans `server.py`.

## Lancer le jeu

### Depuis le code source

```bash
python main.py
```

### Depuis Windows sans console

Double-cliquez sur `launch_motmystere.bat`.

Le lanceur essaie, dans cet ordre :

1. `dist/MotMystere.exe` si un build Windows existe deja
2. `pyw -3 main.py`
3. `pythonw main.py`

## Construire un executable Windows

PyInstaller est deja supporte dans le depot via `motmystere.spec`.

```powershell
.\build_windows.ps1
```

Le script valide d'abord que l'installation Python dispose bien de Tkinter/Tcl.

Le binaire genere est :

```text
dist\MotMystere.exe
```

## Donnees locales

La base SQLite n'est plus utilisee depuis la racine du depot au premier lancement. Par defaut :

- Windows : `%LOCALAPPDATA%\MotMystere\hangman.db`
- autres plateformes : `~/.motmystere/hangman.db`

Variables d'environnement utiles :

- `MOTMYSTERE_DB_PATH` pour forcer le chemin de la base
- `MOTMYSTERE_DATA_DIR` pour forcer le dossier de donnees

## Lancer les tests

```bash
python -m unittest discover -s tests
```

## Structure

- `main.py` : point d'entree de l'application
- `game_logic.py` : interface Tkinter, historique joueur et ecrans principaux
- `game_session.py` : regles de partie et etat de manche
- `categories.py` : chargement des categories et calibration des mots
- `scoring.py` : configuration de difficulte et calcul du score
- `database.py` : persistance SQLite, historique et classement
- `build_windows.ps1` / `motmystere.spec` : build Windows du jeu

## Positionnement actuel

La version principale du projet assume un perimetre stable et demonstrable : un jeu solo propre, maintenable et defendable en portfolio. Le multijoueur n'est pas supprime, mais il n'est toujours pas presente comme une fonctionnalite prete.

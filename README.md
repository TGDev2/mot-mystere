# MotMystere

MotMystere est un jeu du pendu desktop en Python/Tkinter, centre sur une boucle solo locale, fiable et rejouable. Cette version renforce trois axes du produit :

- une difficulte mieux calibree selon la complexite reelle des mots ;
- une progression joueur plus lisible avec historique et insights ;
- un lancement Windows plus simple avec build executable et donnees locales propres.

## Fonctionnalites

- Parcours solo clair : pseudo, categorie, difficulte, partie, rejouabilite.
- Calibration des manches par niveau de difficulte, longueur, lettres rares et repetition.
- Niveaux affiches uniquement lorsqu'un vrai pool de mots est disponible pour tenir la promesse.
- Timer et nombre d'essais differencies selon la difficulte.
- Score persistant aligne sur la difficulte, la complexite du mot, le temps et les essais conserves.
- Profil joueur avec historique recent, niveau le plus rentable, categorie la plus jouee et categorie a travailler.
- Objectifs explicites avec prochain palier recommande sur l'accueil, en manche et en fin de partie.
- Classement local persistant avec score total, meilleur score et taux de victoire.
- Saisie clavier A-Z active pendant la partie et ecran de fin de manche oriente progression.

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

Le script :

1. verifie d'abord que l'installation Python dispose bien de Tkinter/Tcl ;
2. lance la suite de tests unitaires ;
3. execute un smoke test source ;
4. build l'executable ;
5. rejoue le smoke test sur `dist\MotMystere.exe`.

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

Pour verifier rapidement le parcours critique sans ouvrir l'interface :

```bash
python main.py --smoke-test
```

## Structure

- `main.py` : point d'entree de l'application
- `game_logic.py` : interface Tkinter, historique joueur et ecrans principaux
- `game_session.py` : regles de partie et etat de manche
- `categories.py` : chargement des categories et calibration des mots
- `scoring.py` : configuration de difficulte et calcul du score
- `database.py` : persistance SQLite, historique et classement
- `release_smoke.py` : verification smoke test du parcours critique
- `build_windows.ps1` / `motmystere.spec` : build Windows du jeu

## Positionnement actuel

La version principale du projet assume un perimetre stable et demonstrable : un jeu solo propre, maintenable et defendable en portfolio.

Le depot peut encore contenir du code d'exploration annexe, mais rien de tout cela ne fait partie de la proposition de valeur livree. La version a evaluer reste strictement le parcours solo local.

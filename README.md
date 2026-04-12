# MotMystere

MotMystere est un jeu du pendu desktop en Python/Tkinter, centre sur une boucle solo locale, fiable et rejouable.

La version actuelle met l'accent sur trois axes:

- une difficulte mieux calibree selon la complexite reelle des mots ;
- une rejouabilite durable grace a une rotation complete des pools par joueur ;
- une progression lisible avec objectifs, recommandations et sessions guidees.

## Fonctionnalites

- Parcours solo local: pseudo, categorie, difficulte, manche, resume, rejouabilite.
- Accueil oriente reprise: profils recents, dernier reglage jouable, recommandation immediate.
- Calibration des mots par difficulte selon longueur, lettres rares et repetitions.
- Niveaux exposes uniquement lorsqu'un vrai pool jouable existe.
- Rotation persistante des mots par joueur, categorie et difficulte pour eviter les doublons avant epuisement.
- Score persistant lie a la difficulte, a la complexite du mot, au temps et aux essais restants.
- Progression par carte de validation et de maitrise, paliers de score, defis et profil d'apprentissage.
- Sessions guidees et revisions ciblees depuis l'accueil et la fin de manche.
- Catalogue extensible avec packs locaux activables/desactivables sans modifier le code.
- Import guide de packs `.zip` avec preview avant installation.
- Packs officiels embarques: `voyage.zip`, `culture.zip`, `science.zip`.
- Export/restauration de l'environnement local complet avec verification et sauvegarde de secours.
- Classement local persistant et overlays de pilotage editorial.

## Prerequis

- Python 3 avec Tkinter/Tcl disponible.
- Aucune dependance runtime tierce n'est requise pour lancer le jeu depuis le code source.
- `PyInstaller` n'est necessaire que pour construire l'executable Windows.

## Lancer le jeu

### Depuis le code source

```bash
python -m motmystere
```

`python main.py` reste disponible comme point d'entree de compatibilite.

### Depuis Windows sans console

Double-cliquez sur `launch_motmystere.bat`.

Le lanceur essaie, dans cet ordre:

1. `dist/MotMystere.exe` si un build Windows existe deja
2. `pyw -3 -m motmystere`
3. `pythonw -m motmystere`

## Verification rapide

Smoke test source:

```bash
python -m motmystere --smoke-test
```

Suite de tests:

```bash
python -m unittest discover -s tests
```

## Construire un executable Windows

Le depot contient deja `motmystere.spec` et un script de build:

```powershell
.\build_windows.ps1
```

Le script:

1. verifie la presence de Tkinter/Tcl ;
2. lance la suite de tests ;
3. execute un smoke test source ;
4. build `dist\MotMystere.exe` ;
5. rejoue le smoke test sur l'executable genere.

## Donnees locales

Le jeu n'utilise plus la base `hangman.db` a la racine du depot pour son runtime normal.

Par defaut:

- Windows: `%LOCALAPPDATA%\MotMystere\hangman.db`
- autres plateformes: `~/.motmystere/hangman.db`

Variables d'environnement utiles:

- `MOTMYSTERE_DATA_DIR` pour forcer le dossier de donnees
- `MOTMYSTERE_DB_PATH` pour forcer explicitement le chemin de la base

Le dossier de donnees peut aussi contenir:

- `catalog_state.json` pour les overrides d'activation des packs locaux ;
- `packs/<pack_id>/pack.json` et les fichiers de mots associes ;
- `backups/*.zip` pour les sauvegardes exportees.

## Packs de categories

Le catalogue charge:

- les categories integrees embarquees dans `motmystere/assets/wordlists/` ;
- les packs locaux installes dans le dossier de donnees.

Format minimal d'un pack:

```json
{
  "id": "voyage",
  "label": "Pack Voyage",
  "enabled": true,
  "categories": [
    {
      "id": "capitales",
      "label": "Capitales",
      "source": "capitales.txt",
      "enabled": true
    }
  ]
}
```

Regles principales:

- `id` de pack et de categorie: ascii minuscule, chiffres et `_` uniquement ;
- `source` est resolu relativement au dossier qui contient `pack.json` ;
- une categorie n'est jouable que si elle fournit au moins `5` mots pour le niveau vise ;
- la cible editoriale retenue pour un pool solide est `15` mots par niveau, soit `45` mots par categorie complete ;
- un pack ou une categorie desactive restent installes mais ne sont pas charges.

## Documentation

Le depot dispose maintenant d'une documentation structuree dans [`docs/README.md`](docs/README.md):

- [`docs/architecture.md`](docs/architecture.md): architecture globale et flux applicatifs.
- [`docs/presentation-architecture.md`](docs/presentation-architecture.md): contrat de la couche presentation.
- [`docs/gameplay-and-progression.md`](docs/gameplay-and-progression.md): regles de jeu, scoring, progression et sessions.
- [`docs/data-and-catalog.md`](docs/data-and-catalog.md): stockage local, schema SQLite, packs et sauvegardes.
- [`docs/editorial-maintenance.md`](docs/editorial-maintenance.md): calibration des difficultes et cockpit editorial.
- [`docs/development.md`](docs/development.md): environnement de dev, tests, build et points d'entree.

## Structure

- `motmystere/`: package principal de l'application.
- `motmystere/__main__.py`: point d'entree `python -m motmystere`.
- `motmystere/game_logic.py`: bootstrap Tkinter et facade applicative.
- `motmystere/workflows/`: workflows testables pour manche, catalogue, backup, progression et sessions guidees.
- `motmystere/presentation/`: routeur, shell de rendu partage et ecrans Tkinter.
- `motmystere/categories.py`: chargement du catalogue, validation des packs et calibration des mots.
- `motmystere/solo_game_service.py`: orchestration de rotation, resolution de manche et progression.
- `motmystere/database.py`: persistance SQLite, historique, classement et analyse de calibration.
- `motmystere/catalog_service.py` / `motmystere/backup_service.py`: gestion du catalogue local et des sauvegardes.
- `motmystere/editorial_cockpit.py` / `motmystere/difficulty_calibration.py`: lecture editoriale du catalogue et du signal reel.
- `motmystere/release_smoke.py`: smoke test de bout en bout.
- `tests/`: suite `unittest`.
- `experiments/server.py`: code experimental hors proposition de valeur principale.

## Positionnement actuel

Le perimetre de reference reste un jeu solo local, maintenable et defendable en portfolio.

Le depot peut contenir du code d'exploration annexe, mais la version a evaluer et a documenter reste strictement:

- le parcours solo local ;
- la progression persistante ;
- le catalogue local et ses packs ;
- les outils de maintenance editoriale necessaires pour faire evoluer ce catalogue proprement.

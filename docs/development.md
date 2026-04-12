# Developpement

## Prerequis

- Python 3 avec Tkinter/Tcl disponible.
- Aucune dependance runtime externe n'est necessaire pour le developpement courant.
- `PyInstaller` est uniquement requis pour le build Windows.

Le depot ne repose pas sur `pytest`, `poetry` ou un framework web. La base outillage est volontairement minimale.

## Commandes utiles

### Lancer le jeu

```bash
python -m motmystere
```

### Smoke test applicatif

```bash
python -m motmystere --smoke-test
```

### Suite de tests

```bash
python -m unittest discover -s tests
```

### Build Windows

```powershell
.\build_windows.ps1
```

## Ce que verifie le build Windows

`build_windows.ps1`:

1. verifie Tkinter/Tcl ;
2. lance toute la suite `unittest` ;
3. execute le smoke test source ;
4. build `dist\MotMystere.exe` via `motmystere.spec` ;
5. rejoue un smoke test sur l'executable.

## Cartographie rapide des tests

La suite est organisee par responsabilite.

### Domaine et persistance

- `tests/test_game_session.py`
- `tests/test_scoring.py`
- `tests/test_progression.py`
- `tests/test_database.py`
- `tests/test_solo_game_service.py`

### Catalogue, packs et sauvegardes

- `tests/test_categories.py`
- `tests/test_catalog_service.py`
- `tests/test_official_packs.py`
- `tests/test_backup_service.py`

### Workflows et orchestration UI

- `tests/test_round_loop_workflow.py`
- `tests/test_guided_session_workflow.py`
- `tests/test_action_priority.py`
- `tests/test_catalog_game_logic.py`
- `tests/test_backup_game_logic.py`

### Presentation et navigation

- `tests/test_presentation_navigation.py`
- `tests/test_priority_screens.py`

### Maintenance editoriale

- `tests/test_difficulty_calibration.py`
- `tests/test_editorial_cockpit.py`

### Verification de release

- `tests/test_release_smoke.py`

## Points d'entree principaux

- `main.py`
  Compatibilite.

- `motmystere/__main__.py`
  Entree principale et mode smoke test.

- `motmystere/game_logic.py`
  Composition de l'application.

## Recommandations selon la zone modifiee

### Si vous touchez les regles de jeu

Relancer au minimum:

- `tests/test_game_session.py`
- `tests/test_scoring.py`
- `tests/test_solo_game_service.py`
- `tests/test_round_loop_workflow.py`

### Si vous touchez la progression

Relancer au minimum:

- `tests/test_progression.py`
- `tests/test_action_priority.py`
- `tests/test_guided_session_workflow.py`

### Si vous touchez catalogue, packs ou backup

Relancer au minimum:

- `tests/test_categories.py`
- `tests/test_catalog_service.py`
- `tests/test_official_packs.py`
- `tests/test_backup_service.py`

### Si vous touchez la navigation ou les ecrans

Relancer au minimum:

- `tests/test_presentation_navigation.py`
- `tests/test_priority_screens.py`

## Structure de code a respecter

- les ecrans Tkinter restent dans `motmystere/presentation/screens/` ;
- les workflows coordonnent l'application, mais ne calculent pas tout en inline ;
- les services et modules metier doivent rester testables sans UI ;
- les ports `Null*` et `Tk*` servent a separer les side effects des tests.

## Donnees de dev

Le runtime normal ecrit hors du depot, sauf si vous forcez:

- `MOTMYSTERE_DATA_DIR`
- `MOTMYSTERE_DB_PATH`

Pour isoler des essais locaux, pointez ces variables vers un dossier temporaire.

## Fichiers a connaitre avant toute evolution importante

- `motmystere/game_logic.py`
- `motmystere/solo_game_service.py`
- `motmystere/categories.py`
- `motmystere/database.py`
- `motmystere/progression.py`
- `motmystere/workflows/`
- `motmystere/presentation/`

La lecture combinee de [`architecture.md`](architecture.md) et [`presentation-architecture.md`](presentation-architecture.md) est le point de depart recommande avant un refactoring.

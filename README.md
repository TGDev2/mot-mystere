# MotMystere

MotMystere est un jeu du pendu desktop en Python/Tkinter. Cette version est recentrée sur une boucle solo fiable, avec catégories, difficulté, timer, score persistant et classement local.

## Fonctionnalités

- Parcours solo clair: pseudo, catégorie, difficulté, partie, rejouabilité.
- Score de progression basé sur la difficulté, le temps restant et les essais conservés.
- Classement local persistant avec score total, meilleur score et taux de victoire.
- Données de joueurs nettoyées: les pseudos vides ne sont plus acceptés.
- Mode multijoueur conservé à titre expérimental dans `server.py`.

## Lancer le jeu

```bash
python main.py
```

## Lancer les tests

```bash
python -m unittest discover -s tests
```

## Structure

- `main.py`: point d'entrée de l'application.
- `game_logic.py`: interface Tkinter et orchestration.
- `game_session.py`: règles de partie et état métier.
- `scoring.py`: configuration de difficulté et calcul du score.
- `database.py`: persistance SQLite et classement.

## Positionnement actuel

La version principale du projet assume un périmètre stable et démontrable: un jeu solo propre, maintenable et défendable en portfolio. Le multijoueur n'est pas supprimé, mais il n'est plus présenté comme une fonctionnalité prête.

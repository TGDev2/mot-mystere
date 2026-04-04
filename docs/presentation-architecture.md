# Architecture de presentation

## Objectif

La couche presentation est decoupee pour isoler trois responsabilites:

- `motmystere/game_logic.py` orchestre l'etat applicatif, la navigation et les transitions de manche.
- `motmystere/presentation/navigation.py` formalise les routes d'ecran et d'overlay, avec un routeur testable.
- `motmystere/presentation/screens/` contient un module par ecran cle ou overlay.

## Decoupage

### Orchestrateur

`HangmanApp` conserve:

- l'etat durable de l'application (`player`, `session`, `guided_session`);
- les actions utilisateur qui modifient cet etat (`start_game`, `finish_round`, `return_to_menu`);
- les integrations avec les services (`prepare_player`, `resolve_round`, `get_progression_bundle`).

Il ne construit plus directement les ecrans.

### Shell UI partage

`motmystere/presentation/shell.py` centralise les briques de rendu reutilisables:

- cartes, labels, sections ;
- cartes de progression et defis ;
- grille de maitrise ;
- cartes de metriques.

Une evolution visuelle transverse passe par ce shell, pas par chaque ecran.

### Ecrans

Les ecrans sont isoles dans `motmystere/presentation/screens/`:

- `main_menu.py` : accueil, reprise rapide, formulaire de lancement.
- `game_round.py` : manche en cours.
- `round_summary.py` : fin de manche et resume de session guidee.
- `player_dashboard.py` : overlay profil.
- `leaderboard.py` : overlay classement.

Chaque module ne gere que sa composition visuelle et les callbacks qu'il expose.

## Contrat de navigation

Les routes explicites sont definies dans `motmystere/presentation/navigation.py`:

- `main_menu`
- `round`
- `round_summary`
- `guided_session_summary`
- `player_dashboard`
- `leaderboard`

Le parcours critique attendu est:

1. `main_menu`
2. `round`
3. `round_summary`
4. `player_dashboard` ou `leaderboard`

Ce contrat est verifie automatiquement dans [tests/test_presentation_navigation.py](/c:/Users/DIEUTAXI/Documents/Projects/MotMystere/MotMystere/tests/test_presentation_navigation.py).

## Impact attendu pour les evolutions

- Faire evoluer un ecran cible ne demande plus de retoucher le layout des autres.
- La navigation est observable et testable sans lancer toute l'interface Tkinter.
- Les composants visuels partages restent dans un point unique, ce qui limite les regressions de style et de structure.

# Architecture de presentation

## Objectif

La couche presentation est decoupee pour isoler quatre responsabilites:

- `motmystere/game_logic.py` compose l'application et expose une facade stable aux ecrans.
- `motmystere/presentation/navigation.py` formalise les routes d'ecran et d'overlay, avec un routeur testable.
- `motmystere/presentation/screens/` contient un module par ecran cle ou overlay.
- `motmystere/workflows/` porte les workflows applicatifs par responsabilite.

## Decoupage

### Orchestrateur

`HangmanApp` conserve:

- le bootstrap Tkinter, les `StringVar` et les references d'ecrans/overlays ;
- le routeur de presentation ;
- la facade publique appelee par les ecrans (`start_game`, `finish_round`, `return_to_menu`, `show_catalog_overlay`, etc.).

Il ne porte plus directement la logique complete des workflows catalogue, backup, manche et session guidee.

### Workflows applicatifs

`motmystere/workflows/` regroupe les flux majeurs:

- `catalog.py` : reload du catalogue, preview/import de packs, toggles et bundles editoriaux.
- `backup.py` : export/import de sauvegarde et rehydratation de l'environnement apres restauration.
- `round_loop.py` : creation de manche, saisie, timer, resolution et routage de fin de manche.
- `guided_session.py` : demarrage, continuation, cloture et evaluation des sessions guidees/revisions.

Deux supports transverses restent internes a cette couche:

- `selection_support.py` : selection categorie/difficulte, sync apres reload et snapshots d'exploration.
- `player_progression_support.py` : chargement joueur, progression, recent players et resume profil.

Les appels side-effect UI sont encapsules par `ports.py` pour isoler:

- dialogues et selecteurs de fichiers ;
- timer Tkinter.

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
- `catalog.py` : overlay de gestion du catalogue et des packs locaux.

Chaque module ne gere que sa composition visuelle et les callbacks qu'il expose.

## Contrat de navigation

Les routes explicites sont definies dans `motmystere/presentation/navigation.py`:

- `main_menu`
- `round`
- `round_summary`
- `guided_session_summary`
- `player_dashboard`
- `leaderboard`
- `catalog`

Le parcours critique attendu est:

1. `main_menu`
2. `round`
3. `round_summary`
4. `player_dashboard` ou `leaderboard`

Ce contrat est verifie automatiquement dans [tests/test_presentation_navigation.py](/c:/Users/DIEUTAXI/Documents/Projects/MotMystere/MotMystere/tests/test_presentation_navigation.py).

## Impact attendu pour les evolutions

- Faire evoluer un ecran cible ne demande plus de retoucher le layout des autres.
- La navigation est observable et testable sans lancer toute l'interface Tkinter.
- Faire evoluer un workflow majeur n'impose plus de concentrer les changements dans `game_logic.py`.
- Les composants visuels partages restent dans un point unique, ce qui limite les regressions de style et de structure.

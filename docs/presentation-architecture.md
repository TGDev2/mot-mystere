# Architecture de presentation

## Objectif

La couche presentation est decoupee pour separer:

- la composition applicative ;
- la navigation ;
- les ecrans et overlays ;
- les workflows ;
- les briques UI partagees.

Le but est de faire evoluer la presentation sans re-concentrer la logique dans `game_logic.py`.

## Composition generale

`motmystere/game_logic.py` contient `HangmanApp`, qui assemble:

- la fenetre Tkinter ;
- les `StringVar` et references de widgets ;
- les services (`CatalogService`, `BackupService`) ;
- les workflows ;
- le `PresentationRouter` ;
- les objets ecran.

`HangmanApp` reste la facade appelee par l'UI, mais delegue la logique detaillee aux workflows.

## Navigation

La navigation est formalisee dans `motmystere/presentation/navigation.py`.

### Ecrans

- `main_menu`
- `round`
- `round_summary`
- `guided_session_summary`

### Overlays

- `player_dashboard`
- `leaderboard`
- `catalog`
- `editorial_cockpit`
- `difficulty_calibration`

Le routeur enregistre un historique de `NavigationEvent`, ce qui permet de verifier le contrat de navigation sans lancer tout le rendu.

## Ecrans et overlays

Les composants d'ecran sont isoles dans `motmystere/presentation/screens/`.

- `main_menu.py`
  Accueil, formulaire de lancement, profils recents, actions prioritaires.

- `game_round.py`
  Manche en cours, clavier, timer, hints et suivi de progression.

- `round_summary.py`
  Resume de manche et resume de session guidee ou revision ciblee.

- `player_dashboard.py`
  Profil joueur detaille.

- `leaderboard.py`
  Classement local.

- `catalog.py`
  Gestion des packs, preview d'import et alertes catalogue.

- `editorial_cockpit.py`
  Vue de priorisation editoriale par pack et categorie.

- `difficulty_calibration.py`
  Vue technique de calibration des paires categorie/niveau.

Chaque module de `screens/` se limite a:

- composer les widgets ;
- afficher des donnees deja preparees ;
- relier les callbacks exposes par `HangmanApp`.

## Shell UI partage

`motmystere/presentation/shell.py` centralise les briques de rendu reutilisables:

- cartes ;
- sections ;
- metriques ;
- cartes de progression ;
- grille de maitrise ;
- cartes de rotation et d'exploration.

Une evolution visuelle transverse doit passer par ce shell, pas par duplication dans plusieurs ecrans.

## Workflows relies a la presentation

La presentation est pilotee par les workflows de `motmystere/workflows/`.

- `round_loop.py`
  Flux de manche, timer, frappes clavier et resolution.

- `guided_session.py`
  Sessions guidees et revisions avant/apres manche.

- `catalog.py`
  Overlay catalogue, refresh, import, toggle et bundles editoriaux.

- `backup.py`
  Export/restauration et rehydratation de l'UI apres restauration.

- `player_progression_support.py`
  Chargement joueur, profils recents et progression.

- `selection_support.py`
  Synchronisation categorie/difficulte et hints catalogue.

Les appels a `messagebox`, `filedialog` et `after()` sont encapsules par `ports.py` pour rester testables.

## Contrat de navigation attendu

Le parcours critique minimal reste:

1. `main_menu`
2. `round`
3. `round_summary`

Selon le contexte, le flux peut ensuite ouvrir:

- `guided_session_summary`
- `player_dashboard`
- `leaderboard`
- `catalog`
- `editorial_cockpit`
- `difficulty_calibration`

Ce contrat est verifie par [`tests/test_presentation_navigation.py`](../tests/test_presentation_navigation.py).

## Impact attendu pour les evolutions

- Faire evoluer un ecran cible ne demande plus de retoucher tous les autres.
- La navigation est observable et testable.
- Les side effects Tkinter sont limites et mieux encapsules.
- Les refactorings de logique applicative n'imposent plus de grossir `HangmanApp`.

# Architecture globale

## Perimetre

MotMystere est un jeu desktop Tkinter structure autour d'un parcours solo local. Le code de production couvre quatre ensembles:

- le bootstrap et la composition applicative ;
- la presentation et la navigation ;
- les workflows et services applicatifs ;
- le coeur metier et la persistance.

Le fichier `experiments/server.py` reste hors de ce perimetre.

## Vue d'ensemble

```text
main.py
  -> motmystere.__main__.main()
     -> setup_database()
     -> HangmanApp
        -> services (catalogue, backup)
        -> workflows
        -> routeur de presentation
        -> ecrans Tkinter
```

Les dependances runtime restent volontairement simples:

- stdlib Python ;
- Tkinter/Tcl pour l'interface ;
- SQLite via `sqlite3`.

## Couches principales

### 1. Entree et bootstrap

- `main.py`
  Point d'entree de compatibilite.

- `motmystere/__main__.py`
  Point d'entree principal. Prepare la base, gere le mode `--smoke-test` et instancie `HangmanApp`.

### 2. Composition applicative

- `motmystere/game_logic.py`
  Contient `HangmanApp`, la facade centrale de l'application. Cette classe:
  - cree la fenetre Tkinter et les `StringVar` ;
  - compose les services et workflows ;
  - expose les callbacks appeles par les ecrans ;
  - delegue l'essentiel de la logique aux workflows.

`HangmanApp` n'est plus l'endroit ou toute la logique est codee en ligne. Il sert surtout de point de raccord entre UI, workflows et etat courant.

### 3. Presentation

- `motmystere/presentation/navigation.py`
  Definit les routes d'ecran et d'overlay, plus l'historique de navigation observable en tests.

- `motmystere/presentation/shell.py`
  Centralise les briques visuelles partagees.

- `motmystere/presentation/screens/`
  Un module par ecran ou overlay: accueil, manche, resume, profil, classement, catalogue, cockpit editorial, calibration.

La couche presentation ne calcule pas les regles metier. Elle consomme des donnees preparees par les workflows et services.

### 4. Workflows applicatifs

- `motmystere/workflows/round_loop.py`
  Demarrage de manche, saisie clavier, timer, resolution et retour menu.

- `motmystere/workflows/guided_session.py`
  Sessions guidees et revisions ciblees, avant et apres chaque manche.

- `motmystere/workflows/catalog.py`
  Refresh du catalogue, preview/import de packs, toggles d'activation, bundles editoriaux.

- `motmystere/workflows/backup.py`
  Export/restauration de l'environnement local et rehydratation de l'UI apres restauration.

- `motmystere/workflows/player_progression_support.py`
  Chargement du joueur actif, progression, profils recents et resume joueur.

- `motmystere/workflows/selection_support.py`
  Synchronisation categorie/difficulte, hints de catalogue et etat d'exploration.

- `motmystere/workflows/ports.py`
  Ports de dialogue, de fichiers et de timer, avec implementations Tk et versions nulles pour les tests.

Ce decoupage permet de tester les flux sans reconstruire tout le rendu Tkinter.

### 5. Coeur metier

- `motmystere/game_session.py`
  Modele d'une manche et regles atomiques de proposition de lettres.

- `motmystere/scoring.py`
  Configuration des difficultes et calcul du score.

- `motmystere/progression.py`
  Snapshot de progression, carte de maitrise, objectifs, defis, recommandations et options de revision.

- `motmystere/solo_game_service.py`
  Couche d'orchestration pure autour du joueur, de la rotation des mots, des sessions guidees/review et de la resolution de manche.

- `motmystere/action_priority.py`
  Priorisation des actions a afficher sur l'accueil et la fin de manche.

### 6. Catalogue, calibration et persistence

- `motmystere/categories.py`
  Charge les categories integrees et locales, valide les manifests de packs et calibre les mots par difficulte.

- `motmystere/catalog_service.py`
  Persiste l'etat du catalogue local, gere les previews/imports et expose la bibliotheque de packs officiels.

- `motmystere/database.py`
  Gere SQLite: joueurs, historique, rotation, leaderboard, dashboards et requetes de calibration.

- `motmystere/backup_service.py`
  Exporte et restaure la base, l'etat du catalogue et les packs locaux.

- `motmystere/difficulty_calibration.py`
  Transforme l'historique des parties en signal de calibration par paire categorie/niveau.

- `motmystere/editorial_cockpit.py`
  Fusionne profondeur editoriale et signal reel pour prioriser enrichissement, recalibrage ou desactivation.

## Flux nominaux

### Demarrer une manche standard

1. L'accueil collecte pseudo, categorie et difficulte.
2. `PlayerProgressionSupport` charge ou cree le joueur.
3. `RoundLoopWorkflow` demande a `solo_game_service.create_session_for_player()` de construire la manche.
4. `solo_game_service` consulte l'etat de rotation dans SQLite, choisit un mot admissible et sauvegarde le nouvel etat de rotation.
5. L'ecran de manche s'affiche et le timer est planifie.

### Resoudre une manche

1. `RoundLoopWorkflow.finish_round()` coupe le timer.
2. `solo_game_service.resolve_round()` calcule le score, enregistre l'historique et recharge la progression.
3. Le workflow met a jour le joueur actif, l'etat d'exploration et la session guidee si besoin.
4. L'application affiche soit un resume de manche, soit un resume de session guidee.

### Importer un pack

1. `CatalogWorkflow` ouvre un selecteur de fichier ou de dossier.
2. `CatalogService.inspect_pack_source()` prepare une preview a partir du manifest inspecte.
3. L'overlay de catalogue affiche les bloqueurs, alertes et categories jouables.
4. Si l'import est confirme, `CatalogService.import_pack_from_source()` copie le pack dans le dossier de donnees puis persiste l'etat d'activation.
5. Le workflow recharge tout le catalogue et resynchronise la selection active.

### Restaurer une sauvegarde

1. `BackupWorkflow` demande le fichier `.zip`.
2. `BackupService.import_archive()` extrait vers un staging, valide le manifest, la base et le catalogue.
3. Si des donnees existent deja, une sauvegarde de secours est creee.
4. Les fichiers geres sont remplaces.
5. Le workflow recharge le catalogue, tente de recharger le profil le plus recent, puis revient a l'accueil.

## Principes de conception

- Une responsabilite par module quand le flux devient assez important pour etre teste seul.
- Les ecrans assemblent l'UI, les workflows pilotent les interactions, les services et modules metier calculent les resultats.
- Le runtime local est source de verite: base SQLite, etat du catalogue, packs locaux.
- La maintenance editoriale repose sur des fonctions deterministes documentees, pas sur des regles implicites dispersees dans l'UI.

## Fichiers utiles selon la modification

- Modifier une regle de manche: `game_session.py`, `round_loop.py`, `solo_game_service.py`.
- Modifier le scoring ou la difficulte: `scoring.py`, `categories.py`, `difficulty_calibration.py`.
- Modifier progression ou recommandations: `progression.py`, `action_priority.py`, `guided_session.py`.
- Modifier packs, import ou catalogue: `categories.py`, `catalog_service.py`, `workflows/catalog.py`.
- Modifier sauvegarde/restauration: `backup_service.py`, `workflows/backup.py`.
- Modifier navigation ou affichage: `presentation/navigation.py`, `presentation/shell.py`, `presentation/screens/`.

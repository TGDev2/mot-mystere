# Donnees locales et catalogue

## Emplacement des donnees

Par defaut, les donnees runtime sont stockees hors du depot.

### Dossier de donnees

- Windows: `%LOCALAPPDATA%\MotMystere`
- autres plateformes: `~/.motmystere`

Override possible:

- `MOTMYSTERE_DATA_DIR`

### Base SQLite

Chemin par defaut:

- `<data_dir>/hangman.db`

Override possible:

- `MOTMYSTERE_DB_PATH`

## Fichiers geres

Le dossier de donnees peut contenir:

- `hangman.db`
- `catalog_state.json`
- `packs/<pack_id>/...`
- `backups/*.zip`

Le jeu gere ces fichiers comme un ensemble coherent lors des exports/restaurations.

## Schema SQLite

La base est preparee par `motmystere/database.py`.

### Table `players`

Role:

- profil joueur unique par pseudo ;
- stats agregees persistantes.

Colonnes principales:

- `id`
- `name`
- `games_played`
- `games_won`
- `games_lost`
- `score_total`
- `best_score`
- `last_score`

### Table `game_history`

Role:

- historique detaille des manches ;
- source des dashboards, du classement et de la calibration editoriale.

Colonnes principales:

- `player_id`
- `category`
- `difficulty`
- `secret_word`
- `won`
- `end_reason`
- `attempts_left`
- `time_remaining`
- `attempts_limit`
- `time_limit`
- `word_complexity`
- `score_earned`
- `played_at`

### Table `word_rotation`

Role:

- suivi de la rotation par joueur, categorie et difficulte.

Colonnes principales:

- `player_id`
- `category`
- `difficulty`
- `remaining_words`
- `last_word`
- `window_size`
- `pool_signature`

## Migrations prises en charge

`setup_database()` prend en charge:

- la creation initiale des tables ;
- l'ajout de colonnes manquantes sur des bases plus anciennes ;
- le backfill des limites de temps/essais dans `game_history` ;
- la migration legacy depuis une ancienne table `stats`.

## Catalogue integre

Le catalogue de base vient de:

- `motmystere/assets/wordlists/*.txt`

Chaque fichier `.txt` devient une categorie integree. Les doublons sont ignores apres normalisation.

## Packs locaux

Les packs locaux sont lus depuis:

- `<data_dir>/packs/<pack_id>/pack.json`

### Contraintes de format

Regles principales:

- `id` de pack et de categorie: ascii minuscule, chiffres et `_` ;
- `categories` doit etre une liste non vide ;
- chaque categorie doit declarer un `source` ;
- `source` est resolu relativement au dossier du manifest ;
- `enabled` doit etre un booleen, au niveau pack comme au niveau categorie.

### Statuts possibles

Au chargement, un pack peut etre:

- `active`
- `disabled`
- `invalid`

Une categorie peut etre:

- `active`
- `disabled`
- `invalid`

Un pack invalide reste visible dans les outils editoriaux, mais il n'est pas charge dans le catalogue jouable.

## Etat du catalogue

`catalog_state.json` persiste les overrides d'activation des packs locaux:

```json
{
  "pack_overrides": {
    "voyage": {
      "enabled": false
    }
  }
}
```

Ce fichier ne duplique pas le contenu des packs. Il ne memorise que l'etat d'activation force.

## Packs officiels embarques

Le depot embarque:

- `motmystere/assets/official_packs/index.json`
- `motmystere/assets/official_packs/*.zip`

Chaque entree de l'index declare:

- l'identifiant du pack ;
- son label ;
- sa description ;
- le nom de l'archive ;
- les categories annoncees.

Ces packs peuvent etre inspectes et installes depuis l'interface sans connexion reseau.

## Import de packs

`CatalogService` accepte deux sources:

- un dossier contenant `pack.json` ;
- une archive `.zip`.

Pour les archives `.zip`, la structure acceptee est:

- `pack.json` a la racine ;
- ou un unique dossier racine contenant `pack.json`.

Les cas refuses incluent:

- archive sans `pack.json` ;
- plusieurs `pack.json` ;
- plusieurs racines top-level ;
- pack deja installe ;
- dossier cible deja existant ;
- pack sans categorie jouable.

## Format des sauvegardes

`BackupService` exporte une archive ZIP avec:

- `manifest.json`
- `db/hangman.db`
- `data/catalog_state.json` si present
- `packs/...` si des packs locaux existent

### Manifest

Le manifest contient:

- `app_name`
- `backup_format_version`
- `exported_at`
- `includes`
- `logical_targets`

Le service valide strictement:

- le nom d'application ;
- la version du format ;
- la coherence entre `includes` et le contenu reel de l'archive ;
- les cibles logiques attendues.

## Restauration

La restauration:

1. extrait dans un dossier temporaire ;
2. valide la base, le manifest et le catalogue ;
3. cree une sauvegarde de secours si l'environnement courant contient deja des donnees ;
4. remplace la base, l'etat catalogue et les packs locaux.

Il n'y a pas de fusion partielle. La restauration remplace l'environnement gere.

# MotMystere

MotMystere est un jeu du pendu desktop en Python/Tkinter, centre sur une boucle solo locale, fiable et rejouable. Cette version renforce trois axes du produit :

- une difficulte mieux calibree selon la complexite reelle des mots ;
- une rejouabilite plus durable grace a une rotation complete des pools ;
- une progression joueur plus lisible avec historique, maitrise et objectifs clairs.

## Fonctionnalites

- Parcours solo clair : pseudo, categorie, difficulte, partie, rejouabilite.
- Accueil oriente reprise : profils recents, dernier reglage rejouable et recommandation immediate.
- Calibration des manches par niveau de difficulte, longueur, lettres rares et repetition.
- Niveaux affiches uniquement lorsqu'un vrai pool de mots est disponible pour tenir la promesse.
- Catalogue extensible : packs locaux activables/desactivables sans modifier le code.
- Parcours d'import guide : preview avant installation, import `.zip` nominal, activation immediate ou differee.
- Packs officiels embarques : `voyage.zip`, `culture.zip` et `science.zip`, prets a installer depuis l'interface.
- Rotation persistante des mots par joueur, categorie et niveau pour eviter les doublons avant epuisement du pool.
- Timer et nombre d'essais differencies selon la difficulte.
- Score persistant aligne sur la difficulte, la complexite du mot, le temps et les essais conserves.
- Export/restauration de l'environnement local complet avec archive ZIP versionnee et sauvegarde de secours avant remplacement.
- Profil joueur avec historique recent, niveau le plus rentable, categorie la plus jouee et categorie a travailler.
- Carte de maitrise categorie x difficulte avec paires a valider puis a maitriser.
- Objectifs explicites avec prochain palier recommande sur l'accueil, en manche et en fin de partie.
- Defis du moment derives de la maitrise, de la regularite recente et du prochain cap de score.
- Session guidee optionnelle depuis l'accueil et la fin de manche pour enchainer plusieurs manches vers un objectif concret.
- Classement local persistant avec score total, meilleur score et taux de victoire.
- Saisie clavier A-Z active pendant la partie et ecran de fin de manche oriente progression.

## Lancer le jeu

### Depuis le code source

```bash
python -m motmystere
```

`python main.py` reste disponible comme point d'entree de compatibilite.

### Depuis Windows sans console

Double-cliquez sur `launch_motmystere.bat`.

Le lanceur essaie, dans cet ordre :

1. `dist/MotMystere.exe` si un build Windows existe deja
2. `pyw -3 -m motmystere`
3. `pythonw -m motmystere`

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

Depuis l'accueil, deux actions permettent maintenant de proteger ou transferer l'environnement local complet :

- `Sauvegarder mes donnees` exporte une archive `.zip` contenant la base SQLite, l'etat du catalogue et les packs locaux.
- `Restaurer une sauvegarde` valide l'archive, cree une sauvegarde de secours dans `<data_dir>/backups`, puis remplace l'environnement gere sans fusion partielle.

## Packs de categories

Le jeu charge toujours les categories integrees du depot ou du build. Il peut en plus charger des packs locaux dans :

- Windows : `%LOCALAPPDATA%\MotMystere\packs\<nom_du_pack>\pack.json`
- si `MOTMYSTERE_DATA_DIR` est defini : `<MOTMYSTERE_DATA_DIR>\packs\<nom_du_pack>\pack.json`

Format minimal d'un pack :

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

Regles du catalogue :

- `id` de pack et de categorie : minuscules ascii, chiffres et `_` uniquement.
- `source` est resolu relativement au dossier qui contient `pack.json`.
- un pack ou une categorie avec `enabled: false` reste present localement mais n'est pas charge.
- une categorie est jouable seulement si au moins un niveau atteint le minimum garanti (`5` mots).
- si une categorie ne couvre qu'une partie des niveaux, seuls les niveaux soutenus sont exposes.
- les packs invalides, incomplets ou avec fichiers manquants sont signales dans l'interface sans casser l'historique existant.

Depuis l'overlay `Catalogue`, le parcours nominal est maintenant :

1. importer une archive `.zip` ;
2. lire la preview du pack (categories ajoutees, jouables, bloquees, statut) ;
3. choisir `Installer et activer` ou `Installer sans activer`.

Le chemin historique par dossier reste disponible comme option expert.

## Packs officiels embarques

Le build embarque aussi trois packs fiables prets a installer depuis l'interface :

- `voyage.zip` : `Capitales`, `Monuments`, `Transports`
- `culture.zip` : `Cinema`, `Litterature`, `Mythologie`
- `science.zip` : `Informatique`, `Espace`, `Sciences`

Chaque categorie officielle fournit au moins `45` mots uniques, avec `15` mots minimum en `Facile`, `Moyen` et `Difficile`.

## Lancer les tests

```bash
python -m unittest discover -s tests
```

Pour verifier rapidement le parcours critique sans ouvrir l'interface :

```bash
python -m motmystere --smoke-test
```

Le contrat de navigation presentation est aussi couvert par `tests/test_presentation_navigation.py`.

## Structure

- `motmystere/` : package principal de l'application
- `motmystere/__main__.py` : point d'entree executable via `python -m motmystere`
- `motmystere/game_logic.py` : orchestrateur d'etat, navigation et callbacks UI
- `motmystere/presentation/` : routeur, shell de rendu partage et ecrans Tkinter modules
- `motmystere/assets/wordlists/` : listes de mots integrees emballees avec le jeu
- `motmystere/game_session.py` : regles de partie et etat de manche
- `motmystere/categories.py` : chargement du catalogue, validation des packs et calibration des mots
- `motmystere/scoring.py` : configuration de difficulte et calcul du score
- `motmystere/database.py` : persistance SQLite, historique et classement
- `motmystere/solo_game_service.py` : orchestration testable de la rotation, de la resolution de manche et de la progression
- `motmystere/release_smoke.py` : verification smoke test du parcours critique
- `experiments/server.py` : serveur TCP experimental conserve hors du parcours solo principal
- `docs/presentation-architecture.md` : contrat de decoupage de la couche presentation
- `build_windows.ps1` / `motmystere.spec` : build Windows du jeu

## Positionnement actuel

La version principale du projet assume un perimetre stable et demonstrable : un jeu solo propre, rejouable, maintenable et defendable en portfolio.

Le depot peut encore contenir du code d'exploration annexe, mais rien de tout cela ne fait partie de la proposition de valeur livree. La version a evaluer reste strictement le parcours solo local.

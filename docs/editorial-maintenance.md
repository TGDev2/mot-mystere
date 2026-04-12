# Maintenance editoriale

## Objectif

MotMystere ne se contente pas de charger des listes de mots. Le projet fournit aussi une lecture editoriale pour aider a:

- desactiver les contenus non fiables ;
- enrichir les categories trop courtes ;
- recalibrer les difficultes quand le signal reel contredit la promesse ;
- distinguer les categories stables de celles qui manquent simplement de recul.

Deux modules pilotent cette lecture:

- `motmystere/difficulty_calibration.py`
- `motmystere/editorial_cockpit.py`

## Cibles editoriales

Une categorie complete vise:

- `15` mots par niveau ;
- `45` mots au total.

Une categorie reste jouable a partir de `5` mots sur un niveau donne, mais elle sera consideree sous-cible editorialement si elle n'atteint pas les volumes ci-dessus.

## Calibration des difficultes

La calibration reelle s'appuie sur les parties enregistrees dans `game_history`.

### Bandes cibles de taux de victoire

| Difficulte | Bande cible |
| --- | --- |
| Facile | 68%-88% |
| Moyen | 45%-70% |
| Difficile | 22%-48% |

### Lissage

Le taux observe est lisse avec `6` pseudo-parties centrees sur le milieu de la bande cible. Cela evite de sur-reagir aux petits echantillons.

### Statuts

- `insufficient_data`
  Moins de `8` parties sur la paire active.

- `stable`
  Le taux lisse reste dans sa bande, ou l'ecart n'est pas assez fort pour meriter un signal.

- `watch`
  Le taux lisse sort de sa bande d'au moins `8` points.

- `review`
  L'ecart atteint `12` points ou plus, avec au moins `15` parties, un signal coherent et une confiance suffisante.

### Signal "plus dur"

Une paire parait trop dure si l'historique montre au moins un des signaux suivants:

- taux de fin au temps `>= 25 %`
- taux de fin par epuisement des essais `>= 25 %`
- marges moyennes de victoire sous les planchers du niveau

Planchers de marge de victoire:

| Difficulte | Marge temps | Marge essais |
| --- | ---: | ---: |
| Facile | 20% | 25% |
| Moyen | 12% | 15% |
| Difficile | 5% | 10% |

### Signal "plus facile"

Une paire parait trop facile si les marges moyennes de victoire sont toutes deux `>= 35 %` sur le temps et les essais.

### Confiance minimale pour `review`

Le statut `review` demande aussi:

- au moins `2` joueurs distincts ou `25` parties ;
- aucun joueur dominant au-dela de `70 %` de l'echantillon.

## Cockpit editorial

Le cockpit editorial combine:

- la profondeur editoriale du catalogue ;
- le statut reel de calibration ;
- le statut d'installation/activation des packs.

### Actions recommandees

Quatre actions sont possibles:

- `disable`
  Le pack ou la categorie n'est pas assez fiable pour rester dans le catalogue actif.

- `enrich`
  Le contenu est jouable, mais trop court par rapport a la cible editoriale.

- `recalibrate`
  Le volume est suffisant, mais le comportement reel contredit la promesse de difficulte.

- `keep`
  Aucune action prioritaire immediate.

### Priorisation

La priorite remonte selon:

1. l'action recommandee ;
2. l'ampleur du manque de couverture ;
3. le nombre de paires `review` ;
4. la distance maximale a la bande cible.

Le cockpit produit:

- une vue par pack ;
- une vue par categorie ;
- des sections de priorite (`Desactiver`, `Enrichir`, `Recalibrer`, `Laisser`) ;
- des cartes de synthese.

## Lecture pratique

### Quand enrichir

Enrichir une categorie si:

- elle est jouable mais sous `45` mots ;
- un ou plusieurs niveaux sont absents ;
- un niveau reste entre `1` et `14` mots.

### Quand recalibrer

Recalibrer une categorie si:

- la couverture est suffisante ;
- une ou plusieurs paires sont en `review`.

Recalibrer signifie generalement:

- deplacer certains mots vers le niveau inferieur ou superieur ;
- ou enrichir un niveau avec des mots plus adaptes a la promesse visee.

### Quand desactiver

Desactiver un pack ou une categorie si:

- le manifest ou les sources sont invalides ;
- aucun niveau jouable fiable n'existe ;
- le contenu local casse la coherence du catalogue.

## Packs officiels non installes

Le cockpit sait aussi inspecter les packs officiels embarques qui ne sont pas encore installes.

Dans ce cas:

- la couverture editoriale est lisible ;
- la calibration reelle reste `not_installed`, car aucune partie locale n'existe encore ;
- les bloqueurs d'import et alertes sont exposes avant installation.

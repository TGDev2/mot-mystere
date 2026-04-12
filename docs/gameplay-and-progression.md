# Gameplay et progression

## Boucle de jeu

Le parcours nominal est:

1. saisir ou recharger un pseudo ;
2. choisir une categorie et une difficulte jouables ;
3. lancer une manche ;
4. proposer des lettres jusqu'a victoire, epuisement des essais ou fin du temps ;
5. consulter le resume, puis rejouer, suivre une recommandation ou revenir a l'accueil.

Le jeu est strictement solo et local.

## Calibration des mots

Chaque mot est normalise en majuscules puis transforme en `WordProfile`.

Les metriques calculees sont:

- longueur ;
- nombre de lettres uniques ;
- nombre de repetitions ;
- nombre de lettres rares parmi `KQWXYZJ` ;
- score de complexite.

Formule de complexite:

```text
complexite = (longueur * 3)
           + (lettres_uniques * 2)
           + (lettres_rares * 3)
           - repetitions
```

Classification:

- `Facile` si complexite `<= 27`
- `Moyen` si complexite `<= 34`
- `Difficile` au-dela

Une categorie n'expose un niveau que si elle fournit au moins `5` mots calibres pour ce niveau.

## Regles par difficulte

### Budget de manche

| Difficulte | Essais | Temps |
| --- | ---: | ---: |
| Facile | 10 | 75 s |
| Moyen | 7 | 60 s |
| Difficile | 5 | 45 s |

### Score de base et bonus

| Difficulte | Base | Bonus par essai restant | Cap bonus temps |
| --- | ---: | ---: | ---: |
| Facile | 70 | 8 | 35 |
| Moyen | 150 | 12 | 55 |
| Difficile | 240 | 18 | 75 |

## Calcul du score

Le score d'une manche gagnee est:

```text
total =
  base_points
  + (longueur_du_mot * 4)
  + (complexite_du_mot * 2)
  + (essais_restants * bonus_par_essai)
  + bonus_temps
```

Le bonus temps est proportionnel au temps restant, borne par le plafond du niveau.

Une manche perdue ne rapporte aucun point.

## Rotation des mots

La rotation est suivie par:

- joueur ;
- categorie ;
- difficulte.

Pour chaque paire, le jeu stocke:

- les mots encore frais dans la fenetre courante ;
- le dernier mot joue ;
- la taille de fenetre ;
- une signature du pool courant.

Comportement:

- tant qu'il reste des mots frais, un mot deja joue dans la fenetre n'est pas repropose ;
- quand la fenetre est vide, un nouveau cycle est reconstruit ;
- si possible, le dernier mot joue est retire du cycle immediat pour eviter une repetition directe ;
- si le catalogue change, la rotation est recalibree sur le pool courant.

Les sessions de revision ciblee fonctionnent hors rotation normale.

## Progression persistante

La progression est reconstruite a partir de l'historique local.

### Carte de maitrise

Chaque paire categorie/niveau jouable suit:

- `Non joue` si aucune partie enregistree ;
- `A valider` si des tentatives existent sans victoire ;
- `Valide` a partir de `1` victoire ;
- `Maitrise` a partir de `3` victoires.

Deux tableaux de progression en decoulent:

- la carte de validation ;
- la carte de maitrise.

### Objectifs

Le snapshot de progression produit trois objectifs:

- `Carte de validation`
- `Carte de maitrise`
- `Cap de score`

Le premier objectif non complete devient `primary_goal`.

### Defis

Le snapshot produit aussi trois defis:

- un defi de paire a valider ou maitriser ;
- un defi de regularite recente ;
- un defi de score.

Le premier defi non complete devient `featured_challenge`.

## Profil d'apprentissage et recommandation

La recommandation personnalisee compare trois axes:

- `Temps`
- `Erreurs`
- `Maitrise`

Les deux premiers axes sont derives des `5` dernieres parties avec une ponderation `5-4-3-2-1`.

Le moteur regarde notamment:

- les defaites au temps ;
- les defaites par epuisement des essais ;
- les victoires obtenues avec trop peu de marge ;
- la prochaine paire rentable a valider ou maitriser.

Le driver dominant devient le levier principal de recommandation:

- retravailler une paire fragile au chrono ;
- retravailler une paire fragile sur la precision ;
- ou continuer a pousser la carte de maitrise.

## Sessions guidees

Le jeu peut lancer des sessions multi-manches a objectif explicite.

Deux sources existent:

- `primary_goal`
- `featured_challenge`

Une session guidee:

- capture un objectif ;
- calcule son etat initial ;
- synchronise automatiquement la selection categorie/difficulte vers la recommandation associee ;
- reevalue l'objectif apres chaque manche ;
- s'acheve quand l'objectif est rempli ou arrete manuellement.

## Revisions ciblees

Deux modes de revision existent.

### 1. Revision des mots rates

Source:

- jusqu'a `3` mots perdus sur les `8` dernieres parties ;
- uniquement si la cible existe encore dans le catalogue actif.

Effet:

- chaque mot cible est rejoue hors rotation normale ;
- la session suit combien de mots ont ete "nettoyes", c'est-a-dire gagnes au moins une fois.

### 2. Travail d'une paire fragile

Source:

- le driver dominant recent `Temps` ou `Erreurs`.

Effet:

- la session force une paire categorie/niveau fragile ;
- elle vise `2` manches qualifiees maximum sur `3` manches.

Qualification:

- en pression temps: victoire avec plus de `20 %` de marge temps ;
- en pression erreurs: victoire avec plus de `20 %` de marge essais.

## Priorisation des actions UI

`action_priority.py` prepare les actions principales affichees:

- sur l'accueil ;
- sur le resume de manche.

Selon le contexte, l'interface met en avant:

- la recommandation personnalisee ;
- la reprise du dernier reglage ;
- une revision ciblee ;
- une session guidee ;
- un simple lancement libre.

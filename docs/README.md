# Documentation MotMystere

Cette documentation complete le `README.md` racine. Elle est organisee par sujet pour eviter qu'un seul fichier concentre a la fois l'usage, l'architecture et la maintenance.

## Parcours recommande

1. lire le [`README.md`](../README.md) pour le positionnement, le lancement rapide et la structure generale ;
2. lire [`architecture.md`](architecture.md) pour comprendre le decoupage applicatif ;
3. ouvrir ensuite la documentation specialisee selon le besoin.

## Index

- [`architecture.md`](architecture.md)
  Vue d'ensemble de l'application, responsabilites des modules et flux nominaux.

- [`presentation-architecture.md`](presentation-architecture.md)
  Contrat de la couche presentation: routeur, ecrans, overlays, shell UI et workflows.

- [`gameplay-and-progression.md`](gameplay-and-progression.md)
  Regles de jeu, calibration des mots, scoring, rotation, progression, sessions guidees et revisions.

- [`data-and-catalog.md`](data-and-catalog.md)
  Donnees locales, schema SQLite, format des packs, index des packs officiels et format des sauvegardes.

- [`editorial-maintenance.md`](editorial-maintenance.md)
  Politique de calibration des difficultes, cibles editoriales et lecture du cockpit editorial.

- [`development.md`](development.md)
  Prerequis de developpement, commandes utiles, tests, build Windows et points d'attention quand on modifie le code.

## Selon le profil

- Pour lancer ou evaluer le projet:
  `README.md`, puis `gameplay-and-progression.md`.

- Pour modifier le code:
  `architecture.md`, `presentation-architecture.md`, puis `development.md`.

- Pour travailler sur les packs et le contenu:
  `data-and-catalog.md`, puis `editorial-maintenance.md`.

- Pour comprendre la persistance et les exports:
  `data-and-catalog.md`.

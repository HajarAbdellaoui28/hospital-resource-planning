# État du projet

Dernière synthèse : novembre 2026. Ce fichier décrit l’état observable du projet ; les exigences restent dans `specifications.md` et la feuille de route approuvée dans `IMPLEMENTATION_PLAN.md`.

## Phases réalisées

| Phase | Livraison principale | État |
|---|---|---|
| 1 | Contrats de domaine, configuration, formulation mathématique et fondations | Implémentée |
| 2 | Données hospitalières synthétiques reproductibles | Implémentée |
| 3 | Prévisions J+1 à J+7 et validation chronologique | Implémentée |
| 4 | Instance canonique de besoins opérationnels | Implémentée |
| 5 | Baseline Greedy et validateur indépendant | Implémentée |
| 6 | Solveurs MILP/CBC et CP-SAT, objectif commun | Implémentée |
| 7 | Scénarios, expériences et manifeste de sensibilité | Implémentée |
| 8 | API FastAPI, jobs et téléchargements sécurisés | Implémentée |
| 9 | Dashboard Next.js relié aux artefacts API | Implémentée, validation locale finale requise |

## Fonctionnalités disponibles

- Génération de données synthétiques pour URG, MED, REA et CHI.
- Cinq modèles de prévision, sélection chronologique par service et prévisions finales de sept jours.
- Traduction des prévisions en besoins de lits et de personnel.
- Greedy, MILP/CBC et CP-SAT avec objectif canonique et validateur indépendant.
- Scénarios S0–S5, résultats d’expériences et manifeste de sensibilité de 80 combinaisons.
- API FastAPI sur le port 8000 : lectures, jobs explicitement soumis et téléchargements contrôlés.
- Dashboard sur le port 3011 : huit vues, filtres, consultation des résultats et lancement manuel d’une méthode.

## Résultats et validations confirmés

- Les données et résultats du projet sont synthétiques et reproductibles pour une configuration et une graine identiques.
- La validation de prévision réserve le test final ; il n’intervient pas dans la sélection des modèles.
- Les trois méthodes utilisent les mêmes conventions d’unités et les mêmes composantes d’objectif.
- Les admissions refusées sont un KPI en patients ; la pénalité de demande est portée une seule fois par les journées-patients non soutenues.
- Les tests récents confirmés sont `pytest tests/test_api_contract.py -q` (8 tests), `ruff check src tests`, `npm.cmd run typecheck` et `npm.cmd run lint`.

## Jeu de démonstration pour GitHub

Le dépôt sélectionne 79 fichiers d'artefacts, soit 34 173 770 octets (32,59 Mio) : les données synthétiques complètes, six fichiers de prévision, l'instance opérationnelle S0, le manifeste de sensibilité et six expériences persistées (S0/Greedy, S1/MILP, S2/Greedy, S3/Greedy, S4/Greedy, S5/CP-SAT). Les chemins de métadonnées de ces expériences sont relatifs au projet. Un test de lecture depuis un autre dossier a retrouvé 6 scénarios, 4 380 observations historiques, 140 prévisions, 28 besoins opérationnels, 80 lignes de manifeste et les 28 allocations de chacune des 6 expériences.

Les doublons locaux S3 et S4, les sorties d'allocation autonomes, les artefacts Greedy non référencés de S1/S5, les logs et les caches restent exclus. Le contrôle textuel des artefacts sélectionnés n'a pas détecté de courriel, clé, secret ni chemin personnel. Les identifiants de professionnels présents dans les CSV sont synthétiques. Les six expériences ne fournissent pas une comparaison Greedy/MILP/CP-SAT complète sur une même instance.

## Limites connues

- Aucun artefact ne doit être interprété comme une donnée ou recommandation clinique réelle.
- Une méthode peut ne pas avoir produit d’artefact exploitable pour une expérience ; le dashboard affiche alors un état explicite, jamais un KPI inventé.
- Les solveurs exacts et la grille exhaustive de sensibilité sont coûteux et ne sont jamais lancés automatiquement.
- Les jobs sont suivis en mémoire par l’API ; leur état n’est pas conservé après un redémarrage, contrairement aux artefacts écrits.
- La réussite finale de `npm.cmd run build` et de Playwright doit être confirmée sur un poste local autorisant les sockets et Chromium.

## Avant publication ou phase suivante

1. Le dépôt sélectionne les données synthétiques, les prévisions, l'instance S0, six expériences S0–S5 et le manifeste de sensibilité pour la démonstration. Les autres sorties locales restent ignorées par Git.
2. Exécuter localement le build Next.js et Playwright.
3. Vérifier visuellement le dashboard avec FastAPI sur `127.0.0.1:8000` et Next.js sur `localhost:3011`.

Voir le [README](README.md) pour l’installation et les commandes, puis la documentation dans `docs/` pour le détail technique.

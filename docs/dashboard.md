# Dashboard local — phase 9

## Objet et périmètre

Le dashboard Next.js présente les résultats déjà calculés du prototype sur des données exclusivement synthétiques. Les lectures ne génèrent ni donnée ni solveur. La vue Expériences peut toutefois soumettre explicitement un job après action de l’utilisateur ; aucune soumission ne survient au chargement.

Les huit vues prévues par le cahier des charges sont disponibles dans une navigation latérale :

1. vue d’ensemble ;
2. exploration des données ;
3. prévisions ;
4. allocation des ressources ;
5. comparaison des méthodes ;
6. scénarios ;
7. analyse de sensibilité ;
8. expériences et export.

Le dashboard ne contient aucune série de prévision, allocation, KPI ou paramètre de scénario codé en dur. Il lit les artefacts persistés via l'API. Si une phase productrice n'a pas généré l'artefact requis, la vue concernée affiche un état vide explicite ; elle ne présente pas d'exemple comme un résultat calculé.

## Connexion à l’API

Par défaut, le navigateur lit `http://127.0.0.1:8000/api/v1/experiments`. L’URL peut être remplacée sans modifier le code :

```powershell
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
```

Lorsque l’API est joignable, le dashboard charge les scénarios configurés, les séries d'exploration, les prévisions, l'instance opérationnelle nominale, le registre et l'allocation de l'expérience sélectionnée. Les résultats de crise proviennent des expériences persistées, pas d'une instance opérationnelle autonome par scénario. Lorsque l’API ou un artefact est indisponible, il affiche l'erreur ou l'état vide reçu ; il ne fabrique pas de résultat ni ne relance un job.

Le filtre Service est alimenté prioritairement par les services des séries historiques synthétiques, puis par les prévisions si les historiques ne sont pas disponibles. Il ne dépend donc pas d'une instance opérationnelle qui pourrait manquer pour un scénario de crise. L'instance nominale `S0`, déjà produite par la phase 4, est explicitement accessible via l'identifiant de scénario `S0_BASELINE`.

Le filtre global « Résultat » est une lecture : il ne propose que les méthodes réellement persistées pour l'expérience sélectionnée. La vue Expériences possède séparément le choix « Algorithme à exécuter », qui propose Greedy, MILP/CBC et CP-SAT et exige un clic explicite avant toute soumission.

Les téléchargements réels restent sous la responsabilité de l’API. Leur interaction visuelle complète est différée au lot 9B :

```text
GET /api/v1/experiments/{experiment_id}/downloads/{artifact_path}
```

L’API vérifie le chemin de l’artefact avant de répondre. Le bouton CSV de la table rappelle ce contrat ; il ne crée pas de faux fichier en l’absence d’une expérience effectivement stockée.

## Analyse de sensibilité

Le manifeste de sensibilité contient 80 instances et 160 appels exacts potentiels. Il est affiché à titre déclaratif ; les expériences correspondantes ne sont pas considérées comme exécutées tant que leurs artefacts ne sont pas persistés. Aucune courbe, heatmap ou frontière de Pareto chiffrée n’est inventée.

## État fonctionnel final de la phase 9

- Les vues Vue d'ensemble, Exploration, Prévisions, Allocation et Scénarios lisent des données réellement persistées.
- La vue Méthodes compare les KPI seulement lorsque plusieurs méthodes sont présentes dans une même expérience ; sinon elle explique comment obtenir une comparaison valide.
- La vue Expériences soumet explicitement un job, suit son état, recharge le registre après `COMPLETED`, affiche ses KPI et propose les exports existants.
- La vue Sensibilité lit le manifeste réel, son volume et son coût exact estimé, mais ne dessine aucun résultat avant une exécution explicitement persistée.

## Interactions disponibles

La vue Expériences permet de choisir un scénario et une méthode, puis de soumettre explicitement un job via l'API. Elle suit uniquement les états réellement définis par le backend (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`) et actualise le registre après confirmation `COMPLETED`. Aucune soumission n'a lieu au chargement de l'application.

La table détaille les KPI persistés et propose un lien de téléchargement vers l'artefact CSV des lits. Les graphiques existants restent alimentés par les réponses de lecture passives. Les comparaisons multi-méthodes ne combinent que des métriques réellement retournées par une expérience sélectionnée.

Les filtres de résultats sont liés : un changement de scénario limite les expériences à ce scénario, un changement d'expérience adapte les méthodes disponibles, et une méthode absente produit un message explicite plutôt qu'une requête incohérente. Une erreur réseau reste une erreur visible (« API inaccessible »), distincte d'un artefact non généré (404) ou d'une combinaison sans expérience.

Le changement de scénario relit l'instance opérationnelle correspondante. Un compteur de version côté navigateur ignore toute réponse antérieure arrivée après une nouvelle sélection ; ainsi, une réponse lente ne peut pas remplacer les données liées au filtre courant.

## Lancer localement

Dans un terminal, depuis la racine du projet :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m uvicorn hospital_planning.api.app:app --reload --host 127.0.0.1 --port 8000
```

Dans un deuxième terminal :

```powershell
Set-Location frontend
npm.cmd run dev
```

Ouvrir ensuite `http://localhost:3011`. Le script `npm.cmd run dev` fixe ce port, partagé avec Playwright. Les origines CORS autorisées par défaut sont `http://localhost:3011` et `http://127.0.0.1:3011`; les origines 3000 sont conservées pour compatibilité. Pour une autre origine locale, configurer explicitement `HOSPITAL_CORS_ORIGINS` avant de démarrer FastAPI ; le joker `*` est refusé.

## Contrôles

Les commandes de contrôle frontend sont :

```powershell
Set-Location frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Le test navigateur `frontend/tests/dashboard.spec.ts` couvre l’ouverture des huit vues, les filtres et l’absence de calcul automatique pendant la navigation. Installer Chromium une seule fois, puis l’exécuter sur un poste local autorisant `localhost` :

```powershell
Set-Location frontend
npx.cmd playwright install chromium
npm.cmd run test
```

Une vérification visuelle et les tests navigateur nécessitent qu’un serveur Next.js puisse écouter localement. L’environnement Codex de ce projet bloque les sockets locaux ; cette étape doit donc être exécutée sur un poste local autorisant `localhost`.

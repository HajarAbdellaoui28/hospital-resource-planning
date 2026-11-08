# Contrat API applicative

L'API FastAPI est versionnée sous `/api/v1`. Les lectures de configuration, jobs et expériences sont passives : elles ne déclenchent ni génération, ni prévision, ni solveur.

| Endpoint | Réponse | Effet |
|---|---|---|
| `GET /health` | état du service | aucune écriture |
| `GET /api/v1/config/hospital` | `HospitalConfig` validé | lecture de configuration |
| `POST /api/v1/jobs/experiments` | `JobResponse`, HTTP 202 | soumet explicitement une expérience |
| `GET /api/v1/jobs/{job_id}` | `JobResponse` | lecture d'état sans relance |
| `GET /api/v1/experiments` | liste d'`ExperimentSummary` | lecture des métadonnées stockées |
| `GET /api/v1/experiments/{experiment_id}` | métadonnées et KPI | lecture d'artefacts stockés |
| `GET /api/v1/experiments/{experiment_id}/downloads/{artifact_path}` | fichier | téléchargement contrôlé d'un artefact existant |
| `GET /api/v1/dashboard/scenarios` | scénarios configurés | lecture de `configs/scenarios.json` |
| `GET /api/v1/dashboard/sensitivity/manifest` | grille déclarative de sensibilité | lecture de `results/experiments/sensitivity_manifest.csv` |
| `GET /api/v1/dashboard/forecasts` | prévisions finales et métriques | lecture de `results/forecasts/` |
| `GET /api/v1/dashboard/exploration` | admissions, occupation, capacité | lecture de `data/synthetic/` |
| `GET /api/v1/dashboard/operational/{scenario_id}` | besoins opérationnels | lecture de `results/operational_instances/` |
| `GET /api/v1/dashboard/experiments/{experiment_id}/methods/{method_name}` | résultat, lits et couverture RH | lecture contrôlée d'une expérience persistée |

`POST /api/v1/jobs/experiments` accepte `scenario_ids`, `methods` et une graine optionnelle. Par défaut, il exécute seulement Greedy. Un unique worker local traite les jobs afin de ne pas surallouer les solveurs. Les états de job (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`) sont distincts des statuts de méthode (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`, `ERROR`).

## Exemples

Soumettre explicitement Greedy sur S0 :

```json
POST /api/v1/jobs/experiments
{"scenario_ids":["S0_BASELINE"],"methods":["greedy"],"seed":42}
```

La réponse HTTP 202 contient un `job_id`, son état initial et une liste vide d’`experiment_ids` tant que le job n’est pas terminé. Interroger ensuite `GET /api/v1/jobs/{job_id}`. Une fois `COMPLETED`, les identifiants d’expériences peuvent être lus via `GET /api/v1/experiments/{experiment_id}` puis les allocations via l’endpoint `dashboard` correspondant.

Erreurs attendues : identifiant inconnu ou artefact absent (`404`), corps de requête invalide (`422`) et erreur de lecture d’artefact invalide (`500`). Un `404` d’allocation signifie qu’aucun artefact complet de la méthode demandée n’est disponible ; il ne doit pas être présenté comme un KPI nul.

La configuration est résolue par `HOSPITAL_CONFIG_PATH` ou `configs/hospital.json`. `HOSPITAL_PROJECT_ROOT` permet de définir la racine locale et `HOSPITAL_RESULTS_PATH` le répertoire des expériences, utile notamment pour les tests. Les téléchargements sont résolus strictement sous le répertoire de l'expérience afin d'interdire toute traversée de chemin.

## CORS et persistance

Par défaut, `http://localhost:3011` et `http://127.0.0.1:3011` sont autorisées pour le frontend Next.js. Les deux origines 3000 restent autorisées pour compatibilité. La variable `HOSPITAL_CORS_ORIGINS` accepte une liste d'origines HTTP(S) explicites séparées par des virgules; le joker `*` est refusé.

Les expériences persistent en CSV/JSON dans `results/experiments/` et restent lisibles après le redémarrage de l'API. Le registre de jobs est en mémoire : les jobs soumis avant un redémarrage ne sont plus consultables après celui-ci, même si les artefacts éventuellement écrits restent disponibles.

Les artefacts historiques peuvent référencer leurs fichiers soit par chemin absolu, soit par chemin relatif au dossier de l'expérience, soit par chemin relatif à la racine du projet. L'API accepte ces trois formats uniquement après avoir vérifié que le fichier final appartient bien au dossier de l'expérience ; toute traversée reste refusée.

## Contrats de lecture du dashboard

Les endpoints `dashboard` sont strictement passifs. Ils n'appellent ni générateur, ni prévision, ni solveur. Chaque réponse contient une provenance avec le chemin relatif de l'artefact, un identifiant de source et, lorsqu'ils existent, l'horodatage, la graine et l'empreinte de configuration.

- `forecasts` expose les 140 prévisions finales (dont 28 sélectionnées) et les métriques chronologiques ; `yhat` reste une valeur continue en patients/jour.
- `operational` expose les admissions demandées et besoins de lits avant allocation.
- `operational/S0_BASELINE` résout l'artefact nominal historique `results/operational_instances/S0/`; il ne recalcule pas l'instance et conserve donc la même provenance de données.
- `methods` expose une seule méthode appartenant à une expérience explicitement identifiée, avec son `MethodResult`, ses allocations de lits et sa couverture RH. Les admissions refusées sont des patients ; la demande non soutenue est en journées-patients.
- Les allocations exactes peuvent exposer `occupancy_required` : c'est le besoin d'occupation calculé avant décision, conservé comme information optionnelle car les anciens artefacts Greedy ne le portent pas.
- `sensitivity/manifest` expose les paramètres, graines et coûts d'exécution estimés d'une grille déjà créée. Il n'exécute ni solveur ni scénario et ne prétend pas fournir des résultats de sensibilité.
- L'absence d'un artefact producteur retourne HTTP 404 avec un message explicite. Aucun chiffre de remplacement n'est généré.

## Vérification HTTP de bout en bout

Le script `scripts/verify_api.ps1` démarre Uvicorn temporairement puis vérifie santé, configuration, soumission/polling S0 Greedy, KPI, téléchargement CSV, identifiant inconnu, requête invalide, traversée de chemin et prévol CORS. Depuis la racine du projet :

```powershell
.\scripts\verify_api.ps1
```

Les résultats attendus sont : santé `ok`, horizon 7, job final `COMPLETED`, téléchargement HTTP 200 non vide, identifiant inconnu 404, requête invalide 422, traversée 404 et origine CORS `http://localhost:3011`. `QUEUED` et `RUNNING` peuvent être très brefs; le script rapporte toutes les transitions observables. Le script utilise le port 8000 par défaut, configurable via `-Port`.

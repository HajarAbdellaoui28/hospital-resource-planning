# Outil de planification des ressources hospitalières

Prototype reproductible de planification hospitalière fondé exclusivement sur des données synthétiques. Il relie la demande d’admissions, les besoins en lits et en personnel, l’optimisation, des scénarios de stress, une API FastAPI et un dashboard Next.js. Il ne constitue ni une recommandation clinique, ni un outil réglementaire, ni un système de décision de soins.

Les exigences de référence sont dans [specifications.md](specifications.md). La feuille de route est dans [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) et l'état réel du travail dans [PROGRESS.md](PROGRESS.md).

## Fonctionnalités disponibles

- Données synthétiques reproductibles pour URG, MED, REA et CHI.
- Prévisions J+1 à J+7 avec cinq modèles et validation chronologique.
- Instance commune de besoins opérationnels, puis Greedy, MILP/CBC et CP-SAT avec validateur indépendant.
- Scénarios S0 à S5, expériences persistées, API FastAPI et dashboard à huit vues.

Les allocations et comparaisons ne sont affichées que lorsqu’elles ont été effectivement générées et persistées.

## Architecture

```text
Données synthétiques → Prévisions → Besoins opérationnels
       → Optimisation → Scénarios / expériences → API → Dashboard
```

Technologies : Python, pandas, Pydantic, FastAPI, PuLP/CBC, OR-Tools, Next.js 15, React, TypeScript, ESLint et Playwright.

## Installation sous Windows

Cloner le dépôt publié, puis exécuter depuis sa racine :

```powershell
git clone <URL_DU_DEPOT>
Set-Location <DOSSIER_DU_DEPOT>
```

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install . pytest pytest-cov ruff httpx
Set-Location frontend
npm.cmd install
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Le chemin actuel contient un caractère accentué. Sous Windows, l'installation Python non éditable est utilisée pour éviter une limite d'encodage du mécanisme éditable. Après une modification Python, relancer `pip install --force-reinstall --no-deps .` depuis la racine du projet.

La structure utile est : `configs/` (paramètres), `data/` (données synthétiques), `results/` (artefacts), `src/` (backend), `frontend/` (dashboard), `tests/` et `docs/`. Le dépôt inclut un jeu de démonstration sélectionné ; les autres sorties locales restent ignorées par Git.

## Régénérer les données synthétiques (facultatif)

Le dashboard peut démarrer avec les artefacts fournis sans recalcul. Pour régénérer les données après installation Python, exécuter depuis la racine :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.data.generator
```

Les données et le rapport de qualité sont créés dans `data/synthetic/`. Elles sont reproductibles pour une configuration et une graine identiques.

## Évaluer les prévisions

Après la génération des données :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.forecasting.evaluation
```

Les prévisions J+1 à J+7, les métriques et la sélection de modèle par service sont écrites dans `results/forecasts/`. Consulter [docs/forecasting.md](docs/forecasting.md) pour le protocole et les limites.

## Construire les besoins opérationnels

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.operational.requirements
```

Cette commande produit l'instance canonique dans `results/operational_instances/S0/`, sans prendre de décision d'allocation ou de planning. Voir [docs/operational_requirements.md](docs/operational_requirements.md).

## Exécuter la baseline gloutonne

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.optimization.greedy
```

La baseline et son validateur indépendant écrivent leurs résultats dans `results/allocations/greedy/S0/`. Voir [docs/greedy_and_validator.md](docs/greedy_and_validator.md).

## Exécuter les solveurs exacts

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.optimization.exact
```

Les solveurs MILP/CBC et CP-SAT utilisent la même instance S0 et écrivent leurs artefacts dans `results/allocations/milp/S0/` et `results/allocations/cp_sat/S0/`. Voir [docs/exact_solvers.md](docs/exact_solvers.md).

## Exécuter les scénarios

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.experiments.runner
```

La commande crée les expériences Greedy S0–S5 dans `results/experiments/`. Ajouter `--methods greedy milp cp_sat` pour comparer les trois méthodes sur les mêmes instances. Le manifeste de sensibilité à 80 scénarios s'obtient avec `--sensitivity-manifest`. Voir [docs/experiments.md](docs/experiments.md).

## Démarrer l'API locale

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m uvicorn hospital_planning.api.app:app --reload --host 127.0.0.1 --port 8000
```

La documentation interactive est disponible sur `http://127.0.0.1:8000/docs`. L'API permet de soumettre explicitement des jobs d'expérience, de consulter leur état et de télécharger les résultats déjà produits. Voir [docs/api_contract.md](docs/api_contract.md).

Pour exécuter la vérification HTTP complète sur un poste local autorisant les sockets :

```powershell
.\scripts\verify_api.ps1
```

## Démarrer le dashboard

Dans un second terminal, après avoir démarré l'API :

```powershell
Set-Location frontend
npm.cmd run dev
```

Le dashboard est disponible sur `http://localhost:3011`. Après clonage et installation, ses vues lisent les artefacts fournis sans exécuter le pipeline. La vue Expériences peut soumettre explicitement un nouveau calcul après clic utilisateur. Copier éventuellement `frontend/.env.example` vers `frontend/.env.local` pour expliciter l'URL API locale. Consulter [docs/dashboard.md](docs/dashboard.md) pour la connexion API et les limites.

## Limites

- Les données, ratios, scénarios et résultats sont synthétiques.
- Les expériences fournies couvrent S0–S5, avec une méthode référencée par expérience ; elles ne démontrent pas une comparaison complète des trois solveurs sur une même instance.
- Les solveurs exacts et la sensibilité exhaustive peuvent être coûteux et ne sont jamais lancés automatiquement.
- Le build Next.js et les tests Playwright doivent être confirmés sur un poste local autorisant les sockets.

## Vérification et documentation

Depuis la racine :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check src tests
Set-Location frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run test
```

Documentation complémentaire : [modèle mathématique](docs/mathematical_model.md), [données](docs/synthetic_data.md), [prévisions](docs/forecasting.md), [optimisation](docs/exact_solvers.md), [scénarios](docs/experiments.md), [API](docs/api_contract.md), [dashboard](docs/dashboard.md), [dictionnaire de données](docs/data_dictionary.md) et [état du projet](PROGRESS.md).

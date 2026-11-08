# Scénarios, expériences et sensibilité — phase 7

`configs/scenarios.json` définit les six stress tests synthétiques requis. Ils sont des hypothèses explicites de démonstration, et non des estimations hospitalières réelles.

| Scénario | Transformation |
|---|---|
| `S0_BASELINE` | aucune transformation |
| `S1_URGENT_PEAK` | admissions URG × 1,5 pendant les deux premiers jours |
| `S2_GENERAL_SURGE` | admissions × 1,25 |
| `S3_STAFF_ABSENCE` | 15 % des professionnels disponibles sélectionnés de façon déterministe, puis tous leurs créneaux initialement disponibles rendus indisponibles |
| `S4_COMBINED_CRISIS` | admissions × 1,25 et 15 % d'absences supplémentaires |
| `S5_BED_CLOSURE` | capacité opérationnelle × 0,90, arrondie à l'entier inférieur |

## Reproductibilité et immutabilité

Chaque scénario copie les tables de demande, lits et disponibilités de S0 avant toute transformation. Il enregistre la graine, sa définition et l'empreinte SHA-256 de ses entrées. Les absences sont sélectionnées par `numpy.random.default_rng(seed)` parmi les professionnels ayant au moins un créneau disponible, puis ne retirent que leurs créneaux initialement vrais : un scénario ne peut donc jamais augmenter une disponibilité. Les fermetures ne peuvent jamais augmenter une capacité.

Les admissions modifiées reconstruisent l'occupation par cohortes. Une admission ajoutée ou retirée modifie sa sortie après la durée de séjour configurée ; admissions refusées et journées-patients non soutenues restent des métriques distinctes lors de l'optimisation.

## Exécution des scénarios

Par défaut, la commande exécute Greedy pour les six scénarios, ce qui est adapté à une démonstration rapide :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.experiments.runner
```

Pour comparer également les solveurs exacts sur les mêmes copies de scénario :

```powershell
.\.venv\Scripts\python.exe -m hospital_planning.experiments.runner --methods greedy milp cp_sat
```

Chaque expérience écrit ses entrées transformées, les artefacts par méthode, `metrics.csv` et `experiment.json` sous `results/experiments/<experiment_id>/`. Une expérience partielle conserve les méthodes terminées et leurs statuts; aucun résultat ne remplace celui d'un autre scénario.

## Sensibilité

La grille contient 5 taux d'absence × 4 multiplicateurs de demande × 4 réductions de capacité = 80 expériences, soit 160 appels exacts si MILP et CP-SAT sont tous deux demandés. Son manifeste, sans lancer de solveur, est généré par :

```powershell
.\.venv\Scripts\python.exe -m hospital_planning.experiments.runner --sensitivity-manifest
```

L'exécution exhaustive est volontairement distincte de la commande par défaut : elle doit être lancée avec un budget de calcul explicitement choisi et chaque résultat doit conserver ce budget réel.

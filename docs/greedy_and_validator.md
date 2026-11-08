# Heuristique gloutonne et validation indépendante — phase 5

La baseline gloutonne consomme exclusivement les artefacts de l'instance opérationnelle S0. Elle ne modifie ni les prévisions ni leurs besoins de référence.

## Allocation des lits

Pour chaque service et jour, l'heuristique applique les sorties attendues, accepte autant d'admissions demandées que la capacité physique restante, puis ouvre exactement les lits correspondant à l'occupation soutenue. Les admissions non acceptées et les journées-patients non soutenues sont enregistrées séparément.

## Affectation du personnel

La disponibilité future est projetée de manière déterministe depuis la dernière disponibilité observée pour le même jour de semaine et le même poste. Cette hypothèse est explicitement enregistrée dans `planning_availability.csv`.

Les slots sont traités dans un ordre déterministe : date, criticité synthétique du service, poste, rôle et identifiant du professionnel. Une première passe couvre les dotations minimales ; une seconde vise les cibles complètes. Toute affectation respecte disponibilité, qualification, un seul poste par jour, limite de postes, repos minimal et limite de nuits consécutives. Les heures de début synthétiques sont configurées : MORNING 07:00, EVENING 15:00, NIGHT 23:00.

Sous `shortage_permitting`, le déficit par rapport à la cible de personnel est un KPI ; la disponibilité, qualification, repos, limite de postes, capacité et dotation minimale restent des contraintes dures. La politique `strict` rendrait une solution invalide si une cible n'était pas intégralement couverte.

## Validateur indépendant

`optimization/validator.py` contrôle les artefacts retournés sans réutiliser une formulation de solveur : conservation et capacité, disponibilité, qualification, doubles affectations, limites de postes, repos, nuits consécutives, dotation minimale et déficit de cible.

## Exécution

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.optimization.greedy
```

Les artefacts sont écrits dans `results/allocations/greedy/S0/` : allocation de lits, affectations, couverture, disponibilités projetées et résultat normalisé. Ce dernier référence explicitement les fichiers d'allocation et d'affectation qu'il décrit.

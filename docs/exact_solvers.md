# Solveurs exacts et comparabilité — phase 6

Les adaptateurs `milp` (PuLP/CBC) et `cp_sat` (OR-Tools) consomment la même instance opérationnelle, la même projection déterministe de disponibilité et la même configuration que Greedy.

## Formulation commune

Les deux modèles décident les admissions acceptées, l'occupation soutenue, les lits ouverts, les affectations individuelles et le déficit de cible RH. Ils imposent identiquement : capacité, dynamique de cohortes, disponibilité, qualifications, un poste par jour, maximum de postes, repos minimal, nuits consécutives et dotation minimale par rôle/poste pour chaque lit ouvert.

La cible RH est linéarisée par `10 × (assigned_staff + shortage) ≥ ratio × opened_beds`; la dotation minimale est imposée séparément. Sous `shortage_permitting`, seul `shortage` est souple. La politique stricte impose à la fois toutes les admissions et un déficit de cible nul.

L'équité est la somme, par rôle, des étendues de charge parmi tous les professionnels actifs, y compris ceux sans affectation. Pour chaque rôle, les solveurs créent `load_min` et `load_max`, encadrent chaque charge individuelle, puis minimisent `load_max - load_min`. Le validateur recalcule cette valeur à partir des affectations retournées.

## Objectif canonique et statuts

Les méthodes exposent les composantes `opened_bed_cost`, `unmet_patient_day_cost`, `staff_target_shortage_cost`, `workload_imbalance_cost` et `total_cost`. Les admissions refusées restent un KPI sans pénalité propre, afin de ne pas compter deux fois la même demande non soutenue.

Une solution `FEASIBLE` obtenue à la limite de temps est conservée et validée; elle n'est jamais présentée comme optimale. CBC ne fournit pas systématiquement une borne exploitable dans cette configuration, donc son écart d'optimalité peut rester `null`.

## Déficit structurel S0

La cible S0 représente 2 322 affectations et les plafonds contractuels bruts représentent au plus 1 175 affectations (50 médecins × 5, 110 infirmiers × 5, 75 aides-soignants × 5). Avant disponibilités, qualifications, repos et nuits, le déficit structurel minimal est donc 1 147 postes-cibles. Les effectifs et cibles synthétiques ne sont pas modifiés pour améliorer ce résultat.

## Exécution

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.optimization.exact
```

Les sorties sont écrites dans `results/allocations/milp/S0/` et `results/allocations/cp_sat/S0/`, avec les mêmes fichiers que Greedy et un `method_result.json` traçable.

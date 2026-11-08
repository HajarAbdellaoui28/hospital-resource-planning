# Traduction des prévisions en besoins opérationnels — phase 4

Cette étape ne planifie rien. Elle transforme une prévision de demande en instance canonique et commune aux méthodes futures.

## Conventions et unités

- `yhat` reste la prévision continue en patients par jour.
- `requested_admissions = ceil(yhat)` est la demande opérationnelle entière et conservative ; aucune admission n'est acceptée ou refusée à cette étape.
- Les cohortes historiques encore présentes sont reconstruites à partir des admissions et de la durée de séjour synthétique propre au service. `occupancy_start` est le census avant sorties ; les sorties sont ensuite appliquées avant les admissions du jour, conformément à `occupancy_required = occupancy_start - expected_discharges + requested_admissions`.
- `occupancy_required` et `beds_required` sont des patients présents/lits nécessaires en fin de journée.
- `capacity_available` utilise `beds_total` de la configuration S0. Les fermetures aléatoires futures ne sont pas connues à l'avance et ne sont donc pas anticipées.
- `capacity_gap` enregistre l'écart entre besoin et capacité ; il n'est pas transformé en décision d'admission ou d'ouverture de lits.
- `required_staff` est calculé par service, jour, poste et rôle à partir des lits requis, avec les ratios synthétiques configurés et un arrondi supérieur.

## Instance canonique

La commande ci-dessous écrit `demand_requirements.csv`, `bed_requirements.csv`, `staff_requirements.csv` et `operational_instance.json` dans `results/operational_instances/S0/`.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.operational.requirements
```

Le fichier JSON contient la référence de prévision, l'empreinte d'entrée et les unités. Les phases 5 et 6 devront consommer exactement ces artefacts sans les régénérer ni les modifier.

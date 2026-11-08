# Dictionnaire de données contractuel

Les contrats ci-dessous décrivent les tables générées et persistées par le pipeline. Les artefacts disponibles dépendent des commandes effectivement exécutées.

| Table ou contrat | Clé | Champs essentiels | Invariants |
|---|---|---|---|
| `historical_demand` | date, service | admissions, discharges, événements, source | une ligne par date/service; valeurs non négatives |
| `bed_capacity` | date, service | total, unavailable, operational | `0 ≤ unavailable ≤ total`; `operational = total - unavailable` |
| `occupancy` | date, service | start, admissions, discharges, end, overflow | conservation des patients; aucun effacement silencieux |
| `staff` | staff_id | rôle, qualifications, heures, limite de postes, actif | identifiant unique; rôle et qualifications valides |
| `staff_availability` | staff_id, date, shift | disponible, type d'absence | référence vers un professionnel et poste connus |
| `staff_requirements` | date, service, shift, role | required_staff, source_type | besoin entier non négatif par rôle |
| `forecast_results` | run, date, service, model | yhat, bornes, création | yhat fini et non négatif; continu avant conversion opérationnelle |
| `demand_requirements` | date, service | yhat, admissions demandées, modèle | `requested_admissions = ceil(yhat)` ; aucune décision d'admission |
| `bed_requirements` | date, service | occupation, lits requis, capacité, écart | cohortes conservées; sorties avant admissions; écart explicite |
| `staff_requirements` opérationnel | date, service, shift, role | besoin par rôle, source | arrondi supérieur depuis lits requis; ratios synthétiques |
| `operational_instance` | instance | référence de prévision, empreinte, unités | même instance immuable pour toutes les méthodes |
| `bed_allocations` | date, service | admissions demandées/acceptées/refusées, occupation, lits ouverts | conservation des cohortes; `occupation_end ≤ opened_beds ≤ capacity_available` |
| `staff_assignments` | staff_id, date | service, poste, rôle | professionnel disponible et qualifié; un poste/jour; repos, limite de postes et nuits consécutives respectés |
| `staff_coverage` | date, service, shift, role | minimum, cible, effectif affecté, déficit | minimum impératif pour un lit ouvert; déficit de cible séparé en politique permissive |
| `planning_availability` | staff_id, date, shift | disponible, date/type de source | projection déterministe traçable de la disponibilité historique |
| `experiment` | experiment | scénario, graine, empreinte, méthodes, artefacts | les entrées scénario et les résultats de chaque méthode restent distincts |
| `metrics` expérimental | experiment, scenario, method | statut, KPI, objectif, composantes, validation | même empreinte d'entrée pour toutes les méthodes d'une expérience |
| `sensitivity_manifest` | scenario | absence, demande, capacité, graine, appels exacts | 80 combinaisons identifiables sans exécution implicite |
| `MethodResult` | experiment, scenario, method | statut, objectif, KPI, artefacts, validation | statuts normalisés; valeurs manquantes conservées, jamais remplacées par zéro |

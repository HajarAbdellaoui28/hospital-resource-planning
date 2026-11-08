# Formulation mathématique et unités

## Statut

Ce document fixe la formulation de référence pour les phases 4 à 6. Il ne constitue pas une recommandation clinique ou réglementaire. Tous les coefficients et ratios sont synthétiques et configurables.

## Unités

| Variable | Unité | Signification |
|---|---:|---|
| `requested_admissions` | patients/jour | Demande d'admissions prévue |
| `accepted_admissions` | patients/jour | Admissions effectivement acceptées par le plan |
| `rejected_admissions` | patients | Admissions non acceptées sur l'horizon |
| `occupancy` | patients ou lits occupés | Census de fin de journée, identique aux trois postes dans l'approximation journalière |
| `opened_beds` | lits/jour | Lits physiquement disponibles, ouverts et dotés au jour considéré |
| `unmet_patient_days` | journées-patients | Écart d'occupation entre demande complète et demande soutenue |
| `staff_required` / `staff_assigned` | professionnels/poste | Besoin et couverture par rôle, service, jour et poste |

`beds_operational` du jeu de capacité est un plafond physique avant décision; `opened_beds` est la décision réellement soutenue par le planning.

## Dynamique des patients

Pour le service `s`, le jour `t` et une cohorte admise à la date `a` de durée synthétique entière `d_s` :

`occupancy(s,t) = initial_patients(s,t) + Σ accepted_admissions(s,a)` pour chaque `a` tel que `a ≤ t < a + d_s`.

Les sorties sont traitées avant les admissions quotidiennes. La demande complète emploie les admissions demandées; la demande soutenue emploie les admissions acceptées. Les admissions refusées et les journées-patients non soutenues sont donc deux métriques distinctes.

## Décisions jointes

Ensembles: services `S`, jours `T`, postes `K`, rôles `R`, professionnels `I`.

Variables:

- `A[s,t]` : admissions acceptées, entière non négative.
- `O[s,t]` : occupation soutenue, entière non négative.
- `L[s,t]` : lits ouverts, entière non négative.
- `X[i,s,t,k]` : 1 si le professionnel `i` est affecté au service `s`, jour `t`, poste `k`.
- `D[s,t]` : journées-patients non soutenues, entière non négative.
- `Q[s,t,k,r]` : déficit par rapport à la cible de personnel, entier non négatif.

Contraintes dures:

1. `0 ≤ L[s,t] ≤ capacity_available[s,t]` et `O[s,t] ≤ L[s,t]`.
2. `O` respecte la dynamique des cohortes avec `A`.
3. `0 ≤ A[s,t] ≤ requested_admissions[s,t]`.
4. `X[i,s,t,k] ≤ availability[i,t,k]` et `X[i,s,t,k] ≤ qualification[i,s]`.
5. `Σ(s,k) X[i,s,t,k] ≤ 1`.
6. Les heures, le repos, les nuits consécutives et les limites de postes sont respectés, y compris à la frontière de l'horizon.
7. Pour chaque lit ouvert, chaque rôle et chaque poste, les effectifs assignés couvrent le besoin de soutien configuré.

La politique stricte ajoute `A = requested_admissions` et une couverture complète des cibles. La politique permissive ne relâche aucune contrainte ci-dessus; elle permet seulement les variables de déficit par rapport à la demande complète et à la cible de personnel.

## Objectif et KPI

L'objectif partagé est la minimisation de:

`Σ c_b[s] L[s,t] + Σ c_u[s] D[s,t] + Σ c_q[s,k,r] Q[s,t,k,r] + c_f × workload_range`.

Les coefficients sont entiers et identiques pour l'heuristique, PuLP/CBC et CP-SAT. Les groupes comparables sont les professionnels **actifs du même rôle** : rôles, qualifications et besoins ne rendent pas les groupes inter-rôles interchangeables. Un professionnel sans affectation est inclus avec une charge nulle. Pour chaque rôle `r`, l'étendue est `max_i(load_i) - min_i(load_i)`; `workload_range` est la somme de ces étendues. MILP la linéarise avec des variables `load_min[r]` et `load_max[r]`; CP-SAT la représente par les mêmes variables entières et contraintes. Le validateur la recalcule indépendamment.

`rejected_admissions` est un KPI en patients et ne reçoit aucun coût propre. La pénalité de demande est appliquée une seule fois, à `D` en journées-patients; elle reflète l'effet cumulé d'un refus sur la durée de séjour restante dans l'horizon. Chaque résultat conserve séparément les quatre composantes de l'objectif.

`coverage_rate` vaut l'occupation soutenue divisée par l'occupation demandée. Une division par zéro retourne `null` avec un statut explicite.

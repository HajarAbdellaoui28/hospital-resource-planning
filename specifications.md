# Mini-projet 4 — Outil d’aide à la décision pour la planification des ressources hospitalières

## Cahier des charges technique, spécifications d’implémentation et guide de réalisation

**Établissement :** ENSAM Rabat  
**Filière :** INDIA — Santé digitale et ingénierie des systèmes de santé  
**Type :** Mini-projet de data science, recherche opérationnelle et aide à la décision  
**Durée cible :** 4 semaines  
**Équipe :** 6 membres  
**Horizon de planification :** 7 jours  
**Périmètre hospitalier simulé :** 300 lits, 4 services  
**Version du document :** 1.0

---

# 0. Instructions principales destinées à l’agent de développement

## 0.1 Mission

Implémenter une application fonctionnelle permettant de :

1. Générer un jeu de données hospitalières synthétiques, cohérent, reproductible et configurable.
2. Explorer, valider et préparer ces données.
3. Prévoir la demande hospitalière par service pour les sept prochains jours à partir de séries temporelles historiques.
4. Transformer la demande prévue en besoins opérationnels compatibles avec les unités du modèle.
5. Optimiser l’allocation des lits et la planification du personnel en tenant compte des capacités, qualifications, disponibilités et contraintes de planning.
6. Comparer plusieurs méthodes d’optimisation sur des scénarios identiques.
7. Exécuter des analyses de sensibilité sur la demande, les absences et les capacités.
8. Présenter les résultats dans un tableau de bord interactif.
9. Exporter les prévisions, plannings, métriques et résultats des expériences.
10. Fournir des tests automatisés, une documentation complète et une démonstration reproductible.

## 0.2 Principes obligatoires

L’agent doit respecter les règles suivantes :

- Construire un pipeline complet avant d’ajouter des fonctionnalités avancées.
- Ne jamais confondre admissions journalières, patients présents, lits occupés et lits ouverts.
- Ne jamais présenter les paramètres synthétiques comme des normes médicales ou des statistiques hospitalières réelles.
- Comparer les algorithmes sur les mêmes données, prévisions, contraintes et scénarios.
- Valider chaque solution d’optimisation avec un validateur indépendant du solveur.
- Distinguer une solution optimale, une solution faisable non prouvée optimale et une instance infaisable.
- Évaluer les prévisions avec une validation chronologique, jamais avec une séparation aléatoire classique.
- Enregistrer la configuration et les métriques de chaque expérience.
- Fournir un mode de démonstration fonctionnel sans accès à des données externes.
- Utiliser des données synthétiques exclusivement dans la version initiale.
- Ne pas construire une infrastructure distribuée inutile pour un MVP de quatre semaines.

## 0.3 Priorités

**P0 — Fonctionnalités indispensables**

- Génération des données synthétiques.
- Validation des données.
- Prévision à sept jours.
- Au moins trois approches de prévision.
- Allocation agrégée des ressources.
- Heuristique de référence.
- MILP ou CP-SAT.
- Scénarios de crise.
- Calcul des KPI.
- Dashboard de comparaison.
- Tests et documentation.

**P1 — Fonctionnalités souhaitables**

- Deuxième solveur exact.
- Planning individuel complet du personnel.
- Intervalles prédictifs.
- Analyse de sensibilité automatisée.
- Persistance PostgreSQL.
- Export Excel ou CSV.

**P2 — Extensions facultatives**

- Simulation à événements discrets.
- Durées de séjour par patient synthétique.
- Optimisation multiobjectif avec frontière de Pareto.
- Prévision probabiliste.
- Comparaison de métaheuristiques.
- Réoptimisation en cas d’absence de dernière minute.

Ne pas commencer les fonctionnalités P2 avant que les fonctionnalités P0 soient testées.

---

# 1. Contexte, objectifs et périmètre

## 1.1 Hôpital simulé

Le système représente un hôpital régional fictif de 300 lits répartis entre quatre services.

| Service | Code | Capacité théorique initiale | Profil simulé |
|---|---|---:|---|
| Urgences | `URG` | 40 | Demande variable, pics ponctuels |
| Médecine générale | `MED` | 100 | Demande relativement régulière |
| Réanimation | `REA` | 30 | Faible volume, forte criticité |
| Chirurgie | `CHI` | 130 | Demande influencée par le programme opératoire |
| **Total** | | **300** | |

Ces valeurs sont des paramètres de démonstration. Elles doivent être configurables dans un fichier de paramètres et ne constituent pas des recommandations de répartition hospitalière.

La capacité utilisable peut être inférieure à la capacité théorique en raison des lits indisponibles, fermés ou temporairement non dotés en personnel.

## 1.2 Objectifs fonctionnels

### F1 — Génération des données

L’application doit produire plusieurs années de données journalières synthétiques et des tables de capacité, de personnel et de disponibilité.

### F2 — Prévision

L’application doit comparer plusieurs modèles et produire une prévision par service sur sept jours.

### F3 — Allocation des ressources

L’application doit affecter les ressources disponibles afin de limiter les pénuries et les coûts, tout en respectant les contraintes.

### F4 — Planification du personnel

L’application doit pouvoir affecter des professionnels à des services et à des postes, selon leurs compétences et disponibilités.

### F5 — Scénarios

L’application doit permettre de simuler des variations de demande, des absences, des réductions de capacité et des crises combinées.

### F6 — Comparaison

L’application doit comparer les méthodes selon la couverture, le coût, les pénuries, l’équité et le temps de calcul.

### F7 — Visualisation

L’application doit proposer des graphiques interactifs permettant de comprendre les résultats et d’identifier les goulets d’étranglement.

## 1.3 Hors périmètre initial

Ne pas implémenter dans le MVP :

- Une intégration avec un système hospitalier réel.
- Un accès à des dossiers médicaux identifiants.
- Une recommandation clinique automatisée.
- Une application destinée à prendre des décisions médicales réelles.
- Un système de facturation.
- Une infrastructure Kubernetes ou microservices.
- Un modèle de deep learning complexe sans baseline démontrant sa nécessité.

---

# 2. Architecture logicielle

## 2.1 Architecture recommandée

Utiliser une architecture modulaire en Python.

```text
                   ┌───────────────────────────┐
                   │       Dashboard           │
                   │ NextJS + Shadcn        │
                   └─────────────┬─────────────┘
                                 │
                   ┌─────────────▼─────────────┐
                   │     Application Layer     │
                   │ Configuration / Services  │
                   └─────────────┬─────────────┘
                                 │
          ┌──────────────────────┼─────────────────────┐
          │                      │                     │
┌─────────▼────────┐  ┌──────────▼────────┐  ┌─────────▼────────┐
│ Data & Simulation│  │ Forecasting       │  │ Optimization     │
│                  │  │                    │  │                  │
│ Generator        │  │ Baselines          │  │ Greedy           │
│ Validation       │  │ Statistical models │  │ MILP             │
│ Preprocessing    │  │ ML models          │  │ CP-SAT           │
└─────────┬────────┘  └──────────┬─────────┘  └─────────┬────────┘
          │                      │                     │
          └──────────────────────┼─────────────────────┘
                                 │
                   ┌─────────────▼─────────────┐
                   │ Experiment Orchestrator   │
                   │ Scenarios / Metrics       │
                   │ Independent Validator     │
                   └─────────────┬─────────────┘
                                 │
                   ┌─────────────▼─────────────┐
                   │ Results / CSV / SQLite    │
                   └───────────────────────────┘
```

## 2.2 Stack technique

| Composant | Technologie | Utilisation |
|---|---|---|
| Langage | Python 3.12 ou version compatible avec les dépendances | Application principale |
| Données | pandas, NumPy | Génération et préparation |
| Séries temporelles | statsmodels | Modèles statistiques |
| Machine learning | scikit-learn | Régression et modèles à variables retardées |
| Optimisation mathématique | PuLP + CBC | MILP |
| Optimisation combinatoire | OR-Tools CP-SAT | Planning du personnel |
| Visualisation | Plotly | Graphiques interactifs |
| Interface | Streamlit | MVP du dashboard |
| Persistance initiale | CSV et JSON | Données et résultats reproductibles |
| Persistance optionnelle | SQLite ou PostgreSQL | Historique des expériences |
| Tests | pytest | Tests automatisés |
| Qualité du code | Ruff, éventuellement mypy | Lint et vérifications |
| Environnement | venv ou uv | Dépendances isolées |
| Versionnement | Git | Historique du développement |

Documentation :

- Python : https://docs.python.org/3/
- pandas : https://pandas.pydata.org/docs/
- NumPy : https://numpy.org/doc/
- scikit-learn : https://scikit-learn.org/stable/
- statsmodels : https://www.statsmodels.org/stable/
- PuLP : https://coin-or.github.io/pulp/
- OR-Tools : https://developers.google.com/optimization
- Streamlit : https://docs.streamlit.io/
- Plotly : https://plotly.com/python/
- pytest : https://docs.pytest.org/

## 2.3 Choix de l’interface

Utiliser NextJs + shadcnUI pour le MVP.

## 2.4 Principes de conception

- Séparer la génération, la prévision, l’optimisation et la visualisation.
- Éviter les dépendances circulaires entre modules.
- Utiliser des fonctions pures lorsque c’est possible.
- Centraliser les paramètres dans des fichiers de configuration.
- Conserver les résultats bruts des expériences.
- Ne jamais coder en dur les paramètres de scénario dans les fonctions de résolution.
- Utiliser des types explicites pour les données importantes.
- Faire échouer explicitement les validations invalides au lieu de corriger silencieusement des données incohérentes.

---

# 3. Modèle de données

## 3.1 Principe fondamental : séparer les unités

Les variables suivantes ne doivent pas être interchangeables :

- `admissions` : nouvelles admissions pendant une journée.
- `occupancy` : nombre de patients présents à un instant de référence.
- `occupied_beds` : lits effectivement occupés.
- `operational_beds` : lits ouverts et dotés en ressources.
- `staff_required` : nombre de professionnels nécessaires par service et poste.
- `staff_assigned` : nombre de professionnels effectivement affectés.
- `unmet_demand` : demande qui ne peut pas être satisfaite dans le modèle.

Les admissions journalières ne peuvent pas être directement utilisées comme nombre de lits occupés. L’occupation dépend également des patients déjà présents et des sorties.

## 3.2 Table `historical_demand`

Fichier recommandé : `data/synthetic/historical_demand.csv`.

| Colonne | Type | Description |
|---|---|---|
| `date` | date ISO | Date de l’observation |
| `service` | string | Code du service |
| `admissions` | entier ≥ 0 | Nouvelles admissions |
| `discharges` | entier ≥ 0 | Sorties |
| `emergency_arrivals` | entier ≥ 0 ou nul | Arrivées aux urgences |
| `is_holiday` | booléen | Jour férié simulé |
| `is_special_event` | booléen | Événement particulier simulé |
| `data_source` | string | `synthetic` pour le MVP |

Clé logique : (`date`, `service`).

Une seule ligne doit exister par date et service.

## 3.3 Table `bed_capacity`

| Colonne | Type | Description |
|---|---|---|
| `date` | date | Date |
| `service` | string | Code du service |
| `beds_total` | entier | Capacité théorique |
| `beds_unavailable` | entier | Lits indisponibles |
| `beds_operational` | entier | Lits réellement ouverts |

Invariant :

```text
0 <= beds_unavailable <= beds_total
beds_operational = beds_total - beds_unavailable
```

## 3.4 Table `occupancy`

| Colonne | Type | Description |
|---|---|---|
| `date` | date | Date |
| `service` | string | Code du service |
| `occupancy_start` | entier | Patients présents au début du jour |
| `admissions` | entier | Admissions du jour |
| `discharges` | entier | Sorties du jour |
| `occupancy_end` | entier | Patients présents en fin de journée |
| `overflow` | entier ≥ 0 | Demande ou occupation excédentaire modélisée |

La relation de conservation doit être vérifiée.

Dans le cas simple sans transferts :

```text
occupancy_end =
    occupancy_start + admissions_admitted - discharges
```

Ne jamais forcer artificiellement l’occupation à rester sous la capacité en supprimant les patients excédentaires. Enregistrer explicitement les admissions non prises en charge, transferts ou dépassements selon les hypothèses du simulateur.

## 3.5 Table `staff`

| Colonne | Type | Description |
|---|---|---|
| `staff_id` | string | Identifiant synthétique unique |
| `role` | string | Catégorie professionnelle |
| `qualified_services` | liste | Services autorisés dans la simulation |
| `contracted_hours` | nombre | Heures contractuelles |
| `max_shifts` | entier | Limite de postes |
| `active` | booléen | Professionnel actif |

Exemple de catégories synthétiques :

- Médecin.
- Infirmier.
- Aide-soignant.
- Technicien ou personnel spécialisé, si utile.

Ne pas supposer qu’un professionnel est interchangeable avec tous les autres. La couverture doit être calculée par rôle lorsque les contraintes le nécessitent.

## 3.6 Table `staff_availability`

| Colonne | Type | Description |
|---|---|---|
| `staff_id` | string | Professionnel |
| `date` | date | Jour |
| `shift` | string | Poste |
| `available` | booléen | Disponibilité |
| `absence_type` | string ou nul | Type d’indisponibilité |

Valeurs de poste proposées :

- `MORNING`
- `EVENING`
- `NIGHT`

La durée et les règles de repos des postes sont des hypothèses configurables.

## 3.7 Table `staff_requirements`

| Colonne | Type | Description |
|---|---|---|
| `service` | string | Service |
| `shift` | string | Poste |
| `role` | string | Catégorie professionnelle |
| `required_staff` | entier | Besoin minimal |
| `source_type` | string | `synthetic_assumption` |

Les besoins peuvent dépendre du jour, du nombre de lits opérationnels et de la demande estimée.

Ne pas présenter les ratios de staffing du simulateur comme des recommandations cliniques réelles.

## 3.8 Table `forecast_results`

| Colonne | Type | Description |
|---|---|---|
| `forecast_run_id` | string | Identifiant de la prévision |
| `date` | date | Jour prédit |
| `service` | string | Service |
| `model_name` | string | Modèle |
| `yhat` | nombre ≥ 0 | Prévision ponctuelle |
| `lower_bound` | nombre ou nul | Borne basse facultative |
| `upper_bound` | nombre ou nul | Borne haute facultative |
| `created_at` | timestamp | Date de calcul |

Pour des comptages, la prévision peut être arrondie à un entier pour certains calculs opérationnels. Conserver toutefois la valeur continue originale pour l’évaluation statistique.

## 3.9 Résultats d’optimisation

Chaque expérience doit enregistrer au minimum :

- `experiment_id`
- `scenario_id`
- `method_name`
- `solver_status`
- `objective_value`
- `runtime_seconds`
- `optimality_gap`, si disponible
- `unmet_demand_total`
- `staff_shortage_total`
- `coverage_rate`
- `beds_opened_total`
- `fairness_metric`
- `seed`
- `config_hash`

Enregistrer séparément les affectations individuelles et les allocations agrégées.

---

# 4. Génération des données synthétiques

## 4.1 Objectif

Générer des données qui permettent de tester :

- Les tendances.
- Les variations hebdomadaires.
- Les variations entre services.
- Les fluctuations aléatoires.
- Les pics de demande.
- Les absences du personnel.
- Les fermetures de lits.
- Les relations entre admissions, sorties et occupation.

## 4.2 Paramètres par défaut

Créer `configs/hospital.json`.

Exemple :

```json
{
  "hospital_name": "Synthetic Regional Hospital",
  "planning_horizon_days": 7,
  "historical_days": 1095,
  "random_seed": 42,
  "services": {
    "URG": {
      "beds_total": 40,
      "base_daily_admissions": 30
    },
    "MED": {
      "beds_total": 100,
      "base_daily_admissions": 18
    },
    "REA": {
      "beds_total": 30,
      "base_daily_admissions": 5
    },
    "CHI": {
      "beds_total": 130,
      "base_daily_admissions": 12
    }
  },
  "shifts": [
    "MORNING",
    "EVENING",
    "NIGHT"
  ]
}
```

Les admissions de l’exemple sont des valeurs de démonstration, non des données hospitalières observées. L’agent doit vérifier la cohérence entre le volume d’admissions, les durées de séjour et les capacités. Les valeurs peuvent être ajustées pendant la calibration du simulateur.

## 4.3 Génération de la demande

Pour chaque service \(s\) et date \(t\), définir :

\[
\lambda_{s,t} =
\max\left(\epsilon,\,
b_s+w_{s,t}+\tau_{s,t}+e_{s,t}\right)
\]

où :

- \(b_s\) : niveau de base ;
- \(w_{s,t}\) : effet du jour de la semaine ;
- \(\tau_{s,t}\) : tendance ;
- \(e_{s,t}\) : effet d’un événement ;
- \(\epsilon\) : minimum positif.

Générer ensuite :

\[
D_{s,t}\sim \operatorname{Poisson}(\lambda_{s,t})
\]

La loi de Poisson est une baseline. Si les données simulées présentent une variance largement supérieure à leur moyenne, tester une distribution binomiale négative.

### Pseudo-code

```python
for service in services:
    for date in dates:
        rate = (
            base_rate[service]
            + weekday_effect[service][date.weekday()]
            + trend_effect[service][date]
            + event_effect[service][date]
        )

        rate = max(rate, 0.1)
        admissions = rng.poisson(rate)
```

L’implémentation réelle doit utiliser un générateur NumPy dédié :

```python
rng = numpy.random.default_rng(seed)
```

Ne pas utiliser de graine aléatoire globale implicite.

## 4.4 Effets calendaires

Prévoir des profils hebdomadaires configurables.

Exemple :

- Urgences : variation du volume en fonction des jours.
- Chirurgie : réduction des admissions programmées certains jours.
- Médecine : variation plus modérée.
- Réanimation : faible volume, mais fluctuations relatives importantes.

Ces profils doivent être définis dans la configuration et documentés.

## 4.5 Génération des durées de séjour

Une extension utile consiste à générer une durée de séjour entière pour chaque admission.

Pour chaque patient synthétique :

```text
patient_id
service
admission_date
length_of_stay_days
discharge_date
```

Utiliser une distribution configurable, par exemple une loi géométrique ou une loi log-normale arrondie, avec des paramètres différents par service.

Ces distributions sont des hypothèses simulées. Leur objectif est de produire une dynamique plausible, pas de reproduire exactement un hôpital réel.

Calculer les patients présents chaque jour à partir des dates d’admission et de sortie. Vérifier la cohérence des effectifs et des sorties.

## 4.6 Génération du personnel

Générer des professionnels synthétiques selon les rôles et services autorisés.

Les paramètres doivent inclure :

- Nombre de professionnels par rôle.
- Services pour lesquels ils sont qualifiés.
- Disponibilité initiale.
- Heures contractuelles.
- Nombre maximal de postes.
- Contraintes de repos configurables.

Les absences peuvent être tirées au hasard avec une graine reproductible, mais la logique d’affectation doit rester distincte de la logique d’absence.

## 4.7 Fermeture de lits

Simuler des fermetures ponctuelles :

```text
beds_unavailable(date, service)
```

Ne jamais autoriser une capacité négative.

## 4.8 Validation des données générées

Créer `src/data/validation.py`.

Tests requis :

- Aucun doublon de clé date-service.
- Dates continues sur l’intervalle prévu.
- Valeurs non négatives.
- Codes de service connus.
- Cohérence entre capacités totales, indisponibles et opérationnelles.
- Cohérence entre admissions, sorties et occupation.
- Cohérence des identifiants du personnel.
- Cohérence des qualifications et disponibilités.
- Reproductibilité avec une même graine.
- Variabilité observable entre jours et services.

Créer un rapport de qualité contenant :

- Nombre de lignes.
- Dates min/max.
- Valeurs manquantes.
- Doublons.
- Moyennes et écarts-types par service.
- Nombre de valeurs invalides.
- Statut global de validation.

**Livrables :**

- `src/data/generator.py`
- `src/data/validation.py`
- `data/synthetic/*.csv`
- `configs/hospital.json`
- Tests automatisés du générateur.

---

# 5. Prévision de la demande

## 5.1 Cible

Prévoir les admissions journalières par service pour les sept prochains jours.

Pour chaque service :

\[
y_1,\ldots,y_T
\]

Produire :

\[
\hat y_{T+1},\ldots,\hat y_{T+7}
\]

L’occupation doit être traitée comme une variable distincte si elle est également prédite.

## 5.2 Modèles obligatoires

Implémenter au minimum :

1. Naïf.
2. Naïf saisonnier hebdomadaire.
3. Moyenne mobile.
4. Un modèle statistique, tel que SARIMA/SARIMAX ou lissage exponentiel.
5. Une régression avec variables retardées.

Le gradient boosting est une extension recommandée si le volume de données et le temps le permettent.

### Modèle naïf

\[
\hat y_{T+h}=y_T
\]

### Naïf saisonnier hebdomadaire

Pour un horizon hebdomadaire :

\[
\hat y_{T+h}=y_{T+h-7}
\]

si les données requises existent.

### Moyenne mobile

\[
\hat y_{T+1}=\frac{1}{k}\sum_{j=0}^{k-1}y_{T-j}
\]

Pour une prévision multi-pas, préciser comment les valeurs futures sont générées.

### Modèle statistique

Tester SARIMA ou un modèle de lissage exponentiel sur chaque série. Documenter les paramètres et les avertissements de convergence.

### Régression avec variables retardées

Variables possibles :

- `lag_1`
- `lag_7`
- `lag_14`
- `rolling_mean_7`
- `rolling_mean_28`
- jour de la semaine
- week-end
- jour férié simulé
- code du service

Les fenêtres glissantes doivent être calculées sans inclure la valeur cible du jour prédit.

## 5.3 Validation chronologique

Ne pas utiliser un découpage aléatoire classique.

Protocole :

1. Définir une période d’entraînement initiale.
2. Définir une période de validation ultérieure.
3. Répéter l’évaluation sur plusieurs fenêtres temporelles.
4. Conserver une période de test finale non utilisée pour choisir les modèles.
5. Mesurer les erreurs à différents horizons de prévision.

Utiliser une stratégie de type `TimeSeriesSplit` lorsque son comportement convient au protocole choisi.

Documentation :

https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html

Exemple officiel de variables retardées :

https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html

SARIMAX :

https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html

## 5.4 Métriques

### MAE

\[
MAE=\frac{1}{n}\sum_{t=1}^{n}|y_t-\hat y_t|
\]

### RMSE

\[
RMSE=\sqrt{\frac{1}{n}\sum_{t=1}^{n}(y_t-\hat y_t)^2}
\]

### WAPE

\[
WAPE=
\frac{\sum_t|y_t-\hat y_t|}
{\sum_t|y_t|}\times100
\]

Si la somme des observations est nulle, retourner une valeur nulle accompagnée d’un statut explicite ou `NaN`, selon la convention documentée. Ne pas masquer le problème en divisant arbitrairement par un epsilon.

### Biais moyen

\[
Bias=\frac{1}{n}\sum_t(\hat y_t-y_t)
\]

Un biais positif indique une tendance à surestimer la demande ; un biais négatif indique une sous-estimation.

Calculer les métriques :

- Par modèle.
- Par service.
- Par horizon.
- Globalement, avec une agrégation explicitement documentée.

## 5.5 Prévisions opérationnelles

Conserver les prévisions continues pour l’évaluation. Pour le modèle d’allocation, convertir les demandes en unités compatibles avec les variables de décision.

Ne pas arrondir systématiquement toutes les valeurs dès le début du pipeline.

Si des intervalles prédictifs sont ajoutés, évaluer leur couverture et leur largeur sur les données de test.

## 5.6 Sélection du modèle

Le modèle de prévision peut être sélectionné :

- Globalement, si la même méthode est acceptable pour tous les services.
- Par service, si les résultats montrent des différences significatives.

Documenter le choix final et conserver les métriques des modèles non sélectionnés.

**Livrables :**

- `src/forecasting/baselines.py`
- `src/forecasting/statistical.py`
- `src/forecasting/machine_learning.py`
- `src/forecasting/evaluation.py`
- `results/forecasts/`
- Tableau comparatif des modèles.

---

# 6. Traduction des prévisions en besoins opérationnels

## 6.1 Pourquoi une étape intermédiaire est nécessaire

La prévision donne une demande, pas directement une allocation optimale.

Le système doit déterminer :

- Combien de patients peuvent être pris en charge.
- Combien de lits doivent être ouverts.
- Quel effectif est nécessaire par service et poste.
- Quel déficit subsiste si les ressources sont insuffisantes.

## 6.2 Besoin de lits

Si l’occupation future est estimée :

\[
BedsRequired_{s,t}\approx \hat O_{s,t}
\]

La valeur doit être comparée à la capacité opérationnelle.

Si seules les admissions sont prévues, simuler l’occupation future avec les patients déjà présents et les sorties attendues. Ne pas considérer automatiquement les admissions comme des lits occupés sur une journée complète.

## 6.3 Besoin de personnel

Définir des besoins par rôle, service, jour et poste :

\[
R_{s,t,k,r}
\]

où \(r\) représente le rôle professionnel.

Les besoins peuvent dépendre :

- Des lits opérationnels.
- De l’occupation prévue.
- De la demande prévue.
- De paramètres de charge de travail.
- De besoins minimaux définis pour la simulation.

Les ratios utilisés doivent être des hypothèses configurables. La version de démonstration ne doit pas prétendre qu’ils constituent des ratios réglementaires ou cliniques.

---

# 7. Optimisation des lits

## 7.1 Objectif

Minimiser les coûts d’exploitation et les pénuries, sous réserve des capacités disponibles.

## 7.2 Ensembles et paramètres

- \(S\) : services.
- \(T\) : jours.
- \(D_{s,t}\) : demande compatible avec la variable de couverture.
- \(C_{s,t}\) : capacité maximale utilisable.
- \(c^B_s\) : coût d’ouverture d’un lit.
- \(c^U_s\) : pénalité de demande non satisfaite.

## 7.3 Variables

- \(L_{s,t}\) : nombre de lits ouverts.
- \(B_{s,t}\) : nombre de patients pris en charge, avec une unité temporelle cohérente.
- \(U_{s,t}\) : demande non satisfaite.

Ces variables sont entières non négatives.

## 7.4 Fonction objectif

\[
\min Z =
\sum_{s,t}c^B_sL_{s,t}
+
\sum_{s,t}c^U_sU_{s,t}
\]

Les coûts sont des coefficients de simulation. Ils doivent être conservés dans la configuration de l’expérience.

## 7.5 Contraintes

Capacité :

\[
0\le L_{s,t}\le C_{s,t}
\]

Conservation de la demande dans un modèle où les unités sont compatibles :

\[
B_{s,t}+U_{s,t}=D_{s,t}
\]

Couverture par les lits :

\[
B_{s,t}\le L_{s,t}
\]

Cette dernière contrainte est valable lorsque \(B_{s,t}\) représente une occupation compatible avec le nombre de lits ouverts. Elle ne doit pas être utilisée naïvement si \(B_{s,t}\) représente uniquement des admissions quotidiennes.

## 7.6 Extensions

- Coût de fermeture ou d’ouverture d’un lit.
- Pénalité pour changements brusques de capacité.
- Capacité minimale par service.
- Transferts entre services, uniquement si le modèle les définit explicitement.
- Occupation et durée de séjour.
- Demande non satisfaite avec différentes pénalités selon le service.

## 7.7 Implémentation

Utiliser PuLP + CBC comme première implémentation MILP.

Documentation :

https://coin-or.github.io/pulp/

Code du solveur CBC :

https://github.com/coin-or/Cbc

Ne pas coder la résolution exacte à la main. Construire le modèle avec une bibliothèque reconnue et conserver le statut retourné par le solveur.

---

# 8. Optimisation du personnel

## 8.1 Objectif

Affecter les professionnels aux services et aux postes de manière à couvrir les besoins tout en respectant les contraintes de disponibilité, de qualification, de repos et de charge de travail.

## 8.2 Ensembles

- \(I\) : professionnels.
- \(S\) : services.
- \(T\) : jours.
- \(K\) : postes.
- \(R\) : catégories professionnelles.

## 8.3 Paramètres

- \(a_{i,t,k}\) : disponibilité.
- \(q_{i,s}\) : qualification pour le service.
- \(g_{i,r}\) : rôle du professionnel.
- \(N_{s,t,k,r}\) : effectif requis.
- \(H_i\) : heures contractuelles.
- \(M_i\) : nombre maximal de postes.
- \(c_{i,s,t,k}\) : coût d’affectation, si nécessaire.

## 8.4 Variable de décision

\[
X_{i,s,t,k}\in\{0,1\}
\]

Elle vaut 1 si le professionnel \(i\) est affecté au service \(s\), le jour \(t\), au poste \(k\).

## 8.5 Contraintes de disponibilité

\[
X_{i,s,t,k}\le a_{i,t,k}
\]

## 8.6 Contraintes de qualification

\[
X_{i,s,t,k}\le q_{i,s}
\]

## 8.7 Un seul poste par jour

\[
\sum_{s\in S}\sum_{k\in K}X_{i,s,t,k}\le1
\]

Cette contrainte doit être adaptée si les postes peuvent se chevaucher ou si des règles spécifiques sont retenues.

## 8.8 Couverture des besoins

Pour chaque service, jour, poste et rôle :

\[
\sum_{i\in I_r}X_{i,s,t,k}\ge N_{s,t,k,r}
\]

où \(I_r\) représente les professionnels du rôle requis.

## 8.9 Contraintes de charge

Ajouter selon le besoin :

- Maximum de postes par semaine.
- Maximum d’heures contractuelles.
- Temps minimal de repos.
- Interdiction de certaines séquences de postes.
- Limitation des postes de nuit consécutifs.
- Répartition équitable des week-ends.
- Respect des qualifications.
- Préférences individuelles comme contraintes souples.

Les règles précises doivent être configurables et documentées. Les paramètres fictifs du projet ne doivent pas être présentés comme des règles de droit du travail.

## 8.10 Fonction objectif

Exemple :

\[
\min Z =
\lambda_1\cdot\text{Coût}
+\lambda_2\cdot\text{Déficit de couverture}
+\lambda_3\cdot\text{Pénalité d'iniquité}
+\lambda_4\cdot\text{Préférences non respectées}
\]

Pour les contraintes qui ne doivent jamais être violées, utiliser des contraintes dures. Les coefficients de pénalité sont réservés aux objectifs secondaires et aux contraintes souples.

## 8.11 Solveur CP-SAT

Implémenter le planning du personnel avec OR-Tools CP-SAT.

Documentation :

https://developers.google.com/optimization/scheduling/employee_scheduling

Exemple officiel de planning infirmier :

https://github.com/google/or-tools/blob/stable/ortools/sat/samples/nurses_sat.py

Le modèle doit renvoyer :

- Statut du solveur.
- Affectations.
- Besoins couverts.
- Besoins non couverts.
- Temps de résolution.
- Valeur objective si disponible.
- Informations d’optimalité disponibles.

---

# 9. Algorithmes à comparer

## 9.1 Algorithme A — Heuristique gloutonne

Construire une baseline explicable.

Procédure possible :

1. Trier les besoins par criticité configurée.
2. Trier les besoins par déficit.
3. Rechercher les professionnels disponibles et qualifiés.
4. Affecter un professionnel si cela ne viole pas les contraintes dures.
5. Répéter jusqu’à ce que les besoins soient couverts ou qu’il n’existe plus de candidat faisable.
6. Calculer les pénuries et les métriques.
7. Passer le résultat au validateur indépendant.

La méthode doit être déterministe pour une entrée et une configuration identiques, sauf si une randomisation est explicitement activée.

## 9.2 Algorithme B — MILP

Utiliser PuLP + CBC pour le modèle d’allocation et, si le périmètre le permet, une formulation MILP du planning du personnel.

## 9.3 Algorithme C — CP-SAT

Utiliser OR-Tools pour le planning individuel avec contraintes combinatoires.

## 9.4 Comparaison équitable

Les méthodes doivent partager :

- Le même jeu de données.
- Les mêmes prévisions.
- Le même scénario.
- Les mêmes capacités.
- Les mêmes qualifications.
- Les mêmes contraintes dures.
- Les mêmes coefficients de coût.
- Le même validateur.
- Des limites de calcul documentées.

Pour chaque méthode, conserver :

- Statut du solveur.
- Temps de calcul.
- Valeur objective.
- Demande non satisfaite.
- Couverture.
- Pénuries de personnel.
- Équité.
- Écart d’optimalité, lorsqu’il est disponible.

Ne pas déclarer une méthode supérieure uniquement sur la base d’une valeur objective si les modèles ne respectent pas les mêmes contraintes.

## 9.5 État de l’art

La littérature récente sur le nurse rostering couvre notamment la programmation entière, la programmation par contraintes, les heuristiques, les métaheuristiques, les approches hybrides et l’intégration du machine learning.

Références :

- Koukaras et al., *Operations research: a comprehensive literature review on nurse rostering optimisation*, Operational Research, 2026.  
  https://link.springer.com/article/10.1007/s12351-026-01090-9

- Cornei et Breabăn, *The Nurse Rostering Problem: Recent Advances and Future Perspectives*, 2026.  
  https://www.tandfonline.com/doi/full/10.1080/08839514.2026.2690801

- Böðvarsdóttir et Stidsen, *A review of multi-objective optimization methods for personnel rostering problems*, Journal of Scheduling, 2025/2026.  
  https://link.springer.com/article/10.1007/s10951-025-00845-0

Pour le MVP, privilégier l’heuristique, le MILP et le CP-SAT. Les algorithmes génétiques, la recherche tabou, le simulated annealing et les méthodes hybrides peuvent être présentés dans l’état de l’art ou ajoutés comme extensions.

---

# 10. Scénarios expérimentaux

## 10.1 Scénarios de référence

Créer `configs/scenarios.json`.

Scénarios minimaux :

| Code | Scénario | Paramètres |
|---|---|---|
| `S0_BASELINE` | Demande normale | Multiplicateur 1, absences 0 % |
| `S1_URGENT_PEAK` | Pic aux urgences | Hausse de 50 % ou 100 % pendant 2 jours |
| `S2_GENERAL_SURGE` | Hausse générale | Multiplicateur 1,25 |
| `S3_STAFF_ABSENCE` | Absences | 15 % des professionnels initialement disponibles |
| `S4_COMBINED_CRISIS` | Crise combinée | Hausse de demande et absences |
| `S5_BED_CLOSURE` | Fermeture de lits | Réduction configurable de capacité |

Les valeurs sont des hypothèses de stress test, pas des estimations empiriques.

## 10.2 Analyse de sensibilité

Faire varier les absences :

```text
0 %, 5 %, 10 %, 15 %, 20 %
```

Faire varier la demande :

```text
1.00, 1.25, 1.50, 2.00
```

Tester plusieurs réductions de capacité, par exemple :

```text
0 %, 5 %, 10 %, 20 %
```

Chaque combinaison constitue une expérience identifiable.

## 10.3 Répétabilité

Chaque scénario doit avoir :

- Un identifiant stable.
- Une configuration explicite.
- Une graine aléatoire.
- Une version du modèle.
- Les résultats de chaque méthode.
- Un horodatage.
- Un statut de validation.

Ne pas générer de nouvelles données aléatoires invisiblement lors du changement d’un filtre de dashboard.

## 10.4 Protocole expérimental

Séparer les deux expériences suivantes.

### Expérience de prévision

Mesurer les erreurs sur une période historique de test.

### Expérience d’optimisation

Utiliser des prévisions données et comparer les méthodes sur les mêmes instances.

Pour une analyse de robustesse, il est également possible de comparer une politique construite avec la prévision centrale à la demande effectivement simulée. Cette évaluation doit être explicitement distinguée de l’optimisation sous prévision parfaite.

---

# 11. KPI et métriques

## 11.1 Prévision

- MAE.
- RMSE.
- WAPE.
- Biais moyen.
- Métriques par service.
- Métriques par horizon.

## 11.2 Allocation

### Demande satisfaite

\[
DemandServed=\sum_{s,t}B_{s,t}
\]

### Demande non satisfaite

\[
UnmetDemand=\sum_{s,t}U_{s,t}
\]

### Taux de couverture

\[
Coverage=
\frac{DemandServed}{TotalDemand}
\]

Si `TotalDemand` est nul, le KPI doit avoir un statut particulier plutôt qu’une division par zéro.

### Taux d’occupation

\[
OccupancyRate_{s,t}=
\frac{OccupiedBeds_{s,t}}{OperationalBeds_{s,t}}
\]

Si aucun lit n’est opérationnel, l’indicateur doit être marqué non défini.

Ne pas confondre le taux d’occupation et le taux de couverture de la demande.

## 11.3 Personnel

- Nombre de postes requis.
- Nombre de postes couverts.
- Nombre de postes non couverts.
- Heures affectées.
- Heures supplémentaires simulées.
- Nombre de violations de contraintes dures.
- Répartition des nuits.
- Répartition des week-ends.
- Mesure d’équité de la charge.

Une mesure simple d’équité peut utiliser l’écart-type du nombre de postes ou des heures entre professionnels comparables. Il faut documenter les limites de cette mesure, notamment les différences de rôle et de disponibilité.

## 11.4 Performance algorithmique

- Temps de calcul.
- Valeur objective.
- Statut du solveur.
- Écart d’optimalité lorsqu’il est disponible.
- Nombre de contraintes violées selon le validateur.
- Résultat reproductible ou non.

---

# 12. Dashboard interactif

## 12.1 Pages recommandées

### Page 1 — Vue d’ensemble

Afficher :

- Capacité totale.
- Lits opérationnels.
- Demande prévue.
- Couverture estimée.
- Pénuries de personnel.
- Dernière expérience exécutée.
- Statut de validation.

### Page 2 — Exploration des données

Graphiques :

- Admissions historiques par service.
- Distribution journalière.
- Variation par jour de la semaine.
- Occupation simulée.
- Lits indisponibles.
- Absences du personnel.

### Page 3 — Prévision

Graphiques :

- Historique et prévision.
- Comparaison des modèles.
- MAE/RMSE/WAPE par service.
- Prévisions J+1 à J+7.
- Intervalles prédictifs, s’ils ont été validés.

### Page 4 — Allocation des ressources

Afficher :

- Lits ouverts par service et jour.
- Occupation prévue.
- Demande satisfaite et non satisfaite.
- Effectifs requis et affectés.
- Grille du planning du personnel.

### Page 5 — Comparaison des méthodes

Comparer :

- Heuristique gloutonne.
- MILP.
- CP-SAT.

Graphiques :

- Coût total par méthode.
- Couverture par méthode.
- Pénuries par méthode.
- Temps de calcul.
- Statut des solveurs.

### Page 6 — Scénarios

Permettre de sélectionner un scénario et d’examiner :

- Les changements de demande.
- Les changements de capacité.
- Les absences.
- Les allocations résultantes.
- Les KPI.
- Les différences par rapport au scénario de référence.

### Page 7 — Sensibilité

Afficher :

- Courbes de couverture selon l’absentéisme.
- Courbes de coût selon le multiplicateur de demande.
- Heatmap demande × absentéisme.
- Frontière de Pareto coût/couverture.

### Page 8 — Expériences et export

Afficher la liste des expériences avec :

- ID.
- Configuration.
- Date d’exécution.
- Méthodes exécutées.
- Statuts.
- KPI principaux.

Permettre l’export CSV des résultats.

## 12.2 Visualisations obligatoires

1. Courbe historique/prévision par service.
2. Barres groupées des KPI par méthode.
3. Heatmap des pénuries par service et jour.
4. Courbe de couverture en fonction du taux d’absence.
5. Courbe du coût en fonction de la demande.
6. Planning du personnel par jour et poste.
7. Comparaison du nombre de lits ouverts et de l’occupation.
8. Nuage de points coût/couverture.

## 12.3 Frontière de Pareto

Tracer :

- Axe X : coût.
- Axe Y : couverture.

Une solution est dominée lorsqu’une autre solution offre un coût inférieur ou égal et une couverture supérieure ou égale, avec au moins une amélioration stricte.

Si les méthodes ont des contraintes différentes ou des solutions infaisables, ne pas mélanger leurs résultats dans la frontière sans expliciter le traitement.

## 12.4 Interaction

Les filtres doivent modifier les graphiques sans relancer le solveur inutilement.

Les expériences doivent être calculées et stockées séparément de leur visualisation.

Utiliser Plotly pour les graphiques interactifs :

https://plotly.com/python/

---

# 13. Orchestration des expériences

Créer `src/experiments/runner.py`.

## 13.1 Pipeline d’une expérience

```text
Load configuration
       ↓
Validate configuration
       ↓
Load or generate dataset
       ↓
Apply scenario transformation
       ↓
Validate transformed data
       ↓
Generate or load forecasts
       ↓
Run allocation methods
       ↓
Validate each solution independently
       ↓
Calculate KPI
       ↓
Save raw results
       ↓
Generate comparison tables
       ↓
Display in dashboard
```

## 13.2 Contrat de résultat

Chaque méthode doit retourner un objet de résultat normalisé.

Exemple conceptuel :

```python
{
    "experiment_id": "exp_0001",
    "scenario_id": "S0_BASELINE",
    "method_name": "milp",
    "status": "OPTIMAL",
    "runtime_seconds": 1.24,
    "objective_value": 1250.0,
    "unmet_demand": 3,
    "staff_shortage": 0,
    "coverage_rate": 0.97,
    "validation_passed": True,
    "assignments": [],
    "metrics": {}
}
```

Les valeurs numériques sont illustratives et ne représentent pas des résultats de benchmark.

Normaliser les statuts :

- `OPTIMAL`
- `FEASIBLE`
- `INFEASIBLE`
- `UNKNOWN`
- `ERROR`

Ne pas supposer qu’un solveur utilise exactement les mêmes libellés. Convertir les statuts propres aux bibliothèques vers ce vocabulaire interne.

## 13.3 Échecs

Si un solveur échoue :

- Enregistrer l’erreur.
- Conserver les résultats des autres méthodes.
- Marquer l’expérience comme partiellement terminée.
- Ne pas remplacer une solution manquante par zéro.
- Ne pas afficher une solution infaisable comme un planning valide.

---

# 14. Organisation du dépôt

Structure recommandée :

```text
mini-projet-4/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── configs/
│   ├── hospital.json
│   └── scenarios.json
├── data/
│   ├── raw/
│   ├── processed/
│   └── synthetic/
├── src/
│   ├── data/
│   │   ├── generator.py
│   │   ├── occupancy.py
│   │   ├── preprocessing.py
│   │   └── validation.py
│   ├── forecasting/
│   │   ├── baselines.py
│   │   ├── statistical.py
│   │   ├── machine_learning.py
│   │   └── evaluation.py
│   ├── optimization/
│   │   ├── bed_allocation.py
│   │   ├── greedy.py
│   │   ├── milp.py
│   │   ├── cp_sat.py
│   │   └── validator.py
│   ├── experiments/
│   │   ├── scenarios.py
│   │   ├── runner.py
│   │   └── metrics.py
│   ├── storage/
│   │   └── repository.py
│   └── dashboard/
│       ├── app.py
│       └── pages/
├── tests/
│   ├── test_generator.py
│   ├── test_occupancy.py
│   ├── test_forecasting.py
│   ├── test_optimization.py
│   ├── test_validator.py
│   └── test_experiments.py
├── results/
│   ├── forecasts/
│   ├── allocations/
│   ├── metrics/
│   └── figures/
└── docs/
    ├── specification.md
    ├── mathematical_model.md
    ├── data_dictionary.md
    ├── experiment_protocol.md
    └── references.md
```

Les fichiers générés volumineux ne doivent pas être versionnés systématiquement. Documenter ce qui est généré et comment le régénérer.

---

# 15. Tests et assurance qualité

## 15.1 Tests de données

- Reproductibilité de la génération.
- Absence de doublons.
- Dates cohérentes.
- Valeurs non négatives.
- Conservation de l’occupation.
- Cohérence des capacités.
- Cohérence des qualifications.

## 15.2 Tests de prévision

- Chaque modèle accepte les séries valides.
- Les modèles échouent explicitement si les historiques sont trop courts.
- Les sorties couvrent exactement l’horizon demandé.
- Les prévisions ne contiennent pas de valeurs non finies.
- Les métriques traitent les séries nulles selon la convention documentée.
- Les variables retardées n’utilisent pas les cibles futures.
- La validation est chronologique.

## 15.3 Tests d’optimisation

- Aucune affectation à un professionnel indisponible.
- Aucune affectation non qualifiée.
- Aucun double poste interdit.
- Couverture calculée correctement.
- Respect des capacités.
- Demande non satisfaite cohérente.
- Statuts du solveur correctement interprétés.
- Solutions infaisables non affichées comme valides.

## 15.4 Validateur indépendant

Créer `src/optimization/validator.py`.

Le validateur doit vérifier la solution à partir des données d’entrée et des affectations retournées, sans simplement réutiliser les expressions de contraintes du solveur.

Retourner une structure contenant :

```text
valid
hard_constraint_violations
capacity_violations
availability_violations
qualification_violations
double_assignment_violations
coverage_deficits
messages
```

Les contraintes souples doivent être évaluées séparément des contraintes dures.

## 15.5 Tests de scénarios

- Le scénario de référence ne modifie pas les données de base.
- Un scénario d’absence diminue ou maintient la disponibilité.
- Un scénario de fermeture ne peut pas augmenter la capacité.
- Une hausse de demande modifie bien les données d’entrée.
- Le même scénario et la même graine produisent les mêmes résultats déterministes.
- Les résultats d’un scénario restent distincts des résultats d’un autre scénario.

## 15.6 Cas limites

Tester notamment :

- Demande nulle.
- Aucun professionnel disponible.
- Tous les lits fermés.
- Professionnel qualifié pour plusieurs services.
- Aucun professionnel qualifié pour un besoin donné.
- Série historique trop courte.
- Absences très élevées.
- Demande supérieure à la capacité.
- Solveur sans solution faisable.
- Valeurs manquantes ou invalides dans une configuration.

---

# 16. Plan de réalisation sur quatre semaines

## Semaine 1 — Données et spécification

- Définir les unités et les hypothèses.
- Créer les configurations.
- Implémenter le générateur.
- Implémenter la simulation d’occupation.
- Ajouter les contrôles de qualité.
- Construire les premières visualisations exploratoires.
- Écrire la formulation mathématique initiale.

**Critère de sortie :** les données sont générées et validées, et le modèle de données est documenté.

## Semaine 2 — Prévision et allocation initiale

- Implémenter les baselines.
- Implémenter un modèle statistique.
- Implémenter une régression à variables retardées.
- Évaluer les modèles chronologiquement.
- Développer l’allocation agrégée des lits.
- Construire l’heuristique gloutonne.
- Ajouter les tests unitaires.

**Critère de sortie :** prévisions à sept jours et première allocation vérifiable.

## Semaine 3 — Personnel et expériences

- Implémenter le planning du personnel.
- Ajouter les contraintes de disponibilité et de qualification.
- Implémenter CP-SAT et/ou MILP.
- Construire le validateur indépendant.
- Ajouter les scénarios.
- Enregistrer les KPI et les résultats.
- Exécuter les premières comparaisons.

**Critère de sortie :** plusieurs méthodes exécutables sur les mêmes scénarios.

## Semaine 4 — Dashboard et livraison

- Construire les pages du dashboard.
- Ajouter les comparaisons et les heatmaps.
- Ajouter les analyses de sensibilité.
- Finaliser les tests.
- Générer les figures.
- Rédiger le rapport.
- Préparer une démonstration reproductible.

**Critère de sortie :** application fonctionnelle, tests exécutés, résultats reproductibles et documentation livrée.

---

# 17. Répartition du travail entre six membres

| Membre | Responsabilité | Modules |
|---|---|---|
| M1 | Données synthétiques | `src/data/` |
| M2 | Prévision | `src/forecasting/` |
| M3 | Allocation des lits | `src/optimization/bed_allocation.py`, `milp.py` |
| M4 | Planning du personnel | `src/optimization/cp_sat.py`, `greedy.py` |
| M5 | Scénarios et évaluation | `src/experiments/` |
| M6 | Dashboard et intégration | `src/dashboard/`, README et démonstration |

Tous les membres doivent s’accorder sur les contrats de données et les unités avant de développer les modules indépendamment.

---

# 18. Critères d’acceptation finaux

Le projet est considéré comme livré lorsque :

- [ ] Les données synthétiques sont générées automatiquement.
- [ ] La génération est reproductible.
- [ ] Les contrôles de qualité sont automatisés.
- [ ] Les admissions et l’occupation sont modélisées séparément.
- [ ] Plusieurs modèles de prévision sont comparés.
- [ ] Les prévisions sont évaluées chronologiquement.
- [ ] Les résultats sont présentés par service et par horizon.
- [ ] Le modèle d’allocation respecte les capacités.
- [ ] Le planning du personnel respecte les disponibilités et qualifications.
- [ ] Au moins trois approches de planification sont comparées, dont une baseline et une approche exacte ou à contraintes.
- [ ] Les solutions sont vérifiées indépendamment.
- [ ] Les statuts infaisables sont correctement traités.
- [ ] Les scénarios de demande, d’absence et de capacité sont configurables.
- [ ] Les KPI sont calculés de manière cohérente.
- [ ] Le dashboard compare coût, couverture, pénuries et temps de calcul.
- [ ] Une analyse de sensibilité est disponible.
- [ ] Les résultats sont exportables.
- [ ] Les tests automatisés passent.
- [ ] Les hypothèses et limites sont documentées.
- [ ] La démonstration fonctionne sans accès à un système hospitalier réel.

---

# 19. Références scientifiques et techniques

## 19.1 État de l’art : planification du personnel

### R1 — Revue récente du nurse rostering

Koukaras et al. (2026). *Operations research: a comprehensive literature review on nurse rostering optimisation*. Operational Research.

https://link.springer.com/article/10.1007/s12351-026-01090-9

Intérêt : taxonomie des méthodes d’optimisation, programmation entière, heuristiques, métaheuristiques, approches hybrides et directions futures.

### R2 — Avancées récentes du Nurse Rostering Problem

Cornei et Breabăn (2026). *The Nurse Rostering Problem: Recent Advances and Future Perspectives*.

https://www.tandfonline.com/doi/full/10.1080/08839514.2026.2690801

Intérêt : synthèse des travaux publiés entre 2019 et 2025, y compris l’émergence de méthodes intégrant le machine learning.

### R3 — Optimisation multiobjectif des plannings

Böðvarsdóttir et Stidsen. *A review of multi-objective optimization methods for personnel rostering problems*. Journal of Scheduling.

https://link.springer.com/article/10.1007/s10951-025-00845-0

Intérêt : compromis entre les objectifs de l’organisation et ceux du personnel, et comparaison des approches multiobjectifs.

## 19.2 Gestion des lits hospitaliers

### R4 — Revue systématique de la gestion des lits

*A systematic review of research design and modeling techniques in inpatient bed management*. Computers & Industrial Engineering, 2019.

https://doi.org/10.1016/j.cie.2018.10.033

Intérêt : panorama des techniques de modélisation et des méthodes de recherche opérationnelle pour la gestion des lits.

### R5 — Simulation-optimisation de l’allocation des lits

*A Simulation-Optimisation approach for hospital beds allocation*. International Journal of Medical Informatics, 2020.

https://doi.org/10.1016/j.ijmedinf.2020.104174

Intérêt : exemple d’approche combinant simulation et optimisation pour la gestion des capacités hospitalières.

## 19.3 Prévision de la demande hospitalière

### R6 — Revue systématique de la prévision des arrivées aux urgences

*Predictive modeling of hospital emergency department demand using artificial intelligence: A systematic review*. International Journal of Medical Informatics, 2026.

https://doi.org/10.1016/j.ijmedinf.2025.106215

Intérêt : comparaison des méthodes statistiques et d’intelligence artificielle, variables externes, validation et limites de généralisation.

## 19.4 Données synthétiques de santé

### R7 — Synthea

Dépôt officiel :

https://github.com/synthetichealth/synthea

Intérêt : génération de dossiers médicaux synthétiques et exports dans des formats exploitables.

### R8 — Publication scientifique sur Synthea

Walonoski et al. (2018). *Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record*. Journal of the American Medical Informatics Association.

https://doi.org/10.1093/jamia/ocx079

Intérêt : description scientifique de l’approche de génération de patients synthétiques.

## 19.5 Documentation d’implémentation

### R9 — Google OR-Tools : Employee Scheduling

https://developers.google.com/optimization/scheduling/employee_scheduling

À utiliser pour construire le planning du personnel et comprendre les contraintes de disponibilité et de poste.

### R10 — Exemple OR-Tools pour le planning infirmier

https://github.com/google/or-tools/blob/stable/ortools/sat/samples/nurses_sat.py

### R11 — PuLP

https://coin-or.github.io/pulp/

À utiliser pour définir les variables, la fonction objectif et les contraintes du modèle MILP.

### R12 — CBC

https://github.com/coin-or/Cbc

Solveur d’optimisation en nombres entiers.

### R13 — Scikit-learn : variables retardées pour la prévision

https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html

À utiliser pour la création des variables temporelles et l’évaluation des modèles de régression.

### R14 — Validation chronologique

https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html

### R15 — Statsmodels SARIMAX

https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html

### R16 — Plotly Python

https://plotly.com/python/

À utiliser pour les graphiques interactifs du dashboard.

### R17 — Documentation pandas

https://pandas.pydata.org/docs/

### R18 — Documentation NumPy

https://numpy.org/doc/

### R19 — Documentation Streamlit

https://docs.streamlit.io/

### R20 — CNDP Maroc

https://www.cndp.ma/textes-et-lois/

À consulter si le projet évolue vers l’utilisation de données personnelles de santé réelles. Le MVP doit rester fondé sur des données synthétiques.

---

# 20. Prompt de démarrage pour l’agent de code

Tu peux utiliser le texte suivant pour lancer l’implémentation avec un agent de développement.

> Tu es un ingénieur logiciel senior spécialisé en Python, data science, recherche opérationnelle et applications d’aide à la décision.
>
> Implémente le projet décrit dans ce cahier des charges en privilégiant la simplicité, la qualité du code, la reproductibilité et les tests.
>
> Commence par inspecter le dépôt existant et conserve les fonctionnalités déjà présentes lorsqu’elles sont compatibles avec le cahier des charges.
>
> Avant de coder, propose un plan d’implémentation découpé en petites étapes vérifiables. N’implémente pas toutes les fonctionnalités simultanément.
>
> Commence par la configuration, la génération des données synthétiques et leur validation. Ajoute ensuite les modèles de prévision, puis les méthodes d’optimisation, les scénarios et enfin le dashboard.
>
> Utilise Python, pandas, NumPy, scikit-learn, statsmodels, PuLP/CBC, OR-Tools CP-SAT, Streamlit, Plotly et pytest, selon les besoins définis.
>
> Respecte impérativement la distinction entre admissions, occupation, lits opérationnels et effectifs. N’utilise pas le nombre d’admissions comme substitut direct du nombre de lits occupés.
>
> Implémente une baseline avant chaque méthode complexe. Compare les méthodes d’optimisation sur les mêmes instances et contraintes. Vérifie les solutions avec un validateur indépendant.
>
> Chaque expérience doit conserver sa configuration, sa graine, ses métriques, son statut de résolution et ses résultats bruts.
>
> N’invente aucun résultat scientifique ou benchmark. Les paramètres hospitaliers sont synthétiques et doivent être documentés comme tels.
>
> Écris des tests unitaires et d’intégration au fur et à mesure. Ne considère pas une fonctionnalité comme terminée tant que ses tests ne passent pas.
>
> Pour chaque étape, fournis un résumé des fichiers créés ou modifiés, des décisions techniques, des tests exécutés et des limites connues.
>
> Ne commence pas par Kubernetes, Kafka, Spark ou une architecture distribuée. Le premier objectif est de produire un pipeline complet, fiable, explicable et reproductible.
>
> À la fin, fournis un README expliquant l’installation, la génération des données, l’exécution des prévisions, le lancement des expériences, le démarrage du dashboard, les tests et les limites du modèle.

---

## Conclusion

Le résultat attendu est un prototype reproductible de recherche opérationnelle appliquée à la planification hospitalière. Sa valeur scientifique doit venir de la qualité du modèle, de la validation des prévisions, de la formulation des contraintes, de la comparaison équitable des algorithmes et de l’analyse des scénarios — pas seulement de l’interface graphique.

La priorité d’implémentation est :

1. Données synthétiques et validation.
2. Prévision et évaluation.
3. Modèle d’allocation des lits.
4. Planning du personnel.
5. Comparaison des algorithmes.
6. Scénarios et sensibilité.
7. Dashboard.
8. Tests, documentation et rapport final.

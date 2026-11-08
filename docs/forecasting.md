# Prévision de la demande — phase 3

La cible est `admissions`, séparée de l'occupation et des capacités. Chaque méthode produit des valeurs continues, finies et non négatives pour les sept jours suivants.

## Modèles comparés

- `naive` répète la dernière admission observée.
- `seasonal_naive` réutilise la valeur de même position dans la dernière semaine et propage récursivement cette saison pour les horizons suivants.
- `moving_average` emploie une fenêtre de sept jours ; chaque prévision alimente la fenêtre des horizons ultérieurs.
- `exponential_smoothing` ajuste un lissage exponentiel simple du niveau de la série. La saisonnalité hebdomadaire est portée explicitement par le modèle naïf saisonnier ; en cas d'échec numérique, le lissage revient à ce dernier et ne publie jamais de valeur non finie.
- `lagged_regression` utilise `lag_1`, `lag_7`, `lag_14`, moyennes mobiles passées de 7 et 28 jours, jour de semaine et jour férié. Les événements exceptionnels ne sont pas supposés connus dans le futur et ne sont donc pas utilisés comme variable explicative future.

## Validation chronologique

L'entraînement initial comporte 730 jours. Douze origines de validation sont situées strictement avant les 28 derniers jours. Ces 28 jours forment le test final réservé, évalué sur quatre horizons complets de sept jours.

Les modèles sont sélectionnés par service selon la WAPE de validation, puis réajustés sur tout l'historique avant de produire J+1 à J+7. Le test final n'intervient pas dans cette sélection.

Les métriques sont MAE, RMSE, WAPE et biais moyen, calculées par partition, modèle, service et horizon. Lorsque la somme des observations est nulle, la WAPE est `NaN` et `wape_status` vaut `zero_actual_total`.

## Exécution

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.forecasting.evaluation
```

Les fichiers suivants sont écrits dans `results/forecasts/` : prédictions d'évaluation, métriques par horizon, synthèse de métriques, sélection par service, prévisions finales de tous les modèles et métadonnées d'exécution.

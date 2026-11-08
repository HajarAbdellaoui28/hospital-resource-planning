"""Régression déterministe sur variables retardées, sans cible future."""

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

REQUIRED_HISTORY = 28


def lagged_regression_forecast(
    history: pd.Series,
    future_dates: pd.DatetimeIndex,
    holiday_month_days: set[str],
) -> np.ndarray:
    """Prévoit récursivement avec lags, moyennes passées et calendrier connu.

    Les événements exceptionnels ne sont jamais utilisés comme variable future, car
    ils ne sont pas connus lors d'une prévision opérationnelle. Les jours fériés
    synthétiques sont dérivés de la date, donc disponibles sans fuite temporelle.
    """
    if len(history) < REQUIRED_HISTORY:
        raise ValueError(f"La régression retardée requiert au moins {REQUIRED_HISTORY} observations.")
    values = history.astype(float).tolist()
    training_rows = [
        _feature_row(values[:index], history.index[index], holiday_month_days)
        for index in range(REQUIRED_HISTORY, len(values))
    ]
    targets = np.asarray(values[REQUIRED_HISTORY:], dtype=float)
    model = Ridge(alpha=1.0, positive=True)
    model.fit(np.asarray(training_rows), targets)
    predictions: list[float] = []
    for future_date in future_dates:
        feature = _feature_row(values, future_date, holiday_month_days)
        prediction = max(float(model.predict(np.asarray([feature]))[0]), 0.0)
        predictions.append(prediction)
        values.append(prediction)
    return np.asarray(predictions)


def _feature_row(values: list[float], date: pd.Timestamp, holiday_month_days: set[str]) -> list[float]:
    """Construit une ligne de variables exclusivement à partir de l'historique fourni."""
    if len(values) < REQUIRED_HISTORY:
        raise ValueError(f"Au moins {REQUIRED_HISTORY} valeurs passées sont requises.")
    weekday = date.weekday()
    return [
        values[-1],
        values[-7],
        values[-14],
        float(np.mean(values[-7:])),
        float(np.mean(values[-28:])),
        *(1.0 if weekday == day else 0.0 for day in range(1, 7)),
        float(date.strftime("%m-%d") in holiday_month_days),
    ]

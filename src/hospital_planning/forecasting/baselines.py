"""Méthodes de prévision de référence, déterministes et sans fuite temporelle."""

import numpy as np
import pandas as pd


def naive_forecast(history: pd.Series, horizon: int) -> np.ndarray:
    """Répète la dernière valeur observée sur tout l'horizon."""
    _require_history(history, 1)
    return np.repeat(float(history.iloc[-1]), horizon)


def seasonal_naive_forecast(history: pd.Series, horizon: int, period: int = 7) -> np.ndarray:
    """Projette récursivement la dernière saison observée."""
    _require_history(history, period)
    values = history.astype(float).tolist()
    predictions: list[float] = []
    for _ in range(horizon):
        prediction = values[-period]
        predictions.append(prediction)
        values.append(prediction)
    return np.asarray(predictions)


def moving_average_forecast(history: pd.Series, horizon: int, window: int = 7) -> np.ndarray:
    """Prévision multi-pas récursive à moyenne mobile ; les prédictions alimentent la suite."""
    _require_history(history, window)
    values = history.astype(float).tolist()
    predictions: list[float] = []
    for _ in range(horizon):
        prediction = float(np.mean(values[-window:]))
        predictions.append(prediction)
        values.append(prediction)
    return np.asarray(predictions)


def _require_history(history: pd.Series, minimum_length: int) -> None:
    if history.empty or len(history) < minimum_length:
        raise ValueError(
            f"Historique insuffisant : {minimum_length} observations sont requises ({len(history)} reçues)."
        )
    if not np.isfinite(history.to_numpy(dtype=float)).all():
        raise ValueError("L'historique contient des valeurs non finies.")

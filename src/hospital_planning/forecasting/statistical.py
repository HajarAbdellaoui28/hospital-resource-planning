"""Modèle statistique de lissage exponentiel pour séries quotidiennes."""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import SimpleExpSmoothing


def exponential_smoothing_forecast(history: pd.Series, horizon: int) -> np.ndarray:
    """Ajuste un lissage exponentiel simple sur le niveau de la série.

    Les avertissements de convergence sont capturés : en cas d'échec ou de sortie
    non finie, la méthode revient au naïf saisonnier plutôt que de publier une valeur
    invalide.
    """
    values = history.astype(float)
    if len(values) < 14:
        raise ValueError("Le lissage exponentiel requiert au moins 14 observations.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = SimpleExpSmoothing(values, initialization_method="estimated").fit(optimized=True)
        prediction = np.asarray(fitted.forecast(horizon), dtype=float)
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        prediction = _seasonal_fallback(values, horizon)
    if not np.isfinite(prediction).all():
        prediction = _seasonal_fallback(values, horizon)
    return np.maximum(prediction, 0.0)


def _seasonal_fallback(history: pd.Series, horizon: int) -> np.ndarray:
    values = history.tolist()
    prediction: list[float] = []
    for _ in range(horizon):
        value = float(values[-7])
        prediction.append(value)
        values.append(value)
    return np.asarray(prediction)

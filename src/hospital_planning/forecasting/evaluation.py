"""Évaluation chronologique et production d'artefacts de prévision."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from hospital_planning.config.loader import load_hospital_config
from hospital_planning.domain.contracts import HospitalConfig
from hospital_planning.forecasting.baselines import (
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
)
from hospital_planning.forecasting.machine_learning import lagged_regression_forecast
from hospital_planning.forecasting.statistical import exponential_smoothing_forecast

MODEL_NAMES = ("naive", "seasonal_naive", "moving_average", "exponential_smoothing", "lagged_regression")


@dataclass(frozen=True)
class ForecastEvaluationConfig:
    """Paramètres du protocole chronologique, indépendants des données futures."""

    horizon_days: int = 7
    initial_train_days: int = 730
    validation_windows: int = 12
    final_test_days: int = 28
    moving_average_window: int = 7


@dataclass(frozen=True)
class ForecastPipelineResult:
    """Tables finales produites par la phase de prévision."""

    evaluation_predictions: pd.DataFrame
    metrics_by_horizon: pd.DataFrame
    metrics_summary: pd.DataFrame
    model_selection: pd.DataFrame
    forecast_results: pd.DataFrame
    metadata: dict[str, object]


def run_forecasting_pipeline(
    historical_demand: pd.DataFrame,
    hospital_config: HospitalConfig,
    evaluation_config: ForecastEvaluationConfig | None = None,
) -> ForecastPipelineResult:
    """Évalue les cinq modèles, sélectionne par service et prédit J+1 à J+7."""
    config = evaluation_config or ForecastEvaluationConfig(horizon_days=hospital_config.planning_horizon_days)
    _validate_demand(historical_demand)
    demand = historical_demand.copy()
    demand["date"] = pd.to_datetime(demand["date"])
    demand = demand.sort_values(["service", "date"]).reset_index(drop=True)
    service_codes = sorted(demand["service"].unique())
    service_count = len(service_codes)
    series_length = demand.groupby("service").size()
    if series_length.nunique() != 1:
        raise ValueError("Chaque service doit contenir le même nombre d'observations quotidiennes.")
    n_observations = int(series_length.iloc[0])
    validation_origins = _build_origins(n_observations, config, partition="validation")
    final_origins = _build_origins(n_observations, config, partition="test_final")
    holidays = set(hospital_config.synthetic_data.holiday_month_days)

    evaluation_records: list[dict[str, object]] = []
    for service in service_codes:
        service_data = demand[demand["service"] == service].set_index("date")
        series = service_data["admissions"].astype(float)
        for partition, origins in (("validation", validation_origins), ("test_final", final_origins)):
            for origin in origins:
                history = series.iloc[:origin]
                target = series.iloc[origin : origin + config.horizon_days]
                future_dates = target.index
                for model_name in MODEL_NAMES:
                    predictions = _forecast(model_name, history, future_dates, holidays, config)
                    for horizon, (date, actual, prediction) in enumerate(
                        zip(future_dates, target, predictions, strict=True), start=1
                    ):
                        evaluation_records.append(
                            {
                                "partition": partition,
                                "model_name": model_name,
                                "service": service,
                                "origin_date": history.index[-1].date().isoformat(),
                                "date": date.date().isoformat(),
                                "horizon": horizon,
                                "actual": float(actual),
                                "prediction": float(prediction),
                            }
                        )
    evaluation_predictions = pd.DataFrame.from_records(evaluation_records)
    metrics_by_horizon = _calculate_metrics(
        evaluation_predictions,
        ["partition", "model_name", "service", "horizon"],
    )
    metrics_summary = _calculate_metrics(
        evaluation_predictions,
        ["partition", "model_name", "service"],
    )
    selection = _select_models(metrics_summary)
    forecast_results = _generate_final_forecasts(
        demand,
        hospital_config,
        config,
        selection,
        holidays,
    )
    metadata = {
        "forecast_run_id": f"forecast-{demand['date'].max():%Y%m%d}",
        "created_at": datetime.now(UTC).isoformat(),
        "horizon_days": config.horizon_days,
        "validation_origins": len(validation_origins),
        "final_test_origins": len(final_origins),
        "models": list(MODEL_NAMES),
        "services": service_count,
        "demand_config_hash": _config_hash(hospital_config),
    }
    return ForecastPipelineResult(
        evaluation_predictions=evaluation_predictions,
        metrics_by_horizon=metrics_by_horizon,
        metrics_summary=metrics_summary,
        model_selection=selection,
        forecast_results=forecast_results,
        metadata=metadata,
    )


def save_forecast_artifacts(result: ForecastPipelineResult, output_directory: Path) -> dict[str, Path]:
    """Écrit les résultats d'évaluation et les prévisions finales dans des fichiers séparés."""
    output_directory.mkdir(parents=True, exist_ok=True)
    tables = {
        "evaluation_predictions": result.evaluation_predictions,
        "metrics_by_horizon": result.metrics_by_horizon,
        "metrics_summary": result.metrics_summary,
        "model_selection": result.model_selection,
        "forecast_results": result.forecast_results,
    }
    paths: dict[str, Path] = {}
    for name, table in tables.items():
        path = output_directory / f"{name}.csv"
        table.to_csv(path, index=False)
        paths[name] = path
    metadata_path = output_directory / "metadata.json"
    metadata_path.write_text(json.dumps(result.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["metadata"] = metadata_path
    return paths


def _forecast(
    model_name: str,
    history: pd.Series,
    future_dates: pd.DatetimeIndex,
    holidays: set[str],
    config: ForecastEvaluationConfig,
) -> np.ndarray:
    if model_name == "naive":
        prediction = naive_forecast(history, len(future_dates))
    elif model_name == "seasonal_naive":
        prediction = seasonal_naive_forecast(history, len(future_dates))
    elif model_name == "moving_average":
        prediction = moving_average_forecast(history, len(future_dates), config.moving_average_window)
    elif model_name == "exponential_smoothing":
        prediction = exponential_smoothing_forecast(history, len(future_dates))
    elif model_name == "lagged_regression":
        prediction = lagged_regression_forecast(history, future_dates, holidays)
    else:
        raise ValueError(f"Modèle de prévision inconnu : {model_name}")
    if not np.isfinite(prediction).all():
        raise ValueError(f"Le modèle {model_name} a produit une prévision non finie.")
    return np.maximum(prediction, 0.0)


def _build_origins(
    n_observations: int,
    config: ForecastEvaluationConfig,
    *,
    partition: str,
) -> list[int]:
    final_start = n_observations - config.final_test_days
    if config.initial_train_days < 28:
        raise ValueError("La période d'entraînement initiale doit compter au moins 28 jours.")
    if final_start <= config.initial_train_days:
        raise ValueError("L'historique est trop court pour séparer entraînement, validation et test final.")
    if partition == "validation":
        last_origin = final_start - config.horizon_days
        if last_origin < config.initial_train_days:
            raise ValueError("Aucune fenêtre de validation chronologique n'est possible.")
        candidates = np.linspace(config.initial_train_days, last_origin, config.validation_windows, dtype=int)
        return sorted(set(int(origin) for origin in candidates))
    if partition == "test_final":
        origins = list(range(final_start, n_observations - config.horizon_days + 1, config.horizon_days))
        if not origins:
            raise ValueError("La période de test final ne contient pas d'horizon complet.")
        return origins
    raise ValueError(f"Partition inconnue : {partition}")


def _calculate_metrics(predictions: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for keys, group in predictions.groupby(group_columns, sort=True):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        errors = group["prediction"] - group["actual"]
        actual_total = float(group["actual"].sum())
        records.append(
            {
                **dict(zip(group_columns, key_values, strict=True)),
                "observations": len(group),
                "mae": float(errors.abs().mean()),
                "rmse": float(np.sqrt(np.mean(np.square(errors)))),
                "wape": float(errors.abs().sum() / actual_total * 100) if actual_total else np.nan,
                "wape_status": "ok" if actual_total else "zero_actual_total",
                "bias": float(errors.mean()),
            }
        )
    return pd.DataFrame.from_records(records)


def _select_models(metrics_summary: pd.DataFrame) -> pd.DataFrame:
    validation = metrics_summary[metrics_summary["partition"] == "validation"].copy()
    if validation.empty:
        raise ValueError("La sélection exige des métriques de validation.")
    selected = (
        validation.sort_values(["service", "wape", "mae", "model_name"])
        .groupby("service", as_index=False)
        .first()[["service", "model_name", "wape", "mae", "rmse", "bias"]]
        .rename(columns={"model_name": "selected_model", "wape": "validation_wape"})
    )
    return selected


def _generate_final_forecasts(
    demand: pd.DataFrame,
    hospital_config: HospitalConfig,
    config: ForecastEvaluationConfig,
    selection: pd.DataFrame,
    holidays: set[str],
) -> pd.DataFrame:
    run_id = f"forecast-{demand['date'].max():%Y%m%d}"
    created_at = datetime.now(UTC).isoformat()
    selected_models = selection.set_index("service")["selected_model"].to_dict()
    records: list[dict[str, object]] = []
    for service, service_data in demand.groupby("service", sort=True):
        series = service_data.sort_values("date").set_index("date")["admissions"].astype(float)
        first_future_date = series.index[-1] + pd.offsets.Day(1)
        future_dates = pd.date_range(first_future_date, periods=config.horizon_days, freq="D")
        for model_name in MODEL_NAMES:
            predictions = _forecast(model_name, series, future_dates, holidays, config)
            for horizon, (date, prediction) in enumerate(zip(future_dates, predictions, strict=True), start=1):
                records.append(
                    {
                        "forecast_run_id": run_id,
                        "date": date.date().isoformat(),
                        "service": service,
                        "model_name": model_name,
                        "horizon": horizon,
                        "yhat": float(prediction),
                        "selected": model_name == selected_models[service],
                        "origin_date": series.index[-1].date().isoformat(),
                        "created_at": created_at,
                    }
                )
    return pd.DataFrame.from_records(records)


def _validate_demand(demand: pd.DataFrame) -> None:
    required = {"date", "service", "admissions"}
    missing = required - set(demand.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans historical_demand : {sorted(missing)}")
    if demand.duplicated(["date", "service"]).any():
        raise ValueError("historical_demand contient des clés date/service dupliquées.")
    admissions = pd.to_numeric(demand["admissions"], errors="coerce")
    if admissions.isna().any() or (admissions < 0).any():
        raise ValueError("Les admissions doivent être des nombres finis positifs ou nuls.")


def _config_hash(config: HospitalConfig) -> str:
    serialized = json.dumps(config.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def main() -> None:
    """Exécute la phase 3 sur les données synthétiques locales."""
    parser = argparse.ArgumentParser(description="Évalue les modèles de prévision hospitalière.")
    parser.add_argument("--config", type=Path, default=Path("configs/hospital.json"))
    parser.add_argument("--input", type=Path, default=Path("data/synthetic/historical_demand.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/forecasts"))
    arguments = parser.parse_args()
    hospital_config = load_hospital_config(arguments.config)
    demand = pd.read_csv(arguments.input, parse_dates=["date"])
    result = run_forecasting_pipeline(demand, hospital_config)
    save_forecast_artifacts(result, arguments.output)


if __name__ == "__main__":
    main()

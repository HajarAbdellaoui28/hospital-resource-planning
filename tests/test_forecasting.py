"""Tests de la phase 3 : prévisions et validation chronologique."""

import numpy as np
import pandas as pd

from hospital_planning.data.generator import generate_synthetic_dataset
from hospital_planning.domain.contracts import HospitalConfig
from hospital_planning.forecasting.baselines import (
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
)
from hospital_planning.forecasting.evaluation import (
    ForecastEvaluationConfig,
    _calculate_metrics,
    run_forecasting_pipeline,
    save_forecast_artifacts,
)


def test_baselines_have_documented_multi_step_behavior() -> None:
    history = pd.Series([1, 2, 3, 4, 5, 6, 7], dtype=float)

    np.testing.assert_array_equal(naive_forecast(history, 3), [7, 7, 7])
    np.testing.assert_array_equal(seasonal_naive_forecast(history, 3), [1, 2, 3])
    np.testing.assert_allclose(moving_average_forecast(history, 2, window=2), [6.5, 6.75])


def test_pipeline_is_chronological_and_produces_finite_forecasts(
    hospital_config: HospitalConfig,
) -> None:
    raw_config = hospital_config.model_dump()
    raw_config["historical_days"] = 100
    config = HospitalConfig.model_validate(raw_config)
    demand = generate_synthetic_dataset(config).historical_demand
    evaluation_config = ForecastEvaluationConfig(
        initial_train_days=56,
        validation_windows=2,
        final_test_days=14,
        horizon_days=7,
    )

    result = run_forecasting_pipeline(demand, config, evaluation_config)

    assert len(result.model_selection) == 4
    assert len(result.forecast_results) == 4 * 5 * 7
    assert np.isfinite(result.forecast_results["yhat"]).all()
    evaluated_dates = pd.to_datetime(result.evaluation_predictions["date"])
    origin_dates = pd.to_datetime(result.evaluation_predictions["origin_date"])
    assert (evaluated_dates > origin_dates).all()
    test_dates = result.evaluation_predictions.loc[result.evaluation_predictions["partition"] == "test_final", "date"]
    validation_dates = result.evaluation_predictions.loc[
        result.evaluation_predictions["partition"] == "validation", "date"
    ]
    assert pd.to_datetime(validation_dates).max() < pd.to_datetime(test_dates).min()


def test_wape_has_explicit_status_when_actual_total_is_zero() -> None:
    predictions = pd.DataFrame(
        {
            "partition": ["validation", "validation"],
            "model_name": ["naive", "naive"],
            "service": ["REA", "REA"],
            "actual": [0.0, 0.0],
            "prediction": [1.0, 2.0],
        }
    )

    metrics = _calculate_metrics(predictions, ["partition", "model_name", "service"])

    assert metrics.loc[0, "wape_status"] == "zero_actual_total"
    assert np.isnan(metrics.loc[0, "wape"])


def test_final_test_values_do_not_change_validation_selection(hospital_config: HospitalConfig) -> None:
    raw_config = hospital_config.model_dump()
    raw_config["historical_days"] = 100
    config = HospitalConfig.model_validate(raw_config)
    demand = generate_synthetic_dataset(config).historical_demand
    evaluation_config = ForecastEvaluationConfig(
        initial_train_days=56,
        validation_windows=2,
        final_test_days=14,
        horizon_days=7,
    )
    baseline = run_forecasting_pipeline(demand, config, evaluation_config)
    changed_test = demand.copy()
    final_dates = sorted(changed_test["date"].unique())[-14:]
    changed_test.loc[changed_test["date"].isin(final_dates), "admissions"] += 10_000
    changed = run_forecasting_pipeline(changed_test, config, evaluation_config)

    pd.testing.assert_frame_equal(baseline.model_selection, changed.model_selection)


def test_forecast_artifacts_are_exported(hospital_config: HospitalConfig, tmp_path) -> None:
    raw_config = hospital_config.model_dump()
    raw_config["historical_days"] = 90
    config = HospitalConfig.model_validate(raw_config)
    result = run_forecasting_pipeline(
        generate_synthetic_dataset(config).historical_demand,
        config,
        ForecastEvaluationConfig(initial_train_days=49, validation_windows=2, final_test_days=14),
    )

    paths = save_forecast_artifacts(result, tmp_path)

    assert {"forecast_results", "metrics_summary", "metadata"} <= set(paths)
    assert all(path.exists() for path in paths.values())

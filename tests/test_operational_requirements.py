"""Tests de traduction des prévisions en besoins opérationnels."""

from datetime import date

import pandas as pd

from hospital_planning.domain.contracts import HospitalConfig
from hospital_planning.operational.requirements import (
    _build_staff_requirements,
    _config_hash,
    _simulate_future_occupancy,
    build_operational_instance,
    save_operational_instance,
)


def test_future_occupancy_preserves_historical_cohorts(hospital_config: HospitalConfig) -> None:
    dates = pd.to_datetime(["2025-01-01", "2025-01-02"])
    history = pd.DataFrame(
        [
            {"date": day, "service": service, "admissions": admissions}
            for service in hospital_config.services
            for day, admissions in zip(dates, [5, 4] if service == "URG" else [0, 0], strict=True)
        ]
    )
    demand = pd.DataFrame(
        [
            {"date": day, "service": service, "requested_admissions": admissions}
            for service in hospital_config.services
            for day, admissions in zip(
                pd.to_datetime(["2025-01-03", "2025-01-04"]),
                [2, 3] if service == "URG" else [0, 0],
                strict=True,
            )
        ]
    )

    beds = _simulate_future_occupancy(demand, history, hospital_config)
    urgent = beds[beds["service"] == "URG"].reset_index(drop=True)

    assert urgent.loc[0, ["occupancy_start", "expected_discharges", "occupancy_required"]].tolist() == [9, 5, 6]
    assert urgent.loc[1, ["occupancy_start", "expected_discharges", "occupancy_required"]].tolist() == [6, 4, 5]
    assert (
        urgent["occupancy_start"] - urgent["expected_discharges"] + urgent["requested_admissions"]
        == urgent["occupancy_required"]
    ).all()


def test_staff_requirement_rounds_up_from_beds(hospital_config: HospitalConfig) -> None:
    beds = pd.DataFrame([{"date": pd.Timestamp("2025-01-03"), "service": "URG", "beds_required": 11}])

    requirements = _build_staff_requirements(beds, hospital_config)

    by_role = requirements.set_index("role")["required_staff"].to_dict()
    assert by_role == {"PHYSICIAN": 2, "NURSE": 3, "CARE_ASSISTANT": 2}


def test_operational_instance_is_canonical_and_exportable(
    hospital_config: HospitalConfig,
    tmp_path,
) -> None:
    history_dates = pd.date_range("2025-01-01", periods=10, freq="D")
    history = pd.DataFrame(
        [
            {"date": day, "service": service, "admissions": 2}
            for service in hospital_config.services
            for day in history_dates
        ]
    )
    origin_date = history_dates[-1]
    forecast_dates = pd.date_range(origin_date + pd.offsets.Day(1), periods=7, freq="D")
    forecasts = pd.DataFrame(
        [
            {
                "forecast_run_id": "forecast-test",
                "origin_date": origin_date.date().isoformat(),
                "date": day.date().isoformat(),
                "service": service,
                "model_name": "lagged_regression",
                "horizon": horizon,
                "yhat": 2.1,
                "selected": "true",
            }
            for service in hospital_config.services
            for horizon, day in enumerate(forecast_dates, start=1)
        ]
    )
    metadata = {
        "forecast_run_id": "forecast-test",
        "horizon_days": 7,
        "demand_config_hash": _config_hash(hospital_config),
    }

    instance = build_operational_instance(
        history,
        forecasts,
        metadata,
        hospital_config,
        forecast_artifact_path="results/forecasts/forecast_results.csv",
    )
    paths = save_operational_instance(instance, tmp_path)

    assert len(instance.demand_requirements) == 28
    assert len(instance.bed_requirements) == 28
    assert len(instance.staff_requirements) == 28 * 3 * 3
    assert instance.reference.forecast.origin_date == date(2025, 1, 10)
    assert all(path.exists() for path in paths.values())

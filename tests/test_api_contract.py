"""Tests contractuels de l'API applicative, sans démarrer de serveur réseau."""

import json
from datetime import UTC, datetime
from threading import Event

import pytest
from fastapi import HTTPException

from hospital_planning.api.app import (
    app,
    cors_origins,
    download_experiment_artifact,
    get_dashboard_allocation,
    get_dashboard_exploration,
    get_dashboard_forecasts,
    get_dashboard_operational,
    get_dashboard_scenarios,
    get_experiment,
    get_hospital_config,
    get_job,
    get_sensitivity_manifest,
    health,
    list_experiments,
)
from hospital_planning.api.jobs import JobRegistry


def test_health_endpoint_is_read_only_and_available() -> None:
    assert health() == {"status": "ok"}
    paths = app.openapi()["paths"]
    assert "/health" in paths
    assert "/api/v1/jobs/experiments" in paths
    assert "/api/v1/experiments" in paths
    assert "/api/v1/experiments/{experiment_id}/downloads/{artifact_path}" in paths


def test_cors_is_restricted_to_explicit_nextjs_origins(monkeypatch) -> None:
    monkeypatch.delenv("HOSPITAL_CORS_ORIGINS", raising=False)
    assert cors_origins() == [
        "http://localhost:3011",
        "http://127.0.0.1:3011",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    monkeypatch.setenv("HOSPITAL_CORS_ORIGINS", "*")
    with pytest.raises(ValueError):
        cors_origins()


def test_hospital_config_endpoint_returns_valid_contract(monkeypatch, repository_root) -> None:
    monkeypatch.setenv("HOSPITAL_CONFIG_PATH", str(repository_root / "configs" / "hospital.json"))
    response = get_hospital_config()
    assert response.planning_horizon_days == 7
    assert len(response.services) == 4


def test_unknown_job_is_not_presented_as_completed() -> None:
    with pytest.raises(HTTPException) as error:
        get_job("no-such-job")
    assert error.value.status_code == 404


def test_job_registry_completes_a_single_local_task() -> None:
    completed = Event()
    registry = JobRegistry()
    response = registry.submit(lambda: completed.set() or ["experiment-test"])

    assert completed.wait(timeout=2)
    final_response = registry.get(response.job_id)
    assert final_response is not None
    assert final_response.status.value == "COMPLETED"
    assert final_response.experiment_ids == ["experiment-test"]


def test_experiment_read_endpoints_only_read_stored_artifacts(monkeypatch, tmp_path) -> None:
    experiment_directory = tmp_path / "experiment-s0-test"
    experiment_directory.mkdir()
    metadata = {
        "experiment_id": "experiment-s0-test",
        "created_at": datetime.now(UTC).isoformat(),
        "scenario": {"scenario_id": "S0_BASELINE"},
        "methods": ["greedy"],
        "scenario_input_hash": "a" * 64,
    }
    (experiment_directory / "experiment.json").write_text(json.dumps(metadata), encoding="utf-8")
    (experiment_directory / "metrics.csv").write_text(
        "scenario_id,method_name,status,objective_value\nS0_BASELINE,greedy,FEASIBLE,10\n",
        encoding="utf-8",
    )
    (experiment_directory / "artifact.csv").write_text("value\n1\n", encoding="utf-8")
    monkeypatch.setenv("HOSPITAL_RESULTS_PATH", str(tmp_path))

    summaries = list_experiments()
    detail = get_experiment("experiment-s0-test")
    download = download_experiment_artifact("experiment-s0-test", "artifact.csv")

    assert summaries[0].scenario_id == "S0_BASELINE"
    assert detail["metrics"][0]["method_name"] == "greedy"
    assert download.path.name == "artifact.csv"
    with pytest.raises(HTTPException) as error:
        download_experiment_artifact("experiment-s0-test", "../experiment.json")
    assert error.value.status_code == 404


def test_dashboard_read_contracts_expose_only_persisted_artifacts(monkeypatch, repository_root) -> None:
    monkeypatch.setenv("HOSPITAL_PROJECT_ROOT", str(repository_root))
    scenarios = get_dashboard_scenarios()
    forecasts = get_dashboard_forecasts()
    exploration = get_dashboard_exploration()
    operational = get_dashboard_operational("S0")
    operational_baseline = get_dashboard_operational("S0_BASELINE")
    manifest = get_sensitivity_manifest()
    allocation = get_dashboard_allocation("experiment-s0_baseline-16ecc53da404", "greedy")
    milp_allocation = get_dashboard_allocation("experiment-s1_urgent_peak-73744d59852f", "milp")
    legacy_relative_allocation = get_dashboard_allocation("experiment-s3_staff_absence-2d0da06b3a16", "greedy")

    assert scenarios[1].scenario_id == "S1_URGENT_PEAK"
    assert scenarios[2].demand_multiplier == 1.25
    assert len(forecasts.forecasts) == 140
    assert sum(point.selected for point in forecasts.forecasts) == 28
    assert len(exploration.historical_demand) == 4 * 1095
    assert {point.service for point in exploration.historical_demand} == {"URG", "MED", "REA", "CHI"}
    assert len(operational.demand) == 28
    assert len(operational_baseline.demand) == 28
    assert len(manifest) == 80
    assert sum(point.opened_beds for point in allocation.allocations) == allocation.method_result.beds_opened_total
    assert allocation.method_result.unmet_demand_patient_days == 18
    assert allocation.method_result.rejected_admissions == 4
    assert all(point.occupancy_required is None for point in allocation.allocations)
    assert len(milp_allocation.allocations) == 28
    assert all(point.occupancy_required is not None for point in milp_allocation.allocations)
    assert len(legacy_relative_allocation.allocations) == 28


def test_dashboard_returns_explicit_not_found_when_artifacts_are_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOSPITAL_PROJECT_ROOT", str(tmp_path))
    with pytest.raises(HTTPException) as error:
        get_dashboard_forecasts()
    assert error.value.status_code == 404

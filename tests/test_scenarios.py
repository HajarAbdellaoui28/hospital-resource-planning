"""Tests des scénarios déterministes et de l'orchestration d'expériences."""

import json

import pandas as pd

from hospital_planning.domain.contracts import HospitalConfig
from hospital_planning.experiments.runner import run_experiment, sensitivity_manifest
from hospital_planning.experiments.scenarios import ScenarioDefinition, apply_scenario


def _base_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    demand = pd.DataFrame(
        [
            {"date": "2025-01-01", "service": "URG", "requested_admissions": 10, "source_type": "forecast_selected"},
            {"date": "2025-01-02", "service": "URG", "requested_admissions": 10, "source_type": "forecast_selected"},
        ]
    )
    beds = pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "service": "URG",
                "occupancy_start": 0,
                "expected_discharges": 0,
                "requested_admissions": 10,
                "occupancy_required": 10,
                "beds_required": 10,
                "capacity_available": 75,
                "capacity_gap": 0,
                "capacity_source": "configured_nominal",
            },
            {
                "date": "2025-01-02",
                "service": "URG",
                "occupancy_start": 10,
                "expected_discharges": 0,
                "requested_admissions": 10,
                "occupancy_required": 20,
                "beds_required": 20,
                "capacity_available": 75,
                "capacity_gap": 0,
                "capacity_source": "configured_nominal",
            },
        ]
    )
    availability = pd.DataFrame(
        [
            {"staff_id": staff_id, "date": date, "shift": shift, "available": True, "source_type": "historical"}
            for staff_id in ("PHY-1", "NUR-1", "CAR-1")
            for date in ("2025-01-01", "2025-01-02")
            for shift in ("MORNING", "EVENING", "NIGHT")
        ]
    )
    return demand, beds, availability


def test_scenario_transformations_are_immutable_and_reproducible(hospital_config: HospitalConfig) -> None:
    demand, beds, availability = _base_tables()
    baseline_demand = demand.copy(deep=True)
    baseline_beds = beds.copy(deep=True)
    baseline_availability = availability.copy(deep=True)
    scenario = ScenarioDefinition(
        scenario_id="S4_COMBINED_CRISIS",
        description="Test combiné.",
        demand_multiplier=1.25,
        absence_rate=0.15,
        capacity_reduction=0.10,
    )

    first = apply_scenario(scenario, demand, beds, availability, hospital_config, seed=42)
    second = apply_scenario(scenario, demand, beds, availability, hospital_config, seed=42)

    pd.testing.assert_frame_equal(demand, baseline_demand)
    pd.testing.assert_frame_equal(beds, baseline_beds)
    pd.testing.assert_frame_equal(availability, baseline_availability)
    pd.testing.assert_frame_equal(first.demand_requirements, second.demand_requirements)
    pd.testing.assert_frame_equal(first.bed_requirements, second.bed_requirements)
    pd.testing.assert_frame_equal(first.planning_availability, second.planning_availability)
    assert (first.demand_requirements["requested_admissions"] >= baseline_demand["requested_admissions"]).all()
    assert (first.bed_requirements["capacity_available"] <= baseline_beds["capacity_available"]).all()
    assert (~first.planning_availability["available"] | baseline_availability["available"]).all()


def test_peak_scenario_only_changes_declared_service_and_days(hospital_config: HospitalConfig) -> None:
    demand, beds, availability = _base_tables()
    scenario = ScenarioDefinition(
        scenario_id="S1_URGENT_PEAK",
        description="Pic URG.",
        demand_multiplier=1.0,
        absence_rate=0.0,
        capacity_reduction=0.0,
        service_multipliers={"URG": 1.5},
        peak_days=1,
    )

    transformed = apply_scenario(scenario, demand, beds, availability, hospital_config, seed=42)

    assert transformed.demand_requirements["requested_admissions"].tolist() == [15, 10]
    assert transformed.bed_requirements["occupancy_required"].tolist() == [15, 25]


def test_sensitivity_manifest_contains_80_identifiable_experiments(hospital_config: HospitalConfig) -> None:
    manifest = sensitivity_manifest(hospital_config)

    assert len(manifest) == 80
    assert manifest["scenario_id"].is_unique
    assert manifest["exact_calls"].sum() == 160


def test_experiment_uses_one_scenario_instance_for_greedy(hospital_config: HospitalConfig) -> None:
    staff_records = []
    for role in hospital_config.roles:
        for index in range(3):
            staff_records.append(
                {
                    "staff_id": f"{role[:3]}-{index}",
                    "role": role,
                    "qualified_services": json.dumps(["URG"]),
                    "max_shifts": 5,
                    "active": True,
                }
            )
    staff = pd.DataFrame(staff_records)
    availability = pd.DataFrame(
        [
            {"staff_id": staff_id, "date": "2025-01-01", "shift": shift.code, "available": True}
            for staff_id in staff["staff_id"]
            for shift in hospital_config.shifts
        ]
    )
    demand = pd.DataFrame([{"date": "2025-01-01", "service": "URG", "requested_admissions": 1}])
    beds = pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "service": "URG",
                "occupancy_start": 0,
                "expected_discharges": 0,
                "requested_admissions": 1,
                "occupancy_required": 1,
                "beds_required": 1,
                "capacity_available": 75,
                "capacity_gap": 0,
                "capacity_source": "configured_nominal",
            }
        ]
    )
    definition = ScenarioDefinition(
        scenario_id="S0_BASELINE",
        description="Base.",
        demand_multiplier=1.0,
        absence_rate=0.0,
        capacity_reduction=0.0,
    )
    metadata = {"instance": {"instance_id": "tiny", "scenario_id": "S0", "forecast": {"config_hash": "hash"}}}

    experiment, outputs = run_experiment(
        definition,
        demand,
        beds,
        staff,
        availability,
        availability,
        metadata,
        hospital_config,
        methods=("greedy",),
    )

    assert set(outputs) == {"greedy"}
    assert experiment.metrics.loc[0, "scenario_id"] == "S0_BASELINE"
    assert experiment.method_results[0].validation is not None
    assert experiment.method_results[0].validation.valid

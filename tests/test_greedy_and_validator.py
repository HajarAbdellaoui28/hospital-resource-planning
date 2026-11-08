"""Tests de la baseline gloutonne et de son validateur indépendant."""

import json

import pandas as pd

from hospital_planning.domain.contracts import HospitalConfig
from hospital_planning.optimization.exact import run_cp_sat, run_milp
from hospital_planning.optimization.greedy import run_greedy
from hospital_planning.optimization.validator import validate_solution


def test_validator_detects_unavailable_assignment(hospital_config: HospitalConfig) -> None:
    staff = pd.DataFrame(
        [
            {
                "staff_id": "PHY-001",
                "role": "PHYSICIAN",
                "qualified_services": json.dumps(["URG"]),
                "max_shifts": 5,
            }
        ]
    )
    assignments = pd.DataFrame(
        [{"staff_id": "PHY-001", "date": "2025-01-01", "service": "URG", "shift": "MORNING", "role": "PHYSICIAN"}]
    )
    availability = pd.DataFrame([{"staff_id": "PHY-001", "date": "2025-01-01", "shift": "MORNING", "available": False}])
    beds = pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "service": "URG",
                "occupancy_start": 0,
                "expected_discharges": 0,
                "accepted_admissions": 1,
                "occupancy_end": 1,
                "opened_beds": 1,
                "capacity_available": 75,
            }
        ]
    )

    report, _ = validate_solution(beds, assignments, availability, staff, hospital_config)

    assert not report.valid
    assert report.availability_violations == 1


def test_validator_detects_excessive_consecutive_nights(hospital_config: HospitalConfig) -> None:
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    staff = pd.DataFrame(
        [
            {
                "staff_id": "PHY-001",
                "role": "PHYSICIAN",
                "qualified_services": json.dumps(["URG"]),
                "max_shifts": 5,
            }
        ]
    )
    assignments = pd.DataFrame(
        [
            {"staff_id": "PHY-001", "date": date, "service": "URG", "shift": "NIGHT", "role": "PHYSICIAN"}
            for date in dates
        ]
    )
    availability = pd.DataFrame(
        [{"staff_id": "PHY-001", "date": date, "shift": "NIGHT", "available": True} for date in dates]
    )
    beds = pd.DataFrame(
        [
            {
                "date": date,
                "service": "URG",
                "occupancy_start": 0,
                "expected_discharges": 0,
                "accepted_admissions": 0,
                "occupancy_end": 0,
                "opened_beds": 0,
                "capacity_available": 75,
            }
            for date in dates
        ]
    )

    report, _ = validate_solution(beds, assignments, availability, staff, hospital_config)

    assert not report.valid
    assert report.hard_constraint_violations == 1
    assert any("nuits consécutives" in message for message in report.messages)


def test_greedy_is_deterministic_and_respects_hard_constraints(hospital_config: HospitalConfig) -> None:
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
    history_availability = pd.DataFrame(
        [
            {"staff_id": staff_id, "date": "2025-01-01", "shift": shift.code, "available": True}
            for staff_id in staff["staff_id"]
            for shift in hospital_config.shifts
        ]
    )
    demand = pd.DataFrame([{"date": "2025-01-08", "service": "URG", "requested_admissions": 1}])
    beds = pd.DataFrame(
        [
            {
                "date": "2025-01-08",
                "service": "URG",
                "occupancy_start": 0,
                "expected_discharges": 0,
                "occupancy_required": 1,
                "capacity_available": 75,
            }
        ]
    )
    metadata = {"instance": {"instance_id": "test", "scenario_id": "S0", "forecast": {"config_hash": "hash"}}}

    first = run_greedy(demand, beds, staff, history_availability, metadata, hospital_config)
    second = run_greedy(demand, beds, staff, history_availability, metadata, hospital_config)

    pd.testing.assert_frame_equal(first.bed_allocations, second.bed_allocations)
    pd.testing.assert_frame_equal(first.staff_assignments, second.staff_assignments)
    assert first.method_result.status.value == "FEASIBLE"
    assert first.method_result.validation is not None
    assert first.method_result.validation.hard_constraint_violations == 0
    assert first.method_result.validation.workload_range == 0
    assert first.method_result.objective_components is not None
    assert first.method_result.objective_components.workload_imbalance_cost == 0


def test_exact_solvers_match_on_tiny_instance(hospital_config: HospitalConfig) -> None:
    staff_records = []
    for role in hospital_config.roles:
        for index in range(3):
            staff_records.append(
                {
                    "staff_id": f"{role[:3]}-{index:03}",
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
                "occupancy_required": 1,
                "capacity_available": 75,
            }
        ]
    )
    metadata = {"instance": {"instance_id": "tiny", "scenario_id": "S0", "forecast": {"config_hash": "hash"}}}

    milp = run_milp(demand, beds, staff, availability, metadata, hospital_config)
    cp_sat = run_cp_sat(demand, beds, staff, availability, metadata, hospital_config)

    assert milp.method_result.status.value == "OPTIMAL"
    assert cp_sat.method_result.status.value == "OPTIMAL"
    assert milp.method_result.objective_value == cp_sat.method_result.objective_value == 10.0
    assert milp.method_result.validation is not None and milp.method_result.validation.valid
    assert cp_sat.method_result.validation is not None and cp_sat.method_result.validation.valid

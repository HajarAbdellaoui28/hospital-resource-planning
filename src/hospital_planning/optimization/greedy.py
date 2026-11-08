"""Heuristique gloutonne déterministe sur une instance opérationnelle canonique."""

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from hospital_planning.config.loader import load_hospital_config
from hospital_planning.domain.contracts import HospitalConfig, MethodResult
from hospital_planning.domain.enums import MethodStatus
from hospital_planning.optimization.availability import project_planning_availability
from hospital_planning.optimization.objective import calculate_objective_components, calculate_workload_range
from hospital_planning.optimization.validator import validate_solution


@dataclass(frozen=True)
class GreedyResult:
    """Sorties de la baseline, validées séparément de la logique d'affectation."""

    method_result: MethodResult
    bed_allocations: pd.DataFrame
    staff_assignments: pd.DataFrame
    staff_coverage: pd.DataFrame
    planning_availability: pd.DataFrame


def run_greedy(
    demand_requirements: pd.DataFrame,
    bed_requirements: pd.DataFrame,
    staff: pd.DataFrame,
    historical_availability: pd.DataFrame,
    instance_metadata: dict[str, object],
    config: HospitalConfig,
    planning_availability: pd.DataFrame | None = None,
) -> GreedyResult:
    """Construit une allocation et un planning déterministes sans solveur exact."""
    started_at = datetime.now(UTC)
    bed_allocations = _allocate_beds(demand_requirements, bed_requirements, config)
    if planning_availability is None:
        planning_availability = project_planning_availability(
            staff,
            historical_availability,
            bed_allocations["date"],
            config,
        )
    staff_assignments = _assign_staff_greedily(bed_allocations, staff, planning_availability, config)
    report, coverage = validate_solution(
        bed_allocations,
        staff_assignments,
        planning_availability,
        staff,
        config,
    )
    requested_occupancy = int(bed_requirements["occupancy_required"].sum())
    supported_occupancy = int(bed_allocations["occupancy_end"].sum())
    unmet_patient_days = max(requested_occupancy - supported_occupancy, 0)
    rejected_admissions = int(bed_allocations["rejected_admissions"].sum())
    staff_shortage = int(coverage["target_shortage"].sum())
    workload_range = calculate_workload_range(staff_assignments, staff)
    objective_components = calculate_objective_components(
        int(bed_allocations["opened_beds"].sum()),
        unmet_patient_days,
        staff_shortage,
        workload_range,
        config,
    )
    status = MethodStatus.FEASIBLE if report.valid else MethodStatus.INFEASIBLE
    coverage_rate = supported_occupancy / requested_occupancy if requested_occupancy else 1.0
    instance = instance_metadata["instance"]
    method_result = MethodResult(
        experiment_id=f"greedy-{instance['instance_id']}",
        scenario_id=instance["scenario_id"],
        method_name="greedy",
        status=status,
        runtime_seconds=(datetime.now(UTC) - started_at).total_seconds(),
        objective_value=objective_components.total_cost,
        objective_components=objective_components,
        unmet_demand_patient_days=unmet_patient_days,
        rejected_admissions=rejected_admissions,
        staff_shortage_total=staff_shortage,
        coverage_rate=coverage_rate,
        beds_opened_total=int(bed_allocations["opened_beds"].sum()),
        fairness_metric=float(workload_range),
        seed=config.random_seed,
        config_hash=instance["forecast"]["config_hash"],
        validation=report,
        native_status="GREEDY_COMPLETE" if report.valid else "GREEDY_HARD_CONSTRAINT_FAILURE",
    )
    return GreedyResult(
        method_result=method_result,
        bed_allocations=bed_allocations,
        staff_assignments=staff_assignments,
        staff_coverage=coverage,
        planning_availability=planning_availability,
    )


def save_greedy_result(result: GreedyResult, output_directory: Path) -> dict[str, Path]:
    """Écrit les artefacts bruts de la baseline et son résultat normalisé."""
    output_directory.mkdir(parents=True, exist_ok=True)
    tables = {
        "bed_allocations": result.bed_allocations,
        "staff_assignments": result.staff_assignments,
        "staff_coverage": result.staff_coverage,
        "planning_availability": result.planning_availability,
    }
    paths: dict[str, Path] = {}
    for name, table in tables.items():
        path = output_directory / f"{name}.csv"
        table.to_csv(path, index=False)
        paths[name] = path
    result_path = output_directory / "method_result.json"
    result_with_artifact_paths = result.method_result.model_copy(
        update={
            "assignments_artifact_path": str(paths["staff_assignments"]),
            "allocations_artifact_path": str(paths["bed_allocations"]),
        }
    )
    result_path.write_text(
        result_with_artifact_paths.model_dump_json(indent=2),
        encoding="utf-8",
    )
    paths["method_result"] = result_path
    return paths


def _allocate_beds(
    demand_requirements: pd.DataFrame,
    bed_requirements: pd.DataFrame,
    config: HospitalConfig,
) -> pd.DataFrame:
    demand = demand_requirements[["date", "service", "requested_admissions"]].copy()
    demand["date"] = pd.to_datetime(demand["date"])
    required = bed_requirements[
        ["date", "service", "occupancy_start", "expected_discharges", "capacity_available"]
    ].copy()
    required["date"] = pd.to_datetime(required["date"])
    inputs = demand.merge(required, on=["date", "service"], validate="one_to_one")
    records: list[dict[str, object]] = []
    for service, group in inputs.groupby("service", sort=True):
        rejected_discharges: dict[pd.Timestamp, int] = {}
        census = int(group.sort_values("date")["occupancy_start"].iloc[0])
        length_of_stay = config.services[service].length_of_stay_days
        for row in group.sort_values("date").itertuples(index=False):
            current_date = pd.Timestamp(row.date)
            expected_discharges = max(int(row.expected_discharges) - rejected_discharges.pop(current_date, 0), 0)
            occupancy_start = census
            census -= expected_discharges
            requested = int(row.requested_admissions)
            free_beds = max(int(row.capacity_available) - census, 0)
            accepted = min(requested, free_beds)
            rejected = requested - accepted
            census += accepted
            if rejected:
                discharge_date = current_date + pd.DateOffset(days=length_of_stay)
                rejected_discharges[discharge_date] = rejected_discharges.get(discharge_date, 0) + rejected
            records.append(
                {
                    "date": current_date,
                    "service": service,
                    "occupancy_start": occupancy_start,
                    "expected_discharges": expected_discharges,
                    "requested_admissions": requested,
                    "accepted_admissions": accepted,
                    "rejected_admissions": rejected,
                    "occupancy_end": census,
                    "opened_beds": census,
                    "capacity_available": int(row.capacity_available),
                }
            )
    return pd.DataFrame.from_records(records).sort_values(["date", "service"]).reset_index(drop=True)


def _assign_staff_greedily(
    bed_allocations: pd.DataFrame,
    staff: pd.DataFrame,
    availability: pd.DataFrame,
    config: HospitalConfig,
) -> pd.DataFrame:
    qualifications = staff.set_index("staff_id")["qualified_services"].map(json.loads).to_dict()
    roles = staff.set_index("staff_id")["role"].to_dict()
    max_shifts = staff.set_index("staff_id")["max_shifts"].to_dict()
    priority = {service: config.services[service].priority for service in config.services}
    shift_order = {shift.code: shift.start_hour for shift in config.shifts}
    candidates_by_slot = (
        availability[availability["available"]].groupby(["date", "shift"])["staff_id"].apply(list).to_dict()
    )
    assignment_count: dict[str, int] = {}
    assigned_dates: set[tuple[str, pd.Timestamp]] = set()
    intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    assigned_night_dates: dict[str, set[pd.Timestamp]] = {}
    records: list[dict[str, object]] = []
    ordered_beds = bed_allocations.copy()
    ordered_beds["priority"] = ordered_beds["service"].map(priority)
    slots: list[tuple[object, object, str, int, int]] = []
    for bed in ordered_beds.sort_values(["date", "priority", "service"]).itertuples(index=False):
        for shift in sorted(config.shifts, key=lambda item: shift_order[item.code]):
            for role in config.roles:
                target = _target_staff(int(bed.opened_beds), role, config)
                minimum = config.synthetic_data.minimum_staff_by_role[role] if bed.opened_beds else 0
                slots.append((bed, shift, role, minimum, target))
    for phase in ("minimum", "target"):
        for bed, shift, role, minimum, target in slots:
            needed = minimum if phase == "minimum" else target - minimum
            for _ in range(needed):
                candidate = _first_feasible_candidate(
                    candidates_by_slot.get((pd.Timestamp(bed.date), shift.code), []),
                    role,
                    bed.service,
                    pd.Timestamp(bed.date),
                    shift.code,
                    qualifications,
                    roles,
                    max_shifts,
                    assignment_count,
                    assigned_dates,
                    intervals,
                    assigned_night_dates,
                    config,
                )
                if candidate is None:
                    break
                start, end = _shift_interval(pd.Timestamp(bed.date), shift.code, config)
                assignment_count[candidate] = assignment_count.get(candidate, 0) + 1
                assigned_dates.add((candidate, pd.Timestamp(bed.date)))
                intervals.setdefault(candidate, []).append((start, end))
                if shift.code == "NIGHT":
                    assigned_night_dates.setdefault(candidate, set()).add(pd.Timestamp(bed.date).normalize())
                records.append(
                    {
                        "staff_id": candidate,
                        "date": pd.Timestamp(bed.date),
                        "service": bed.service,
                        "shift": shift.code,
                        "role": role,
                    }
                )
    return pd.DataFrame.from_records(records, columns=["staff_id", "date", "service", "shift", "role"])


def _target_staff(opened_beds: int, role: str, config: HospitalConfig) -> int:
    if not opened_beds:
        return 0
    minimum = config.synthetic_data.minimum_staff_by_role[role]
    per_ten = config.synthetic_data.staff_per_ten_beds[role]
    return max(minimum, -(-opened_beds * per_ten // 10))


def _first_feasible_candidate(
    candidates: list[str],
    role: str,
    service: str,
    date: pd.Timestamp,
    shift_code: str,
    qualifications: dict[str, list[str]],
    roles: dict[str, str],
    max_shifts: dict[str, int],
    assignment_count: dict[str, int],
    assigned_dates: set[tuple[str, pd.Timestamp]],
    intervals: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
    assigned_night_dates: dict[str, set[pd.Timestamp]],
    config: HospitalConfig,
) -> str | None:
    start, end = _shift_interval(date, shift_code, config)
    for staff_id in sorted(candidates):
        if roles[staff_id] != role or service not in qualifications[staff_id]:
            continue
        if (staff_id, date) in assigned_dates or assignment_count.get(staff_id, 0) >= max_shifts[staff_id]:
            continue
        if any(
            _insufficient_rest(start, end, other_start, other_end, config)
            for other_start, other_end in intervals.get(staff_id, [])
        ):
            continue
        if shift_code == "NIGHT" and _would_exceed_consecutive_nights(
            date,
            assigned_night_dates.get(staff_id, set()),
            config.planning_policy.max_consecutive_nights,
        ):
            continue
        return staff_id
    return None


def _shift_interval(date: pd.Timestamp, shift_code: str, config: HospitalConfig) -> tuple[pd.Timestamp, pd.Timestamp]:
    shift = next(shift for shift in config.shifts if shift.code == shift_code)
    start = date.normalize() + timedelta(hours=int(shift.start_hour))
    return start, start + timedelta(hours=int(shift.duration_hours))


def _insufficient_rest(
    start: pd.Timestamp,
    end: pd.Timestamp,
    other_start: pd.Timestamp,
    other_end: pd.Timestamp,
    config: HospitalConfig,
) -> bool:
    if start >= other_end:
        return start - other_end < timedelta(hours=int(config.planning_policy.min_rest_hours))
    if other_start >= end:
        return other_start - end < timedelta(hours=int(config.planning_policy.min_rest_hours))
    return True


def _would_exceed_consecutive_nights(
    date: pd.Timestamp,
    assigned_night_dates: set[pd.Timestamp],
    maximum: int,
) -> bool:
    """Indique si l'ajout d'une nuit crée une séquence au-delà de la limite."""
    candidate_dates = assigned_night_dates | {date.normalize()}
    current_date = date.normalize()
    consecutive_nights = 1
    previous_date = current_date - timedelta(days=1)
    while previous_date in candidate_dates:
        consecutive_nights += 1
        previous_date -= timedelta(days=1)
    next_date = current_date + timedelta(days=1)
    while next_date in candidate_dates:
        consecutive_nights += 1
        next_date += timedelta(days=1)
    return consecutive_nights > maximum


def main() -> None:
    """Exécute l'heuristique sur l'instance S0, sans appeler de solveur."""
    parser = argparse.ArgumentParser(description="Exécute la baseline gloutonne hospitalière.")
    parser.add_argument("--config", type=Path, default=Path("configs/hospital.json"))
    parser.add_argument("--instance", type=Path, default=Path("results/operational_instances/S0"))
    parser.add_argument("--staff", type=Path, default=Path("data/synthetic/staff.csv"))
    parser.add_argument("--availability", type=Path, default=Path("data/synthetic/staff_availability.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/allocations/greedy/S0"))
    arguments = parser.parse_args()
    config = load_hospital_config(arguments.config)
    instance = arguments.instance
    result = run_greedy(
        pd.read_csv(instance / "demand_requirements.csv", parse_dates=["date"]),
        pd.read_csv(instance / "bed_requirements.csv", parse_dates=["date"]),
        pd.read_csv(arguments.staff),
        pd.read_csv(arguments.availability, parse_dates=["date"]),
        json.loads((instance / "operational_instance.json").read_text(encoding="utf-8")),
        config,
    )
    save_greedy_result(result, arguments.output)


if __name__ == "__main__":
    main()

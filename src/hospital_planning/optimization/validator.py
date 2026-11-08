"""Validation indépendante des allocations et affectations retournées."""

import json
from datetime import timedelta

import numpy as np
import pandas as pd

from hospital_planning.domain.contracts import HospitalConfig, ValidationReport


def validate_solution(
    bed_allocations: pd.DataFrame,
    staff_assignments: pd.DataFrame,
    planning_availability: pd.DataFrame,
    staff: pd.DataFrame,
    config: HospitalConfig,
) -> tuple[ValidationReport, pd.DataFrame]:
    """Vérifie les sorties sans réutiliser de contrainte de solveur.

    Le déficit de cible reste séparé des violations dures lorsque la politique
    permissive est active. La table de couverture expose ce déficit par slot.
    """
    messages: list[str] = []
    capacity_violations = _count_capacity_violations(bed_allocations)
    availability_violations = _count_availability_violations(staff_assignments, planning_availability)
    qualification_violations = _count_qualification_violations(staff_assignments, staff)
    double_assignment_violations = _count_double_assignment_violations(staff_assignments)
    max_shift_violations = _count_max_shift_violations(staff_assignments, staff)
    rest_violations = _count_rest_violations(staff_assignments, config)
    consecutive_night_violations = _count_consecutive_night_violations(staff_assignments, config)
    coverage = _build_coverage(bed_allocations, staff_assignments, config)
    minimum_coverage_violations = int((coverage["assigned_staff"] < coverage["minimum_staff"]).sum())
    coverage_deficits = int(coverage["target_shortage"].sum())
    workload_range = _calculate_workload_range(staff_assignments, staff)
    hard_constraint_violations = (
        capacity_violations
        + availability_violations
        + qualification_violations
        + double_assignment_violations
        + max_shift_violations
        + rest_violations
        + consecutive_night_violations
        + minimum_coverage_violations
    )
    if capacity_violations:
        messages.append(f"{capacity_violations} violation(s) de capacité ou de conservation.")
    if availability_violations:
        messages.append(f"{availability_violations} affectation(s) indisponible(s).")
    if qualification_violations:
        messages.append(f"{qualification_violations} affectation(s) non qualifiée(s).")
    if double_assignment_violations:
        messages.append(f"{double_assignment_violations} double(s) affectation(s) journalière(s).")
    if max_shift_violations:
        messages.append(f"{max_shift_violations} dépassement(s) de limite de postes.")
    if rest_violations:
        messages.append(f"{rest_violations} violation(s) de repos minimal.")
    if consecutive_night_violations:
        messages.append(f"{consecutive_night_violations} violation(s) de nuits consécutives.")
    if minimum_coverage_violations:
        messages.append(f"{minimum_coverage_violations} dotation(s) minimale(s) non couverte(s).")
    if coverage_deficits:
        messages.append(f"Déficit cumulé de cible de personnel : {coverage_deficits} poste(s).")
    strict_failure = config.planning_policy.mode.value == "strict" and coverage_deficits > 0
    if strict_failure:
        messages.append("La politique stricte interdit tout déficit de cible.")
    report = ValidationReport(
        valid=hard_constraint_violations == 0 and not strict_failure,
        hard_constraint_violations=hard_constraint_violations,
        capacity_violations=capacity_violations,
        availability_violations=availability_violations,
        qualification_violations=qualification_violations,
        double_assignment_violations=double_assignment_violations,
        coverage_deficits=coverage_deficits,
        workload_range=workload_range,
        messages=messages,
    )
    return report, coverage


def _count_capacity_violations(bed_allocations: pd.DataFrame) -> int:
    required = {
        "occupancy_start",
        "expected_discharges",
        "accepted_admissions",
        "occupancy_end",
        "opened_beds",
        "capacity_available",
    }
    if required - set(bed_allocations):
        return len(bed_allocations)
    conservation = (
        bed_allocations["occupancy_start"]
        - bed_allocations["expected_discharges"]
        + bed_allocations["accepted_admissions"]
        == bed_allocations["occupancy_end"]
    )
    capacity = (
        (bed_allocations["opened_beds"] >= 0)
        & (bed_allocations["opened_beds"] <= bed_allocations["capacity_available"])
        & (bed_allocations["occupancy_end"] <= bed_allocations["opened_beds"])
    )
    return int((~(conservation & capacity)).sum())


def _count_availability_violations(assignments: pd.DataFrame, availability: pd.DataFrame) -> int:
    keys = ["staff_id", "date", "shift"]
    available = availability[keys + ["available"]].copy()
    available["date"] = pd.to_datetime(available["date"])
    assigned = assignments[keys].copy()
    assigned["date"] = pd.to_datetime(assigned["date"])
    merged = assigned.merge(available, on=keys, how="left", validate="many_to_one")
    return int((~merged["available"].fillna(False).astype(bool)).sum())


def _count_qualification_violations(assignments: pd.DataFrame, staff: pd.DataFrame) -> int:
    if assignments.empty:
        return 0
    qualifications = staff[["staff_id", "role", "qualified_services"]].copy()
    qualifications["qualified_services"] = qualifications["qualified_services"].map(json.loads)
    merged = assignments.merge(qualifications, on="staff_id", how="left", validate="many_to_one")
    invalid = merged["role_x"] != merged["role_y"]
    invalid |= merged.apply(
        lambda row: not isinstance(row["qualified_services"], list) or row["service"] not in row["qualified_services"],
        axis=1,
    )
    return int(invalid.sum())


def _count_double_assignment_violations(assignments: pd.DataFrame) -> int:
    if assignments.empty:
        return 0
    counts = assignments.groupby(["staff_id", "date"]).size()
    return int((counts - 1).clip(lower=0).sum())


def _count_max_shift_violations(assignments: pd.DataFrame, staff: pd.DataFrame) -> int:
    if assignments.empty:
        return 0
    limits = staff.set_index("staff_id")["max_shifts"]
    counts = assignments.groupby("staff_id").size()
    return int(sum(max(int(count) - int(limits[staff_id]), 0) for staff_id, count in counts.items()))


def _count_rest_violations(assignments: pd.DataFrame, config: HospitalConfig) -> int:
    if assignments.empty:
        return 0
    shifts = {shift.code: shift for shift in config.shifts}
    violations = 0
    for _, group in assignments.groupby("staff_id"):
        intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        for row in group.itertuples(index=False):
            shift = shifts[row.shift]
            start = pd.Timestamp(row.date).normalize() + timedelta(hours=int(shift.start_hour))
            end = start + timedelta(hours=int(shift.duration_hours))
            intervals.append((start, end))
        intervals.sort()
        for (_, previous_end), (next_start, _) in zip(intervals, intervals[1:], strict=False):
            if next_start - previous_end < timedelta(hours=int(config.planning_policy.min_rest_hours)):
                violations += 1
    return violations


def _count_consecutive_night_violations(assignments: pd.DataFrame, config: HospitalConfig) -> int:
    """Compte les nuits au-delà de la limite dans chaque séquence individuelle."""
    if assignments.empty:
        return 0
    night_assignments = assignments[assignments["shift"] == "NIGHT"].copy()
    night_assignments["date"] = pd.to_datetime(night_assignments["date"]).dt.normalize()
    violations = 0
    for _, group in night_assignments.groupby("staff_id"):
        previous_date: pd.Timestamp | None = None
        consecutive_nights = 0
        for current_date in sorted(group["date"].unique()):
            current_timestamp = pd.Timestamp(current_date)
            if previous_date is not None and current_timestamp - previous_date == timedelta(days=1):
                consecutive_nights += 1
            else:
                consecutive_nights = 1
            if consecutive_nights > config.planning_policy.max_consecutive_nights:
                violations += 1
            previous_date = current_timestamp
    return violations


def _calculate_workload_range(assignments: pd.DataFrame, staff: pd.DataFrame) -> int:
    """Recalcule l'étendue de charge, en incluant les actifs sans affectation."""
    active_mask = staff["active"] if "active" in staff else pd.Series(True, index=staff.index)
    active_staff = staff.loc[active_mask, ["staff_id", "role"]].copy()
    if active_staff.empty:
        return 0
    assignment_counts = assignments.groupby("staff_id").size().rename("assigned_shifts")
    active_staff = active_staff.join(assignment_counts, on="staff_id")
    active_staff["assigned_shifts"] = active_staff["assigned_shifts"].fillna(0).astype(int)
    ranges = active_staff.groupby("role")["assigned_shifts"].agg(lambda values: int(values.max() - values.min()))
    return int(ranges.sum())


def _build_coverage(
    bed_allocations: pd.DataFrame,
    assignments: pd.DataFrame,
    config: HospitalConfig,
) -> pd.DataFrame:
    assigned = assignments.groupby(["date", "service", "shift", "role"]).size().rename("assigned_staff")
    records: list[dict[str, object]] = []
    for bed in bed_allocations.itertuples(index=False):
        for shift in config.shifts:
            for role in config.roles:
                minimum = config.synthetic_data.minimum_staff_by_role[role] if bed.opened_beds else 0
                per_ten = config.synthetic_data.staff_per_ten_beds[role]
                target = max(minimum, int(np.ceil(bed.opened_beds * per_ten / 10))) if bed.opened_beds else 0
                key = (pd.Timestamp(bed.date), bed.service, shift.code, role)
                assigned_count = int(assigned.get(key, 0))
                records.append(
                    {
                        "date": pd.Timestamp(bed.date),
                        "service": bed.service,
                        "shift": shift.code,
                        "role": role,
                        "opened_beds": int(bed.opened_beds),
                        "minimum_staff": minimum,
                        "target_staff": target,
                        "assigned_staff": assigned_count,
                        "target_shortage": max(target - assigned_count, 0),
                    }
                )
    return pd.DataFrame.from_records(records).sort_values(["date", "service", "shift", "role"]).reset_index(drop=True)

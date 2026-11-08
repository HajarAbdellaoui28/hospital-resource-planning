"""Objectif canonique partagé par les méthodes de planification."""

import pandas as pd

from hospital_planning.domain.contracts import HospitalConfig, ObjectiveComponents


def calculate_workload_range(staff_assignments: pd.DataFrame, staff: pd.DataFrame) -> int:
    """Calcule la somme des étendues de charge par rôle parmi les actifs.

    Les groupes comparables sont les professionnels actifs ayant le même rôle.
    Les professionnels sans affectation restent dans leur groupe avec une charge
    nulle : les exclure masquerait un déséquilibre réel.
    """
    active_mask = staff["active"] if "active" in staff else pd.Series(True, index=staff.index)
    active_staff = staff.loc[active_mask, ["staff_id", "role"]].copy()
    if active_staff.empty:
        return 0
    assignment_counts = staff_assignments.groupby("staff_id").size().rename("assigned_shifts")
    active_staff = active_staff.join(assignment_counts, on="staff_id")
    active_staff["assigned_shifts"] = active_staff["assigned_shifts"].fillna(0).astype(int)
    ranges = active_staff.groupby("role")["assigned_shifts"].agg(lambda values: int(values.max() - values.min()))
    return int(ranges.sum())


def calculate_objective_components(
    opened_beds_total: int,
    unmet_patient_days: int,
    staff_target_shortage: int,
    workload_range: int,
    config: HospitalConfig,
) -> ObjectiveComponents:
    """Applique une seule fois les coefficients entiers configurés."""
    opened_bed_cost = opened_beds_total * config.objective_weights.opened_bed
    unmet_cost = unmet_patient_days * config.objective_weights.unmet_patient_day
    shortage_cost = staff_target_shortage * config.objective_weights.staff_target_shortage
    imbalance_cost = workload_range * config.objective_weights.workload_imbalance
    return ObjectiveComponents(
        opened_bed_cost=float(opened_bed_cost),
        unmet_patient_day_cost=float(unmet_cost),
        staff_target_shortage_cost=float(shortage_cost),
        workload_imbalance_cost=float(imbalance_cost),
        total_cost=float(opened_bed_cost + unmet_cost + shortage_cost + imbalance_cost),
    )

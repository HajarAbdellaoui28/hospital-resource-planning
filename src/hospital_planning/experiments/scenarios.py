"""Transformations déterministes, explicites et non mutantes des scénarios."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from hospital_planning.domain.contracts import HospitalConfig


class ScenarioDefinition(BaseModel):
    """Hypothèses d'un scénario de stress test synthétique."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    scenario_id: str = Field(pattern=r"^(S[0-9]_[A-Z_]+|SENS_[A-Z0-9_]+)$")
    description: str = Field(min_length=1)
    demand_multiplier: float = Field(ge=1)
    absence_rate: float = Field(ge=0, le=1)
    capacity_reduction: float = Field(ge=0, lt=1)
    service_multipliers: dict[str, float] = Field(default_factory=dict)
    peak_days: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_peak(self) -> "ScenarioDefinition":
        if self.service_multipliers and self.peak_days is None:
            raise ValueError("peak_days est requis lorsqu'un multiplicateur par service est défini.")
        if self.peak_days is not None and not self.service_multipliers:
            raise ValueError("peak_days ne peut être défini sans multiplicateur par service.")
        return self


@dataclass(frozen=True)
class ScenarioInstance:
    """Entrées résultantes, séparées de l'instance de référence non modifiée."""

    definition: ScenarioDefinition
    demand_requirements: pd.DataFrame
    bed_requirements: pd.DataFrame
    planning_availability: pd.DataFrame
    seed: int
    input_hash: str


def load_scenarios(path: Path, config: HospitalConfig) -> list[ScenarioDefinition]:
    """Charge les scénarios déclaratifs et vérifie les services référencés."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenarios = [ScenarioDefinition.model_validate(item) for item in raw["scenarios"]]
    identifiers = [scenario.scenario_id for scenario in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Les identifiants de scénario doivent être uniques.")
    for scenario in scenarios:
        unknown = set(scenario.service_multipliers) - set(config.services)
        if unknown:
            raise ValueError(f"Services inconnus dans {scenario.scenario_id}: {sorted(unknown)}")
    return scenarios


def apply_scenario(
    definition: ScenarioDefinition,
    demand_requirements: pd.DataFrame,
    bed_requirements: pd.DataFrame,
    planning_availability: pd.DataFrame,
    config: HospitalConfig,
    *,
    seed: int,
) -> ScenarioInstance:
    """Crée une instance scénario reproductible sans modifier les tables sources."""
    demand = demand_requirements.copy(deep=True)
    beds = bed_requirements.copy(deep=True)
    availability = planning_availability.copy(deep=True)
    demand["date"] = pd.to_datetime(demand["date"])
    beds["date"] = pd.to_datetime(beds["date"])
    availability["date"] = pd.to_datetime(availability["date"])
    _apply_demand_multiplier(demand, definition)
    _rebuild_bed_requirements(demand, beds, definition.capacity_reduction, config)
    _apply_absences(availability, definition.absence_rate, seed)
    input_hash = _scenario_hash(definition, demand, beds, availability, seed)
    return ScenarioInstance(definition, demand, beds, availability, seed, input_hash)


def sensitivity_definitions() -> list[ScenarioDefinition]:
    """Retourne les 80 combinaisons absence × demande × capacité requises."""
    definitions = []
    for absence_rate in (0.0, 0.05, 0.10, 0.15, 0.20):
        for demand_multiplier in (1.00, 1.25, 1.50, 2.00):
            for capacity_reduction in (0.0, 0.05, 0.10, 0.20):
                absence_code = int(absence_rate * 100)
                demand_code = int(demand_multiplier * 100)
                capacity_code = int(capacity_reduction * 100)
                scenario_id = f"SENS_A{absence_code:02}_D{demand_code:03}_C{capacity_code:02}"
                definitions.append(
                    ScenarioDefinition(
                        scenario_id=scenario_id,
                        description="Combinaison de sensibilité synthétique.",
                        demand_multiplier=demand_multiplier,
                        absence_rate=absence_rate,
                        capacity_reduction=capacity_reduction,
                    )
                )
    return definitions


def _apply_demand_multiplier(demand: pd.DataFrame, definition: ScenarioDefinition) -> None:
    multipliers = pd.Series(definition.demand_multiplier, index=demand.index, dtype=float)
    if definition.service_multipliers:
        first_dates = sorted(demand["date"].unique())[: definition.peak_days]
        peak_mask = demand["date"].isin(first_dates)
        for service, multiplier in definition.service_multipliers.items():
            multipliers.loc[peak_mask & demand["service"].eq(service)] *= multiplier
    demand["scenario_multiplier"] = multipliers
    demand["requested_admissions"] = np.ceil(demand["requested_admissions"] * multipliers).astype(int)
    demand["source_type"] = "scenario_transformed"


def _rebuild_bed_requirements(
    demand: pd.DataFrame,
    beds: pd.DataFrame,
    capacity_reduction: float,
    config: HospitalConfig,
) -> None:
    demand_by_key = demand.set_index(["service", "date"])["requested_admissions"]
    for service, group in beds.groupby("service", sort=False):
        ordered = group.sort_values("date")
        length_of_stay = config.services[service].length_of_stay_days
        baseline_discharges = ordered.set_index("date")["expected_discharges"].to_dict()
        baseline_demand = ordered.set_index("date")["requested_admissions"].to_dict()
        census = int(ordered.iloc[0]["occupancy_start"])
        scenario_demand: dict[pd.Timestamp, int] = {}
        for row in ordered.itertuples(index=False):
            date = pd.Timestamp(row.date)
            shifted_date = date - pd.DateOffset(days=length_of_stay)
            changed_discharge = scenario_demand.get(
                shifted_date, baseline_demand.get(shifted_date, 0)
            ) - baseline_demand.get(shifted_date, 0)
            discharges = max(int(baseline_discharges[date]) + changed_discharge, 0)
            admissions = int(demand_by_key[(service, date)])
            capacity = int(np.floor(int(row.capacity_available) * (1 - capacity_reduction)))
            row_mask = beds["service"].eq(service) & beds["date"].eq(date)
            beds.loc[row_mask, "occupancy_start"] = census
            beds.loc[row_mask, "expected_discharges"] = discharges
            beds.loc[row_mask, "requested_admissions"] = admissions
            census = census - discharges + admissions
            beds.loc[row_mask, "occupancy_required"] = census
            beds.loc[row_mask, "beds_required"] = census
            beds.loc[row_mask, "capacity_available"] = capacity
            beds.loc[row_mask, "capacity_gap"] = max(census - capacity, 0)
            beds.loc[row_mask, "capacity_source"] = "scenario_capacity"
            scenario_demand[date] = admissions


def _apply_absences(availability: pd.DataFrame, absence_rate: float, seed: int) -> None:
    availability["scenario_absence"] = False
    if absence_rate == 0:
        return
    eligible_staff = np.sort(availability.loc[availability["available"], "staff_id"].unique())
    count = int(np.floor(len(eligible_staff) * absence_rate))
    rng = np.random.default_rng(seed)
    selected_staff = rng.choice(eligible_staff, size=count, replace=False)
    selected_mask = availability["staff_id"].isin(selected_staff) & availability["available"]
    availability.loc[selected_mask, "available"] = False
    availability.loc[selected_mask, "scenario_absence"] = True
    availability.loc[selected_mask, "source_type"] = "scenario_additional_absence"


def _scenario_hash(
    definition: ScenarioDefinition,
    demand: pd.DataFrame,
    beds: pd.DataFrame,
    availability: pd.DataFrame,
    seed: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(definition.model_dump_json().encode("utf-8"))
    digest.update(str(seed).encode("utf-8"))
    for table in (demand, beds, availability):
        digest.update(table.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"))
    return digest.hexdigest()

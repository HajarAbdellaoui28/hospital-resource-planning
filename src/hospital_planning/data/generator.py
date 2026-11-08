"""Génération reproductible de données hospitalières exclusivement synthétiques."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from hospital_planning.config.loader import load_hospital_config
from hospital_planning.data.occupancy import simulate_occupancy
from hospital_planning.domain.contracts import HospitalConfig


@dataclass(frozen=True)
class SyntheticDataset:
    """Ensemble cohérent des tables produites par la phase 2."""

    historical_demand: pd.DataFrame
    bed_capacity: pd.DataFrame
    occupancy: pd.DataFrame
    staff: pd.DataFrame
    staff_availability: pd.DataFrame
    staff_requirements: pd.DataFrame

    def tables(self) -> dict[str, pd.DataFrame]:
        """Retourne les tables selon leurs noms de fichier contractuels."""
        return {
            "historical_demand": self.historical_demand,
            "bed_capacity": self.bed_capacity,
            "occupancy": self.occupancy,
            "staff": self.staff,
            "staff_availability": self.staff_availability,
            "staff_requirements": self.staff_requirements,
        }


def generate_synthetic_dataset(config: HospitalConfig) -> SyntheticDataset:
    """Génère toutes les tables synthétiques avec une graine NumPy dédiée."""
    rng = np.random.default_rng(config.random_seed)
    dates = pd.date_range(
        config.synthetic_data.start_date,
        periods=config.historical_days,
        freq="D",
    )
    special_events = {date: bool(rng.random() < config.synthetic_data.special_event_probability) for date in dates}
    holidays = {value for value in config.synthetic_data.holiday_month_days}

    bed_capacity = _generate_bed_capacity(config, dates, rng)
    historical_demand = _generate_historical_demand(
        config,
        dates,
        special_events,
        holidays,
        rng,
    )
    occupancy = simulate_occupancy(
        historical_demand,
        bed_capacity,
        {code: service.length_of_stay_days for code, service in config.services.items()},
    )
    historical_demand = historical_demand.drop(columns="discharges").merge(
        occupancy[["date", "service", "discharges"]],
        on=["date", "service"],
        validate="one_to_one",
    )
    historical_demand = (
        historical_demand[
            [
                "date",
                "service",
                "admissions",
                "discharges",
                "emergency_arrivals",
                "is_holiday",
                "is_special_event",
                "data_source",
            ]
        ]
        .sort_values(["date", "service"])
        .reset_index(drop=True)
    )
    staff = _generate_staff(config)
    staff_availability = _generate_staff_availability(config, staff, dates, rng)
    staff_requirements = _generate_staff_requirements(config, bed_capacity)
    return SyntheticDataset(
        historical_demand=historical_demand,
        bed_capacity=bed_capacity,
        occupancy=occupancy,
        staff=staff,
        staff_availability=staff_availability,
        staff_requirements=staff_requirements,
    )


def _generate_historical_demand(
    config: HospitalConfig,
    dates: pd.DatetimeIndex,
    special_events: dict[pd.Timestamp, bool],
    holidays: set[str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for service_code, service in config.services.items():
        for day_index, current_date in enumerate(dates):
            is_special_event = special_events[current_date]
            rate = (
                service.base_daily_admissions
                + service.weekday_effects[current_date.weekday()]
                + (service.trend_per_day * day_index)
                + (service.special_event_effect if is_special_event else 0)
            )
            admissions = int(rng.poisson(max(rate, 0.1)))
            emergency_arrivals: int | None
            if service_code == "URG":
                emergency_arrivals = admissions + int(rng.poisson(max(admissions * 0.2, 0.1)))
            else:
                emergency_arrivals = None
            records.append(
                {
                    "date": current_date,
                    "service": service_code,
                    "admissions": admissions,
                    "discharges": 0,
                    "emergency_arrivals": emergency_arrivals,
                    "is_holiday": current_date.strftime("%m-%d") in holidays,
                    "is_special_event": is_special_event,
                    "data_source": "synthetic",
                }
            )
    return pd.DataFrame.from_records(records).sort_values(["date", "service"]).reset_index(drop=True)


def _generate_bed_capacity(
    config: HospitalConfig,
    dates: pd.DatetimeIndex,
    rng: np.random.Generator,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for service_code, service in config.services.items():
        maximum_closure = int(np.floor(service.beds_total * config.synthetic_data.max_bed_closure_fraction))
        for current_date in dates:
            beds_unavailable = 0
            if maximum_closure and rng.random() < config.synthetic_data.bed_closure_probability:
                beds_unavailable = int(rng.integers(1, maximum_closure + 1))
            records.append(
                {
                    "date": current_date,
                    "service": service_code,
                    "beds_total": service.beds_total,
                    "beds_unavailable": beds_unavailable,
                    "beds_operational": service.beds_total - beds_unavailable,
                }
            )
    return pd.DataFrame.from_records(records).sort_values(["date", "service"]).reset_index(drop=True)


def _generate_staff(config: HospitalConfig) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    service_codes = sorted(config.services)
    for role, count in config.synthetic_data.staff_by_role.items():
        for index in range(1, count + 1):
            qualification_count = 1 + ((index - 1) % min(2, len(service_codes)))
            start_index = (index - 1) % len(service_codes)
            qualified_services = [
                service_codes[(start_index + offset) % len(service_codes)] for offset in range(qualification_count)
            ]
            records.append(
                {
                    "staff_id": f"{role[:3]}-{index:03d}",
                    "role": role,
                    "qualified_services": json.dumps(qualified_services),
                    "contracted_hours": config.synthetic_data.contracted_hours,
                    "max_shifts": config.synthetic_data.max_shifts,
                    "active": True,
                }
            )
    return pd.DataFrame.from_records(records).sort_values("staff_id").reset_index(drop=True)


def _generate_staff_availability(
    config: HospitalConfig,
    staff: pd.DataFrame,
    dates: pd.DatetimeIndex,
    rng: np.random.Generator,
) -> pd.DataFrame:
    staff_ids = staff["staff_id"].to_numpy()
    shifts = [shift.code for shift in config.shifts]
    index = pd.MultiIndex.from_product(
        [staff_ids, dates, shifts],
        names=["staff_id", "date", "shift"],
    )
    total = len(index)
    available = rng.random(total) >= config.synthetic_data.absence_probability
    return pd.DataFrame(
        {
            "staff_id": index.get_level_values("staff_id"),
            "date": index.get_level_values("date"),
            "shift": index.get_level_values("shift"),
            "available": available,
            "absence_type": np.where(available, None, "SYNTHETIC_ABSENCE"),
        }
    )


def _generate_staff_requirements(config: HospitalConfig, bed_capacity: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in bed_capacity.itertuples(index=False):
        for shift in config.shifts:
            for role in config.roles:
                per_ten = config.synthetic_data.staff_per_ten_beds[role]
                minimum = config.synthetic_data.minimum_staff_by_role[role]
                required_staff = max(minimum, int(np.ceil(row.beds_operational * per_ten / 10)))
                records.append(
                    {
                        "date": row.date,
                        "service": row.service,
                        "shift": shift.code,
                        "role": role,
                        "required_staff": required_staff,
                        "source_type": "synthetic_assumption",
                    }
                )
    return pd.DataFrame.from_records(records).sort_values(["date", "service", "shift", "role"]).reset_index(drop=True)


def save_synthetic_dataset(dataset: SyntheticDataset, output_directory: Path) -> dict[str, Path]:
    """Écrit les tables en CSV avec dates ISO et renvoie leurs chemins."""
    output_directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for table_name, table in dataset.tables().items():
        path = output_directory / f"{table_name}.csv"
        table.to_csv(path, index=False, date_format="%Y-%m-%d")
        paths[table_name] = path
    return paths


def main() -> None:
    """Point d'entrée CLI de génération, sans étape de prévision ou d'optimisation."""
    parser = argparse.ArgumentParser(description="Génère les données hospitalières synthétiques.")
    parser.add_argument("--config", type=Path, default=Path("configs/hospital.json"))
    parser.add_argument("--output", type=Path, default=Path("data/synthetic"))
    arguments = parser.parse_args()
    config = load_hospital_config(arguments.config)
    dataset = generate_synthetic_dataset(config)
    save_synthetic_dataset(dataset, arguments.output)
    from hospital_planning.data.validation import validate_synthetic_dataset

    report = validate_synthetic_dataset(dataset, config)
    (arguments.output / "quality_report.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

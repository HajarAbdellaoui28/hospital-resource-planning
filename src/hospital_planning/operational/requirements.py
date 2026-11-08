"""Construction d'une instance opérationnelle canonique à partir des prévisions."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from hospital_planning.config.loader import load_hospital_config
from hospital_planning.domain.contracts import (
    ForecastReference,
    HospitalConfig,
    PlanningInstanceReference,
)


@dataclass(frozen=True)
class OperationalInstance:
    """Entrées canoniques partagées par les futurs planificateurs."""

    reference: PlanningInstanceReference
    demand_requirements: pd.DataFrame
    bed_requirements: pd.DataFrame
    staff_requirements: pd.DataFrame
    metadata: dict[str, object]


def build_operational_instance(
    historical_demand: pd.DataFrame,
    forecast_results: pd.DataFrame,
    forecast_metadata: dict[str, object],
    hospital_config: HospitalConfig,
    *,
    forecast_artifact_path: str,
    scenario_id: str = "S0",
) -> OperationalInstance:
    """Traduit les prévisions retenues en demandes, lits et personnel cibles.

    Cette fonction ne choisit ni les admissions acceptées, ni les lits ouverts, ni les
    affectations. Elle conserve donc les écarts de capacité comme exigences à traiter
    par les phases d'allocation et de planification.
    """
    selected_forecasts = _select_and_validate_forecasts(forecast_results, hospital_config)
    _validate_forecast_metadata(selected_forecasts, forecast_metadata, hospital_config)
    history = _prepare_history(historical_demand, hospital_config)
    demand_requirements = _build_demand_requirements(selected_forecasts)
    bed_requirements = _simulate_future_occupancy(demand_requirements, history, hospital_config)
    staff_requirements = _build_staff_requirements(bed_requirements, hospital_config)
    input_hash = _input_hash(demand_requirements, bed_requirements, staff_requirements, hospital_config)
    forecast_reference = ForecastReference(
        forecast_run_id=str(forecast_metadata["forecast_run_id"]),
        origin_date=pd.Timestamp(selected_forecasts["origin_date"].iloc[0]).date(),
        horizon_days=hospital_config.planning_horizon_days,
        artifact_path=forecast_artifact_path,
        config_hash=str(forecast_metadata["demand_config_hash"]),
    )
    instance_id = f"instance-{forecast_reference.forecast_run_id.lower()}-{scenario_id.lower()}"
    reference = PlanningInstanceReference(
        instance_id=instance_id,
        scenario_id=scenario_id,
        forecast=forecast_reference,
        input_hash=input_hash,
        created_at=datetime.now(UTC),
    )
    metadata = {
        "instance": reference.model_dump(mode="json"),
        "units": {
            "yhat": "patients/jour (continu)",
            "requested_admissions": "patients/jour (entier, plafond de yhat)",
            "occupancy_required": "patients ou lits occupés en fin de journée",
            "beds_required": "lits/jour",
            "capacity_gap": "lits/jour",
            "required_staff": "professionnels/poste",
        },
        "capacity_assumption": (
            "Les capacités futures utilisent beds_total configuré ; les fermetures "
            "aléatoires ne sont pas connues à l'avance."
        ),
        "conversion_assumption": "requested_admissions = ceil(yhat), borné à zéro.",
    }
    return OperationalInstance(
        reference=reference,
        demand_requirements=demand_requirements,
        bed_requirements=bed_requirements,
        staff_requirements=staff_requirements,
        metadata=metadata,
    )


def save_operational_instance(instance: OperationalInstance, output_directory: Path) -> dict[str, Path]:
    """Écrit l'instance immuable dans des artefacts distincts et lisibles."""
    output_directory.mkdir(parents=True, exist_ok=True)
    tables = {
        "demand_requirements": instance.demand_requirements,
        "bed_requirements": instance.bed_requirements,
        "staff_requirements": instance.staff_requirements,
    }
    paths: dict[str, Path] = {}
    for name, table in tables.items():
        path = output_directory / f"{name}.csv"
        table.to_csv(path, index=False)
        paths[name] = path
    metadata_path = output_directory / "operational_instance.json"
    metadata_path.write_text(json.dumps(instance.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["metadata"] = metadata_path
    return paths


def _select_and_validate_forecasts(
    forecast_results: pd.DataFrame,
    config: HospitalConfig,
) -> pd.DataFrame:
    required_columns = {"date", "service", "model_name", "horizon", "yhat", "selected", "origin_date"}
    missing = required_columns - set(forecast_results.columns)
    if missing:
        raise ValueError(f"Colonnes de prévision manquantes : {sorted(missing)}")
    selected_mask = forecast_results["selected"].astype(str).str.lower().eq("true")
    selected = forecast_results[selected_mask].copy()
    selected["date"] = pd.to_datetime(selected["date"])
    selected["origin_date"] = pd.to_datetime(selected["origin_date"])
    selected["yhat"] = pd.to_numeric(selected["yhat"], errors="coerce")
    if selected.empty or selected["yhat"].isna().any() or (selected["yhat"] < 0).any():
        raise ValueError("Les prévisions sélectionnées doivent être finies et non négatives.")
    expected_rows = len(config.services) * config.planning_horizon_days
    if len(selected) != expected_rows or selected.duplicated(["date", "service"]).any():
        raise ValueError("Une prévision retenue unique est requise par service et par jour de l'horizon.")
    if set(selected["service"]) != set(config.services):
        raise ValueError("Les services des prévisions retenues ne correspondent pas à la configuration.")
    for service, group in selected.groupby("service"):
        first_forecast_date = group["origin_date"].iloc[0] + pd.offsets.Day(1)
        expected_dates = pd.date_range(
            first_forecast_date,
            periods=config.planning_horizon_days,
            freq="D",
        )
        if not group.sort_values("date")["date"].reset_index(drop=True).equals(pd.Series(expected_dates)):
            raise ValueError(f"L'horizon de prévision de {service} est incomplet ou non consécutif.")
    return selected.sort_values(["date", "service"]).reset_index(drop=True)


def _validate_forecast_metadata(
    selected_forecasts: pd.DataFrame,
    metadata: dict[str, object],
    config: HospitalConfig,
) -> None:
    required = {"forecast_run_id", "horizon_days", "demand_config_hash"}
    missing = required - set(metadata)
    if missing:
        raise ValueError(f"Métadonnées de prévision incomplètes : {sorted(missing)}")
    if int(metadata["horizon_days"]) != config.planning_horizon_days:
        raise ValueError("L'horizon des métadonnées ne correspond pas à la configuration.")
    if selected_forecasts.get("forecast_run_id") is not None:
        run_ids = set(selected_forecasts["forecast_run_id"])
        if run_ids != {metadata["forecast_run_id"]}:
            raise ValueError("Les prévisions retenues et leurs métadonnées proviennent de runs différents.")
    if str(metadata["demand_config_hash"]) != _config_hash(config):
        raise ValueError("L'empreinte de configuration des prévisions ne correspond pas à la configuration active.")


def _prepare_history(historical_demand: pd.DataFrame, config: HospitalConfig) -> pd.DataFrame:
    required_columns = {"date", "service", "admissions"}
    missing = required_columns - set(historical_demand.columns)
    if missing:
        raise ValueError(f"Colonnes historiques manquantes : {sorted(missing)}")
    history = historical_demand.copy()
    history["date"] = pd.to_datetime(history["date"])
    history["admissions"] = pd.to_numeric(history["admissions"], errors="coerce")
    if history["admissions"].isna().any() or (history["admissions"] < 0).any():
        raise ValueError("Les admissions historiques doivent être non négatives.")
    if history.duplicated(["date", "service"]).any() or set(history["service"]) != set(config.services):
        raise ValueError("L'historique doit contenir une clé date/service unique pour chaque service configuré.")
    return history.sort_values(["date", "service"]).reset_index(drop=True)


def _build_demand_requirements(selected_forecasts: pd.DataFrame) -> pd.DataFrame:
    demand = selected_forecasts[["date", "service", "model_name", "horizon", "yhat"]].copy()
    demand["requested_admissions"] = np.ceil(demand["yhat"]).astype(int)
    demand["source_type"] = "forecast_selected"
    return demand.sort_values(["date", "service"]).reset_index(drop=True)


def _simulate_future_occupancy(
    demand_requirements: pd.DataFrame,
    history: pd.DataFrame,
    config: HospitalConfig,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for service_code, service in config.services.items():
        service_demand = demand_requirements[demand_requirements["service"] == service_code].sort_values("date")
        first_date = pd.Timestamp(service_demand["date"].iloc[0])
        service_history = history[history["service"] == service_code]
        cohorts = _remaining_cohorts(
            service_history,
            first_date,
            service.length_of_stay_days,
        )
        census = sum(cohorts.values())
        for row in service_demand.itertuples(index=False):
            current_date = pd.Timestamp(row.date)
            occupancy_start = census
            discharges = cohorts.pop(current_date, 0)
            census -= discharges
            admissions = int(row.requested_admissions)
            census += admissions
            cohorts[current_date + pd.DateOffset(days=service.length_of_stay_days)] = admissions
            capacity_available = service.beds_total
            records.append(
                {
                    "date": current_date,
                    "service": service_code,
                    "occupancy_start": occupancy_start,
                    "expected_discharges": discharges,
                    "requested_admissions": admissions,
                    "occupancy_required": census,
                    "beds_required": census,
                    "capacity_available": capacity_available,
                    "capacity_gap": max(census - capacity_available, 0),
                    "capacity_source": "configured_nominal",
                }
            )
    return pd.DataFrame.from_records(records).sort_values(["date", "service"]).reset_index(drop=True)


def _remaining_cohorts(
    history: pd.DataFrame,
    first_forecast_date: pd.Timestamp,
    length_of_stay: int,
) -> dict[pd.Timestamp, int]:
    """Reconstruit les cohortes historiques encore présentes au début de l'horizon."""
    cohorts: dict[pd.Timestamp, int] = {}
    for row in history.itertuples(index=False):
        admission_date = pd.Timestamp(row.date)
        discharge_date = admission_date + pd.DateOffset(days=length_of_stay)
        if discharge_date >= first_forecast_date:
            cohorts[discharge_date] = cohorts.get(discharge_date, 0) + int(row.admissions)
    return cohorts


def _build_staff_requirements(bed_requirements: pd.DataFrame, config: HospitalConfig) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in bed_requirements.itertuples(index=False):
        for shift in config.shifts:
            for role in config.roles:
                per_ten_beds = config.synthetic_data.staff_per_ten_beds[role]
                minimum = config.synthetic_data.minimum_staff_by_role[role]
                required_staff = max(minimum, int(np.ceil(row.beds_required * per_ten_beds / 10)))
                records.append(
                    {
                        "date": row.date,
                        "service": row.service,
                        "shift": shift.code,
                        "role": role,
                        "required_staff": required_staff,
                        "source_type": "forecasted_occupancy",
                    }
                )
    return pd.DataFrame.from_records(records).sort_values(["date", "service", "shift", "role"]).reset_index(drop=True)


def _input_hash(
    demand_requirements: pd.DataFrame,
    bed_requirements: pd.DataFrame,
    staff_requirements: pd.DataFrame,
    config: HospitalConfig,
) -> str:
    digest = hashlib.sha256()
    for table in (demand_requirements, bed_requirements, staff_requirements):
        digest.update(table.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"))
    digest.update(_config_hash(config).encode("utf-8"))
    return digest.hexdigest()


def _config_hash(config: HospitalConfig) -> str:
    serialized = json.dumps(config.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def main() -> None:
    """Construit l'instance opérationnelle S0 sans exécuter de planificateur."""
    parser = argparse.ArgumentParser(description="Traduit les prévisions en besoins opérationnels.")
    parser.add_argument("--config", type=Path, default=Path("configs/hospital.json"))
    parser.add_argument("--history", type=Path, default=Path("data/synthetic/historical_demand.csv"))
    parser.add_argument("--forecasts", type=Path, default=Path("results/forecasts/forecast_results.csv"))
    parser.add_argument("--forecast-metadata", type=Path, default=Path("results/forecasts/metadata.json"))
    parser.add_argument("--output", type=Path, default=Path("results/operational_instances/S0"))
    arguments = parser.parse_args()
    config = load_hospital_config(arguments.config)
    instance = build_operational_instance(
        pd.read_csv(arguments.history, parse_dates=["date"]),
        pd.read_csv(arguments.forecasts),
        json.loads(arguments.forecast_metadata.read_text(encoding="utf-8")),
        config,
        forecast_artifact_path=str(arguments.forecasts),
    )
    save_operational_instance(instance, arguments.output)


if __name__ == "__main__":
    main()

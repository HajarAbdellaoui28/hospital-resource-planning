"""Validation explicite des jeux de données synthétiques."""

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass

import pandas as pd

from hospital_planning.data.generator import SyntheticDataset
from hospital_planning.domain.contracts import HospitalConfig


@dataclass(frozen=True)
class ValidationIssue:
    """Anomalie trouvée par les contrôles indépendants de la génération."""

    table: str
    code: str
    message: str


@dataclass(frozen=True)
class QualityReport:
    """Rapport de qualité sérialisable, sans correction silencieuse des données."""

    valid: bool
    row_counts: dict[str, int]
    date_min: str | None
    date_max: str | None
    missing_values: dict[str, int]
    duplicate_rows: dict[str, int]
    service_statistics: dict[str, dict[str, float]]
    invalid_value_count: int
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, object]:
        """Retourne une structure compatible JSON."""
        result = asdict(self)
        result["issues"] = [asdict(issue) for issue in self.issues]
        return result


class DataValidationError(ValueError):
    """Levée lorsque les données synthétiques violent un invariant requis."""


def validate_synthetic_dataset(
    dataset: SyntheticDataset,
    config: HospitalConfig,
    *,
    raise_on_error: bool = True,
) -> QualityReport:
    """Valide les tables produites contre les invariants du cahier des charges."""
    issues: list[ValidationIssue] = []
    service_codes = set(config.services)
    expected_dates = pd.date_range(
        config.synthetic_data.start_date,
        periods=config.historical_days,
        freq="D",
    )
    _validate_date_service_table(
        dataset.historical_demand,
        "historical_demand",
        expected_dates,
        service_codes,
        issues,
    )
    _validate_date_service_table(
        dataset.bed_capacity,
        "bed_capacity",
        expected_dates,
        service_codes,
        issues,
    )
    _validate_date_service_table(
        dataset.occupancy,
        "occupancy",
        expected_dates,
        service_codes,
        issues,
    )
    _validate_non_negative(
        dataset.historical_demand,
        "historical_demand",
        ["admissions", "discharges", "emergency_arrivals"],
        issues,
    )
    _validate_non_negative(
        dataset.bed_capacity,
        "bed_capacity",
        ["beds_total", "beds_unavailable", "beds_operational"],
        issues,
    )
    _validate_non_negative(
        dataset.occupancy,
        "occupancy",
        ["occupancy_start", "admissions", "discharges", "occupancy_end", "overflow"],
        issues,
    )
    _validate_capacity(dataset.bed_capacity, issues)
    _validate_occupancy(dataset.occupancy, dataset.historical_demand, issues)
    _validate_staff(dataset, config, expected_dates, issues)
    _validate_variability(dataset.historical_demand, issues)
    report = _build_quality_report(dataset, issues)
    if raise_on_error and not report.valid:
        messages = "; ".join(issue.message for issue in report.issues)
        raise DataValidationError(messages)
    return report


def _validate_date_service_table(
    table: pd.DataFrame,
    table_name: str,
    expected_dates: pd.DatetimeIndex,
    service_codes: set[str],
    issues: list[ValidationIssue],
) -> None:
    duplicate_count = int(table.duplicated(["date", "service"]).sum())
    if duplicate_count:
        issues.append(ValidationIssue(table_name, "duplicate_key", f"{duplicate_count} clés date/service dupliquées."))
    actual_dates = pd.DatetimeIndex(pd.to_datetime(table["date"]).unique()).sort_values()
    if not actual_dates.equals(expected_dates):
        issues.append(ValidationIssue(table_name, "date_gap", "Les dates ne couvrent pas l'intervalle attendu."))
    unknown_services = set(table["service"].unique()) - service_codes
    if unknown_services:
        issues.append(ValidationIssue(table_name, "unknown_service", f"Services inconnus: {sorted(unknown_services)}."))


def _validate_non_negative(
    table: pd.DataFrame,
    table_name: str,
    columns: Iterable[str],
    issues: list[ValidationIssue],
) -> None:
    for column in columns:
        values = pd.to_numeric(table[column], errors="coerce")
        invalid_count = int((values.dropna() < 0).sum())
        if invalid_count:
            issues.append(
                ValidationIssue(table_name, "negative_value", f"{column}: {invalid_count} valeurs négatives.")
            )


def _validate_capacity(table: pd.DataFrame, issues: list[ValidationIssue]) -> None:
    invalid = (table["beds_unavailable"] > table["beds_total"]) | (
        table["beds_operational"] != table["beds_total"] - table["beds_unavailable"]
    )
    if int(invalid.sum()):
        issues.append(ValidationIssue("bed_capacity", "capacity_invariant", "Capacité de lits incohérente."))


def _validate_occupancy(
    occupancy: pd.DataFrame,
    demand: pd.DataFrame,
    issues: list[ValidationIssue],
) -> None:
    conservation = occupancy["occupancy_start"] + occupancy["admissions"] - occupancy["discharges"]
    if not (conservation == occupancy["occupancy_end"]).all():
        issues.append(ValidationIssue("occupancy", "conservation", "La conservation de l'occupation est violée."))
    merged = occupancy.merge(
        demand[["date", "service", "admissions", "discharges"]],
        on=["date", "service"],
        suffixes=("_occupancy", "_demand"),
        validate="one_to_one",
    )
    if not (
        (merged["admissions_occupancy"] == merged["admissions_demand"])
        & (merged["discharges_occupancy"] == merged["discharges_demand"])
    ).all():
        issues.append(ValidationIssue("occupancy", "demand_mismatch", "Admissions ou sorties incohérentes."))


def _validate_staff(
    dataset: SyntheticDataset,
    config: HospitalConfig,
    expected_dates: pd.DatetimeIndex,
    issues: list[ValidationIssue],
) -> None:
    staff = dataset.staff
    if int(staff["staff_id"].duplicated().sum()):
        issues.append(ValidationIssue("staff", "duplicate_staff_id", "Identifiants de personnel dupliqués."))
    staff_ids = set(staff["staff_id"])
    for qualified_services in staff["qualified_services"]:
        try:
            unknown = set(json.loads(qualified_services)) - set(config.services)
        except (TypeError, json.JSONDecodeError):
            issues.append(ValidationIssue("staff", "invalid_qualifications", "Qualifications non sérialisables."))
            break
        if unknown:
            issues.append(ValidationIssue("staff", "unknown_qualification", "Qualification vers un service inconnu."))
            break
    availability = dataset.staff_availability
    if set(availability["staff_id"]) - staff_ids:
        issues.append(
            ValidationIssue("staff_availability", "unknown_staff", "Disponibilité pour un personnel inconnu.")
        )
    duplicate_count = int(availability.duplicated(["staff_id", "date", "shift"]).sum())
    if duplicate_count:
        issues.append(ValidationIssue("staff_availability", "duplicate_key", "Disponibilités dupliquées."))
    expected_count = len(staff) * len(expected_dates) * len(config.shifts)
    if len(availability) != expected_count:
        issues.append(
            ValidationIssue(
                "staff_availability",
                "incomplete_availability",
                "Grille de disponibilité incomplète.",
            )
        )
    invalid_absence = availability[availability["available"] & availability["absence_type"].notna()]
    if not invalid_absence.empty:
        issues.append(ValidationIssue("staff_availability", "absence_inconsistent", "Absence sur disponibilité vraie."))


def _validate_variability(demand: pd.DataFrame, issues: list[ValidationIssue]) -> None:
    distinct_values = demand.groupby("service")["admissions"].nunique()
    if (distinct_values <= 1).any():
        issues.append(ValidationIssue("historical_demand", "no_variability", "Variabilité insuffisante par service."))


def _build_quality_report(dataset: SyntheticDataset, issues: list[ValidationIssue]) -> QualityReport:
    tables = dataset.tables()
    demand = dataset.historical_demand
    service_statistics = {
        service: {
            "admissions_mean": float(group["admissions"].mean()),
            "admissions_std": float(group["admissions"].std(ddof=0)),
        }
        for service, group in demand.groupby("service", sort=True)
    }
    missing_values = {name: int(table.isna().sum().sum()) for name, table in tables.items()}
    duplicate_rows = {name: int(table.duplicated().sum()) for name, table in tables.items()}
    all_dates = pd.to_datetime(demand["date"])
    invalid_value_count = len(issues)
    return QualityReport(
        valid=not issues,
        row_counts={name: len(table) for name, table in tables.items()},
        date_min=all_dates.min().strftime("%Y-%m-%d") if not all_dates.empty else None,
        date_max=all_dates.max().strftime("%Y-%m-%d") if not all_dates.empty else None,
        missing_values=missing_values,
        duplicate_rows=duplicate_rows,
        service_statistics=service_statistics,
        invalid_value_count=invalid_value_count,
        issues=tuple(issues),
    )

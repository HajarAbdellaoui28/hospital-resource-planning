"""Projection déterministe et partagée des disponibilités de planification."""

import pandas as pd

from hospital_planning.domain.contracts import HospitalConfig


def project_planning_availability(
    staff: pd.DataFrame,
    historical_availability: pd.DataFrame,
    planning_dates: pd.Series,
    config: HospitalConfig,
) -> pd.DataFrame:
    """Projette le dernier profil observé pour le même jour de semaine et poste."""
    active_staff = staff[staff["active"]].copy()
    availability = historical_availability.copy()
    availability["date"] = pd.to_datetime(availability["date"])
    dates = sorted(pd.to_datetime(planning_dates.unique()))
    records: list[dict[str, object]] = []
    for target_date in dates:
        for shift in config.shifts:
            source_date = availability.loc[
                (availability["date"].dt.weekday == target_date.weekday()) & (availability["shift"] == shift.code),
                "date",
            ].max()
            source = availability[(availability["date"] == source_date) & (availability["shift"] == shift.code)]
            source_by_staff = source.set_index("staff_id")
            for staff_id in active_staff["staff_id"]:
                source_row = source_by_staff.loc[staff_id]
                records.append(
                    {
                        "staff_id": staff_id,
                        "date": target_date,
                        "shift": shift.code,
                        "available": bool(source_row["available"]),
                        "source_date": source_date,
                        "source_type": "last_observed_weekday_pattern",
                    }
                )
    return pd.DataFrame.from_records(records)

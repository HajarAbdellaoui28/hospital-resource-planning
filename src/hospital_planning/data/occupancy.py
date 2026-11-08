"""Simulation agrégée de l'occupation hospitalière."""

from collections import defaultdict

import pandas as pd


def simulate_occupancy(
    historical_demand: pd.DataFrame,
    bed_capacity: pd.DataFrame,
    length_of_stay_by_service: dict[str, int],
) -> pd.DataFrame:
    """Construit une occupation par cohortes sans supprimer les dépassements.

    Les sorties sont appliquées avant les admissions. Les admissions restent présentes
    jusqu'à la date de sortie déterminée par la durée synthétique du service.
    """
    capacity_lookup = bed_capacity.set_index(["date", "service"])["beds_operational"]
    records: list[dict[str, object]] = []

    for service, service_demand in historical_demand.groupby("service", sort=True):
        cohorts: dict[pd.Timestamp, int] = defaultdict(int)
        census = 0
        length_of_stay = length_of_stay_by_service[service]
        for row in service_demand.sort_values("date").itertuples(index=False):
            current_date = pd.Timestamp(row.date)
            occupancy_start = census
            discharges = cohorts.pop(current_date, 0)
            census -= discharges
            admissions = int(row.admissions)
            census += admissions
            discharge_date = current_date + pd.DateOffset(days=int(length_of_stay))
            cohorts[discharge_date] += admissions
            beds_operational = int(capacity_lookup.loc[(current_date, service)])
            records.append(
                {
                    "date": current_date,
                    "service": service,
                    "occupancy_start": occupancy_start,
                    "admissions": admissions,
                    "discharges": discharges,
                    "occupancy_end": census,
                    "overflow": max(census - beds_operational, 0),
                }
            )

    return pd.DataFrame.from_records(records).sort_values(["date", "service"]).reset_index(drop=True)

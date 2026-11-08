"""Tests de conservation de l'occupation simulée."""

from hospital_planning.data.generator import generate_synthetic_dataset
from hospital_planning.domain.contracts import HospitalConfig


def test_occupancy_conserves_patients_and_tracks_overflow(hospital_config: HospitalConfig) -> None:
    config = hospital_config.model_copy(update={"historical_days": 40})
    dataset = generate_synthetic_dataset(config)
    occupancy = dataset.occupancy
    capacity = dataset.bed_capacity.rename(columns={"beds_operational": "capacity"})
    merged = occupancy.merge(capacity[["date", "service", "capacity"]], on=["date", "service"])

    assert (merged["occupancy_start"] + merged["admissions"] - merged["discharges"] == merged["occupancy_end"]).all()
    assert (merged["overflow"] == (merged["occupancy_end"] - merged["capacity"]).clip(lower=0)).all()

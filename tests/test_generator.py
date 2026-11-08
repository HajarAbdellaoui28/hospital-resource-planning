"""Tests de génération synthétique reproductible."""

import pandas as pd

from hospital_planning.data.generator import generate_synthetic_dataset, save_synthetic_dataset
from hospital_planning.data.validation import validate_synthetic_dataset
from hospital_planning.domain.contracts import HospitalConfig


def test_generation_is_reproducible_for_same_configuration(hospital_config: HospitalConfig) -> None:
    config = hospital_config.model_copy(update={"historical_days": 30})
    first = generate_synthetic_dataset(config)
    second = generate_synthetic_dataset(config)

    for table_name, first_table in first.tables().items():
        pd.testing.assert_frame_equal(first_table, second.tables()[table_name])


def test_generated_dataset_is_complete_and_valid(hospital_config: HospitalConfig) -> None:
    config = hospital_config.model_copy(update={"historical_days": 30})
    dataset = generate_synthetic_dataset(config)
    report = validate_synthetic_dataset(dataset, config)

    assert report.valid
    assert report.date_min == "2023-01-01"
    assert report.date_max == "2023-01-30"
    assert report.row_counts["historical_demand"] == 30 * 4
    assert report.row_counts["staff_requirements"] == 30 * 4 * 3 * 3


def test_generated_tables_can_be_exported(hospital_config: HospitalConfig, tmp_path) -> None:
    config = hospital_config.model_copy(update={"historical_days": 10})
    paths = save_synthetic_dataset(generate_synthetic_dataset(config), tmp_path)

    assert set(paths) == {
        "historical_demand",
        "bed_capacity",
        "occupancy",
        "staff",
        "staff_availability",
        "staff_requirements",
    }
    assert all(path.exists() for path in paths.values())

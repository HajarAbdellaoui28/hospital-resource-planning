"""Tests des contrôles de qualité indépendants."""

from dataclasses import replace

from hospital_planning.data.generator import generate_synthetic_dataset
from hospital_planning.data.validation import validate_synthetic_dataset
from hospital_planning.domain.contracts import HospitalConfig


def test_validation_reports_capacity_invariant_violation(hospital_config: HospitalConfig) -> None:
    config = hospital_config.model_copy(update={"historical_days": 14})
    dataset = generate_synthetic_dataset(config)
    corrupted_capacity = dataset.bed_capacity.copy()
    corrupted_capacity.loc[0, "beds_operational"] += 1
    corrupted_dataset = replace(dataset, bed_capacity=corrupted_capacity)

    report = validate_synthetic_dataset(corrupted_dataset, config, raise_on_error=False)

    assert not report.valid
    assert any(issue.code == "capacity_invariant" for issue in report.issues)

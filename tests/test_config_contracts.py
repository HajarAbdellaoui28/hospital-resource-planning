"""Tests des contrats de configuration de la phase 1."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hospital_planning.domain.contracts import HospitalConfig


def test_default_hospital_config_has_expected_capacity(hospital_config: HospitalConfig) -> None:
    assert hospital_config.planning_horizon_days == 7
    assert sum(service.beds_total for service in hospital_config.services.values()) == 300
    assert set(hospital_config.services) == {"URG", "MED", "REA", "CHI"}


def test_config_round_trip_is_stable(hospital_config: HospitalConfig) -> None:
    restored = HospitalConfig.model_validate_json(hospital_config.model_dump_json())
    assert restored == hospital_config


def test_duplicate_shift_codes_are_rejected(hospital_config: HospitalConfig) -> None:
    invalid = deepcopy(hospital_config.model_dump())
    invalid["shifts"][1]["code"] = invalid["shifts"][0]["code"]
    with pytest.raises(ValidationError, match="codes de poste"):
        HospitalConfig.model_validate(invalid)


def test_unknown_configuration_fields_are_rejected(hospital_config: HospitalConfig) -> None:
    invalid = hospital_config.model_dump()
    invalid["unexpected"] = True
    with pytest.raises(ValidationError):
        HospitalConfig.model_validate(invalid)


def test_synthetic_role_mappings_must_cover_all_roles(hospital_config: HospitalConfig) -> None:
    invalid = hospital_config.model_dump()
    missing_role = hospital_config.roles[-1]
    del invalid["synthetic_data"]["staff_per_ten_beds"][missing_role]
    with pytest.raises(ValidationError, match="ne définit pas les rôles"):
        HospitalConfig.model_validate(invalid)

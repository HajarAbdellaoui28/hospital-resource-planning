"""Chargement strict des fichiers JSON de configuration."""

import json
from pathlib import Path

from hospital_planning.domain.contracts import HospitalConfig


def load_hospital_config(path: Path) -> HospitalConfig:
    """Charge une configuration hospitalière et échoue pour toute incohérence."""
    with path.open(encoding="utf-8") as config_file:
        raw_config = json.load(config_file)
    return HospitalConfig.model_validate(raw_config)

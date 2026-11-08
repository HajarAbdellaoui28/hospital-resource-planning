"""Fixtures partagées de la phase 1."""

from pathlib import Path

import pytest

from hospital_planning.config.loader import load_hospital_config
from hospital_planning.domain.contracts import HospitalConfig


@pytest.fixture
def repository_root() -> Path:
    """Retourne la racine du dépôt, indépendamment du répertoire courant."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def hospital_config(repository_root: Path) -> HospitalConfig:
    """Charge la configuration de référence validée."""
    return load_hospital_config(repository_root / "configs" / "hospital.json")

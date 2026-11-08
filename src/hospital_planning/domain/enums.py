"""Énumérations stables des contrats métier."""

from enum import StrEnum


class MethodStatus(StrEnum):
    """Statut normalisé d'une méthode de planification."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class JobStatus(StrEnum):
    """État de cycle de vie d'une exécution applicative."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class PlanningPolicyMode(StrEnum):
    """Politique de couverture autorisée par le modèle."""

    SHORTAGE_PERMITTING = "shortage_permitting"
    STRICT = "strict"

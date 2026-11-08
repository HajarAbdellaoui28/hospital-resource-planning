"""Schémas Pydantic constituant les contrats de la phase 1."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hospital_planning.domain.enums import JobStatus, MethodStatus, PlanningPolicyMode

PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class ServiceConfig(BaseModel):
    """Hypothèses synthétiques associées à un service."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    beds_total: PositiveInt
    base_daily_admissions: NonNegativeFloat
    priority: NonNegativeInt
    weekday_effects: list[float] = Field(min_length=7, max_length=7)
    trend_per_day: float = 0.0
    special_event_effect: float = 0.0
    length_of_stay_days: PositiveInt


class SyntheticDataConfig(BaseModel):
    """Hypothèses explicites de la simulation de données synthétiques."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    start_date: date
    special_event_probability: Annotated[float, Field(ge=0, le=1)]
    holiday_month_days: list[str] = Field(default_factory=list)
    bed_closure_probability: Annotated[float, Field(ge=0, le=1)]
    max_bed_closure_fraction: Annotated[float, Field(ge=0, le=1)]
    absence_probability: Annotated[float, Field(ge=0, le=1)]
    staff_by_role: dict[str, PositiveInt] = Field(min_length=1)
    contracted_hours: PositiveInt
    max_shifts: PositiveInt
    staff_per_ten_beds: dict[str, NonNegativeInt] = Field(min_length=1)
    minimum_staff_by_role: dict[str, NonNegativeInt] = Field(min_length=1)


class ShiftConfig(BaseModel):
    """Définition contractuelle d'un poste de travail."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str = Field(pattern=r"^[A-Z_]+$")
    start_hour: Annotated[int, Field(ge=0, lt=24)]
    duration_hours: Annotated[int, Field(gt=0, le=24)]


class PlanningPolicyConfig(BaseModel):
    """Règles de planification configurables et synthétiques."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: PlanningPolicyMode = PlanningPolicyMode.SHORTAGE_PERMITTING
    min_rest_hours: Annotated[int, Field(ge=0, le=24)]
    max_consecutive_nights: PositiveInt
    solver_time_limit_seconds: PositiveInt
    solver_num_workers: PositiveInt


class ObjectiveWeights(BaseModel):
    """Coefficients entiers partagés par les méthodes de planification."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    opened_bed: NonNegativeInt
    unmet_patient_day: NonNegativeInt
    staff_target_shortage: NonNegativeInt
    workload_imbalance: NonNegativeInt


class HospitalConfig(BaseModel):
    """Configuration complète et valide de l'hôpital synthétique."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    hospital_name: str = Field(min_length=1)
    planning_horizon_days: PositiveInt
    historical_days: PositiveInt
    random_seed: NonNegativeInt
    services: dict[str, ServiceConfig] = Field(min_length=1)
    shifts: list[ShiftConfig] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    synthetic_data: SyntheticDataConfig
    planning_policy: PlanningPolicyConfig
    objective_weights: ObjectiveWeights

    @field_validator("services")
    @classmethod
    def validate_service_codes(cls, services: dict[str, ServiceConfig]) -> dict[str, ServiceConfig]:
        for code in services:
            if not code.isupper() or not code.replace("_", "").isalpha():
                raise ValueError("Un code de service doit être en majuscules avec des underscores éventuels.")
        return services

    @model_validator(mode="after")
    def validate_unique_codes(self) -> "HospitalConfig":
        shift_codes = [shift.code for shift in self.shifts]
        if len(shift_codes) != len(set(shift_codes)):
            raise ValueError("Les codes de poste doivent être uniques.")
        if len(self.roles) != len(set(self.roles)):
            raise ValueError("Les rôles doivent être uniques.")
        if any(not role.isupper() for role in self.roles):
            raise ValueError("Les rôles doivent être en majuscules.")
        for mapping_name, mapping in {
            "staff_by_role": self.synthetic_data.staff_by_role,
            "staff_per_ten_beds": self.synthetic_data.staff_per_ten_beds,
            "minimum_staff_by_role": self.synthetic_data.minimum_staff_by_role,
        }.items():
            unknown_roles = set(mapping) - set(self.roles)
            if unknown_roles:
                raise ValueError(f"{mapping_name} contient des rôles inconnus: {sorted(unknown_roles)}")
            missing_roles = set(self.roles) - set(mapping)
            if missing_roles:
                raise ValueError(f"{mapping_name} ne définit pas les rôles: {sorted(missing_roles)}")
        for month_day in self.synthetic_data.holiday_month_days:
            try:
                datetime.strptime(month_day, "%m-%d")
            except ValueError as error:
                raise ValueError("Les jours fériés doivent suivre le format MM-JJ.") from error
        return self


class ForecastReference(BaseModel):
    """Référence immuable à un artefact de prévision."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    forecast_run_id: str = Field(min_length=1)
    origin_date: date
    horizon_days: PositiveInt
    artifact_path: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)


class PlanningInstanceReference(BaseModel):
    """Référence à une instance canonique partagée entre les méthodes."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    instance_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    forecast: ForecastReference
    input_hash: str = Field(min_length=1)
    created_at: datetime


class ValidationReport(BaseModel):
    """Résultat du validateur indépendant prévu en phase 5."""

    model_config = ConfigDict(extra="forbid")
    valid: bool
    hard_constraint_violations: NonNegativeInt = 0
    capacity_violations: NonNegativeInt = 0
    availability_violations: NonNegativeInt = 0
    qualification_violations: NonNegativeInt = 0
    double_assignment_violations: NonNegativeInt = 0
    coverage_deficits: NonNegativeInt = 0
    workload_range: NonNegativeInt = 0
    messages: list[str] = Field(default_factory=list)


class ObjectiveComponents(BaseModel):
    """Décomposition traçable de la fonction objectif canonique."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    opened_bed_cost: NonNegativeFloat
    unmet_patient_day_cost: NonNegativeFloat
    staff_target_shortage_cost: NonNegativeFloat
    workload_imbalance_cost: NonNegativeFloat
    total_cost: NonNegativeFloat


class MethodResult(BaseModel):
    """Contrat normalisé d'un résultat de méthode de planification."""

    model_config = ConfigDict(extra="forbid")
    experiment_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    method_name: Literal["greedy", "milp", "cp_sat"]
    status: MethodStatus
    runtime_seconds: NonNegativeFloat
    objective_value: float | None = None
    objective_components: ObjectiveComponents | None = None
    optimality_gap: NonNegativeFloat | None = None
    unmet_demand_patient_days: NonNegativeInt | None = None
    rejected_admissions: NonNegativeInt | None = None
    staff_shortage_total: NonNegativeInt | None = None
    coverage_rate: Annotated[float, Field(ge=0, le=1)] | None = None
    beds_opened_total: NonNegativeInt | None = None
    fairness_metric: NonNegativeFloat | None = None
    seed: NonNegativeInt
    config_hash: str = Field(min_length=1)
    validation: ValidationReport | None = None
    assignments_artifact_path: str | None = None
    allocations_artifact_path: str | None = None
    native_status: str | None = None
    error_message: str | None = None


class JobResponse(BaseModel):
    """Contrat HTTP de suivi d'une exécution asynchrone locale."""

    job_id: str = Field(min_length=1)
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    experiment_ids: list[str] = Field(default_factory=list)
    error_message: str | None = None


class ExperimentJobRequest(BaseModel):
    """Demande de calcul explicite d'expériences de scénarios."""

    model_config = ConfigDict(extra="forbid")
    scenario_ids: list[str] | None = None
    methods: list[Literal["greedy", "milp", "cp_sat"]] = Field(default_factory=lambda: ["greedy"])
    seed: NonNegativeInt | None = None

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, methods: list[str]) -> list[str]:
        if not methods or len(methods) != len(set(methods)):
            raise ValueError("methods doit contenir des méthodes uniques et non vides.")
        return methods


class ExperimentSummary(BaseModel):
    """Vue de lecture compacte d'une expérience stockée."""

    model_config = ConfigDict(extra="forbid")
    experiment_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    created_at: datetime
    methods: list[str]
    scenario_input_hash: str = Field(min_length=1)


class ArtifactProvenance(BaseModel):
    """Provenance d'une réponse de lecture destinée au dashboard."""

    model_config = ConfigDict(extra="forbid")
    artifact_path: str = Field(min_length=1)
    generated_at: datetime | None = None
    config_hash: str | None = None
    random_seed: NonNegativeInt | None = None
    source_id: str | None = None


class ScenarioReadModel(BaseModel):
    """Projection de lecture d'un scénario déclaré dans la configuration."""

    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    demand_multiplier: Annotated[float, Field(ge=1)]
    absence_rate: Annotated[float, Field(ge=0, le=1)]
    capacity_reduction: Annotated[float, Field(ge=0, lt=1)]
    service_multipliers: dict[str, float] = Field(default_factory=dict)
    peak_days: PositiveInt | None = None


class SensitivityManifestEntry(BaseModel):
    """Ligne déclarative d'une sensibilité non exécutée."""

    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(min_length=1)
    absence_rate: Annotated[float, Field(ge=0, le=1)]
    demand_multiplier: Annotated[float, Field(ge=1)]
    capacity_reduction: Annotated[float, Field(ge=0, lt=1)]
    seed: NonNegativeInt
    exact_calls: NonNegativeInt


class ForecastPoint(BaseModel):
    """Prévision finale sérialisée, continue avant conversion opérationnelle."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    model_name: str
    horizon: PositiveInt
    yhat: NonNegativeFloat
    selected: bool
    origin_date: date


class ForecastMetric(BaseModel):
    """Métrique d'évaluation chronologique d'un modèle de prévision."""

    model_config = ConfigDict(extra="forbid")
    partition: str
    model_name: str
    service: str
    observations: NonNegativeInt
    mae: NonNegativeFloat
    rmse: NonNegativeFloat
    wape: float | None = None
    wape_status: str
    bias: float


class ForecastArtifactResponse(BaseModel):
    """Prévisions et métriques persistées, sans recalcul."""

    model_config = ConfigDict(extra="forbid")
    provenance: ArtifactProvenance
    forecasts: list[ForecastPoint]
    metrics: list[ForecastMetric]


class ExplorationDemandPoint(BaseModel):
    """Observation historique synthétique d'admissions."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    admissions: NonNegativeInt
    discharges: NonNegativeInt
    emergency_arrivals: NonNegativeInt | None = None
    is_holiday: bool
    is_special_event: bool


class ExplorationOccupancyPoint(BaseModel):
    """Occupation synthétique historique par service et jour."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    occupancy_end: NonNegativeInt
    overflow: NonNegativeInt


class ExplorationCapacityPoint(BaseModel):
    """Capacité opérationnelle synthétique par service et jour."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    beds_operational: NonNegativeInt
    beds_unavailable: NonNegativeInt


class ExplorationArtifactResponse(BaseModel):
    """Séries d'exploration stockées par la phase de génération."""

    model_config = ConfigDict(extra="forbid")
    provenance: ArtifactProvenance
    historical_demand: list[ExplorationDemandPoint]
    occupancy: list[ExplorationOccupancyPoint]
    capacity: list[ExplorationCapacityPoint]


class OperationalDemandPoint(BaseModel):
    """Demande opérationnelle dérivée d'une prévision sélectionnée."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    model_name: str
    horizon: PositiveInt
    yhat: NonNegativeFloat
    requested_admissions: NonNegativeInt
    source_type: str


class OperationalBedPoint(BaseModel):
    """Besoin de lit opérationnel avant toute décision d'allocation."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    occupancy_start: NonNegativeInt
    expected_discharges: NonNegativeInt
    requested_admissions: NonNegativeInt
    occupancy_required: NonNegativeInt
    beds_required: NonNegativeInt
    capacity_available: NonNegativeInt
    capacity_gap: NonNegativeInt
    capacity_source: str


class OperationalArtifactResponse(BaseModel):
    """Instance opérationnelle canonique sérialisée, sans allocation."""

    model_config = ConfigDict(extra="forbid")
    provenance: ArtifactProvenance
    demand: list[OperationalDemandPoint]
    beds: list[OperationalBedPoint]


class AllocationPoint(BaseModel):
    """Décision de lits issue d'une méthode terminée."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    occupancy_start: NonNegativeInt
    expected_discharges: NonNegativeInt
    requested_admissions: NonNegativeInt
    occupancy_required: NonNegativeInt | None = None
    accepted_admissions: NonNegativeInt
    rejected_admissions: NonNegativeInt
    occupancy_end: NonNegativeInt
    opened_beds: NonNegativeInt
    capacity_available: NonNegativeInt


class StaffCoveragePoint(BaseModel):
    """Couverture RH calculée pour un rôle, service, jour et poste."""

    model_config = ConfigDict(extra="forbid")
    date: date
    service: str
    shift: str
    role: str
    opened_beds: NonNegativeInt
    minimum_staff: NonNegativeInt
    target_staff: NonNegativeInt
    assigned_staff: NonNegativeInt
    target_shortage: NonNegativeInt


class AllocationArtifactResponse(BaseModel):
    """Résultat de méthode avec lits et couverture RH réellement persistés."""

    model_config = ConfigDict(extra="forbid")
    provenance: ArtifactProvenance
    method_result: MethodResult
    allocations: list[AllocationPoint]
    staff_coverage: list[StaffCoveragePoint]

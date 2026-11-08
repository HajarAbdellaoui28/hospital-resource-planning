"""API FastAPI pour soumettre, consulter et télécharger les expériences locales."""

import json
import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from hospital_planning.api.jobs import JobRegistry
from hospital_planning.config.loader import load_hospital_config
from hospital_planning.domain.contracts import (
    AllocationArtifactResponse,
    ArtifactProvenance,
    ExperimentJobRequest,
    ExperimentSummary,
    ExplorationArtifactResponse,
    ForecastArtifactResponse,
    HospitalConfig,
    JobResponse,
    MethodResult,
    OperationalArtifactResponse,
    ScenarioReadModel,
    SensitivityManifestEntry,
)
from hospital_planning.experiments.runner import run_experiment, save_experiment
from hospital_planning.experiments.scenarios import load_scenarios
from hospital_planning.optimization.availability import project_planning_availability

app = FastAPI(
    title="Hospital Resource Planning API",
    version="0.1.0",
    description="API locale pour les expériences hospitalières synthétiques.",
)
job_registry = JobRegistry()


def cors_origins() -> list[str]:
    """Retourne les origines Next.js locales autorisées, jamais un joker global."""
    raw_origins = os.environ.get(
        "HOSPITAL_CORS_ORIGINS",
        "http://localhost:3011,http://127.0.0.1:3011,http://localhost:3000,http://127.0.0.1:3000",
    )
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    if not origins or "*" in origins or any(not origin.startswith(("http://", "https://")) for origin in origins):
        raise ValueError("HOSPITAL_CORS_ORIGINS doit contenir des origines HTTP(S) explicites, sans '*'.")
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def project_root() -> Path:
    """Résout la racine locale configurée, sans dépendre du chemin d'installation."""
    return Path(os.environ.get("HOSPITAL_PROJECT_ROOT", Path.cwd())).resolve()


def hospital_config_path() -> Path:
    """Résout la configuration sans dépendre du chemin d'installation du paquet."""
    configured_path = os.environ.get("HOSPITAL_CONFIG_PATH")
    return Path(configured_path) if configured_path else project_root() / "configs" / "hospital.json"


def experiments_root() -> Path:
    """Retourne le répertoire d'artefacts, configurable pour les tests ou déploiements locaux."""
    configured_path = os.environ.get("HOSPITAL_RESULTS_PATH")
    return Path(configured_path).resolve() if configured_path else project_root() / "results" / "experiments"


def synthetic_data_root() -> Path:
    """Retourne le répertoire de données synthétiques produit par la phase 2."""
    return project_root() / "data" / "synthetic"


def forecast_root() -> Path:
    """Retourne le répertoire des artefacts persistés de prévision."""
    return project_root() / "results" / "forecasts"


def operational_root(scenario_id: str) -> Path:
    """Retourne l'instance opérationnelle sans accepter de traversée de chemin."""
    root = (project_root() / "results" / "operational_instances").resolve()
    # L'artefact canonique de l'instance nominale est historiquement nommé S0,
    # tandis que la configuration de scénarios le désigne S0_BASELINE.
    directory_name = {"S0_BASELINE": "S0"}.get(scenario_id, scenario_id)
    directory = (root / directory_name).resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Instance opérationnelle introuvable.")
    return directory


@app.get("/health")
def health() -> dict[str, str]:
    """Expose l'état minimal du service sans déclencher de calcul."""
    return {"status": "ok"}


@app.get("/api/v1/config/hospital", response_model=HospitalConfig)
def get_hospital_config() -> HospitalConfig:
    """Retourne la configuration validée de l'hôpital synthétique."""
    try:
        return load_hospital_config(hospital_config_path())
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Configuration hospitalière invalide.") from error


@app.post("/api/v1/jobs/experiments", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_experiment_job(request: ExperimentJobRequest) -> JobResponse:
    """Soumet un job explicite; aucun endpoint de lecture ne lance de calcul."""
    return job_registry.submit(lambda: _run_experiment_job(request))


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    """Retourne l'état réel d'un job local sans jamais le relancer."""
    response = job_registry.get(job_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Job inconnu: {job_id}")
    return response


@app.get("/api/v1/experiments", response_model=list[ExperimentSummary])
def list_experiments() -> list[ExperimentSummary]:
    """Liste les expériences déjà stockées; cette lecture est strictement passive."""
    root = experiments_root()
    if not root.exists():
        return []
    return [summary for path in sorted(root.glob("*/experiment.json")) if (summary := _read_experiment_summary(path))]


@app.get("/api/v1/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict[str, object]:
    """Retourne les métadonnées et KPI d'une expérience stockée, sans calcul."""
    directory = _experiment_directory(experiment_id)
    metadata_path = directory / "experiment.json"
    metrics_path = directory / "metrics.csv"
    if not metadata_path.is_file() or not metrics_path.is_file():
        raise HTTPException(status_code=404, detail=f"Expérience inconnue: {experiment_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metrics = pd.read_csv(metrics_path).where(pd.notna, None).to_dict(orient="records")
    return {"metadata": metadata, "metrics": metrics}


@app.get("/api/v1/experiments/{experiment_id}/downloads/{artifact_path:path}")
def download_experiment_artifact(experiment_id: str, artifact_path: str) -> FileResponse:
    """Télécharge un artefact existant après contrôle strict du chemin."""
    directory = _experiment_directory(experiment_id)
    artifact = (directory / artifact_path).resolve()
    if not artifact.is_relative_to(directory) or not artifact.is_file():
        raise HTTPException(status_code=404, detail="Artefact introuvable.")
    return FileResponse(artifact, filename=artifact.name)


@app.get("/api/v1/dashboard/scenarios", response_model=list[ScenarioReadModel])
def get_dashboard_scenarios() -> list[ScenarioReadModel]:
    """Expose les scénarios déclarés, sans les transformer ni les exécuter."""
    try:
        config = load_hospital_config(hospital_config_path())
        return [
            ScenarioReadModel(**scenario.model_dump())
            for scenario in load_scenarios(project_root() / "configs" / "scenarios.json", config)
        ]
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Scénarios invalides ou indisponibles.") from error


@app.get("/api/v1/dashboard/sensitivity/manifest", response_model=list[SensitivityManifestEntry])
def get_sensitivity_manifest() -> list[SensitivityManifestEntry]:
    """Expose le manifeste déjà produit, sans déclencher la grille coûteuse."""
    path = experiments_root() / "sensitivity_manifest.csv"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Manifeste de sensibilité non généré.")
    return [SensitivityManifestEntry.model_validate(record) for record in _csv_records(path)]


@app.get("/api/v1/dashboard/forecasts", response_model=ForecastArtifactResponse)
def get_dashboard_forecasts() -> ForecastArtifactResponse:
    """Lit les prévisions finales et métriques enregistrées, sans les recalculer."""
    root = forecast_root()
    forecasts_path = root / "forecast_results.csv"
    metrics_path = root / "metrics_summary.csv"
    metadata_path = root / "metadata.json"
    _require_files(forecasts_path, metrics_path, metadata_path, detail="Artefacts de prévision non générés.")
    metadata = _read_json(metadata_path, detail="Métadonnées de prévision invalides.")
    forecasts = _csv_records(
        forecasts_path,
        date_columns=("date", "origin_date"),
        columns=("date", "service", "model_name", "horizon", "yhat", "selected", "origin_date"),
    )
    metrics = _csv_records(metrics_path)
    return ForecastArtifactResponse(
        provenance=ArtifactProvenance(
            artifact_path=str(root.relative_to(project_root())),
            generated_at=metadata.get("created_at"),
            config_hash=metadata.get("demand_config_hash"),
            source_id=metadata.get("forecast_run_id"),
        ),
        forecasts=forecasts,
        metrics=metrics,
    )


@app.get("/api/v1/dashboard/exploration", response_model=ExplorationArtifactResponse)
def get_dashboard_exploration() -> ExplorationArtifactResponse:
    """Lit les séries synthétiques historiques nécessaires aux graphiques d'exploration."""
    root = synthetic_data_root()
    demand_path = root / "historical_demand.csv"
    occupancy_path = root / "occupancy.csv"
    capacity_path = root / "bed_capacity.csv"
    _require_files(demand_path, occupancy_path, capacity_path, detail="Données synthétiques non générées.")
    return ExplorationArtifactResponse(
        provenance=ArtifactProvenance(
            artifact_path=str(root.relative_to(project_root())),
            random_seed=load_hospital_config(hospital_config_path()).random_seed,
            source_id="synthetic-data",
        ),
        historical_demand=_csv_records(
            demand_path,
            date_columns=("date",),
            columns=(
                "date",
                "service",
                "admissions",
                "discharges",
                "emergency_arrivals",
                "is_holiday",
                "is_special_event",
            ),
        ),
        occupancy=_csv_records(
            occupancy_path,
            date_columns=("date",),
            columns=("date", "service", "occupancy_end", "overflow"),
        ),
        capacity=_csv_records(
            capacity_path,
            date_columns=("date",),
            columns=("date", "service", "beds_operational", "beds_unavailable"),
        ),
    )


@app.get("/api/v1/dashboard/operational/{scenario_id}", response_model=OperationalArtifactResponse)
def get_dashboard_operational(scenario_id: str) -> OperationalArtifactResponse:
    """Lit une instance canonique opérationnelle, sans déclencher de décision."""
    root = operational_root(scenario_id)
    demand_path = root / "demand_requirements.csv"
    beds_path = root / "bed_requirements.csv"
    metadata_path = root / "operational_instance.json"
    _require_files(demand_path, beds_path, metadata_path, detail="Instance opérationnelle non générée.")
    metadata = _read_json(metadata_path, detail="Métadonnées opérationnelles invalides.")
    instance = metadata.get("instance", {})
    forecast = instance.get("forecast", {}) if isinstance(instance, dict) else {}
    return OperationalArtifactResponse(
        provenance=ArtifactProvenance(
            artifact_path=str(root.relative_to(project_root())),
            generated_at=instance.get("created_at") if isinstance(instance, dict) else None,
            config_hash=forecast.get("config_hash"),
            source_id=instance.get("instance_id") if isinstance(instance, dict) else None,
        ),
        demand=_csv_records(demand_path, date_columns=("date",)),
        beds=_csv_records(beds_path, date_columns=("date",)),
    )


@app.get(
    "/api/v1/dashboard/experiments/{experiment_id}/methods/{method_name}",
    response_model=AllocationArtifactResponse,
)
def get_dashboard_allocation(experiment_id: str, method_name: str) -> AllocationArtifactResponse:
    """Lit les allocations et la couverture RH d'une méthode déjà terminée."""
    directory = _experiment_directory(experiment_id)
    metadata_path = directory / "experiment.json"
    if not metadata_path.is_file():
        raise HTTPException(status_code=404, detail="Expérience inconnue.")
    metadata = _read_json(metadata_path, detail="Métadonnées d'expérience invalides.")
    artifacts = metadata.get("method_artifacts", {}).get(method_name)
    if not isinstance(artifacts, dict):
        raise HTTPException(status_code=404, detail="Méthode non disponible pour cette expérience.")
    allocations_path = _resolve_experiment_artifact(directory, artifacts.get("bed_allocations"))
    coverage_path = _resolve_experiment_artifact(directory, artifacts.get("staff_coverage"))
    result_path = _resolve_experiment_artifact(directory, artifacts.get("method_result"))
    _require_files(allocations_path, coverage_path, result_path, detail="Artefacts d'allocation non générés.")
    result = MethodResult.model_validate(_read_json(result_path, detail="Résultat de méthode invalide."))
    return AllocationArtifactResponse(
        provenance=ArtifactProvenance(
            artifact_path=str(directory.relative_to(experiments_root().resolve())),
            generated_at=metadata.get("created_at"),
            random_seed=metadata.get("seed"),
            config_hash=result.config_hash,
            source_id=experiment_id,
        ),
        method_result=result,
        allocations=_csv_records(allocations_path, date_columns=("date",)),
        staff_coverage=_csv_records(coverage_path, date_columns=("date",)),
    )


def _experiment_directory(experiment_id: str) -> Path:
    root = experiments_root().resolve()
    directory = (root / experiment_id).resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Expérience introuvable.")
    return directory


def _resolve_experiment_artifact(directory: Path, raw_path: object) -> Path:
    """Résout un chemin d'artefact absolu, local ou historique sans traversée."""
    if not isinstance(raw_path, str) or not raw_path:
        raise HTTPException(status_code=404, detail="Artefact introuvable.")
    candidate = Path(raw_path)
    candidates = [candidate.resolve()] if candidate.is_absolute() else [
        (directory / candidate).resolve(),
        (project_root() / candidate).resolve(),
    ]
    for artifact in candidates:
        if artifact.is_relative_to(directory) and artifact.is_file():
            return artifact
    raise HTTPException(status_code=404, detail="Artefact introuvable.")


def _require_files(*paths: Path, detail: str) -> None:
    """Retourne une erreur explicite lorsque la phase productrice n'a pas tourné."""
    if any(not path.is_file() for path in paths):
        raise HTTPException(status_code=404, detail=detail)


def _read_json(path: Path, *, detail: str) -> dict[str, object]:
    """Charge un JSON artefact avec une erreur HTTP stable."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail=detail) from error
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail=detail)
    return value


def _csv_records(
    path: Path,
    *,
    date_columns: tuple[str, ...] = (),
    columns: tuple[str, ...] | None = None,
) -> list[dict[str, object]]:
    """Sérialise un CSV artefact en enregistrements JSON sans perdre les dates."""
    try:
        frame = pd.read_csv(path, parse_dates=list(date_columns))
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Artefact CSV invalide.") from error
    if columns is not None:
        missing = set(columns) - set(frame.columns)
        if missing:
            raise HTTPException(status_code=500, detail="Colonnes d'artefact inattendues.")
        frame = frame.loc[:, list(columns)]
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _read_experiment_summary(metadata_path: Path) -> ExperimentSummary | None:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        scenario = metadata["scenario"]
        return ExperimentSummary(
            experiment_id=metadata["experiment_id"],
            scenario_id=scenario["scenario_id"],
            created_at=metadata["created_at"],
            methods=metadata["methods"],
            scenario_input_hash=metadata["scenario_input_hash"],
        )
    except (KeyError, OSError, ValueError):
        return None


def _run_experiment_job(request: ExperimentJobRequest) -> list[str]:
    """Exécute les scénarios demandés dans l'unique worker local borné."""
    root = project_root()
    config = load_hospital_config(hospital_config_path())
    instance_directory = root / "results" / "operational_instances" / "S0"
    demand = pd.read_csv(instance_directory / "demand_requirements.csv", parse_dates=["date"])
    beds = pd.read_csv(instance_directory / "bed_requirements.csv", parse_dates=["date"])
    staff = pd.read_csv(root / "data" / "synthetic" / "staff.csv")
    availability = pd.read_csv(root / "data" / "synthetic" / "staff_availability.csv", parse_dates=["date"])
    metadata = json.loads((instance_directory / "operational_instance.json").read_text(encoding="utf-8"))
    planning_availability = project_planning_availability(staff, availability, demand["date"], config)
    scenarios = load_scenarios(root / "configs" / "scenarios.json", config)
    if request.scenario_ids is not None:
        requested_ids = set(request.scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.scenario_id in requested_ids]
        missing = requested_ids - {scenario.scenario_id for scenario in scenarios}
        if missing:
            raise ValueError(f"Scénarios inconnus: {sorted(missing)}")
    experiment_ids = []
    for scenario in scenarios:
        experiment, outputs = run_experiment(
            scenario,
            demand,
            beds,
            staff,
            availability,
            planning_availability,
            metadata,
            config,
            methods=tuple(request.methods),
            seed=request.seed,
        )
        save_experiment(experiment, outputs, experiments_root() / experiment.experiment_id)
        experiment_ids.append(experiment.experiment_id)
    return experiment_ids

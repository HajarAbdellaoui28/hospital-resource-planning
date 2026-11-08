import type { AllocationArtifact, DashboardBootstrap, ExperimentDetail, ExperimentJobRequest, ExperimentSummary, JobResponse, LoadState, OperationalArtifact, Scenario, ForecastArtifact, ExplorationArtifact, SensitivityManifestEntry } from "./api-types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

function apiUrl(baseUrl: string, path: string) { return `${baseUrl.replace(/\/$/, "")}${path}`; }

async function getJson<T>(baseUrl: string, path: string): Promise<T> {
  const response = await fetch(apiUrl(baseUrl, path));
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? `Erreur HTTP ${response.status}`, response.status);
  }
  return response.json() as Promise<T>;
}

async function sendJson<T>(baseUrl: string, path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(baseUrl, path), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(payload?.detail ?? `Erreur HTTP ${response.status}`, response.status);
  }
  return response.json() as Promise<T>;
}

function resource<T>(promise: Promise<T>): Promise<LoadState<T>> {
  return promise.then((data): LoadState<T> => Array.isArray(data) && data.length === 0 ? { status: "empty", message: "Aucun artefact disponible." } : { status: "success", data }).catch((error: unknown): LoadState<T> => {
    if (error instanceof ApiError && error.status === 404) return { status: "empty", message: error.message };
    if (error instanceof TypeError) return { status: "error", message: "API inaccessible : vérifiez FastAPI sur http://127.0.0.1:8000 et les origines CORS." };
    return { status: "error", message: error instanceof Error ? `Erreur serveur : ${error.message}` : "Erreur de lecture inconnue." };
  });
}

export function loadDashboardBootstrap(baseUrl: string): Promise<DashboardBootstrap> {
  return Promise.all([
    resource(getJson<Scenario[]>(baseUrl, "/api/v1/dashboard/scenarios")),
    resource(getJson<ForecastArtifact>(baseUrl, "/api/v1/dashboard/forecasts")),
    resource(getJson<ExplorationArtifact>(baseUrl, "/api/v1/dashboard/exploration")),
    resource(getJson<OperationalArtifact>(baseUrl, "/api/v1/dashboard/operational/S0_BASELINE")),
    resource(getJson<ExperimentSummary[]>(baseUrl, "/api/v1/experiments")),
  ]).then(([scenarios, forecasts, exploration, operational, experiments]) => ({ scenarios, forecasts, exploration, operational, experiments }));
}

export function loadAllocation(baseUrl: string, experimentId: string, methodName: string) {
  return resource(getJson<AllocationArtifact>(baseUrl, `/api/v1/dashboard/experiments/${encodeURIComponent(experimentId)}/methods/${encodeURIComponent(methodName)}`));
}
export function loadSensitivityManifest(baseUrl: string) { return resource(getJson<SensitivityManifestEntry[]>(baseUrl, "/api/v1/dashboard/sensitivity/manifest")); }

export function submitExperiment(baseUrl: string, request: ExperimentJobRequest) { return sendJson<JobResponse>(baseUrl, "/api/v1/jobs/experiments", request); }
export function loadJob(baseUrl: string, jobId: string) { return getJson<JobResponse>(baseUrl, `/api/v1/jobs/${encodeURIComponent(jobId)}`); }
export function loadExperimentDetail(baseUrl: string, experimentId: string) { return getJson<ExperimentDetail>(baseUrl, `/api/v1/experiments/${encodeURIComponent(experimentId)}`); }
export function artifactDownloadUrl(baseUrl: string, experimentId: string, artifactPath: string) { return apiUrl(baseUrl, `/api/v1/experiments/${encodeURIComponent(experimentId)}/downloads/${artifactPath.split("/").map(encodeURIComponent).join("/")}`); }

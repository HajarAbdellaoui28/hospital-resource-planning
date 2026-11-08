export type LoadState<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "empty"; message: string }
  | { status: "error"; message: string };

export type ArtifactProvenance = {
  artifact_path: string;
  generated_at: string | null;
  config_hash: string | null;
  random_seed: number | null;
  source_id: string | null;
};

export type Scenario = {
  scenario_id: string;
  description: string;
  demand_multiplier: number;
  absence_rate: number;
  capacity_reduction: number;
  service_multipliers: Record<string, number>;
  peak_days: number | null;
};
export type SensitivityManifestEntry = { scenario_id: string; absence_rate: number; demand_multiplier: number; capacity_reduction: number; seed: number; exact_calls: number };

export type ForecastPoint = {
  date: string;
  service: string;
  model_name: string;
  horizon: number;
  yhat: number;
  selected: boolean;
  origin_date: string;
};

export type ForecastMetric = {
  partition: string;
  model_name: string;
  service: string;
  observations: number;
  mae: number;
  rmse: number;
  wape: number | null;
  wape_status: string;
  bias: number;
};

export type ForecastArtifact = { provenance: ArtifactProvenance; forecasts: ForecastPoint[]; metrics: ForecastMetric[] };
export type ExplorationDemand = { date: string; service: string; admissions: number; discharges: number; emergency_arrivals: number | null; is_holiday: boolean; is_special_event: boolean };
export type ExplorationOccupancy = { date: string; service: string; occupancy_end: number; overflow: number };
export type ExplorationCapacity = { date: string; service: string; beds_operational: number; beds_unavailable: number };
export type ExplorationArtifact = { provenance: ArtifactProvenance; historical_demand: ExplorationDemand[]; occupancy: ExplorationOccupancy[]; capacity: ExplorationCapacity[] };
export type OperationalDemand = { date: string; service: string; model_name: string; horizon: number; yhat: number; requested_admissions: number; source_type: string };
export type OperationalBed = { date: string; service: string; occupancy_start: number; expected_discharges: number; requested_admissions: number; occupancy_required: number; beds_required: number; capacity_available: number; capacity_gap: number; capacity_source: string };
export type OperationalArtifact = { provenance: ArtifactProvenance; demand: OperationalDemand[]; beds: OperationalBed[] };
export type ExperimentSummary = { experiment_id: string; scenario_id: string; created_at: string; methods: string[]; scenario_input_hash: string };
export type ObjectiveComponents = { opened_bed_cost: number; unmet_patient_day_cost: number; staff_target_shortage_cost: number; workload_imbalance_cost: number; total_cost: number };
export type MethodResult = { experiment_id: string; scenario_id: string; method_name: string; status: string; runtime_seconds: number; objective_value: number | null; objective_components: ObjectiveComponents | null; optimality_gap: number | null; unmet_demand_patient_days: number | null; rejected_admissions: number | null; staff_shortage_total: number | null; coverage_rate: number | null; beds_opened_total: number | null; fairness_metric: number | null; seed: number; config_hash: string; validation: { valid: boolean; hard_constraint_violations: number; workload_range: number; messages: string[] } | null; native_status: string | null };
export type AllocationPoint = { date: string; service: string; occupancy_start: number; expected_discharges: number; requested_admissions: number; occupancy_required: number | null; accepted_admissions: number; rejected_admissions: number; occupancy_end: number; opened_beds: number; capacity_available: number };
export type StaffCoveragePoint = { date: string; service: string; shift: string; role: string; opened_beds: number; minimum_staff: number; target_staff: number; assigned_staff: number; target_shortage: number };
export type AllocationArtifact = { provenance: ArtifactProvenance; method_result: MethodResult; allocations: AllocationPoint[]; staff_coverage: StaffCoveragePoint[] };
export type ExperimentJobRequest = { scenario_ids: string[]; methods: string[]; seed?: number };
export type JobResponse = { job_id: string; status: "QUEUED" | "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED"; created_at: string; started_at: string | null; finished_at: string | null; experiment_ids: string[]; error_message: string | null };
export type ExperimentMetric = { experiment_id: string; scenario_id: string; method_name: string; status: string; native_status: string | null; runtime_seconds: number; objective_value: number | null; optimality_gap: number | null; unmet_demand_patient_days: number | null; rejected_admissions: number | null; staff_shortage_total: number | null; coverage_rate: number | null; beds_opened_total: number | null; fairness_metric: number | null; hard_constraint_violations: number | null; validation_passed: boolean | null; opened_bed_cost: number | null; unmet_patient_day_cost: number | null; staff_target_shortage_cost: number | null; workload_imbalance_cost: number | null };
export type ExperimentDetail = { metadata: { experiment_id: string; created_at: string; seed: number; scenario: Scenario; methods: string[]; method_artifacts: Record<string, Record<string, string>> }; metrics: ExperimentMetric[] };
export type DashboardBootstrap = { scenarios: LoadState<Scenario[]>; forecasts: LoadState<ForecastArtifact>; exploration: LoadState<ExplorationArtifact>; operational: LoadState<OperationalArtifact>; experiments: LoadState<ExperimentSummary[]> };

# Implementation Plan — Hospital Resource Planning

## 1. Review outcome and retained decisions

This refines the existing ten-phase plan against `specifications.md`; it preserves its architecture and implementation sequence.

The plan covers the mandatory requirements. Its principal risks are the joint optimization model, equivalent solver formulations, reproducibility, and the additional API work required by Next.js. The following refinements address those risks.

| Area | Review finding | Refinement |
|---|---|---|
| Completeness | Broad coverage was correct, but acceptance evidence was implicit | Add explicit phase gates and requirement traceability |
| Interface | The specification mixes Streamlit references with an explicit Next.js requirement | Retain Next.js + shadcn/ui, following §2.3 |
| Planning scope | Joint optimization exceeds the simplest formulations in the specification | Retain the joint model, as selected during review |
| Units | Rejected admissions and unmet occupancy could be conflated | Record admissions and patient-day metrics separately |
| Staffing | Shortage variables could inadvertently permit unstaffed operational beds | Make staffing support for opened beds a hard constraint |
| Feasibility | Greedy failure does not prove an instance infeasible | Reserve `INFEASIBLE` for proven infeasibility |
| Dependencies | Installing PuLP alone does not ensure CBC availability | Explicitly provision and smoke-test both solvers |
| Sensitivity | The full grid creates a substantial batch workload | Separate demonstration runs from the full benchmark |
| Delivery | API and integration responsibilities overloaded the dashboard owner | Share application/API integration between M5 and M6 |

The delivery baseline includes all five forecasting models, three comparable planning methods, individual schedules, six scenarios, sensitivity analysis, exports, tests, and documentation. Features labeled optional earlier in the specification remain mandatory where its final acceptance checklist requires them.

## 2. Architecture and modeling contracts

### Application architecture

Use a local modular application:

```text
Next.js / TypeScript / shadcn/ui / Plotly.js
                       │
                    FastAPI
                       │
            Shared application services
                 CLI + experiment runner
                       │
    Synthetic data → Forecasting → Operational needs
                                          │
                                Frozen planning instance
                                          │
                              Greedy / MILP / CP-SAT
                                          │
                               Independent validation
                                          │
                              Metrics → CSV/JSON storage
```

- Python modules own simulation, forecasting, planning, validation, and metrics.
- The CLI and API invoke the same services; the frontend contains no duplicated planning logic.
- Preserve the specification’s module boundaries. Add a domain/contracts layer, application services, an API layer, and a separate frontend.
- Use CSV/JSON persistence with immutable run artifacts and atomic manifest updates.
- Run one API process and one bounded local compute worker. Execute batch methods sequentially for predictable resource use and benchmark timing.
- Read requests and dashboard filters never trigger computation. Execution requires an explicit command or submission.
- Keep charts, fonts, and other required demonstration assets local so runtime operation does not depend on external services.

**Dependencies:** Python 3.12, NumPy, pandas, statsmodels, scikit-learn, PuLP/CBC, OR-Tools, FastAPI/Pydantic/Uvicorn; Next.js, TypeScript, shadcn/ui, Plotly.js; pytest, Ruff, ESLint, TypeScript checks, and Playwright.

Use an isolated Python environment and npm lockfile. Resolve and freeze compatible released versions during Phase 1. Do not reuse global Python packages as the project environment.

The current machine has Python 3.12.1 and Node 22.14.0, but the statistical and solver stack is incomplete. Current PuLP documentation describes breaking version-4 APIs and requires separate CBC provisioning through `pulp[cbc]` or an external binary; the planned adapter will use the documented `COIN_CMD` interface. [PuLP installation and API documentation](https://pypi.org/project/PuLP/).

### Data and operational units

Preserve the specified tables and add the minimum fields needed to remove ambiguities:

- Record requested admission demand, admitted patients, and admissions not served separately. Forecast admission demand; calculate actual occupancy from admitted patients.
- Add `date` to daily staffing requirements.
- Store initial occupancy cohorts with their remaining simulated stay durations.
- Preserve the input capacity invariant. Document its `beds_operational` field as the preplanning capacity ceiling; distinguish that ceiling from the optimized number of staffed, opened beds.
- Record forecast origin, horizon, target, model configuration, and evaluation partition alongside forecast artifacts.
- Serialize list-valued qualifications consistently as JSON arrays in CSV cells.

The planning model uses aggregate cohorts with a configurable, fixed integer stay duration per service. It does not create individual patient records.

Daily simulation order is discharges followed by admissions. The resulting census is the modeled occupancy for all three shifts that day. This daily approximation does not represent intraday occupancy peaks.

For each service and day:

- Forecast demand determines requested admissions.
- Accepted admissions contribute to occupancy throughout their modeled stay.
- Existing patients remain present until their scheduled discharge.
- Full-demand occupancy is the census obtained if all forecast admissions are accepted.
- Unmet occupancy is full-demand occupancy minus supported occupancy.

Consequently:

- `unmet_demand_total` uses **patient-days**.
- Rejected admissions are reported separately as **patients**.
- Coverage compares supported patient-days with requested patient-days.
- Bed occupancy compares occupied beds with staffed, opened beds.
- Summed opened beds over the horizon are labeled **bed-days**, rather than unique beds.

Keep continuous forecasts for statistical evaluation. At the planning boundary, apply scenario multipliers and then round admission demand upward to whole patients.

### Joint planning model

All three methods receive the same immutable planning instance: forecasts, initial cohorts, capacities, staff, availability, qualifications, shift rules, costs, and scenario.

The common model includes:

- Accepted admissions and cohort-based occupancy conservation.
- Integer opened beds within available capacity.
- Binary individual staff assignments by service, date, and shift.
- Hard staffing support for opened beds, separately for every required role and shift.
- Availability, active status, qualifications, one shift per day, maximum hours/shifts, and configured rest rules.
- Prior schedule history sufficient to check boundary rest and consecutive-night rules.
- End-of-horizon occupancy and staff state for subsequent planning.

Distinguish two staffing quantities:

1. **Staff needed for opened beds:** a hard operational requirement.
2. **Staff needed to support full forecast demand:** the target used to measure staffing shortages.

The default shortage-permitting policy may leave admission demand and target staffing unmet. It cannot relax qualifications, availability, rest, physical capacity, or staffing support for beds actually opened. A strict policy requires complete demand and target coverage and may be infeasible.

Use one configurable weighted objective for operating cost, unmet patient-days, staffing target deficits, and workload imbalance. All methods use identical coefficients and scaling. Use a linear workload-range penalty within comparable staff groups; report workload standard deviation separately as an explanatory KPI.

Use integer coefficients in both exact formulations. CP-SAT requires integer constraints, so scaling must preserve the same mathematical problem. [OR-Tools CP-SAT documentation](https://developers.google.com/optimization/cp/cp_solver).

### Public interfaces and results

Define shared contracts for configuration, dataset references, forecast runs, planning instances, method results, validation reports, and experiment manifests.

The API exposes versioned operations for:

- Configuration retrieval and validation.
- Dataset generation and quality reports.
- Forecast, experiment, and sensitivity submissions.
- Job status and experiment/result retrieval.
- Artifact downloads.

Execution submissions return job identifiers; results reference persisted artifacts. Generate frontend types from OpenAPI.

Keep execution lifecycle separate from method outcomes:

- Job lifecycle: queued, running, completed, partial, failed.
- Method status: `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`, `ERROR`.

Preserve every result field required by §3.9, native solver status, validation findings, and separate aggregate allocations and individual assignments.

A validated greedy candidate is `FEASIBLE`. Greedy failure is `UNKNOWN` unless an independent mathematical check proves infeasibility. Invalid returned candidates are retained for diagnostics, marked as errors, and excluded from valid comparisons.

## 3. Refined implementation phases

### Phase 1 — Contracts, mathematical specification, and foundation

**Dependencies:** None.  
**Owners:** All members; M3/M4 lead the planning formulation.

**Deliverables:** Project skeleton, isolated environments and dependency locks, configuration contracts, data dictionary, common mathematical formulation, API contract, hand-calculated fixtures, and acceptance-test matrix.

Document synthetic staffing ratios, costs, shift times, rest rules, stay durations, and calibration assumptions in configuration. Establish independent fixtures before solver implementation.

**Validation gate:** Configuration errors fail explicitly; contracts round-trip correctly; the four configured services total 300 beds; both solvers execute a tiny smoke-test problem on Windows; backend and frontend checks run from the documented environment.

### Phase 2 — Synthetic data and quality validation

**Dependencies:** Phase 1.  
**Owner:** M1.

**Deliverables:** Reproducible 1,095-day generation; weekly patterns, trend, simulated events, Poisson demand, aggregate occupancy cohorts, staff qualifications, availability, closures, preprocessing, quality reports, and exploratory figures.

Use dedicated seeded NumPy generators. Calibrate admissions, stay duration, and capacity together. Preserve unserved admissions or explicitly modeled overflow; never discard patients to satisfy capacity.

**Validation gate:** Complete dates, unique keys, nonnegative values, valid references, capacity invariants, occupancy conservation, and deterministic generation pass automated checks. Variability exists across dates and services. The report includes counts, date range, missingness, duplicates, invalid values, and service-level summaries.

### Phase 3 — Five forecasting models and evaluation

**Dependencies:** Phase 1 contracts; Phase 2 data for integration.  
**Owner:** M2.

**Deliverables:**

- Last-value naïve.
- Weekly seasonal naïve.
- Seven-day moving average, held constant across the forecast horizon.
- Additive seasonal exponential smoothing with weekly seasonality.
- Regularized lagged regression using recursive seven-step prediction.
- Forecast artifacts, model comparison, and service-specific model selection.

Use six expanding-window, seven-day validation blocks before four final seven-day test blocks. Default minimum initial training length is 365 days. Freeze model selection before the test period; subsequent test origins may use observations already available at that origin.

Select by validation MAE, then RMSE, then a fixed documented model-order tie-breaker. Fit transformations at each origin using training data only.

**Validation gate:** Outputs cover exactly seven dates per service and contain finite, nonnegative continuous predictions. Tests detect future-target leakage, including recursive forecasts and rolling features. Short histories fail clearly. MAE, RMSE, WAPE, and bias match hand calculations and are reported by model, service, horizon, and documented global aggregation.

### Phase 4 — Operational translation and canonical instance

**Dependencies:** Phases 1–3.  
**Owner:** M3, supported by M1/M2.

**Deliverables:** Forecast-to-admission conversion, initial discharge cohorts, projected occupancy, dated role/shift targets, capacity ceilings, planning policies, and immutable instance fingerprints.

Keep unconstrained demand projection separate from the occupancy resulting from accepted admissions. Serialize the full instance so every method can consume identical inputs.

**Validation gate:** Hand-calculated multi-day examples establish conservation and correct units. Rejecting an admission changes all affected future occupancy days. Initial patients cannot disappear. Closures below unavoidable occupancy produce an explicit feasibility conflict. Model inputs are finite, complete, and internally consistent.

### Phase 5 — Greedy planning and independent validator

**Dependencies:** Phase 1 contracts and Phase 4 integration.  
**Owner:** M4; M5 reviews validation independently.

**Deliverables:** Deterministic greedy allocation, individual schedules, aggregate results, structured validation reports, and the first complete CLI pipeline.

Process admissions chronologically with configured service priorities and deterministic tie-breaking. Before accepting an admission, reserve bed and staff support for its entire modeled stay within the horizon. Roll back unsuccessful tentative additions. Failure to construct support for existing patients returns an unproven failure, rather than fabricated feasibility.

The validator reconstructs occupancy, staffing support, hours, rest, deficits, and objective components from raw inputs and assignments. It does not reuse solver constraint expressions.

**Validation gate:** Every published candidate passes hard constraints. Corrupted fixtures independently trigger each violation category required by §15.4, including double assignment and qualification errors. Soft deficits remain separate. The end-to-end CLI produces validated results before advanced features proceed.

### Phase 6 — Equivalent MILP and CP-SAT methods

**Dependencies:** Phases 4–5.  
**Owners:** M3 for MILP; M4 for CP-SAT.

**Deliverables:** Two native solver adapters implementing the same joint model; standalone bed-allocation diagnostic cases; normalized statuses; incumbent handling; available bounds/gaps; solver logs; build and solve timings.

Create assignment variables only for eligible staff/service/shift combinations. Use a default 30-second solve limit and one solver thread for each exact method. Store any altered limits in experiment configuration.

**Validation gate:** Enumeratable fixtures establish optimal values and infeasibility. Both formulations agree on proven optimum values within documented numerical tolerance. Timeout tests distinguish valid incumbents from missing solutions. Every accepted candidate passes the independent validator. Large instances may return `FEASIBLE` or `UNKNOWN`; optimality is never required without proof.

### Phase 7 — Scenarios, experiments, metrics, and storage

**Dependencies:** Phase 1 contracts; integrated execution uses Phases 2–6.  
**Owner:** M5.

**Deliverables:** All six scenarios, experiment orchestration, sensitivity batches, KPI calculations, manifests, raw results, comparison tables, and CSV/JSON exports.

Default scenarios are:

| Scenario | Default transformation |
|---|---|
| S0 baseline | Unchanged demand and no additional absence |
| S1 urgent peak | URG demand +50% on planning days 3–4; +100% configurable |
| S2 general surge | All-service demand ×1.25 |
| S3 staff absence | Remove 15% of initially available professionals |
| S4 combined crisis | General surge plus 15% absence |
| S5 bed closure | Reduce available capacity by 10%, configurable |

Apply demand changes to future planning inputs without changing historical forecast evaluation. Select absent professionals reproducibly and remove their availability throughout the planning horizon. Use a stable ranking so increasing absence rates select nested subsets.

Run the specified sensitivity grid: five absence levels × four demand multipliers × four closure levels = **80 instances**, each evaluated by all three methods.

**Validation gate:** Source inputs remain unchanged; transformations have the intended direction; baseline is an identity transformation; fingerprints match across methods; partial failures preserve completed results. Recompute all KPIs independently, including nights, weekends, hours, overtime, workload fairness, shortages, coverage, occupancy, costs, and runtime.

Undefined ratios return JSON `null` with an explanatory status. Missing solutions never become zero-valued results.

### Phase 8 — Application services and API

**Dependencies:** Phase 1 contracts; Phase 7 integration.  
**Owners:** M5/M6.

**Deliverables:** Shared application services, versioned endpoints, generated frontend types, local job execution, status polling, downloads, restart handling, and documented CLI/API usage.

Persist completed method results immediately. Mark interrupted jobs after restart and allow explicit reruns; do not silently resume or duplicate experiments.

**Validation gate:** API tests cover invalid configurations, missing artifacts, duplicate execution requests, queued/running/partial/failed jobs, and restart recovery. Read-only operations never invoke solvers. Downloads resolve only registered artifacts.

### Phase 9 — Dashboard and interactive comparison

**Dependencies:** Phase 1 fixtures permit early development; Phases 7–8 supply live results.  
**Owner:** M6.

**Deliverables:** All eight specified pages and eight mandatory visualizations, including individual schedules, historical/forecast charts, method KPI comparisons, shortage heatmaps, sensitivity curves, opened-bed/occupancy comparisons, and cost/coverage scatter plots.

Display configuration, synthetic assumptions, units, solver status, and validation findings. Identify nondominated observed results only within comparable valid runs; this does not introduce a multiobjective optimization extension.

**Validation gate:** Browser tests cover a successful workflow, partial failure, infeasibility, undefined metrics, scenario comparisons, and exports. Displayed totals match persisted results. Filtering and navigation submit no computation requests. Charts remain usable at narrower widths and do not fail during server rendering.

### Phase 10 — Release, report, and reproducible demonstration

**Dependencies:** Phases 2–9.  
**Owners:** All members.

**Deliverables:** Installation and Windows launch instructions; mathematical model; data dictionary; experiment protocol; assumptions and limitations; verified references and concise literature review; comparison report; exported figures; demonstration configuration; final acceptance evidence.

Provide a short demonstration profile with five-second exact-method limits and saved full-benchmark results. Keep benchmark results clearly associated with their actual budgets.

**Validation gate:** A clean environment can install locked dependencies, generate and validate data, compare forecasts, execute all three planning methods, run scenarios and sensitivity, launch the dashboard, and export results. After installation, the demonstration runs without network access or hospital-system access. All required checks pass.

## 4. Verification, coverage, and implementation risks

| Mandatory requirement | Delivery evidence |
|---|---|
| Synthetic, configurable, reproducible data and automated quality checks | Phases 1–2 |
| Admissions/occupancy separation and operational translation | Phases 2 and 4 |
| Five models, chronological evaluation, service/horizon metrics | Phase 3 |
| Aggregate beds and qualified individual scheduling | Phases 4–6 |
| Three methods on identical inputs and constraints | Phases 6–7 |
| Independent validation and correct feasibility/status handling | Phases 5–8 |
| Demand, absence, capacity, and combined scenarios | Phase 7 |
| Consistent KPI, sensitivity analysis, and exports | Phase 7 |
| Dashboard comparisons and all required visuals | Phase 9 |
| Tests, assumptions, documentation, report, reproducible demo | Phase 10 |

Required edge cases include zero demand, no available staff, all beds closed, missing qualifications, multi-qualified staff, excess demand, very high absence, short history, malformed configuration, cross-midnight rest conflicts, solver errors, timeouts, and proven infeasibility.

Add explicit regression checks for:

- Daily admissions being incorrectly substituted for occupancy.
- Opening beds supported by only some required shifts or roles.
- Forecast leakage from future observations.
- Scenario mutations contaminating baseline experiments.
- Greedy failure being mislabeled as proven infeasibility.
- Invalid or incomparable results entering rankings or Pareto displays.

| Risk | Mitigation |
|---|---|
| Joint modeling exceeds four-week effort | Freeze common constraints early; deliver greedy pipeline first; develop solver adapters independently |
| MILP and CP-SAT drift mathematically | Shared fixtures, independent objective recomputation, and optimum comparisons on tiny instances |
| Synthetic parameters create a permanently infeasible baseline | Calibrate baseline separately from stress cases and retain conservation checks |
| Full sensitivity workload is expensive | Explicit batch execution, persisted progress, and separate demo budgets |
| Reproducibility is overstated | Guarantee deterministic inputs/heuristic; record solver versions, seeds, threads, hardware, and budgets; allow alternate optima and timeout variation |
| Library or binary incompatibility | Isolated environments, locked versions, Windows solver smoke tests before feature development |
| Frontend/API integration slips | Agree contracts in Phase 1 and develop against fixtures |

The full grid entails 160 exact solves. At 30 seconds each, the configured solver-time allowance alone is approximately **80 minutes**, plus model building and other processing. This is a workload estimate, not a benchmark result.

## 5. Schedule, defaults, and deferred work

| Week | Exit milestone | Parallel ownership |
|---|---|---|
| 1 | Contracts frozen; generated data validated; solver installation verified | M1 data; M2 forecasting; M3/M4 model and validation fixtures; M5 experiment contracts; M6 interface/API fixtures |
| 2 | Complete forecast-to-greedy CLI pipeline with independent validation | M1 calibration; M2 evaluation; M3 operational translation/MILP; M4 greedy/validator; M5 scenarios/storage; M6 dashboard |
| 3 | All three methods integrated on common scenarios | M3 MILP; M4 CP-SAT; M5 experiments/API; M6 live interface; M1/M2 integration support |
| 4 | Sensitivity results, complete dashboard, passing acceptance checks, report and demo | All members |

Defaults are a seven-day horizon, 1,095 historical days, seed 42, and capacities URG 40 / MED 100 / REA 30 / CHI 130. Use explicit historical dates in the demonstration configuration rather than an implicit current-date dependency.

All staffing ratios, stay durations, costs, priorities, and working-time parameters are configurable synthetic assumptions. Contractual hours are hard limits in the baseline, so simulated overtime is zero unless an explicitly configured extension changes that policy.

PostgreSQL, predictive intervals, Excel workbooks, individual patient records, discrete-event simulation, gradient boosting, metaheuristics, multiobjective search, and distributed infrastructure remain deferred. Mandatory acceptance requirements are not removed to preserve optional work.

Delivery requires recorded acceptance evidence; it does not require an advanced forecast to beat the naïve baseline or an exact method to prove optimality on every large stress instance.

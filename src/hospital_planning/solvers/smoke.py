"""Tests de fumée sans modèle de planification métier."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SolverSmokeResult:
    """Résultat compact et sérialisable d'une vérification de solveur."""

    solver: str
    status: str
    objective_value: int


def solve_pulp_smoke_problem() -> SolverSmokeResult:
    """Résout un minuscule MILP afin de vérifier PuLP et CBC."""
    import pulp

    problem = pulp.LpProblem("phase1_smoke", pulp.LpMinimize)
    decision = problem.add_variable("decision", lowBound=0, upBound=1, cat="Binary")
    problem += decision
    problem += decision >= 1
    stats = problem.solve(pulp.COIN_CMD(msg=False))
    status = stats.status_str
    if status.lower() not in {"optimal", "optimal solution found"}:
        raise RuntimeError(f"CBC n'a pas résolu le problème de fumée: {status}")
    return SolverSmokeResult(
        solver="pulp_cbc",
        status="OPTIMAL",
        objective_value=int(pulp.value(decision)),
    )


def solve_cp_sat_smoke_problem() -> SolverSmokeResult:
    """Résout un minuscule CP-SAT afin de vérifier OR-Tools."""
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    decision = model.new_bool_var("decision")
    model.add(decision == 1)
    model.minimize(decision)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(f"CP-SAT n'a pas résolu le problème de fumée: {solver.status_name(status)}")
    return SolverSmokeResult(
        solver="cp_sat",
        status="OPTIMAL",
        objective_value=solver.value(decision),
    )

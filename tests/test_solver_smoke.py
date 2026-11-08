"""Vérifications d'installation des solveurs requis par la phase 1."""

from hospital_planning.solvers.smoke import solve_cp_sat_smoke_problem, solve_pulp_smoke_problem


def test_pulp_cbc_solves_a_tiny_milp() -> None:
    result = solve_pulp_smoke_problem()
    assert (result.solver, result.status, result.objective_value) == ("pulp_cbc", "OPTIMAL", 1)


def test_cp_sat_solves_a_tiny_integer_problem() -> None:
    result = solve_cp_sat_smoke_problem()
    assert (result.solver, result.status, result.objective_value) == ("cp_sat", "OPTIMAL", 1)

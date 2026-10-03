import pytest
from fastapi.testclient import TestClient

from solver_app.equations import EquationInputError, solve_equation
from solver_app.main import app


client = TestClient(app)


def test_solves_linear_equation_with_steps() -> None:
    result = solve_equation("2x + 3 = 7")

    assert result["status"] == "solved"
    assert result["degree"] == 1
    assert result["solutions"] == ["2"]
    assert len(result["steps"]) == 2


def test_solves_quadratic_with_real_roots() -> None:
    result = solve_equation("x^2 - 5x + 6 = 0")

    assert result["degree"] == 2
    assert result["solutions"] == ["2", "3"]
    assert any("discriminant" in step.lower() for step in result["steps"])


def test_solves_quadratic_with_complex_roots() -> None:
    result = solve_equation("x^2 + 4 = 0")

    assert result["solutions"] == ["-2*I", "2*I"]


def test_reports_identity_and_inconsistent_equations() -> None:
    identity = solve_equation("x + 1 = x + 1")
    contradiction = solve_equation("x + 1 = x + 2")

    assert identity["status"] == "all_reals"
    assert contradiction["status"] == "no_solution"


@pytest.mark.parametrize("equation", ["x / x = 1", "1 / (x - 1) = 0", "x / (x - x + 1) = 1"])
def test_rejects_variable_denominators_before_simplification(equation: str) -> None:
    with pytest.raises(EquationInputError, match="Variable denominators"):
        solve_equation(equation)


def test_rejects_nested_powers_before_building_large_intermediates() -> None:
    expression = "2"
    for _ in range(9):
        expression = f"({expression})^8"

    with pytest.raises(EquationInputError, match="excessively large intermediate"):
        solve_equation(f"{expression} * x = 0")


def test_bounds_power_growth_for_scientific_notation_constants() -> None:
    with pytest.raises(EquationInputError, match="excessively large intermediate"):
        solve_equation("1e308^8 * x = 0")


@pytest.mark.parametrize(
    "equation",
    [
        "",
        "x =",
        "x + 1",
        "x^3 = 1",
        "x^9 = 1",
        "1 / 0 = x",
        "__import__('os') = 0",
        "x.__class__ = 0",
    ],
)
def test_rejects_malformed_and_unsupported_equations(equation: str) -> None:
    with pytest.raises(EquationInputError):
        solve_equation(equation)


def test_api_readiness_and_browser_are_served() -> None:
    assert client.get("/api/ready").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200
    assert "Solve an equation, step by step." in page.text


def test_api_solves_equation_and_returns_validation_errors() -> None:
    response = client.post("/api/solve", json={"equation": "x^2 + 4 = 0"})
    invalid = client.post("/api/solve", json={"equation": "x ="})
    invalid_domain = client.post("/api/solve", json={"equation": "x / x = 1"})

    expression = "2"
    for _ in range(9):
        expression = f"({expression})^8"
    excessive = client.post(
        "/api/solve",
        json={"equation": f"{expression} * x = 0"},
    )

    assert response.status_code == 200
    assert response.json()["solutions"] == ["-2*I", "2*I"]
    assert invalid.status_code == 422
    assert "detail" in invalid.json()
    assert invalid_domain.status_code == 422
    assert excessive.status_code == 422

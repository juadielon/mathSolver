import string

import pytest
from fastapi.testclient import TestClient

from solver_app.main import app


client = TestClient(app)


@pytest.mark.parametrize("variable", string.ascii_letters)
def test_differentiates_every_single_letter_variable(variable: str) -> None:
    result = operate({
        "operation": "differentiate", "expression": f"2{variable}^2",
        "variable": variable,
    })
    assert result["variable"] == variable
    assert result["result"] == f"4*{variable}"
    if variable != "E":
        inferred = operate({"operation": "differentiate", "expression": f"{variable}^2"})
        assert inferred["variable"] == variable
        assert inferred["result"] == f"2*{variable}"


def test_preserves_constants_and_allows_explicit_euler_variable() -> None:
    constant = operate({"operation": "differentiate", "expression": "E*A + pi"})
    selected = operate({
        "operation": "differentiate", "expression": "E^2 + pi", "variable": "E",
    })
    assert constant["variable"] == "A"
    assert constant["result"] == "E"
    assert selected["result"] == "2*E"
    assert operate({"operation": "integrate", "expression": "E"})["antiderivative"] == "E*x"
    assert operate({
        "operation": "integrate", "expression": "Q", "lower": "0", "upper": "E",
    })["result"] == "exp(2)/2"


def test_inference_retains_cancelled_variables_and_requires_unambiguous_selection() -> None:
    cancelled = operate({"operation": "differentiate", "expression": "A-A"})
    polynomial = operate({"operation": "polynomial_solve", "equation": "B-B=0"})
    assert cancelled["variable"] == "A"
    assert cancelled["result"] == "0"
    assert polynomial["variable"] == "B"
    assert polynomial["status"] == "all_values"
    ambiguous = client.post(
        "/api/operate", json={"operation": "differentiate", "expression": "A+B"},
    )
    assert ambiguous.status_code == 422
    assert "explicitly" in ambiguous.json()["detail"]
    explicit = operate({
        "operation": "differentiate", "expression": "A*B", "variable": "B",
    })
    assert explicit["result"] == "A"


@pytest.mark.parametrize("variable", ["a", "Q", "E"])
def test_other_operations_use_selected_single_letters(variable: str) -> None:
    assert operate({
        "operation": "polynomial_solve", "equation": f"{variable}^3=8",
        "variable": variable,
    })["variable"] == variable
    assert operate({
        "operation": "exponential_solve", "equation": f"exp({variable})=3",
        "variable": variable,
    })["solutions"] == ["log(3)"]
    assert operate({
        "operation": "integrate", "expression": variable, "variable": variable,
        "lower": "0", "upper": "2",
    })["result"] == "2"
    assert operate({
        "operation": "limit", "expression": f"sin({variable})/{variable}",
        "variable": variable, "point": "0",
    })["result"] == "1"
    assert operate({
        "operation": "trig_solve", "equation": f"sin({variable})=0", "variable": variable,
    })["variable"] == variable
    assert operate({
        "operation": "trig_simplify",
        "expression": f"sin({variable})^2+cos({variable})^2", "variable": variable,
    })["result"] == "1"


def test_system_log_and_matrix_operations_accept_new_letters_without_changing_constants() -> None:
    system = operate({
        "operation": "system_solve", "equations": ["A+b=3", "A-b=1"],
    })
    assert system["variables"] == ["A", "b"]
    assert system["solutions"] == [["2", "1"]]
    euler_system = operate({
        "operation": "system_solve", "equations": ["E+Q=3", "E-Q=1"], "variable": "E",
    })
    assert euler_system["variables"] == ["E", "Q"]
    assert euler_system["solutions"] == [["2", "1"]]
    assert operate({"operation": "log_expand", "expression": "log(A*b)"})[
        "transformed"
    ] == "log(A) + log(b)"
    assert operate({
        "operation": "matrix_determinant", "matrix": [["A", 0], [0, "E"]],
    })["result"] == "E*A"
    assert operate({
        "operation": "differentiate", "expression": "1e+3A + 0x1A",
    })["result"] == "1000"


def test_implicit_products_and_cancelled_system_variables_are_preserved() -> None:
    assert operate({
        "operation": "differentiate", "expression": "A(A+1)",
    })["result"] == "2*A + 1"
    assert operate({
        "operation": "differentiate", "expression": "(A+1)A",
    })["result"] == "2*A + 1"
    assert operate({
        "operation": "differentiate", "expression": "(J+1)2J",
    })["result"] == "4*J + 2"
    assert operate({
        "operation": "differentiate", "expression": "2E*A + 2pi",
    })["result"] == "2*E"
    system = operate({
        "operation": "system_solve", "equations": ["A-A+B=1", "B=1"],
    })
    assert system["variables"] == ["A", "B"]
    assert system["solutions"] == [["A", "1"]]


def test_inferred_ode_and_euler_constant_in_system() -> None:
    result = operate({
        "operation": "ode_solve", "equation": "Derivative(F(Q), Q)+F(Q)=0",
    })
    assert result["variable"] == "Q"
    constant = operate({
        "operation": "system_solve", "equations": ["A=E", "A=E"],
    })
    assert constant["variables"] == ["A"]
    assert constant["solutions"] == [["E"]]


@pytest.mark.parametrize(
    ("dependent", "independent"),
    [("f", "r"), ("G", "T"), ("E", "Q"), ("F", "E")],
)
def test_ode_accepts_single_letter_dependent_and_independent_names(
    dependent: str, independent: str
) -> None:
    result = operate({
        "operation": "ode_solve",
        "equation": f"Derivative({dependent}({independent}), {independent}) + {dependent}({independent}) = 0",
        "variable": independent,
    })
    assert result["variable"] == independent
    assert result["dependent_variable"] == dependent
    assert result["solutions"] == [f"Eq({dependent}({independent}), C1*exp(-{independent}))"]


@pytest.mark.parametrize("equation", [
    "Derivative(f(Q), Q, Q) + f(Q) = 0",
    "Derivative(f(Q), A) + f(Q) = 0",
    "Derivative(f(Q), Q) + g(Q) = 0",
    "Derivative(foo(Q), Q) + foo(Q) = 0",
    "Derivative(f(Q), Q) + A*f(Q) = 0",
])
def test_generalised_ode_keeps_first_order_and_name_restrictions(equation: str) -> None:
    response = client.post("/api/operate", json={"operation": "ode_solve", "equation": equation})
    assert response.status_code == 422


@pytest.mark.parametrize("variable", ["", "ab", "x1", "_", "é", "π", "A\n", 1, True])
def test_rejects_invalid_selected_variable_names(variable: object) -> None:
    response = client.post("/api/operate", json={
        "operation": "differentiate", "expression": "x", "variable": variable,
    })
    assert response.status_code == 422


@pytest.mark.parametrize("expression", [
    "foo(A)", "gamma(A)", "sinus(A)", "a_b", "AA", "\uff21", "\u212a", "\uff53\uff49\uff4e(A)",
])
def test_rejects_unsupported_function_and_symbol_names(expression: str) -> None:
    response = client.post("/api/operate", json={
        "operation": "differentiate", "expression": expression,
    })
    assert response.status_code == 422


def operate(payload: dict[str, object]):
    response = client.post("/api/operate", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_solves_higher_degree_polynomial_and_linear_system() -> None:
    polynomial = operate(
        {"operation": "polynomial_solve", "equation": "x^3 - 6x^2 + 11x - 6 = 0"}
    )
    system = operate(
        {"operation": "system_solve", "equations": ["x + y = 3", "x - y = 1"]}
    )

    assert polynomial["degree"] == 3
    assert polynomial["solutions"] == ["1", "2", "3"]
    assert system["variables"] == ["x", "y"]
    assert system["solutions"] == [["2", "1"]]


def test_expands_and_condenses_logarithms() -> None:
    expanded = operate({"operation": "log_expand", "expression": "log(x*y)"})
    condensed = operate({"operation": "log_condense", "expression": "log(x) + log(y)"})

    assert expanded["transformed"] == "log(x) + log(y)"
    assert condensed["transformed"] == "log(x*y)"
    assert "positive real" in expanded["steps"][1]


def test_solves_exponential_equation() -> None:
    result = operate({"operation": "exponential_solve", "equation": "exp(x) = 3"})

    assert result["solutions"] == ["log(3)"]


def test_rejects_exponential_equations_with_infinite_periodic_solutions() -> None:
    response = client.post(
        "/api/operate",
        json={"operation": "exponential_solve", "equation": "exp(sin(x)) = 1"},
    )

    assert response.status_code == 422
    assert "infinitely many solutions" in response.json()["detail"]


def test_rejects_nested_numeric_powers_before_large_intermediates() -> None:
    response = client.post(
        "/api/operate",
        json={
            "operation": "differentiate",
            "expression": "(((2**32*x)**32)**32)**32",
        },
    )

    assert response.status_code == 422
    assert "excessively large intermediate" in response.json()["detail"]


def test_allows_bounded_nested_powers_with_symbolic_bases() -> None:
    result = operate(
        {"operation": "differentiate", "expression": "((2*x)^2)^2"}
    )

    assert result["result"] == "64*x**3"


def test_differentiates_with_product_and_chain_rules() -> None:
    result = operate({"operation": "differentiate", "expression": "x^2 * sin(x)"})
    second_derivative = operate(
        {"operation": "differentiate", "expression": "x^3", "order": 2}
    )

    assert result["result"] == "x**2*cos(x) + 2*x*sin(x)"
    assert any("product, quotient, and chain" in step for step in result["steps"])
    assert second_derivative["result"] == "6*x"


def test_computes_definite_and_indefinite_integrals() -> None:
    indefinite = operate({"operation": "integrate", "expression": "x * exp(x)"})
    substitution = operate(
        {"operation": "integrate", "expression": "2*x*cos(x^2)"}
    )
    definite = operate(
        {"operation": "integrate", "expression": "x", "lower": "0", "upper": "1"}
    )

    assert indefinite["antiderivative"] == "(x - 1)*exp(x)"
    assert substitution["antiderivative"] == "sin(x**2)"
    assert definite["result"] == "1/2"
    assert indefinite["definite"] is False
    assert definite["definite"] is True


def test_limit_reports_lhopitals_rule_for_zero_over_zero() -> None:
    result = operate({"operation": "limit", "expression": "sin(x)/x", "point": "0"})

    assert result["result"] == "1"
    assert any("L'Hôpital's Rule" in step for step in result["steps"])


def test_solves_first_order_ode() -> None:
    result = operate(
        {
            "operation": "ode_solve",
            "equation": "Derivative(y(x), x) + y(x) = 0",
        }
    )

    assert result["solutions"] == ["Eq(y(x), C1*exp(-x))"]


def test_solves_trigonometric_equation_and_simplifies_identity() -> None:
    solved = operate({"operation": "trig_solve", "equation": "sin(x) = 0"})
    simplified = operate(
        {"operation": "trig_simplify", "expression": "sin(x)^2 + cos(x)^2"}
    )

    assert "ImageSet" in solved["solution_set"]
    assert simplified["result"] == "1"


def test_matrix_determinant_rref_and_inverse() -> None:
    matrix = [[1, 2], [3, 4]]
    determinant = operate({"operation": "matrix_determinant", "matrix": matrix})
    rref = operate({"operation": "matrix_rref", "matrix": matrix})
    inverse = operate({"operation": "matrix_inverse", "matrix": matrix})

    assert determinant["result"] == "-2"
    assert rref["result"] == [["1", "0"], ["0", "1"]]
    assert inverse["result"] == [["-2", "1"], ["3/2", "-1/2"]]


def test_rejects_malformed_or_unsupported_operation_input() -> None:
    malformed_expression = client.post(
        "/api/operate",
        json={"operation": "differentiate", "expression": "__import__('os').system('id')"},
    )
    unsupported_input = client.post(
        "/api/operate",
        json={"operation": "matrix_inverse", "matrix": [[1, 2], [2, 4]]},
    )
    invalid_operation = client.post(
        "/api/operate",
        json={"operation": "integrate", "expression": "x", "unexpected": True},
    )

    assert malformed_expression.status_code == 422
    assert unsupported_input.status_code == 422
    assert invalid_operation.status_code == 422
    assert "detail" in malformed_expression.json()
    assert "detail" in unsupported_input.json()
    assert "detail" in invalid_operation.json()


def test_operation_validation_errors_are_explicit() -> None:
    response = client.post(
        "/api/operate",
        json={"operation": "system_solve", "equations": ["x + y^2 = 1", "x - y = 0"]},
    )

    assert response.status_code == 422
    assert "linear" in response.json()["detail"]


def test_operation_api_and_browser_controls_are_available() -> None:
    response = client.post(
        "/api/operate",
        json={"operation": "polynomial_solve", "equation": "x^3 - 1 = 0"},
    )
    page = client.get("/")

    assert response.status_code == 200
    assert "polynomial_solve" == response.json()["operation"]
    assert 'id="operation"' in page.text
    assert 'id="matrix"' in page.text

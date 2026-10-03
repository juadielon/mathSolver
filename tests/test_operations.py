from fastapi.testclient import TestClient

from solver_app.main import app


client = TestClient(app)


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

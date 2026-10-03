from collections.abc import Callable
from typing import Any

import sympy as sp

from solver_app.equations import EquationInputError, _parse_expression


_VARIABLE_NAMES = {"x", "y", "z", "t"}


def _parse(source: str, variables: set[str] | None = None) -> sp.Expr:
    if not source or not source.strip():
        raise EquationInputError("Enter a mathematical expression.")
    if len(source) > 512:
        raise EquationInputError("Expressions must be 512 characters or fewer.")
    return _parse_expression(
        source,
        allowed_variables=variables or _VARIABLE_NAMES,
        allow_functions=True,
    )


def _parse_equation(equation: str) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    if not equation or not equation.strip():
        raise EquationInputError("Enter an equation.")
    if len(equation) > 512:
        raise EquationInputError("Equations must be 512 characters or fewer.")
    if equation.count("=") != 1:
        raise EquationInputError("Enter exactly one equals sign in the equation.")
    left_source, right_source = equation.split("=", maxsplit=1)
    if not left_source.strip() or not right_source.strip():
        raise EquationInputError("Enter an expression on both sides of the equals sign.")
    left = _parse(left_source)
    right = _parse(right_source)
    return left, right, left - right


def _variable(expression: sp.Expr, name: str, require_present: bool = True) -> sp.Symbol:
    if name not in _VARIABLE_NAMES:
        raise EquationInputError("Choose x, y, z, or t as the variable.")
    variable = sp.Symbol(name)
    if require_present and variable not in expression.free_symbols:
        raise EquationInputError(f"The expression does not contain {name}.")
    return variable


def _result(operation: str, value: Any, steps: list[str], **details: Any) -> dict[str, Any]:
    return {"operation": operation, "result": value, "steps": steps, **details}


def _solve_polynomial(request: dict[str, Any]) -> dict[str, Any]:
    equation = request.get("equation")
    if not isinstance(equation, str):
        raise EquationInputError("This operation requires an equation string.")
    _, _, expression = _parse_equation(equation)
    variable = _variable(expression, request.get("variable", "x"), require_present=False)
    try:
        polynomial = sp.Poly(expression, variable)
    except (sp.PolynomialError, ValueError) as error:
        raise EquationInputError("The equation must be polynomial in the selected variable.") from error
    if polynomial.is_zero:
        return _result(
            "polynomial_solve",
            "all values",
            ["Both sides are equal for every value of the selected variable."],
            equation=equation,
            variable=str(variable),
            solutions=[],
            status="all_values",
        )
    degree = polynomial.degree()
    if degree > 8:
        raise EquationInputError("Polynomial equations are supported through degree 8.")
    solutions = sp.solve(polynomial.as_expr(), variable)
    return _result(
        "polynomial_solve",
        [sp.sstr(solution) for solution in solutions] or "no solution",
        [
            f"Move all terms to one side: {sp.sstr(polynomial.as_expr())} = 0.",
            f"Solve the degree-{degree} polynomial for {variable}.",
        ],
        equation=equation,
        variable=str(variable),
        degree=degree,
        solutions=[sp.sstr(solution) for solution in solutions],
        status="solved" if solutions else "no_solution",
    )


def _solve_system(request: dict[str, Any]) -> dict[str, Any]:
    equations = request.get("equations")
    if not isinstance(equations, list) or not 1 < len(equations) <= 8:
        raise EquationInputError("Enter between 2 and 8 linear equations.")
    if not all(isinstance(equation, str) for equation in equations):
        raise EquationInputError("Each system equation must be a string.")
    expressions = [_parse_equation(equation)[2] for equation in equations]
    variables = set().union(*(expression.free_symbols for expression in expressions))
    if not variables or len(variables) > 8:
        raise EquationInputError("A system must contain between 1 and 4 variables (x, y, z, or t).")
    ordered_variables = sorted(variables, key=lambda symbol: symbol.name)
    for expression in expressions:
        try:
            polynomial = sp.Poly(expression, *ordered_variables)
        except sp.PolynomialError as error:
            raise EquationInputError("Every system equation must be linear.") from error
        if polynomial.total_degree() > 1:
            raise EquationInputError("Every system equation must be linear.")

    solution_set = sp.linsolve(expressions, ordered_variables)
    if solution_set is sp.EmptySet:
        values: list[list[str]] = []
        status = "no_solution"
        summary = "The system is inconsistent and has no solution."
    else:
        values = [
            [sp.sstr(value) for value in solution]
            for solution in solution_set
        ]
        status = "solved"
        summary = values
    return _result(
        "system_solve",
        summary,
        [
            "Write each equation as a linear expression equal to zero.",
            f"Solve the simultaneous system for {', '.join(map(str, ordered_variables))}.",
        ],
        variables=[str(variable) for variable in ordered_variables],
        solutions=values,
        status=status,
    )


def _log_transform(request: dict[str, Any], expand: bool) -> dict[str, Any]:
    expression_text = request.get("expression")
    if not isinstance(expression_text, str):
        raise EquationInputError("This operation requires an expression string.")
    expression = _parse(expression_text)
    if not expression.has(sp.log):
        raise EquationInputError("The expression must contain a logarithm.")
    transformed = (
        sp.expand_log(expression, force=True)
        if expand
        else sp.logcombine(expression, force=True)
    )
    operation = "log_expand" if expand else "log_condense"
    wording = "Expand" if expand else "Condense"
    return _result(
        operation,
        sp.sstr(transformed),
        [
            f"{wording} logarithms using logarithm rules: {sp.sstr(expression)} → {sp.sstr(transformed)}.",
            "These identities assume positive real log arguments.",
        ],
        expression=sp.sstr(expression),
        transformed=sp.sstr(transformed),
    )


def _solve_exponential(request: dict[str, Any]) -> dict[str, Any]:
    equation = request.get("equation")
    if not isinstance(equation, str):
        raise EquationInputError("This operation requires an equation string.")
    _, _, expression = _parse_equation(equation)
    variable = _variable(expression, request.get("variable", "x"))
    powers_with_variable_exponent = [
        power for power in expression.atoms(sp.Pow) if power.exp.has(variable)
    ]
    if not expression.has(sp.exp) and not powers_with_variable_exponent:
        raise EquationInputError("The equation must contain an exponential term.")
    exponential_arguments = [
        exponential.args[0] for exponential in expression.atoms(sp.exp)
    ]
    if any(
        argument.has(variable) and argument.has(sp.sin, sp.cos, sp.tan)
        for argument in [
            *(power.exp for power in powers_with_variable_exponent),
            *exponential_arguments,
        ]
    ):
        raise EquationInputError(
            "Exponential equations with periodic exponents may have infinitely many "
            "solutions and are not supported."
        )
    solutions = sp.solveset(expression, variable, domain=sp.S.Reals)
    if solutions is sp.S.EmptySet:
        solution_values = []
    elif isinstance(solutions, sp.FiniteSet):
        solution_values = list(solutions)
    else:
        raise EquationInputError(
            "Only finite real solution sets are supported for exponential equations."
        )
    solution_text = [sp.sstr(solution) for solution in solution_values]
    return _result(
        "exponential_solve",
        solution_text,
        [
            f"Rearrange the equation as {sp.sstr(expression)} = 0.",
            f"Solve over the real numbers for {variable}: {', '.join(solution_text) or 'no real solutions'}.",
        ],
        equation=equation,
        variable=str(variable),
        solutions=solution_text,
        status="solved" if solution_text else "no_solution",
    )


def _differentiate(request: dict[str, Any]) -> dict[str, Any]:
    expression_text = request.get("expression")
    if not isinstance(expression_text, str):
        raise EquationInputError("This operation requires an expression string.")
    expression = _parse(expression_text)
    variable = _variable(expression, request.get("variable", "x"))
    order = request.get("order", 1)
    if not isinstance(order, int) or isinstance(order, bool) or not 1 <= order <= 10:
        raise EquationInputError("Derivative order must be an integer from 1 to 10.")
    derivative = sp.diff(expression, variable, order)
    rule = "The product, quotient, and chain rules are applied where needed."
    return _result(
        "differentiate",
        sp.sstr(derivative),
        [
            f"Differentiate {sp.sstr(expression)} with respect to {variable}, {order} time(s).",
            rule,
            f"Result: {sp.sstr(derivative)}.",
        ],
        expression=sp.sstr(expression),
        variable=str(variable),
        order=order,
    )


def _integrate(request: dict[str, Any]) -> dict[str, Any]:
    expression_text = request.get("expression")
    if not isinstance(expression_text, str):
        raise EquationInputError("This operation requires an expression string.")
    expression = _parse(expression_text)
    variable = _variable(expression, request.get("variable", "x"))
    lower_source, upper_source = request.get("lower"), request.get("upper")
    definite = lower_source is not None or upper_source is not None
    if definite and (lower_source is None or upper_source is None):
        raise EquationInputError("Provide both lower and upper bounds for a definite integral.")
    steps = [
        f"Integrate {sp.sstr(expression)} with respect to {variable}.",
        "Symbolic integration uses substitution or integration by parts when those methods apply.",
    ]
    if definite:
        lower = _parse_bound(lower_source)
        upper = _parse_bound(upper_source)
        value = sp.integrate(expression, (variable, lower, upper))
        if value.has(sp.Integral):
            raise EquationInputError("SymPy could not evaluate this definite integral in closed form.")
        steps.append(f"Evaluate the antiderivative from {sp.sstr(lower)} to {sp.sstr(upper)}.")
        steps.append(f"Result: {sp.sstr(value)}.")
        return _result(
            "integrate",
            sp.sstr(value),
            steps,
            expression=sp.sstr(expression),
            variable=str(variable),
            definite=True,
            lower=sp.sstr(lower),
            upper=sp.sstr(upper),
        )
    antiderivative = sp.integrate(expression, variable)
    if antiderivative.has(sp.Integral):
        raise EquationInputError("SymPy could not find a closed-form antiderivative for this expression.")
    steps.extend(
        [
            f"Add the constant of integration: {sp.sstr(antiderivative)} + C.",
            "Differentiating the antiderivative recovers the integrand.",
        ]
    )
    return _result(
        "integrate",
        f"{sp.sstr(antiderivative)} + C",
        steps,
        expression=sp.sstr(expression),
        variable=str(variable),
        definite=False,
        antiderivative=sp.sstr(antiderivative),
    )


def _parse_bound(source: Any) -> sp.Expr:
    if not isinstance(source, str):
        raise EquationInputError("Integral bounds must be numeric strings.")
    bound = _parse(source)
    if bound.free_symbols:
        raise EquationInputError("Integral bounds must not contain variables.")
    return bound


def _limit(request: dict[str, Any]) -> dict[str, Any]:
    expression_text = request.get("expression")
    point_source = request.get("point")
    if not isinstance(expression_text, str) or not isinstance(point_source, str):
        raise EquationInputError("A limit requires expression and point strings.")
    expression = _parse(expression_text)
    variable = _variable(expression, request.get("variable", "x"))
    point = _parse_bound(point_source)
    direction = request.get("direction", "both")
    if direction not in {"both", "+", "-"}:
        raise EquationInputError("Limit direction must be 'both', '+', or '-'.")
    sympy_direction = "+-" if direction == "both" else direction
    numerator, denominator = sp.fraction(sp.together(expression))
    steps = [f"Evaluate the limit of {sp.sstr(expression)} as {variable} approaches {sp.sstr(point)}."]
    if denominator != 1:
        current_numerator = numerator
        current_denominator = denominator
        for _ in range(10):
            if not (
                current_numerator.subs(variable, point).is_zero
                and current_denominator.subs(variable, point).is_zero
            ):
                break
            top_derivative = sp.diff(current_numerator, variable)
            bottom_derivative = sp.diff(current_denominator, variable)
            if top_derivative == 0 or bottom_derivative == 0:
                break
            steps.append(
                "The current ratio is indeterminate (0/0), so apply L'Hôpital's Rule "
                f"to differentiate the numerator and denominator: {sp.sstr(top_derivative)} / "
                f"{sp.sstr(bottom_derivative)}."
            )
            current_numerator = top_derivative
            current_denominator = bottom_derivative
    value = sp.limit(expression, variable, point, dir=sympy_direction)
    if isinstance(value, sp.Limit) or value.has(sp.Limit):
        raise EquationInputError("SymPy could not evaluate this limit.")
    steps.append(f"The limit is {sp.sstr(value)}.")
    return _result(
        "limit",
        sp.sstr(value),
        steps,
        expression=sp.sstr(expression),
        variable=str(variable),
        point=sp.sstr(point),
        direction=direction,
    )


def _solve_ode(request: dict[str, Any]) -> dict[str, Any]:
    equation = request.get("equation")
    if not isinstance(equation, str):
        raise EquationInputError("This operation requires an equation string.")
    _, _, expression = _parse_equation(equation)
    dependent_functions = expression.atoms(sp.core.function.AppliedUndef)
    if len(dependent_functions) != 1:
        raise EquationInputError("Use one dependent function, written as y(x), in the first-order ODE.")
    function = next(iter(dependent_functions))
    if len(function.args) != 1 or not isinstance(function.args[0], sp.Symbol):
        raise EquationInputError("Write the dependent function with one variable, such as y(x).")
    derivatives = expression.atoms(sp.Derivative)
    if not derivatives or any(derivative.expr != function or derivative.derivative_count != 1 for derivative in derivatives):
        raise EquationInputError("Only first-order derivatives of the dependent function are supported.")
    if any(derivative.variables != (function.args[0],) for derivative in derivatives):
        raise EquationInputError("Differentiate the dependent function with respect to its argument.")
    try:
        solution = sp.dsolve(sp.Eq(expression, 0), function)
    except (NotImplementedError, ValueError, sp.SympifyError) as error:
        raise EquationInputError("SymPy could not solve this first-order ODE.") from error
    if isinstance(solution, list):
        solution_text = [sp.sstr(item) for item in solution]
    else:
        solution_text = [sp.sstr(solution)]
    return _result(
        "ode_solve",
        solution_text,
        [
            f"Identify the first-order differential equation: {sp.sstr(expression)} = 0.",
            "Solve symbolically for the dependent function, including an arbitrary constant where required.",
        ],
        equation=equation,
        solutions=solution_text,
    )


def _trig_solve(request: dict[str, Any]) -> dict[str, Any]:
    equation = request.get("equation")
    if not isinstance(equation, str):
        raise EquationInputError("This operation requires an equation string.")
    _, _, expression = _parse_equation(equation)
    variable = _variable(expression, request.get("variable", "x"))
    if not expression.has(sp.sin, sp.cos, sp.tan):
        raise EquationInputError("The equation must contain a trigonometric function.")
    solutions = sp.solveset(expression, variable, domain=sp.S.Reals)
    if isinstance(solutions, sp.ConditionSet):
        raise EquationInputError("SymPy could not solve this trigonometric equation.")
    return _result(
        "trig_solve",
        sp.sstr(solutions),
        [
            f"Solve {sp.sstr(expression)} = 0 over the real numbers.",
            "The result includes periodic solution sets when SymPy can express them.",
        ],
        equation=equation,
        variable=str(variable),
        solution_set=sp.sstr(solutions),
    )


def _trig_simplify(request: dict[str, Any]) -> dict[str, Any]:
    expression_text = request.get("expression")
    if not isinstance(expression_text, str):
        raise EquationInputError("This operation requires an expression string.")
    expression = _parse(expression_text)
    if not expression.has(sp.sin, sp.cos, sp.tan):
        raise EquationInputError("The expression must contain a trigonometric function.")
    simplified = sp.trigsimp(expression)
    return _result(
        "trig_simplify",
        sp.sstr(simplified),
        [
            f"Apply trigonometric identities to {sp.sstr(expression)}.",
            f"Simplified result: {sp.sstr(simplified)}.",
        ],
        expression=sp.sstr(expression),
    )


def _matrix(request: dict[str, Any]) -> sp.Matrix:
    entries = request.get("matrix")
    if not isinstance(entries, list) or not entries or len(entries) > 8:
        raise EquationInputError("Provide a non-empty matrix with at most 8 rows.")
    if any(not isinstance(row, list) or not row or len(row) > 8 for row in entries):
        raise EquationInputError("Each matrix row must contain between 1 and 8 entries.")
    if len({len(row) for row in entries}) != 1:
        raise EquationInputError("All matrix rows must have the same number of entries.")
    parsed_rows = []
    for row in entries:
        parsed_row = []
        for entry in row:
            if isinstance(entry, bool) or not isinstance(entry, (str, int, float)):
                raise EquationInputError("Matrix entries must be numbers or safe expression strings.")
            parsed_row.append(_parse(str(entry)))
        parsed_rows.append(parsed_row)
    return sp.Matrix(parsed_rows)


def _matrix_operation(request: dict[str, Any], operation: str) -> dict[str, Any]:
    matrix = _matrix(request)
    matrix_text = [[sp.sstr(value) for value in row] for row in matrix.tolist()]
    if operation in {"matrix_determinant", "matrix_inverse"} and matrix.rows != matrix.cols:
        raise EquationInputError("Determinants and inverses require a square matrix.")
    if operation == "matrix_determinant":
        value = matrix.det()
        result: Any = sp.sstr(value)
        steps = [f"Calculate the determinant of the {matrix.rows}×{matrix.cols} matrix: {result}."]
    elif operation == "matrix_rref":
        reduced, pivots = matrix.rref()
        result = [[sp.sstr(value) for value in row] for row in reduced.tolist()]
        steps = [f"Use elementary row operations to reduce the matrix to RREF; pivot columns: {list(pivots)}."]
    else:
        if matrix.det() == 0:
            raise EquationInputError("A singular matrix has no inverse.")
        inverse = matrix.inv()
        result = [[sp.sstr(value) for value in row] for row in inverse.tolist()]
        steps = ["Find the inverse by row reduction or exact matrix inversion."]
    return _result(
        operation,
        result,
        steps,
        matrix=matrix_text,
    )


_OPERATIONS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "polynomial_solve": _solve_polynomial,
    "system_solve": _solve_system,
    "log_expand": lambda request: _log_transform(request, expand=True),
    "log_condense": lambda request: _log_transform(request, expand=False),
    "exponential_solve": _solve_exponential,
    "differentiate": _differentiate,
    "integrate": _integrate,
    "limit": _limit,
    "ode_solve": _solve_ode,
    "trig_solve": _trig_solve,
    "trig_simplify": _trig_simplify,
    "matrix_determinant": lambda request: _matrix_operation(request, "matrix_determinant"),
    "matrix_rref": lambda request: _matrix_operation(request, "matrix_rref"),
    "matrix_inverse": lambda request: _matrix_operation(request, "matrix_inverse"),
}


def operate(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")
    handler = _OPERATIONS.get(operation) if isinstance(operation, str) else None
    if handler is None:
        supported = ", ".join(_OPERATIONS)
        raise EquationInputError(f"Choose a supported operation: {supported}.")
    try:
        return handler(request)
    except EquationInputError:
        raise
    except (ArithmeticError, NotImplementedError, sp.PolynomialError, TypeError, ValueError) as error:
        raise EquationInputError("The requested operation could not be completed for this input.") from error

import math
from typing import Any

import sympy as sp

from solver_app.equations import EquationInputError, _parse_expression


_X = sp.Symbol("x")
_MAX_DOMAIN_WIDTH = 2000
_ROOT_TOLERANCE = 1e-8


def _finite_number(value: Any) -> float | None:
    try:
        numeric = complex(value)
    except (ArithmeticError, TypeError, ValueError):
        return None
    if abs(numeric.imag) > 1e-10 or not math.isfinite(numeric.real):
        return None
    return float(numeric.real)


def _evaluate(function: Any, x_value: float) -> float | None:
    try:
        return _finite_number(function(x_value))
    except (ArithmeticError, OverflowError, TypeError, ValueError):
        return None


def _compile(expression: sp.Expr) -> Any:
    if expression == _X:
        return lambda x_value: x_value
    if expression == sp.pi:
        return lambda _x_value: math.pi
    if expression == sp.E:
        return lambda _x_value: math.e
    if expression.is_Number:
        numeric = complex(sp.N(expression, 16))
        value = numeric.real if numeric.imag == 0 else numeric
        return lambda _x_value: value
    if expression.is_Add:
        terms = [_compile(term) for term in expression.args]
        return lambda x_value: sum(term(x_value) for term in terms)
    if expression.is_Mul:
        factors = [_compile(factor) for factor in expression.args]
        return lambda x_value: math.prod(factor(x_value) for factor in factors)
    if expression.is_Pow:
        base, exponent = (_compile(argument) for argument in expression.args)
        return lambda x_value: base(x_value) ** exponent(x_value)

    functions = {
        sp.log: math.log,
        sp.exp: math.exp,
        sp.sin: math.sin,
        sp.cos: math.cos,
        sp.tan: math.tan,
        sp.asin: math.asin,
        sp.acos: math.acos,
        sp.atan: math.atan,
        sp.Abs: abs,
    }
    function = functions.get(expression.func)
    if function is not None:
        arguments = [_compile(argument) for argument in expression.args]
        return lambda x_value: function(*(argument(x_value) for argument in arguments))
    raise EquationInputError("This expression contains an unsupported graphing operation.")


def _in_domain(value: sp.Expr, lower: float, upper: float) -> float | None:
    numeric = _finite_number(sp.N(value, 16))
    if numeric is None or numeric < lower - _ROOT_TOLERANCE or numeric > upper + _ROOT_TOLERANCE:
        return None
    return min(upper, max(lower, numeric))


def _exact_roots(expression: sp.Expr, lower: float, upper: float) -> list[dict[str, Any]] | None:
    try:
        polynomial = sp.Poly(expression, _X)
    except (sp.PolynomialError, ValueError):
        return None
    if polynomial.degree() > 4:
        return None
    try:
        solutions = sp.solveset(expression, _X, domain=sp.Interval(lower, upper))
    except (ArithmeticError, NotImplementedError, ValueError, sp.PolynomialError):
        return None
    if not isinstance(solutions, sp.FiniteSet):
        return None
    markers = []
    for solution in solutions:
        numeric = _in_domain(solution, lower, upper)
        if numeric is not None and solution.is_real is not False:
            markers.append(
                {
                    "x": numeric,
                    "y": 0.0,
                    "kind": "exact_symbolic",
                    "exact_x": sp.sstr(solution),
                }
            )
    return sorted(markers, key=lambda marker: marker["x"])


def _sampled_roots(
    samples: list[dict[str, float | None]],
    function: Any,
    exact_roots: list[dict[str, Any]],
    asymptotes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []

    def add_root(x_value: float) -> None:
        if any(abs(root["x"] - x_value) < 1e-6 for root in exact_roots + markers):
            return
        markers.append(
            {
                "x": x_value,
                "y": 0.0,
                "kind": "sampled_estimate",
                "exact_x": None,
            }
        )

    for sample in samples:
        y_value = sample["y"]
        if y_value is not None and abs(y_value) < _ROOT_TOLERANCE:
            add_root(sample["x"])

    for left, right in zip(samples, samples[1:]):
        left_y, right_y = left["y"], right["y"]
        if left_y is None or right_y is None or left_y * right_y >= 0:
            continue
        if any(left["x"] < marker["x"] < right["x"] for marker in asymptotes):
            continue
        middle_y = _evaluate(function, (left["x"] + right["x"]) / 2)
        if middle_y is None or abs(middle_y) >= min(abs(left_y), abs(right_y)):
            continue
        lower, upper = left["x"], right["x"]
        lower_y = left_y
        for _ in range(48):
            middle = (lower + upper) / 2
            middle_y = _evaluate(function, middle)
            if middle_y is None:
                break
            if abs(middle_y) < 1e-13:
                lower = upper = middle
                break
            if lower_y * middle_y <= 0:
                upper = middle
            else:
                lower, lower_y = middle, middle_y
        add_root((lower + upper) / 2)
    return markers


def _extrema(
    expression: sp.Expr,
    derivative: sp.Expr,
    samples: list[dict[str, float | None]],
    lower: float,
    upper: float,
    asymptotes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    try:
        polynomial = sp.Poly(derivative, _X)
    except (sp.PolynomialError, ValueError):
        polynomial = None
    if polynomial is not None and polynomial.degree() <= 3:
        try:
            critical_points = sp.solveset(derivative, _X, domain=sp.Interval(lower, upper))
        except (ArithmeticError, NotImplementedError, ValueError, sp.PolynomialError):
            critical_points = None
        if isinstance(critical_points, sp.FiniteSet):
            markers = []
            second_derivative = sp.diff(expression, _X, 2)
            for point in critical_points:
                x_value = _in_domain(point, lower, upper)
                if x_value is None:
                    continue
                y_value = _finite_number(sp.N(expression.subs(_X, point), 16))
                curvature = _finite_number(sp.N(second_derivative.subs(_X, point), 16))
                if y_value is None or curvature is None or abs(curvature) < 1e-10:
                    continue
                markers.append(
                    {
                        "x": x_value,
                        "y": y_value,
                        "kind": "exact_symbolic",
                        "extremum": "minimum" if curvature > 0 else "maximum",
                        "exact_x": sp.sstr(point),
                        "exact_y": sp.sstr(sp.simplify(expression.subs(_X, point))),
                    }
                )
            return sorted(markers, key=lambda marker: marker["x"]), "exact_symbolic"

    markers = []
    for previous, current, following in zip(samples, samples[1:], samples[2:]):
        if any(previous["x"] < marker["x"] < following["x"] for marker in asymptotes):
            continue
        before, value, after = previous["y"], current["y"], following["y"]
        if before is None or value is None or after is None:
            continue
        if value < before and value < after:
            kind = "minimum"
        elif value > before and value > after:
            kind = "maximum"
        else:
            continue
        markers.append(
            {
                "x": current["x"],
                "y": value,
                "kind": "sampled_estimate",
                "extremum": kind,
                "exact_x": None,
                "exact_y": None,
            }
        )
    return markers, "sampled_estimate"


def _asymptotes(expression: sp.Expr, lower: float, upper: float) -> dict[str, Any]:
    markers: list[dict[str, Any]] = []
    try:
        numerator, denominator = sp.fraction(sp.together(expression))
        if denominator != 1:
            denominator_polynomial = sp.Poly(denominator, _X)
            if denominator_polynomial.degree() > 8:
                return {"status": "unsupported", "markers": [], "reason": "Denominator degree exceeds 8."}
            if denominator_polynomial.degree() > 0:
                poles = sp.solveset(
                    denominator,
                    _X,
                    domain=sp.Interval(lower, upper),
                )
                if not isinstance(poles, sp.FiniteSet):
                    return {"status": "unsupported", "markers": [], "reason": "Poles could not be enumerated exactly."}
                for pole in poles:
                    x_value = _in_domain(pole, lower, upper)
                    numerator_value = _finite_number(sp.N(numerator.subs(_X, pole), 16))
                    if x_value is None or numerator_value is None or abs(numerator_value) < 1e-12:
                        continue
                    markers.append(
                        {
                            "x": x_value,
                            "kind": "exact_symbolic",
                            "exact_x": sp.sstr(pole),
                        }
                    )

        for tangent in expression.atoms(sp.tan):
            argument = tangent.args[0]
            slope = sp.diff(argument, _X)
            if slope.has(_X) or slope == 0:
                return {"status": "unsupported", "markers": [], "reason": "Only affine tangent arguments are supported."}
            intercept = sp.simplify(argument - slope * _X)
            slope_value = _finite_number(sp.N(slope, 16))
            intercept_value = _finite_number(sp.N(intercept, 16))
            if slope_value is None or intercept_value is None:
                return {"status": "unsupported", "markers": [], "reason": "Tangent poles could not be enumerated."}
            first = math.ceil((min(slope_value * lower + intercept_value, slope_value * upper + intercept_value) - math.pi / 2) / math.pi)
            last = math.floor((max(slope_value * lower + intercept_value, slope_value * upper + intercept_value) - math.pi / 2) / math.pi)
            if last - first > 640:
                return {"status": "unsupported", "markers": [], "reason": "Too many tangent poles in the selected domain."}
            for index in range(first, last + 1):
                point = sp.simplify((sp.pi / 2 + index * sp.pi - intercept) / slope)
                x_value = _in_domain(point, lower, upper)
                if x_value is not None:
                    markers.append(
                        {
                            "x": x_value,
                            "kind": "exact_symbolic",
                            "exact_x": sp.sstr(point),
                        }
                    )
    except (ArithmeticError, NotImplementedError, ValueError, sp.PolynomialError):
        return {"status": "unsupported", "markers": [], "reason": "Asymptotes could not be determined exactly."}

    unique: dict[float, dict[str, Any]] = {}
    for marker in markers:
        unique[round(marker["x"], 10)] = marker
    return {
        "status": "exact_symbolic" if unique else "none_detected",
        "markers": sorted(unique.values(), key=lambda marker: marker["x"]),
    }


def _tangent(expression: sp.Expr, derivative: sp.Expr, x_value: float) -> dict[str, Any]:
    function = _compile(expression)
    derivative_function = _compile(derivative)
    y_value = _evaluate(function, x_value)
    slope = _evaluate(derivative_function, x_value)
    if y_value is None or slope is None:
        return {
            "x": x_value,
            "status": "unsupported",
            "reason": "The function or derivative is not finite at this point.",
        }
    point = sp.Float(x_value, 16)
    exact_y = sp.sstr(sp.simplify(expression.subs(_X, point)))
    exact_slope = sp.sstr(sp.simplify(derivative.subs(_X, point)))
    return {
        "x": x_value,
        "y": y_value,
        "slope": slope,
        "intercept": y_value - slope * x_value,
        "line": f"y = {exact_y} + ({exact_slope})*(x - {x_value:g})",
        "status": "numerical_at_requested_point",
    }


def graph_function(request: dict[str, Any]) -> dict[str, Any]:
    source = request.get("expression")
    if not isinstance(source, str) or not source.strip():
        raise EquationInputError("Enter a mathematical function of x.")
    if len(source) > 512:
        raise EquationInputError("Expressions must be 512 characters or fewer.")
    lower, upper = request.get("x_min", -10), request.get("x_max", 10)
    count = request.get("sample_count", 800)
    if isinstance(lower, bool) or isinstance(upper, bool) or not all(
        isinstance(value, (int, float)) and math.isfinite(value) for value in (lower, upper)
    ):
        raise EquationInputError("Graph bounds must be finite numbers.")
    if lower >= upper:
        raise EquationInputError("The minimum x bound must be less than the maximum x bound.")
    if upper - lower > _MAX_DOMAIN_WIDTH:
        raise EquationInputError(f"The graph domain must be {_MAX_DOMAIN_WIDTH} units wide or less.")
    if isinstance(count, bool) or not isinstance(count, int) or not 100 <= count <= 2000:
        raise EquationInputError("Sample count must be an integer from 100 to 2000.")
    tangent_points = request.get("tangent_points", [])
    if not isinstance(tangent_points, list) or len(tangent_points) > 10:
        raise EquationInputError("Request at most 10 tangent points.")
    if any(
        isinstance(point, bool)
        or not isinstance(point, (int, float))
        or not math.isfinite(point)
        or point < lower
        or point > upper
        for point in tangent_points
    ):
        raise EquationInputError("Tangent points must be finite numbers inside the graph domain.")

    try:
        expression = _parse_expression(
            source,
            allowed_variables={"x"},
            allow_functions=True,
        )
    except EquationInputError:
        raise
    if expression.has(sp.Derivative) or expression.has(sp.core.function.AppliedUndef):
        raise EquationInputError("Graph only explicit functions of x.")

    try:
        derivative = sp.diff(expression, _X)
        function = _compile(expression)
        derivative_function = _compile(derivative)
    except (
        ArithmeticError,
        NotImplementedError,
        RecursionError,
        SyntaxError,
        TypeError,
        ValueError,
        sp.SympifyError,
    ) as error:
        raise EquationInputError("This expression is outside the supported graphing range.") from error

    step = (upper - lower) / (count - 1)
    x_values = [lower + index * step for index in range(count)]
    if any(right <= left for left, right in zip(x_values, x_values[1:])):
        raise EquationInputError("The graph range is too narrow for the requested sample count.")
    samples = [
        {
            "x": x_value,
            "y": _evaluate(function, x_value),
        }
        for x_value in x_values
    ]
    if not any(sample["y"] is not None for sample in samples):
        raise EquationInputError("The function has no finite real values in the selected graph range.")
    derivative_samples = None
    if request.get("include_derivative", False):
        derivative_samples = [
            {
                "x": sample["x"],
                "y": _evaluate(derivative_function, sample["x"]),
            }
            for sample in samples
        ]

    asymptotes = _asymptotes(expression, lower, upper)
    asymptote_markers = asymptotes["markers"]
    exact_roots = _exact_roots(expression, lower, upper)
    root_markers = (
        exact_roots
        if exact_roots is not None
        else _sampled_roots(samples, function, [], asymptote_markers)
    )
    root_status = "exact_symbolic" if exact_roots is not None else "sampled_estimate"
    if exact_roots is None and not root_markers:
        root_status = "no_roots_detected"

    intercept_y = _evaluate(function, 0.0) if lower <= 0 <= upper else None
    if lower <= 0 <= upper and intercept_y is not None:
        y_intercept = {
            "status": "exact_symbolic",
            "x": 0.0,
            "y": intercept_y,
            "exact_y": sp.sstr(sp.simplify(expression.subs(_X, 0))),
        }
    elif lower <= 0 <= upper:
        y_intercept = {"status": "undefined"}
    else:
        y_intercept = {"status": "outside_domain"}

    extrema, extrema_status = _extrema(
        expression,
        derivative,
        samples,
        lower,
        upper,
        asymptote_markers,
    )
    return {
        "operation": "graph",
        "expression": sp.sstr(expression),
        "domain": {"x_min": lower, "x_max": upper},
        "sample_count": count,
        "samples": samples,
        "roots": {"status": root_status, "markers": root_markers},
        "y_intercept": y_intercept,
        "extrema": {"status": extrema_status if extrema else "none_detected", "markers": extrema},
        "asymptotes": asymptotes,
        "derivative": {
            "expression": sp.sstr(derivative),
            "samples": derivative_samples,
        }
        if derivative_samples is not None
        else None,
        "tangents": [_tangent(expression, derivative, float(point)) for point in tangent_points],
        "steps": [
            f"Sample {sp.sstr(expression)} at {count} evenly spaced x-values from {lower:g} to {upper:g}.",
            "Markers labelled exact are symbolic; sampled estimates are numerical and may miss closely spaced features.",
            "Undefined or non-real sample values are left blank so discontinuities are not joined.",
        ],
    }

import ast
import math
import re

import sympy as sp


_VARIABLE = sp.Symbol("x")
_BINARY_OPERATORS = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.Pow: lambda left, right: left**right,
}
_UNARY_OPERATORS = {
    ast.UAdd: lambda value: value,
    ast.USub: lambda value: -value,
}
_MAX_AST_NODES = 128
_MAX_AST_DEPTH = 24
_MAX_INTERMEDIATE_BITS = 2048


class EquationInputError(ValueError):
    """Raised when an equation is invalid or outside the supported scope."""


def _normalise_expression(source: str) -> str:
    source = source.replace("^", "**")
    source = re.sub(r"(?<=[0-9)])\s*(?=x\b)", "*", source)
    source = re.sub(r"(?<=x)\s*(?=\()", "*", source)
    source = re.sub(r"(?<=\))\s*(?=[(0-9x])", "*", source)
    return source


def _preflight_expression(tree: ast.AST) -> None:
    remaining_nodes = _MAX_AST_NODES

    def inspect(node: ast.AST, depth: int = 0) -> int | None:
        nonlocal remaining_nodes
        remaining_nodes -= 1
        if remaining_nodes < 0 or depth > _MAX_AST_DEPTH:
            raise EquationInputError("The equation is too complex.")

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise EquationInputError("Only numeric constants and the variable x are supported.")
            if isinstance(node.value, int):
                return node.value.bit_length()
            if not math.isfinite(node.value):
                raise EquationInputError("Numeric constants must be finite.")
            rational = sp.Rational(str(node.value))
            return max(abs(rational.p).bit_length(), rational.q.bit_length())

        if isinstance(node, ast.Name):
            if node.id != "x":
                raise EquationInputError("Only the variable x is supported in this phase.")
            return 1

        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return inspect(node.operand, depth + 1)

        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            if isinstance(node.op, ast.Div) and any(
                isinstance(child, ast.Name) and child.id == "x" for child in ast.walk(node.right)
            ):
                raise EquationInputError("Variable denominators are not supported.")

            left_bits = inspect(node.left, depth + 1)
            right_bits = inspect(node.right, depth + 1)

            if isinstance(node.op, ast.Pow):
                if (
                    not isinstance(node.right, ast.Constant)
                    or isinstance(node.right.value, bool)
                    or not isinstance(node.right.value, int)
                ):
                    raise EquationInputError(
                        "Powers must be non-negative integer constants up to 8."
                    )
                exponent = node.right.value
                if exponent < 0 or exponent > 8:
                    raise EquationInputError(
                        "Powers must be non-negative integer constants up to 8."
                    )
                result_bits = left_bits * exponent
            elif isinstance(node.op, (ast.Add, ast.Sub)):
                result_bits = left_bits + right_bits + 1
            else:
                result_bits = left_bits + right_bits

            if result_bits is not None and result_bits > _MAX_INTERMEDIATE_BITS:
                raise EquationInputError("The equation creates an excessively large intermediate value.")
            return result_bits

        raise EquationInputError(
            "Use numbers, x, parentheses, and +, -, *, /, or non-negative integer powers."
        )

    inspect(tree)


def _parse_expression(source: str) -> sp.Expr:
    try:
        parsed = ast.parse(_normalise_expression(source.strip()), mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise EquationInputError("Enter a valid mathematical expression.") from error

    _preflight_expression(parsed.body)

    def build(node: ast.AST, depth: int = 0) -> sp.Expr:
        if depth > _MAX_AST_DEPTH:
            raise EquationInputError("The equation is too complex.")

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise EquationInputError("Only numeric constants and the variable x are supported.")
            return sp.Rational(str(node.value))

        if isinstance(node, ast.Name):
            if node.id != "x":
                raise EquationInputError("Only the variable x is supported in this phase.")
            return _VARIABLE

        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return _UNARY_OPERATORS[type(node.op)](build(node.operand, depth + 1))

        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left = build(node.left, depth + 1)
            right = build(node.right, depth + 1)
            if isinstance(node.op, ast.Div) and right.is_zero:
                raise EquationInputError("Division by zero is not defined.")
            if isinstance(node.op, ast.Pow):
                if right.free_symbols or not right.is_Integer:
                    raise EquationInputError("Powers must be non-negative integer constants up to 8.")
                exponent = int(right)
                if exponent < 0 or exponent > 8:
                    raise EquationInputError("Powers must be non-negative integer constants up to 8.")
            return _BINARY_OPERATORS[type(node.op)](left, right)

        raise EquationInputError(
            "Use numbers, x, parentheses, and +, -, *, /, or non-negative integer powers."
        )

    try:
        return build(parsed.body)
    except (OverflowError, ValueError, TypeError) as error:
        if isinstance(error, EquationInputError):
            raise
        raise EquationInputError("The expression contains an invalid operation.") from error


def solve_equation(equation: str) -> dict[str, object]:
    if not equation or not equation.strip():
        raise EquationInputError("Enter an equation to solve.")
    if len(equation) > 512:
        raise EquationInputError("The equation must be 512 characters or fewer.")
    if equation.count("=") != 1:
        raise EquationInputError("Enter one equation with exactly one equals sign.")

    left_source, right_source = equation.split("=", maxsplit=1)
    if not left_source.strip() or not right_source.strip():
        raise EquationInputError("Enter an expression on both sides of the equals sign.")

    left = _parse_expression(left_source)
    right = _parse_expression(right_source)

    try:
        polynomial = sp.Poly(left - right, _VARIABLE)
    except (sp.PolynomialError, ZeroDivisionError) as error:
        raise EquationInputError("The equation must simplify to a polynomial in x.") from error

    if polynomial.is_zero:
        return {
            "equation": equation,
            "variable": "x",
            "degree": None,
            "status": "all_reals",
            "solutions": [],
            "steps": ["Both sides are equal for every value of x."],
        }

    degree = polynomial.degree()
    if degree == 0:
        return {
            "equation": equation,
            "variable": "x",
            "degree": 0,
            "status": "no_solution",
            "solutions": [],
            "steps": ["The equation reduces to a non-zero constant, so it has no solution."],
        }
    if degree > 2:
        raise EquationInputError("This phase supports linear and quadratic equations only.")

    expression = polynomial.as_expr()
    solutions = sp.solve(expression, _VARIABLE)
    steps = [f"Move all terms to one side: {sp.sstr(expression)} = 0."]

    if degree == 1:
        coefficient, constant = polynomial.all_coeffs()
        root = solutions[0]
        steps.append(
            f"Isolate x: x = -({sp.sstr(constant)}) / ({sp.sstr(coefficient)}) = {sp.sstr(root)}."
        )
    else:
        leading, linear, constant = polynomial.all_coeffs()
        discriminant = sp.simplify(linear**2 - 4 * leading * constant)
        steps.append(f"Calculate the discriminant: b^2 - 4ac = {sp.sstr(discriminant)}.")
        steps.append(
            "Apply the quadratic formula: x = "
            f"({sp.sstr(-linear)} +/- sqrt({sp.sstr(discriminant)})) / "
            f"{sp.sstr(2 * leading)}."
        )
        steps.append(f"The distinct solutions are {', '.join(sp.sstr(root) for root in solutions)}.")

    return {
        "equation": equation,
        "variable": "x",
        "degree": degree,
        "status": "solved",
        "solutions": [sp.sstr(root) for root in solutions],
        "steps": steps,
    }

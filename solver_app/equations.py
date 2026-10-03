import ast
import math
import re
from fractions import Fraction

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
_FUNCTION_ARITIES = {
    "log": {1, 2},
    "exp": {1},
    "sin": {1},
    "cos": {1},
    "tan": {1},
    "asin": {1},
    "acos": {1},
    "atan": {1},
    "sqrt": {1},
    "Abs": {1},
}


class EquationInputError(ValueError):
    """Raised when an equation is invalid or outside the supported scope."""


def _normalise_expression(source: str) -> str:
    source = source.replace("^", "**")
    source = re.sub(r"(?<=[0-9)])\s*(?=x\b)", "*", source)
    source = re.sub(r"(?<=x)\s*(?=\()", "*", source)
    source = re.sub(r"(?<=\))\s*(?=[(0-9x])", "*", source)
    return source


def _preflight_expression(
    tree: ast.AST,
    variables: set[str],
    allow_functions: bool,
    legacy_mode: bool,
) -> None:
    remaining_nodes = _MAX_AST_NODES

    def bit_size(value: Fraction) -> int:
        return max(abs(value.numerator).bit_length(), value.denominator.bit_length())

    def check_size(value: Fraction) -> None:
        if bit_size(value) > _MAX_INTERMEDIATE_BITS:
            raise EquationInputError(
                "The equation creates an excessively large intermediate value."
            )

    def inspect(node: ast.AST, depth: int = 0) -> tuple[Fraction | None, int]:
        nonlocal remaining_nodes
        remaining_nodes -= 1
        if remaining_nodes < 0 or depth > _MAX_AST_DEPTH:
            raise EquationInputError("The equation is too complex.")

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise EquationInputError("Only numeric constants and supported variables are allowed.")
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise EquationInputError("Numeric constants must be finite.")
            value = Fraction(str(node.value))
            check_size(value)
            return value, bit_size(value)

        if isinstance(node, ast.Name):
            if node.id in {"pi", "E"} and allow_functions:
                return None, 1
            if node.id not in variables:
                if legacy_mode:
                    raise EquationInputError("Only the variable x is supported in this phase.")
                raise EquationInputError(
                    f"Only these variables are supported: {', '.join(sorted(variables))}."
                )
            return None, 1

        if isinstance(node, ast.Call) and allow_functions:
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise EquationInputError(
                    "Only named mathematical functions without keywords are supported."
                )
            if node.func.id not in _FUNCTION_ARITIES and node.func.id not in {
                "y",
                "Derivative",
            }:
                raise EquationInputError("That function is not supported.")
            arguments = [inspect(argument, depth + 1) for argument in node.args]
            return None, max((bits for _, bits in arguments), default=1)

        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            value, bits = inspect(node.operand, depth + 1)
            if value is not None and isinstance(node.op, ast.USub):
                value = -value
            return value, bits

        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            if isinstance(node.op, ast.Div) and legacy_mode and any(
                isinstance(child, ast.Name) and child.id in variables
                for child in ast.walk(node.right)
            ):
                raise EquationInputError("Variable denominators are not supported.")

            left, left_bits = inspect(node.left, depth + 1)
            right, right_bits = inspect(node.right, depth + 1)

            if isinstance(node.op, ast.Pow):
                if legacy_mode and (
                    not isinstance(node.right, ast.Constant)
                    or isinstance(node.right.value, bool)
                    or not isinstance(node.right.value, int)
                ):
                    raise EquationInputError(
                        "Powers must be non-negative integer constants up to 8."
                    )
                if right is None:
                    return None, left_bits
                if right.denominator != 1:
                    return None, left_bits
                exponent = right.numerator
                if abs(exponent) > _MAX_INTERMEDIATE_BITS:
                    raise EquationInputError(
                        "The equation creates an excessively large intermediate value."
                    )
                if legacy_mode and not 0 <= exponent <= 8:
                    raise EquationInputError(
                        "Powers must be non-negative integer constants up to 8."
                    )
                result_bits = left_bits * abs(exponent)
                if result_bits > _MAX_INTERMEDIATE_BITS:
                    raise EquationInputError(
                        "The equation creates an excessively large intermediate value."
                    )
                if left is None:
                    return None, max(1, result_bits)
                value = left**exponent
                check_size(value)
                return value, max(1, result_bits)

            if isinstance(node.op, (ast.Add, ast.Sub)):
                estimate = max(left_bits, right_bits) + 1
            else:
                estimate = left_bits + right_bits
            if estimate > _MAX_INTERMEDIATE_BITS:
                raise EquationInputError(
                    "The equation creates an excessively large intermediate value."
                )

            if left is None or right is None:
                return None, estimate
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            else:
                if right == 0:
                    raise EquationInputError("Division by zero is not defined.")
                value = left / right
            check_size(value)
            return value, estimate

        raise EquationInputError(
            "Use numbers, supported variables, parentheses, and +, -, *, /, or powers."
        )

    inspect(tree)


def _parse_expression(
    source: str,
    allowed_variables: set[str] | None = None,
    allow_functions: bool = False,
) -> sp.Expr:
    legacy_mode = allowed_variables is None and not allow_functions
    variables = {"x"} if allowed_variables is None else allowed_variables
    normalised_source = _normalise_expression(source.strip())
    if not legacy_mode:
        normalised_source = source.strip().replace("^", "**")
        variable_pattern = "|".join(
            re.escape(name) for name in sorted(variables, key=len, reverse=True)
        )
        normalised_source = re.sub(
            rf"(?<=[0-9)])\s*(?=(?:{variable_pattern})\b)",
            "*",
            normalised_source,
        )
    try:
        parsed = ast.parse(normalised_source, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise EquationInputError("Enter a valid mathematical expression.") from error

    _preflight_expression(parsed.body, variables, allow_functions, legacy_mode)

    def build(node: ast.AST, depth: int = 0) -> sp.Expr:
        if depth > _MAX_AST_DEPTH:
            raise EquationInputError("The equation is too complex.")

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise EquationInputError("Only numeric constants and supported variables are allowed.")
            return sp.Rational(str(node.value))

        if isinstance(node, ast.Name):
            if node.id in {"pi", "E"} and allow_functions:
                return sp.pi if node.id == "pi" else sp.E
            if node.id not in variables:
                if legacy_mode:
                    raise EquationInputError("Only the variable x is supported in this phase.")
                raise EquationInputError(
                    f"Only these variables are supported: {', '.join(sorted(variables))}."
                )
            return _VARIABLE if node.id == "x" else sp.Symbol(node.id)

        if isinstance(node, ast.Call) and allow_functions:
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise EquationInputError(
                    "Only named mathematical functions without keywords are supported."
                )
            arguments = [build(argument, depth + 1) for argument in node.args]
            if node.func.id in _FUNCTION_ARITIES:
                if len(arguments) not in _FUNCTION_ARITIES[node.func.id]:
                    raise EquationInputError(
                        f"{node.func.id} received the wrong number of arguments."
                    )
                functions = {
                    "log": sp.log,
                    "exp": sp.exp,
                    "sin": sp.sin,
                    "cos": sp.cos,
                    "tan": sp.tan,
                    "asin": sp.asin,
                    "acos": sp.acos,
                    "atan": sp.atan,
                    "sqrt": sp.sqrt,
                    "Abs": sp.Abs,
                }
                return functions[node.func.id](*arguments)
            if node.func.id == "y" and len(arguments) == 1:
                return sp.Function("y")(*arguments)
            if node.func.id == "Derivative" and len(arguments) >= 2:
                try:
                    return sp.Derivative(arguments[0], *arguments[1:])
                except (ValueError, TypeError) as error:
                    raise EquationInputError(
                        "Use Derivative(function, variable) for derivatives."
                    ) from error
            raise EquationInputError("That function is not supported.")

        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return _UNARY_OPERATORS[type(node.op)](build(node.operand, depth + 1))

        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left = build(node.left, depth + 1)
            right = build(node.right, depth + 1)
            if isinstance(node.op, ast.Div) and right.is_zero:
                raise EquationInputError("Division by zero is not defined.")
            if isinstance(node.op, ast.Pow):
                if legacy_mode:
                    if right.free_symbols or not right.is_Integer:
                        raise EquationInputError(
                            "Powers must be non-negative integer constants up to 8."
                        )
                    exponent = int(right)
                    if exponent < 0 or exponent > 8:
                        raise EquationInputError(
                            "Powers must be non-negative integer constants up to 8."
                        )
                elif not right.free_symbols and right.is_Rational:
                    if abs(int(right.p)) > 32 or int(right.q) > 16:
                        raise EquationInputError("The power is outside the supported range.")
                elif right.free_symbols:
                    if not allow_functions:
                        raise EquationInputError("Symbolic powers are not supported here.")
                else:
                    raise EquationInputError(
                        "Powers must be numeric or a supported variable."
                    )
            return _BINARY_OPERATORS[type(node.op)](left, right)

        raise EquationInputError(
            "Use numbers, supported variables, parentheses, and +, -, *, /, or powers."
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
        steps.append(
            f"The distinct solutions are {', '.join(sp.sstr(root) for root in solutions)}."
        )

    return {
        "equation": equation,
        "variable": "x",
        "degree": degree,
        "status": "solved",
        "solutions": [sp.sstr(root) for root in solutions],
        "steps": steps,
    }

# Genius Mathematical Solver

Genius is a self-contained, step-by-step mathematical solver.
The application is built and run in Docker.
The host does not need Python, Node.js, or project dependencies installed.

## Run with Docker Compose

The host needs Docker Engine with the Compose plugin.
Build and start the application from the repository root:

```sh
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000) in a browser.
The service listens only on the host loopback interface.
Stop the service with `Ctrl+C` or run `docker compose down`.

## Phase 1 equation API

The original equation endpoint remains available:

```sh
curl -X POST http://localhost:8000/api/solve \
  -H "Content-Type: application/json" \
  -d "{\"equation\":\"x^2 + 4 = 0\"}"
```

It solves linear and quadratic equations in `x`.
It reports identities, inconsistent equations, malformed input,
and unsupported polynomial degrees distinctly.
Powers may use `^` or `**`.

## Phase 2 operation API

Send a typed operation request to `POST /api/operate`.
Successful responses include the operation, a structured result,
and ordered explanation steps.
Invalid, malformed, and unsupported requests return HTTP 422
with an explanatory `detail`.

### Polynomials and systems

Polynomial equations in `x`, `y`, `z`, or `t` are supported through degree 8:

```sh
curl -X POST http://localhost:8000/api/operate \
  -H "Content-Type: application/json" \
  -d "{\"operation\":\"polynomial_solve\",\"equation\":\"x^3 - 6x^2 + 11x - 6 = 0\"}"
```

Solve a linear system by passing one equation per array entry:

```json
{
  "operation": "system_solve",
  "equations": ["x + y = 3", "x - y = 1"]
}
```

Every system equation must be linear.
Non-linear systems, more than eight equations,
and variables outside `x`, `y`, `z`, and `t` are rejected explicitly.

### Logarithms and exponential equations

The `log_expand` and `log_condense` operations transform logarithms.
The identities are reported with their positive-real-argument assumption:

```json
{"operation": "log_expand", "expression": "log(x*y)"}
```

The `exponential_solve` operation solves supported real equations
containing `exp(x)` or a numeric base raised to a variable:

```json
{"operation": "exponential_solve", "equation": "exp(x) = 3"}
```

### Calculus and differential equations

Differentiate with the `differentiate` operation.
Set `order` from 1 to 10 for higher derivatives.
Product, quotient, and chain rules are applied symbolically:

```json
{"operation": "differentiate", "expression": "x^2 * sin(x)", "variable": "x"}
```

Integrate indefinitely by omitting bounds,
or provide both `lower` and `upper` for a definite integral:

```json
{"operation": "integrate", "expression": "x * exp(x)", "variable": "x"}
```

```json
{
  "operation": "integrate",
  "expression": "x",
  "variable": "x",
  "lower": "0",
  "upper": "1"
}
```

SymPy returns exact antiderivatives when available,
including results found through substitution or integration by parts.
An integral that remains unevaluated is returned as an explicit error.

Limits accept `expression`, `variable`, `point`,
and an optional `direction` of `both`, `+`, or `-`:

```json
{"operation": "limit", "expression": "sin(x)/x", "point": "0"}
```

When substitution gives 0/0, the explanation identifies L'Hôpital's Rule.

First-order ODEs use `Derivative(y(x), x)` notation:

```json
{
  "operation": "ode_solve",
  "equation": "Derivative(y(x), x) + y(x) = 0"
}
```

Only a single dependent function and its first derivative are supported.
Unsupported or unevaluated differential equations return an explicit error.

### Trigonometry and matrices

Trigonometric equations return real solution sets,
including periodic forms when SymPy can express them:

```json
{"operation": "trig_solve", "equation": "sin(x) = 0"}
```

Simplify identities with `trig_simplify`:

```json
{"operation": "trig_simplify", "expression": "sin(x)^2 + cos(x)^2"}
```

The matrix operations accept a rectangular JSON array of numbers
or safe expression strings:

```json
{"operation": "matrix_determinant", "matrix": [[1, 2], [3, 4]]}
{"operation": "matrix_rref", "matrix": [[1, 2], [3, 4]]}
{"operation": "matrix_inverse", "matrix": [[1, 2], [3, 4]]}
```

Matrices are limited to eight rows and columns.
Determinants and inverses require square matrices.
Singular matrices do not have an inverse.

## Safe expression syntax

Expressions are parsed through a restricted Python abstract syntax tree.
They are never evaluated as Python code.
The solver does not call `eval`, `sympify`, or `parse_expr` on input.

The supported scalar variables are `x`, `y`, `z`, and `t`.
Available functions are `log`, `exp`, `sin`, `cos`, `tan`,
`asin`, `acos`, `atan`, `sqrt`, and `Abs`.
Use `pi` and `E` for those constants.
Use explicit `*` for multiplication except for familiar forms such as `2x`.

Inputs are limited to 512 characters and expressions to a bounded syntax tree.
Unsupported functions, malformed equations, unevaluated operations,
and invalid matrix shapes are rejected rather than guessed.
Log expansion and condensation assume positive real arguments.
Some valid symbolic problems may remain outside SymPy's closed-form coverage.

## Readiness and tests

Check service readiness at `GET /api/ready`.
Run the tests entirely in Docker:

```sh
docker compose run --build --rm solver pytest -q
```

Graphing, OCR, and image or handwriting input are outside this phase.

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
Only the variable `x` and basic arithmetic are supported in Phase 1.
The input is parsed as restricted mathematical syntax and is never evaluated as Python code.
Equations with variable-dependent denominators are rejected because simplification can otherwise hide excluded values.
Expressions whose estimated numeric intermediates exceed the configured size limit are rejected before evaluation, including coefficients multiplied by variables and nested powers.

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

Only finite real solution sets are returned.
Equations with periodic exponents, such as `exp(sin(x)) = 1`,
are rejected because they can have infinitely many solutions.

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

## Phase 3 graphing

Graph one explicit Cartesian function of `x` with `POST /api/graph`:

```json
{
  "expression": "sin(x)",
  "x_min": -10,
  "x_max": 10,
  "sample_count": 800,
  "include_derivative": true,
  "tangent_points": [1]
}
```

The response contains graph samples, x-root markers, the y-intercept,
local extrema, asymptote markers, optional derivative samples,
and tangent-line data for each requested x-value.
Markers distinguish `exact_symbolic` results from `sampled_estimate` results.
Undefined or non-real samples are `null` and break the plotted curve
instead of joining across a discontinuity.

The browser graph supports drag-to-pan, scroll-to-zoom, coordinate tooltips,
and toggles for roots, the y-intercept, extrema, asymptotes,
the derivative overlay, and requested tangent lines.
Enter tangent x-values as comma-separated numbers.
The graph endpoint rejects extra fields and invalid ranges.
Expressions are limited to 512 characters;
x-bounds are in `[-1000, 1000]` and at most 2000 units apart;
sample counts are from 100 to 2000;
and at most 10 tangent points may be requested within the graph range.

Roots are reported as exact when a polynomial root set can be enumerated
symbolically through degree 4.
Other roots and non-polynomial extrema use labelled numerical estimates
based on the selected sample grid.
Exact extrema are limited to enumerable polynomial stationary points
with a non-zero second derivative.
Vertical asymptotes are determined exactly for rational functions
with denominator degree at most 8 and tangent functions with affine arguments.
Other asymptote forms are marked unsupported rather than guessed.
Sampling can miss closely spaced or narrow features.
The input must describe an explicit, real-valued function of `x`;
implicit curves and parametric graphs are not supported.

## Phase 4 image and handwriting input

The browser accepts PNG, JPEG, and WebP images,
or a formula drawn with a mouse, finger, or stylus on its touch-enabled canvas.
Select an equation or expression operation first,
recognise the image locally,
then review or edit the filled solver field before submitting it.
For a system of equations,
recognised input is appended as a new equation line.

OCR uses the Apache-2.0 UniMERNet small formula-recognition model
(`wanderkid/unimernet_small`, pinned to revision
`82cb85440138c2038680fca410c8f70bb7343d6d`).
The model was selected because its published UniMER-Test includes
6,332 handwritten-expression examples as well as printed, complex, and
screen-captured formula classes.
Its checkpoint is approximately 810 MB;
the CPU-only PyTorch runtime and OCR dependencies make the Docker image
substantially larger than earlier phases.
The Docker build downloads the pinned checkpoint and verifies its SHA-256
before the image is usable.
The running application uses the bundled model only;
it does not contact external OCR services or download weights at runtime.

The recogniser processes one formula crop at a time,
not full-page documents or mixed text and equation regions.
It accepts images up to 8 MiB (8,388,608 bytes),
4096 pixels per side,
and 12 megapixels,
in PNG, JPEG, or WebP format;
PDF, GIF, and animated-image input are not supported.
Handwriting recognition is supported but not guaranteed,
and accuracy depends on legibility, contrast, crop, and symbol style.
Always check OCR output before calculating.
The output adapter supports the solver's scalar syntax,
including fractions, square roots, powers, equality,
basic arithmetic, `pi`, and supported trigonometric, logarithmic,
and exponential functions.
Subscripts and other unsupported notation are rejected with an explicit error
instead of being silently rewritten;
enter or edit that notation manually in the solver field.

To build and run the application with the local model,
or execute the complete test suite in Docker:

```sh
docker compose up --build
docker compose run --build --rm solver pytest -q
```

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

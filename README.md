# Genius Mathematical Solver

Genius is a self-contained, step-by-step mathematical solver.
The application is built and run in Docker, so the host does not need Python, Node.js, or project dependencies installed.

## Phase 1 capabilities

Enter a linear or quadratic equation in `x` and view its solution and working.
Quadratic equations include real and complex roots.
The solver reports identities, equations with no solution, malformed input, and unsupported polynomial degrees distinctly.

## Run with Docker Compose

The host needs Docker Engine with the Compose plugin.
Build and start the application from the repository root:

```sh
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000) in a browser.
The service listens only on the host loopback interface.
Stop the service with `Ctrl+C` or run `docker compose down`.

## Solver API

Submit an equation as JSON:

```sh
curl -X POST http://localhost:8000/api/solve \
  -H "Content-Type: application/json" \
  -d "{\"equation\":\"x^2 + 4 = 0\"}"
```

The response contains the polynomial degree, solutions, status, and ordered explanation steps.
Powers may use `^` or `**`.
Only the variable `x` and basic arithmetic are supported in Phase 1.
The input is parsed as restricted mathematical syntax and is never evaluated as Python code.

Check service readiness at `GET /api/ready`.

## Run tests in Docker

```sh
docker compose run --build --rm solver pytest
```

No test runner or language runtime needs to be installed on the host.

## Current limitations

This phase supports linear and quadratic equations only.
Powers must be non-negative integer constants between 0 and 8.
Systems, calculus, matrices, graphing, and image or handwriting input are planned for later phases.

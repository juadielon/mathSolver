---
description: 'Code review guidance for Math Solver'
applyTo: '**'
excludeAgent: ["coding-agent"]
---

# Math Solver code review

Review changes for concrete defects introduced by the change. Prioritise incorrect or unsafe results, regressions in the API or browser, resource-exhaustion risks, and missing tests for changed behaviour. Skip style-only preferences and generic best-practice comments unless they cause a real problem here.

## Project context

- The service is a Python 3.11+ FastAPI application using SymPy, with a browser UI served from `solver_app/static`.
- The application and its tests run in Docker. The supported test command is `docker compose run --build --rm solver pytest -q`.
- The OCR recogniser uses a pinned UniMERNet model bundled into the image. Runtime inference is local and offline.
- Public endpoints include `/api/solve`, `/api/operate`, `/api/graph`, `/api/recognise`, and `/api/ready`.

## Review priorities

### Critical: unsafe input handling or materially wrong results

- Treat every equation, expression, graph request, matrix value, and uploaded image as untrusted input.
- Never evaluate user input as Python or pass it to `eval`, `sympify`, or `parse_expr`. Keep parsing restricted to the project's validated syntax and supported operations.
- Check that validation and size limits still apply before expensive symbolic, numeric, or image-processing work. Consider expression complexity as well as string length; image byte, dimension, and pixel limits; graph sample and domain limits; and matrix size limits.
- Check mathematical domain restrictions, excluded denominator values, real-versus-complex behaviour, and whether a result is exact or only a sampled estimate. Unsupported or uncertain results must not be presented as exact.

### High: broken API or user-visible behaviour

- Keep request validation aligned with each endpoint's supported inputs and limits. Unexpected fields should remain rejected where the request model forbids them.
- Preserve clear error behaviour: invalid or unsupported requests return an explanatory 422, oversized image bodies return 413, and OCR service failures return 503.
- Keep response shapes and the browser UI in sync. In particular, preserve labelled graph estimates, `null` samples across undefined or non-real regions, and explicit errors for unevaluated operations.
- Do not add runtime network calls for OCR or silently fetch unpinned model data. Preserve the pinned model revision and build-time checksum verification.
- Check Docker and dependency changes against the CPU-only runtime, offline inference, non-root container, and documented Compose workflow.

### Medium: meaningful reliability or maintainability risks

- Look for boundary cases in symbolic operations, graph sampling, image decoding, and request validation that could crash the service or return misleading output.
- Check that new behaviour has focused pytest coverage, including invalid-input and limit-boundary cases where relevant. Keep tests deterministic and independent of external services.
- Follow the existing module boundaries: API validation in `main.py`, operation logic in the relevant solver module, and browser changes alongside their affected API behaviour.

## Review comments

Report only actionable findings. For each one, use the changed line range where possible and state the user impact and a concrete fix. Use these severities:

- **Critical** — unsafe input handling, data exposure, or a serious correctness failure.
- **High** — a major API, solver, or UI regression, or a practical resource-exhaustion risk.
- **Medium** — a contained correctness or reliability issue with a clear user impact.
- **Low** — a minor issue worth fixing, only when it is specific and actionable.

Do not report missing tests by themselves unless the uncovered behaviour creates a material risk. If there are no actionable findings, say so plainly.

# Docker build caching

Run `docker compose build` normally to reuse Docker's previous layers.
Use `--no-cache` only when deliberately rebuilding everything.

The Dockerfile installs system and Python dependencies from `pyproject.toml`
before copying application code. The pinned UniMERNet download and checksum
check depend only on those dependencies and `solver_app/fetch_unimernet.py`.
Routine solver, frontend or test edits therefore reuse the expensive
dependency and model layers. Application code is installed with `--no-deps`
afterwards, and tests are copied last. README and documentation-only edits
do not invalidate build layers.

Changing dependencies, the model fetch script or the base image can still
require a slower rebuild and network access. The first build with this layer
layout must populate the new cache.

For tests without touching a running Compose deployment, use a separate
project name:

```sh
docker compose -p mathsolver-validation run --build --rm solver pytest -q
docker compose -p mathsolver-validation down
```

`compose run` does not publish the service's ports unless `--service-ports`
is requested, so this command leaves the existing port 8000 server alone.

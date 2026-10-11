# Project instructions

Read [README.md](README.md) for current features and API examples,
[CONTRIBUTING.md](CONTRIBUTING.md) for development and contribution guidance,
and [ROADMAP.md](ROADMAP.md) for priorities and completion criteria.
Treat upcoming roadmap items as unavailable until their PRs land.

## Architecture and boundaries

Math Solver uses FastAPI and SymPy,
with vanilla JavaScript, CSS, and HTML in `solver_app/static`.
The supported application runtime is Docker only.
Run Python tests in Docker;
Node.js is optional for the built-in browser regression tests.
Use the commands in CONTRIBUTING.md.

Keep API validation in `solver_app/main.py`,
mathematical logic in the relevant solver module,
and browser behaviour aligned with API request and response shapes.
Read affected callers and tests before editing.
Preserve restricted input parsing and resource limits;
never evaluate user input as Python.
Reject unsupported or unevaluated maths explicitly,
and distinguish exact results from numerical estimates.

Keep recognition local and offline at runtime.
Preserve the pinned UniMERNet checkpoint and build-time checksum verification.
A specialist formula-recognition model is acceptable;
do not promise model-free handwriting, scratch-out gestures, or live recognition.

## Documentation and language

Use Australian English in prose, comments, and new names,
except where external APIs or existing interfaces require exact spellings.
Follow [Semantic Line Breaks](https://sembr.org/) in Markdown prose:
start a new source line after each sentence,
and at substantial clause boundaries when this helps readability.
Preserve paragraphs and rendered meaning;
do not add forced Markdown line breaks.
Leave code blocks, URLs, and structured syntax intact.

Describe user-facing features by what they do,
not by historical implementation phases.
Update directly related documentation when behaviour changes.
Check current code before claiming support,
especially for variable names and handwriting input.

## Commits and pull requests

Use [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
Follow the syntax, examples, and breaking-change rules in CONTRIBUTING.md.
Commit after each small, coherent logical step,
with the relevant checks completed and their outcomes recorded.
Keep commits and PRs focused and reviewable;
do not accumulate a huge PR.
Split independent work into separate PRs,
and use dependent stacks only when later work needs earlier changes.
Open multiple small PRs as coherent pieces become ready to merge.
Preserve the repository PR template,
report exact validation commands and results,
and state anything not checked.

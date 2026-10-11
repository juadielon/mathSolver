# Contributing

Start with [README.md](README.md) for supported inputs and API examples,
and [ROADMAP.md](ROADMAP.md) for current capabilities and upcoming priorities.
[AGENTS.md](AGENTS.md) contains durable instructions for developers and agents.

## Development and checks

The application uses FastAPI and SymPy,
with a vanilla JavaScript, CSS, and HTML browser interface.
Docker Engine with the Compose plugin is required.
Python and project dependencies do not need to be installed on the host.

From the repository root,
build and start the application:

```sh
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000).
`GET /api/ready` reports service readiness.
Stop the service with `Ctrl+C`,
or use `docker compose down`.
The initial build needs network access to install dependencies and download the pinned OCR checkpoint;
recognition runs offline from the bundled model afterwards.

Run the complete Python suite in Docker:

```sh
docker compose run --build --rm solver pytest -q
```

For a focused change,
select the relevant existing test files:

```sh
docker compose run --build --rm solver pytest -q tests/test_equations.py tests/test_operations.py
```

The other Python suites cover graphing and OCR in `tests/test_graphing.py`
and `tests/test_ocr.py`.
Browser result-formatting regressions use Node.js's built-in runner,
without npm dependencies:

```sh
node --test tests/test_browser.js
```

Node.js is optional development tooling,
not an application runtime requirement.
These tests do not replace checking affected browser interactions.
Add focused coverage for changed behaviour,
including invalid inputs and relevant limit boundaries.
For documentation-only changes,
check links, examples, and claims against the source;
application tests are not required.

## Semantic line breaks

Follow [Semantic Line Breaks](https://sembr.org/) when writing or revising Markdown prose.
Put each sentence on a new source line,
and split substantial clauses where this makes edits easier to review.
Keep blank lines between paragraphs.
Ordinary line wrapping must not change rendered meaning;
do not add trailing double spaces or `<br>` tags to force breaks.
Do not split code, inline links, or other structured syntax.

For example,
these source lines render as one paragraph:

```markdown
Recognition runs locally,
using the model bundled into the Docker image.
Review the recognised expression before calculating.
```

Use Australian English.
Use feature names in user documentation and interface copy,
not historical implementation phases.
Keep current support separate from upcoming work.

## Conventional Commits

Use [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

`feat` introduces a feature;
`fix` corrects a bug.
Use `docs` for documentation,
`test` for tests,
and an appropriate type such as `refactor`, `build`, or `chore` for other work.
An optional scope identifies the affected area.
Separate the body and footers from preceding content with a blank line.

```text
docs: explain offline recognition limits
fix(graph): preserve gaps at undefined samples
feat(solver): support additional single-letter variables
```

These are message examples,
not claims that upcoming features have landed.
Mark a breaking change with `!` before the colon,
or a `BREAKING CHANGE: <description>` footer.
Use the uppercase footer spelling exactly,
and explain the required migration.
A breaking change can occur under any commit type.

```text
feat(api)!: rename a request field

BREAKING CHANGE: Clients must replace the old field name with the new name.
```

## Small commits and focused PRs

Make a commit after each coherent logical step,
once its relevant checks are complete.
Keep related implementation, tests, and documentation together;
do not mix unrelated fixes or reformatting.
Record exact commands and outcomes,
and explain skipped checks rather than implying they passed.

Open a focused PR when a coherent piece is ready to merge,
instead of collecting a very long PR.
Split independent changes into separate PRs.
When later work depends on earlier changes,
use a small dependent stack and explain each dependency.
Each PR should have a clear purpose and completion criteria.

Use [.github/pull_request_template.md](.github/pull_request_template.md),
preserving its headings, comments, checklist items, and order.
Describe user impact and breaking changes accurately.
Update the roadmap when an upcoming capability lands,
but do not publish release dates or commitments without an agreed basis.

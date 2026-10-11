# Developer and agent roadmap

This roadmap describes user needs and completion criteria,
not historical implementation phases or promised release dates.
[README.md](README.md) documents current API behaviour and limits.
Follow [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md)
when taking on a change.

## Current capabilities

The Docker application serves a browser interface and a FastAPI API,
with SymPy providing symbolic calculations.
Users can type maths,
draw a formula with a mouse, finger, or stylus,
or upload a PNG, JPEG, or WebP formula crop.
Recognition fills an editable solver field;
users review the expression before calculating.

Supported operations include linear and quadratic equations,
polynomial equations through degree 8,
linear systems,
logarithmic transformations and supported exponential equations,
derivatives, integrals, limits, first-order differential equations,
trigonometric operations,
and matrix determinants, row reduction, and inverses.
The browser also graphs explicit functions of one variable,
with labelled exact or sampled markers,
optional derivative overlays,
and tangent lines.

Variables can be any single letter, `a` to `z` or `A` to `Z`.
[docs/api-variables.md](docs/api-variables.md) explains detection,
the `pi` and `E` constant rules,
and differential equation notation.
The browser offers one Type, Write, or Upload choice,
groups calculations in a single menu,
and detects the variable unless the user picks one.

## Next user-centred priorities

### Keep handwritten input local and honest

Recognition must remain local and offline at runtime.
A specialist formula-recognition model is acceptable;
the current pinned UniMERNet architecture remains the baseline.
Handwriting accuracy is not guaranteed,
and users must be able to correct recognition errors.

Completion criteria for recognition improvements:

- Reproducible formula examples show what improves and what remains unsupported, including handwritten input.
- The model remains bundled, pinned, and checksum-verified at build time, with no runtime downloads or external OCR service calls.
- Image validation, resource limits, unsupported-notation errors, and review-before-calculation behaviour remain intact.
- Any changed model or runtime requirements have evidence and updated documentation before being presented as supported.

Model-free handwriting, scratch-out gestures, and live recognition are not promised capabilities.

## Known constraints

The supported runtime is Docker only.
The initial build downloads dependencies and the pinned model;
the OCR checkpoint is approximately 810 MB,
and its CPU-only runtime makes the image substantially larger than a solver without OCR.

Recognition processes one formula crop at a time,
not full pages or mixed text regions.
Uploads are limited to 8 MiB,
4096 pixels per side,
and 12 megapixels.
PDFs and animated images are unsupported.
Unsupported recognised notation is rejected rather than silently rewritten.

Symbolic support is bounded by the restricted parser,
resource limits,
and SymPy's ability to return a supported result.
Graph sampling can miss narrow features;
implicit curves and parametric graphs are unsupported.
Keep exact results, sampled estimates, and unsupported results clearly distinct.

## Delivering roadmap work

Take one coherent user outcome at a time,
with focused tests and directly related documentation.
Split independent changes into separate PRs,
or use small dependent stacks where necessary.
Mark a capability current only after its PR lands and the completion criteria are met.
Do not infer availability from a plan, branch name, or implementation milestone.

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
The browser also graphs explicit functions of `x`,
with labelled exact or sampled markers,
optional derivative overlays,
and tangent lines.

Scalar variables are currently limited to `x`, `y`, `z`, and `t`.
The broader variable support and simpler input workspace below are in progress,
not released.

## Next user-centred priorities

### Use the variable names in the problem

Users should be able to enter any single-letter variable,
instead of rewriting a problem to fit four allowed letters.
Broader variable support is upcoming;
do not document arbitrary letters as supported until its PR lands.

Completion criteria:

- Supported solver operations accept single-letter variables consistently across parsing, request validation, and result labels.
- Constants and reserved function notation have explicit, documented rules rather than ambiguous interpretation.
- Existing `x`, `y`, `z`, and `t` examples keep working, and invalid or unsupported input still produces a clear error.
- Focused tests cover new letters, existing syntax, and conflicts with reserved notation; browser controls and documentation match the landed API.

Graphing currently uses `x`,
and differential equations use the documented `y(x)` notation.
Any change to those conventions needs explicit coverage and documentation,
not an assumption that changing a shared variable list is sufficient.

### Make Type, Write, and Upload easier to use

Users should have a simpler workspace for keyboard input,
handwriting with a finger, mouse, or stylus,
and uploading a formula image.
The unified Type/Write/Upload workspace is upcoming;
the current browser already supports typing, drawing, and image recognition,
but does not yet provide that simplified organisation.

Completion criteria:

- Input choices are easy to find and use on desktop and touch devices, without historical phase labels.
- Users can enter maths by keyboard, draw with supported pointer devices, or upload a supported image without losing their input when moving through the workflow.
- Recognised text remains editable before submission, with visible progress, clear errors, and a deliberate calculation action.
- Operation-specific inputs, results, graph controls, and system-equation entry remain usable; keyboard access and focus behaviour are checked alongside touch and mouse interactions.
- Relevant browser regressions and manual interaction checks are recorded, and user documentation describes only the landed interface.

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

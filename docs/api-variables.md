# Variables in the solver API

Variables are case-sensitive single ASCII Latin letters: `a` through `z` and
`A` through `Z`. Multi-letter names, subscripts and other alphabets are rejected.
The mathematical function allowlist and existing input, resource and domain
limits still apply.

`POST /api/solve` infers the letter from the equation and returns `variable`.
It accepts one variable at a time, including `E`, and retains that letter when
all variable terms cancel. Use `/api/operate` with `system_solve` for systems
of up to eight single-letter variables.

`POST /api/operate` and `POST /api/graph` accept an optional `variable`:

```json
{"operation": "differentiate", "expression": "A^2", "variable": "A"}
```

Omit `variable` or send `null` for Auto. Operations requiring a variable infer
the sole free variable; constant expressions default to `x`. If all terms
cancel, the sole letter mentioned in the input is retained. Multiple free
variables require an explicit selection; symbolic operations may treat the
others as parameters. Systems, log transformations, trig simplification and
matrix operations do not require selecting a single variable.

In symbolic operations and graphs, `pi` and `E` remain mathematical constants.
Select `"variable": "E"` explicitly to use `E` as a variable. This also applies
to systems and other operations containing `E`. Integral bounds and limit
points always interpret `E` as a constant and cannot contain variables.

Graphs must contain only the selected variable, not other free parameters:

```json
{"expression": "Q^2 - 1", "include_derivative": true, "tangent_points": [1]}
```

Graph responses include `variable` for axis labels. The expression, derivative,
tangent line and sampling explanation use that letter. Existing `x_min`,
`x_max`, sample/marker `x`, `exact_x` and tangent point keys are unchanged;
they represent horizontal coordinates regardless of the variable name.
Exact markers, null values at undefined points and sampling limits are unchanged.

## Migrating clients

Omitting `variable` from an operation now means Auto, rather than selecting `x`.
Clients that require the old behaviour must send `"variable": "x"`.

Graph clients must use the response's `variable` in axis labels, tooltips,
function labels and range controls. A client that still labels these as `x`
must send `"variable": "x"` until it supports the response metadata. Do not
infer the label from coordinate keys: `sample.x` remains a compatibility key,
even when the graph uses another letter.

## ODEs, OCR and numeric syntax

First-order ODEs accept any single-letter dependent and independent names,
for example `Derivative(F(Q), Q) + F(Q) = 0`. There must be exactly one
dependent function with one independent variable, and derivatives must be
first order with respect to that argument. If `variable` is provided, it must
match the independent variable. An independent `E` requires explicit selection.

OCR adaptation preserves these letters and validates the same safe syntax.
Recognition returns text, not a selected variable; the calculation endpoint
applies the constant/variable rules above.

Implicit multiplication supports forms such as `2A`, `A(A+1)` and `(A+1)A`.
Numeric tokens such as `1e+3`, `1E-3` and `0x1A` are preserved rather than
split into variables. Thus `2e+1` means scientific notation (`20`), not
`2*e + 1`; write the multiplication explicitly or separate the operator
(`2e + 1`) when using `e` as a variable. Numeric suffixes `j` and `J` are
interpreted as single-letter variables, not Python complex literals.

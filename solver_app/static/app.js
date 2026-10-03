const form = document.querySelector("#solver-form");
const operationSelect = document.querySelector("#operation");
const equationInput = document.querySelector("#equation");
const equationsInput = document.querySelector("#equations");
const expressionInput = document.querySelector("#expression");
const matrixInput = document.querySelector("#matrix");
const results = document.querySelector("#results");
const errorMessage = document.querySelector("#error-message");
const resultTitle = document.querySelector("#result-title");
const degreeBadge = document.querySelector("#degree-badge");
const stepsList = document.querySelector("#steps");
const calculateButton = form.querySelector("button");

const fields = {
  equation: document.querySelector("#equation-field"),
  equations: document.querySelector("#equations-field"),
  expression: document.querySelector("#expression-field"),
  matrix: document.querySelector("#matrix-field"),
  variable: document.querySelector("#variable-field"),
  order: document.querySelector("#order-field"),
  point: document.querySelector("#point-field"),
  direction: document.querySelector("#direction-field"),
  bounds: document.querySelector("#bounds-field"),
};

const examples = {
  equation_solve: ["x^2 + 4 = 0", "Linear or quadratic equation in x."],
  polynomial_solve: ["x^3 - 6x^2 + 11x - 6 = 0", "Polynomial equations through degree 8."],
  system_solve: ["", "Enter one linear equation per line."],
  log_expand: ["log(x*y)", "Use log(...), exp(...), sin(...), cos(...), and related functions."],
  log_condense: ["log(x) + log(y)", "Log identities assume positive real arguments."],
  exponential_solve: ["exp(x) = 3", "Use exp(x) or a numeric base raised to x."],
  differentiate: ["x^2 * sin(x)", "Product, quotient, and chain rules are applied."],
  integrate: ["x * exp(x)", "Leave both bounds blank for an indefinite integral."],
  limit: ["sin(x)/x", "The approach point and side can be selected below."],
  ode_solve: ["Derivative(y(x), x) + y(x) = 0", "Write a first-order ODE using Derivative(y(x), x)."],
  trig_solve: ["sin(x) = 0", "Periodic real solution sets are included where available."],
  trig_simplify: ["sin(x)^2 + cos(x)^2", "Simplify using trigonometric identities."],
  matrix_determinant: ["", "Enter a matrix as JSON, for example [[1, 2], [3, 4]]."],
  matrix_rref: ["", "Enter a matrix as JSON; rectangular matrices are supported."],
  matrix_inverse: ["", "Enter a square matrix as JSON."],
};

operationSelect.addEventListener("change", updateOperationFields);
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  hideError();

  try {
    const operation = operationSelect.value;
    const legacySolve = operation === "equation_solve";
    const payload = legacySolve ? { equation: equationInput.value } : buildRequest(operation);
    const response = await fetch(legacySolve ? "/api/solve" : "/api/operate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.detail || "The operation could not be completed.");
    }
    showResult(body);
  } catch (error) {
    results.hidden = true;
    errorMessage.textContent = error.message || "The solver is unavailable. Try again shortly.";
    errorMessage.hidden = false;
  } finally {
    setLoading(false);
  }
});

function buildRequest(operation) {
  const payload = { operation };
  const text = (selector) => document.querySelector(selector).value;
  if (["polynomial_solve", "exponential_solve", "ode_solve", "trig_solve"].includes(operation)) {
    payload.equation = equationInput.value;
    payload.variable = text("#variable");
  }
  if (operation === "system_solve") {
    payload.equations = equationsInput.value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  }
  if (["log_expand", "log_condense", "differentiate", "integrate", "limit", "trig_simplify"].includes(operation)) {
    payload.expression = expressionInput.value;
  }
  if (["differentiate", "integrate", "limit"].includes(operation)) {
    payload.variable = text("#variable");
  }
  if (operation === "differentiate") payload.order = Number(text("#order"));
  if (operation === "integrate") {
    const lower = text("#lower").trim();
    const upper = text("#upper").trim();
    if (lower) payload.lower = lower;
    if (upper) payload.upper = upper;
  }
  if (operation === "limit") {
    payload.point = text("#point");
    payload.direction = text("#direction");
  }
  if (operation.startsWith("matrix_")) {
    try {
      payload.matrix = JSON.parse(matrixInput.value);
    } catch {
      throw new Error("Enter the matrix as valid JSON, such as [[1, 2], [3, 4]].");
    }
  }
  return payload;
}

function updateOperationFields() {
  const operation = operationSelect.value;
  const isEquation = ["equation_solve", "polynomial_solve", "exponential_solve", "ode_solve", "trig_solve"].includes(operation);
  const isExpression = ["log_expand", "log_condense", "differentiate", "integrate", "limit", "trig_simplify"].includes(operation);
  const isMatrix = operation.startsWith("matrix_");
  fields.equation.hidden = !isEquation;
  fields.equations.hidden = operation !== "system_solve";
  fields.expression.hidden = !isExpression;
  fields.matrix.hidden = !isMatrix;
  fields.variable.hidden = !["polynomial_solve", "exponential_solve", "differentiate", "integrate", "limit", "trig_solve"].includes(operation);
  fields.order.hidden = operation !== "differentiate";
  fields.point.hidden = operation !== "limit";
  fields.direction.hidden = operation !== "limit";
  fields.bounds.hidden = operation !== "integrate";

  const [example, help] = examples[operation];
  if (isEquation) equationInput.value = operation === "equation_solve" ? "x^2 + 4 = 0" : example;
  if (isExpression) expressionInput.value = example;
  document.querySelector("#input-help").textContent = help;
}

function showResult(solution) {
  resultTitle.textContent = solution.operation
    ? formatValue(solution.result)
    : formatSolutions(solution);
  degreeBadge.textContent = solution.operation
    ? solution.operation.replaceAll("_", " ")
    : solution.degree === null
      ? "Identity"
      : solution.degree === 0
        ? "Constant"
        : solution.degree === 1
          ? "Linear"
          : "Quadratic";
  stepsList.replaceChildren(
    ...solution.steps.map((step) => {
      const item = document.createElement("li");
      item.textContent = step;
      return item;
    }),
  );
  errorMessage.hidden = true;
  results.hidden = false;
}

function formatValue(value) {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function formatSolutions(solution) {
  if (solution.status === "all_reals") return "Every real number is a solution";
  if (solution.status === "no_solution") return "No solution";
  return solution.solutions.map((root) => `x = ${root}`).join("  ·  ");
}

function setLoading(isLoading) {
  calculateButton.disabled = isLoading;
  calculateButton.querySelector("span").textContent = isLoading ? "Working…" : "Calculate";
}

function hideError() {
  errorMessage.hidden = true;
  errorMessage.textContent = "";
}

updateOperationFields();

const form = document.querySelector("#solver-form");
const operationSelect = document.querySelector("#operation");
const equationInput = document.querySelector("#equation");
const equationsInput = document.querySelector("#equations");
const expressionInput = document.querySelector("#expression");
const matrixInput = document.querySelector("#matrix");
const graphFields = document.querySelector("#graph-fields");
const results = document.querySelector("#results");
const errorMessage = document.querySelector("#error-message");
const resultTitle = document.querySelector("#result-title");
const degreeBadge = document.querySelector("#degree-badge");
const stepsList = document.querySelector("#steps");
const calculateButton = form.querySelector("button");
const imageUpload = document.querySelector("#image-upload");
const drawingCanvas = document.querySelector("#drawing-canvas");
const drawingContext = drawingCanvas.getContext("2d");
const recogniseButton = document.querySelector("#recognise-input");
const recognitionStatus = document.querySelector("#recognition-status");
const inputMethods = {
  type: document.querySelector("#type-input"),
  write: document.querySelector("#write-input"),
  upload: document.querySelector("#upload-input"),
};

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
  graph: graphFields,
};

let graphData = null;
let graphViewport = null;
let graphDrag = null;
let drawingPointer = null;
let drawingStrokes = [];
let inputMode = "type";
let isBusy = false;

const examples = {
  equation_solve: ["2a + 3 = 7", "Linear or quadratic equations in any letter, a–z or A–Z. Use ^ for powers, and 2*e for 2 times e."],
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
  graph: ["sin(x)", "Graph a real-valued function in one variable; try sin(x), a^2 or 1 / (t - 1)."],
};

for (const [mode, button] of Object.entries(inputMethods)) {
  button.addEventListener("click", () => setInputMode(mode));
}
operationSelect.addEventListener("change", updateOperationFields);
recogniseButton.addEventListener("click", recogniseVisualInput);
document.querySelector("#clear-drawing").addEventListener("click", clearDrawing);
document.querySelector("#undo-drawing").addEventListener("click", () => {
  drawingStrokes.pop();
  drawingPointer = null;
  redrawDrawing();
});
imageUpload.addEventListener("change", () => { recognitionStatus.textContent = ""; });
form.addEventListener("input", () => {
  results.hidden = true;
  hideError();
});
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  hideError();

  try {
    const operation = operationSelect.value;
    const legacySolve = operation === "equation_solve";
    const graphOperation = operation === "graph";
    const payload = legacySolve ? { equation: equationInput.value } : graphOperation ? buildGraphRequest() : buildRequest(operation);
    const response = await fetch(legacySolve ? "/api/solve" : graphOperation ? "/api/graph" : "/api/operate", {
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
    if (chosenVariable()) payload.variable = chosenVariable();
  }
  if (operation === "system_solve") {
    payload.equations = equationsInput.value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  }
  if (["log_expand", "log_condense", "differentiate", "integrate", "limit", "trig_simplify"].includes(operation)) {
    payload.expression = expressionInput.value;
  }
  if (["differentiate", "integrate", "limit"].includes(operation)) {
    if (chosenVariable()) payload.variable = chosenVariable();
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

// A hidden field can still hold a letter from a previous calculation.
function chosenVariable() {
  return fields.variable.hidden ? "" : document.querySelector("#variable").value.trim();
}

function buildGraphRequest() {
  const tangentText = document.querySelector("#tangent-points").value.trim();
  const tangentPoints = tangentText
    ? tangentText.split(",").map((value) => {
      const point = Number(value.trim());
      if (!Number.isFinite(point)) throw new Error("Tangent points must be finite numbers separated by commas.");
      return point;
    })
    : [];
  return {
    expression: expressionInput.value,
    ...(chosenVariable() ? { variable: chosenVariable() } : {}),
    x_min: Number(document.querySelector("#x-min").value),
    x_max: Number(document.querySelector("#x-max").value),
    sample_count: Number(document.querySelector("#sample-count").value),
    include_derivative: document.querySelector("#include-derivative").checked,
    tangent_points: tangentPoints,
  };
}

function updateOperationFields() {
  const operation = operationSelect.value;
  const isEquation = ["equation_solve", "polynomial_solve", "exponential_solve", "ode_solve", "trig_solve"].includes(operation);
  const isExpression = ["log_expand", "log_condense", "differentiate", "integrate", "limit", "trig_simplify", "graph"].includes(operation);
  const isMatrix = operation.startsWith("matrix_");
  const isGraph = operation === "graph";
  fields.equation.hidden = !isEquation;
  fields.equations.hidden = operation !== "system_solve";
  fields.expression.hidden = !isExpression;
  fields.matrix.hidden = !isMatrix;
  fields.variable.hidden = !["polynomial_solve", "exponential_solve", "differentiate", "integrate", "limit", "trig_solve", "graph"].includes(operation);
  fields.order.hidden = operation !== "differentiate";
  fields.point.hidden = operation !== "limit";
  fields.direction.hidden = operation !== "limit";
  fields.bounds.hidden = operation !== "integrate";
  fields.graph.hidden = !isGraph;

  const [example, help] = examples[operation];
  if (isEquation) equationInput.placeholder = example;
  if (isExpression) expressionInput.placeholder = example;
  equationInput.required = isEquation;
  expressionInput.required = isExpression;
  equationsInput.required = operation === "system_solve";
  matrixInput.required = isMatrix;
  document.querySelector("#input-help").textContent = help;
  document.querySelector("#calculation-label").textContent = operationSelect.selectedOptions[0].textContent;
  if (isMatrix) setInputMode("type");
  inputMethods.write.disabled = isMatrix;
  inputMethods.upload.disabled = isMatrix;
  results.hidden = true;
  hideError();
}

function setInputMode(mode) {
  inputMode = mode;
  for (const [name, button] of Object.entries(inputMethods)) {
    button.setAttribute("aria-pressed", String(name === mode));
  }
  document.querySelector("#visual-input").hidden = mode === "type";
  document.querySelector("#drawing-input").hidden = mode !== "write";
  document.querySelector("#upload-panel").hidden = mode !== "upload";
  recognitionStatus.textContent = "";
  if (mode === "write") resizeDrawingCanvas();
  if (mode === "type") {
    const activeInput = [equationInput, equationsInput, expressionInput, matrixInput]
      .find((input) => !input.parentElement.hidden);
    activeInput.focus();
  }
}

function showResult(solution) {
  resultTitle.textContent = solution.operation === "graph"
    ? solution.expression
    : solution.operation
      ? formatValue(solution.result)
    : formatSolutions(solution);
  degreeBadge.textContent = solution.operation
    ? operationSelect.selectedOptions[0].textContent
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
  const graphView = document.querySelector("#graph-view");
  graphView.hidden = solution.operation !== "graph";
  if (solution.operation === "graph") {
    graphData = solution;
    graphViewport = initialGraphViewport(solution);
    document.querySelector("#derivative-toggle-label").hidden = !solution.derivative;
    document.querySelector("#toggle-derivative").checked = false;
    document.querySelector("#tangent-toggle-label").hidden = !solution.tangents.length;
    document.querySelector("#toggle-tangents").checked = true;
    const asymptoteStatus = solution.asymptotes.status === "unsupported"
      ? `Asymptotes: unsupported (${solution.asymptotes.reason})`
      : `Asymptotes: ${solution.asymptotes.markers.length}`;
    const rootsStatus = solution.roots.status === "sampled_estimate"
      ? "sampled root estimates"
      : solution.roots.status.replaceAll("_", " ");
    document.querySelector("#graph-summary").textContent =
      `Roots: ${solution.roots.markers.length} ${rootsStatus} · ` +
      `Extrema: ${solution.extrema.markers.length} ${solution.extrema.status.replaceAll("_", " ")} · ` +
      `${asymptoteStatus} · Y-intercept: ${solution.y_intercept.status.replaceAll("_", " ")}`;
    requestAnimationFrame(drawGraph);
  } else {
    graphData = null;
  }
  errorMessage.hidden = true;
  results.hidden = false;
}

function initialGraphViewport(data) {
  const values = data.samples.map((sample) => sample.y).filter(Number.isFinite).sort((a, b) => a - b);
  const percentile = (fraction) => values[Math.floor((values.length - 1) * fraction)] || 0;
  let yMin = percentile(0.03);
  let yMax = percentile(0.97);
  if (!Number.isFinite(yMin) || !Number.isFinite(yMax) || yMin === yMax) {
    yMin = -1;
    yMax = 1;
  }
  const padding = Math.max((yMax - yMin) * 0.12, 0.5);
  return {
    xMin: data.domain.x_min,
    xMax: data.domain.x_max,
    yMin: yMin - padding,
    yMax: yMax + padding,
  };
}

function drawGraph() {
  if (!graphData || document.querySelector("#graph-view").hidden) return;
  const canvas = document.querySelector("#graph-canvas");
  const context = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const pixelRatio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * pixelRatio);
  canvas.height = Math.round(height * pixelRatio);
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.clearRect(0, 0, width, height);

  const margin = { left: 54, right: 18, top: 18, bottom: 34 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const toX = (value) => margin.left + (value - graphViewport.xMin) / (graphViewport.xMax - graphViewport.xMin) * plotWidth;
  const toY = (value) => margin.top + (graphViewport.yMax - value) / (graphViewport.yMax - graphViewport.yMin) * plotHeight;

  context.fillStyle = "#fff";
  context.fillRect(0, 0, width, height);
  context.font = "11px Segoe UI, Arial, sans-serif";
  context.strokeStyle = "#e9ece6";
  context.fillStyle = "#68736c";
  context.lineWidth = 1;
  for (let index = 0; index <= 8; index += 1) {
    const px = margin.left + index / 8 * plotWidth;
    const xValue = graphViewport.xMin + index / 8 * (graphViewport.xMax - graphViewport.xMin);
    context.beginPath();
    context.moveTo(px, margin.top);
    context.lineTo(px, height - margin.bottom);
    context.stroke();
    context.fillText(formatNumber(xValue), px - 16, height - 12);
  }
  for (let index = 0; index <= 6; index += 1) {
    const py = margin.top + index / 6 * plotHeight;
    const yValue = graphViewport.yMax - index / 6 * (graphViewport.yMax - graphViewport.yMin);
    context.beginPath();
    context.moveTo(margin.left, py);
    context.lineTo(width - margin.right, py);
    context.stroke();
    context.fillText(formatNumber(yValue), 4, py + 4);
  }
  context.strokeStyle = "#53655a";
  context.lineWidth = 1.5;
  if (graphViewport.xMin <= 0 && graphViewport.xMax >= 0) {
    context.beginPath();
    context.moveTo(toX(0), margin.top);
    context.lineTo(toX(0), height - margin.bottom);
    context.stroke();
  }
  if (graphViewport.yMin <= 0 && graphViewport.yMax >= 0) {
    context.beginPath();
    context.moveTo(margin.left, toY(0));
    context.lineTo(width - margin.right, toY(0));
    context.stroke();
  }

  context.save();
  context.beginPath();
  context.rect(margin.left, margin.top, plotWidth, plotHeight);
  context.clip();
  for (const asymptote of document.querySelector("#toggle-asymptotes").checked ? graphData.asymptotes.markers : []) {
    context.strokeStyle = "#cb5b48";
    context.setLineDash([5, 5]);
    context.beginPath();
    context.moveTo(toX(asymptote.x), margin.top);
    context.lineTo(toX(asymptote.x), height - margin.bottom);
    context.stroke();
    context.setLineDash([]);
  }
  if (document.querySelector("#toggle-derivative").checked && graphData.derivative) {
    drawSeries(context, graphData.derivative.samples, "#9482cc", toX, toY, graphData.asymptotes.markers);
  }
  drawSeries(context, graphData.samples, "#3c761e", toX, toY, graphData.asymptotes.markers);
  if (document.querySelector("#toggle-tangents").checked) {
    for (const tangent of graphData.tangents) {
      if (tangent.status !== "numerical_at_requested_point") continue;
      context.strokeStyle = "#e08932";
      context.lineWidth = 1.5;
      context.setLineDash([6, 4]);
      context.beginPath();
      context.moveTo(toX(graphViewport.xMin), toY(tangent.slope * graphViewport.xMin + tangent.intercept));
      context.lineTo(toX(graphViewport.xMax), toY(tangent.slope * graphViewport.xMax + tangent.intercept));
      context.stroke();
      context.setLineDash([]);
    }
  }
  drawMarkers(
    context,
    document.querySelector("#toggle-roots").checked ? graphData.roots.markers : [],
    toX,
    toY,
    "#b43535",
    "root",
  );
  drawMarkers(
    context,
    document.querySelector("#toggle-intercept").checked && graphData.y_intercept.status === "exact_symbolic"
      ? [graphData.y_intercept]
      : [],
    toX,
    toY,
    "#3278a8",
    "intercept",
  );
  drawMarkers(
    context,
    document.querySelector("#toggle-extrema").checked ? graphData.extrema.markers : [],
    toX,
    toY,
    "#a34e9c",
    "extremum",
  );
  context.restore();

  canvas.onpointerdown = (event) => {
    graphDrag = { x: event.clientX, y: event.clientY, viewport: { ...graphViewport } };
    canvas.setPointerCapture(event.pointerId);
  };
  canvas.onpointermove = (event) => {
    if (graphDrag) {
      const dx = (event.clientX - graphDrag.x) / plotWidth * (graphDrag.viewport.xMax - graphDrag.viewport.xMin);
      const dy = (event.clientY - graphDrag.y) / plotHeight * (graphDrag.viewport.yMax - graphDrag.viewport.yMin);
      graphViewport = {
        xMin: graphDrag.viewport.xMin - dx,
        xMax: graphDrag.viewport.xMax - dx,
        yMin: graphDrag.viewport.yMin + dy,
        yMax: graphDrag.viewport.yMax + dy,
      };
      drawGraph();
      return;
    }
    showGraphTooltip(event, canvas, margin, plotWidth, plotHeight);
  };
  canvas.onpointerup = () => { graphDrag = null; };
  canvas.onpointercancel = () => { graphDrag = null; };
  canvas.onpointerleave = () => {
    if (!graphDrag) document.querySelector("#graph-tooltip").hidden = true;
  };
  canvas.onwheel = (event) => {
    event.preventDefault();
    const bounds = canvas.getBoundingClientRect();
    const relativeX = (event.clientX - bounds.left - margin.left) / plotWidth;
    const relativeY = (event.clientY - bounds.top - margin.top) / plotHeight;
    const factor = event.deltaY < 0 ? 0.85 : 1.18;
    const xCentre = graphViewport.xMin + relativeX * (graphViewport.xMax - graphViewport.xMin);
    const yCentre = graphViewport.yMax - relativeY * (graphViewport.yMax - graphViewport.yMin);
    graphViewport = {
      xMin: xCentre + (graphViewport.xMin - xCentre) * factor,
      xMax: xCentre + (graphViewport.xMax - xCentre) * factor,
      yMin: yCentre + (graphViewport.yMin - yCentre) * factor,
      yMax: yCentre + (graphViewport.yMax - yCentre) * factor,
    };
    drawGraph();
  };
}

function drawSeries(context, samples, colour, toX, toY, asymptotes) {
  context.strokeStyle = colour;
  context.lineWidth = 2;
  context.beginPath();
  let connected = false;
  let previousX = null;
  for (const sample of samples) {
    if (!Number.isFinite(sample.y) || Math.abs(sample.y) > 1e100) {
      connected = false;
      previousX = sample.x;
      continue;
    }
    const crossesPole = previousX !== null && asymptotes.some((pole) =>
      pole.x > Math.min(previousX, sample.x) && pole.x < Math.max(previousX, sample.x));
    const pixelY = toY(sample.y);
    if (crossesPole || pixelY < -10000 || pixelY > 10000) connected = false;
    if (!connected) context.moveTo(toX(sample.x), pixelY);
    else context.lineTo(toX(sample.x), pixelY);
    connected = true;
    previousX = sample.x;
  }
  context.stroke();
}

function drawMarkers(context, markers, toX, toY, colour, markerType) {
  context.font = "11px Segoe UI, Arial, sans-serif";
  for (const marker of markers) {
    if (!Number.isFinite(marker.y) || marker.y < graphViewport.yMin || marker.y > graphViewport.yMax) continue;
    context.beginPath();
    context.arc(toX(marker.x), toY(marker.y), 4, 0, Math.PI * 2);
    context.fillStyle = colour;
    context.fill();
    context.fillStyle = "#26362c";
    const label = marker.kind === "sampled_estimate" ? "estimate" : "exact";
    const descriptor = markerType === "extremum" ? marker.extremum : markerType;
    context.fillText(`${descriptor} · ${label}`, toX(marker.x) + 6, toY(marker.y) - 6);
  }
}

function showGraphTooltip(event, canvas, margin, plotWidth, plotHeight) {
  const bounds = canvas.getBoundingClientRect();
  const xPosition = event.clientX - bounds.left - margin.left;
  const yPosition = event.clientY - bounds.top - margin.top;
  if (xPosition < 0 || xPosition > plotWidth || yPosition < 0 || yPosition > plotHeight) return;
  const xValue = graphViewport.xMin + xPosition / plotWidth * (graphViewport.xMax - graphViewport.xMin);
  const nearest = graphData.samples.reduce((best, sample) =>
    Math.abs(sample.x - xValue) < Math.abs(best.x - xValue) ? sample : best);
  const tooltip = document.querySelector("#graph-tooltip");
  const variable = graphData.variable || "x";
  tooltip.textContent = `${variable} = ${formatNumber(nearest.x)} · f(${variable}) = ${nearest.y === null ? "undefined" : formatNumber(nearest.y)}`;
  tooltip.style.left = `${Math.min(event.clientX - bounds.left + 12, bounds.width - 220)}px`;
  tooltip.style.top = `${Math.max(4, event.clientY - bounds.top - 28)}px`;
  tooltip.hidden = false;
}

function formatNumber(value) {
  if (!Number.isFinite(value)) return "undefined";
  return Number(value.toPrecision(5)).toString();
}

for (const selector of [
  "#toggle-roots",
  "#toggle-intercept",
  "#toggle-extrema",
  "#toggle-asymptotes",
  "#toggle-derivative",
  "#toggle-tangents",
]) {
  document.querySelector(selector).addEventListener("change", drawGraph);
}
new ResizeObserver(drawGraph).observe(document.querySelector("#graph-canvas"));

function formatSolutions(solution) {
  if (solution.status === "all_reals") return "Every real number is a solution";
  if (solution.status === "no_solution") return "No solution";
  return solution.solutions.map((root) => `${solution.variable} = ${root}`).join("  ·  ");
}

function formatValue(value) {
  if (typeof value === "string") return formatEquality(value);
  // Lists of answers read better inline; matrices keep their row structure.
  if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
    return value.map(formatEquality).join("  ·  ");
  }
  return JSON.stringify(value);
}

function formatEquality(text) {
  if (!text.startsWith("Eq(") || !text.endsWith(")")) return text;
  let depth = 0;
  for (let index = 3; index < text.length - 1; index += 1) {
    if (text[index] === "(") depth += 1;
    if (text[index] === ")") depth -= 1;
    if (text[index] === "," && depth === 0) {
      return `${text.slice(3, index).trim()} = ${text.slice(index + 1, -1).trim()}`;
    }
  }
  return text;
}

function setLoading(isLoading) {
  isBusy = isLoading;
  for (const control of [...form.querySelectorAll("input, select, textarea, button"), ...Object.values(inputMethods), imageUpload, recogniseButton]) {
    control.disabled = isLoading;
  }
  if (!isLoading) {
    const isMatrix = operationSelect.value.startsWith("matrix_");
    inputMethods.write.disabled = isMatrix;
    inputMethods.upload.disabled = isMatrix;
  }
  updateDrawingControls();
  form.setAttribute("aria-busy", String(isLoading));
  calculateButton.querySelector("span").textContent = isLoading ? "Working…" : "Calculate";
}

function hideError() {
  errorMessage.hidden = true;
  errorMessage.textContent = "";
}

updateOperationFields();
resizeDrawingCanvas();
new ResizeObserver(resizeDrawingCanvas).observe(drawingCanvas);
drawingCanvas.addEventListener("pointerdown", startDrawing);
drawingCanvas.addEventListener("pointermove", continueDrawing);
drawingCanvas.addEventListener("pointerup", stopDrawing);
drawingCanvas.addEventListener("pointercancel", stopDrawing);

async function recogniseVisualInput() {
  const file = inputMode === "upload" ? imageUpload.files[0] : null;
  const hasDrawing = inputMode === "write" && !isDrawingCanvasBlank();
  if (!file && !hasDrawing) {
    recognitionStatus.textContent = "Choose an image or draw a formula first.";
    return;
  }
  if (!canAcceptRecognisedInput()) return;

  setLoading(true);
  recognitionStatus.textContent = "Recognising maths locally…";
  try {
    const formData = new FormData();
    if (file) {
      formData.append("image", file);
    } else {
      const blob = await new Promise((resolve) => drawingCanvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("The drawing could not be prepared. Try again.");
      formData.append("image", blob, "drawing.png");
    }
    const response = await fetch("/api/recognise", { method: "POST", body: formData });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "The image could not be recognised.");
    insertRecognisedInput(body.expression);
    recognitionStatus.textContent = "Check the recognised text below. Edit anything that looks wrong, then calculate.";
  } catch (error) {
    recognitionStatus.textContent = error.message || "Local mathematical OCR is unavailable.";
  } finally {
    setLoading(false);
  }
}

function canAcceptRecognisedInput() {
  const operation = operationSelect.value;
  const equationOperations = [
    "equation_solve", "polynomial_solve", "exponential_solve", "ode_solve", "trig_solve",
  ];
  const expressionOperations = [
    "log_expand", "log_condense", "differentiate", "integrate", "limit", "trig_simplify", "graph",
  ];
  if (equationOperations.includes(operation) || expressionOperations.includes(operation) || operation === "system_solve") {
    return true;
  }
  recognitionStatus.textContent = "Choose an equation or expression operation before recognising maths.";
  return false;
}

function insertRecognisedInput(expression) {
  const operation = operationSelect.value;
  if (operation === "system_solve") {
    const existing = equationsInput.value.trim();
    equationsInput.value = existing ? `${existing}\n${expression}` : expression;
  } else if (["equation_solve", "polynomial_solve", "exponential_solve", "ode_solve", "trig_solve"].includes(operation)) {
    equationInput.value = expression;
  } else {
    expressionInput.value = expression;
  }
  results.hidden = true;
  hideError();
}

function resizeDrawingCanvas() {
  const bounds = drawingCanvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const pixelRatio = window.devicePixelRatio || 1;
  const width = Math.round(bounds.width * pixelRatio);
  const height = Math.round(bounds.height * pixelRatio);
  if (drawingCanvas.width === width && drawingCanvas.height === height) return;
  drawingCanvas.width = width;
  drawingCanvas.height = height;
  drawingContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  redrawDrawing();
}

function redrawDrawing() {
  const bounds = drawingCanvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  drawingContext.fillStyle = "#fff";
  drawingContext.fillRect(0, 0, bounds.width, bounds.height);
  drawingContext.strokeStyle = "#192b24";
  drawingContext.fillStyle = "#192b24";
  drawingContext.lineCap = "round";
  drawingContext.lineJoin = "round";
  for (const stroke of drawingStrokes) {
    const first = stroke[0];
    drawingContext.beginPath();
    drawingContext.arc(first.x * bounds.width, first.y * bounds.height, first.width / 2, 0, Math.PI * 2);
    drawingContext.fill();
    for (let index = 1; index < stroke.length; index += 1) {
      drawStrokeSegment(stroke[index - 1], stroke[index], bounds);
    }
  }
  updateDrawingControls();
}

function drawingPoint(event) {
  const bounds = drawingCanvas.getBoundingClientRect();
  return {
    x: (event.clientX - bounds.left) / bounds.width,
    y: (event.clientY - bounds.top) / bounds.height,
    width: event.pointerType === "pen" ? Math.max(1.5, 1 + event.pressure * 3) : 3,
  };
}

function drawStrokeSegment(previous, point, bounds) {
  drawingContext.beginPath();
  drawingContext.moveTo(previous.x * bounds.width, previous.y * bounds.height);
  drawingContext.lineTo(point.x * bounds.width, point.y * bounds.height);
  drawingContext.lineWidth = point.width;
  drawingContext.stroke();
}

function updateDrawingControls() {
  const blank = isDrawingCanvasBlank();
  document.querySelector("#undo-drawing").disabled = isBusy || blank;
  document.querySelector("#clear-drawing").disabled = isBusy || blank;
  document.querySelector("#drawing-placeholder").hidden = !blank;
}

function startDrawing(event) {
  if (isBusy || drawingPointer !== null || (event.pointerType === "mouse" && event.button !== 0)) return;
  event.preventDefault();
  drawingCanvas.setPointerCapture(event.pointerId);
  drawingPointer = event.pointerId;
  drawingStrokes.push([drawingPoint(event)]);
  recognitionStatus.textContent = "";
  redrawDrawing();
}

function continueDrawing(event) {
  if (isBusy || drawingPointer !== event.pointerId) return;
  const stroke = drawingStrokes[drawingStrokes.length - 1];
  const point = drawingPoint(event);
  drawStrokeSegment(stroke[stroke.length - 1], point, drawingCanvas.getBoundingClientRect());
  stroke.push(point);
}

function stopDrawing(event) {
  if (drawingPointer !== event.pointerId) return;
  if (event.type === "pointerup") continueDrawing(event);
  if (drawingCanvas.hasPointerCapture(event.pointerId)) drawingCanvas.releasePointerCapture(event.pointerId);
  drawingPointer = null;
}

function clearDrawing() {
  drawingStrokes = [];
  drawingPointer = null;
  redrawDrawing();
  recognitionStatus.textContent = "";
}

function isDrawingCanvasBlank() {
  return drawingStrokes.length === 0;
}

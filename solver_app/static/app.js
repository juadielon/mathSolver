const form = document.querySelector("#solver-form");
const equationInput = document.querySelector("#equation");
const results = document.querySelector("#results");
const errorMessage = document.querySelector("#error-message");
const resultTitle = document.querySelector("#result-title");
const degreeBadge = document.querySelector("#degree-badge");
const stepsList = document.querySelector("#steps");
const solveButton = form.querySelector("button");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  hideError();

  try {
    const response = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ equation: equationInput.value }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "The equation could not be solved.");
    }
    showResult(payload);
  } catch (error) {
    results.hidden = true;
    errorMessage.textContent = error.message || "The solver is unavailable. Try again shortly.";
    errorMessage.hidden = false;
  } finally {
    setLoading(false);
  }
});

function showResult(solution) {
  resultTitle.textContent = formatSolutions(solution);
  degreeBadge.textContent = solution.degree === null
    ? "Identity"
    : `${solution.degree === 0 ? "Constant" : solution.degree === 1 ? "Linear" : "Quadratic"}`;
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

function formatSolutions(solution) {
  if (solution.status === "all_reals") {
    return "Every real number is a solution";
  }
  if (solution.status === "no_solution") {
    return "No solution";
  }
  return solution.solutions.map((root) => `x = ${root}`).join("  ·  ");
}

function setLoading(isLoading) {
  solveButton.disabled = isLoading;
  solveButton.querySelector("span").textContent = isLoading ? "Solving…" : "Solve";
}

function hideError() {
  errorMessage.hidden = true;
  errorMessage.textContent = "";
}

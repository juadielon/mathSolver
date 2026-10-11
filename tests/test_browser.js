const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const source = readFileSync(join(__dirname, "..", "solver_app", "static", "app.js"), "utf8");
const formatter = source.slice(
  source.indexOf("function formatSolutions("),
  source.indexOf("function setLoading("),
);
const { formatSolutions, formatValue } = runInNewContext(
  `${formatter}\n({ formatSolutions, formatValue });`,
);

test("standard solver results display the returned variable", () => {
  for (const variable of ["x", "y", "z", "t"]) {
    assert.equal(
      formatSolutions({ status: "solved", variable, solutions: ["4/3"] }),
      `${variable} = 4/3`,
    );
  }
});

test("quadratic results label every root with the returned variable", () => {
  assert.equal(
    formatSolutions({ status: "solved", variable: "y", solutions: ["2", "3"] }),
    "y = 2  ·  y = 3",
  );
});

test("operation results show equalities as readable equations", () => {
  assert.equal(formatValue(["Eq(y(x), C1*exp(-x))"]), "y(x) = C1*exp(-x)");
  assert.equal(formatValue("Eq(log(x, 2), f(a, b))"), "log(x, 2) = f(a, b)");
  assert.equal(formatValue(["pi/6", "5*pi/6"]), "pi/6  ·  5*pi/6");
  assert.equal(formatValue("2*x"), "2*x");
  assert.equal(formatValue([["1", "0"], ["0", "1"]]), '[["1","0"],["0","1"]]');
});

test("identity and inconsistent result messages stay unchanged", () => {
  assert.equal(
    formatSolutions({ status: "all_reals", variable: "y", solutions: [] }),
    "Every real number is a solution",
  );
  assert.equal(
    formatSolutions({ status: "no_solution", variable: "y", solutions: [] }),
    "No solution",
  );
});

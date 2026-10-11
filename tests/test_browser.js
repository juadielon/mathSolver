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
const formatSolutions = runInNewContext(`${formatter}\nformatSolutions;`);

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

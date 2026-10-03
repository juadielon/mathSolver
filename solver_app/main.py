from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator

from solver_app.equations import EquationInputError, solve_equation
from solver_app.graphing import graph_function
from solver_app.operations import operate


class SolveRequest(BaseModel):
    equation: str = Field(min_length=1, max_length=512)


class OperationRequest(BaseModel):
    model_config = {"extra": "forbid"}

    operation: Literal[
        "polynomial_solve",
        "system_solve",
        "log_expand",
        "log_condense",
        "exponential_solve",
        "differentiate",
        "integrate",
        "limit",
        "ode_solve",
        "trig_solve",
        "trig_simplify",
        "matrix_determinant",
        "matrix_rref",
        "matrix_inverse",
    ]
    equation: str | None = Field(default=None, max_length=512)
    equations: list[str] | None = Field(default=None, max_length=8)
    expression: str | None = Field(default=None, max_length=512)
    variable: Literal["x", "y", "z", "t"] = "x"
    order: int = Field(default=1, ge=1, le=10)
    point: str | None = Field(default=None, max_length=128)
    direction: Literal["both", "+", "-"] = "both"
    lower: str | None = Field(default=None, max_length=128)
    upper: str | None = Field(default=None, max_length=128)
    matrix: list[list[str | int | float]] | None = Field(default=None, max_length=8)


class GraphRequest(BaseModel):
    model_config = {"extra": "forbid"}

    expression: str = Field(min_length=1, max_length=512)
    x_min: float = Field(default=-10, ge=-1000, le=1000, allow_inf_nan=False)
    x_max: float = Field(default=10, ge=-1000, le=1000, allow_inf_nan=False)
    sample_count: int = Field(default=800, ge=100, le=2000)
    include_derivative: StrictBool = False
    tangent_points: list[float] = Field(default_factory=list, max_length=10)

    @field_validator("x_min", "x_max", mode="before")
    @classmethod
    def reject_boolean_bounds(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Graph bounds must be finite numbers.")
        return value

    @field_validator("tangent_points", mode="before")
    @classmethod
    def reject_boolean_tangent_points(cls, values: object) -> object:
        if isinstance(values, list) and any(isinstance(value, bool) for value in values):
            raise ValueError("Tangent points must be finite numbers.")
        return values

    @model_validator(mode="after")
    def validate_graph_range(self) -> "GraphRequest":
        if self.x_min >= self.x_max:
            raise ValueError("The minimum x bound must be less than the maximum x bound.")
        if self.x_max - self.x_min > 2000:
            raise ValueError("The graph domain must be 2000 units wide or less.")
        if any(
            not value == value or value in (float("inf"), float("-inf"))
            or value < self.x_min or value > self.x_max
            for value in self.tangent_points
        ):
            raise ValueError("Tangent points must be finite numbers inside the graph domain.")
        return self


app = FastAPI(title="Genius Mathematical Solver", version="0.1.0")


@app.get("/api/ready")
def readiness() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/solve")
def solve(request: SolveRequest) -> dict[str, object]:
    try:
        return solve_equation(request.equation)
    except EquationInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/operate")
def operate_math(request: OperationRequest) -> dict[str, object]:
    try:
        return operate(request.model_dump(exclude_none=True))
    except EquationInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/graph")
def graph(request: GraphRequest) -> dict[str, object]:
    try:
        return graph_function(request.model_dump())
    except EquationInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


static_directory = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_directory, html=True), name="static")

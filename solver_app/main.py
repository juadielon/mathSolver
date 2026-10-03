from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from solver_app.equations import EquationInputError, solve_equation
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


static_directory = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_directory, html=True), name="static")

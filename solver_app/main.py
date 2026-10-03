from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from solver_app.equations import EquationInputError, solve_equation


class SolveRequest(BaseModel):
    equation: str = Field(min_length=1, max_length=512)


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


static_directory = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_directory, html=True), name="static")

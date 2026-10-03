import math

from html.parser import HTMLParser

from fastapi.testclient import TestClient

from solver_app.main import app


client = TestClient(app)


def graph(payload: dict[str, object]):
    response = client.post("/api/graph", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_graph_returns_exact_roots_and_y_intercept() -> None:
    result = graph({"expression": "x^2 - 1", "x_min": -2, "x_max": 2})

    assert result["roots"]["status"] == "exact_symbolic"
    assert [marker["exact_x"] for marker in result["roots"]["markers"]] == ["-1", "1"]
    assert result["y_intercept"]["exact_y"] == "-1"


def test_graph_returns_extrema_derivative_samples_and_tangent() -> None:
    result = graph(
        {
            "expression": "x^2",
            "x_min": -2,
            "x_max": 2,
            "sample_count": 400,
            "include_derivative": True,
            "tangent_points": [1],
        }
    )

    assert result["extrema"]["markers"][0]["extremum"] == "minimum"
    assert result["extrema"]["markers"][0]["kind"] == "exact_symbolic"
    assert len(result["derivative"]["samples"]) == 400
    tangent = result["tangents"][0]
    assert tangent["status"] == "numerical_at_requested_point"
    assert math.isclose(tangent["slope"], 2, abs_tol=1e-10)
    assert "x - 1" in tangent["line"]


def test_graph_detects_rational_asymptote_and_leaves_gap() -> None:
    result = graph(
        {"expression": "1 / (x - 1)", "x_min": -2, "x_max": 3, "sample_count": 501}
    )

    assert result["asymptotes"]["status"] == "exact_symbolic"
    assert result["asymptotes"]["markers"][0]["exact_x"] == "1"
    assert any(sample["y"] is None for sample in result["samples"])
    assert result["roots"]["markers"] == []


def test_graph_samples_trigonometric_function_and_labels_estimated_roots() -> None:
    result = graph(
        {
            "expression": "sin(x)",
            "x_min": -4,
            "x_max": 4,
            "sample_count": 400,
        }
    )

    assert len(result["samples"]) == 400
    assert result["roots"]["status"] == "sampled_estimate"
    assert result["roots"]["markers"]
    assert all(marker["kind"] == "sampled_estimate" for marker in result["roots"]["markers"])
    assert result["asymptotes"]["status"] == "none_detected"


def test_graph_detects_tangent_function_asymptotes() -> None:
    result = graph({"expression": "tan(x)", "x_min": -4, "x_max": 4})

    assert result["asymptotes"]["status"] == "exact_symbolic"
    assert len(result["asymptotes"]["markers"]) == 2
    assert all(marker["kind"] == "exact_symbolic" for marker in result["asymptotes"]["markers"])


def test_graph_rejects_malformed_unbounded_and_extra_requests() -> None:
    malformed = client.post("/api/graph", json={"expression": "__import__('os').system('id')"})
    unbounded_domain = client.post(
        "/api/graph",
        json={"expression": "x", "x_min": -1000, "x_max": 1000.1},
    )
    too_many_samples = client.post(
        "/api/graph",
        json={"expression": "x", "sample_count": 2001},
    )
    invalid_tangent = client.post(
        "/api/graph",
        json={"expression": "x", "tangent_points": [11]},
    )
    unexpected = client.post("/api/graph", json={"expression": "x", "unexpected": True})

    assert all(
        response.status_code == 422
        for response in (malformed, unbounded_domain, too_many_samples, invalid_tangent, unexpected)
    )
    assert all("detail" in response.json() for response in (malformed, unbounded_domain, too_many_samples))


def test_graph_ui_controls_are_served() -> None:
    page = client.get("/")

    assert page.status_code == 200
    assert 'value="graph"' in page.text
    assert 'id="graph-canvas"' in page.text


def test_graph_and_integral_controls_have_independent_visibility() -> None:
    class FieldHierarchyParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.ancestors: dict[str, list[str]] = {}
            self.hidden: set[str] = set()
            self.stack: list[tuple[str, str | None]] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attributes = dict(attrs)
            element_id = attributes.get("id")
            if element_id:
                self.ancestors[element_id] = [ancestor_id for _, ancestor_id in self.stack if ancestor_id]
                if "hidden" in attributes:
                    self.hidden.add(element_id)
            void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
            if tag not in void_tags:
                self.stack.append((tag, element_id))

        def handle_endtag(self, tag: str) -> None:
            open_tags = [open_tag for open_tag, _ in self.stack]
            if tag in open_tags:
                self.stack = self.stack[:len(open_tags) - 1 - open_tags[::-1].index(tag)]

    page = client.get("/")
    parser = FieldHierarchyParser()
    parser.feed(page.text)
    script = client.get("/app.js")

    assert parser.ancestors["bounds-field"] == parser.ancestors["graph-fields"]
    assert "bounds-field" in parser.ancestors["lower"]
    assert "graph-fields" in parser.ancestors["graph-range"]
    assert {"bounds-field", "graph-fields"} <= parser.hidden
    assert "fields.bounds.hidden = operation !== \"integrate\";" in script.text
    assert "fields.graph.hidden = !isGraph;" in script.text

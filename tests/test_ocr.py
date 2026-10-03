from io import BytesIO

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from solver_app import main
from solver_app.ocr import (
    ImageValidationError,
    OCRServiceError,
    OCRUnrecognisedError,
    decode_image,
    latex_to_expression,
)


client = TestClient(main.app)


def png_bytes(width: int = 320, height: int = 120) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(image).line((20, height // 2, width - 20, height // 2), fill="black", width=3)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_validation_accepts_supported_png_and_normalises_rgb() -> None:
    image = decode_image(png_bytes(), "image/png")

    assert image.mode == "RGB"
    assert image.size == (320, 120)


def test_image_validation_rejects_invalid_or_mismatched_image_types() -> None:
    for content, content_type in (
        (b"not an image", "image/png"),
        (png_bytes(), "image/jpeg"),
        (png_bytes(), "application/octet-stream"),
    ):
        try:
            decode_image(content, content_type)
        except ImageValidationError:
            pass
        else:
            raise AssertionError("Invalid image input must be rejected.")


def test_image_validation_rejects_dimensions_and_upload_size_limits() -> None:
    oversized_dimensions = png_bytes(5000, 2600)
    try:
        decode_image(oversized_dimensions, "image/png")
    except ImageValidationError as error:
        assert "4096 pixels per side" in str(error)
    else:
        raise AssertionError("Over-limit image dimensions must be rejected.")

    too_many_pixels = png_bytes(3600, 3600)
    try:
        decode_image(too_many_pixels, "image/png")
    except ImageValidationError as error:
        assert "12 megapixels total" in str(error)
    else:
        raise AssertionError("Over-limit image pixel counts must be rejected.")

    try:
        decode_image(b"x" * (8 * 1024 * 1024 + 1), "image/png")
    except ImageValidationError as error:
        assert error.status_code == 413
    else:
        raise AssertionError("Over-limit image uploads must be rejected.")


def test_latex_recognition_is_converted_to_solver_syntax() -> None:
    assert latex_to_expression(r"x^{2}+\frac{4}{2}=0") == "x^(2)+(4)/(2)=0"
    assert latex_to_expression(r"\sqrt{x}+\sin(x)") == "sqrt(x)+sin(x)"
    assert latex_to_expression(r"\ln(x)\, + \arcsin(x)") == "log(x) + asin(x)"
    assert latex_to_expression(r"\sin x") == "sin(x)"
    assert latex_to_expression(r"\cos 2x") == "cos(2*x)"
    assert latex_to_expression(r"\tan {x+1}") == "tan(x+1)"
    assert latex_to_expression(r"\log \frac{x}{2}") == "log((x)/(2))"
    assert latex_to_expression(r"\exp \sqrt{x}") == "exp(sqrt(x))"


def test_latex_function_argument_stops_before_following_operators() -> None:
    assert latex_to_expression(r"\sin x + \cos y") == "sin(x) + cos(y)"
    assert latex_to_expression(r"\sin x+y") == "sin(x)+y"
    assert latex_to_expression(r"\log x^2") == "log(x)^2"
    assert latex_to_expression(r"\log \frac{x}{y}+1") == "log((x)/(y))+1"


def test_latex_function_rejects_missing_arguments() -> None:
    try:
        latex_to_expression(r"\sin")
    except OCRUnrecognisedError:
        pass
    else:
        raise AssertionError("A function without an argument must be rejected.")


def test_unsupported_or_empty_recognition_is_explicit() -> None:
    for latex in ("", r"\int x\,dx", r"x_{1}+1", "this is not maths"):
        try:
            latex_to_expression(latex)
        except OCRUnrecognisedError:
            pass
        else:
            raise AssertionError("Unsupported OCR output must not be guessed.")


def test_ocr_endpoint_returns_editable_recognition(monkeypatch) -> None:
    monkeypatch.setattr(main, "recognise_math", lambda image: r"x^{2}+4=0")

    response = client.post(
        "/api/recognise",
        files={"image": ("formula.png", png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "latex": r"x^{2}+4=0",
        "expression": "x^(2)+4=0",
    }
    solved = client.post(
        "/api/solve", json={"equation": response.json()["expression"]}
    )
    assert solved.status_code == 200
    assert solved.json()["solutions"] == ["-2*I", "2*I"]


def test_ocr_endpoint_rejects_invalid_images_and_large_uploads() -> None:
    invalid = client.post(
        "/api/recognise",
        files={"image": ("invalid.png", b"not a png", "image/png")},
    )
    too_large = client.post(
        "/api/recognise",
        files={
            "image": (
                "large.png",
                b"x" * (8 * 1024 * 1024 + 1),
                "image/png",
            )
        },
    )

    assert invalid.status_code == 422
    assert "valid" in invalid.json()["detail"]
    assert too_large.status_code == 413
    assert "8 MiB" in too_large.json()["detail"]
    unsupported_type = client.post(
        "/api/recognise",
        files={"image": ("formula.gif", b"image", "image/gif")},
    )
    assert unsupported_type.status_code == 415


def test_ocr_endpoint_reports_blank_images_instead_of_guessing(monkeypatch) -> None:
    monkeypatch.setattr(main, "recognise_math", lambda _image: "0")
    blank = BytesIO()
    Image.new("RGB", (320, 120), "white").save(blank, format="PNG")

    response = client.post(
        "/api/recognise",
        files={"image": ("blank.png", blank.getvalue(), "image/png")},
    )

    assert response.status_code == 422
    assert "No mathematical marks" in response.json()["detail"]


def test_ocr_endpoint_reports_model_failure_and_unrecognised_output(monkeypatch) -> None:
    def unavailable(_image):
        raise OCRServiceError("The bundled mathematical OCR model failed.")

    monkeypatch.setattr(main, "recognise_math", unavailable)
    unavailable_response = client.post(
        "/api/recognise",
        files={"image": ("formula.png", png_bytes(), "image/png")},
    )
    monkeypatch.setattr(main, "recognise_math", lambda _image: r"\int x\,dx")
    unrecognised_response = client.post(
        "/api/recognise",
        files={"image": ("formula.png", png_bytes(), "image/png")},
    )

    assert unavailable_response.status_code == 503
    assert "OCR model failed" in unavailable_response.json()["detail"]
    assert unrecognised_response.status_code == 422
    assert "notation" in unrecognised_response.json()["detail"]

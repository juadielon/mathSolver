from __future__ import annotations

import hashlib
import logging
import re
import threading
import tokenize
import warnings
from io import BytesIO, StringIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from solver_app.equations import EquationInputError, _SUPPORTED_VARIABLES, _parse_expression


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
MAX_IMAGE_PIXELS = 12_000_000
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
MODEL_DIRECTORY = Path("/opt/unimernet_small")
MODEL_WEIGHT_SHA256 = "fa54b0a8126bb60060bc90818ce20a5ca1b5dd5d7da5c0983579f5c3a2cc90ea"

logger = logging.getLogger(__name__)
_model = None
_processor = None
_model_lock = threading.Lock()


class ImageValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


class OCRServiceError(RuntimeError):
    pass


class OCRUnrecognisedError(ValueError):
    pass


def decode_image(content: bytes, content_type: str | None) -> Image.Image:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ImageValidationError(
            "Upload a PNG, JPEG, or WebP image.", status_code=415
        )
    if not content:
        raise ImageValidationError("The uploaded image is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImageValidationError("Images must be 8 MiB or smaller.", status_code=413)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != ALLOWED_IMAGE_TYPES[content_type]:
                    raise ImageValidationError(
                        "The file content does not match its declared image type."
                    )
                if getattr(image, "n_frames", 1) != 1:
                    raise ImageValidationError(
                        "Animated images are not supported; upload a single-frame image."
                    )
                width, height = image.size
                if (
                    width < 1
                    or height < 1
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ImageValidationError(
                        "Images must be no larger than 4096 pixels per side "
                        "and 12 megapixels total."
                    )
                image.load()
                oriented = ImageOps.exif_transpose(image)
                if oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, "white")
                    background.alpha_composite(rgba)
                    return background.convert("RGB")
                return oriented.convert("RGB")
    except ImageValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as error:
        raise ImageValidationError(
            "The upload is not a valid, safely decodable image."
        ) from error


def latex_to_expression(latex: str) -> str:
    source = latex.strip()
    for left, right in ((r"\[", r"\]"), (r"\(", r"\)"), ("$$", "$$"), ("$", "$")):
        if source.startswith(left) and source.endswith(right):
            source = source[len(left) : len(source) - len(right)].strip()
            break
    source = source.replace("−", "-").replace("×", "*").replace("÷", "/")
    source = source.replace("π", "pi")
    source = re.sub(r"(?<=\d)\s+(?=\d)", "", source)
    output, position = _convert_latex_fragment(source, 0, expect_closing=False)
    expression = "".join(output).strip()
    expression = expression.replace("[", "(").replace("]", ")")
    if not expression or len(expression) > 512:
        raise OCRUnrecognisedError(
            "No supported equation or expression was recognised. "
            "Try a clearer, tightly cropped image or enter it manually."
        )
    if not any(character.isalpha() or character.isdigit() for character in expression):
        raise OCRUnrecognisedError(
            "The recognised image did not contain a usable mathematical expression."
        )
    sides = expression.split("=")
    if len(sides) > 2 or any(not side.strip() for side in sides):
        raise OCRUnrecognisedError(
            "The recognised text is not a supported equation or expression."
        )
    try:
        for side in sides:
            _parse_expression(
                side,
                allowed_variables=_SUPPORTED_VARIABLES - {"E"},
                allow_functions=True,
                allow_dependent_functions=True,
            )
    except EquationInputError as error:
        raise OCRUnrecognisedError(
            "The recognised text is outside the solver's supported syntax. "
            "Edit it manually before calculating."
        ) from error
    return expression


def image_has_ink(image: Image.Image) -> bool:
    histogram = image.convert("L").histogram()
    return sum(histogram[:245]) >= 32


def _convert_latex_fragment(
    source: str, position: int, *, expect_closing: bool
) -> tuple[list[str], int]:
    output: list[str] = []
    while position < len(source):
        character = source[position]
        if character == "}":
            if not expect_closing:
                raise OCRUnrecognisedError("The recognised formula has unmatched braces.")
            return output, position + 1
        if character == "{":
            nested, position = _convert_latex_fragment(
                source, position + 1, expect_closing=True
            )
            output.extend(("(", *nested, ")"))
            continue
        if character == "\\":
            command_end = position + 1
            while command_end < len(source) and source[command_end].isalpha():
                command_end += 1
            command = source[position + 1 : command_end]
            if not command:
                if position + 1 < len(source) and source[position + 1] in ",;:! ":
                    position += 2
                    continue
                position += 1
                if position < len(source) and source[position].isspace():
                    position += 1
                continue
            if command in {"left", "right", "displaystyle", "textstyle"}:
                position = command_end
                continue
            if command in {"frac", "dfrac", "tfrac"}:
                first, position = _read_latex_group(source, command_end)
                first_expression = "".join(
                    _convert_latex_fragment(first, 0, expect_closing=False)[0]
                )
                second, position = _read_latex_group(source, position)
                second_expression = "".join(
                    _convert_latex_fragment(second, 0, expect_closing=False)[0]
                )
                output.extend(("(", first_expression, ")/(", second_expression, ")"))
                continue
            if command == "sqrt":
                radicand, position = _read_latex_group(source, command_end)
                radicand_expression = "".join(
                    _convert_latex_fragment(radicand, 0, expect_closing=False)[0]
                )
                output.extend(("sqrt(", radicand_expression, ")"))
                continue
            if command in {
                "sin", "cos", "tan", "asin", "arcsin", "acos", "arccos",
                "atan", "arctan", "log", "ln", "exp",
            }:
                argument, position = _read_latex_function_argument(source, command_end)
                argument_expression = "".join(
                    _convert_latex_fragment(argument, 0, expect_closing=False)[0]
                )
                function_name = {
                    "arcsin": "asin",
                    "arccos": "acos",
                    "arctan": "atan",
                    "ln": "log",
                }.get(command, command)
                output.extend((function_name, "(", argument_expression, ")"))
                continue
            replacements = {
                "cdot": "*",
                "times": "*",
                "div": "/",
                "pi": "pi",
            }
            if command not in replacements:
                raise OCRUnrecognisedError(
                    "The recognised formula contains notation outside the solver's "
                    "supported syntax. Edit it manually before solving."
                )
            output.append(replacements[command])
            position = command_end
            continue
        if character == "_":
            raise OCRUnrecognisedError(
                "Subscript notation is not supported by the solver. "
                "Edit the recognised expression before solving."
            )
        if character.isalnum() or character in " +-*/=^().,[]":
            output.append(character)
            position += 1
            continue
        if character.isspace():
            position += 1
            continue
        raise OCRUnrecognisedError(
            "The recognised formula contains notation outside the solver's "
            "supported syntax. Edit it manually before solving."
        )
    if expect_closing:
        raise OCRUnrecognisedError("The recognised formula has unmatched braces.")
    return output, position


def _read_latex_group(source: str, position: int) -> tuple[str, int]:
    while position < len(source) and source[position].isspace():
        position += 1
    if position >= len(source) or source[position] != "{":
        raise OCRUnrecognisedError(
            "The recognised formula contains an incomplete fraction or root."
        )
    depth = 1
    start = position + 1
    position += 1
    while position < len(source):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start:position], position + 1
        position += 1
    raise OCRUnrecognisedError("The recognised formula has unmatched braces.")


def _read_latex_function_argument(source: str, position: int) -> tuple[str, int]:
    while position < len(source) and source[position].isspace():
        position += 1
    if position >= len(source):
        raise OCRUnrecognisedError(
            "The recognised formula has a function without an argument."
        )
    if source[position] == "{":
        return _read_latex_group(source, position)
    if source[position] == "\\":
        command_end = position + 1
        while command_end < len(source) and source[command_end].isalpha():
            command_end += 1
        command = source[position + 1 : command_end]
        if command in {"frac", "dfrac", "tfrac", "sqrt"}:
            if command == "sqrt":
                _, group_position = _read_latex_group(source, command_end)
            else:
                _, group_position = _read_latex_group(source, command_end)
                _, group_position = _read_latex_group(source, group_position)
            return source[position:group_position], group_position
        if command in {
            "sin", "cos", "tan", "asin", "arcsin", "acos", "arccos",
            "atan", "arctan", "log", "ln", "exp",
        }:
            _, end_position = _read_latex_function_argument(source, command_end)
            return source[position:end_position], end_position
        raise OCRUnrecognisedError(
            "The recognised function argument uses unsupported notation."
        )
    if source[position] == "(":
        end_position = position + 1
        depth = 1
        while end_position < len(source):
            if source[end_position] == "(":
                depth += 1
            elif source[end_position] == ")":
                depth -= 1
                if depth == 0:
                    return source[position + 1 : end_position], end_position + 1
            end_position += 1
        raise OCRUnrecognisedError(
            "The recognised formula has unmatched function parentheses."
        )
    if source[position].isalpha():
        return source[position], position + 1
    if source[position].isdigit():
        tokens = tokenize.generate_tokens(StringIO(source[position:]).readline)
        numeric_token = next(tokens)
        end_position = position + numeric_token.end[1]
        number = numeric_token.string
        next_token = next(tokens)
        if (
            next_token.type == tokenize.NAME
            and next_token.string in _SUPPORTED_VARIABLES
            and next_token.start == numeric_token.end
        ):
            return f"{number}*{next_token.string}", position + next_token.end[1]
        return number, end_position
    raise OCRUnrecognisedError(
        "Use braces or parentheses around compound function arguments."
    )


def recognise_math(image: Image.Image) -> str:
    global _model, _processor

    try:
        with _model_lock:
            if _model is None or _processor is None:
                _model, _processor = _load_model()
            import torch

            tensor = _processor(image).unsqueeze(0)
            with torch.inference_mode():
                result = _model.generate(
                    {"image": tensor}, temperature=0.0, do_sample=False
                )
            prediction = result["pred_str"][0].strip()
            if not prediction:
                raise OCRUnrecognisedError(
                    "No mathematical expression was recognised. "
                    "Try a clearer, tightly cropped image or enter it manually."
                )
            return prediction
    except OCRUnrecognisedError:
        raise
    except Exception as error:
        logger.exception("Bundled UniMERNet formula recognition failed")
        raise OCRServiceError(
            "The bundled mathematical OCR model failed to process this image. "
            "Check that the container was built successfully and try again."
        ) from error


def _load_model():
    import argparse
    import torch
    import unimernet  # noqa: F401 - registers the model, task, and image processor
    import unimernet.tasks as tasks
    from unimernet.common.config import Config
    from unimernet.processors import load_processor

    weight_path = MODEL_DIRECTORY / "unimernet_small.pth"
    if not weight_path.is_file():
        raise FileNotFoundError("The bundled UniMERNet checkpoint is missing.")
    digest = _sha256_file(weight_path)
    if digest != MODEL_WEIGHT_SHA256:
        raise ValueError("The bundled UniMERNet checkpoint failed its SHA-256 check.")

    torch.set_num_threads(1)
    config_path = Path(__file__).with_name("unimernet.yaml")
    config = Config(argparse.Namespace(cfg_path=str(config_path), options=None))
    task = tasks.setup_task(config)
    model = task.build_model(config).to("cpu").float().eval()
    processor = load_processor(
        "formula_image_eval",
        config.config.datasets.formula_rec_eval.vis_processor.eval,
    )
    return model, processor


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as checkpoint:
        for chunk in iter(lambda: checkpoint.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

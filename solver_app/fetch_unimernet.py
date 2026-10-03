import hashlib
from pathlib import Path

from huggingface_hub import snapshot_download


MODEL_REVISION = "82cb85440138c2038680fca410c8f70bb7343d6d"
MODEL_SHA256 = "fa54b0a8126bb60060bc90818ce20a5ca1b5dd5d7da5c0983579f5c3a2cc90ea"
MODEL_PATH = Path("/opt/unimernet_small")


def main() -> None:
    snapshot_download(
        repo_id="wanderkid/unimernet_small",
        revision=MODEL_REVISION,
        local_dir=MODEL_PATH,
        allow_patterns=[
            "config.json",
            "preprocessor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "unimernet_small.pth",
        ],
    )
    checkpoint = MODEL_PATH / "unimernet_small.pth"
    digest = _sha256_file(checkpoint)
    if digest != MODEL_SHA256:
        raise RuntimeError(
            f"UniMERNet checkpoint checksum mismatch: expected {MODEL_SHA256}, got {digest}"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as checkpoint:
        for chunk in iter(lambda: checkpoint.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()

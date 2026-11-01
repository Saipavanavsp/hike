"""Download the ONNX export of all-MiniLM-L6-v2 (used in production) into a directory.

Usage: python scripts/download_model.py /models/all-MiniLM-L6-v2
"""

import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO = "sentence-transformers/all-MiniLM-L6-v2"
FILES = {"onnx/model.onnx": "model.onnx", "tokenizer.json": "tokenizer.json"}


def main(target: str) -> None:
    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    for remote, local in FILES.items():
        path = hf_hub_download(repo_id=REPO, filename=remote)
        shutil.copyfile(path, out / local)
        print(f"saved {out / local}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "models_cache/all-MiniLM-L6-v2")

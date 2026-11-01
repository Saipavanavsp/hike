"""Text extraction from PDF / DOCX, run in a separate, resource-limited process.

PDF and DOCX parsers are large C/Python code bases that read attacker-controlled bytes, so
they do not run inside the API or worker process. `extract_text_isolated` starts

    python -I doc_extract.py <kind> <memory_mb> <cpu_seconds>

with the file on stdin and a minimal environment (no DATABASE_URL, JWT_SECRET, or other
secrets). The child lowers its own limits before parsing (address space, CPU time, no core
dumps; POSIX only) and the parent kills it after a wall-clock timeout. A crash, hang or
memory blow-up in the parser is reported as an unreadable file instead of taking the
service down.

This file must import only the standard library and the two parser packages: `python -I`
runs it without the application on sys.path.
"""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

MIN_TEXT_CHARS = 30
MAX_PAGES = 10


class InvalidResumeFile(ValueError):
    pass


def extract_text(data: bytes, kind: str) -> str:
    """Parse in the current process. Use extract_text_isolated for untrusted uploads."""
    import docx
    import pdfplumber

    try:
        if kind == "pdf":
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages[:MAX_PAGES]]
            text = "\n".join(pages)
        else:
            d = docx.Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            text = "\n".join(parts)
    except Exception as e:
        raise InvalidResumeFile("Could not read text from this file") from e
    text = text.replace("\x00", "").strip()
    if len(text) < MIN_TEXT_CHARS:
        raise InvalidResumeFile(
            "No readable text found. Scanned resumes are not supported; export a text PDF."
        )
    return text


def _child_env() -> dict[str, str]:
    keep = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG", "LC_ALL")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def extract_text_isolated(data: bytes, kind: str, timeout: int, memory_mb: int) -> str:
    cmd = [sys.executable, "-I", str(Path(__file__).resolve()), kind, str(memory_mb), str(timeout)]
    try:
        proc = subprocess.run(
            cmd, input=data, capture_output=True, timeout=timeout, env=_child_env(), check=False
        )
    except subprocess.TimeoutExpired as e:
        raise InvalidResumeFile("This file took too long to read") from e
    try:
        out = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        # Killed by a resource limit, or the parser crashed hard.
        raise InvalidResumeFile("Could not read text from this file") from e
    if not out.get("ok"):
        raise InvalidResumeFile(out.get("error") or "Could not read text from this file")
    return out["text"]


def _limit_resources(memory_mb: int, cpu_seconds: int) -> None:
    try:
        import resource
    except ImportError:  # Windows: only the wall-clock timeout applies
        return
    resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _main(argv: list[str]) -> int:
    kind, memory_mb, cpu_seconds = argv[0], int(argv[1]), int(argv[2])
    _limit_resources(memory_mb, cpu_seconds)
    data = sys.stdin.buffer.read()
    try:
        out = {"ok": True, "text": extract_text(data, kind)}
    except InvalidResumeFile as e:
        out = {"ok": False, "error": str(e)}
    except MemoryError:
        out = {"ok": False, "error": "This file is too complex to read"}
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))

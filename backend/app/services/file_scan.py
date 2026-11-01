"""Malware screening for uploads, run before a file is stored.

Two layers:
1. Built-in checks (always on): active content that a resume has no reason to contain.
   PDF: JavaScript, launch actions, embedded files, rich media, including names hidden with
   #xx escapes or inside compressed object streams. DOCX: VBA macros, ActiveX, embedded OLE
   objects, remote templates, and zip bombs. Also the EICAR anti-virus test signature.
2. ClamAV (MALWARE_SCAN=clamav): the file is streamed to clamd over TCP (INSTREAM).
   If the scanner is unreachable the upload is refused (fail closed).

Heuristics are not a virus scanner; they block the common resume-borne attack vectors.
"""

import io
import re
import socket
import struct
import zipfile
import zlib
from dataclasses import dataclass

from app.core.config import settings
from app.services.doc_extract import InvalidResumeFile

EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
PDF_BLOCKED_NAMES = {b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia"}
_PDF_NAME = re.compile(rb"/[A-Za-z0-9#]+")
_PDF_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
MAX_INFLATE_PER_STREAM = 2 * 1024 * 1024
MAX_INFLATE_TOTAL = 20 * 1024 * 1024
DOCX_MAX_UNCOMPRESSED = 50 * 1024 * 1024
DOCX_MAX_ENTRIES = 2000
DOCX_MAX_RATIO = 200


class MalwareDetected(InvalidResumeFile):
    def __init__(self, reason: str):
        super().__init__("This file was blocked by the security scan")
        self.reason = reason


class ScannerUnavailable(RuntimeError):
    pass


@dataclass
class ScanResult:
    engine: str  # "heuristic" or "heuristic+clamav"
    clean: bool
    detail: str = ""

    @property
    def summary(self) -> str:
        return f"{self.engine}:{'clean' if self.clean else self.detail}"[:60]


def _decode_name(name: bytes) -> bytes:
    return re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), name)


def _pdf_names(chunk: bytes) -> set[bytes]:
    return {_decode_name(n) for n in _PDF_NAME.findall(chunk)}


def scan_pdf(data: bytes) -> str | None:
    found = _pdf_names(data) & PDF_BLOCKED_NAMES
    inflated_total = 0
    for m in _PDF_STREAM.finditer(data):
        if found or inflated_total >= MAX_INFLATE_TOTAL:
            break
        try:
            chunk = zlib.decompressobj().decompress(m.group(1), MAX_INFLATE_PER_STREAM)
        except zlib.error:
            continue  # not Flate-encoded (images etc.)
        inflated_total += len(chunk)
        found |= _pdf_names(chunk) & PDF_BLOCKED_NAMES
    if found:
        return "pdf active content " + ",".join(sorted(n.decode() for n in found))
    return None


def scan_docx(data: bytes) -> str | None:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None  # rejected later as an invalid document
    infos = z.infolist()
    if len(infos) > DOCX_MAX_ENTRIES:
        return "docx too many entries"
    if sum(i.file_size for i in infos) > DOCX_MAX_UNCOMPRESSED:
        return "docx zip bomb"
    for info in infos:
        name = info.filename.lower()
        if info.compress_size and info.file_size / info.compress_size > DOCX_MAX_RATIO:
            return "docx zip bomb"
        if name.endswith("vbaproject.bin") or name.endswith(".vba"):
            return "docx macro"
        if name.startswith("word/activex/"):
            return "docx activex"
        if name.startswith("word/embeddings/") and name.endswith(".bin"):
            return "docx embedded ole object"
        if name.endswith(".rels"):
            rels = z.read(info)
            if b'TargetMode="External"' in rels and (
                b"attachedTemplate" in rels or b"oleObject" in rels
            ):
                return "docx remote template"
    return None


def heuristic_scan(data: bytes, kind: str) -> str | None:
    if EICAR in data:
        return "eicar test signature"
    return scan_pdf(data) if kind == "pdf" else scan_docx(data)


def clamav_scan(data: bytes, host: str, port: int, timeout: float = 15.0) -> str | None:
    """None if clean, else the signature name. Raises ScannerUnavailable."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 64 * 1024):
                chunk = data[i : i + 64 * 1024]
                sock.sendall(struct.pack("!L", len(chunk)) + chunk)
            sock.sendall(struct.pack("!L", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                part = sock.recv(4096)
                if not part:
                    break
                reply += part
    except OSError as e:
        raise ScannerUnavailable(f"ClamAV unreachable: {e}") from e
    text = reply.rstrip(b"\0").decode("utf-8", "replace").strip()
    if text.endswith("OK"):
        return None
    if text.endswith("FOUND"):
        return text.split(":", 1)[-1].removesuffix("FOUND").strip()
    raise ScannerUnavailable(f"ClamAV error: {text}")


def clamav_ping(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"zPING\0")
            return sock.recv(16).startswith(b"PONG")
    except OSError:
        return False


def scan_upload(data: bytes, kind: str) -> ScanResult:
    """Raise MalwareDetected / ScannerUnavailable, else return what was checked."""
    reason = heuristic_scan(data, kind)
    if reason:
        raise MalwareDetected(reason)
    if settings.malware_scan != "clamav":
        return ScanResult("heuristic", True)
    signature = clamav_scan(data, settings.clamav_host, settings.clamav_port)
    if signature:
        raise MalwareDetected(f"clamav {signature}")
    return ScanResult("heuristic+clamav", True)

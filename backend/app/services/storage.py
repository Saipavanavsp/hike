"""File storage behind a small interface: local disk in dev, any S3-compatible bucket in prod.

Files are encrypted before they reach either backend (Fernet: AES-128-CBC + HMAC-SHA256),
so a copied disk volume or a leaked bucket does not expose resumes. Files written before
encryption was added have no header and are read as-is.
"""

import base64
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet

from app.core.config import settings

ENCRYPTED_HEADER = b"HIKEENC1"


class Storage(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> None: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self) -> None:
        import boto3  # imported lazily: only needed when STORAGE_BACKEND=s3

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def fernet_from_secret(secret: str) -> Fernet:
    # Any string works as FILE_ENCRYPTION_KEY: it is stretched to a 32-byte Fernet key.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


class EncryptedStorage:
    def __init__(self, inner: Storage, fernet: Fernet):
        self.inner = inner
        self.fernet = fernet

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self.inner.save(key, ENCRYPTED_HEADER + self.fernet.encrypt(data), content_type)

    def read(self, key: str) -> bytes:
        blob = self.inner.read(key)
        if blob.startswith(ENCRYPTED_HEADER):
            return self.fernet.decrypt(blob[len(ENCRYPTED_HEADER) :])
        return blob  # legacy plaintext file

    def delete(self, key: str) -> None:
        self.inner.delete(key)


@lru_cache
def get_storage() -> Storage:
    inner: Storage = (
        S3Storage() if settings.storage_backend == "s3" else LocalStorage(settings.storage_dir)
    )
    secret = settings.file_encryption_key or f"hike-file-key:{settings.jwt_secret}"
    return EncryptedStorage(inner, fernet_from_secret(secret))

"""Object storage with two interchangeable backends.

The MinIO/S3 backend keeps audio behind boto3 and presigned URLs. The local
backend writes to a hostPath-mounted directory and serves audio back to the
browser through the FastAPI process. We need both because Olares blocks
cross-namespace access to the system MinIO; on Olares we run "local".
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlparse

import boto3
from botocore.client import Config

from app.config import settings


class _Backend(Protocol):
    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def delete_object(self, key: str) -> None: ...
    def get_audio_url(self, key: str, expires: timedelta) -> str: ...


class _S3Backend:
    def _client(self):
        parsed = urlparse(settings.minio_endpoint)
        return boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
            use_ssl=parsed.scheme == "https",
        )

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self._client().put_object(
            Bucket=settings.minio_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        obj = self._client().get_object(Bucket=settings.minio_bucket, Key=key)
        return obj["Body"].read()

    def delete_object(self, key: str) -> None:
        self._client().delete_object(Bucket=settings.minio_bucket, Key=key)

    def get_audio_url(self, key: str, expires: timedelta) -> str:
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.minio_bucket, "Key": key},
            ExpiresIn=int(expires.total_seconds()),
        )


class _LocalBackend:
    """Writes objects to `settings.storage_local_path / <key>`.

    Audio URLs become relative paths to the FastAPI audio router, which the
    browser fetches via the Next.js /api/* proxy. Range requests are served
    by Starlette's FileResponse, so the <audio> player can seek.
    """

    @property
    def root(self) -> Path:
        return Path(settings.storage_local_path)

    def _path(self, key: str) -> Path:
        return self.root / key

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete_object(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def get_audio_url(self, key: str, expires: timedelta) -> str:  # noqa: ARG002
        # Each path segment is encoded separately so slashes between
        # <org_id>/<filename> stay routable.
        encoded = "/".join(quote(part, safe="") for part in key.split("/"))
        return f"/api/v1/audio/{encoded}"

    def local_path(self, key: str) -> Path:
        return self._path(key)


def _make_backend() -> _Backend:
    if settings.storage_backend == "local":
        return _LocalBackend()
    return _S3Backend()


backend: _Backend = _make_backend()


def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    backend.upload_bytes(key, data, content_type)


def get_bytes(key: str) -> bytes:
    return backend.get_bytes(key)


def delete_object(key: str) -> None:
    backend.delete_object(key)


def get_presigned_url(key: str, expires: timedelta = timedelta(hours=1)) -> str:
    """URL the browser can use to fetch this object.

    For S3: a time-limited presigned URL. For local: a relative path to the
    FastAPI audio-streaming endpoint (the `expires` argument is ignored).
    """
    return backend.get_audio_url(key, expires)

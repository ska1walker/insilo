"""MinIO/S3 client wrapper."""

from datetime import timedelta
from urllib.parse import urlparse

import boto3
from botocore.client import Config

from app.config import settings


def _client():
    """Synchronous boto3 client. boto3 is sync — wrap in `asyncio.to_thread` if needed."""
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


def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(
        Bucket=settings.minio_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=settings.minio_bucket, Key=key)


def get_presigned_url(key: str, expires: timedelta = timedelta(hours=1)) -> str:
    """Return a temporary URL the browser can use to fetch this object directly."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": key},
        ExpiresIn=int(expires.total_seconds()),
    )

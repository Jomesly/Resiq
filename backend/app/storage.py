import hashlib
import hmac
import os
import shutil
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import UUID, uuid4

from app.config import Settings


def valid_key(key: str) -> str:
    path = PurePosixPath(key)
    if (
        not key
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in key
        or ":" in key
        or str(path) != key
    ):
        raise ValueError("Invalid storage key.")
    return key


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete_prefix(self, prefix: str) -> None: ...
    def objects(self) -> Iterator[tuple[str, datetime]]: ...
    def delete(self, key: str) -> None: ...


class LocalBlobStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        target = (self.root / valid_key(key)).resolve()
        if not target.is_relative_to(self.root) or target == self.root:
            raise ValueError("Storage path escaped its root.")
        return target

    def put(self, key: str, data: bytes) -> None:
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + "." + uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete_prefix(self, prefix: str) -> None:
        target = self.path(prefix)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    def objects(self):
        for directory, _, files in os.walk(self.root, followlinks=False):
            for name in files:
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                try:
                    yield (
                        path.relative_to(self.root).as_posix(),
                        datetime.fromtimestamp(path.stat().st_mtime, UTC),
                    )
                except FileNotFoundError:
                    continue

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)


class S3BlobStore:
    def __init__(self, settings: Settings):
        import boto3
        from botocore.config import Config

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            config=Config(
                connect_timeout=5,
                read_timeout=30,
                retries={"mode": "standard", "total_max_attempts": 2},
            ),
        )
        self.bucket = settings.s3_bucket

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=valid_key(key), Body=data)

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=valid_key(key))
            with response["Body"] as body:
                return body.read()
        except self.client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(key) from exc

    def delete_prefix(self, prefix: str) -> None:
        prefix = valid_key(prefix).rstrip("/") + "/"
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        )
        for page in pages:
            keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if keys:
                result = self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})
                if result.get("Errors"):
                    raise OSError("Could not remove all receipt images.")

    def objects(self):
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            for item in page.get("Contents", []):
                yield item["Key"], item["LastModified"]

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=valid_key(key))


def get_store(settings: Settings) -> BlobStore:
    return (
        S3BlobStore(settings)
        if settings.storage_backend == "s3"
        else LocalBlobStore(settings.storage_root)
    )


class ImageSigner:
    variants = {"original", "processed", "warped", "enhanced"}

    def __init__(self, settings: Settings):
        self.key = settings.signing_secret.get_secret_value().encode()
        self.ttl = settings.image_url_ttl_s
        self.base = settings.public_api_url.rstrip("/")

    def digest(self, receipt_id: UUID, variant: str, expiry: int) -> str:
        return hmac.new(
            self.key, f"{receipt_id}:{variant}:{expiry}".encode(), hashlib.sha256
        ).hexdigest()

    def url(self, receipt_id: UUID, variant: str) -> str:
        expiry = int(time.time()) + self.ttl
        return f"{self.base}/api/images/{receipt_id}/{variant}?exp={expiry}&sig={self.digest(receipt_id, variant, expiry)}"

    def valid(self, receipt_id: UUID, variant: str, expiry: int, signature: str) -> bool:
        now = int(time.time())
        return (
            variant in self.variants
            and now <= expiry <= now + self.ttl
            and hmac.compare_digest(self.digest(receipt_id, variant, expiry), signature)
        )

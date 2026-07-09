from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class CaseLawStorage:
    backend_name = "base"

    def put_file(self, *, local_path, key, content_type="application/octet-stream"):
        raise NotImplementedError

    def put_bytes(self, *, content, key, content_type="application/octet-stream"):
        raise NotImplementedError

    def exists(self, key):
        raise NotImplementedError

    def open(self, key):
        raise NotImplementedError

    def url_for(self, key):
        return ""


class FilesystemCaseLawStorage(CaseLawStorage):
    backend_name = "filesystem"

    def __init__(self, root=None):
        self.root = Path(root or settings.CASELAW_STORAGE_ROOT)
        if not self.root.is_absolute():
            self.root = settings.REPO_DIR / self.root

    def _path(self, key):
        clean_key = str(key).lstrip("/")
        path = (self.root / clean_key).resolve()
        root = self.root.resolve()
        if root not in [path, *path.parents]:
            raise ValueError("Storage key escapes CASELAW_STORAGE_ROOT")
        return path

    def put_file(self, *, local_path, key, content_type="application/octet-stream"):
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, destination)
        return {"key": key, "size": destination.stat().st_size, "sha256": sha256_file(destination)}

    def put_bytes(self, *, content, key, content_type="application/octet-stream"):
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return {"key": key, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}

    def exists(self, key):
        return self._path(key).exists()

    def open(self, key):
        return self._path(key).open("rb")


class ObjectCaseLawStorage(CaseLawStorage):
    backend_name = "object"

    def __init__(self):
        if not settings.CASELAW_STORAGE_BUCKET:
            raise ImproperlyConfigured("CASELAW_STORAGE_BUCKET is required for object caselaw storage.")
        try:
            import boto3
        except ImportError as exc:
            raise ImproperlyConfigured("Install boto3 to use CASELAW_STORAGE_BACKEND=object.") from exc
        self.bucket = settings.CASELAW_STORAGE_BUCKET
        kwargs = {
            "aws_access_key_id": settings.CASELAW_STORAGE_ACCESS_KEY_ID or None,
            "aws_secret_access_key": settings.CASELAW_STORAGE_SECRET_ACCESS_KEY or None,
            "region_name": settings.CASELAW_STORAGE_REGION or None,
            "endpoint_url": settings.CASELAW_STORAGE_ENDPOINT_URL or None,
        }
        self.client = boto3.client("s3", **{key: value for key, value in kwargs.items() if value})

    def put_file(self, *, local_path, key, content_type="application/octet-stream"):
        path = Path(local_path)
        self.client.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return {"key": key, "size": path.stat().st_size, "sha256": sha256_file(path)}

    def put_bytes(self, *, content, key, content_type="application/octet-stream"):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)
        return {"key": key, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def open(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"]


def get_caselaw_storage():
    backend = settings.CASELAW_STORAGE_BACKEND
    if backend == "filesystem":
        return FilesystemCaseLawStorage()
    if backend == "object":
        return ObjectCaseLawStorage()
    raise ImproperlyConfigured(f"Unsupported CASELAW_STORAGE_BACKEND: {backend}")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

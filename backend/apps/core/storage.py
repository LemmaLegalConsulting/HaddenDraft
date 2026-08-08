"""Document storage: the boundary between documents the repository carries and
documents an organization side-loads.

Case-law PDFs and private organization content are too large, too private, or
too frequently revised to live in git. They arrive through this layer instead,
which splits every store into two areas:

    raw/        what an operator uploads. Source material, in whatever shape it
                came in. Nothing serves directly out of here.
    published/  what the application reads and serves. Written by an ingest or
                publish step, never by hand.

Keeping those apart is what makes a partial upload safe: files can accumulate
under ``raw/`` for as long as it takes without the running application seeing a
half-finished corpus, and a publish step is the single moment the change becomes
visible.

Two backends implement the interface. ``filesystem`` is what local development
and the current Azure deployment use, where the root is a mounted file share.
``s3`` talks to any S3-compatible endpoint and is the migration target; it is
fully implemented but stays dormant until ``DOCUMENT_STORAGE_BACKEND=s3`` and a
bucket are configured. Callers only ever see :class:`DocumentStorage`, so moving
between them is configuration rather than code.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

RAW = "raw"
PUBLISHED = "published"
AREAS = (RAW, PUBLISHED)


class DocumentStorage:
    """Key/value storage for opaque document bytes.

    Keys are ``/``-separated relative paths. Implementations must reject keys
    that escape the configured root or bucket prefix.
    """

    backend_name = "base"

    def put_file(self, *, local_path, key, content_type="application/octet-stream"):
        raise NotImplementedError

    def put_bytes(self, *, content, key, content_type="application/octet-stream"):
        raise NotImplementedError

    def exists(self, key):
        raise NotImplementedError

    def open(self, key):
        raise NotImplementedError

    def iter_keys(self, prefix=""):
        """Yield every key under ``prefix``, in no guaranteed order."""
        raise NotImplementedError

    def download_to(self, key, local_path):
        """Copy one object to a local path, creating parent directories.

        Ingestion needs real files on disk — it hashes them, reads them with
        pypdf, and hands paths to other tooling — so every backend has to be
        able to materialize an object locally.
        """
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.open(key) as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)
        return destination

    def url_for(self, key):
        return ""


class FilesystemDocumentStorage(DocumentStorage):
    backend_name = "filesystem"

    def __init__(self, root):
        self.root = Path(root)

    def _path(self, key):
        clean_key = str(key).lstrip("/")
        path = (self.root / clean_key).resolve()
        root = self.root.resolve()
        if root not in [path, *path.parents]:
            raise ValueError("Storage key escapes the storage root")
        return path

    def put_file(self, *, local_path, key, content_type="application/octet-stream"):
        source = Path(local_path)
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Re-publishing an artifact that is already in place is a no-op rather
        # than an error, so an interrupted ingest can simply be re-run.
        if not (destination.exists() and source.samefile(destination)):
            shutil.copyfile(source, destination)
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

    def iter_keys(self, prefix=""):
        base = self._path(prefix) if prefix else self.root
        if not base.exists():
            return
        root = self.root.resolve()
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            yield path.resolve().relative_to(root).as_posix()

    def download_to(self, key, local_path):
        source = self._path(key)
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not (destination.exists() and source.samefile(destination)):
            shutil.copyfile(source, destination)
        return destination


class S3DocumentStorage(DocumentStorage):
    """Any S3-compatible endpoint: AWS S3, Cloudflare R2, Backblaze B2, MinIO.

    Not exercised by the current deployment. It exists so that switching stores
    is a configuration change, and so the interface above stays honest about
    what an object store can and cannot do cheaply — note that ``iter_keys``
    paginates and ``download_to`` transfers bytes, neither of which is free the
    way the filesystem equivalents are.
    """

    backend_name = "s3"

    def __init__(self, *, bucket, endpoint_url=None, access_key_id=None,
                 secret_access_key=None, region=None):
        if not bucket:
            raise ImproperlyConfigured("DOCUMENT_STORAGE_BUCKET is required for the s3 backend.")
        try:
            import boto3
        except ImportError as exc:
            raise ImproperlyConfigured("Install boto3 to use DOCUMENT_STORAGE_BACKEND=s3.") from exc
        self.bucket = bucket
        options = {
            "aws_access_key_id": access_key_id or None,
            "aws_secret_access_key": secret_access_key or None,
            "region_name": region or None,
            "endpoint_url": endpoint_url or None,
        }
        self.client = boto3.client("s3", **{key: value for key, value in options.items() if value})

    @staticmethod
    def _key(key):
        clean_key = str(key).lstrip("/")
        # ".." never has a legitimate meaning in an S3 key and would let a
        # crafted sidecar filename write outside its area.
        if ".." in clean_key.split("/"):
            raise ValueError("Storage key escapes its area")
        return clean_key

    def put_file(self, *, local_path, key, content_type="application/octet-stream"):
        path = Path(local_path)
        self.client.upload_file(str(path), self.bucket, self._key(key),
                                ExtraArgs={"ContentType": content_type})
        return {"key": key, "size": path.stat().st_size, "sha256": sha256_file(path)}

    def put_bytes(self, *, content, key, content_type="application/octet-stream"):
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=content,
                               ContentType=content_type)
        return {"key": key, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except Exception:
            return False

    def open(self, key):
        return self.client.get_object(Bucket=self.bucket, Key=self._key(key))["Body"]

    def iter_keys(self, prefix=""):
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._key(prefix) if prefix else ""):
            for item in page.get("Contents", []):
                yield item["Key"]


class PrefixedDocumentStorage(DocumentStorage):
    """A view of another store scoped under one key prefix.

    This is how an area becomes a storage object in its own right: callers hold
    a handle that can only see ``raw/`` or only see ``published/``, so writing
    across the boundary takes a deliberate second handle rather than a typo.
    """

    def __init__(self, inner, prefix):
        self.inner = inner
        self.prefix = prefix.strip("/")
        self.backend_name = inner.backend_name

    def _key(self, key):
        clean_key = str(key).lstrip("/")
        return f"{self.prefix}/{clean_key}" if self.prefix else clean_key

    def _strip(self, key):
        marker = f"{self.prefix}/"
        return key[len(marker):] if self.prefix and key.startswith(marker) else key

    def put_file(self, *, local_path, key, content_type="application/octet-stream"):
        result = self.inner.put_file(local_path=local_path, key=self._key(key), content_type=content_type)
        return {**result, "key": key}

    def put_bytes(self, *, content, key, content_type="application/octet-stream"):
        result = self.inner.put_bytes(content=content, key=self._key(key), content_type=content_type)
        return {**result, "key": key}

    def exists(self, key):
        return self.inner.exists(self._key(key))

    def open(self, key):
        return self.inner.open(self._key(key))

    def iter_keys(self, prefix=""):
        for key in self.inner.iter_keys(self._key(prefix) if prefix else self.prefix):
            yield self._strip(key)

    def download_to(self, key, local_path):
        return self.inner.download_to(self._key(key), local_path)

    def url_for(self, key):
        return self.inner.url_for(self._key(key))


def build_backend():
    """Construct the configured backend, without any area prefix applied."""
    backend = settings.DOCUMENT_STORAGE_BACKEND
    if backend == "filesystem":
        return FilesystemDocumentStorage(settings.DOCUMENT_STORAGE_ROOT)
    if backend == "s3":
        return S3DocumentStorage(
            bucket=settings.DOCUMENT_STORAGE_BUCKET,
            endpoint_url=settings.DOCUMENT_STORAGE_ENDPOINT_URL,
            access_key_id=settings.DOCUMENT_STORAGE_ACCESS_KEY_ID,
            secret_access_key=settings.DOCUMENT_STORAGE_SECRET_ACCESS_KEY,
            region=settings.DOCUMENT_STORAGE_REGION,
        )
    raise ImproperlyConfigured(f"Unsupported DOCUMENT_STORAGE_BACKEND: {backend}")


def get_document_storage(area=PUBLISHED):
    if area not in AREAS:
        raise ValueError(f"Unknown storage area: {area}. Expected one of {AREAS}.")
    return PrefixedDocumentStorage(build_backend(), area)


def copy_area(source, destination, *, prefix="", content_type="application/octet-stream",
              skip_existing=True, progress=None):
    """Stream every object under ``prefix`` from one storage handle to another.

    Goes through the public interface rather than the filesystem, so publishing
    behaves the same whether the store is a mounted share today or an S3 bucket
    later. Streams via a temporary file instead of reading whole objects into
    memory, because a scanned appellate PDF can be tens of megabytes.

    Returns ``(copied, skipped)``.
    """
    import tempfile

    copied = 0
    skipped = 0
    for key in source.iter_keys(prefix):
        if skip_existing and destination.exists(key):
            skipped += 1
            continue
        with tempfile.TemporaryDirectory() as staging:
            staged = Path(staging) / Path(key).name
            source.download_to(key, staged)
            destination.put_file(local_path=staged, key=key, content_type=content_type)
        copied += 1
        if progress:
            progress(key)
    return copied, skipped


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

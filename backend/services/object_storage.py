"""Domain-neutral private object storage for local development and S3 APIs."""
import os
from pathlib import Path, PurePosixPath
from uuid import uuid4
from urllib.parse import urlparse

from flask import current_app


class ObjectStorageError(RuntimeError):
    pass


def _key(value: str) -> str:
    if (not isinstance(value, str) or not value or '\\' in value
            or value.startswith('/') or any(part in ('', '.', '..') for part in value.split('/'))):
        raise ObjectStorageError('Chave de objeto invalida.')
    return value


class LocalObjectStorage:
    provider = 'local'

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        safe = _key(key)
        path = (self.root / PurePosixPath(safe)).resolve()
        if not path.is_relative_to(self.root):
            raise ObjectStorageError('Chave de objeto invalida.')
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        temporary = path.with_name(f'.{uuid4().hex}.tmp')
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('xb') as handle:
                handle.write(data)
            os.replace(temporary, path)
        except OSError as exc:
            raise ObjectStorageError('Armazenamento de objetos indisponivel.') from exc
        finally:
            temporary.unlink(missing_ok=True)

    def read(self, key: str, max_bytes: int) -> bytes:
        try:
            with self._path(key).open('rb') as handle:
                data = handle.read(max_bytes + 1)
        except OSError as exc:
            raise ObjectStorageError('Armazenamento de objetos indisponivel.') from exc
        if len(data) > max_bytes:
            raise ObjectStorageError('Objeto excede o limite de leitura.')
        return data

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise ObjectStorageError('Armazenamento de objetos indisponivel.') from exc


class S3ObjectStorage:
    provider = 's3'

    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(Bucket=self.bucket, Key=_key(key), Body=data, ContentType=content_type)
        except Exception as exc:
            raise ObjectStorageError('Armazenamento de objetos indisponivel.') from exc

    def read(self, key: str, max_bytes: int) -> bytes:
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=_key(key))['Body']
            try:
                data = body.read(max_bytes + 1)
            finally:
                body.close()
        except Exception as exc:
            raise ObjectStorageError('Armazenamento de objetos indisponivel.') from exc
        if len(data) > max_bytes:
            raise ObjectStorageError('Objeto excede o limite de leitura.')
        return data

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=_key(key))
        except Exception as exc:
            raise ObjectStorageError('Armazenamento de objetos indisponivel.') from exc


class LegacyDriveObjectStorage:
    """Read-only adapter for existing Google Drive file references."""
    provider = 'google_drive'

    def read(self, key: str, max_bytes: int) -> bytes:
        try:
            from services.drive_service import get_drive_service
            data = get_drive_service().download_file(_key(key))
        except Exception as exc:
            raise ObjectStorageError('Arquivo legado indisponivel.') from exc
        if len(data) > max_bytes:
            raise ObjectStorageError('Objeto excede o limite de leitura.')
        return data


def get_object_storage(provider=None):
    """Resolve provider from server config; never accept provider or credentials from HTTP."""
    config = current_app.config
    local_allowed = bool(config.get('DEBUG') or config.get('TESTING'))
    provider = provider or config.get('STORAGE_PROVIDER') or ('local' if local_allowed else '')
    if provider == 'google_drive':
        return LegacyDriveObjectStorage()
    if provider == 'local' and local_allowed:
        return LocalObjectStorage(Path(config['OBJECT_STORAGE_LOCAL_DIR']))
    if provider == 's3':
        endpoint = config.get('OBJECT_STORAGE_ENDPOINT', '')
        parsed = urlparse(endpoint)
        if (not endpoint or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or (parsed.scheme != 'https' and not local_allowed)
                or parsed.scheme not in ('https', 'http')
                or (not local_allowed and (not parsed.hostname.endswith('.r2.cloudflarestorage.com')
                                           or parsed.path not in ('', '/')))):
            raise ObjectStorageError('Configuracao de object storage invalida.')
        if not all(config.get(name) for name in (
                'OBJECT_STORAGE_BUCKET', 'OBJECT_STORAGE_ACCESS_KEY_ID',
                'OBJECT_STORAGE_SECRET_ACCESS_KEY', 'OBJECT_STORAGE_REGION')):
            raise ObjectStorageError('Configuracao de object storage incompleta.')
        try:
            import boto3
            client = boto3.client('s3', endpoint_url=endpoint,
                aws_access_key_id=config['OBJECT_STORAGE_ACCESS_KEY_ID'],
                aws_secret_access_key=config['OBJECT_STORAGE_SECRET_ACCESS_KEY'],
                region_name=config['OBJECT_STORAGE_REGION'])
        except Exception as exc:
            raise ObjectStorageError('Armazenamento de objetos indisponivel.') from exc
        return S3ObjectStorage(client, config['OBJECT_STORAGE_BUCKET'])
    raise ObjectStorageError('STORAGE_PROVIDER deve ser s3 em producao ou local no desenvolvimento.')

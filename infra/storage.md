# Storage

## Why

Recording artifacts (audio files, video, screenshots) need persistence beyond the database. Binary media doesn't belong in Postgres — it needs an object storage layer with presigned URL support for client downloads. The storage abstraction lets the stack run anywhere: MinIO in Docker Compose, S3 in production, local filesystem for tests.

## What

3 storage backends behind a unified `StorageClient` interface. Each backend implements: `upload_file`, `download_file`, `get_presigned_url`, `delete_file`, `file_exists`.

### Backends

| Backend | When to use | Presigned URLs | Config |
|---------|-------------|---------------|--------|
| **MinIO** (default) | Docker Compose, self-hosted | Yes (S3-compatible) | `STORAGE_BACKEND=minio` |
| **S3** | AWS production | Yes (native) | `STORAGE_BACKEND=s3` |
| **Local filesystem** | Testing without object storage | No (returns `file://` URI) | `STORAGE_BACKEND=local` |

MinIO and S3 both use the same `MinIOStorageClient` class (boto3 S3 client underneath). The difference is endpoint and auth configuration.

### Data model

Storage is tracked in two Postgres tables:

```
recordings ──1:N──► media_files
                      ├── storage_path (e.g., "recordings/123/audio.wav")
                      ├── storage_backend ("minio", "s3", "local")
                      ├── type ("audio", "video", "screenshot")
                      ├── format ("wav", "webm", "opus", "mp3", "jpg", "png")
                      └── file_size_bytes, duration_seconds, metadata (JSONB)
```

Default bucket: `vexa-recordings`.

### Configuration

**MinIO (default):**

| Env var | Default | Purpose |
|---------|---------|---------|
| `STORAGE_BACKEND` | `minio` | Backend selector |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO server address |
| `MINIO_ACCESS_KEY` | `vexa-access-key` | Access key |
| `MINIO_SECRET_KEY` | `vexa-secret-key` | Secret key |
| `MINIO_BUCKET` | `vexa-recordings` | Bucket name |
| `MINIO_SECURE` | `false` | Use HTTPS |

**S3:**

| Env var | Default | Purpose |
|---------|---------|---------|
| `STORAGE_BACKEND` | — | Set to `s3` |
| `S3_ENDPOINT` | `""` (AWS default) | Custom S3-compatible endpoint |
| `AWS_ACCESS_KEY_ID` | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | — | AWS credentials |
| `S3_BUCKET` | falls back to `MINIO_BUCKET` | Bucket name |
| `S3_SECURE` | `true` | Use HTTPS |
| `AWS_REGION` | `us-east-1` | AWS region |

**Local filesystem:**

| Env var | Default | Purpose |
|---------|---------|---------|
| `STORAGE_BACKEND` | — | Set to `local` |
| `LOCAL_STORAGE_DIR` | `/tmp/vexa-recordings` | Base directory |
| `LOCAL_STORAGE_FSYNC` | `true` | fsync after writes |

## How

### Docker Compose

MinIO runs as a compose service:

```yaml
minio:
  image: minio/minio
  command: server /data --console-address ":9001"
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # Console UI
  environment:
    MINIO_ROOT_USER: vexa-access-key
    MINIO_ROOT_PASSWORD: vexa-secret-key
```

Bucket `vexa-recordings` is created automatically by an init container on startup.

### Usage in code

```python
from shared_models.storage import create_storage_client

client = create_storage_client()  # reads STORAGE_BACKEND env var
client.upload_file("recordings/123/audio.wav", audio_bytes, "audio/wav")
url = client.get_presigned_url("recordings/123/audio.wav", expires=3600)
```

Factory function: `create_storage_client(backend=None)` — reads `STORAGE_BACKEND` env var if backend not specified.

### Verification

```bash
# Check MinIO health
curl -f http://localhost:9000/minio/health/live

# Check bucket exists
docker compose exec minio mc alias set local http://localhost:9000 vexa-access-key vexa-secret-key
docker compose exec minio mc ls local/vexa-recordings

# Or via boto3/aws CLI
aws --endpoint-url http://localhost:9000 s3 ls s3://vexa-recordings/
```

### Known limitations

| Area | Status | Detail |
|------|--------|--------|
| **Low adoption** | Observation | 2 recordings and 2 media files in production. Feature works but is barely used. |
| **No upload retry** | Risk | `upload_file` is a single PUT. No retry on network failure. Large files could fail silently. |
| **No lifecycle policies** | Gap | No automatic cleanup of old recordings. Storage will grow unbounded. |
| **No size limits** | Gap | No max file size enforcement. A large upload could exhaust disk/memory. |
| **Local backend has no presigned URLs** | Limitation | Returns `file://` URIs — only works for same-machine access. Not usable in production. |
| **Single bucket** | Simplification | All users share one bucket. No per-tenant isolation. Path-based separation only. |
| **No path traversal in S3** | Security | Local backend validates paths to prevent `../` traversal. MinIO/S3 backends rely on S3 key semantics (no filesystem traversal risk). |

### References

- Storage client: [`packages/shared-models/shared_models/storage.py`](../packages/shared-models/shared_models/storage.py)
- Models (Recording, MediaFile): [`packages/shared-models/shared_models/models.py`](../packages/shared-models/shared_models/models.py)
- PostgreSQL (table details): [postgresql.md](postgresql.md)
- Redis (ephemeral layer): [redis.md](redis.md)

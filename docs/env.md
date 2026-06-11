# Environment variables

Loaded by `app/config.py`. `.env` is not committed (in production, use Railway environment variables).

| Variable | Default | Description |
|---|---|---|
| `PORT` | 8000 | Listen port (injected by Railway) |
| `DATA_DIR` | `./data` | Location for SQLite, images, and cache. In production this is `/data` (volume) |
| `MODEL_PATH` | `models/dinov2_vits14.onnx` | Path to the embedding ONNX. Startup fails explicitly if missing |
| `MODEL_NAME` | `dinov2_vits14` | Embedding model name recorded in the DB (used to decide re-embedding) |
| `EMBED_VERSION` | 1 | Embedding version, including preprocessing. Bumping it triggers re-embedding |
| `KNN_K` | 9 | Default k for k-NN (overridable per project) |
| `UNCERTAIN_THRESHOLD` | 0.55 | Confidence below this marks the result `uncertain=true` |
| `MAX_IMAGE_BYTES` | 10485760 | Maximum accepted image size (10MB). Over the limit returns 413 |
| `ALLOW_IMAGE_URL` | `false` | Whether to accept `image_url`. Off by default due to SSRF concerns ([security.md](security.md)) |
| `ADMIN_USER` | (required) | admin Basic auth user |
| `ADMIN_PASS` | (required) | admin Basic auth password |
| `AUTH_DISABLED` | `false` | **Local development only.** When true, disables API key / Basic auth. Never set true in production |
| `DEFAULT_PROJECT` | (optional) | Default project name for development. Not used in production |
| `LOG_LEVEL` | `info` | Log level |

## Auth / secrets

- Never commit `ADMIN_PASS` or per-project API keys.
- API keys are stored as hashes in the DB. Do not put them in env (the plaintext is returned exactly once in the issuance response).

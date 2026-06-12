# System Architecture

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web | FastAPI + uvicorn (single ASGI process. Inference runs on CPU, so a single worker is enough) |
| Embedding | DINOv2 ViT-S/14 exported to ONNX, inferred via onnxruntime (CPUExecutionProvider) |
| Numerics | numpy (k-NN is brute-force cosine similarity — fast enough for thousands of samples) |
| Image | Pillow (decode, resize, preprocess). SHA-256 for duplicate detection |
| DB | SQLite (stdlib `sqlite3`, WAL mode). The file lives on the `/data` volume |
| Admin UI | Server-side rendering with Jinja2 templates is sufficient. No SPA |
| Deploy | Railway (Dockerfile build, `/data` mounted as a volume) |

Dependencies are kept minimal (no heavy ML framework as a whole). `torch` is used **only by the ONNX export script** and is not installed in the production runtime (just onnxruntime).

## Directory Layout (target)

```
app/
  main.py            FastAPI entry point (routing, model/DB load on startup)
  config.py          Environment variable loading (matches env.md)
  db.py              SQLite connection, schema creation, CRUD (all SQL lives here)
  models.py          Pydantic schemas (request/response)
  embed.py           DINOv2 ONNX inference (preprocess → embedding vector)
  classifier.py      k-NN core (neighbor search, majority vote, confidence, flip-augmented registration)
  store.py           In-memory embedding index per project, plus warm-up
  auth.py            API key verification, admin Basic auth
  routes/
    predict.py       POST /v1/{project}/predict
    label.py         POST /v1/{project}/label
    projects.py      POST /v1/projects (create), GET /v1/projects (list, admin)
    admin.py         GET /admin (UI), correction endpoints
    health.py        GET /healthz
  templates/         Jinja2 templates for the admin UI
scripts/
  export_dinov2_onnx.py   DINOv2 → ONNX export (run once at build time or beforehand)
  import_labels.py        Bulk import of existing labels (CSV / directory)
models/
  dinov2_vits14.onnx      Bundled embedding model (Git LFS or fetched at build time)
data/                     (gitignored) SQLite, images, cache for local runs
  facing.db
  images/                 Long-side 256px JPEG thumbnails stored by sha256 (admin display only)
docs/                     Design documentation (this directory)
Dockerfile
railway.json
pyproject.toml            Dependency definitions (uv or pip)
```

## Request Data Flow

### predict (classification)

```
POST /v1/{project}/predict  (image)
  → auth: verify API key (bound to the project)
  → decode and preprocess image (224x224, ImageNet normalization)
  → DINOv2 ONNX → 384-dim vector → L2 normalize
  → classifier: cosine k-nearest neighbors over the project's labeled vector set
  → majority vote → left/right; confidence from vote ratio and neighbor distances
  → {facing, confidence, uncertain, neighbors?}
```

Images are not stored on predict (they are not labels). An audit log entry may optionally be kept.

### label (adding training data)

```
POST /v1/{project}/label  (image + facing)
  → auth
  → decode image → sha256 (if a duplicate, update facing)
  → save a long-side 256px JPEG thumbnail to data/images/<sha>.jpg (admin display only)
  → DINOv2 → vector → save to samples/embeddings (source='human', etc.)
  → flip augmentation: embed the horizontally flipped image and add it with the inverted facing (is_flip_aug=1)
  → also add to the in-memory project index (effective immediately, no retraining)
```

### Startup

```
boot → load DINOv2 ONNX → load all per-project embeddings from the DB into memory
     → predict/label thereafter use the in-memory index (the DB is for persistence)
```

## Process Model

- Start with a single process, single worker (CPU inference, single-file SQLite).
- The embedding index is **held in process memory**, with the DB as the source of truth.
  On startup it is restored from the DB; on label it is written to both the DB and memory.
- If brute-force k-NN becomes slow at larger scale, leave room to swap in approximate nearest neighbor (hnswlib, etc.).
  Brute-force numpy is sufficient for the first version — practical up to tens of thousands of samples.

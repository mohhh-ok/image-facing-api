# HTTP API Specification

The base URL is environment-dependent (local `http://localhost:8000`, production is the Railway URL).
The version prefix is `/v1`. For authentication see [security.md](security.md) and [multi-tenant.md](multi-tenant.md).

Common to all endpoints:
- Images can be sent in **three ways** (pick one): a `multipart/form-data` file, JSON `image_base64`, or JSON `image_url`.
- **The server auto-detects the image format.** Pillow identifies the format (JPEG / PNG / WebP / GIF, etc.) from the magic bytes and decodes it, so the client
  **does not need to convert to PNG or anything else before sending**. Just send the raw bytes you generated or fetched
  (unsupported formats and corrupt images are rejected with `bad_image` — see [security.md](security.md)).
- Auth: service-to-service calls use the `X-API-Key` header (key bound to a project). The admin UI uses Basic auth.
- Errors are returned as `{"error": {"code": "...", "message": "..."}}` with appropriate HTTP status codes.

---

## POST /v1/{project}/predict

Predict the facing of an image. **Not added to the training set** (this is not a label).

Request (JSON example):
```json
{ "image_base64": "iVBORw0KGgo..." }
```
Or a multipart `file` field, or `{"image_url": "https://..."}`.

Response:
```json
{
  "facing": "left",
  "confidence": 0.86,
  "uncertain": false,
  "neighbors": [
    { "sample_id": 1421, "facing": "left", "similarity": 0.94 },
    { "sample_id": 0987, "facing": "left", "similarity": 0.91 }
  ],
  "model": "dinov2_vits14",
  "k": 9
}
```

- `facing`: `"left" | "right"`.
- `confidence`: 0..1. Computed from neighbor vote share and distance (see [model.md](model.md)).
- `uncertain`: true when below threshold (split vote / distant neighbors / too few labels yet).
  Clients can use this to route to a **fallback (e.g. LLM judgement) or to admin**.
- `neighbors`: for debugging and admin display (can be omitted with `include_neighbors=false`).

`facing` is always returned even when `uncertain=true` (clients need a binary answer).

---

## POST /v1/{project}/label

Register a ground-truth label. It is added to the training set and **takes effect immediately** for subsequent predicts.

Request (JSON example):
```json
{
  "image_base64": "iVBORw0KGgo...",
  "facing": "right",
  "external_id": "yokai-51",     // optional. Client-side identifier (stored in DB only; not used for matching)
  "source": "human"               // optional. "human" | "import" | "model", etc. Default "human"
}
```

Response:
```json
{ "sample_id": 1422, "facing": "right", "deduped": false, "flip_added": true, "project_size": 318 }
```

- If the same image (sha256 match) already exists, **its facing is updated** (`deduped: true`).
- `flip_added`: whether a horizontally flipped variant was added with the inverse label (added by default; see [model.md](model.md)).
- `project_size`: current label count, including flip augmentation.
- `source="human"` is the highest-priority label from admin/manual input. `model`-sourced labels may be treated with lower trust.

---

## POST /v1/{project}/predict_and_maybe_label (optional, future)

A convenience flow that auto-labels when the predict confidence is high. Not required in v1.

---

## POST /v1/projects

Create a new project and issue an API key (**admin auth required**).

Request: `{ "name": "my-project", "description": "facing classification" }`

Response:
```json
{ "project": "my-project", "api_key": "fk_live_xxx", "created_at": "..." }
```
The `api_key` plaintext **is only returned in this response** (the DB stores a hash).

## GET /v1/projects

List projects (**admin auth required**). Returns counts, last-updated, etc.

## POST /v1/projects/{name}/rotate_key

**Reissue** the API key for an existing project (**admin auth required** + same-origin).
The old key is invalidated immediately, so any client still using it will get 403 until it switches to the new key.

Response: `{ "project": "...", "api_key": "fk_live_new", "created_at": "..." }` (plaintext only in this response).

```bash
curl -X POST https://<host>/v1/projects/<name>/rotate_key -u "$ADMIN_USER:$ADMIN_PASS"
```

---

## POST /admin/delete

Delete a label (**original only**) and its flip-augmented row (**admin auth required** + same-origin).
The row is removed from the DB and evicted from the in-memory k-NN index at the same time. Embeddings are removed via cascade.
The image file is kept because it can be shared at the sha level.

Invoked from the "Delete" button on each sample card in the admin UI.

Request (form): `project=<name>&sample_id=<original id>` (optionally `show_flip`)
Response: **303** redirect back to `/admin?project=<name>` (use `curl -i` to inspect, `-L` to follow).

```bash
curl -i -X POST https://<host>/admin/delete -u "$ADMIN_USER:$ADMIN_PASS" \
  -d project=<name> -d sample_id=<id>
```

---

## GET /admin

Admin UI (**Basic auth**). Select a project, list samples, and correct facings by hand.
See [admin.md](admin.md) for details. Corrections internally go through the same path as `label`.

## GET /healthz

`{ "status": "ok", "model_loaded": true, "projects": 3 }`. No auth. Used for Railway health checks.

---

## Status codes and error codes

| HTTP | code | meaning |
|---|---|---|
| 400 | `bad_image` | image cannot be decoded / size exceeded / unsupported format |
| 400 | `bad_request` | required field missing / `facing` is not `left` or `right` |
| 401 | `unauthorized` | missing or invalid API key / Basic auth |
| 403 | `forbidden` | key is valid but does not match the project |
| 404 | `no_such_project` | project does not exist |
| 413 | `payload_too_large` | image exceeds the size limit (see [security.md](security.md)) |
| 422 | (FastAPI default validation error) | |
| 500 | `internal` | unexpected. Do not swallow; log it |

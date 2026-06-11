# API Usage Guide

A how-to for **callers** of this service. The authoritative endpoint spec is [api.md](api.md);
this document covers how to actually hit it in practice.

## In one line

Send an image, get back `facing` (`"left"` or `"right"`). Accuracy improves the more labels you add (see [model.md](model.md)).
No LLM calls, no external side effects — a pure image-to-label function.

---

## Base URL and version

- Local: `http://localhost:8000` (`PORT` defaults to 8000; see [env.md](env.md))
- All API endpoints are prefixed with `/v1` (except `admin` and `healthz`).

The examples below assume `BASE=http://localhost:8000` and `PROJECT=my-project`.

---

## Authentication

| Purpose | Method | Header |
|---|---|---|
| predict / label (service-to-service) | API key | `X-API-Key: fk_live_xxx` |
| project create/list, admin UI | Basic auth | `Authorization: Basic ...` (`ADMIN_USER` / `ADMIN_PASS`) |
| healthz | none | — |

- API keys are **per project**. If the key does not match the `{project}` in the URL, you get `403 forbidden`.
- For local development, `AUTH_DISABLED=1` bypasses auth entirely (**never enable this in production**; see [security.md](security.md)).
- The API key plaintext is **returned exactly once**, in the creation response (the DB stores a hash). If you lose it, rotate the key.

---

## How to send the image (three options, pick one)

Common to all endpoints. Parsed by `app/request_input.py`.

1. **JSON `image_base64`** (safe and recommended)
   ```json
   { "image_base64": "iVBORw0KGgo..." }
   ```
   The `data:image/png;base64,...` data-URL prefix is also accepted.
2. **multipart/form-data `file` field** — send other values (`facing`, etc.) as form fields.
3. **JSON `image_url`** — only enabled when `ALLOW_IMAGE_URL=true` (off by default due to SSRF risk).

The size limit is `MAX_IMAGE_BYTES` (default 10MB). Exceeding it returns `413 payload_too_large`.

---

## Per-endpoint usage

### Create a project (admin, one-time)

```bash
curl -u "$ADMIN_USER:$ADMIN_PASS" \
  -X POST "$BASE/v1/projects" \
  -H 'content-type: application/json' \
  -d '{"name":"my-project","description":"facing classification"}'
# => {"project":"my-project","api_key":"fk_live_xxxxxxxx...","created_at":"..."}
```
Save the `api_key` into the client's env (e.g. `FACING_API_KEY`). Listing is `GET /v1/projects` (also admin).

### Predict

A read-only operation that **does not** add to the training set. Call it whenever you want.

```bash
curl -X POST "$BASE/v1/$PROJECT/predict" \
  -H "X-API-Key: $FACING_API_KEY" \
  -H 'content-type: application/json' \
  -d "{\"image_base64\":\"$(base64 -i sample.png)\"}"
```
Response:
```json
{ "facing": "left", "confidence": 0.86, "uncertain": false,
  "neighbors": [ {"sample_id":1421,"facing":"left","similarity":0.94} ],
  "model": "dinov2_vits14", "k": 9 }
```
- `facing` is always returned, even when `uncertain=true` (split vote / distant neighbors / few labels).
  Clients should use `uncertain` to route to a **fallback (e.g. an existing LLM judgement) or to admin**.
- `neighbors` is for debugging. If you don't need it, suppress with `?include_neighbors=false` (or the same field in JSON).
- Predict leaves only the **image hash and the result** in the audit log (the image itself is not stored).

### Register a label

Adds to the training set and **takes effect immediately** for subsequent predicts. `facing` is required.

```bash
curl -X POST "$BASE/v1/$PROJECT/label" \
  -H "X-API-Key: $FACING_API_KEY" \
  -H 'content-type: application/json' \
  -d "{\"image_base64\":\"$(base64 -i sample.png)\",\"facing\":\"right\",\"source\":\"human\"}"
# => {"sample_id":1422,"facing":"right","deduped":false,"flip_added":true,"project_size":318}
```
- `source` defaults to `"human"` (`"human" | "import" | "model"`). `human` is the highest-priority label.
- If the same image (**sha256 match**) already exists, the facing is overwritten and `deduped:true` is returned (see flow below).
- `flip_added`: whether a horizontally flipped variant was auto-added with the inverse label (added by default; this balances left/right automatically).
- `external_id` is optional, but it is **only stored in the DB and is not used for matching** (matching is by image sha256).
- **Only send confirmed labels through `label`**. Pumping automated or experimental predictions in pollutes the label space.

### Health check

```bash
curl "$BASE/healthz"   # => {"status":"ok","model_loaded":true,"projects":3}
```

---

## Flow: predict → user confirms/corrects in UI → correction flows back

Predict is stateless; the server **does not issue** an ID (such as `predict_id`) tying predict to label.
Matching is done by **the image's sha256**, so the wiring looks like this:

```
1. Client keeps the image to be classified in hand
2. POST /predict (image)        → receive facing / uncertain, show in UI
3. User confirms or corrects in the UI
4. POST /label with the corrected facing (same image + facing, source="human")
   → sha256 matches, so the existing label is overwritten (deduped:true). If new, it's added.
   → Immediately reflected in k-NN
```

Key points:
- **Send the same image again when correcting** (predict has no ID in its response, so the image is the matching key).
  The client must keep the image it predicted on, not discard it.
- Corrections from the admin UI (`/admin`) go through the same `label` path. To correct from your client UI,
  just relay that action to `/label` (`source="human"`).
- The usual operating pattern is: "first classify with an LLM or similar, then feed the human-corrected ones into `label` to grow the seed."

---

## Client implementation notes

- **Always set timeouts and a fallback.** This is an external dependency; if it goes down, the caller's batch should not stop.
- Hold the URL and key in env (`FACING_API_URL` / `FACING_API_KEY`); if unset, fall back (local offline autonomy).
- Do not transform the image bytes. **Carry the facing as data and flip in CSS at render time.**

### Python (requests)

```python
import base64, requests

def predict(img_bytes: bytes) -> dict:
    b64 = base64.b64encode(img_bytes).decode()
    r = requests.post(
        f"{BASE}/v1/{PROJECT}/predict",
        headers={"X-API-Key": API_KEY},
        json={"image_base64": b64},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()   # {"facing": ..., "uncertain": ..., ...}
```

### TypeScript (fetch)

```ts
async function predict(imgBase64: string): Promise<{ facing: "left" | "right"; uncertain: boolean }> {
  const res = await fetch(`${BASE}/v1/${PROJECT}/predict`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "content-type": "application/json" },
    body: JSON.stringify({ image_base64: imgBase64 }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`facing-api ${res.status}`);
  return res.json();
}
```

---

## Errors

The format is `{"error": {"code": "...", "message": "..."}}`. Common ones (full list in [api.md](api.md)):

| HTTP | code | what to do |
|---|---|---|
| 400 | `bad_image` / `bad_request` | image cannot be decoded / required field missing (e.g. `facing`) / `facing` is not `left` or `right` |
| 401 | `unauthorized` | no `X-API-Key` / no Basic auth |
| 403 | `forbidden` | key is valid but does not match the project |
| 404 | `no_such_project` | project has not been created |
| 413 | `payload_too_large` | image exceeds `MAX_IMAGE_BYTES` |
| 500 | `internal` | unexpected. Handle with retry + fallback |

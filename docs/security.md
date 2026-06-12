# Security

This service only **takes an image and returns left/right**. It does not call an LLM and has no external side effects.
The attack surface is limited to "the images and metadata it receives" and "authentication".

## Authentication

- **Service-to-service (predict / label)**: `X-API-Key` header. Keys are scoped to a project and verified by hash ([multi-tenant.md](multi-tenant.md)).
- **admin / project creation**: Basic auth (`ADMIN_USER` / `ADMIN_PASS`).
- Never store API keys in plaintext in the DB (return plaintext only at issuance time; afterwards only the hash is kept).
- Auth is wired in **from day one**. "Add it later" leaks at the moment you go public.
  For local development only, `AUTH_DISABLED=1` may bypass it (never enable in production).
- **CSRF**: admin uses Basic auth, so browsers auto-send credentials. State-changing POSTs
  (`/admin/correct`, `POST /v1/projects`) are protected by **same-origin checks on Origin/Referer**
  (`app/auth.py:verify_same_origin`). Service-to-service calls without Origin/Referer (curl, etc.) pass through.

## Handling untrusted input

What arrives from outside is "images" and "a small amount of metadata (external_id, etc.)".

- **Images**:
  - Size cap (e.g. 10MB, `MAX_IMAGE_BYTES`). Over the limit returns 413.
  - Decoded via Pillow. Decode failures, unsupported formats, and excessive pixel counts (decompression bombs) are rejected
    (`Image.MAX_IMAGE_PIXELS` is set).
  - Code-execution risk via images depends on known Pillow CVEs; keep dependencies up to date.
  - When accepting `image_url`, **beware of SSRF**: block internal IPs / localhost / metadata endpoints (169.254.169.254),
    allow only the https scheme, limit redirect following, and apply timeouts.
    If in doubt, disable `image_url` in the initial release and accept only base64/multipart.
  - Implementation note: fetches are **streamed and aborted when cumulative bytes exceed `MAX_IMAGE_BYTES`**; if Content-Length
    is present, reject up front (DoS mitigation). However, host validation **cannot fully prevent DNS rebinding** due to
    re-resolution between "name resolution" and "connect". If you enable `ALLOW_IMAGE_URL=true` in production, assume an
    egress proxy / allow-list is also in place (default is false).
- **Metadata (external_id, description, project name)**:
  - Length caps and character-class restrictions (project name: alphanumerics and hyphens only).
  - SQL always uses parameter binding (no string concatenation).
  - When rendering in the admin UI, **HTML-escape** (do not disable the template's auto-escape).
- This service has **no path that interprets received text as instructions** (no LLM), so it suffers no direct
  prompt injection harm. How the client consumes this service's output, however, is the client's responsibility.

## Resource / abuse mitigations

- Request body cap, timeouts, and (if needed) per-project rate limiting.
- predict does not persist images (if you want an audit log, store only hashes). Only label persists an image, and only as a long-side 256px JPEG thumbnail for admin display — not the original bytes.
- Do not log plaintext API keys or raw image bodies.

## Secrets

- `ADMIN_PASS`, API keys, and (client-side) LLM tokens are passed via env and never committed to the repo.
- `.env` is not committed (`.gitignore`). In production, set via Railway environment variables.

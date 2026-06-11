# Multi-tenancy (project isolation)

## Why separate

This is a general-purpose service, so each client has a different image domain (character illustration, photo, product image, ...). **What counts as `left` varies by domain**, and mixing labels contaminates k-NN neighbors with other domains. Therefore we **completely isolate the label space, k-NN index, and API key per project**.

## What a project is

- An identifier that appears in URLs (`/v1/{project}/...`). Alphanumeric and hyphen only (e.g. `my-project`).
- 1 project = 1 label set = 1 k-NN index = 1 API key (split into a separate table if you need multiple keys).
- predict / label always run **within project scope**. There is no global cross-project prediction.

## API key

- Issued at project creation (`POST /v1/projects`, admin auth).
- Suggested format: `fk_live_<32 random chars>`. **The plaintext is returned only in the creation response.**
- The DB stores only `api_key_hash` (sha256 or argon2; sha256 is acceptable for lookupability, but for safety on leak see [security.md](security.md)).
- Validation: hash the request's `X-API-Key`, confirm it matches `projects.api_key_hash`, and confirm the URL project matches. Otherwise return 401/403.

## Rotation and revocation

- Reissue overwrites with a new hash (the old key is immediately invalidated). For the first version, "recreate" is enough.
- If multiple keys or expiration timestamps are needed later, split into an `api_keys(project, hash, label, revoked_at)` table.

## admin and tenants

- admin (Basic auth) is for operators and **spans all projects** for browsing and editing.
- The admin UI picks a project and fixes labels ([admin.md](admin.md)).
- Project API keys are for "service-to-service automated calls"; admin is for "humans operating the system." Keep the roles distinct.

## Default project

- To ease early development, you may provide a single `DEFAULT_PROJECT` via env (optional).
- In production, however, give each client its own project. Do not collapse everything into `default`.

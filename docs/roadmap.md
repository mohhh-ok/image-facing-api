# Implementation roadmap

Build bottom-up, following the design docs. Each phase is sized so the result is "running and verifiable".

## Phase 0: scaffolding

- [ ] `pyproject.toml` (fastapi, uvicorn, onnxruntime, pillow, numpy, jinja2. torch only for dev/scripts)
- [ ] `.gitignore` (`data/`, `.env`, `__pycache__`; large models via LFS or managed separately)
- [ ] `app/config.py` (read the variables in [env.md](env.md))
- [ ] `app/db.py` (create the schema in [database.md](database.md) with `CREATE TABLE IF NOT EXISTS`)
- [ ] `GET /healthz`

## Phase 1: embeddings

- [ ] `scripts/export_dinov2_onnx.py` (DINOv2 ViT-S/14 -> `models/dinov2_vits14.onnx`)
- [ ] `app/embed.py` (preprocessing fixed exactly as in [model.md](model.md) -> 384-dim L2-normalized vector)
- [ ] Sanity check: the same image and its horizontal flip must produce **different vectors** (proof that facing information is preserved)

## Phase 2: training set and k-NN

- [ ] `app/store.py` (at startup, load embeddings into a per-project numpy matrix; append on label)
- [ ] `app/classifier.py` (cosine neighbors, majority vote, confidence; formulas in [model.md](model.md))
- [ ] flip augmentation (on label, also insert the flipped image with the opposite label, linked by `origin_sample_id`)

## Phase 3: API

- [ ] `app/auth.py` (API key hash verification, admin Basic, `AUTH_DISABLED` local-only)
- [ ] `POST /v1/projects` (create / issue key) / `GET /v1/projects`
- [ ] `POST /v1/{project}/label` (dedupe, image persistence, embedding, flip augmentation, instant reflection)
- [ ] `POST /v1/{project}/predict` (decision, confidence, uncertain)
- [ ] Error codes ([api.md](api.md)) and image size cap ([security.md](security.md))

## Phase 4: admin UI

- [ ] `GET /admin` (project picker, sample list, preview flip, `[<-left][right->]` toggle)
- [ ] Filters for uncertain / unlabeled / recently added; hide flip-augmentation rows
- [ ] When the original sample is corrected, its flip-augmentation row follows automatically

## Phase 5: deploy

- [ ] `Dockerfile` (model bundled, no torch)
- [ ] `railway.json` (`/healthz`, `/data` volume)
- [ ] Create the production project and issue its API key

## Phase 6: client integration

- [ ] `scripts/import_labels.py` (example of bulk-seeding labels from existing labels/images)

## Verification angles

- The same image vs. its flip yields opposite facing (symmetry).
- Adding labels reduces the uncertain rate (learning is effective).
- admin corrections are reflected in the very next predict (no restart needed).
- API key / project scope isolation (a project cannot touch another project's labels).
- Malformed images, oversized images, and unauthenticated requests are correctly rejected.

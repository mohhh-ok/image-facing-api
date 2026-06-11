# Documentation Index

The source of truth for design and spec lives under this `docs/` directory. For a high-level overview, see the root [README.md](../README.md).

**This repository is docs-first**: implementation follows the docs. Read top to bottom (overview → architecture → api → model …).

| Document | Contents |
|---|---|
| [overview.md](overview.md) | Purpose, scope, non-goals, terminology (definition of left/right) |
| [architecture.md](architecture.md) | Tech stack, directory layout, request data flow |
| [api.md](api.md) | HTTP API spec (predict / label / projects / admin / healthz, request/response examples) |
| [usage.md](usage.md) | API usage guide (how-to for callers, curl/Python/TS examples, predict → review → correct flow) |
| [model.md](model.md) | Classification model (DINOv2 embeddings, k-NN, flip augmentation, confidence, preprocessing, model trade-offs) |
| [database.md](database.md) | SQLite schema, image/embedding storage, migration policy |
| [multi-tenant.md](multi-tenant.md) | Tenant isolation via the project key, API key issuance and verification |
| [admin.md](admin.md) | Admin UI, Basic auth, active-learning operational flow |
| [security.md](security.md) | Authentication, handling untrusted input (images/metadata), resource limits |
| [env.md](env.md) | Environment variables |
| [roadmap.md](roadmap.md) | Implementation steps (phased), validation plan |

## Design Assumptions (already decided)

- The goal is a **general-purpose left/right classifier**, reusable from multiple services.
- Stack is **Python + FastAPI** (the embedding model inference is central, so we stay close to the ML ecosystem).
- Classification uses **DINOv2 embeddings + k-NN** (no end-to-end CNN training — small data, CPU, instant updates).
- Tenants are **separated by the project key** (labels from different domains are never mixed).
- This is an **independent repository** (`~/Dev/image-facing-api`).

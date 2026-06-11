# Purpose, Scope, Terminology

## Purpose

An HTTP service that decides whether the main subject of an image (character, person, animal, object) is facing `left` or `right` **from the viewer's perspective**. Classification is trainable — accuracy improves as more ground-truth labels are added.

The service is designed as a **domain-agnostic, general-purpose classifier** (domains are separated via the project key — see [multi-tenant.md](multi-tenant.md)).

## Definition of `left` / `right` (important — consistent across the project)

The convention is **viewer-relative** (from the perspective of the person looking at the image):

- `left`  = the subject is facing **toward the left side of the frame** (face/body oriented left).
- `right` = the subject is facing **toward the right side of the frame**.

The service does not hard-code any orientation rule — **it learns from human-provided labels**. In practice, "what counts as `left`" is determined by the label distribution within each project.

## Scope

- **Binary `left` / `right` classification** of a single image, with a confidence score.
- Registering ground-truth labels, with immediate accuracy improvement (k-NN).
- Per-project tenant isolation.
- Manual correction via an admin UI.

## Non-goals (explicitly out of scope)

- `front` / multi-class / continuous angle (yaw degree) regression. **Binary only** (ambiguity is expressed through confidence).
  We may add `front` later, but the first version is binary.
- Face detection, pose detection, or object detection per se (embeddings are computed over the whole image).
- Image generation, modification, or storing flipped images (**facing is returned as data only**; the service does not return a flipped image. Flipping for display is the client's responsibility).
- LLM calls (this service does not embed an LLM).

## Why this shape

- **Why not fine-tune a CNN end-to-end**: it does not satisfy small-data, CPU-only, instant-update constraints. Details in [model.md](model.md).
- **Why a standalone service**: left/right classification is reused across multiple services, so generalization is the goal.
- **Why not return a flipped image**: binary flipping is lossy and hard to undo. If facing is held as data, fixing a label retroactively corrects every client's display without regenerating any image.

# Prediction model

## Overview

```
image ──[preprocess]──▶ DINOv2 ViT-S/14 (ONNX) ──▶ 384-dim vector ──[L2 normalize]──┐
                                                                                    ▼
                              project's labeled vector set ──[cosine k-NN]──▶ majority vote ──▶ {facing, confidence}
```

Training is just "append a labeled vector to the set." **No gradient descent, no retraining step.** This is what makes "keep the server up and let it predict and learn continuously" actually work.

## Why this approach (decision record)

| Approach | Training cost | Instant updates | Small data | Decision |
|---|---|---|---|---|
| Full CNN fine-tuning (ResNet, etc.) | Heavy (tens of minutes on CPU, GPU assumed) | No (requires retraining) | No | Rejected |
| Embeddings + logistic regression | Light (seconds) | Partial (requires refit) | Good | Runner-up |
| **Embeddings + k-NN** | **Near zero** | **Yes (just append)** | Good | **Adopted** |

k-NN is the only one that satisfies small data, CPU, and instant updates simultaneously. If the dataset grows to tens of thousands of samples and k-NN becomes too coarse, there is room to migrate to logistic regression or approximate nearest neighbor.

## Embedding model: DINOv2 ViT-S/14

- Self-supervised general-purpose visual features. **Strong linear-probe / k-NN-probe performance**, i.e. it works well with few labels. It tends to preserve facing differences in its features across domains like illustration, character art, and photos.
- ViT-S/14 is small (about 21M params) and **CPU inference fits within a few hundred ms per image**.
- Output is 384 dimensions (the CLS token). We L2-normalize it and use cosine similarity.
- Converted to ONNX and run on onnxruntime (CPU). The production runtime does not include `torch` (conversion is done once via `scripts/export_dinov2_onnx.py` at build time or ahead of time).

Alternative candidates (design to be swappable if needed):
- **CLIP ViT-B/32**: a text-aligned model but its visual features are general-purpose. Slightly larger.
- DINOv2 ViT-B/14: higher accuracy, lower speed. An option once data grows.

`embed.py` confines the interface to "image → 384-dim np.ndarray" so swapping models does not ripple into the DB or classifier. The `model_name` and `dim` of the embedding are recorded in the DB so we can detect when **re-embedding is required** after a model change.

## Preprocessing (must be strictly fixed)

If preprocessing differs between predict and label, accuracy collapses. **Fix it in one place (embed.py):**

1. Convert to RGB (composite transparent PNGs onto white or a configured color. Character art assumes transparency, so the composite color can be project-configurable).
2. Resize so the shorter side is 224 preserving aspect ratio, then center-crop 224x224 (DINOv2 standard; for facing prediction we assume the main subject is in the center crop).
3. Scale to `[0,1]`, then normalize with ImageNet mean `[0.485,0.456,0.406]` / std `[0.229,0.224,0.225]`.
4. NCHW float32.

## k-NN classification

- Distance: **cosine similarity** (vectors are L2-normalized, so a dot product suffices).
- `k`: default 9 (overridable per project). If fewer than k labels exist, vote over all of them.
- Majority vote: the more frequent facing among the top k neighbors. On ties, decide by **similarity-weighted** vote.
- **Because of flip augmentation, the left/right counts are structurally balanced** (see below).

## Computing confidence

Combine "vote skew" with "closeness" of neighbors. Reference implementation:

```
votes_left, votes_right = weighted votes (weight = similarity or exp distance)
margin = |votes_left - votes_right| / (votes_left + votes_right)   # 0..1: vote skew
top_sim = cosine similarity of the nearest neighbor                # 0..1: do similar examples exist at all?
confidence = margin * clamp01((top_sim - sim_floor) / (1 - sim_floor))
```

- `uncertain = confidence < UNCERTAIN_THRESHOLD` (default around 0.55, tunable via env).
- For projects with few labels, `top_sim` stays low and predictions naturally fall into uncertain → the client falls back (to an LLM) or routes to admin. This is the correct behavior during the bootstrap phase.

## Flip augmentation (label-time only)

- When a label is registered, in addition to the original image, **embed the horizontally flipped image and register it with the opposite facing** (`is_flip_aug=1`).
  - A `left` image, flipped, is guaranteed correct data for `right`. The label is 100% accurate.
  - Effect: doubles the data, keeps left/right counts balanced, and yields a left/right-symmetric decision boundary.
- **Do not flip the query image at predict time** (we want to judge the input as-is). Flip is training-side only.
- Note: the original and flipped vectors are strongly correlated, so consider a deduplication step to avoid double-counting when both end up among the k-NN neighbors (e.g. collapse to one vote per `origin_sample_id`). The first version can be naive, but [database.md](database.md) keeps the origin so we can add this later.

## Re-embedding on model updates

- Changing the embedding model or the preprocessing makes existing vectors incompatible.
- Mitigation: store `model_name` and `embed_version` in the DB, warn at startup on mismatch. Re-embedding is **served by the existing vectors in the `embeddings` table** as long as the model is unchanged — the long-side 256px JPEG thumbnails in `data/images/` are kept for admin display only and are sufficient to re-embed into DINOv2-class (224px input) models, but not high-resolution successors. Swapping to a model that requires the original resolution is out of scope.

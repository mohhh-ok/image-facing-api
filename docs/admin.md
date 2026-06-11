# admin UI and operations (active learning)

## Purpose

The UI side of the loop where **accuracy goes up the more an operator corrects labels by hand**. k-NN reflects corrected labels immediately, so one click in admin directly affects the next prediction.

## Authentication

- **Basic auth** (`ADMIN_USER` / `ADMIN_PASS`; see [env.md](env.md)).
- Run locally first; enable authentication without fail before exposing it publicly ([security.md](security.md)).
- admin can operate across all projects.

## Screens (minimal set)

`GET /admin` (server-side rendering with Jinja2 is enough; no SPA required).

1. **Project selector**.
2. **Sample list**: a thumbnail of each sample plus its current facing and (if available) confidence.
   - Showing `left` samples flipped to face left, and `right` samples flipped to face right, as a **preview-flipped** view, makes errors easier to spot visually (display flip = `transform: scaleX(-1)`; aligning the orientation makes outliers stand out).
3. **One-click correction**: a `[← left] [right →]` toggle per sample. Pressing it updates facing through the same code path as label (`source='human'`, immediately reflected in the index).
4. **Filters**: "unlabeled", "was uncertain", "recently added", "hide flip augmentation".

## Operating efficiently (active learning)

There is no need to look at everything. The efficient approach is to **only correct what the model is uncertain about**.

1. The client sends predict results with `uncertain=true` to admin as "needs review" (or marks them via external_id).
2. admin prioritizes correcting that uncertain set.
3. Corrections tighten the neighbor set, raising confidence on similar future images → fewer uncertain results.
4. Iterating this drives the amount of human touch down over time.

## What "beating Opus" means

- If you bootstrap labels with an LLM (e.g. a vision judgment from Claude/GPT), the model inherits the LLM's mistakes too (the limit of distillation: you can't beat the teacher).
- **Hand-correction in admin makes a human the teacher**, which lets you overwrite the LLM's mistakes. This is the path that pushes accuracy above the LLM.
- So the operational core is: "LLM as initial labels → admin corrects only the misses." Corrections stay around as ground truth.

## Handling flip augmentation (UI notes)

- When facing on an original sample is corrected in admin, the corresponding flip-augmentation row (linked by `origin_sample_id`) should **automatically follow with the inverted facing** (don't make a human do it twice).
- Flip-augmentation rows are hidden from the list by default (`is_flip_aug=1` filter).

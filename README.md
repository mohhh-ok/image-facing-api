# ai-facing-api

A general-purpose microservice that decides whether the subject in an image
is facing **left** or **right**.

Designed to be reused from multiple services, so it stands alone as an HTTP API.

## What it does

- Send an image, get back `left` / `right` with a confidence score
  (`POST /v1/{project}/predict`).
- Send a ground-truth label and it joins the training set, making subsequent
  predictions smarter (`POST /v1/{project}/label`).
- The admin UI lets you correct labels by hand, and **accuracy goes up the more
  you correct** (human-in-the-loop).

## Design in three lines

- **Embeddings + k-NN.** DINOv2 turns each image into a feature vector;
  prediction is a majority vote over the nearest labeled vectors.
  No end-to-end CNN training, so it runs on **small data, CPU, with instant updates**.
- **Adding a label = instant learning.** k-NN just appends one vector to the
  neighbor set — no retraining step. The server keeps predicting and learning
  while it stays up.
- **Per-project label spaces** (multi-tenant). Illustration projects and
  photo projects never mix labels.

## Documentation

**The source of truth for design and spec lives under [`docs/`](docs/README.md).**
Start with [`docs/README.md`](docs/README.md). This repository is
**docs-first**: implementation follows the docs, not the other way around.

## Stack

Python 3.12 / FastAPI / uvicorn / onnxruntime (DINOv2 ONNX, CPU) / SQLite / Railway.
See [docs/architecture.md](docs/architecture.md) for details.

## License

The code in this repository is licensed under the [MIT License](LICENSE).

The embedding model is Meta's [DINOv2](https://github.com/facebookresearch/dinov2)
(ViT-S/14), exported to ONNX. **DINOv2 itself is licensed under Apache 2.0** —
see the upstream repository for the authoritative terms. Users of this service
must also comply with the upstream model license.

# Going-public checklist

Procedure to follow when flipping the repo from private to public. Order matters.

## 1. Pre-checks (done)

- [x] `gitleaks detect` shows no leaks
- [x] `.env` is in `.gitignore` and absent from git history
- [x] onnx is uploaded to this repo's `v1` Release (sha256: `b43bd497e2d9f79722371c3177fb2f92917da84df1db9aece9cdce03abfeea1b`)

## 2. Add the license

- [x] `LICENSE` (MIT) added at the repo root
- [x] README notes the upstream DINOv2 (Apache 2.0) license

## 3. Flip to public

```sh
gh repo edit mohhh-ok/image-facing-api --visibility public --accept-visibility-change-consequences
```

## 4. Update the URL in the Dockerfile

Change `mohhh-ok/ai-facing-api-models` to `mohhh-ok/image-facing-api`. The sha256 is unchanged so it stays as-is.

```diff
- curl -fsSL https://github.com/mohhh-ok/ai-facing-api-models/releases/download/v1/dinov2_vits14.onnx \
+ curl -fsSL https://github.com/mohhh-ok/image-facing-api/releases/download/v1/dinov2_vits14.onnx \
```

Also update the matching references in CLAUDE.md and `.gitignore` comments.

## 5. Verify the build

Redeploy on Railway and confirm in the build log that the onnx fetch and the sha256 verification succeed.

## 6. Archive the old repo

Once the build is stable:

```sh
gh repo edit mohhh-ok/ai-facing-api-models --archived
```

Add "Moved to https://github.com/mohhh-ok/image-facing-api" to the README before archiving.

# Public 化チェックリスト

private → public に切り替えるときに実施する手順。順序厳守。

## 1. 事前確認 (済)

- [x] `gitleaks detect` で漏洩なし
- [x] `.env` が `.gitignore` 済み・git 履歴に無い
- [x] onnx を本 repo の Release `v1` にアップロード済 (sha256: `b43bd497e2d9f79722371c3177fb2f92917da84df1db9aece9cdce03abfeea1b`)

## 2. ライセンス追加

- [x] `LICENSE` (MIT) をリポジトリ直下に追加済
- [x] README に DINOv2 (Apache 2.0) のライセンス継承についての注記を追加済

## 3. Public 化

```sh
gh repo edit mohhh-ok/image-facing-api --visibility public --accept-visibility-change-consequences
```

## 4. Dockerfile の URL 差し替え

`mohhh-ok/ai-facing-api-models` → `mohhh-ok/image-facing-api` に変更。sha256 は同一なのでそのまま。

```diff
- curl -fsSL https://github.com/mohhh-ok/ai-facing-api-models/releases/download/v1/dinov2_vits14.onnx \
+ curl -fsSL https://github.com/mohhh-ok/image-facing-api/releases/download/v1/dinov2_vits14.onnx \
```

CLAUDE.md / `.gitignore` 内のコメントの参照先も合わせて更新。

## 5. ビルド確認

Railway を再デプロイし、build log で onnx の取得と sha256 検証が通ることを確認。

## 6. 旧 repo の archive

ビルドが安定したら:

```sh
gh repo edit mohhh-ok/ai-facing-api-models --archived
```

README に "Moved to https://github.com/mohhh-ok/image-facing-api" を追記してから archive。

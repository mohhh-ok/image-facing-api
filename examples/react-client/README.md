# image-facing-api / React サンプルクライアント

`image-facing-api` の使い方サンプル。Vite + React + TypeScript。
画像をドロップ → `POST /v1/{project}/predict` で左右判定 → 間違っていれば
`POST /v1/{project}/label` で正解を登録する human-in-the-loop の流れを最小構成で示す。

## セットアップ

パッケージマネージャは **pnpm** を使います (npm より素のデフォルトでの
サプライチェーン耐性が高いため: lifecycle script デフォルト無効・
`minimumReleaseAge` 24h cooldown・exotic subdep ブロック)。

```bash
cd examples/react-client
cp .env.example .env       # VITE_API_BASE / VITE_PROJECT / VITE_API_KEY を埋める
pnpm install
pnpm dev                   # http://localhost:5173
```

API キーは admin で project を作成したときに 1 度だけ平文で返るものを使う
(`docs/api.md` の `POST /v1/projects`).

## できること

- 接続設定 (base URL / project / API キー) を UI で編集 → localStorage に保存
- 画像のドラッグ&ドロップ or 選択
- `predict` で `facing` / `confidence` / `uncertain` / `neighbors` を表示
- `left` / `right` ボタンで `label` として登録 (flip 拡張はサーバ側で自動)

## 注意

- API キーをブラウザに置く構成です。**信頼できる環境でのデモ用途**として使ってください。
  本番では自前のバックエンドからプロキシするのが安全です。
- CORS が必要な場合は API 側で許可設定が必要です。

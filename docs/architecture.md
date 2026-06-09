# システム構成

## 技術スタック

| レイヤー | 技術 |
|---|---|
| 言語 | Python 3.12 |
| Web | FastAPI + uvicorn（ASGI 単一プロセス。判定は CPU で完結するのでワーカー1でよい） |
| 埋め込み | DINOv2 ViT-S/14 を ONNX 化 → onnxruntime（CPUExecutionProvider）で推論 |
| 数値計算 | numpy（k-NN は cosine 類似度の総当たり。数千件規模なら十分速い） |
| 画像 | Pillow（デコード・リサイズ・前処理）。SHA-256 で重複検出 |
| DB | SQLite（標準ライブラリ `sqlite3`。WAL モード）。ファイルは `/data` ボリューム |
| admin UI | サーバ側レンダリング（Jinja2 テンプレート）で十分。SPA は作らない |
| デプロイ | Railway（Dockerfile ビルド・ボリュームに `/data` をマウント） |

依存は最小に保つ（重い ML フレームワークを丸ごとは入れない）。
`torch` は **ONNX 変換スクリプトでのみ**使い、本番ランタイムには入れない（onnxruntime だけ）。

## ディレクトリ構成（実装時の目標）

```
app/
  main.py            FastAPI エントリ（ルーティング・起動時のモデル/DBロード）
  config.py          環境変数の読み込み（env.md と対応）
  db.py              SQLite 接続・スキーマ作成・CRUD（全 SQL はここに集約）
  models.py          Pydantic スキーマ（リクエスト/レスポンス）
  embed.py           DINOv2 ONNX 推論（前処理 → 埋め込みベクトル）
  classifier.py      k-NN 本体（近傍検索・多数決・confidence・flip 拡張の登録）
  store.py           project ごとの埋め込みインデックスのメモリ保持とウォームアップ
  auth.py            API キー検証・admin Basic 認証
  routes/
    predict.py       POST /v1/{project}/predict
    label.py         POST /v1/{project}/label
    projects.py      POST /v1/projects（作成）・GET /v1/projects（一覧, admin）
    admin.py         GET /admin（UI）・修正の受け口
    health.py        GET /healthz
  templates/         admin UI の Jinja2 テンプレート
scripts/
  export_dinov2_onnx.py   DINOv2 → ONNX 変換（ビルド時 or 事前に1回）
  import_labels.py        既存ラベルの一括取り込み（CSV/ディレクトリ）
models/
  dinov2_vits14.onnx      同梱する埋め込みモデル（Git LFS or ビルド時取得）
data/                     （gitignore）ローカル実行時の SQLite・画像・キャッシュ
  facing.db
  images/                 sha256 で保存した元画像（admin 表示・再埋め込み用）
docs/                     設計ドキュメント（このディレクトリ）
Dockerfile
railway.json
pyproject.toml            依存定義（uv or pip）
```

## リクエストのデータフロー

### predict（判定）

```
POST /v1/{project}/predict  (画像)
  → auth: API キー検証（project と紐付く）
  → 画像デコード・前処理（224x224・ImageNet 正規化）
  → DINOv2 ONNX → 384 次元ベクトル → L2 正規化
  → classifier: project のラベル付きベクトル集合から cosine 近傍 k 件
  → 多数決で left/right、票割合と近傍距離から confidence
  → {facing, confidence, uncertain, neighbors?}
```

判定で画像は保存しない（ラベルではないので）。任意で監査ログだけ残す。

### label（学習データ追加）

```
POST /v1/{project}/label  (画像 + facing)
  → auth
  → 画像デコード → sha256（重複なら facing を更新）
  → 元画像を data/images/<sha>.png に保存（admin 表示・将来の再埋め込み用）
  → DINOv2 → ベクトル → samples/embeddings に保存（source='human' など）
  → flip 拡張: 水平反転した画像の埋め込みを逆 facing で追加（is_flip_aug=1）
  → メモリ上の project インデックスにも追加（再学習なしで即反映）
```

### 起動時

```
起動 → DINOv2 ONNX をロード → DB から全 project の埋め込みをメモリへ
     → 以降 predict/label はメモリインデックスを使う（DB は永続化用）
```

## プロセスモデル

- 単一プロセス・単一ワーカーで開始（CPU 推論・SQLite 単一ファイルのため）。
- 埋め込みインデックスは **プロセスメモリに保持**し、DB を source of truth とする。
  起動時に DB から復元、label 時に DB とメモリの両方へ書く。
- 規模が増えて総当たり k-NN が遅くなったら、近似最近傍（hnswlib 等）に差し替える余地を残す
  （初版は numpy 総当たりで十分。数千〜数万件まで実用）。

# ai-facing-api

画像内のキャラ・被写体が **どちら（left / right）を向いているか** を判定する、
汎用の左右向き判定マイクロサービス。

複数のサービスから再利用する前提で、HTTP API として独立させてある
（最初のクライアントは [ai-kyoto-osaka](../ai-kyoto-osaka) の妖怪姿絵の向き合わせ）。

## これは何をするものか

- 画像を投げると `left` / `right` と確信度を返す（`POST /v1/{project}/predict`）。
- 正解ラベルを投げると学習データに加わり、以降の判定が賢くなる（`POST /v1/{project}/label`）。
- admin 画面でラベルをポチポチ修正でき、**直すほど精度が上がる**（human-in-the-loop）。

## 設計の芯（3行）

- **埋め込み + k-NN**。DINOv2 で画像を特徴ベクトル化し、ラベル付きベクトルの近傍多数決で判定する。
  CNN を丸ごと学習しないので、**少データ・CPU・即時反映**で回る。
- **ラベル追加で即学習**。k-NN は近傍集合に1件足すだけ＝再学習ステップが無い。立てっぱなしで判定と学習を回し続けられる。
- **project ごとにラベル空間を分離**（マルチテナント）。姿絵イラストと写真が混ざらない。

## ドキュメント

**設計・仕様の正は [`docs/`](docs/README.md) 配下。** まず [`docs/README.md`](docs/README.md) を読むこと。
このリポジトリは **設計ドキュメント先行**で、実装はドキュメントに従って起こす。

## スタック

Python 3.12 / FastAPI / uvicorn / onnxruntime（DINOv2 ONNX・CPU）/ SQLite / Railway。
詳細は [docs/architecture.md](docs/architecture.md)。

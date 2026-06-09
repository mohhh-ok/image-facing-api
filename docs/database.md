# 永続化・DB スキーマ

SQLite 単一ファイル（`/data/facing.db`・WAL モード）。全 SQL は `app/db.py` に集約する。
画像の元データは `/data/images/<sha256>.png` に保存（DB には画像本体を入れず、パス/ハッシュだけ持つ）。

## なぜ SQLite か

- 単一プロセス・単一ボリュームの構成に最適。運用が軽い。
- 規模（数千〜数万ラベル / project）では性能十分。埋め込みの近傍探索はメモリ上で行うので
  DB は「永続化と一覧表示」が主務。
- 将来テナントが激増したら Postgres へ移す余地は残す（`db.py` 集約で差し替え面を限定）。

## テーブル

### projects

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT UNIQUE | project キー（URL に出る。英数・ハイフン） |
| description | TEXT | 任意 |
| api_key_hash | TEXT | API キーの hash（平文は保存しない・[security.md](security.md)） |
| k | INTEGER | k-NN の k（既定 9・NULL ならグローバル既定） |
| settings_json | TEXT | 透過合成色・しきい値など project 個別設定（任意） |
| created_at | TEXT | ISO8601 |

### samples（ラベル付きデータ＝学習集合の1件）

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | |
| project | TEXT | projects.name（インデックス対象） |
| image_sha256 | TEXT | 元画像のハッシュ（`is_flip_aug=1` の行は元画像と同じ sha を指す） |
| facing | TEXT | `'left' \| 'right'` |
| source | TEXT | `'human' \| 'import' \| 'model'` 等。human 最優先 |
| is_flip_aug | INTEGER | 0/1。1 = flip 拡張で自動生成された逆ラベル行 |
| origin_sample_id | INTEGER | flip 行が元にした sample.id（二重カウント抑制・再生成用）。元行は NULL |
| external_id | TEXT | クライアント側識別子（任意・保存のみ。突合は image_sha256 で行う） |
| created_at | TEXT | |
| updated_at | TEXT | facing 更新時刻 |

インデックス: `(project, image_sha256)`, `(project, facing)`, `(project, is_flip_aug)`。

### embeddings（埋め込みベクトル）

| カラム | 型 | 説明 |
|---|---|---|
| sample_id | INTEGER PK FK→samples.id | |
| model_name | TEXT | 例 `dinov2_vits14` |
| embed_version | INTEGER | 前処理込みのバージョン。変えたら再埋め込み |
| dim | INTEGER | 384 |
| vector | BLOB | float32 を L2 正規化したものを raw bytes で（np.tobytes） |

> samples と embeddings を分けるのは、埋め込みモデルを変えたとき embeddings だけ貼り直せるようにするため。
> 1 sample に 1 ベクトル（現行モデル分）。複数モデルを併存させたいなら `(sample_id, model_name)` を PK にする。

### predictions（任意・監査ログ）

predict のリクエストを残すなら最小限で（画像は保存しない・ハッシュだけ）。
精度の事後分析や「uncertain がどれだけ出ているか」の監視に使う。初版は省略可。

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | |
| project | TEXT | |
| image_sha256 | TEXT | （保存する場合）|
| facing | TEXT | 返した結果 |
| confidence | REAL | |
| uncertain | INTEGER | |
| created_at | TEXT | |

## メモリ側のインデックス

- 起動時に `embeddings` を project ごとに numpy 行列へ載せる（`store.py`）。
- predict は行列との内積（cosine）で近傍を取る。label は DB 追記＋行列へ 1 行 append。
- プロセス再起動で DB から再構築できるので、メモリは純粋なキャッシュ。

## マイグレーション

- 初版は `db.py` の `init_schema()` が `CREATE TABLE IF NOT EXISTS` を流すだけでよい。
- スキーマ変更は素朴に ALTER か、件数が小さいので作り直し＋`scripts/import_labels.py` で再投入。
- 重い ORM は入れない（標準 `sqlite3` で十分）。

# API 利用ガイド

このサービスを**呼ぶ側**の手順書。エンドポイントの厳密な仕様は [api.md](api.md) が正で、
ここは「実際にどう叩くか」の how-to。ai-kyoto-osaka 固有の移行手順は [client-integration.md](client-integration.md) を参照。

## 1 行でいうと

画像を投げると `facing`（`"left"` か `"right"`）を返す。ラベルを足すほど精度が上がる（[model.md](model.md)）。
LLM は呼ばない・外部に副作用を持たない、画像 → ラベルの純関数的サービス。

---

## ベース URL とバージョン

- ローカル: `http://localhost:8000`（`PORT` 既定 8000・[env.md](env.md)）
- 本番: `https://facing-api-production.up.railway.app`
- 全 API にバージョンプレフィックス `/v1` が付く（admin / healthz を除く）。

以降の例では `BASE=http://localhost:8000`、`PROJECT=ai-kyoto-osaka` とする。

---

## 認証

| 用途 | 方式 | ヘッダ |
|---|---|---|
| predict / label（サービス間） | API キー | `X-API-Key: fk_live_xxx` |
| projects 作成・一覧 / admin UI | Basic 認証 | `Authorization: Basic ...`（`ADMIN_USER` / `ADMIN_PASS`） |
| healthz | 不要 | — |

- API キーは **project ごと**。URL の `{project}` とキーが一致しないと `403 forbidden`。
- ローカル開発では `AUTH_DISABLED=1` で認証を丸ごとバイパスできる（**本番では絶対に立てない**・[security.md](security.md)）。
- API キーは作成レスポンスで **一度だけ平文を返す**（DB は hash 保存）。控え忘れたら作り直し。

---

## 画像の渡し方（3 通り・どれか 1 つ）

すべてのエンドポイント共通。`app/request_input.py` で解釈する。

1. **JSON `image_base64`**（無難・推奨）
   ```json
   { "image_base64": "iVBORw0KGgo..." }
   ```
   `data:image/png;base64,...` の data URL プレフィックス付きでも受け付ける。
2. **multipart/form-data の `file` フィールド** — そのほかの値（`facing` 等）はフォーム項目で送る。
3. **JSON `image_url`** — `ALLOW_IMAGE_URL=true` のときだけ有効（SSRF 懸念で既定オフ）。

上限は `MAX_IMAGE_BYTES`（既定 10MB）。超過は `413 payload_too_large`。

---

## エンドポイント別の使い方

### project を作る（admin・最初に一度）

```bash
curl -u "$ADMIN_USER:$ADMIN_PASS" \
  -X POST "$BASE/v1/projects" \
  -H 'content-type: application/json' \
  -d '{"name":"ai-kyoto-osaka","description":"妖怪姿絵の向き合わせ"}'
# => {"project":"ai-kyoto-osaka","api_key":"fk_live_xxxxxxxx...","created_at":"..."}
```
`api_key` をクライアントの env（`FACING_API_KEY` 等）へ保存する。一覧は `GET /v1/projects`（同じく admin）。

### 判定する（predict）

学習データには**加えない**読み取り操作。好きなタイミングで叩いてよい。

```bash
curl -X POST "$BASE/v1/$PROJECT/predict" \
  -H "X-API-Key: $FACING_API_KEY" \
  -H 'content-type: application/json' \
  -d "{\"image_base64\":\"$(base64 -i sample.png)\"}"
```
レスポンス:
```json
{ "facing": "left", "confidence": 0.86, "uncertain": false,
  "neighbors": [ {"sample_id":1421,"facing":"left","similarity":0.94} ],
  "model": "dinov2_vits14", "k": 9 }
```
- `uncertain=true` でも `facing` は必ず返る（票が割れた／近傍が遠い／ラベルが少ない）。
  クライアントはこれを見て **フォールバック（既存 LLM 判定など）や admin 行き**に回す。
- `neighbors` はデバッグ用。不要なら `?include_neighbors=false`（または JSON に同フィールド）で省ける。
- predict は監査ログに **画像ハッシュ＋判定結果のみ**残す（画像本体は保存しない）。

### 正解を登録する（label）

学習データに加わり、以降の predict に**即時反映**される。`facing` が必須。

```bash
curl -X POST "$BASE/v1/$PROJECT/label" \
  -H "X-API-Key: $FACING_API_KEY" \
  -H 'content-type: application/json' \
  -d "{\"image_base64\":\"$(base64 -i sample.png)\",\"facing\":\"right\",\"source\":\"human\"}"
# => {"sample_id":1422,"facing":"right","deduped":false,"flip_added":true,"project_size":318}
```
- `source` 既定 `"human"`（`"human" | "import" | "model"`）。`human` が最優先ラベル。
- 同一画像（**sha256 一致**）が既にあれば facing を上書きし `deduped:true`（→ 後述のフロー）。
- `flip_added`: 水平反転版を逆ラベルで自動追加したか（既定で追加。母数が自動で左右均衡する）。
- `external_id` は任意で渡せるが **DB に保存されるだけで突合には使われない**（突合は画像の sha256）。
- **label に流すのは正解だけ**。自動・実験的な判定結果を無闇に流すとラベル空間が汚れる（[client-integration.md](client-integration.md)）。

### ヘルスチェック（healthz）

```bash
curl "$BASE/healthz"   # => {"status":"ok","model_loaded":true,"projects":3}
```

---

## 「判定 → 使用者 UI で確認・修正 → 修正反映」のフロー

predict はステートレスで、サーバは predict と label を繋ぐ ID（predict_id 等）を**発行しない**。
突合は **画像の sha256**で行うため、繋ぎは次の形になる。

```
1. クライアントが判定対象の画像を手元に保持する
2. POST /predict（画像）       → facing / uncertain を受け取り UI に出す
3. 使用者が UI で確認・修正する
4. 修正後の facing を POST /label（同じ画像 + facing, source="human"）で送る
   → 同じ画像なので sha256 一致で既存ラベルを上書き（deduped:true）。新規なら追加。
   → 即 k-NN に反映される
```

ポイント:
- **修正時は同じ画像をもう一度送る**（predict の応答に ID が無いため、画像が突合キー）。
  クライアントは predict した画像を破棄せず保持しておくこと。
- 修正は admin UI（`/admin`）からでも同じ label 経路を通る。クライアント UI から直すなら
  その操作を `/label`（`source="human"`）へ中継すればよい。
- 「最初は LLM 等で判定 → 人が直したぶんだけ label に流して種を育てる」運用が基本（[client-integration.md](client-integration.md)）。

---

## クライアント実装メモ

- **タイムアウトとフォールバックを必ず用意**する。外部依存なので、落ちても呼び出し側のバッチを止めない。
- env は `FACING_API_URL` / `FACING_API_KEY` で持ち、未設定ならフォールバックに倒す（ローカルのオフライン自律性）。
- 画像バイナリは加工しない。**向きはデータ（facing）で持ち、表示時に CSS で反転**する。

### Python（requests）

```python
import base64, requests

def predict(img_bytes: bytes) -> dict:
    b64 = base64.b64encode(img_bytes).decode()
    r = requests.post(
        f"{BASE}/v1/{PROJECT}/predict",
        headers={"X-API-Key": API_KEY},
        json={"image_base64": b64},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()   # {"facing": ..., "uncertain": ..., ...}
```

### TypeScript（fetch）

```ts
async function predict(imgBase64: string): Promise<{ facing: "left" | "right"; uncertain: boolean }> {
  const res = await fetch(`${BASE}/v1/${PROJECT}/predict`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "content-type": "application/json" },
    body: JSON.stringify({ image_base64: imgBase64 }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`facing-api ${res.status}`);
  return res.json();
}
```

---

## エラー

形式は `{"error": {"code": "...", "message": "..."}}`。主なもの（全量は [api.md](api.md)）:

| HTTP | code | 対処 |
|---|---|---|
| 400 | `bad_image` / `bad_request` | 画像がデコード不可・必須欠落（facing 等）・facing が left/right 以外 |
| 401 | `unauthorized` | `X-API-Key` / Basic が無い |
| 403 | `forbidden` | キーは有効だが project 不一致 |
| 404 | `no_such_project` | project 未作成 |
| 413 | `payload_too_large` | 画像が `MAX_IMAGE_BYTES` 超過 |
| 500 | `internal` | 想定外。リトライ＋フォールバックで受ける |

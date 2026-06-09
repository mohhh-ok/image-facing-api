# セキュリティ

このサービスは **画像を受け取り left/right を返すだけ**で、LLM を呼ばず外部に副作用を持たない。
攻撃面は「受け取る画像・メタデータ」と「認証」に限られる。

## 認証

- **サービス間（predict / label）**: `X-API-Key` ヘッダ。project に紐づくキーを hash 照合（[multi-tenant.md](multi-tenant.md)）。
- **admin / project 作成**: Basic 認証（`ADMIN_USER` / `ADMIN_PASS`）。
- API キーは平文を DB に置かない（発行時のみ平文返却・以後は hash）。
- 認証は**最初から付ける**前提で実装する。「あとで付ける」と公開時に漏れる。
  ローカル開発でだけ `AUTH_DISABLED=1` で外せるようにしてよい（本番では絶対に立てない）。

## untrusted input の扱い

外部から来るのは「画像」と「少量のメタデータ（external_id 等）」。

- **画像**:
  - サイズ上限（例 10MB・`MAX_IMAGE_BYTES`）。超過は 413。
  - デコードは Pillow。デコード失敗・非対応形式・ピクセル数過大（decompression bomb）を弾く
    （`Image.MAX_IMAGE_PIXELS` を設定）。
  - 画像経由のコード実行リスクは Pillow の既知 CVE に依存するので、依存を最新に保つ。
  - `image_url` を受ける場合は **SSRF に注意**: 内部 IP / localhost / メタデータエンドポイント（169.254.169.254）を
    ブロックし、スキームは https のみ、リダイレクト追跡を制限、タイムアウトを付ける。
    不安なら初版は `image_url` を無効化し base64/multipart のみにする。
- **メタデータ（external_id, description, project 名）**:
  - 長さ上限・文字種制限（project 名は英数ハイフンのみ）。
  - SQL は必ずパラメータバインド（文字列連結禁止）。
  - admin UI に表示するときは **HTML エスケープ**（テンプレートの自動エスケープを切らない）。
- このサービスは受け取ったテキストを**指示として解釈する経路を持たない**（LLM なし）ので、
  prompt injection の直接被害は無い。ただしクライアント側がこのサービスの出力をどう使うかは
  クライアントの責務（→ [client-integration.md](client-integration.md)）。

## リソース・濫用対策

- リクエストボディ上限・タイムアウト・（必要なら）project 単位のレート制限。
- predict は画像を保存しない（監査ログを残すならハッシュのみ）。label のみ元画像を保存する。
- ログに API キー平文・画像本体を出さない。

## 秘密情報

- `ADMIN_PASS`・API キー・（クライアント側の）LLM トークン等は env で渡し、リポにコミットしない。
- `.env` はコミットしない（`.gitignore`）。本番は Railway の環境変数で設定。

# クライアント連携

クライアントは「画像を投げて facing を受け取り、**表示時に CSS で反転**する」だけ。
画像バイナリは加工しない（向きはデータで持つ）。ここでは最初のクライアント
[ai-kyoto-osaka](../../ai-kyoto-osaka)（妖怪姿絵の向き合わせ）を例に、移行手順を示す。

## 連携の原則

- **predict は読み取り**。クライアントの好きなタイミングで叩いてよい。
- **label（学習データ追加）は admin/人手の正解だけ**。実験的・自動の判定結果を無闇に label に流して
  ラベル空間を汚さない（汚染防止）。
- confidence が低い（`uncertain=true`）ときは、クライアント側で **フォールバック**（既存の LLM 判定など）に
  回すか、admin レビュー対象として印を付ける。
- クライアントの**オフライン自律性を壊さない**: ローカル開発では既定でこのサービスを叩かず、
  mock かローカル内処理で動かす。本番 or 明示時だけ API を叩く。

## ai-kyoto-osaka の現状（移行前）

- `src/img/gptimage.ts`: 生成 PNG を Opus で判定し、**right なら `sharp.flop()` で画像バイナリを左右反転**して
  「全部左向き」に統一保存していた。`facing_judgements` テーブルは監査ログ。
- `src/web/components/BattleReplay.tsx`: 「全部左向き」前提で、左に立つキャラだけ CSS 反転
  （`-scale-x-100`）して向き合わせていた。

## 移行後の形

1. **生成側（`gptimage.ts`）**: `flop()` を廃止し、**画像は生成ままで保存**。
   向きは facing-api の `POST /v1/ai-kyoto-osaka/predict` で取得する。
   - 認証なし環境や API 失敗時は **既存の Opus 判定にフォールバック**（さらに失敗なら `left`）。
   - 取得した facing と confidence を妖怪レコードに保存。
2. **スキーマ**: `yokai` に `facing TEXT`（`'left'|'right'`）カラムを追加。`facing_judgements` は監査として残す。
3. **API/型**: 公開ステートの妖怪に `facing` を含める。
4. **UI（表示時に反転）**: 「置きたい向き ≠ facing」のときだけ CSS 反転する。
   ```
   shouldFlip = (desiredFacing !== yokai.facing)   // desired は配置で決める
   ```
   - 妖怪カード / 殿堂: 左向きで揃えたいなら `desired = 'left'`。
   - 合戦リプレイ: 右に立つ味方は `desired = 'right'`、左の敵は `desired = 'left'`。
   - 既存の `-scale-x-100` の仕組みをこの条件式に置き換えるだけ。
5. **既存データの移行**: 既存姿絵は既に flop 済み（＝全部左向き）。よって **`facing = 'left'` で初期化**すれば
   見た目は現状のまま変わらない。新規生成分から flop 廃止＋生 facing に切り替わる。
6. **admin での修正**: 向きの手修正は facing-api 側の `/admin` に集約してよい（全 project 横断で運用）。
   ai-kyoto-osaka 側 UI から直すなら、その操作を facing-api の `/label`（`source='human'`）へ中継する。

## ラベルの育て方（ai-kyoto-osaka の場合）

1. 立ち上げ期: Opus 判定を初期 facing にしつつ、生成画像を facing-api に label として流して種にする
   （Opus 由来は `source='model'` で登録し、人手 `human` と区別）。
2. admin で uncertain や明らかな誤りを修正（`human`）。flip 拡張で母数は自動で均衡。
3. ラベルが数百件貯まれば、predict の confidence が上がり、Opus フォールバックを呼ぶ頻度が下がる。
4. さらに貯まれば Opus を完全に外し、facing-api 単独で回す。

## 最低限のクライアント実装メモ

- リクエストは base64 が無難（multipart でも可）。`X-API-Key` を付ける。
- タイムアウトとフォールバックを必ず用意（外部依存なので、落ちても日次バッチを止めない）。
- `FACING_API_URL` と `FACING_API_KEY` を env で持つ。未設定ならフォールバックに倒す
  （ローカルのオフライン自律性のため）。

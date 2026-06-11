import { useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  type Facing,
  type LabelResponse,
  type PredictResponse,
  label,
  predict,
} from "./api";

const LS_KEY = "image-facing-api.config";

function loadConfig(): ApiConfig {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw) as ApiConfig;
  } catch {
    // ignore
  }
  return {
    baseUrl: import.meta.env.VITE_API_BASE ?? "http://localhost:8000",
    project: import.meta.env.VITE_PROJECT ?? "demo",
    apiKey: import.meta.env.VITE_API_KEY ?? "",
  };
}

function saveConfig(cfg: ApiConfig) {
  localStorage.setItem(LS_KEY, JSON.stringify(cfg));
}

export function App() {
  const [cfg, setCfg] = useState<ApiConfig>(loadConfig);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [labelMsg, setLabelMsg] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => saveConfig(cfg), [cfg]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const ready = useMemo(
    () => cfg.baseUrl && cfg.project && cfg.apiKey,
    [cfg],
  );

  function pickFile(f: File | null) {
    setFile(f);
    setResult(null);
    setError(null);
    setLabelMsg(null);
  }

  async function onPredict() {
    if (!file || !ready) return;
    setLoading(true);
    setError(null);
    setLabelMsg(null);
    try {
      const r = await predict(cfg, file);
      setResult(r);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  async function onLabel(facing: Facing) {
    if (!file || !ready) return;
    setLoading(true);
    setError(null);
    try {
      const r: LabelResponse = await label(cfg, file, facing);
      setLabelMsg(
        `登録: facing=${r.facing} / sample_id=${r.sample_id} / project_size=${r.project_size}` +
          (r.deduped ? " (既存を更新)" : "") +
          (r.flip_added ? " / flip追加" : ""),
      );
    } catch (e) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }

  return (
    <div className="wrap">
      <h1>image-facing-api デモクライアント</h1>

      <div className="card">
        <h2>接続設定</h2>
        <div className="row">
          <div>
            <label>API ベース URL</label>
            <input
              type="text"
              value={cfg.baseUrl}
              onChange={(e) => setCfg({ ...cfg, baseUrl: e.target.value })}
              placeholder="http://localhost:8000"
            />
          </div>
          <div>
            <label>project</label>
            <input
              type="text"
              value={cfg.project}
              onChange={(e) => setCfg({ ...cfg, project: e.target.value })}
              placeholder="demo"
            />
          </div>
        </div>
        <label>API キー (X-API-Key)</label>
        <input
          type="password"
          value={cfg.apiKey}
          onChange={(e) => setCfg({ ...cfg, apiKey: e.target.value })}
          placeholder="fk_live_..."
        />
        <p className="muted">
          .env (VITE_API_BASE / VITE_PROJECT / VITE_API_KEY) から初期化され、変更は
          localStorage に保存されます。
        </p>
      </div>

      <div className="card">
        <h2>画像</h2>
        <div
          className={`drop${dragOver ? " over" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          {file
            ? `${file.name} (${Math.round(file.size / 1024)} KB)`
            : "ここに画像をドロップ、またはクリックして選択"}
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />
        </div>

        {previewUrl && (
          <div className="preview" style={{ marginTop: 16 }}>
            <img src={previewUrl} alt="preview" />
            <div style={{ flex: 1 }}>
              <div className="actions">
                <button
                  className="primary"
                  onClick={onPredict}
                  disabled={loading || !ready}
                >
                  judge (predict)
                </button>
                <button onClick={() => pickFile(null)} disabled={loading}>
                  クリア
                </button>
              </div>
              {!ready && (
                <p className="warn">
                  接続設定が未入力です（API キー必須）
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {result && (
        <div className="card">
          <h2>判定結果</h2>
          <div className={`facing ${result.facing}`}>
            {result.facing.toUpperCase()}
          </div>
          <div className="muted">
            confidence: {(result.confidence * 100).toFixed(1)}% / model:{" "}
            {result.model} / k={result.k}
          </div>
          <div className="bar">
            <div style={{ width: `${result.confidence * 100}%` }} />
          </div>
          {result.uncertain && (
            <p className="warn">
              uncertain: 票が割れた / 近傍が遠い / ラベルが少ない可能性。
              下の「正解として登録」で学習させると次回から反映されます。
            </p>
          )}

          <h2 style={{ marginTop: 16 }}>正解として登録 (label)</h2>
          <div className="actions">
            <button onClick={() => onLabel("left")} disabled={loading}>
              ← left として登録
            </button>
            <button onClick={() => onLabel("right")} disabled={loading}>
              right として登録 →
            </button>
          </div>
          {labelMsg && <p className="muted">{labelMsg}</p>}

          {result.neighbors && result.neighbors.length > 0 && (
            <>
              <h2 style={{ marginTop: 16 }}>近傍 (k-NN)</h2>
              <pre>{JSON.stringify(result.neighbors, null, 2)}</pre>
            </>
          )}
        </div>
      )}

      {error && (
        <div className="card">
          <p className="err">エラー: {error}</p>
        </div>
      )}
    </div>
  );
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) return `[${e.status} ${e.code}] ${e.message}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

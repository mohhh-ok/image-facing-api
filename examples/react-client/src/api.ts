export type Facing = "left" | "right";

export type Neighbor = {
  sample_id: number;
  facing: Facing;
  similarity: number;
};

export type PredictResponse = {
  facing: Facing;
  confidence: number;
  uncertain: boolean;
  neighbors?: Neighbor[];
  model: string;
  k: number;
};

export type LabelResponse = {
  sample_id: number;
  facing: Facing;
  deduped: boolean;
  flip_added: boolean;
  project_size: number;
};

export type ApiConfig = {
  baseUrl: string;
  project: string;
  apiKey: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function postFile<T>(
  cfg: ApiConfig,
  path: string,
  file: File,
  extra?: Record<string, string>,
): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  }
  const res = await fetch(`${cfg.baseUrl}/v1/${cfg.project}${path}`, {
    method: "POST",
    headers: { "X-API-Key": cfg.apiKey },
    body: fd,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const code = json?.error?.code ?? "unknown";
    const msg = json?.error?.message ?? res.statusText;
    throw new ApiError(res.status, code, msg);
  }
  return json as T;
}

export function predict(cfg: ApiConfig, file: File) {
  return postFile<PredictResponse>(cfg, "/predict", file);
}

export function label(
  cfg: ApiConfig,
  file: File,
  facing: Facing,
  externalId?: string,
) {
  const extra: Record<string, string> = { facing, source: "human" };
  if (externalId) extra.external_id = externalId;
  return postFile<LabelResponse>(cfg, "/label", file, extra);
}

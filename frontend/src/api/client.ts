import type {
  AnalysisResult,
  AnalyzeContext,
  Meta,
  OCRResponse,
  PhraseDetail,
  PhraseSummary,
  Province,
  SearchResponse,
  StageEvent,
  Stats,
  Theme,
  VehicleType,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status}).`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 429) message = "Too many requests. Please wait a little and try again.";
  return new ApiError(res.status, message);
}

export async function request<T>(path: string, init: RequestInit & { token?: string | null } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (init.token) headers.set("Authorization", `Bearer ${init.token}`);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the analysis server. Check your connection and try again.");
  }
  if (!res.ok) throw await parseError(res);
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, String(v)));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export interface AnalyzeInput {
  text: string;
  context?: AnalyzeContext | null;
  contribute?: boolean;
  ocr_text?: string | null;
  ocr_provider?: string | null;
}

export interface StreamHandlers {
  onStage?: (e: StageEvent) => void;
  onPreliminary?: (r: AnalysisResult) => void;
}

/** POST /api/analyze/stream and parse server-sent events from the response body. */
export async function analyzeStream(input: AnalyzeInput, handlers: StreamHandlers, signal?: AbortSignal): Promise<AnalysisResult> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/analyze/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(input),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Can't reach the analysis server. Check your connection and try again.");
  }
  if (!res.ok || !res.body) throw await parseError(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: AnalysisResult | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) data.push(line.slice(6));
      }
      if (!data.length) continue;
      const payload = JSON.parse(data.join("\n"));
      if (event === "stage") handlers.onStage?.(payload);
      else if (event === "preliminary") handlers.onPreliminary?.(payload);
      else if (event === "result") result = payload;
      else if (event === "error") throw new ApiError(500, payload.detail ?? "The analysis failed.");
    }
  }
  if (!result) throw new ApiError(500, "The analysis ended without a result. Please try again.");
  return result;
}

export const api = {
  health: () => request<{ status: string; engine: string; corpus_size: number; ocr: string; admin_enabled: boolean }>("/api/health"),
  meta: () => request<Meta>("/api/meta"),
  examples: () => request<PhraseSummary[]>("/api/examples"),
  analysis: (id: string) => request<AnalysisResult>(`/api/analyses/${encodeURIComponent(id)}`),
  analyze: (input: AnalyzeInput) => request<AnalysisResult>("/api/analyze", { method: "POST", body: JSON.stringify(input) }),
  ocr: (file: Blob, filename = "inscription.jpg") => {
    const fd = new FormData();
    fd.append("file", file, filename);
    return request<OCRResponse>("/api/ocr", { method: "POST", body: fd });
  },
  phrases: (params: { theme?: string; cluster?: string; valence?: string; needs_review?: boolean; limit?: number } = {}) =>
    request<{ total: number; items: PhraseSummary[] }>(`/api/phrases${qs({ limit: 500, ...params })}`),
  phrase: (id: number | string) => request<PhraseDetail>(`/api/phrases/${id}`),
  search: (q: string, theme?: string) => request<SearchResponse>(`/api/search${qs({ q, theme, k: 20 })}`),
  themes: () => request<Theme[]>("/api/themes"),
  clusters: () => request<{ name: string; member_ids: number[]; description: string }[]>("/api/clusters"),
  stats: () => request<Stats>("/api/stats"),
  locations: () => request<Province[]>("/api/locations"),
  municipalities: (districtId: number) =>
    request<{ id: number; name_en: string; name_ne: string | null; kind: string | null }[]>(`/api/locations/districts/${districtId}/municipalities`),
  vehicles: () => request<VehicleType[]>("/api/vehicles"),
  references: () => request<import("./types").Reference[]>("/api/references"),
};

// --- Admin -----------------------------------------------------------------------------

export const adminApi = {
  login: (username: string, password: string) =>
    request<{ token: string; expires_at: string; username: string }>("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  get: <T>(path: string, token: string) => request<T>(`/api/admin${path}`, { token }),
  send: <T>(path: string, token: string, method: "POST" | "PUT" | "DELETE", body?: unknown) =>
    request<T>(`/api/admin${path}`, { method, token, body: body === undefined ? undefined : JSON.stringify(body) }),
  upload: <T>(path: string, token: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<T>(`/api/admin${path}`, { method: "POST", token, body: fd });
  },
  download: async (path: string, token: string, filename: string) => {
    const res = await fetch(`${BASE}/api/admin${path}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw await parseError(res);
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    a.click();
    URL.revokeObjectURL(url);
  },
};

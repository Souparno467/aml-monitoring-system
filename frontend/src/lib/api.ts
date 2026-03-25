import type { ApiError } from "./types";

const DEFAULT_BASE = "/api/v1";

function getBaseUrl() {
  const env = import.meta.env as unknown as { VITE_API_BASE_URL?: string };
  return (env.VITE_API_BASE_URL || DEFAULT_BASE).replace(/\/+$/, "");
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiError | undefined;
    if (body?.detail) return body.detail;
  } catch {
    // ignore JSON parse errors
  }
  return `${res.status} ${res.statusText}`.trim();
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${getBaseUrl()}${path}`, {
    headers: { Accept: "application/json" }
  });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return (await res.json()) as T;
}

export async function apiSend<T>(
  path: string,
  method: "POST" | "PATCH",
  payload: unknown
): Promise<T> {
  const res = await fetch(`${getBaseUrl()}${path}`, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(await readErrorMessage(res));
  return (await res.json()) as T;
}


import type { ApiError } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiRequestError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (options?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiError | null;
    throw new ApiRequestError(response.status, body?.error ?? "request_failed", body?.message ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

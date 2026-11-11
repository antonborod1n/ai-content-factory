const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const PROJECT_KEY = "acf.projectId";

export function currentProjectId(): string {
  return localStorage.getItem(PROJECT_KEY) ?? "";
}

export function setCurrentProjectId(projectId: string): void {
  localStorage.setItem(PROJECT_KEY, projectId);
  window.dispatchEvent(new CustomEvent("acf:project", { detail: projectId }));
}

/** Persist without notifying the layout (used when the layout already shows this id). */
export function rememberProjectId(projectId: string): void {
  localStorage.setItem(PROJECT_KEY, projectId);
}

function projectHeaders(pinned?: string): Record<string, string> {
  const projectId = pinned ?? currentProjectId();
  return projectId ? { "X-Project-Id": projectId } : {};
}

/** Discovery and competitor clustering can take several minutes. */
const LONG_REQUEST_MS = 10 * 60 * 1000;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function errorDetail(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) {
    return fallback;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String(item.msg);
        }
        return "";
      })
      .filter(Boolean);
    if (messages.length > 0) {
      return messages.join("; ");
    }
  }
  return fallback;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText || "Запрос не выполнен";
    try {
      detail = errorDetail(await response.json(), detail);
    } catch {
      // Keep the HTTP status text when the body is not JSON.
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { headers: projectHeaders() });
  return parseResponse<T>(response);
}

export async function apiPatchJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...projectHeaders() },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(response);
}

/** `projectId` pins the request to a project chosen earlier, e.g. at batch start. */
export async function apiPostJson<T>(
  path: string,
  body: unknown,
  projectId?: string,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...projectHeaders(projectId) },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(LONG_REQUEST_MS),
  });
  return parseResponse<T>(response);
}

export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: projectHeaders(),
  });
  if (response.status === 204) {
    return;
  }
  await parseResponse<unknown>(response);
}

export async function apiPostForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: projectHeaders(),
    body,
    signal: AbortSignal.timeout(LONG_REQUEST_MS),
  });
  return parseResponse<T>(response);
}

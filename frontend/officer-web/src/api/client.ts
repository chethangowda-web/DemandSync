// Same-origin by default (the API serves this app in production; Vite proxies /api in dev).
// Every value shown in the UI comes from the API; nothing here is mocked.
const BASE: string = import.meta.env.VITE_API_BASE || '';
const TOKEN_KEY = 'demandsync.token';

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const getToken = (): string | null => { try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; } };
export const setToken = (t: string | null) => {
  try { t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
};

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...opts,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.headers as any) },
    });
  } catch {
    // Backend down, proxy ECONNREFUSED, or browser offline: fetch itself throws (TypeError).
    throw new ApiError(0, 'Could not reach the server. Please check your connection and try again.');
  }
  if (!res.ok) {
    // 5xx (including the Vite dev proxy's empty-body 500 "Internal Server Error" when the
    // API process is not running) is never actionable by the officer: show a friendly
    // message instead of the raw HTTP status text.
    if (res.status >= 500 || res.status === 0) {
      throw new ApiError(res.status, 'Something went wrong on our side. Please try again in a moment.');
    }
    let detail = '';
    try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail); } catch { /* not json */ }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const post = <T = any>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

export const get = <T = any>(path: string) => api<T>(path);

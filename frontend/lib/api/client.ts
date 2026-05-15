/**
 * Thin fetch wrapper for the Insilo backend.
 *
 * In production the request is authenticated by Olares' Envoy sidecar
 * which injects the `X-Bfl-User` header. For local dev we mock it via
 * NEXT_PUBLIC_USER so the FastAPI dependency `get_current_user` succeeds.
 */

// Production (Olares): empty string -> requests go to the same origin (e.g.
// https://insilo.kaivostudio.olares.de), Next.js rewrites `/api/*` to the
// backend via cluster DNS. Avoids CORS + a second Authelia hop on the
// invisible api entrance.
// Local dev: NEXT_PUBLIC_API_URL=http://localhost:8000 in .env.local.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const DEV_USER = process.env.NEXT_PUBLIC_USER ?? "devuser";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | object | null;
};

const LOCALE_COOKIE = "insilo-locale";
const SUPPORTED_LOCALES = new Set(["de", "en", "fr", "es", "it"]);

/** Read the in-app locale override the LocaleSwitcher writes to a cookie.
 *  Returns null on the server (no document) or when no/invalid cookie. */
function readLocaleCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp("(?:^|; )" + LOCALE_COOKIE + "=([^;]+)"),
  );
  if (!match) return null;
  const value = decodeURIComponent(match[1]);
  return SUPPORTED_LOCALES.has(value) ? value : null;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, headers, ...rest } = options;

  // Mock Olares Envoy auth header for local dev.
  const finalHeaders: Record<string, string> = {
    "X-Bfl-User": DEV_USER,
    ...((headers as Record<string, string>) ?? {}),
  };

  // Forward the in-app locale override (LocaleSwitcher → cookie) as
  // Accept-Language so the backend's error i18n picks the same language
  // as the UI. Without this the browser-set Accept-Language wins, which
  // diverges as soon as the user manually overrides via /einstellungen.
  if (!finalHeaders["Accept-Language"]) {
    const cookieLocale = readLocaleCookie();
    if (cookieLocale) {
      finalHeaders["Accept-Language"] = cookieLocale;
    }
  }

  let finalBody: BodyInit | null | undefined = undefined;
  if (body !== undefined && body !== null) {
    if (
      body instanceof FormData ||
      body instanceof Blob ||
      body instanceof ArrayBuffer ||
      typeof body === "string"
    ) {
      finalBody = body;
    } else {
      finalBody = JSON.stringify(body);
      (finalHeaders as Record<string, string>)["Content-Type"] = "application/json";
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: finalBody,
  });

  if (!res.ok) {
    let parsed: unknown = null;
    try {
      parsed = await res.json();
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, parsed);
  }

  // Some endpoints (DELETE) return 204
  if (res.status === 204) return undefined as T;

  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "GET" });
}

export function apiPost<T>(path: string, body?: BodyInit | object): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body });
}

export function apiDelete<T = void>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "DELETE" });
}

export function apiPut<T>(path: string, body?: BodyInit | object): Promise<T> {
  return apiRequest<T>(path, { method: "PUT", body });
}

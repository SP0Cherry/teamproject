import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

export interface ApiEnvelope<T = unknown> {
  code: string;
  message: string;
  data: T | null;
  request_id: string;
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

const baseURL = import.meta.env.VITE_API_BASE || "/api/v1";

export const api: AxiosInstance = axios.create({
  baseURL,
  withCredentials: true,
});

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

/** Auth endpoints must not trigger auto-refresh (would loop on /auth/refresh). */
function isAuthRequest(url?: string): boolean {
  return !!url && /\/auth\/(login|register|refresh|logout)(\?|$|\/)/.test(url);
}

/**
 * Coordinated single refresh: concurrent 401s share one in-flight refresh so
 * the rotated refresh token is never replayed concurrently (SEC-06).
 */
let refreshPromise: Promise<boolean> | null = null;

export async function attemptRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      // Dynamic import avoids a circular dependency with the Pinia store,
      // which imports this module for setAccessToken.
      const { useAuthStore } = await import("../stores/auth");
      const auth = useAuthStore();
      return await auth.tryRefresh();
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

async function handleAuthFailure(): Promise<void> {
  setAccessToken(null);
  try {
    const { useAuthStore } = await import("../stores/auth");
    useAuthStore().doLogout();
  } catch {
    // ignore
  }
  if (
    typeof window !== "undefined" &&
    !window.location.pathname.startsWith("/login")
  ) {
    window.location.assign("/login");
  }
}

function normalizeError(error: AxiosError): ApiError {
  const data = error.response?.data as ApiEnvelope | undefined;
  if (data) {
    return new ApiError(data.code, data.message, error.response!.status);
  }
  return new ApiError(
    "INTERNAL_ERROR",
    "network error",
    error.response?.status || 0
  );
}

type RetryableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (response) => response.data as any,
  async (error: AxiosError) => {
    const config = error.config as RetryableConfig | undefined;
    if (
      error.response?.status === 401 &&
      config &&
      !isAuthRequest(config.url) &&
      !config._retried
    ) {
      config._retried = true;
      const refreshed = await attemptRefresh();
      if (refreshed) {
        const newToken = getAccessToken();
        if (newToken) {
          config.headers = config.headers || ({} as any);
          config.headers.Authorization = `Bearer ${newToken}`;
        }
        return api.request(config);
      }
      await handleAuthFailure();
    }
    return Promise.reject(normalizeError(error));
  }
);

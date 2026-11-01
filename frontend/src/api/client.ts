import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuth } from "@/stores/auth";
import type { TokenResponse } from "./types";

const baseURL = import.meta.env.VITE_API_URL || "";

// indexes: null -> ?location=Pune&location=Remote, which is what FastAPI list params expect.
export const api = axios.create({
  baseURL,
  withCredentials: true,
  paramsSerializer: { indexes: null },
});

api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

/** Exchange the httpOnly refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<string | null> {
  if (!refreshing) {
    refreshing = axios
      .post<TokenResponse>(`${baseURL}/api/auth/refresh`, null, { withCredentials: true })
      .then((res) => {
        useAuth.getState().setSession(res.data.access_token, res.data.user);
        return res.data.access_token;
      })
      .catch(() => {
        useAuth.getState().clear();
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const isAuthCall = original?.url?.startsWith("/api/auth/");
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      const token = await refreshSession();
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  },
);

interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
}

function cleanMsg(msg: string): string {
  return msg.replace(/^Value error, /, "");
}

/** One human-readable message for a failed request. */
export function apiErrorMessage(
  err: unknown,
  fallback = "Something went wrong. Try again.",
): string {
  if (!axios.isAxiosError(err)) return fallback;
  if (!err.response) return "Cannot reach the server. Check your connection.";
  const detail = (err.response.data as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return (detail as ValidationIssue[]).map((d) => cleanMsg(d.msg)).join(". ");
  }
  return fallback;
}

/** Field-level messages from a FastAPI 422 response, keyed by field name. */
export function apiFieldErrors(err: unknown): Record<string, string> {
  if (!axios.isAxiosError(err) || err.response?.status !== 422) return {};
  const detail = (err.response.data as { detail?: unknown })?.detail;
  if (!Array.isArray(detail)) return {};
  const out: Record<string, string> = {};
  for (const d of detail as ValidationIssue[]) {
    const field = d.loc[d.loc.length - 1];
    if (typeof field === "string" && field !== "body") out[field] = cleanMsg(d.msg);
  }
  return out;
}

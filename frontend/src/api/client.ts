import axios, { AxiosError, AxiosInstance } from "axios";

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

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response.data as any,
  (error: AxiosError) => {
    const data = error.response?.data as ApiEnvelope | undefined;
    if (data) {
      return Promise.reject(
        new ApiError(data.code, data.message, error.response!.status)
      );
    }
    return Promise.reject(
      new ApiError("INTERNAL_ERROR", "network error", error.response?.status || 0)
    );
  }
);

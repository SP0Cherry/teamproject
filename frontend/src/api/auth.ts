import { api, ApiEnvelope } from "./client";

export interface AuthResult {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export async function register(
  username: string,
  password: string
): Promise<ApiEnvelope<{ user_id: string; username: string }>> {
  return api.post("/auth/register", { username, password });
}

export async function login(
  username: string,
  password: string
): Promise<ApiEnvelope<AuthResult>> {
  return api.post("/auth/login", { username, password });
}

export async function logout(): Promise<ApiEnvelope> {
  return api.post("/auth/logout");
}

export async function refresh(): Promise<ApiEnvelope<AuthResult>> {
  return api.post("/auth/refresh");
}

export async function me(): Promise<ApiEnvelope<{ user_id: string; username: string }>> {
  return api.get("/auth/me");
}

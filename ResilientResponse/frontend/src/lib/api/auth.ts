import { api, setToken, setStoredAdmin, clearToken, getStoredAdmin, Admin } from "./client";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  admin: Admin;
}

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const res = await api.postPublic<LoginResponse>("/api/auth/login", credentials);
  setToken(res.access_token);
  setStoredAdmin(res.admin);
  return res;
}

export async function logout(): Promise<void> {
  try {
    await api.post("/api/auth/logout", {});
  } finally {
    clearToken();
  }
}

export async function getMe(): Promise<Admin> {
  return api.get<Admin>("/api/auth/me");
}

export { getStoredAdmin };

import { api } from "./client";
import type { ListResponse } from "./hospitals";

export interface Resource {
  id: string;
  name: string;
  type: string;
  quantity: number;
  available_quantity: number;
  unit: string | null;
  location: string | null;
  city: string | null;
  state: string | null;
  latitude: number | null;
  longitude: number | null;
  status: "AVAILABLE" | "DEPLOYED" | "MAINTENANCE" | "INACTIVE";
  created_at: string;
  updated_at: string;
}

export interface ResourceCreate {
  name: string;
  type: string;
  quantity: number;
  available_quantity: number;
  unit?: string;
  location?: string;
  city?: string;
  state?: string;
  latitude?: number;
  longitude?: number;
  status?: "AVAILABLE" | "DEPLOYED" | "MAINTENANCE" | "INACTIVE";
}

export function getResources(params?: { skip?: number; limit?: number; search?: string; type?: string }) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.search) qs.set("search", params.search);
  if (params?.type) qs.set("type", params.type);
  const q = qs.toString();
  return api.get<ListResponse<Resource>>(`/api/resources${q ? `?${q}` : ""}`);
}

export function getResource(id: string) {
  return api.get<Resource>(`/api/resources/${id}`);
}

export function createResource(data: ResourceCreate) {
  return api.post<Resource>("/api/resources", data);
}

export function updateResource(id: string, data: Partial<ResourceCreate>) {
  return api.put<Resource>(`/api/resources/${id}`, data);
}

export function deleteResource(id: string) {
  return api.delete<void>(`/api/resources/${id}`);
}

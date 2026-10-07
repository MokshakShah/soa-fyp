import { api } from "./client";
import type { ListResponse } from "./hospitals";

export interface PoliceStation {
  id: string;
  name: string;
  station_code: string | null;
  phone: string;
  emergency_phone: string | null;
  email: string | null;
  address: string | null;
  city: string;
  state: string | null;
  latitude: number | null;
  longitude: number | null;
  status: "ACTIVE" | "INACTIVE";
  created_at: string;
  updated_at: string;
}

export interface PoliceStationCreate {
  name: string;
  station_code?: string;
  phone: string;
  emergency_phone?: string;
  email?: string;
  address?: string;
  city: string;
  state?: string;
  latitude?: number;
  longitude?: number;
  status?: "ACTIVE" | "INACTIVE";
}

export function getPoliceStations(params?: { skip?: number; limit?: number; search?: string }) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.search) qs.set("search", params.search);
  const q = qs.toString();
  return api.get<ListResponse<PoliceStation>>(`/api/police-stations${q ? `?${q}` : ""}`);
}

export function getPoliceStation(id: string) {
  return api.get<PoliceStation>(`/api/police-stations/${id}`);
}

export function createPoliceStation(data: PoliceStationCreate) {
  return api.post<PoliceStation>("/api/police-stations", data);
}

export function updatePoliceStation(id: string, data: Partial<PoliceStationCreate>) {
  return api.put<PoliceStation>(`/api/police-stations/${id}`, data);
}

export function deletePoliceStation(id: string) {
  return api.delete<void>(`/api/police-stations/${id}`);
}

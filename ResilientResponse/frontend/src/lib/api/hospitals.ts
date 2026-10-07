import { api } from "./client";

export interface Hospital {
  id: string;
  name: string;
  registration_number: string | null;
  phone: string;
  emergency_phone: string | null;
  email: string | null;
  address: string | null;
  city: string;
  state: string | null;
  latitude: number | null;
  longitude: number | null;
  emergency_capacity: number | null;
  available_beds: number | null;
  icu_beds: number | null;
  status: "ACTIVE" | "INACTIVE";
  created_at: string;
  updated_at: string;
}

export interface HospitalCreate {
  name: string;
  registration_number?: string;
  phone: string;
  emergency_phone?: string;
  email?: string;
  address?: string;
  city: string;
  state?: string;
  latitude?: number;
  longitude?: number;
  emergency_capacity?: number;
  available_beds?: number;
  icu_beds?: number;
  status?: "ACTIVE" | "INACTIVE";
}

export interface ListResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export function getHospitals(params?: { skip?: number; limit?: number; search?: string }) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.search) qs.set("search", params.search);
  const q = qs.toString();
  return api.get<ListResponse<Hospital>>(`/api/hospitals${q ? `?${q}` : ""}`);
}

export function getHospital(id: string) {
  return api.get<Hospital>(`/api/hospitals/${id}`);
}

export function createHospital(data: HospitalCreate) {
  return api.post<Hospital>("/api/hospitals", data);
}

export function updateHospital(id: string, data: Partial<HospitalCreate>) {
  return api.put<Hospital>(`/api/hospitals/${id}`, data);
}

export function deleteHospital(id: string) {
  return api.delete<void>(`/api/hospitals/${id}`);
}

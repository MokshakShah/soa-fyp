import { api } from "./client";

export interface RouteRecord {
  id: string;
  incident_id: string | null;
  workflow_id: string | null;
  origin_lat: number;
  origin_lon: number;
  destination_lat: number;
  destination_lon: number;
  distance_km: number | null;
  estimated_travel_minutes: number | null;
  status: "CALCULATED" | "PROVIDER_UNAVAILABLE" | "INVALID_INPUT";
  provider: string;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export function getRoutes(params?: {
  skip?: number;
  limit?: number;
  incident_id?: string;
  workflow_id?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.incident_id) qs.set("incident_id", params.incident_id);
  if (params?.workflow_id) qs.set("workflow_id", params.workflow_id);
  const q = qs.toString();
  return api.get<{ items: RouteRecord[]; total: number }>(`/api/routes${q ? `?${q}` : ""}`);
}

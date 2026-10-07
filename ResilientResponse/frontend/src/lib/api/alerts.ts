import { api } from "./client";
import type { ListResponse } from "./hospitals";

export interface Alert {
  id: string;
  external_id: string | null;
  source: string;
  title: string;
  description: string | null;
  disaster_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  city: string | null;
  latitude: number | null;
  longitude: number | null;
  location_name: string | null;
  affected_area: string | null;
  issued_at: string | null;
  expires_at: string | null;
  source_url: string | null;
  status: "NEW" | "PROCESSING" | "PROCESSED" | "FAILED" | "EXPIRED" | "ACTIVE" | "CANCELLED";
  created_at: string;
  updated_at: string;
}

export interface TriggerWorkflowResult {
  id: string;
  status: string;
  workflow_type: string;
  events?: Array<{
    action: string;
    status: string;
    result?: { no_nearby_places?: boolean; message?: string } | null;
  }>;
}

export interface Incident {
  id: string;
  alert_id: string | null;
  title: string;
  description: string | null;
  disaster_type: string;
  severity: string;
  location_name: string | null;
  latitude: number | null;
  longitude: number | null;
  status: "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface FetchResult {
  source: string;
  fetched: number;
  created: number;
  updated: number;
  failed: number;
  errors: string[];
}

export function getAlerts(params?: {
  skip?: number;
  limit?: number;
  search?: string;
  source?: string;
  severity?: string;
  status?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.search) qs.set("search", params.search);
  if (params?.source) qs.set("source", params.source);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.status) qs.set("status", params.status);
  const q = qs.toString();
  return api.get<ListResponse<Alert>>(`/api/alerts${q ? `?${q}` : ""}`);
}

export function getAlert(id: string) {
  return api.get<Alert>(`/api/alerts/${id}`);
}

export function getIncidents(params?: { skip?: number; limit?: number }) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return api.get<ListResponse<Incident>>(`/api/incidents${q ? `?${q}` : ""}`);
}

export function createDemoAlert(data: {
  title: string;
  disaster_type: string;
  severity?: string;
  location_name?: string;
  description?: string;
}) {
  return api.post<Alert>("/api/alerts/demo", data);
}

export function fetchAlerts(source?: string) {
  const q = source ? `?source=${encodeURIComponent(source)}` : "";
  return api.post<FetchResult>(`/api/alerts/fetch${q}`, {});
}

export function triggerAlertWorkflow(alert: Alert) {
  return api.post<TriggerWorkflowResult>('/api/workflows/execute', {
    incident_id: `alert-${alert.id}`,
    disaster_type: alert.disaster_type,
    severity: alert.severity,
    latitude: alert.latitude,
    longitude: alert.longitude,
    expand_search: true,
    search_timeout_seconds: 25,
  });
}

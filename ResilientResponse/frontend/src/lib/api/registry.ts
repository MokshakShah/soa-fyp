import { api } from "./client";

export interface RegistryInstance {
  instance_id: string;
  role: "PRIMARY" | "BACKUP";
  status: "UP" | "DOWN" | "DEGRADED" | "RECOVERING" | "UNKNOWN";
  last_health_check: string | null;
  response_time_ms: number | null;
  error: string | null;
  base_url: string;
  version: string | null;
  last_heartbeat: string | null;
  registered_at: string | null;
}

export interface RegistryServiceSummary {
  service_name: string;
  total_instances: number;
  healthy_instances: number;
  status_breakdown: Record<string, number>;
  instances: RegistryInstance[];
}

export interface RegistrySummary {
  total_instances: number;
  healthy_instances: number;
  status_counts: Record<string, number>;
  services: RegistryServiceSummary[];
}

export interface WorkflowSummaryData {
  total: number;
  by_status: Record<string, number>;
  running: number;
  completed: number;
  partial: number;
  failed: number;
}

export interface NotificationSummaryData {
  total: number;
  by_status: Record<string, number>;
  sent: number;
  failed: number;
  pending: number;
}

export interface MonitoringSummary {
  registry: { available: boolean } & Partial<RegistrySummary>;
  workflows: { available: boolean } & Partial<WorkflowSummaryData>;
  notifications: { available: boolean } & Partial<NotificationSummaryData>;
}

export function getRegistrySummary() {
  return api.get<RegistrySummary>("/api/registry/summary");
}

export function getMonitoringSummary() {
  return api.get<MonitoringSummary>("/api/monitoring/summary");
}

import { api } from "./client";

export interface ServiceStatus {
  service_name: string;
  instance_id: string;
  base_url: string;
  status: "UP" | "DOWN" | "DEGRADED" | "RECOVERING" | "UNKNOWN";
  version: string;
  instance_role: "PRIMARY" | "BACKUP";
  response_time_ms: number | null;
  last_checked: string | null;
  last_heartbeat: string | null;
  registered_at: string | null;
  error: string | null;
}

export interface ServicesResponse {
  items: ServiceStatus[];
  total: number;
}

export interface DiscoveryInstance {
  instance_id: string;
  base_url: string;
  status: string;
  instance_role: string;
  version: string;
  response_time_ms: number | null;
  last_heartbeat: string | null;
}

export interface DiscoveryResponse {
  service_name: string;
  instances: DiscoveryInstance[];
  selected: DiscoveryInstance | null;
}

/** Get all registered service instances (registry listing) */
export function getServices() {
  return api.get<ServicesResponse>("/api/services");
}

/** Get full registry listing via Phase 3 registry API */
export function getRegistryServices() {
  return api.get<ServicesResponse>("/api/registry/services");
}

/** Discover healthy instances for a specific service */
export function discoverService(serviceName: string) {
  return api.get<DiscoveryResponse>(`/api/registry/discover/${serviceName}`);
}

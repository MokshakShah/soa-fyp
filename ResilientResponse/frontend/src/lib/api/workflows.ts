import { api } from "./client";

export interface Workflow {
  id: string;
  incident_id: string | null;
  workflow_type: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED" | "WAITING" | "RECOVERING";
  current_step: number;
  total_steps: number;
  failure_reason: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEvent {
  id: string;
  workflow_id: string;
  step_index: number;
  service: string;
  action: string;
  status: "SUCCESS" | "FAILED" | "SKIPPED";
  error: string | null;
  duration_ms: number | null;
  timestamp: string;
}

export interface WorkflowDetail extends Workflow {
  events: WorkflowEvent[];
}

export interface WorkflowSummary {
  total: number;
  by_status: Record<string, number>;
  running: number;
  completed: number;
  partial: number;
  failed: number;
}

export function getWorkflows(params?: { skip?: number; limit?: number; status?: string }) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.status) qs.set("status", params.status);
  const q = qs.toString();
  return api.get<{ items: Workflow[]; total: number }>(`/api/workflows${q ? `?${q}` : ""}`);
}

export function getWorkflow(id: string) {
  return api.get<WorkflowDetail>(`/api/workflows/${id}`);
}

export function getWorkflowEvents(id: string) {
  return api.get<{ workflow_id: string; items: WorkflowEvent[]; total: number }>(
    `/api/workflows/${id}/events`
  );
}

export function getWorkflowSummary() {
  return api.get<WorkflowSummary>("/api/workflows/summary");
}

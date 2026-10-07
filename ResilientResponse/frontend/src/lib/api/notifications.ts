import { api } from "./client";

export interface NotificationRecord {
  id: string;
  incident_id: string | null;
  workflow_id: string | null;
  recipient_type: string;
  recipient_id: string | null;
  recipient_name: string;
  phone_number: string;
  message: string;
  priority: string;
  status: "PENDING" | "SENT" | "FAILED" | "QUEUED" | "SENDING" | "DELIVERED" | "ACKNOWLEDGED";
  provider: string;
  sent_at: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
  reply?: any;
}

export interface NotificationSummary {
  total: number;
  by_status: Record<string, number>;
  sent: number;
  failed: number;
  pending: number;
}

export function getNotifications(params?: {
  skip?: number;
  limit?: number;
  incident_id?: string;
  workflow_id?: string;
  status?: string;
  recipient_type?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.skip != null) qs.set("skip", String(params.skip));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.incident_id) qs.set("incident_id", params.incident_id);
  if (params?.workflow_id) qs.set("workflow_id", params.workflow_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.recipient_type) qs.set("recipient_type", params.recipient_type);
  const q = qs.toString();
  return api.get<{ items: NotificationRecord[]; total: number }>(
    `/api/notifications${q ? `?${q}` : ""}`
  );
}

export function getNotificationSummary() {
  return api.get<NotificationSummary>("/api/notifications/summary");
}

export function sendNotification(data: {
  recipient_type: string;
  recipient_name: string;
  phone_number: string;
  message: string;
  priority: string;
  incident_id?: string;
}) {
  return api.post<NotificationRecord>("/api/notifications/send", data);
}

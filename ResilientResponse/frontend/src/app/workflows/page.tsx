"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import Modal from "@/components/ui/Modal";
import {
  GitBranch, RefreshCw, ChevronRight, CheckCircle2,
  XCircle, AlertTriangle, Clock,
} from "lucide-react";
import {
  getWorkflows, getWorkflow, getWorkflowSummary,
  type Workflow, type WorkflowDetail, type WorkflowSummary,
} from "@/lib/api/workflows";

function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function fmtDuration(startIso: string | null | undefined, endIso: string | null | undefined): string {
  if (!startIso || !endIso) return "—";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (ms < 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`;
}

const STATUS_TABS = [
  { label: "All", value: "" },
  { label: "Running", value: "RUNNING" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Partial", value: "PARTIAL" },
  { label: "Failed", value: "FAILED" },
];

function StepEventIcon({ status }: { status: string }) {
  if (status === "SUCCESS") return <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />;
  if (status === "FAILED")  return <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />;
  return <AlertTriangle className="w-4 h-4 text-gray-500 flex-shrink-0" />;
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<WorkflowSummary | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail modal
  const [selected, setSelected] = useState<WorkflowDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [wfRes, summaryRes] = await Promise.allSettled([
        getWorkflows({ limit: 100, status: statusFilter || undefined }),
        getWorkflowSummary(),
      ]);
      if (wfRes.status === "fulfilled") {
        setWorkflows(wfRes.value.items);
        setTotal(wfRes.value.total);
      } else {
        setError(wfRes.reason instanceof Error ? wfRes.reason.message : "Failed to load workflows");
      }
      if (summaryRes.status === "fulfilled") setSummary(summaryRes.value);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (id: string) => {
    setSelected(null);
    setDetailLoading(true);
    setDetailError(null);
    try {
      const detail = await getWorkflow(id);
      setSelected(detail);
    } catch (e: unknown) {
      setDetailError(e instanceof Error ? e.message : "Failed to load workflow detail");
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <AdminShell title="Workflows" description="Emergency response workflow execution history">

      {/* Summary bar */}
      {summary && (
        <div className="grid grid-cols-2 xl:grid-cols-5 gap-3 mb-5">
          {[
            { label: "Total",     value: summary.total,     color: "text-white"        },
            { label: "Running",   value: summary.running,   color: "text-blue-400"     },
            { label: "Completed", value: summary.completed, color: "text-green-400"    },
            { label: "Partial",   value: summary.partial,   color: "text-amber-400"    },
            { label: "Failed",    value: summary.failed,    color: "text-red-400"      },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Status filter tabs + refresh */}
      <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
        <div className="flex gap-1">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                statusFilter === tab.value
                  ? "bg-red-900 border-red-700 text-red-300"
                  : "bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-200"
              }`}
            >
              {tab.label}
              {tab.value && summary && (
                <span className="ml-1 opacity-60">
                  ({summary.by_status[tab.value] ?? 0})
                </span>
              )}
            </button>
          ))}
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded-lg hover:bg-gray-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? (
          <LoadingSpinner />
        ) : workflows.length === 0 ? (
          <EmptyState
            icon={GitBranch}
            title="No workflows yet"
            description="Workflows appear here when the orchestrator processes a classified incident."
          />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {["ID", "Incident", "Type", "Status", "Progress", "Duration", "Started", ""].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {workflows.map((w) => (
                  <tr key={w.id} className="hover:bg-gray-800/40">
                    <td className="px-4 py-3 text-xs text-gray-500 font-mono">{w.id.slice(-8)}</td>
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                      {w.incident_id ? w.incident_id.slice(-8) : "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{w.workflow_type}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={w.status} />
                      {w.failure_reason && (
                        <p className="text-xs text-red-400 mt-0.5 truncate max-w-[180px]" title={w.failure_reason}>
                          {w.failure_reason}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-800 rounded-full h-1.5 w-20">
                          <div
                            className={`h-1.5 rounded-full ${
                              w.status === "COMPLETED" ? "bg-green-500"
                                : w.status === "PARTIAL" ? "bg-amber-400"
                                : w.status === "FAILED" ? "bg-red-500"
                                : "bg-blue-500"
                            }`}
                            style={{ width: `${w.total_steps > 0 ? (w.current_step / w.total_steps) * 100 : 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">{w.current_step}/{w.total_steps}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {fmtDuration(w.started_at, w.completed_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(w.started_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => openDetail(w.id)}
                        className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded-md"
                        title="View step events"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">
              {total} workflow{total !== 1 ? "s" : ""}
              {statusFilter && ` (filtered: ${statusFilter})`}
            </div>
          </>
        )}
      </div>

      {/* Workflow detail modal */}
      <Modal
        open={detailLoading || !!selected || !!detailError}
        onClose={() => { setSelected(null); setDetailError(null); }}
        title="Workflow Detail"
        size="lg"
      >
        {detailLoading && <LoadingSpinner />}
        {detailError && <ErrorBanner message={detailError} onDismiss={() => setDetailError(null)} />}
        {selected && (
          <div className="space-y-4">
            {/* Header info */}
            <div className="grid grid-cols-2 gap-3">
              {[
                ["Workflow ID",  selected.id],
                ["Incident ID",  selected.incident_id ?? "—"],
                ["Type",         selected.workflow_type],
                ["Status",       selected.status],
                ["Steps",        `${selected.current_step} / ${selected.total_steps}`],
                ["Started",      fmtDate(selected.started_at)],
                ["Completed",    fmtDate(selected.completed_at)],
                ["Duration",     fmtDuration(selected.started_at, selected.completed_at)],
              ].map(([label, value]) => (
                <div key={label} className="bg-gray-800 rounded-lg px-3 py-2">
                  <p className="text-xs text-gray-500 mb-0.5">{label}</p>
                  <p className="text-sm text-white font-medium break-all">{value}</p>
                </div>
              ))}
            </div>

            {selected.failure_reason && (
              <div className="bg-red-950 border border-red-800 rounded-lg px-3 py-2">
                <p className="text-xs text-red-400 mb-0.5">Failure Reason</p>
                <p className="text-sm text-red-300 break-all">{selected.failure_reason}</p>
              </div>
            )}

            {/* Step events */}
            {selected.events && selected.events.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-gray-400 mb-2 uppercase tracking-wide">
                  Step Events ({selected.events.length})
                </h4>
                <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                  {selected.events.map((evt) => (
                    <div
                      key={evt.id}
                      className={`flex items-start gap-3 px-3 py-2 rounded-lg border ${
                        evt.status === "SUCCESS"
                          ? "bg-green-950/30 border-green-900"
                          : evt.status === "FAILED"
                          ? "bg-red-950/30 border-red-900"
                          : "bg-gray-800 border-gray-700"
                      }`}
                    >
                      <StepEventIcon status={evt.status} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-gray-200">
                            Step {evt.step_index} — {evt.action}
                          </span>
                          <span className="text-xs text-gray-500 flex-shrink-0">
                            {evt.duration_ms != null ? `${evt.duration_ms}ms` : ""}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">{evt.service}</p>
                        {evt.error && (
                          <p className="text-xs text-red-400 mt-0.5 break-all">{evt.error}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Clock className="w-3 h-3 text-gray-600" />
                        <span className="text-xs text-gray-600">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selected.events && selected.events.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">No step events recorded yet.</p>
            )}
          </div>
        )}
      </Modal>
    </AdminShell>
  );
}

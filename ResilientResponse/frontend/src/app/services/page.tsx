"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import { Activity, RefreshCw, Clock, ChevronRight } from "lucide-react";
import { getServices, type ServiceStatus } from "@/lib/api/services";
import { getRegistrySummary, type RegistrySummary } from "@/lib/api/registry";

function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "UP"        ? "bg-green-500" :
    status === "RECOVERING"? "bg-yellow-400" :
    status === "DEGRADED"  ? "bg-orange-400" :
    status === "DOWN"      ? "bg-red-500" :
    "bg-gray-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${color} flex-shrink-0`} />;
}

function RoleBadge({ role }: { role: string }) {
  const cls = role === "PRIMARY"
    ? "bg-blue-900 text-blue-300 border-blue-800"
    : "bg-gray-800 text-gray-400 border-gray-700";
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${cls}`}>{role}</span>
  );
}

function HealthBar({ healthy, total }: { healthy: number; total: number }) {
  const pct = total > 0 ? (healthy / total) * 100 : 0;
  const color = pct === 100 ? "bg-green-500" : pct >= 50 ? "bg-yellow-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-800 rounded-full h-1.5 w-16">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400">{healthy}/{total}</span>
    </div>
  );
}

export default function ServicesPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [summary, setSummary] = useState<RegistrySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [selected, setSelected] = useState<ServiceStatus | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [servicesRes, summaryRes] = await Promise.allSettled([
        getServices(),
        getRegistrySummary(),
      ]);
      if (servicesRes.status === "fulfilled") setServices(servicesRes.value.items);
      else setError(servicesRes.reason instanceof Error ? servicesRes.reason.message : "Failed to fetch services");
      if (summaryRes.status === "fulfilled") setSummary(summaryRes.value);
      setLastRefresh(new Date());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(load, 15_000);
    return () => clearInterval(t);
  }, [autoRefresh, load]);

  // Derive counts from live service list
  const upCount        = services.filter((s) => s.status === "UP").length;
  const downCount      = services.filter((s) => s.status === "DOWN").length;
  const recoveringCount = services.filter((s) => s.status === "RECOVERING").length;
  const degradedCount  = services.filter((s) => s.status === "DEGRADED").length;

  // Group by service_name for table display
  const grouped = services.reduce<Record<string, ServiceStatus[]>>((acc, s) => {
    if (!acc[s.service_name]) acc[s.service_name] = [];
    acc[s.service_name].push(s);
    return acc;
  }, {});

  return (
    <AdminShell title="Services" description="Service registry — registered instances and health">

      {/* Summary cards */}
      <div className="flex items-center gap-4 mb-5 flex-wrap">
        {[
          { label: "Online",     count: upCount,         dot: "bg-green-500"  },
          { label: "Degraded",   count: degradedCount,   dot: "bg-orange-400" },
          { label: "Recovering", count: recoveringCount, dot: "bg-yellow-400" },
          { label: "Offline",    count: downCount,       dot: "bg-red-500"    },
          { label: "Total",      count: services.length, dot: "bg-gray-500"   },
        ].map(({ label, count, dot }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />
            <div>
              <p className="text-2xl font-bold text-white">{count}</p>
              <p className="text-xs text-gray-400">{label}</p>
            </div>
          </div>
        ))}

        <div className="ml-auto flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Clock className="w-3 h-3" /> {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              autoRefresh
                ? "bg-green-900 border-green-700 text-green-300"
                : "bg-gray-800 border-gray-700 text-gray-400 hover:text-gray-200"
            }`}
          >
            Auto {autoRefresh ? "ON" : "OFF"}
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg hover:bg-gray-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Per-service health summary from registry (Phase 12) */}
      {summary && summary.services && summary.services.length > 0 && (
        <div className="mb-5 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800 bg-gray-800/30">
            <h3 className="text-sm font-medium text-gray-300">Service Health Overview</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {summary.healthy_instances} of {summary.total_instances} instances healthy
              {" — "}last updated by background health monitor
            </p>
          </div>
          <div className="grid grid-cols-2 xl:grid-cols-3 gap-px bg-gray-800">
            {summary.services.map((svc) => (
              <div key={svc.service_name} className="bg-gray-900 px-4 py-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-white">{svc.service_name}</span>
                  <HealthBar healthy={svc.healthy_instances} total={svc.total_instances} />
                </div>
                <div className="flex flex-wrap gap-2">
                  {svc.instances.map((inst) => (
                    <div key={inst.instance_id} className="flex items-center gap-1.5">
                      <StatusDot status={inst.status} />
                      <RoleBadge role={inst.role} />
                      <span className="text-xs text-gray-500">
                        {inst.response_time_ms != null ? `${inst.response_time_ms}ms` : ""}
                      </span>
                    </div>
                  ))}
                </div>
                {svc.instances.some((i) => i.error) && (
                  <p className="text-xs text-red-400 mt-1 truncate">
                    {svc.instances.find((i) => i.error)?.error}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Full instance table grouped by service */}
      {loading && services.length === 0 ? (
        <LoadingSpinner />
      ) : services.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No services registered"
          description="Services register themselves with the registry on startup. Start the Docker Compose environment to see registered instances."
        />
      ) : (
        <div className="space-y-3">
          {Object.entries(grouped).map(([serviceName, instances]) => {
            const anyDown = instances.some((i) => i.status === "DOWN");
            const allUp   = instances.every((i) => i.status === "UP");
            const groupStatus = allUp ? "UP" : anyDown ? "DOWN" : "DEGRADED";
            return (
              <div key={serviceName} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                {/* Group header */}
                <div className="px-4 py-2.5 bg-gray-800/50 border-b border-gray-800 flex items-center gap-3">
                  <StatusDot status={groupStatus} />
                  <span className="text-sm font-medium text-white">{serviceName}</span>
                  <span className="text-xs text-gray-500">
                    {instances.length} instance{instances.length !== 1 ? "s" : ""}
                  </span>
                  {anyDown && (
                    <span className="text-xs text-red-400 bg-red-950 px-2 py-0.5 rounded-md border border-red-800">
                      degraded
                    </span>
                  )}
                </div>
                {/* Instances */}
                <table className="w-full">
                  <thead className="bg-gray-800/30">
                    <tr>
                      {["Instance", "Role", "Version", "Status", "Response Time", "Last Health Check", ""].map((h) => (
                        <th key={h} className="text-left text-xs font-medium text-gray-500 px-4 py-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800">
                    {[...instances]
                      .sort((a, b) => (a.instance_role === "PRIMARY" ? -1 : 1))
                      .map((inst) => (
                        <tr key={inst.instance_id} className="hover:bg-gray-800/30 transition-colors">
                          <td className="px-4 py-3">
                            <span className="text-sm text-gray-200 font-mono">{inst.instance_id}</span>
                            <p className="text-xs text-gray-500 mt-0.5 truncate max-w-xs">{inst.base_url}</p>
                          </td>
                          <td className="px-4 py-3"><RoleBadge role={inst.instance_role} /></td>
                          <td className="px-4 py-3 text-sm text-gray-400">{inst.version || "—"}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <StatusDot status={inst.status} />
                              <StatusBadge status={inst.status} />
                            </div>
                            {inst.error && (
                              <p className="text-xs text-red-400 mt-0.5 truncate max-w-[200px]" title={inst.error}>
                                {inst.error}
                              </p>
                            )}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-300">
                            {inst.response_time_ms != null ? `${inst.response_time_ms} ms` : "—"}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(inst.last_checked)}</td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => setSelected(inst)}
                              className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded-md"
                              title="View details"
                            >
                              <ChevronRight className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      )}

      {/* Health monitor info */}
      <div className="mt-4 bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
        <Clock className="w-4 h-4 text-gray-500 flex-shrink-0" />
        <p className="text-xs text-gray-500">
          <span className="text-gray-400 font-medium">Phase 12 — </span>
          Health checks run every 15 s. States: UP → DEGRADED (slow) → DOWN (2 failures) → RECOVERING (1 success) → UP (3 successes).
          PRIMARY is preferred for discovery; BACKUP is used automatically when PRIMARY is DOWN or RECOVERING.
        </p>
      </div>

      {/* Instance detail modal */}
      <Modal open={!!selected} onClose={() => setSelected(null)} title="Service Instance Detail" size="md">
        {selected && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {[
                ["Service",        selected.service_name],
                ["Instance ID",    selected.instance_id],
                ["Role",           selected.instance_role],
                ["Version",        selected.version || "—"],
                ["Status",         selected.status],
                ["Response Time",  selected.response_time_ms != null ? `${selected.response_time_ms} ms` : "—"],
                ["Last Checked",   fmtDate(selected.last_checked)],
                ["Last Heartbeat", fmtDate(selected.last_heartbeat)],
                ["Registered At",  fmtDate(selected.registered_at)],
              ].map(([label, value]) => (
                <div key={label} className="bg-gray-800 rounded-lg px-3 py-2">
                  <p className="text-xs text-gray-500 mb-0.5">{label}</p>
                  <p className="text-sm text-white font-medium break-all">{value}</p>
                </div>
              ))}
              <div className="col-span-2 bg-gray-800 rounded-lg px-3 py-2">
                <p className="text-xs text-gray-500 mb-0.5">Base URL</p>
                <p className="text-sm text-white font-mono break-all">{selected.base_url}</p>
              </div>
            </div>
            {selected.error && (
              <div className="bg-red-950 border border-red-800 rounded-lg px-3 py-2">
                <p className="text-xs text-red-400 mb-0.5">Last Error</p>
                <p className="text-sm text-red-300 break-all">{selected.error}</p>
              </div>
            )}
            {selected.status === "DOWN" && (
              <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5">
                <p className="text-xs text-gray-400 font-medium mb-1">Failure Recovery</p>
                <p className="text-xs text-gray-500">
                  Discovery will automatically return the healthy BACKUP instance while this instance is DOWN.
                  It will enter RECOVERING once the health check succeeds.
                </p>
                <code className="text-xs text-yellow-300 font-mono block mt-1 bg-gray-900 px-2 py-1 rounded">
                  docker stop resilientresponse-{selected.instance_id}
                </code>
              </div>
            )}
          </div>
        )}
      </Modal>
    </AdminShell>
  );
}

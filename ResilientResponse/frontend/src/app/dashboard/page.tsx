"use client";

import { useEffect, useState, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import {
  AlertTriangle, Building2, Truck, ShieldAlert, GitBranch,
  Bell, Route, CheckCircle, Activity, RefreshCw, Server,
} from "lucide-react";
import { getAlerts, getIncidents, type Incident, type Alert } from "@/lib/api/alerts";
import { getHospitals } from "@/lib/api/hospitals";
import { getResources } from "@/lib/api/resources";
import { getWorkflows, type Workflow } from "@/lib/api/workflows";
import { getNotifications, type NotificationRecord } from "@/lib/api/notifications";
import { getRoutes, type RouteRecord } from "@/lib/api/routes";
import { getMonitoringSummary, type MonitoringSummary } from "@/lib/api/registry";
import StatusBadge from "@/components/ui/StatusBadge";
import Link from "next/link";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function StatCard({
  label, value, icon: Icon, color, bg, href, loading,
}: {
  label: string; value: string; icon: React.ElementType;
  color: string; bg: string; href: string; loading: boolean;
}) {
  return (
    <Link href={href}>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors cursor-pointer h-full">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-gray-400">{label}</p>
          <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center`}>
            <Icon className={`w-5 h-5 ${color}`} />
          </div>
        </div>
        <p className="text-3xl font-bold text-white">{loading ? "…" : value}</p>
      </div>
    </Link>
  );
}

function MonitoringBar({
  monitoring, loading,
}: {
  monitoring: MonitoringSummary | null; loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-4 mb-5">
        {["Service Health", "Workflows", "Notifications"].map((label) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 animate-pulse">
            <p className="text-xs text-gray-500 mb-2">{label}</p>
            <p className="text-2xl font-bold text-gray-700">…</p>
          </div>
        ))}
      </div>
    );
  }

  const reg = monitoring?.registry;
  const wf = monitoring?.workflows;
  const notif = monitoring?.notifications;

  const healthyPct =
    reg?.available && reg.total_instances
      ? Math.round(((reg.healthy_instances ?? 0) / reg.total_instances) * 100)
      : null;

  const healthColor =
    healthyPct === null ? "text-gray-400"
      : healthyPct === 100 ? "text-green-400"
      : healthyPct >= 50 ? "text-yellow-400"
      : "text-red-400";

  return (
    <div className="grid grid-cols-3 gap-4 mb-5">
      {/* Service health */}
      <Link href="/services">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors cursor-pointer">
          <div className="flex items-center gap-2 mb-3">
            <Server className="w-4 h-4 text-blue-400" />
            <p className="text-xs font-medium text-gray-300">Service Health</p>
            {!reg?.available && <span className="text-xs text-gray-600 ml-auto">unavailable</span>}
          </div>
          {reg?.available ? (
            <>
              <p className={`text-2xl font-bold ${healthColor}`}>
                {reg.healthy_instances ?? 0}
                <span className="text-sm text-gray-500 font-normal"> / {reg.total_instances ?? 0}</span>
              </p>
              <p className="text-xs text-gray-500 mt-1">healthy instances</p>
              <div className="flex gap-2 mt-2 flex-wrap">
                {Object.entries(reg.status_counts ?? {}).map(([st, n]) => (
                  <span key={st} className="text-xs text-gray-400">
                    <span className={
                      st === "UP" ? "text-green-400"
                        : st === "DOWN" ? "text-red-400"
                        : st === "DEGRADED" ? "text-orange-400"
                        : st === "RECOVERING" ? "text-yellow-400"
                        : "text-gray-500"
                    }>{n}</span> {st}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-600">Registry unavailable</p>
          )}
        </div>
      </Link>

      {/* Workflow summary */}
      <Link href="/workflows">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors cursor-pointer">
          <div className="flex items-center gap-2 mb-3">
            <GitBranch className="w-4 h-4 text-orange-400" />
            <p className="text-xs font-medium text-gray-300">Workflows</p>
            {!wf?.available && <span className="text-xs text-gray-600 ml-auto">unavailable</span>}
          </div>
          {wf?.available ? (
            <>
              <p className="text-2xl font-bold text-white">{wf.total ?? 0}</p>
              <p className="text-xs text-gray-500 mt-1">total executions</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2">
                <span className="text-xs"><span className="text-blue-400 font-medium">{wf.running ?? 0}</span> running</span>
                <span className="text-xs"><span className="text-green-400 font-medium">{wf.completed ?? 0}</span> completed</span>
                <span className="text-xs"><span className="text-amber-400 font-medium">{wf.partial ?? 0}</span> partial</span>
                <span className="text-xs"><span className="text-red-400 font-medium">{wf.failed ?? 0}</span> failed</span>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-600">Orchestrator unavailable</p>
          )}
        </div>
      </Link>

      {/* Notification summary */}
      <Link href="/notifications">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors cursor-pointer">
          <div className="flex items-center gap-2 mb-3">
            <Bell className="w-4 h-4 text-yellow-400" />
            <p className="text-xs font-medium text-gray-300">Notifications</p>
            {!notif?.available && <span className="text-xs text-gray-600 ml-auto">unavailable</span>}
          </div>
          {notif?.available ? (
            <>
              <p className="text-2xl font-bold text-white">{notif.total ?? 0}</p>
              <p className="text-xs text-gray-500 mt-1">total dispatched</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2">
                <span className="text-xs"><span className="text-green-400 font-medium">{notif.sent ?? 0}</span> sent</span>
                <span className="text-xs"><span className="text-red-400 font-medium">{notif.failed ?? 0}</span> failed</span>
                <span className="text-xs"><span className="text-yellow-400 font-medium">{notif.pending ?? 0}</span> pending</span>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-600">Notification service unavailable</p>
          )}
        </div>
      </Link>
    </div>
  );
}

export default function DashboardPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [hospitalCount, setHospitalCount] = useState<number | null>(null);
  const [resourceCount, setResourceCount] = useState<number | null>(null);
  const [monitoring, setMonitoring] = useState<MonitoringSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [monitoringLoading, setMonitoringLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const loadMonitoring = useCallback(async () => {
    setMonitoringLoading(true);
    try {
      const m = await getMonitoringSummary();
      setMonitoring(m);
    } catch {
      // monitoring summary failure is non-fatal
    } finally {
      setMonitoringLoading(false);
    }
  }, []);

  const loadActivity = useCallback(async () => {
    setLoading(true);
    await Promise.allSettled([
      getAlerts({ limit: 5 }),
      getIncidents({ limit: 5 }),
      getWorkflows({ limit: 5 }),
      getNotifications({ limit: 5 }),
      getRoutes({ limit: 5 }),
      getHospitals({ limit: 1 }),
      getResources({ limit: 1 }),
    ]).then(([alertsRes, incidentsRes, workflowsRes, notificationsRes, routesRes, hospitalsRes, resourcesRes]) => {
      if (alertsRes.status === "fulfilled") setAlerts(alertsRes.value.items);
      if (incidentsRes.status === "fulfilled") setIncidents(incidentsRes.value.items);
      if (workflowsRes.status === "fulfilled") setWorkflows(workflowsRes.value.items);
      if (notificationsRes.status === "fulfilled") setNotifications(notificationsRes.value.items);
      if (routesRes.status === "fulfilled") setRoutes(routesRes.value.items);
      if (hospitalsRes.status === "fulfilled") setHospitalCount(hospitalsRes.value.total);
      if (resourcesRes.status === "fulfilled") setResourceCount(resourcesRes.value.total);
    });
    setLastRefresh(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    loadActivity();
    loadMonitoring();
  }, [loadActivity, loadMonitoring]);

  // Auto-refresh monitoring bar every 15 s
  useEffect(() => {
    const t = setInterval(loadMonitoring, 15_000);
    return () => clearInterval(t);
  }, [loadMonitoring]);

  const activeIncidents = incidents.filter(
    (i) => i.status === "OPEN" || i.status === "IN_PROGRESS",
  ).length;
  const resolvedToday = incidents.filter((i) => {
    if (!i.resolved_at) return false;
    return new Date(i.resolved_at).toDateString() === new Date().toDateString();
  }).length;
  const activeWorkflows = workflows.filter(
    (w) => w.status === "RUNNING" || w.status === "PENDING",
  ).length;
  const failedNotifications = notifications.filter((n) => n.status === "FAILED").length;

  const stats = [
    { label: "Active Incidents",     value: String(activeIncidents),                              icon: ShieldAlert, color: "text-red-400",    bg: "bg-red-950",    href: "/incidents" },
    { label: "Active Workflows",     value: String(activeWorkflows),                              icon: GitBranch,   color: "text-orange-400", bg: "bg-orange-950", href: "/workflows" },
    { label: "Registered Hospitals", value: hospitalCount != null ? String(hospitalCount) : "—", icon: Building2,   color: "text-blue-400",   bg: "bg-blue-950",   href: "/organizations/hospitals" },
    { label: "Resources Tracked",    value: resourceCount != null ? String(resourceCount) : "—", icon: Truck,       color: "text-green-400",  bg: "bg-green-950",  href: "/resources" },
    { label: "Routes Calculated",    value: String(routes.length),                                icon: Route,       color: "text-cyan-400",   bg: "bg-cyan-950",   href: "/routes" },
    { label: "Notifications Failed", value: String(failedNotifications),                          icon: Bell,        color: "text-yellow-400", bg: "bg-yellow-950", href: "/notifications" },
    { label: "Resolved Today",       value: String(resolvedToday),                                icon: CheckCircle, color: "text-purple-400", bg: "bg-purple-950", href: "/incidents" },
  ];

  return (
    <AdminShell title="Dashboard" description="Emergency coordination overview">
      {/* Operational monitoring summary row */}
      <MonitoringBar monitoring={monitoring} loading={monitoringLoading} />

      {/* Refresh control */}
      <div className="flex items-center justify-end gap-3 mb-5">
        {lastRefresh && (
          <span className="text-xs text-gray-500">
            Updated {lastRefresh.toLocaleTimeString()}
          </span>
        )}
        <button
          onClick={() => { loadActivity(); loadMonitoring(); }}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded-lg hover:bg-gray-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-5 mb-6">
        {stats.map((stat) => (
          <StatCard key={stat.label} loading={loading} {...stat} />
        ))}
      </div>

      {/* Recent activity panels */}
      <div className="grid grid-cols-2 gap-5 mb-5">
        {/* Recent alerts */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" /> Recent Alerts
            </h3>
            <Link href="/alerts" className="text-xs text-red-400 hover:text-red-300">View all</Link>
          </div>
          {loading ? (
            <div className="text-gray-600 text-sm py-8 text-center">Loading…</div>
          ) : alerts.length === 0 ? (
            <div className="text-gray-600 text-sm py-8 text-center">No alerts yet</div>
          ) : (
            <div className="space-y-2">
              {alerts.map((a) => (
                <div key={a.id} className="flex items-start justify-between gap-3 py-2 border-b border-gray-800 last:border-0">
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{a.title}</p>
                    <p className="text-xs text-gray-500">{a.disaster_type} · {a.location_name ?? "Unknown location"}</p>
                  </div>
                  <StatusBadge status={a.severity} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent incidents */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-orange-400" /> Recent Incidents
            </h3>
            <Link href="/incidents" className="text-xs text-red-400 hover:text-red-300">View all</Link>
          </div>
          {loading ? (
            <div className="text-gray-600 text-sm py-8 text-center">Loading…</div>
          ) : incidents.length === 0 ? (
            <div className="text-gray-600 text-sm py-8 text-center">No incidents yet</div>
          ) : (
            <div className="space-y-2">
              {incidents.map((i) => (
                <div key={i.id} className="flex items-start justify-between gap-3 py-2 border-b border-gray-800 last:border-0">
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{i.title}</p>
                    <p className="text-xs text-gray-500">{i.disaster_type} · {fmtDate(i.created_at)}</p>
                  </div>
                  <StatusBadge status={i.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Workflow activity */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-orange-400" /> Workflow Activity
            </h3>
            <Link href="/workflows" className="text-xs text-red-400 hover:text-red-300">View all</Link>
          </div>
          {loading ? (
            <div className="text-gray-600 text-sm py-8 text-center">Loading…</div>
          ) : workflows.length === 0 ? (
            <div className="text-gray-600 text-sm py-8 text-center">No workflow activity</div>
          ) : (
            <div className="space-y-2">
              {workflows.map((w) => (
                <div key={w.id} className="flex items-center justify-between gap-3 py-2 border-b border-gray-800 last:border-0">
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{w.workflow_type}</p>
                    <p className="text-xs text-gray-500">
                      {w.incident_id ? `Incident ${w.incident_id.slice(-8)}` : "Manual trigger"}
                      {" · "}step {w.current_step}/{w.total_steps}
                    </p>
                  </div>
                  <StatusBadge status={w.status} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent notifications */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
              <Bell className="w-4 h-4 text-yellow-400" /> Recent Notifications
            </h3>
            <Link href="/notifications" className="text-xs text-red-400 hover:text-red-300">View all</Link>
          </div>
          {loading ? (
            <div className="text-gray-600 text-sm py-8 text-center">Loading…</div>
          ) : notifications.length === 0 ? (
            <div className="text-gray-600 text-sm py-8 text-center">No notifications recorded</div>
          ) : (
            <div className="space-y-2">
              {notifications.map((n) => (
                <div key={n.id} className="flex items-start justify-between gap-3 py-2 border-b border-gray-800 last:border-0">
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{n.recipient_name}</p>
                    <p className="text-xs text-gray-500">
                      {n.recipient_type}
                      {n.provider ? ` · ${n.provider}` : ""}
                      {" · "}{fmtDate(n.sent_at ?? n.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={n.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AdminShell>
  );
}

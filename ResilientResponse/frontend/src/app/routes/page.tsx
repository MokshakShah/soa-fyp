"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { Map, RefreshCw } from "lucide-react";
import { getRoutes, type RouteRecord } from "@/lib/api/routes";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function RoutesPage() {
  const [routes, setRoutes] = useState<RouteRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await getRoutes({ limit: 100 });
      setRoutes(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load routes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <AdminShell title="Routes" description="Dispatch route calculations and routing outcomes">
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="flex justify-end mb-4">
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded-lg hover:bg-gray-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? <LoadingSpinner /> : routes.length === 0 ? (
          <EmptyState
            icon={Map}
            title="No route calculations"
            description="Route records are created when the orchestrator plans the next travel path for an incident response."
          />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {['Incident', 'Workflow', 'Status', 'Provider', 'Distance', 'ETA', 'Created'].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {routes.map((route) => (
                  <tr key={route.id} className="hover:bg-gray-800/40">
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">{route.incident_id ? route.incident_id.slice(-8) : "—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">{route.workflow_id ? route.workflow_id.slice(-8) : "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={route.status} /></td>
                    <td className="px-4 py-3 text-sm text-gray-300">{route.provider}</td>
                    <td className="px-4 py-3 text-sm text-gray-300">{route.distance_km != null ? `${route.distance_km.toFixed(1)} km` : "—"}</td>
                    <td className="px-4 py-3 text-sm text-gray-300">{route.estimated_travel_minutes != null ? `${route.estimated_travel_minutes.toFixed(0)} min` : "—"}</td>
                    <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(route.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">{total} route{total !== 1 ? "s" : ""}</div>
          </>
        )}
      </div>
    </AdminShell>
  );
}

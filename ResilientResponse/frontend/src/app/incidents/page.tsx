"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { ShieldAlert, RefreshCw } from "lucide-react";
import { getIncidents, type Incident } from "@/lib/api/alerts";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await getIncidents({ limit: 100 });
      setIncidents(res.items); setTotal(res.total);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to load incidents"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <AdminShell title="Incidents" description="Active and resolved emergency incidents">
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
        {loading ? <LoadingSpinner /> : incidents.length === 0 ? (
          <EmptyState icon={ShieldAlert} title="No incidents" description="Incidents will appear here once the alert-to-incident pipeline creates persisted records from backend workflow processing." />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {["Title", "Type", "Severity", "Location", "Status", "Created", "Resolved"].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {incidents.map((i) => (
                  <tr key={i.id} className="hover:bg-gray-800/40">
                    <td className="px-4 py-3">
                      <p className="text-sm text-white font-medium max-w-xs truncate">{i.title}</p>
                      {i.alert_id && <p className="text-xs text-gray-500">Alert: {i.alert_id.slice(-8)}</p>}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{i.disaster_type}</td>
                    <td className="px-4 py-3"><StatusBadge status={i.severity} /></td>
                    <td className="px-4 py-3 text-sm text-gray-300">{i.location_name ?? "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={i.status} /></td>
                    <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(i.created_at)}</td>
                    <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(i.resolved_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">{total} incident{total !== 1 ? "s" : ""}</div>
          </>
        )}
      </div>
    </AdminShell>
  );
}

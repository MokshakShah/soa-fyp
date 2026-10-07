"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import Modal from "@/components/ui/Modal";
import {
  AlertTriangle, Search, FlaskConical, RefreshCw,
  Download, ExternalLink, ChevronRight, X, Info, Send,
} from "lucide-react";
import {
  getAlerts, createDemoAlert, fetchAlerts,
  type Alert, type FetchResult, triggerAlertWorkflow,
} from "@/lib/api/alerts";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function SourceBadge({ source }: { source: string }) {
  const classes =
    source === "DEMO"
      ? "bg-purple-900 text-purple-300 border-purple-800"
      : source === "GDACS"
      ? "bg-blue-900 text-blue-300 border-blue-800"
      : source === "CAP"
      ? "bg-green-900 text-green-300 border-green-800"
      : "bg-gray-800 text-gray-300 border-gray-700";
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${classes}`}>
      {source}
    </span>
  );
}

const DISASTER_TYPES = ["FLOOD","EARTHQUAKE","FIRE","CYCLONE","LANDSLIDE","TSUNAMI","DROUGHT","VOLCANO","STORM","OTHER"];
const SEVERITIES = ["LOW","MEDIUM","HIGH","CRITICAL"];
const SOURCES = ["GDACS","CAP","DEMO"];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");

  // Detail modal
  const [detailAlert, setDetailAlert] = useState<Alert | null>(null);

  // Demo modal
  const [demoOpen, setDemoOpen] = useState(false);
  const [demoForm, setDemoForm] = useState({ title: "", disaster_type: "FLOOD", severity: "MEDIUM", location_name: "", description: "" });
  const [demoError, setDemoError] = useState<string | null>(null);
  const [demoSubmitting, setDemoSubmitting] = useState(false);

  // Fetch modal
  const [fetchOpen, setFetchOpen] = useState(false);
  const [fetchSource, setFetchSource] = useState("GDACS");
  const [fetchLoading, setFetchLoading] = useState(false);
  const [fetchResult, setFetchResult] = useState<FetchResult | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [triggeringAlertId, setTriggeringAlertId] = useState<string | null>(null);
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await getAlerts({
        search: search || undefined,
        source: sourceFilter || undefined,
        severity: severityFilter || undefined,
        limit: 100,
      });
      setAlerts(res.items); setTotal(res.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load alerts");
    } finally { setLoading(false); }
  }, [search, sourceFilter, severityFilter]);

  useEffect(() => { load(); }, [load]);

  // Demo alert
  async function handleDemoSubmit(e: React.FormEvent) {
    e.preventDefault(); setDemoError(null);
    if (!demoForm.title.trim()) { setDemoError("Title is required."); return; }
    setDemoSubmitting(true);
    try {
      await createDemoAlert(demoForm);
      setDemoOpen(false);
      load();
    } catch (e: unknown) {
      setDemoError(e instanceof Error ? e.message : "Failed to create demo alert");
    } finally { setDemoSubmitting(false); }
  }

  // External fetch
  async function handleFetch() {
    setFetchLoading(true); setFetchResult(null); setFetchError(null);
    try {
      const result = await fetchAlerts(fetchSource);
      setFetchResult(result);
      load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Fetch failed";
      setFetchError(msg);
    } finally { setFetchLoading(false); }
  }

  async function handleTrigger(alert: Alert) {
    setTriggeringAlertId(alert.id);
    setTriggerMessage(null);
    setTriggerError(null);
    try {
      if (alert.latitude == null || alert.longitude == null) {
        throw new Error("This alert has no coordinates for nearby response search.");
      }
      const result = await triggerAlertWorkflow(alert);
      const noNearby = result.events?.some(
        (event) => event.result?.no_nearby_places,
      );
      setTriggerMessage(
        noNearby
          ? "No nearby hospitals or police stations found within the 25-second search window."
          : `Response workflow ${result.status.toLowerCase()} for ${alert.title}.`,
      );
    } catch (e: unknown) {
      setTriggerError(e instanceof Error ? e.message : "Failed to trigger response workflow");
    } finally {
      setTriggeringAlertId(null);
    }
  }

  function clearFilters() {
    setSearch(""); setSearchInput(""); setSourceFilter(""); setSeverityFilter("");
  }

  const hasFilters = search || sourceFilter || severityFilter;

  return (
    <AdminShell title="Alerts" description="Disaster alert records">

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
        <div className="flex items-center gap-2 flex-1">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") setSearch(searchInput); }}
              placeholder="Search alerts…"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-600"
            />
          </div>
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
            <option value="">All sources</option>
            {SOURCES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
            <option value="">All severities</option>
            {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <button onClick={() => setSearch(searchInput)} className="px-3 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700">Search</button>
          {hasFilters && <button onClick={clearFilters} className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1"><X className="w-3 h-3" />Clear</button>}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg hover:bg-gray-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
          <button
            onClick={() => { setFetchResult(null); setFetchError(null); setFetchOpen(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-900 hover:bg-blue-800 border border-blue-700 text-blue-200 text-sm font-medium rounded-lg"
          >
            <Download className="w-4 h-4" /> Fetch Alerts
          </button>
          <button
            onClick={() => { setDemoForm({ title: "", disaster_type: "FLOOD", severity: "MEDIUM", location_name: "", description: "" }); setDemoError(null); setDemoOpen(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 text-sm font-medium rounded-lg"
          >
            <FlaskConical className="w-4 h-4 text-purple-400" /> Demo Alert
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      {triggerError && <ErrorBanner message={triggerError} onDismiss={() => setTriggerError(null)} />}
      {triggerMessage && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
          <span>{triggerMessage}</span>
          <button onClick={() => setTriggerMessage(null)} aria-label="Dismiss response message"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? (
          <LoadingSpinner />
        ) : alerts.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="No alerts"
            description={
              hasFilters
                ? "No alerts match your filters. Try clearing them."
                : 'No alerts yet. Use "Fetch Alerts" to pull from GDACS, or "Demo Alert" to create test data.'
            }
          />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {["Source", "Title", "Type", "Severity", "Location", "Issued", "Expires", "Status", ""].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                  {alerts.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-3"><SourceBadge source={a.source} /></td>
                    <td className="px-4 py-3 max-w-xs">
                      <p className="text-sm text-white truncate">{a.title}</p>
                      {a.description && (
                        <p className="text-xs text-gray-500 truncate">{a.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{a.disaster_type}</td>
                    <td className="px-4 py-3"><StatusBadge status={a.severity} /></td>
                    <td className="px-4 py-3 max-w-[150px]">
                      <p className="text-sm text-gray-300 truncate">{a.city ?? a.location_name ?? "—"}</p>
                      {a.city && a.location_name && a.location_name !== a.city && (
                        <p className="text-xs text-gray-500 truncate">{a.location_name}</p>
                      )}
                      {a.latitude != null && a.longitude != null && (
                        <p className="text-[10px] text-gray-500 font-mono">{a.latitude.toFixed(4)}, {a.longitude.toFixed(4)}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(a.issued_at)}</td>
                    <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(a.expires_at)}</td>
                    <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleTrigger(a)}
                          disabled={triggeringAlertId === a.id || a.latitude == null || a.longitude == null}
                          className="p-1.5 text-blue-600 hover:bg-blue-100 rounded-md disabled:cursor-not-allowed disabled:opacity-40"
                          title={a.latitude == null || a.longitude == null ? "No coordinates available" : "Trigger nearby response"}
                        >
                          <Send className={`w-4 h-4 ${triggeringAlertId === a.id ? "animate-pulse" : ""}`} />
                        ["City", detailAlert.city ?? "—"],
                        </button>
                        <button
                          onClick={() => setDetailAlert(a)}
                          className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded-md"
                          title="View alert details"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">
              {total} alert{total !== 1 ? "s" : ""}
              {hasFilters && " (filtered)"}
            </div>
          </>
        )}
      </div>

      {/* Alert Detail Modal */}
      <Modal open={!!detailAlert} onClose={() => setDetailAlert(null)} title="Alert Detail" size="lg">
        {detailAlert && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <SourceBadge source={detailAlert.source} />
              <StatusBadge status={detailAlert.severity} />
              <StatusBadge status={detailAlert.status} />
              {detailAlert.source === "DEMO" && (
                <span className="flex items-center gap-1 text-xs text-purple-300 bg-purple-950 border border-purple-800 px-2 py-0.5 rounded">
                  <Info className="w-3 h-3" /> Development test alert — not a real emergency
                </span>
              )}
            </div>

            <div>
              <p className="text-lg font-semibold text-white">{detailAlert.title}</p>
              {detailAlert.description && (
                <p className="text-sm text-gray-400 mt-1">{detailAlert.description}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              {[
                ["Disaster Type", detailAlert.disaster_type],
                ["Location", detailAlert.location_name ?? "—"],
                ["Affected Area", detailAlert.affected_area ?? "—"],
                ["Coordinates", detailAlert.latitude != null ? `${detailAlert.latitude}, ${detailAlert.longitude}` : "—"],
                ["Issued At", fmtDate(detailAlert.issued_at)],
                ["Expires At", fmtDate(detailAlert.expires_at)],
                ["External ID", detailAlert.external_id ?? "—"],
                ["Recorded", fmtDate(detailAlert.created_at)],
              ].map(([label, value]) => (
                <div key={label} className="bg-gray-800 rounded-lg px-3 py-2">
                  <p className="text-xs text-gray-500 mb-0.5">{label}</p>
                  <p className="text-sm text-white break-all">{value}</p>
                </div>
              ))}
            </div>

            {detailAlert.source_url && (
              <a
                href={detailAlert.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300"
              >
                <ExternalLink className="w-4 h-4" /> View source
              </a>
            )}
          </div>
        )}
      </Modal>

      {/* Fetch Alerts Modal */}
      <Modal open={fetchOpen} onClose={() => setFetchOpen(false)} title="Fetch External Alerts" size="sm">
        <div className="flex items-center gap-2 bg-blue-950 border border-blue-800 rounded-lg px-3 py-2 mb-4">
          <Download className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <p className="text-xs text-blue-300">
            Fetch real disaster alerts from the configured external source. Duplicates are automatically detected and skipped.
          </p>
        </div>

        <div className="mb-4">
          <label className="block text-xs text-gray-400 mb-1">Alert Source</label>
          <select
            value={fetchSource}
            onChange={(e) => setFetchSource(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600"
          >
            <option value="GDACS">GDACS — Global Disaster Alert and Coordination System</option>
            <option value="DEMO">DEMO — Development test alerts</option>
          </select>
        </div>

        {fetchError && <ErrorBanner message={fetchError} onDismiss={() => setFetchError(null)} />}

        {fetchResult && (
          <div className="bg-gray-800 rounded-lg p-3 mb-4 space-y-1">
            <p className="text-xs font-medium text-gray-300">Fetch complete</p>
            <div className="grid grid-cols-2 gap-1 text-xs">
              <span className="text-gray-400">Source:</span><span className="text-white">{fetchResult.source}</span>
              <span className="text-gray-400">Fetched:</span><span className="text-white">{fetchResult.fetched}</span>
              <span className="text-gray-400">Created:</span><span className="text-green-400">{fetchResult.created}</span>
              <span className="text-gray-400">Updated:</span><span className="text-blue-400">{fetchResult.updated}</span>
              <span className="text-gray-400">Failed:</span><span className={fetchResult.failed > 0 ? "text-red-400" : "text-gray-400"}>{fetchResult.failed}</span>
            </div>
            {fetchResult.errors.length > 0 && (
              <div className="mt-2">
                <p className="text-xs text-red-400">Errors:</p>
                {fetchResult.errors.slice(0, 3).map((e, i) => (
                  <p key={i} className="text-xs text-red-300 truncate">{e}</p>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button onClick={() => setFetchOpen(false)} className="px-4 py-2 text-sm text-gray-400 bg-gray-800 rounded-lg hover:bg-gray-700">
            {fetchResult ? "Close" : "Cancel"}
          </button>
          {!fetchResult && (
            <button
              onClick={handleFetch}
              disabled={fetchLoading}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white rounded-lg"
            >
              {fetchLoading ? (
                <><RefreshCw className="w-4 h-4 animate-spin" /> Fetching…</>
              ) : (
                <><Download className="w-4 h-4" /> Fetch Now</>
              )}
            </button>
          )}
        </div>
      </Modal>

      {/* Demo Alert Modal */}
      <Modal open={demoOpen} onClose={() => setDemoOpen(false)} title="Create Demo Alert" size="sm">
        <div className="flex items-center gap-2 bg-purple-950 border border-purple-800 rounded-lg px-3 py-2 mb-4">
          <FlaskConical className="w-4 h-4 text-purple-400 flex-shrink-0" />
          <p className="text-xs text-purple-300">
            Creates a test alert marked source=DEMO. NOT a real government or external alert.
          </p>
        </div>
        <form onSubmit={handleDemoSubmit} className="space-y-3">
          {demoError && <ErrorBanner message={demoError} />}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Title *</label>
            <input
              value={demoForm.title}
              onChange={(e) => setDemoForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600"
              placeholder="[DEMO] Test flood alert"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Disaster Type</label>
              <select value={demoForm.disaster_type} onChange={(e) => setDemoForm((f) => ({ ...f, disaster_type: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
                {DISASTER_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Severity</label>
              <select value={demoForm.severity} onChange={(e) => setDemoForm((f) => ({ ...f, severity: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
                {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Location</label>
            <input value={demoForm.location_name} onChange={(e) => setDemoForm((f) => ({ ...f, location_name: e.target.value }))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="Central City" />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Description</label>
            <textarea value={demoForm.description} onChange={(e) => setDemoForm((f) => ({ ...f, description: e.target.value }))} rows={2} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600 resize-none" />
          </div>
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={() => setDemoOpen(false)} className="px-4 py-2 text-sm text-gray-400 bg-gray-800 rounded-lg">Cancel</button>
            <button type="submit" disabled={demoSubmitting} className="px-4 py-2 text-sm font-medium bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white rounded-lg">
              {demoSubmitting ? "Creating…" : "Create Demo Alert"}
            </button>
          </div>
        </form>
      </Modal>
    </AdminShell>
  );
}

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import Modal from "@/components/ui/Modal";
import { Bell, RefreshCw, ChevronRight, CheckCircle, AlertTriangle, Send } from "lucide-react";
import {
  getNotifications, getNotificationSummary, sendNotification,
  type NotificationRecord, type NotificationSummary,
} from "@/lib/api/notifications";
import { api } from "@/lib/api/client";

function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const STATUS_TABS = [
  { label: "All", value: "" }, { label: "Sent", value: "SENT" },
  { label: "Failed", value: "FAILED" }, { label: "Pending", value: "PENDING" },
];
const RECIPIENT_TABS = [
  { label: "All", value: "" }, { label: "Hospital", value: "HOSPITAL" },
  { label: "Police", value: "POLICE" }, { label: "Response Team", value: "RESPONSE_TEAM" },
];

function extractRequirements(message: string) {
  // Matches both "Prepare 30 emergency bed" and "Prepare 10 MORE emergency bed"
  const beds  = message.match(/Prepare (\d+)(?: MORE)? emergency bed/)?.[1];
  // Matches both "Require 10 police unit" and "Require 5 MORE police unit"
  const units = message.match(/Require (\d+)(?: MORE)? police unit/)?.[1];
  return { beds: beds ? parseInt(beds) : null, units: units ? parseInt(units) : null };
}

function buildResendMessage(original: string, reply: Record<string, any>, reqs: ReturnType<typeof extractRequirements>) {
  let msg = original;
  if (reqs.beds !== null && reply.available_beds !== undefined) {
    const avail = parseInt(reply.available_beds) || 0, gap = Math.max(0, reqs.beds - avail);
    if (gap > 0) msg = msg.replace(/Prepare \d+ emergency bed\(s\)/, `Prepare ${gap} MORE emergency bed(s) (${avail} already confirmed)`);
  }
  if (reqs.units !== null && reply.available_units !== undefined) {
    const avail = parseInt(reply.available_units) || 0, gap = Math.max(0, reqs.units - avail);
    if (gap > 0) msg = msg.replace(/Require \d+ police unit\(s\)/, `Require ${gap} MORE police unit(s) (${avail} already on-site)`);
  }
  return msg;
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [total,     setTotal]     = useState(0);
  const [summary,   setSummary]   = useState<NotificationSummary | null>(null);
  const [statusFilter,    setStatusFilter]    = useState("");
  const [recipientFilter, setRecipientFilter] = useState("");
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);
  const [selected, setSelected] = useState<NotificationRecord | null>(null);
  const [liveDetail,    setLiveDetail]    = useState<NotificationRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [resending,     setResending]     = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [notifRes, summaryRes] = await Promise.allSettled([
        getNotifications({ limit: 100, status: statusFilter || undefined, recipient_type: recipientFilter || undefined }),
        getNotificationSummary(),
      ]);
      if (notifRes.status === "fulfilled") { setNotifications(notifRes.value.items); setTotal(notifRes.value.total); }
      else setError(notifRes.reason instanceof Error ? notifRes.reason.message : "Failed to load notifications");
      if (summaryRes.status === "fulfilled") setSummary(summaryRes.value);
    } finally { setLoading(false); }
  }, [statusFilter, recipientFilter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!selected) {
      setLiveDetail(null); setResendSuccess(false);
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    const fetchDetail = async () => {
      setDetailLoading(true);
      try { const fresh = await api.get<NotificationRecord>(`/api/notifications/${selected.id}`); setLiveDetail(fresh); }
      catch { setLiveDetail(selected); }
      finally { setDetailLoading(false); }
    };
    fetchDetail();
    pollRef.current = setInterval(fetchDetail, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [selected]);

  const detail = liveDetail ?? selected;

  const handleResend = async () => {
    if (!detail) return;
    setResending(true); setResendSuccess(false);
    try {
      const reqs  = extractRequirements(detail.message);
      const reply = detail.reply as Record<string, any> | undefined;
      const newMessage = reply ? buildResendMessage(detail.message, reply, reqs) : detail.message;
      await sendNotification({ recipient_type: detail.recipient_type, recipient_name: detail.recipient_name,
        phone_number: detail.phone_number, priority: detail.priority,
        incident_id: detail.incident_id || undefined, message: newMessage });
      setResendSuccess(true); load();
    } catch (e: any) { alert("Re-send failed: " + e.message); }
    finally { setResending(false); }
  };

  return (
    <AdminShell title="Notifications" description="Outbound notification log">
      {summary && (
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-5">
          {[{ label:"Total",value:summary.total,color:"text-white"},{ label:"Sent",value:summary.sent,color:"text-green-400"},
            { label:"Failed",value:summary.failed,color:"text-red-400"},{ label:"Pending",value:summary.pending,color:"text-yellow-400"}]
            .map(({ label, value, color }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      <div className="flex items-start justify-between mb-4 gap-4 flex-wrap">
        <div className="flex flex-col gap-2">
          <div className="flex gap-1">
            {STATUS_TABS.map((tab) => (
              <button key={tab.value} onClick={() => setStatusFilter(tab.value)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${statusFilter===tab.value?"bg-red-900 border-red-700 text-red-300":"bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-200"}`}>
                {tab.label}{tab.value&&summary&&<span className="ml-1 opacity-60">({summary.by_status[tab.value]??0})</span>}
              </button>
            ))}
          </div>
          <div className="flex gap-1">
            {RECIPIENT_TABS.map((tab) => (
              <button key={tab.value} onClick={() => setRecipientFilter(tab.value)}
                className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${recipientFilter===tab.value?"bg-blue-900 border-blue-700 text-blue-300":"bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-200"}`}>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded-lg hover:bg-gray-700 disabled:opacity-50">
          <RefreshCw className={`w-3.5 h-3.5 ${loading?"animate-spin":""}`} /> Refresh
        </button>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? <LoadingSpinner /> : notifications.length===0 ? (
          <EmptyState icon={Bell} title="No notifications" description="Notifications appear here once the workflow dispatcher creates outbound notification records." />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>{["Incident","Workflow","Recipient","Type","Provider","Status","Reply","Sent",""].map((h)=>(
                  <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {notifications.map((n) => (
                  <tr key={n.id} className="hover:bg-gray-800/40">
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">{n.incident_id?n.incident_id.slice(-8):"—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">{n.workflow_id?n.workflow_id.slice(-8):"—"}</td>
                    <td className="px-4 py-3"><p className="text-sm text-white">{n.recipient_name}</p><p className="text-xs text-gray-500">{n.phone_number}</p></td>
                    <td className="px-4 py-3"><span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded border border-gray-700">{n.recipient_type}</span></td>
                    <td className="px-4 py-3 text-xs text-gray-400">{n.provider||"—"}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={n.status} />
                      {n.failure_reason&&<p className="text-xs text-red-400 mt-0.5 truncate max-w-[160px]" title={n.failure_reason}>{n.failure_reason}</p>}
                    </td>
                    <td className="px-4 py-3">
                      {n.reply?<span className="flex items-center gap-1 text-xs text-gray-300"><CheckCircle className="w-3 h-3"/>Replied</span>
                              :<span className="text-xs text-gray-600">Awaiting</span>}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">{fmtDate(n.sent_at)}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => setSelected(n)} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded-md">
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">
              {total} notification{total!==1?"s":""}
              {statusFilter&&` · filtered by: ${statusFilter}`}{recipientFilter&&` · recipient: ${recipientFilter}`}
            </div>
          </>
        )}
      </div>

      <Modal open={!!selected} onClose={() => setSelected(null)} title="Notification Detail" size="md">
        {selected && (
          <div className="space-y-3">
            {detailLoading&&!liveDetail&&<div className="text-xs text-gray-400 animate-pulse">Loading latest data...</div>}
            <div className="grid grid-cols-2 gap-3">
              {([["Status",detail?.status],["Provider",detail?.provider||"—"],["Recipient",detail?.recipient_name],
                ["Recipient Type",detail?.recipient_type],["Phone",detail?.phone_number],["Priority",detail?.priority],
                ["Incident ID",detail?.incident_id??"—"],["Workflow ID",detail?.workflow_id??"—"],
                ["Sent At",fmtDate(detail?.sent_at)],["Created At",fmtDate(detail?.created_at)]] as [string,string|undefined][])
                .map(([label,value])=>(
                <div key={label} className="bg-gray-800 rounded-lg px-3 py-2">
                  <p className="text-xs text-gray-500 mb-0.5">{label}</p>
                  <p className="text-sm text-white font-medium break-all">{value}</p>
                </div>
              ))}
            </div>
            <div className="bg-gray-800 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-500 mb-1">Message Sent</p>
              <p className="text-sm text-gray-200 whitespace-pre-wrap">{detail?.message}</p>
            </div>
            {detail?.failure_reason&&(
              <div className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2">
                <p className="text-xs text-gray-400 mb-0.5">Failure Reason</p>
                <p className="text-sm text-white break-all">{detail.failure_reason}</p>
              </div>
            )}
            {detail?.reply ? (
              <div className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-3">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle className="w-4 h-4 text-white" />
                  <p className="text-xs text-white font-semibold uppercase tracking-wide">Responder Reply Received</p>
                  {detailLoading&&<span className="text-xs text-gray-500 animate-pulse">· syncing...</span>}
                </div>
                {detail.recipient_type==="HOSPITAL"?(
                  <div className="grid grid-cols-2 gap-2 mb-3">
                    <div className="bg-gray-700 rounded px-3 py-2">
                      <p className="text-xs text-gray-400 mb-1">Available Beds</p>
                      <p className="text-2xl font-bold text-white">{(detail.reply as any).available_beds??"—"}</p>
                    </div>
                    <div className="bg-gray-700 rounded px-3 py-2">
                      <p className="text-xs text-gray-400 mb-1">Available Ambulances</p>
                      <p className="text-2xl font-bold text-white">{(detail.reply as any).available_ambulances??"—"}</p>
                    </div>
                  </div>
                ):(
                  <div className="bg-gray-700 rounded px-3 py-2 mb-3">
                    <p className="text-xs text-gray-400 mb-1">Available Units / Officers</p>
                    <p className="text-2xl font-bold text-white">{(detail.reply as any).available_units??"—"}</p>
                  </div>
                )}
                {(()=>{
                  const reqs=extractRequirements(detail.message);
                  const reply=detail.reply as Record<string,any>;
                  const bedsGap=reqs.beds!==null&&reply.available_beds!==undefined?Math.max(0,reqs.beds-(parseInt(reply.available_beds)||0)):null;
                  const unitsGap=reqs.units!==null&&reply.available_units!==undefined?Math.max(0,reqs.units-(parseInt(reply.available_units)||0)):null;
                  const hasGap=(bedsGap!==null&&bedsGap>0)||(unitsGap!==null&&unitsGap>0);
                  if(!hasGap) return <p className="text-xs text-gray-400">✓ Requirements fully met — no re-send needed.</p>;
                  return (
                    <div className="bg-gray-700 border border-gray-500 rounded px-3 py-2">
                      <div className="flex items-center gap-1 mb-1">
                        <AlertTriangle className="w-3 h-3 text-gray-300"/>
                        <p className="text-xs text-gray-200 font-semibold">Shortfall — re-send recommended</p>
                      </div>
                      {bedsGap!==null&&bedsGap>0&&<p className="text-xs text-gray-300">· Beds: need {reqs.beds}, got {parseInt(reply.available_beds)||0} → <strong className="text-white">{bedsGap} more needed</strong></p>}
                      {unitsGap!==null&&unitsGap>0&&<p className="text-xs text-gray-300">· Police: need {reqs.units}, got {parseInt(reply.available_units)||0} → <strong className="text-white">{unitsGap} more needed</strong></p>}
                    </div>
                  );
                })()}
              </div>
            ):(
              <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 flex items-center gap-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"/>
                <p className="text-xs text-gray-400">Waiting for responder — auto-refreshing every 3s...</p>
              </div>
            )}
            <div className="mt-4 pt-4 border-t border-gray-800 flex justify-end gap-3 items-center flex-wrap">
              {resendSuccess && <span className="text-xs text-gray-300 flex items-center gap-1"><CheckCircle className="w-3 h-3"/>Re-sent!</span>}
              {(() => {
                const reqs    = detail?.message ? extractRequirements(detail.message) : null;
                const reply   = detail?.reply as Record<string,any> | undefined;
                const hasGap  = reply && reqs && (
                  (reqs.beds  !== null && reply.available_beds  !== undefined && Math.max(0, reqs.beds  - (parseInt(reply.available_beds)  || 0)) > 0) ||
                  (reqs.units !== null && reply.available_units !== undefined && Math.max(0, reqs.units - (parseInt(reply.available_units) || 0)) > 0)
                );
                if (hasGap) return (
                  <button onClick={() => { if(confirm("Mark this incident as resolved even with unmet requirements? This closes the loop.")) { setResendSuccess(true); } }}
                    className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm font-medium rounded-lg border border-gray-600">
                    Mark as Done
                  </button>
                );
                return null;
              })()}
              <button onClick={handleResend} disabled={resending}
                className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-gray-100 disabled:opacity-50 text-gray-900 text-sm font-medium rounded-lg">
                <Send className="w-3.5 h-3.5"/>
                {resending ? "Sending..." : detail?.reply ? "Re-send with updated requirements" : "Re-send alert"}
              </button>
            </div>
          </div>
        )}
      </Modal>

    </AdminShell>
  );
}

"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { Shield, Plus, Search, Pencil, Trash2, Phone } from "lucide-react";
import {
  getPoliceStations, createPoliceStation, updatePoliceStation, deletePoliceStation,
  type PoliceStation, type PoliceStationCreate,
} from "@/lib/api/police";

const EMPTY_FORM: PoliceStationCreate = {
  name: "", phone: "", city: "", station_code: "", emergency_phone: "",
  email: "", address: "", state: "", status: "ACTIVE",
};

export default function PoliceStationsPage() {
  const [stations, setStations] = useState<PoliceStation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<PoliceStation | null>(null);
  const [form, setForm] = useState<PoliceStationCreate>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await getPoliceStations({ search: search || undefined, limit: 100 });
      setStations(res.items); setTotal(res.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load police stations");
    } finally { setLoading(false); }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  function openAdd() { setEditTarget(null); setForm(EMPTY_FORM); setFormError(null); setModalOpen(true); }
  function openEdit(s: PoliceStation) {
    setEditTarget(s);
    setForm({ name: s.name, phone: s.phone, city: s.city, station_code: s.station_code ?? "", emergency_phone: s.emergency_phone ?? "", email: s.email ?? "", address: s.address ?? "", state: s.state ?? "", status: s.status });
    setFormError(null); setModalOpen(true);
  }

  function setField<K extends keyof PoliceStationCreate>(k: K, v: PoliceStationCreate[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setFormError(null);
    if (!form.name.trim()) { setFormError("Station name is required."); return; }
    if (!form.phone.trim()) { setFormError("Phone number is required."); return; }
    if (!form.city.trim()) { setFormError("City is required."); return; }
    setSubmitting(true);
    try {
      const payload = { ...form, name: form.name.trim(), phone: form.phone.trim(), city: form.city.trim() };
      if (editTarget) { await updatePoliceStation(editTarget.id, payload); }
      else { await createPoliceStation(payload); }
      setModalOpen(false); load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to save station");
    } finally { setSubmitting(false); }
  }

  async function handleDelete() {
    if (!deleteId) return;
    try { await deletePoliceStation(deleteId); setDeleteId(null); load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to delete station"); setDeleteId(null); }
  }

  return (
    <AdminShell title="Police Stations" description="Registered police stations and contact information">
      <div className="flex items-center justify-between gap-4 mb-5">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") setSearch(searchInput); }} placeholder="Search stations…" className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-600" />
          </div>
          <button onClick={() => setSearch(searchInput)} className="px-3 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700">Search</button>
          {search && <button onClick={() => { setSearch(""); setSearchInput(""); }} className="text-xs text-gray-500 hover:text-gray-300">Clear</button>}
        </div>
        <button onClick={openAdd} className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          <Plus className="w-4 h-4" /> Add Station
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? <LoadingSpinner /> : stations.length === 0 ? (
          <EmptyState icon={Shield} title="No police stations registered" description="Add the first police station to manage emergency contacts." action={<button onClick={openAdd} className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm px-4 py-2 rounded-lg"><Plus className="w-4 h-4" />Add Station</button>} />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {["Station", "Phone", "City", "Status", ""].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {stations.map((s) => (
                  <tr key={s.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-3">
                      <p className="text-sm text-white font-medium">{s.name}</p>
                      {s.station_code && <p className="text-xs text-gray-500">{s.station_code}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-sm text-gray-300">
                        <Phone className="w-3.5 h-3.5 text-gray-500" /> {s.phone}
                      </div>
                      {s.emergency_phone && <p className="text-xs text-gray-500 mt-0.5">Emergency: {s.emergency_phone}</p>}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{s.city}{s.state ? `, ${s.state}` : ""}</td>
                    <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => openEdit(s)} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded-md"><Pencil className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setDeleteId(s.id)} className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-950 rounded-md"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">{total} station{total !== 1 ? "s" : ""}</div>
          </>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? "Edit Police Station" : "Add Police Station"} size="md">
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && <ErrorBanner message={formError} />}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Station Name *</label>
              <input value={form.name} onChange={(e) => setField("name", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="Central Police Station" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Station Code</label>
              <input value={form.station_code ?? ""} onChange={(e) => setField("station_code", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="CPSD-01" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Email</label>
              <input type="email" value={form.email ?? ""} onChange={(e) => setField("email", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Phone *</label>
              <input value={form.phone} onChange={(e) => setField("phone", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Emergency Phone</label>
              <input value={form.emergency_phone ?? ""} onChange={(e) => setField("emergency_phone", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">City *</label>
              <input value={form.city} onChange={(e) => setField("city", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">State</label>
              <input value={form.state ?? ""} onChange={(e) => setField("state", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Address</label>
              <input value={form.address ?? ""} onChange={(e) => setField("address", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Status</label>
              <select value={form.status} onChange={(e) => setField("status", e.target.value as "ACTIVE" | "INACTIVE")} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white bg-gray-800 rounded-lg">Cancel</button>
            <button type="submit" disabled={submitting} className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg">{submitting ? "Saving…" : editTarget ? "Save Changes" : "Add Station"}</button>
          </div>
        </form>
      </Modal>

      <Modal open={!!deleteId} onClose={() => setDeleteId(null)} title="Delete Police Station" size="sm">
        <p className="text-sm text-gray-300 mb-5">This will permanently delete the station record. This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <button onClick={() => setDeleteId(null)} className="px-4 py-2 text-sm text-gray-400 bg-gray-800 rounded-lg hover:bg-gray-700">Cancel</button>
          <button onClick={handleDelete} className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg">Delete</button>
        </div>
      </Modal>
    </AdminShell>
  );
}

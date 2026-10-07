"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { Building2, Plus, Search, Pencil, Trash2, Phone } from "lucide-react";
import {
  getHospitals, createHospital, updateHospital, deleteHospital,
  type Hospital, type HospitalCreate,
} from "@/lib/api/hospitals";

const EMPTY_FORM: HospitalCreate = {
  name: "", phone: "", city: "", registration_number: "", emergency_phone: "",
  email: "", address: "", state: "", emergency_capacity: undefined,
  available_beds: undefined, icu_beds: undefined, status: "ACTIVE",
};

export default function HospitalsPage() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Hospital | null>(null);
  const [form, setForm] = useState<HospitalCreate>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await getHospitals({ search: search || undefined, limit: 100 });
      setHospitals(res.items); setTotal(res.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load hospitals");
    } finally { setLoading(false); }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  function openAdd() { setEditTarget(null); setForm(EMPTY_FORM); setFormError(null); setModalOpen(true); }
  function openEdit(h: Hospital) {
    setEditTarget(h);
    setForm({ name: h.name, phone: h.phone, city: h.city, registration_number: h.registration_number ?? "", emergency_phone: h.emergency_phone ?? "", email: h.email ?? "", address: h.address ?? "", state: h.state ?? "", emergency_capacity: h.emergency_capacity ?? undefined, available_beds: h.available_beds ?? undefined, icu_beds: h.icu_beds ?? undefined, status: h.status });
    setFormError(null); setModalOpen(true);
  }

  function setField<K extends keyof HospitalCreate>(k: K, v: HospitalCreate[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setFormError(null);
    if (!form.name.trim()) { setFormError("Hospital name is required."); return; }
    if (!form.phone.trim()) { setFormError("Phone number is required."); return; }
    if (!form.city.trim()) { setFormError("City is required."); return; }
    setSubmitting(true);
    try {
      const payload = { ...form, name: form.name.trim(), phone: form.phone.trim(), city: form.city.trim() };
      if (editTarget) { await updateHospital(editTarget.id, payload); }
      else { await createHospital(payload); }
      setModalOpen(false); load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to save hospital");
    } finally { setSubmitting(false); }
  }

  async function handleDelete() {
    if (!deleteId) return;
    try { await deleteHospital(deleteId); setDeleteId(null); load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to delete hospital"); setDeleteId(null); }
  }

  return (
    <AdminShell title="Hospitals" description="Registered hospitals and their emergency capacity">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 mb-5">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") setSearch(searchInput); }}
              placeholder="Search hospitals…"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-600"
            />
          </div>
          <button onClick={() => setSearch(searchInput)} className="px-3 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700">Search</button>
          {search && <button onClick={() => { setSearch(""); setSearchInput(""); }} className="text-xs text-gray-500 hover:text-gray-300">Clear</button>}
        </div>
        <button onClick={openAdd} className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          <Plus className="w-4 h-4" /> Add Hospital
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? <LoadingSpinner /> : hospitals.length === 0 ? (
          <EmptyState icon={Building2} title="No hospitals registered" description="Add the first hospital to start managing emergency capacity." action={<button onClick={openAdd} className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm px-4 py-2 rounded-lg"><Plus className="w-4 h-4" />Add Hospital</button>} />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {["Name", "Phone", "City", "Capacity / Beds", "Status", ""].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {hospitals.map((h) => (
                  <tr key={h.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-3">
                      <p className="text-sm text-white font-medium">{h.name}</p>
                      {h.registration_number && <p className="text-xs text-gray-500">{h.registration_number}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-sm text-gray-300">
                        <Phone className="w-3.5 h-3.5 text-gray-500" /> {h.phone}
                      </div>
                      {h.emergency_phone && <p className="text-xs text-gray-500 mt-0.5">Emergency: {h.emergency_phone}</p>}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{h.city}{h.state ? `, ${h.state}` : ""}</td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-white">{h.emergency_capacity ?? "—"} total</p>
                      <p className="text-xs text-gray-500">{h.available_beds ?? "—"} available · {h.icu_beds ?? "—"} ICU</p>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={h.status} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => openEdit(h)} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded-md"><Pencil className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setDeleteId(h.id)} className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-950 rounded-md"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">{total} hospital{total !== 1 ? "s" : ""}</div>
          </>
        )}
      </div>

      {/* Add/Edit Modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? "Edit Hospital" : "Add Hospital"} size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && <ErrorBanner message={formError} />}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Hospital Name *</label>
              <input value={form.name} onChange={(e) => setField("name", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="City General Hospital" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Registration Number</label>
              <input value={form.registration_number ?? ""} onChange={(e) => setField("registration_number", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="HOS-001" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Email</label>
              <input type="email" value={form.email ?? ""} onChange={(e) => setField("email", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="info@hospital.example" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Phone *</label>
              <input value={form.phone} onChange={(e) => setField("phone", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="+1-555-0100" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Emergency Phone</label>
              <input value={form.emergency_phone ?? ""} onChange={(e) => setField("emergency_phone", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="+1-555-0911" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">City *</label>
              <input value={form.city} onChange={(e) => setField("city", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="Central City" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">State</label>
              <input value={form.state ?? ""} onChange={(e) => setField("state", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="CC" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Address</label>
              <input value={form.address ?? ""} onChange={(e) => setField("address", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="123 Medical Drive" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Emergency Capacity</label>
              <input type="number" min="0" value={form.emergency_capacity ?? ""} onChange={(e) => setField("emergency_capacity", e.target.value ? Number(e.target.value) : undefined)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Available Beds</label>
              <input type="number" min="0" value={form.available_beds ?? ""} onChange={(e) => setField("available_beds", e.target.value ? Number(e.target.value) : undefined)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">ICU Beds</label>
              <input type="number" min="0" value={form.icu_beds ?? ""} onChange={(e) => setField("icu_beds", e.target.value ? Number(e.target.value) : undefined)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
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
            <button type="submit" disabled={submitting} className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg">{submitting ? "Saving…" : editTarget ? "Save Changes" : "Add Hospital"}</button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirm */}
      <Modal open={!!deleteId} onClose={() => setDeleteId(null)} title="Delete Hospital" size="sm">
        <p className="text-sm text-gray-300 mb-5">This will permanently delete the hospital record. This action cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <button onClick={() => setDeleteId(null)} className="px-4 py-2 text-sm text-gray-400 bg-gray-800 rounded-lg hover:bg-gray-700">Cancel</button>
          <button onClick={handleDelete} className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg">Delete</button>
        </div>
      </Modal>
    </AdminShell>
  );
}

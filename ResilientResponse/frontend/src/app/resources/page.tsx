"use client";

import { useState, useEffect, useCallback } from "react";
import AdminShell from "@/components/layout/AdminShell";
import StatusBadge from "@/components/ui/StatusBadge";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { Truck, Plus, Search, Pencil, Trash2 } from "lucide-react";
import {
  getResources, createResource, updateResource, deleteResource,
  type Resource, type ResourceCreate,
} from "@/lib/api/resources";

const RESOURCE_TYPES = ["AMBULANCE", "RESCUE_VEHICLE", "MEDICAL_KIT", "WATER", "FOOD", "RESCUE_EQUIPMENT", "OTHER"];

const EMPTY_FORM: ResourceCreate = {
  name: "", type: "AMBULANCE", quantity: 0, available_quantity: 0,
  unit: "", location: "", city: "", state: "", status: "AVAILABLE",
};

export default function ResourcesPage() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Resource | null>(null);
  const [form, setForm] = useState<ResourceCreate>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await getResources({ search: search || undefined, type: typeFilter || undefined, limit: 100 });
      setResources(res.items); setTotal(res.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load resources");
    } finally { setLoading(false); }
  }, [search, typeFilter]);

  useEffect(() => { load(); }, [load]);

  function openAdd() { setEditTarget(null); setForm(EMPTY_FORM); setFormError(null); setModalOpen(true); }
  function openEdit(r: Resource) {
    setEditTarget(r);
    setForm({ name: r.name, type: r.type, quantity: r.quantity, available_quantity: r.available_quantity, unit: r.unit ?? "", location: r.location ?? "", city: r.city ?? "", state: r.state ?? "", status: r.status });
    setFormError(null); setModalOpen(true);
  }

  function setField<K extends keyof ResourceCreate>(k: K, v: ResourceCreate[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setFormError(null);
    if (!form.name.trim()) { setFormError("Resource name is required."); return; }
    if (!form.type.trim()) { setFormError("Type is required."); return; }
    if (form.available_quantity > form.quantity) { setFormError("Available quantity cannot exceed total quantity."); return; }
    setSubmitting(true);
    try {
      const payload = { ...form, name: form.name.trim() };
      if (editTarget) { await updateResource(editTarget.id, payload); }
      else { await createResource(payload); }
      setModalOpen(false); load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to save resource");
    } finally { setSubmitting(false); }
  }

  async function handleDelete() {
    if (!deleteId) return;
    try { await deleteResource(deleteId); setDeleteId(null); load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to delete resource"); setDeleteId(null); }
  }

  return (
    <AdminShell title="Resources" description="Emergency resources and availability">
      <div className="flex items-center justify-between gap-4 mb-5">
        <div className="flex items-center gap-2 flex-1">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") setSearch(searchInput); }} placeholder="Search resources…" className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-600" />
          </div>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
            <option value="">All types</option>
            {RESOURCE_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
          <button onClick={() => setSearch(searchInput)} className="px-3 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700">Search</button>
          {(search || typeFilter) && <button onClick={() => { setSearch(""); setSearchInput(""); setTypeFilter(""); }} className="text-xs text-gray-500 hover:text-gray-300">Clear</button>}
        </div>
        <button onClick={openAdd} className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
          <Plus className="w-4 h-4" /> Add Resource
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? <LoadingSpinner /> : resources.length === 0 ? (
          <EmptyState icon={Truck} title="No resources found" description="Add emergency resources to start tracking availability." action={<button onClick={openAdd} className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm px-4 py-2 rounded-lg"><Plus className="w-4 h-4" />Add Resource</button>} />
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {["Name", "Type", "Quantity", "Location", "Status", ""].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-400 px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {resources.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-3 text-sm text-white font-medium">{r.name}</td>
                    <td className="px-4 py-3"><span className="text-xs bg-gray-800 text-gray-300 px-2 py-1 rounded">{r.type.replace(/_/g, " ")}</span></td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-white">{r.available_quantity} / {r.quantity}</p>
                      <p className="text-xs text-gray-500">{r.unit ?? "units"}</p>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{r.city ?? r.location ?? "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => openEdit(r)} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-gray-700 rounded-md"><Pencil className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setDeleteId(r.id)} className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-950 rounded-md"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">{total} resource{total !== 1 ? "s" : ""}</div>
          </>
        )}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editTarget ? "Edit Resource" : "Add Resource"} size="md">
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && <ErrorBanner message={formError} />}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Name *</label>
              <input value={form.name} onChange={(e) => setField("name", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="Ambulance Unit A1" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Type *</label>
              <select value={form.type} onChange={(e) => setField("type", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
                {RESOURCE_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Unit</label>
              <input value={form.unit ?? ""} onChange={(e) => setField("unit", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="vehicles, kits, packs…" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Total Quantity *</label>
              <input type="number" min="0" value={form.quantity} onChange={(e) => setField("quantity", Number(e.target.value))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Available Quantity *</label>
              <input type="number" min="0" value={form.available_quantity} onChange={(e) => setField("available_quantity", Number(e.target.value))} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">City</label>
              <input value={form.city ?? ""} onChange={(e) => setField("city", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Location</label>
              <input value={form.location ?? ""} onChange={(e) => setField("location", e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600" placeholder="Central Fire Station" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Status</label>
              <select value={form.status} onChange={(e) => setField("status", e.target.value as ResourceCreate["status"])} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-600">
                <option value="AVAILABLE">Available</option>
                <option value="DEPLOYED">Deployed</option>
                <option value="MAINTENANCE">Maintenance</option>
                <option value="INACTIVE">Inactive</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white bg-gray-800 rounded-lg">Cancel</button>
            <button type="submit" disabled={submitting} className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg">{submitting ? "Saving…" : editTarget ? "Save Changes" : "Add Resource"}</button>
          </div>
        </form>
      </Modal>

      <Modal open={!!deleteId} onClose={() => setDeleteId(null)} title="Delete Resource" size="sm">
        <p className="text-sm text-gray-300 mb-5">This will permanently delete the resource record. This cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <button onClick={() => setDeleteId(null)} className="px-4 py-2 text-sm text-gray-400 bg-gray-800 rounded-lg hover:bg-gray-700">Cancel</button>
          <button onClick={handleDelete} className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg">Delete</button>
        </div>
      </Modal>
    </AdminShell>
  );
}

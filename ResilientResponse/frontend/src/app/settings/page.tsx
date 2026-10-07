import AdminShell from "@/components/layout/AdminShell";
import { Settings, Database, Server, Shield, Clock } from "lucide-react";

const systemInfo = [
  { label: "Platform", value: "ResilientResponse" },
  { label: "Phase", value: "Phase 12 — Monitoring + Observability" },
  { label: "Frontend", value: "Next.js 14 + TypeScript + Tailwind CSS" },
  { label: "Backend", value: "Python 3.13 + FastAPI 0.111" },
  { label: "Database", value: "MongoDB 7.0" },
  { label: "Admin Role", value: "ADMIN (single role)" },
];

export default function SettingsPage() {
  return (
    <AdminShell title="Settings" description="Platform configuration and system information">
      <div className="max-w-2xl space-y-5">

        {/* System Info */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-4 h-4 text-gray-400" />
            <h3 className="text-sm font-medium text-gray-300">System Information</h3>
          </div>
          <div className="space-y-2">
            {systemInfo.map((item) => (
              <div key={item.label} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                <span className="text-sm text-gray-400">{item.label}</span>
                <span className="text-sm text-white font-medium">{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Auth Info */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-gray-400" />
            <h3 className="text-sm font-medium text-gray-300">Authentication</h3>
          </div>
          <div className="space-y-2 text-sm text-gray-400">
            <p>Authentication uses JWT tokens with configurable expiry.</p>
            <p>Passwords are hashed with bcrypt. The JWT secret is configured via the <code className="bg-gray-800 px-1.5 py-0.5 rounded text-gray-300 text-xs">JWT_SECRET</code> environment variable.</p>
            <p className="text-yellow-400 text-xs mt-3 bg-yellow-950 border border-yellow-900 rounded-lg px-3 py-2">
              ⚠ Change the default JWT secret and admin credentials before any production deployment.
            </p>
          </div>
        </div>

        {/* DB Info */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-4 h-4 text-gray-400" />
            <h3 className="text-sm font-medium text-gray-300">Database</h3>
          </div>
          <div className="space-y-1 text-sm text-gray-400">
            <p>MongoDB connection is configured via the <code className="bg-gray-800 px-1.5 py-0.5 rounded text-gray-300 text-xs">MONGO_URI</code> environment variable per service.</p>
            <p className="mt-2">Collections: admins, alerts, incidents, hospitals, police_stations, resources, workflows, workflow_events, notifications, service_registry, service_health</p>
          </div>
        </div>

        {/* Future phases */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-gray-400" />
            <h3 className="text-sm font-medium text-gray-300">Future Configuration</h3>
          </div>
          <ul className="space-y-1 text-sm text-gray-500">
            <li>• Multi-tenant admin roles and RBAC expansion</li>
            <li>• Additional external alert ingestion sources</li>
            <li>• Notification template management and escalation rules</li>
            <li>• Service registry failover automation and policy tuning</li>
            <li>• Kafka-based event streaming integration</li>
            <li>• Advanced dashboard reporting and export tooling</li>
          </ul>
        </div>
      </div>
    </AdminShell>
  );
}

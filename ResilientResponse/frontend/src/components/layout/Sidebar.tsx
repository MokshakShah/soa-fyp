"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  AlertTriangle,
  Building2,
  Shield as PoliceIcon,
  Truck,
  Map,
  Bell,
  Settings,
  Activity,
  ShieldAlert,
  GitBranch,
} from "lucide-react";
import { Shield } from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Alerts", href: "/alerts", icon: AlertTriangle },
  { label: "Incidents", href: "/incidents", icon: ShieldAlert },
  { label: "Hospitals", href: "/organizations/hospitals", icon: Building2 },
  { label: "Police Stations", href: "/organizations/police", icon: PoliceIcon },
  { label: "Resources", href: "/resources", icon: Truck },
  { label: "Workflows", href: "/workflows", icon: GitBranch },
  { label: "Notifications", href: "/notifications", icon: Bell },
  { label: "Routes", href: "/routes", icon: Map },
  { label: "Services", href: "/services", icon: Activity },
  { label: "Settings", href: "/settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 min-h-screen bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0 shadow-[4px_0_18px_rgba(30,64,90,0.04)]">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <Shield className="w-7 h-7 text-red-500" />
          <div>
            <p className="text-sm font-bold text-white leading-tight">
              ResilientResponse
            </p>
            <p className="text-xs text-gray-400">Admin Console</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-red-600 text-white shadow-sm"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-500">v1.0.0 — Admin Console</p>
      </div>
    </aside>
  );
}

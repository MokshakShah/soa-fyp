"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { logout } from "@/lib/api/auth";

interface TopBarProps {
  title: string;
  description?: string;
}

export default function TopBar({ title, description }: TopBarProps) {
  const { admin, signOut } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    signOut();
    router.replace("/login");
  }

  return (
    <header className="h-16 border-b border-gray-800 bg-gray-900 px-8 flex items-center justify-between flex-shrink-0 shadow-[0_1px_12px_rgba(30,64,90,0.05)]">
      <div>
        <h1 className="text-lg font-semibold text-white">{title}</h1>
        {description && (
          <p className="text-xs text-gray-400">{description}</p>
        )}
      </div>
      <div className="flex items-center gap-3">
        {admin && (
          <span className="text-xs text-gray-300">{admin.name}</span>
        )}
        <span className="text-xs text-gray-400 bg-gray-800 px-3 py-1 rounded-full">
          Admin
        </span>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
          title="Sign out"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign out
        </button>
      </div>
    </header>
  );
}

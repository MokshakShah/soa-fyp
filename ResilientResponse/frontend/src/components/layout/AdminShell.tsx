import AuthGuard from "@/components/auth/AuthGuard";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

interface AdminShellProps {
  children: React.ReactNode;
  title: string;
  description?: string;
}

export default function AdminShell({
  children,
  title,
  description,
}: AdminShellProps) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen bg-gray-950 text-gray-900">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar title={title} description={description} />
          <main className="flex-1 p-8 overflow-auto">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}

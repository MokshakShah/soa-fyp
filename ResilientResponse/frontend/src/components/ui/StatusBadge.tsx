interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

const colorMap: Record<string, string> = {
  ACTIVE: "bg-green-900 text-green-300 border-green-800",
  AVAILABLE: "bg-green-900 text-green-300 border-green-800",
  UP: "bg-green-900 text-green-300 border-green-800",
  OPEN: "bg-red-900 text-red-300 border-red-800",
  CRITICAL: "bg-red-900 text-red-300 border-red-800",
  HIGH: "bg-orange-900 text-orange-300 border-orange-800",
  MEDIUM: "bg-yellow-900 text-yellow-300 border-yellow-800",
  LOW: "bg-blue-900 text-blue-300 border-blue-800",
  INACTIVE: "bg-gray-800 text-gray-400 border-gray-700",
  DOWN: "bg-red-900 text-red-300 border-red-800",
  DEGRADED: "bg-orange-900 text-orange-300 border-orange-800",
  RECOVERING: "bg-yellow-900 text-yellow-300 border-yellow-800",
  DEPLOYED: "bg-blue-900 text-blue-300 border-blue-800",
  MAINTENANCE: "bg-yellow-900 text-yellow-300 border-yellow-800",
  IN_PROGRESS: "bg-blue-900 text-blue-300 border-blue-800",
  RESOLVED: "bg-green-900 text-green-300 border-green-800",
  CLOSED: "bg-gray-800 text-gray-400 border-gray-700",
  SENT: "bg-green-900 text-green-300 border-green-800",
  FAILED: "bg-red-900 text-red-300 border-red-800",
  PENDING: "bg-yellow-900 text-yellow-300 border-yellow-800",
  RUNNING: "bg-blue-900 text-blue-300 border-blue-800",
  COMPLETED: "bg-green-900 text-green-300 border-green-800",
  PARTIAL: "bg-amber-900 text-amber-300 border-amber-800",
  DEMO: "bg-purple-900 text-purple-300 border-purple-800",
  PROCESSED: "bg-gray-800 text-gray-400 border-gray-700",
  EXPIRED: "bg-gray-800 text-gray-400 border-gray-700",
  UNKNOWN: "bg-gray-800 text-gray-400 border-gray-700",
};

export default function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const classes = colorMap[status] ?? "bg-gray-800 text-gray-400 border-gray-700";
  const sizeClasses = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-2.5 py-1";
  return (
    <span className={`inline-flex items-center rounded-md border font-medium ${sizeClasses} ${classes}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

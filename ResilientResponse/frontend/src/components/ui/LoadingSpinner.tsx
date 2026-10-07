export default function LoadingSpinner({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-16 gap-3">
      <div className="w-5 h-5 border-2 border-gray-700 border-t-red-500 rounded-full animate-spin" />
      <span className="text-sm text-gray-400">{message}</span>
    </div>
  );
}

interface JobStatusBadgeProps {
  status: string;
}

const STATUS_STYLES: Record<string, string> = {
  queued: "bg-gray-100 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  memory_hit: "bg-purple-100 text-purple-700",
};

export default function JobStatusBadge({ status }: JobStatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`badge ${style}`}>
      {status === "running" && (
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse inline-block" />
      )}
      {status}
    </span>
  );
}

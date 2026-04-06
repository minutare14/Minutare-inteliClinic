import { STATUS_COLORS, PRIORITY_COLORS } from "@/lib/constants";

export function Badge({
  children,
  variant = "default",
  className = "",
}: {
  children: React.ReactNode;
  variant?: string;
  className?: string;
}) {
  const colors =
    STATUS_COLORS[variant] ||
    PRIORITY_COLORS[variant] ||
    "bg-gray-100 text-gray-700";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors} ${className}`}
    >
      {children}
    </span>
  );
}

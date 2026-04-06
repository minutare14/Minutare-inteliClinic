import { Card } from "@/components/ui/card";

export function StatCard({
  label,
  value,
  icon,
  color = "text-blue-600",
}: {
  label: string;
  value: string | number;
  icon?: string;
  color?: string;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
        </div>
        {icon && (
          <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center">
            <svg className={`w-5 h-5 ${color}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
            </svg>
          </div>
        )}
      </div>
    </Card>
  );
}

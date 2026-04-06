"use client";

import type { ScheduleSlot, Professional } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/formatters";

export function ScheduleTable({
  slots,
  professionals,
  onCancel,
}: {
  slots: ScheduleSlot[];
  professionals: Professional[];
  onCancel?: (slotId: string) => void;
}) {
  const profMap = new Map(professionals.map((p) => [p.id, p]));

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
          <tr>
            <th className="px-4 py-3 text-left">Profissional</th>
            <th className="px-4 py-3 text-left">Especialidade</th>
            <th className="px-4 py-3 text-left">Inicio</th>
            <th className="px-4 py-3 text-left">Fim</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Tipo</th>
            <th className="px-4 py-3 text-left">Origem</th>
            <th className="px-4 py-3 text-left">Notas</th>
            {onCancel && <th className="px-4 py-3 text-left"></th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {slots.map((s) => {
            const prof = profMap.get(s.professional_id);
            return (
              <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-medium text-gray-900">
                  {prof?.full_name ?? s.professional_id.slice(0, 8)}
                </td>
                <td className="px-4 py-3 text-gray-600">{prof?.specialty ?? "—"}</td>
                <td className="px-4 py-3 text-gray-600 text-xs">{formatDateTime(s.start_at)}</td>
                <td className="px-4 py-3 text-gray-600 text-xs">{formatDateTime(s.end_at)}</td>
                <td className="px-4 py-3">
                  <Badge variant={s.status}>{s.status}</Badge>
                </td>
                <td className="px-4 py-3 text-gray-500">{s.slot_type}</td>
                <td className="px-4 py-3 text-gray-500">{s.source}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{s.notes || "—"}</td>
                {onCancel && (
                  <td className="px-4 py-3">
                    {(s.status === "booked" || s.status === "confirmed") && (
                      <button
                        onClick={() => onCancel(s.id)}
                        className="text-red-600 hover:text-red-800 text-xs font-medium"
                      >
                        Cancelar
                      </button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

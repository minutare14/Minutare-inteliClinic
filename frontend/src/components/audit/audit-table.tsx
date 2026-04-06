import type { AuditEvent } from "@/lib/types";
import { formatDateTime, truncate } from "@/lib/formatters";

export function AuditTable({ events }: { events: AuditEvent[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
          <tr>
            <th className="px-4 py-3 text-left">Ator</th>
            <th className="px-4 py-3 text-left">Acao</th>
            <th className="px-4 py-3 text-left">Recurso</th>
            <th className="px-4 py-3 text-left">Resource ID</th>
            <th className="px-4 py-3 text-left">Payload</th>
            <th className="px-4 py-3 text-left">Data</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {events.map((e) => (
            <tr key={e.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <span className="text-xs font-medium text-gray-500">{e.actor_type}</span>
                <span className="text-gray-400 mx-1">/</span>
                <span className="text-gray-700">{e.actor_id}</span>
              </td>
              <td className="px-4 py-3 font-mono text-xs text-gray-800">{e.action}</td>
              <td className="px-4 py-3 text-gray-600">{e.resource_type}</td>
              <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                {e.resource_id.slice(0, 8)}...
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs max-w-[200px]">
                {e.payload ? truncate(e.payload, 60) : "—"}
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(e.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

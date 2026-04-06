import type { RagDocument } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/formatters";

export function RagDocumentsTable({ documents }: { documents: RagDocument[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
          <tr>
            <th className="px-4 py-3 text-left">Titulo</th>
            <th className="px-4 py-3 text-left">Categoria</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Versao</th>
            <th className="px-4 py-3 text-left">Source</th>
            <th className="px-4 py-3 text-left">Criado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {documents.map((d) => (
            <tr key={d.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 font-medium text-gray-900">{d.title}</td>
              <td className="px-4 py-3">
                <Badge variant="default">{d.category}</Badge>
              </td>
              <td className="px-4 py-3">
                <Badge variant={d.status}>{d.status}</Badge>
              </td>
              <td className="px-4 py-3 text-gray-600">{d.version}</td>
              <td className="px-4 py-3 text-gray-500 text-xs max-w-[200px] truncate">
                {d.source_path || "—"}
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(d.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

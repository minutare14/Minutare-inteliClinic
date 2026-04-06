"use client";

import { useState, useCallback } from "react";
import { useHandoffs } from "@/hooks/use-handoffs";
import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime } from "@/lib/formatters";
import { updateHandoffStatus } from "@/lib/api";
import Link from "next/link";

const STATUS_FILTERS = [
  { value: "", label: "Todos" },
  { value: "open", label: "Abertos" },
  { value: "assigned", label: "Em atendimento" },
  { value: "resolved", label: "Resolvidos" },
];

export default function HandoffsPage() {
  const [statusFilter, setStatusFilter] = useState("open");
  const { data, loading, error, refetch } = useHandoffs(statusFilter || undefined);

  const handleStatusChange = useCallback(
    async (id: string, newStatus: string) => {
      try {
        await updateHandoffStatus(id, newStatus);
        refetch();
      } catch {
        alert("Erro ao atualizar status");
      }
    },
    [refetch]
  );

  return (
    <div>
      <SectionHeader
        title="Handoffs"
        description="Conversas escaladas para atendimento humano"
        action={
          <div className="flex gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                  statusFilter === f.value
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        }
      />

      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && data && data.length === 0 && (
        <EmptyState message="Nenhum handoff encontrado" />
      )}

      {data && data.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Motivo</th>
                <th className="px-4 py-3 text-left">Prioridade</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Contexto</th>
                <th className="px-4 py-3 text-left">Criado</th>
                <th className="px-4 py-3 text-left">Conversa</th>
                <th className="px-4 py-3 text-left">Acoes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((h) => (
                <tr key={h.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-800 max-w-[200px] truncate">
                    {h.reason}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={h.priority}>{h.priority}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={h.status}>{h.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs max-w-[250px] truncate">
                    {h.context_summary || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {formatDateTime(h.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/conversations/${h.conversation_id}`}
                      className="text-blue-600 hover:text-blue-800 text-xs"
                    >
                      Abrir
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      {h.status === "open" && (
                        <button
                          onClick={() => handleStatusChange(h.id, "assigned")}
                          className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                        >
                          Assumir
                        </button>
                      )}
                      {h.status === "assigned" && (
                        <button
                          onClick={() => handleStatusChange(h.id, "resolved")}
                          className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
                        >
                          Resolver
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

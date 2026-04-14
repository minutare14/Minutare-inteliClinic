"use client";

import { useState, useCallback } from "react";
import { useHandoffs } from "@/hooks/use-handoffs";
import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime, formatRelativeTime } from "@/lib/formatters";
import { updateHandoffStatus } from "@/lib/api";
import Link from "next/link";
import type { Handoff } from "@/lib/types";

const STATUS_FILTERS = [
  { value: "", label: "Todos" },
  { value: "open", label: "Abertos" },
  { value: "assigned", label: "Em atendimento" },
  { value: "resolved", label: "Resolvidos" },
];

const REASON_LABELS: Record<string, string> = {
  low_confidence:         "Baixa confiança da IA",
  no_consent:             "Sem consentimento de IA",
  urgent:                 "Urgência detectada",
  explicit_request:       "Pedido explícito do paciente",
  clinical_question:      "Questão clínica",
  unknown_intent:         "Intenção desconhecida",
};

function ContextSummary({ summary }: { summary: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!summary) return <span className="text-gray-400 text-xs">—</span>;

  const isLong = summary.length > 80;
  return (
    <span className="block text-xs text-gray-600 leading-relaxed">
      {expanded || !isLong ? summary : summary.slice(0, 80) + "…"}
      {isLong && (
        <button
          className="ml-1 text-blue-600 hover:text-blue-800"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "menos" : "mais"}
        </button>
      )}
    </span>
  );
}

function HandoffRow({
  h,
  onStatusChange,
}: {
  h: Handoff;
  onStatusChange: (id: string, status: string) => void;
}) {
  return (
    <tr className="hover:bg-gray-50 transition-colors group align-top">
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-gray-800">
            {REASON_LABELS[h.reason] ?? h.reason}
          </p>
          <p className="text-xs text-gray-400 font-mono mt-0.5">{h.reason}</p>
        </div>
      </td>
      <td className="px-4 py-3">
        <Badge variant={h.priority}>{h.priority}</Badge>
      </td>
      <td className="px-4 py-3">
        <Badge variant={h.status}>{h.status}</Badge>
      </td>
      <td className="px-4 py-3 max-w-[280px]">
        <ContextSummary summary={h.context_summary} />
      </td>
      <td className="px-4 py-3 text-gray-500 text-xs">
        <span title={formatDateTime(h.created_at)}>
          {formatRelativeTime(h.created_at)}
        </span>
      </td>
      <td className="px-4 py-3">
        <Link
          href={`/conversations/${h.conversation_id}`}
          className="text-blue-600 hover:text-blue-800 text-xs font-medium"
        >
          Abrir
        </Link>
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {h.status === "open" && (
            <button
              onClick={() => onStatusChange(h.id, "assigned")}
              className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
            >
              Assumir
            </button>
          )}
          {h.status === "assigned" && (
            <button
              onClick={() => onStatusChange(h.id, "resolved")}
              className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
            >
              Resolver
            </button>
          )}
          {(h.status === "open" || h.status === "assigned") && (
            <button
              onClick={() => onStatusChange(h.id, "resolved")}
              className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
            >
              Fechar
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function HandoffsPage() {
  const [statusFilter, setStatusFilter] = useState("open");
  const { data, loading, error, refetch } = useHandoffs(statusFilter || undefined);

  const handleStatusChange = useCallback(
    async (id: string, newStatus: string) => {
      try {
        await updateHandoffStatus(id, newStatus);
        refetch();
      } catch {
        // noop
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
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Motivo</th>
                <th className="px-4 py-3 text-left">Prioridade</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Contexto da IA</th>
                <th className="px-4 py-3 text-left">Criado</th>
                <th className="px-4 py-3 text-left">Conversa</th>
                <th className="px-4 py-3 text-left">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((h) => (
                <HandoffRow key={h.id} h={h} onStatusChange={handleStatusChange} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

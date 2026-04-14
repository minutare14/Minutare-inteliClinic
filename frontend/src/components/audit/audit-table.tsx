"use client";

import { useState } from "react";
import type { AuditEvent } from "@/lib/types";
import { formatDateTime } from "@/lib/formatters";

const ACTOR_COLORS: Record<string, string> = {
  ai:     "bg-purple-100 text-purple-700",
  system: "bg-gray-100 text-gray-700",
  human:  "bg-blue-100 text-blue-700",
  bot:    "bg-indigo-100 text-indigo-700",
};

const ACTION_LABELS: Record<string, string> = {
  "conversation.created":   "Conversa criada",
  "slot.created":           "Slot criado",
  "slot.booked":            "Slot reservado",
  "slot.cancelled":         "Slot cancelado",
  "handoff.created":        "Handoff criado",
  "document.ingested":      "Documento ingerido",
  "document.deleted":       "Documento excluído",
  "pipeline.completed":     "Pipeline concluído",
  "patient.created":        "Paciente criado",
  "patient.updated":        "Paciente atualizado",
};

function ActionLabel({ action }: { action: string }) {
  const label = ACTION_LABELS[action];
  return (
    <span>
      {label ? (
        <span className="text-gray-800">{label}</span>
      ) : (
        <span className="font-mono text-xs text-gray-600">{action}</span>
      )}
    </span>
  );
}

function PayloadCell({ payload }: { payload: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!payload) return <span className="text-gray-400">—</span>;

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(payload);
  } catch {
    // not JSON
  }

  if (parsed && typeof parsed === "object") {
    return (
      <span>
        {expanded ? (
          <span className="block">
            <pre className="text-xs text-gray-700 whitespace-pre-wrap break-all bg-gray-50 rounded p-2 max-w-xs">
              {JSON.stringify(parsed, null, 2)}
            </pre>
            <button
              className="text-xs text-blue-600 mt-1"
              onClick={() => setExpanded(false)}
            >
              Ocultar
            </button>
          </span>
        ) : (
          <button
            className="text-xs text-blue-600 hover:text-blue-800"
            onClick={() => setExpanded(true)}
          >
            Ver dados
          </button>
        )}
      </span>
    );
  }

  return (
    <span className="text-xs text-gray-500 truncate max-w-[160px] block">
      {payload.length > 60 ? payload.slice(0, 60) + "…" : payload}
    </span>
  );
}

export function AuditTable({ events }: { events: AuditEvent[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
          <tr>
            <th className="px-4 py-3 text-left">Ator</th>
            <th className="px-4 py-3 text-left">Ação</th>
            <th className="px-4 py-3 text-left">Recurso</th>
            <th className="px-4 py-3 text-left">ID</th>
            <th className="px-4 py-3 text-left">Dados</th>
            <th className="px-4 py-3 text-left">Data</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {events.map((e) => (
            <tr key={e.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    ACTOR_COLORS[e.actor_type] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {e.actor_type}
                </span>
              </td>
              <td className="px-4 py-3">
                <ActionLabel action={e.action} />
              </td>
              <td className="px-4 py-3 text-gray-600 text-xs capitalize">
                {e.resource_type.replace(/_/g, " ")}
              </td>
              <td className="px-4 py-3 text-gray-400 font-mono text-xs">
                {e.resource_id.slice(0, 8)}
              </td>
              <td className="px-4 py-3">
                <PayloadCell payload={e.payload} />
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(e.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

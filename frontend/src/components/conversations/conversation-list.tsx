"use client";

import Link from "next/link";
import type { Conversation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { INTENT_LABELS } from "@/lib/constants";
import { formatRelativeTime, formatConfidence } from "@/lib/formatters";

const CHANNEL_ICONS: Record<string, string> = {
  telegram: "✈",
  whatsapp: "💬",
  web: "🌐",
  phone: "📞",
};

const STATUS_DOT: Record<string, string> = {
  active: "bg-green-500",
  waiting_input: "bg-yellow-400",
  escalated: "bg-red-500",
  closed: "bg-gray-400",
};

export function ConversationList({
  conversations,
  onClose,
}: {
  conversations: Conversation[];
  onClose?: (id: string) => void;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
          <tr>
            <th className="px-4 py-3 text-left w-6"></th>
            <th className="px-4 py-3 text-left">Canal</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Intenção</th>
            <th className="px-4 py-3 text-left">Confiança</th>
            <th className="px-4 py-3 text-left">Atribuído</th>
            <th className="px-4 py-3 text-left">Última msg</th>
            <th className="px-4 py-3 text-left">Ações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {conversations.map((c) => (
            <tr key={c.id} className="hover:bg-gray-50 transition-colors group">
              {/* Status dot */}
              <td className="pl-4 py-3">
                <div className={`w-2 h-2 rounded-full ${STATUS_DOT[c.status] ?? "bg-gray-300"}`} />
              </td>
              {/* Channel */}
              <td className="px-4 py-3">
                <span className="flex items-center gap-1.5 text-xs text-gray-700">
                  <span>{CHANNEL_ICONS[c.channel] ?? "?"}</span>
                  <span className="capitalize">{c.channel}</span>
                </span>
              </td>
              {/* Status */}
              <td className="px-4 py-3">
                <Badge variant={c.status}>{c.status.replace("_", " ")}</Badge>
              </td>
              {/* Intent */}
              <td className="px-4 py-3 text-gray-700">
                {c.current_intent
                  ? INTENT_LABELS[c.current_intent] || c.current_intent
                  : <span className="text-gray-400">—</span>}
              </td>
              {/* Confidence */}
              <td className="px-4 py-3">
                {c.confidence_score !== null ? (
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          (c.confidence_score ?? 0) >= 0.7
                            ? "bg-green-500"
                            : (c.confidence_score ?? 0) >= 0.5
                            ? "bg-yellow-400"
                            : "bg-red-400"
                        }`}
                        style={{ width: `${((c.confidence_score ?? 0) * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-gray-500">
                      {formatConfidence(c.confidence_score)}
                    </span>
                  </div>
                ) : (
                  <span className="text-gray-400 text-xs">—</span>
                )}
              </td>
              {/* Assignee */}
              <td className="px-4 py-3 text-gray-600 text-xs">{c.human_assignee || "—"}</td>
              {/* Time */}
              <td className="px-4 py-3 text-gray-500 text-xs">
                {formatRelativeTime(c.last_message_at ?? c.created_at)}
              </td>
              {/* Actions */}
              <td className="px-4 py-3">
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Link
                    href={`/conversations/${c.id}`}
                    className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                  >
                    Abrir
                  </Link>
                  {c.patient_id && (
                    <Link
                      href={`/patients/${c.patient_id}`}
                      className="text-gray-400 hover:text-gray-700 text-xs"
                    >
                      Paciente
                    </Link>
                  )}
                  {c.status !== "closed" && onClose && (
                    <button
                      onClick={() => onClose(c.id)}
                      className="text-gray-400 hover:text-red-600 text-xs"
                    >
                      Fechar
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

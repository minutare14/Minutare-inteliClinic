"use client";

import Link from "next/link";
import type { Conversation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { INTENT_LABELS } from "@/lib/constants";
import { formatRelativeTime, formatConfidence } from "@/lib/formatters";

export function ConversationList({ conversations }: { conversations: Conversation[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
          <tr>
            <th className="px-4 py-3 text-left">Canal</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Intencao</th>
            <th className="px-4 py-3 text-left">Confianca</th>
            <th className="px-4 py-3 text-left">Atribuido</th>
            <th className="px-4 py-3 text-left">Ultima msg</th>
            <th className="px-4 py-3 text-left"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {conversations.map((c) => (
            <tr key={c.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <Badge variant={c.channel === "telegram" ? "active" : "default"}>
                  {c.channel}
                </Badge>
              </td>
              <td className="px-4 py-3">
                <Badge variant={c.status}>{c.status}</Badge>
              </td>
              <td className="px-4 py-3 text-gray-700">
                {c.current_intent ? INTENT_LABELS[c.current_intent] || c.current_intent : "—"}
              </td>
              <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                {formatConfidence(c.confidence_score)}
              </td>
              <td className="px-4 py-3 text-gray-600">{c.human_assignee || "—"}</td>
              <td className="px-4 py-3 text-gray-500 text-xs">
                {formatRelativeTime(c.last_message_at)}
              </td>
              <td className="px-4 py-3">
                <Link
                  href={`/conversations/${c.id}`}
                  className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                >
                  Abrir
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

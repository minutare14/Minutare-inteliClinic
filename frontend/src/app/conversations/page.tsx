"use client";

import { useState } from "react";
import { useConversations } from "@/hooks/use-conversations";
import { ConversationList } from "@/components/conversations/conversation-list";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";

const STATUS_FILTERS = [
  { value: "", label: "Todas" },
  { value: "active", label: "Ativas" },
  { value: "waiting_input", label: "Aguardando" },
  { value: "escalated", label: "Escaladas" },
  { value: "closed", label: "Fechadas" },
];

export default function ConversationsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data, loading, error } = useConversations(statusFilter || undefined);

  return (
    <div>
      <SectionHeader
        title="Conversas"
        description="Conversas do Telegram processadas pelo AI Engine"
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
      {data && data.length === 0 && <EmptyState message="Nenhuma conversa encontrada" />}
      {data && data.length > 0 && <ConversationList conversations={data} />}
    </div>
  );
}

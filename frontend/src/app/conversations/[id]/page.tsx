"use client";

import { use } from "react";
import { useConversation, useMessages } from "@/hooks/use-conversations";
import { ConversationDetail } from "@/components/conversations/conversation-detail";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import Link from "next/link";

export default function ConversationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: conversation, loading: loadConv, refetch } = useConversation(id);
  const { data: messages, loading: loadMsg } = useMessages(id);

  if (loadConv || loadMsg) return <LoadingState />;
  if (!conversation) return <p className="text-red-500">Conversa não encontrada.</p>;

  return (
    <div>
      <SectionHeader
        title="Conversa"
        description={`ID: ${id.slice(0, 8)}... · Canal: ${conversation.channel}`}
        action={
          <Link
            href="/conversations"
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Voltar
          </Link>
        }
      />
      <ConversationDetail
        conversation={conversation}
        messages={messages || []}
        onStatusChange={refetch}
      />
    </div>
  );
}

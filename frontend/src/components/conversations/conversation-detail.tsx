"use client";

import { useState } from "react";
import Link from "next/link";
import type { Conversation, Message } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { MessageBubble } from "./message-bubble";
import { INTENT_LABELS } from "@/lib/constants";
import { formatDateTime, formatConfidence } from "@/lib/formatters";
import { updateConversationStatus } from "@/lib/api";

export function ConversationDetail({
  conversation,
  messages,
  onStatusChange,
}: {
  conversation: Conversation;
  messages: Message[];
  onStatusChange?: () => void;
}) {
  const [updating, setUpdating] = useState(false);

  const handleStatusChange = async (newStatus: string) => {
    setUpdating(true);
    try {
      await updateConversationStatus(conversation.id, newStatus);
      onStatusChange?.();
    } catch {
      // noop
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Messages */}
      <div className="lg:col-span-2">
        <Card>
          <CardBody className="max-h-[600px] overflow-y-auto">
            {messages.length === 0 ? (
              <p className="text-gray-400 text-sm text-center py-8">
                Nenhuma mensagem
              </p>
            ) : (
              messages.map((m) => <MessageBubble key={m.id} message={m} />)
            )}
          </CardBody>
        </Card>
      </div>

      {/* Sidebar info */}
      <div className="space-y-4">
        <Card>
          <CardBody>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Detalhes</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Canal</dt>
                <dd><Badge variant="active">{conversation.channel}</Badge></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Status</dt>
                <dd><Badge variant={conversation.status}>{conversation.status.replace("_", " ")}</Badge></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Intenção</dt>
                <dd className="text-gray-700">
                  {conversation.current_intent
                    ? INTENT_LABELS[conversation.current_intent] || conversation.current_intent
                    : "—"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Confiança</dt>
                <dd className="font-mono text-xs">{formatConfidence(conversation.confidence_score)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Atribuído</dt>
                <dd className="text-gray-700">{conversation.human_assignee || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Criado</dt>
                <dd className="text-gray-600 text-xs">{formatDateTime(conversation.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Última msg</dt>
                <dd className="text-gray-600 text-xs">{formatDateTime(conversation.last_message_at)}</dd>
              </div>
            </dl>

            {/* Status actions */}
            <div className="mt-4 pt-3 border-t border-gray-100 flex flex-wrap gap-2">
              {conversation.status !== "closed" && (
                <button
                  onClick={() => handleStatusChange("closed")}
                  disabled={updating}
                  className="px-3 py-1.5 text-xs bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
                >
                  Fechar
                </button>
              )}
              {conversation.status === "closed" && (
                <button
                  onClick={() => handleStatusChange("active")}
                  disabled={updating}
                  className="px-3 py-1.5 text-xs bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 disabled:opacity-50"
                >
                  Reabrir
                </button>
              )}
            </div>
          </CardBody>
        </Card>

        {conversation.patient_id && (
          <Card>
            <CardBody>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Paciente</h3>
              <Link
                href={`/patients/${conversation.patient_id}`}
                className="text-blue-600 hover:text-blue-800 text-sm"
              >
                Ver perfil do paciente →
              </Link>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}

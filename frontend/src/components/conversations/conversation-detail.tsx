"use client";

import type { Conversation, Message } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { MessageBubble } from "./message-bubble";
import { INTENT_LABELS } from "@/lib/constants";
import { formatDateTime, formatConfidence } from "@/lib/formatters";

export function ConversationDetail({
  conversation,
  messages,
}: {
  conversation: Conversation;
  messages: Message[];
}) {
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
                <dd><Badge variant={conversation.status}>{conversation.status}</Badge></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Intencao</dt>
                <dd className="text-gray-700">
                  {conversation.current_intent
                    ? INTENT_LABELS[conversation.current_intent] || conversation.current_intent
                    : "—"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Confianca</dt>
                <dd className="font-mono text-xs">{formatConfidence(conversation.confidence_score)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Atribuido</dt>
                <dd className="text-gray-700">{conversation.human_assignee || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Criado</dt>
                <dd className="text-gray-600 text-xs">{formatDateTime(conversation.created_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Ultima msg</dt>
                <dd className="text-gray-600 text-xs">{formatDateTime(conversation.last_message_at)}</dd>
              </div>
            </dl>
          </CardBody>
        </Card>

        {conversation.patient_id && (
          <Card>
            <CardBody>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Paciente</h3>
              <a
                href={`/patients/${conversation.patient_id}`}
                className="text-blue-600 hover:text-blue-800 text-sm"
              >
                Ver paciente
              </a>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}

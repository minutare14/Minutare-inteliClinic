"use client";

import { use, useState } from "react";
import Link from "next/link";
import { usePatient } from "@/hooks/use-patients";
import { PatientDetailCard } from "@/components/patients/patient-detail-card";
import { PatientFormModal } from "@/components/patients/patient-form-modal";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { Badge } from "@/components/ui/badge";
import { useFetch } from "@/hooks/use-fetch";
import { getPatientConversations, getPatientSchedules } from "@/lib/api";
import type { Conversation, ScheduleSlot } from "@/lib/types";
import { formatDateTime, formatRelativeTime } from "@/lib/formatters";

type Tab = "perfil" | "conversas" | "agendamentos";

function ConversationRow({ conv }: { conv: Conversation }) {
  return (
    <Link
      href={`/conversations`}
      className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 rounded-lg transition-colors group"
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-2 h-2 rounded-full flex-shrink-0 bg-blue-400" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">
            {conv.current_intent ?? "Conversa"}
          </p>
          <p className="text-xs text-gray-500">
            Canal: {conv.channel} · {formatRelativeTime(conv.last_message_at ?? conv.created_at)}
          </p>
        </div>
      </div>
      <Badge variant={conv.status}>{conv.status}</Badge>
    </Link>
  );
}

function ScheduleRow({ slot }: { slot: ScheduleSlot }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 rounded-lg">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-2 h-2 rounded-full flex-shrink-0 bg-green-400" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900">
            {formatDateTime(slot.start_at)}
          </p>
          <p className="text-xs text-gray-500 capitalize">
            {slot.slot_type} · via {slot.source}
            {slot.notes ? ` · ${slot.notes}` : ""}
          </p>
        </div>
      </div>
      <Badge variant={slot.status}>{slot.status}</Badge>
    </div>
  );
}

export default function PatientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: patient, loading, refetch } = usePatient(id);
  const [activeTab, setActiveTab] = useState<Tab>("perfil");
  const [showEdit, setShowEdit] = useState(false);

  const { data: conversations, loading: loadingConvs } = useFetch(
    () => getPatientConversations(id),
    [id]
  );
  const { data: schedules, loading: loadingSlots } = useFetch(
    () => getPatientSchedules(id),
    [id]
  );

  if (loading) return <LoadingState />;
  if (!patient) return <p className="text-red-500">Paciente não encontrado.</p>;

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "perfil", label: "Perfil" },
    { id: "conversas", label: "Conversas", count: conversations?.length },
    { id: "agendamentos", label: "Agendamentos", count: schedules?.length },
  ];

  return (
    <div>
      <SectionHeader
        title={patient.full_name}
        description={`ID: ${id.slice(0, 8)}...`}
        action={
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowEdit(true)}
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Editar
            </button>
            <Link
              href="/patients"
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Voltar
            </Link>
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-1.5 px-1.5 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "perfil" && <PatientDetailCard patient={patient} />}

      {activeTab === "conversas" && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {loadingConvs ? (
            <div className="p-8 text-center text-sm text-gray-500">Carregando...</div>
          ) : !conversations?.length ? (
            <div className="p-8 text-center text-sm text-gray-500">
              Nenhuma conversa encontrada para este paciente.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {conversations.map((conv) => (
                <ConversationRow key={conv.id} conv={conv} />
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "agendamentos" && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {loadingSlots ? (
            <div className="p-8 text-center text-sm text-gray-500">Carregando...</div>
          ) : !schedules?.length ? (
            <div className="p-8 text-center text-sm text-gray-500">
              Nenhum agendamento encontrado para este paciente.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {schedules.map((slot) => (
                <ScheduleRow key={slot.id} slot={slot} />
              ))}
            </div>
          )}
        </div>
      )}

      <PatientFormModal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        onSuccess={() => refetch()}
        patient={patient}
      />
    </div>
  );
}

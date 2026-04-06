"use client";

import { useState, useCallback } from "react";
import { useSchedules, useProfessionals } from "@/hooks/use-schedules";
import { ScheduleTable } from "@/components/schedules/schedule-table";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { cancelSlot } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "available", label: "Disponivel" },
  { value: "booked", label: "Agendado" },
  { value: "confirmed", label: "Confirmado" },
  { value: "cancelled", label: "Cancelado" },
  { value: "completed", label: "Concluido" },
];

export default function SchedulesPage() {
  const [profFilter, setProfFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("booked");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data: professionals } = useProfessionals();
  const { data: slots, loading, error, refetch } = useSchedules({
    professional_id: profFilter || undefined,
    status: statusFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const handleCancel = useCallback(
    async (slotId: string) => {
      if (!confirm("Confirmar cancelamento deste slot?")) return;
      try {
        await cancelSlot(slotId);
        refetch();
      } catch (e) {
        alert("Erro ao cancelar slot");
      }
    },
    [refetch]
  );

  return (
    <div>
      <SectionHeader title="Agenda" description="Slots de agendamento" />

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={profFilter}
          onChange={(e) => setProfFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todos profissionais</option>
          {professionals?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.full_name} — {p.specialty}
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="De"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Ate"
        />
      </div>

      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && slots && slots.length === 0 && (
        <EmptyState message="Nenhum slot encontrado com os filtros selecionados" />
      )}
      {slots && slots.length > 0 && (
        <ScheduleTable
          slots={slots}
          professionals={professionals || []}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
}

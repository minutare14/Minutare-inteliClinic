"use client";

import { useFetch } from "@/hooks/use-fetch";
import { getDashboardSummary, getHealth, getHealthDb } from "@/lib/api";
import { StatCard } from "@/components/dashboard/stat-card";
import { SectionHeader } from "@/components/ui/section-header";
import { Card, CardBody } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";

function StatusIndicator({ label, ok }: { label: string; ok: boolean | null }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span
        className={`w-3 h-3 rounded-full ${
          ok === null ? "bg-gray-300" : ok ? "bg-green-500" : "bg-red-500"
        }`}
      />
      <span className="text-sm text-gray-700">{label}</span>
      <span className="text-xs text-gray-400 ml-auto">
        {ok === null ? "verificando..." : ok ? "online" : "offline"}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const { data: summary, loading, error } = useFetch(() => getDashboardSummary());
  const { data: apiHealth } = useFetch(() =>
    getHealth()
      .then(() => true)
      .catch(() => false)
  );
  const { data: dbHealth } = useFetch(() =>
    getHealthDb()
      .then((d) => d.status === "ok")
      .catch(() => false)
  );

  if (loading) return <LoadingState />;
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
          <span className="text-2xl">⚠️</span>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Erro ao carregar dashboard</h3>
        <p className="text-sm text-gray-500 mb-4">{error}</p>
        <p className="text-xs text-gray-400">Verifique se o backend está acessível e o token de acesso é válido.</p>
      </div>
    );
  }

  return (
    <div>
      <SectionHeader title="Dashboard" description="Visao geral do sistema Minutare Med" />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Pacientes"
          value={summary?.total_patients ?? "—"}
          color="text-blue-600"
          icon="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
        />
        <StatCard
          label="Conversas"
          value={summary?.total_conversations ?? "—"}
          color="text-indigo-600"
          icon="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
        />
        <StatCard
          label="Handoffs Abertos"
          value={summary?.total_handoffs_open ?? "—"}
          color={summary?.total_handoffs_open ? "text-orange-600" : "text-green-600"}
          icon="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
        <StatCard
          label="Agendamentos"
          value={summary?.total_slots_booked ?? "—"}
          color="text-emerald-600"
          icon="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardBody>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Status do Sistema</h3>
            <StatusIndicator label="API Backend" ok={apiHealth ?? null} />
            <StatusIndicator label="Banco de Dados" ok={dbHealth ?? null} />
            <StatusIndicator label="Telegram Webhook" ok={apiHealth ?? null} />
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Base de Conhecimento (RAG)</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Documentos</span>
                <span className="font-medium">{summary?.total_rag_documents ?? "—"}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Chunks indexados</span>
                <span className="font-medium">{summary?.total_rag_chunks ?? "—"}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Slots disponiveis</span>
                <span className="font-medium">{summary?.total_slots ?? "—"}</span>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

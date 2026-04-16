"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/use-fetch";
import {
  getCrmLeads,
  getCrmStats,
  getPendingFollowUps,
  getOpenAlerts,
  updateLeadStage,
  completeFollowUp,
  resolveAlert,
} from "@/lib/api";
import type { CrmLead, CrmStats, CrmFollowUp, CrmAlert } from "@/lib/types";
import { SectionHeader } from "@/components/ui/section-header";
import { Card, CardBody } from "@/components/ui/card";

type Tab = "leads" | "followups" | "alerts";

const STAGE_LABELS: Record<string, string> = {
  lead: "Lead",
  patient: "Paciente",
  inactive: "Inativo",
};

const STAGE_COLORS: Record<string, string> = {
  lead: "bg-yellow-100 text-yellow-700",
  patient: "bg-green-100 text-green-700",
  inactive: "bg-gray-100 text-gray-500",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-blue-50 text-blue-600",
  normal: "bg-gray-100 text-gray-600",
  high: "bg-orange-100 text-orange-600",
  urgent: "bg-red-100 text-red-600",
};

function StatsBar({ stats }: { stats: CrmStats }) {
  return (
    <div className="grid grid-cols-5 gap-4 mb-6">
      <Card>
        <CardBody>
          <p className="text-xs text-gray-500 mb-1">Leads</p>
          <p className="text-2xl font-bold text-yellow-600">{stats.stages.lead}</p>
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <p className="text-xs text-gray-500 mb-1">Pacientes</p>
          <p className="text-2xl font-bold text-green-600">{stats.stages.patient}</p>
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <p className="text-xs text-gray-500 mb-1">Inativos</p>
          <p className="text-2xl font-bold text-gray-500">{stats.stages.inactive}</p>
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <p className="text-xs text-gray-500 mb-1">Follow-ups</p>
          <p className="text-2xl font-bold text-blue-600">{stats.pending_followups}</p>
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <p className="text-xs text-gray-500 mb-1">Alertas</p>
          <p className="text-2xl font-bold text-red-500">{stats.open_alerts}</p>
        </CardBody>
      </Card>
    </div>
  );
}

function LeadsTab() {
  const [stageFilter, setStageFilter] = useState<string>("all");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetcher = () => getCrmLeads(stageFilter === "all" ? undefined : stageFilter);
  const { data: leads, loading, error, refetch } = useFetch<CrmLead[]>(fetcher, [stageFilter]);

  const handleStageChange = async (id: string, stage: string) => {
    setUpdatingId(id);
    try {
      await updateLeadStage(id, stage);
      refetch();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Erro ao atualizar estágio");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {["all", "lead", "patient", "inactive"].map((s) => (
          <button
            key={s}
            onClick={() => setStageFilter(s)}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              stageFilter === s
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:border-gray-300"
            }`}
          >
            {s === "all" ? "Todos" : STAGE_LABELS[s]}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-500">Carregando...</p>}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {leads && leads.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-8">Nenhum registro encontrado.</p>
      )}

      {leads && leads.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Nome</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Telefone</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Estágio</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Tags</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Origem</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Alterar estágio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{lead.full_name}</td>
                  <td className="px-4 py-3 text-gray-500">{lead.phone ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STAGE_COLORS[lead.stage] ?? "bg-gray-100 text-gray-500"}`}>
                      {STAGE_LABELS[lead.stage] ?? lead.stage}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {lead.tags.filter(Boolean).map((tag) => (
                        <span key={tag} className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{lead.source ?? "—"}</td>
                  <td className="px-4 py-3">
                    <select
                      value={lead.stage}
                      disabled={updatingId === lead.id}
                      onChange={(e) => handleStageChange(lead.id, e.target.value)}
                      className="text-xs border border-gray-200 rounded px-2 py-1 disabled:opacity-50"
                    >
                      <option value="lead">Lead</option>
                      <option value="patient">Paciente</option>
                      <option value="inactive">Inativo</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FollowUpsTab() {
  const [completing, setCompleting] = useState<string | null>(null);
  const { data: followups, loading, error, refetch } = useFetch<CrmFollowUp[]>(getPendingFollowUps);

  const handleComplete = async (id: string) => {
    setCompleting(id);
    try {
      await completeFollowUp(id);
      refetch();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Erro ao completar follow-up");
    } finally {
      setCompleting(null);
    }
  };

  if (loading) return <p className="text-sm text-gray-500">Carregando...</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!followups?.length) return <p className="text-sm text-gray-400 text-center py-8">Nenhum follow-up pendente.</p>;

  return (
    <div className="space-y-3">
      {followups.map((fu) => (
        <div key={fu.id} className="bg-white rounded-xl border border-gray-200 px-5 py-4 flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">
                {fu.type}
              </span>
              <span className="text-xs text-gray-400">
                {new Date(fu.scheduled_at).toLocaleString("pt-BR")}
              </span>
            </div>
            <p className="text-sm text-gray-600">{fu.notes ?? "Sem observações"}</p>
            <p className="text-xs text-gray-400 mt-1">Paciente: {fu.patient_id.slice(0, 8)}...</p>
          </div>
          <button
            onClick={() => handleComplete(fu.id)}
            disabled={completing === fu.id}
            className="shrink-0 text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {completing === fu.id ? "..." : "Concluir"}
          </button>
        </div>
      ))}
    </div>
  );
}

function AlertsTab() {
  const [resolving, setResolving] = useState<string | null>(null);
  const { data: alerts, loading, error, refetch } = useFetch<CrmAlert[]>(getOpenAlerts);

  const handleResolve = async (id: string) => {
    setResolving(id);
    try {
      await resolveAlert(id);
      refetch();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Erro ao resolver alerta");
    } finally {
      setResolving(null);
    }
  };

  if (loading) return <p className="text-sm text-gray-500">Carregando...</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!alerts?.length) return <p className="text-sm text-gray-400 text-center py-8">Nenhum alerta aberto.</p>;

  return (
    <div className="space-y-3">
      {alerts.map((alert) => (
        <div key={alert.id} className="bg-white rounded-xl border border-gray-200 px-5 py-4 flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${PRIORITY_COLORS[alert.priority] ?? "bg-gray-100 text-gray-600"}`}>
                {alert.priority.toUpperCase()}
              </span>
              <span className="text-xs text-gray-400 font-medium">{alert.type}</span>
              <span className="text-xs text-gray-400">
                {new Date(alert.created_at).toLocaleString("pt-BR")}
              </span>
            </div>
            <p className="text-sm text-gray-800">{alert.message}</p>
          </div>
          <button
            onClick={() => handleResolve(alert.id)}
            disabled={resolving === alert.id}
            className="shrink-0 text-xs bg-gray-600 text-white px-3 py-1.5 rounded-lg hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {resolving === alert.id ? "..." : "Resolver"}
          </button>
        </div>
      ))}
    </div>
  );
}

export default function CrmPage() {
  const [tab, setTab] = useState<Tab>("leads");
  const { data: stats } = useFetch<CrmStats>(getCrmStats);

  const tabs: { id: Tab; label: string }[] = [
    { id: "leads", label: "Leads & Pacientes" },
    { id: "followups", label: "Follow-ups" },
    { id: "alerts", label: "Alertas" },
  ];

  return (
    <div>
      <SectionHeader
        title="CRM"
        description="Ciclo de vida de leads, follow-ups e alertas operacionais"
      />

      {stats && <StatsBar stats={stats} />}

      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "leads" && <LeadsTab />}
      {tab === "followups" && <FollowUpsTab />}
      {tab === "alerts" && <AlertsTab />}
    </div>
  );
}

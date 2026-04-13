"use client";
import { useState } from "react";
import { useFetch } from "@/hooks/use-fetch";
import { getAllProfessionals, deactivateProfessional } from "@/lib/api";
import { Professional } from "@/lib/types";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { ProfessionalFormModal } from "@/components/professionals/professional-form-modal";

export default function ProfessionalsPage() {
  const { data, loading, error, refetch } = useFetch(() => getAllProfessionals());
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Professional | null>(null);
  const [deactivating, setDeactivating] = useState<string | null>(null);

  const handleDeactivate = async (prof: Professional) => {
    if (!confirm(`Desativar ${prof.full_name}? O profissional não aparecerá mais na agenda.`)) return;
    setDeactivating(prof.id);
    try {
      await deactivateProfessional(prof.id);
      refetch();
    } catch (e) {
      alert("Erro ao desativar profissional");
    } finally {
      setDeactivating(null);
    }
  };

  return (
    <div>
      <SectionHeader
        title="Profissionais"
        description={`${data?.length ?? 0} profissionais cadastrados`}
        action={
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Novo Profissional
          </button>
        }
      />

      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm mt-4">{error}</p>}
      {!loading && data?.length === 0 && <EmptyState message="Nenhum profissional cadastrado" />}

      {data && data.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">Nome</th>
                <th className="px-4 py-3 text-left">Especialidade</th>
                <th className="px-4 py-3 text-left">CRM</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Cadastrado em</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {data.map((prof) => (
                <tr key={prof.id} className={`hover:bg-gray-50 transition-colors ${!prof.active ? "opacity-50" : ""}`}>
                  <td className="px-4 py-3 font-medium text-gray-900">{prof.full_name}</td>
                  <td className="px-4 py-3 text-gray-600">{prof.specialty}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{prof.crm}</td>
                  <td className="px-4 py-3">
                    <Badge variant={prof.active ? "green" : "gray"}>{prof.active ? "Ativo" : "Inativo"}</Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{new Date(prof.created_at).toLocaleDateString("pt-BR")}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setEditing(prof)}
                        className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 border border-blue-200 rounded-md hover:bg-blue-50 transition-colors"
                      >
                        Editar
                      </button>
                      {prof.active && (
                        <button
                          onClick={() => handleDeactivate(prof)}
                          disabled={deactivating === prof.id}
                          className="px-3 py-1 text-xs font-medium text-red-600 hover:text-red-800 border border-red-200 rounded-md hover:bg-red-50 disabled:opacity-50 transition-colors"
                        >
                          {deactivating === prof.id ? "..." : "Desativar"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ProfessionalFormModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSuccess={refetch}
      />
      <ProfessionalFormModal
        open={!!editing}
        onClose={() => setEditing(null)}
        onSuccess={refetch}
        professional={editing}
      />
    </div>
  );
}

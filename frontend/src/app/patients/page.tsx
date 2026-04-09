"use client";

import { useState, useMemo } from "react";
import { usePatients } from "@/hooks/use-patients";
import { PatientTable } from "@/components/patients/patient-table";
import { PatientFormModal } from "@/components/patients/patient-form-modal";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";

export default function PatientsPage() {
  const { data, loading, error, refetch } = usePatients();
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const filtered = useMemo(() => {
    if (!data) return [];
    if (!search.trim()) return data;
    const q = search.toLowerCase();
    return data.filter(
      (p) =>
        p.full_name.toLowerCase().includes(q) ||
        (p.cpf && p.cpf.includes(q)) ||
        (p.telegram_user_id && p.telegram_user_id.includes(q))
    );
  }, [data, search]);

  return (
    <div>
      <SectionHeader
        title="Pacientes"
        description={`${data?.length ?? 0} pacientes cadastrados`}
        action={
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Buscar nome, CPF ou Telegram ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md w-72 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={() => setShowCreate(true)}
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Novo Paciente
            </button>
          </div>
        }
      />
      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && filtered.length === 0 && <EmptyState message="Nenhum paciente encontrado" />}
      {filtered.length > 0 && <PatientTable patients={filtered} />}

      <PatientFormModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSuccess={() => refetch()}
      />
    </div>
  );
}

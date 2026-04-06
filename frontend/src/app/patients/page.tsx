"use client";

import { useState, useMemo } from "react";
import { usePatients } from "@/hooks/use-patients";
import { PatientTable } from "@/components/patients/patient-table";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";

export default function PatientsPage() {
  const { data, loading, error } = usePatients();
  const [search, setSearch] = useState("");

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
          <input
            type="text"
            placeholder="Buscar nome, CPF ou Telegram ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md w-72 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        }
      />
      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && filtered.length === 0 && <EmptyState message="Nenhum paciente encontrado" />}
      {filtered.length > 0 && <PatientTable patients={filtered} />}
    </div>
  );
}

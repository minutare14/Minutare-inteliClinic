"use client";

import { use, useState } from "react";
import { usePatient } from "@/hooks/use-patients";
import { PatientDetailCard } from "@/components/patients/patient-detail-card";
import { PatientFormModal } from "@/components/patients/patient-form-modal";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import Link from "next/link";

export default function PatientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: patient, loading, refetch } = usePatient(id);
  const [showEdit, setShowEdit] = useState(false);

  if (loading) return <LoadingState />;
  if (!patient) return <p className="text-red-500">Paciente nao encontrado</p>;

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
      <PatientDetailCard patient={patient} />

      <div className="mt-4 flex gap-3">
        <Link
          href={`/conversations`}
          className="px-4 py-2 text-sm bg-gray-100 rounded-md hover:bg-gray-200 text-gray-700"
        >
          Ver conversas
        </Link>
        <Link
          href={`/schedules`}
          className="px-4 py-2 text-sm bg-gray-100 rounded-md hover:bg-gray-200 text-gray-700"
        >
          Ver agendamentos
        </Link>
      </div>

      <PatientFormModal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        onSuccess={() => refetch()}
        patient={patient}
      />
    </div>
  );
}

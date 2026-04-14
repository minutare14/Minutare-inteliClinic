import type { Patient } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { formatDate, formatDateTime } from "@/lib/formatters";

const STAGE_LABELS: Record<string, { label: string; variant: string }> = {
  lead:     { label: "Lead",    variant: "waiting_input" },
  patient:  { label: "Paciente", variant: "active" },
  inactive: { label: "Inativo", variant: "cancelled" },
};

function StageChip({ stage }: { stage: string | null }) {
  const s = STAGE_LABELS[stage ?? ""] ?? { label: stage ?? "—", variant: "closed" };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

function TagChips({ tags }: { tags: string | null }) {
  if (!tags) return <span className="text-gray-400 text-sm">—</span>;
  const list = tags.split(",").map((t) => t.trim()).filter(Boolean);
  return (
    <div className="flex flex-wrap gap-1">
      {list.map((tag) => (
        <span
          key={tag}
          className="px-2 py-0.5 text-xs rounded-full bg-blue-50 text-blue-700 border border-blue-200"
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

export function PatientDetailCard({ patient }: { patient: Patient }) {
  return (
    <div className="space-y-4">
      {/* Header row */}
      <Card>
        <CardBody>
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{patient.full_name}</h3>
              <p className="text-sm text-gray-500 mt-0.5">
                {patient.phone ?? patient.email ?? "Sem contato"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StageChip stage={patient.stage} />
              <Badge variant={patient.consented_ai ? "active" : "cancelled"}>
                {patient.consented_ai ? "Consentiu IA" : "Sem consentimento"}
              </Badge>
            </div>
          </div>

          {/* Dados pessoais */}
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Dados Pessoais</p>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 mb-4">
            {([
              ["CPF", patient.cpf],
              ["Nascimento", formatDate(patient.birth_date)],
              ["Telefone", patient.phone],
              ["E-mail", patient.email],
              ["Canal preferido", patient.preferred_channel],
              ["Telegram ID", patient.telegram_user_id],
            ] as [string, string | null][]).map(([label, value]) => (
              <div key={label} className="flex justify-between text-sm border-b border-gray-50 pb-2">
                <dt className="text-gray-500">{label}</dt>
                <dd className="text-gray-800 font-medium">{value ?? "—"}</dd>
              </div>
            ))}
          </dl>

          {/* Convênio */}
          {(patient.convenio_name || patient.insurance_card_number) && (
            <>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Convênio</p>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 mb-4">
                <div className="flex justify-between text-sm border-b border-gray-50 pb-2">
                  <dt className="text-gray-500">Convênio</dt>
                  <dd className="text-gray-800 font-medium">{patient.convenio_name ?? "—"}</dd>
                </div>
                <div className="flex justify-between text-sm border-b border-gray-50 pb-2">
                  <dt className="text-gray-500">Carteirinha</dt>
                  <dd className="text-gray-800 font-medium">{patient.insurance_card_number ?? "—"}</dd>
                </div>
              </dl>
            </>
          )}

          {/* CRM */}
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">CRM</p>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 mb-4">
            <div className="flex justify-between text-sm border-b border-gray-50 pb-2">
              <dt className="text-gray-500">Origem</dt>
              <dd className="text-gray-800 font-medium capitalize">{patient.source ?? "—"}</dd>
            </div>
            <div className="flex justify-between text-sm border-b border-gray-50 pb-2">
              <dt className="text-gray-500">Criado em</dt>
              <dd className="text-gray-800 font-medium">{formatDateTime(patient.created_at)}</dd>
            </div>
          </dl>

          <div className="mb-3">
            <p className="text-xs text-gray-500 mb-1.5">Tags</p>
            <TagChips tags={patient.tags} />
          </div>

          {patient.crm_notes && (
            <div className="mt-3 p-3 bg-blue-50 rounded-md text-sm">
              <p className="text-xs font-medium text-blue-700 mb-1">Notas CRM</p>
              <p className="text-blue-900">{patient.crm_notes}</p>
            </div>
          )}

          {patient.operational_notes && (
            <div className="mt-3 p-3 bg-yellow-50 rounded-md text-sm">
              <p className="text-xs font-medium text-yellow-700 mb-1">Notas operacionais</p>
              <p className="text-yellow-900">{patient.operational_notes}</p>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

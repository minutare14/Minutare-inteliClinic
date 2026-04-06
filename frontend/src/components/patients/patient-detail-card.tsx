import type { Patient } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { formatDateTime } from "@/lib/formatters";

export function PatientDetailCard({ patient }: { patient: Patient }) {
  const fields: [string, string | null | boolean][] = [
    ["Nome completo", patient.full_name],
    ["CPF", patient.cpf],
    ["Telefone", patient.phone],
    ["Email", patient.email],
    ["Data nascimento", patient.birth_date],
    ["Convenio", patient.convenio_name],
    ["Carteirinha", patient.insurance_card_number],
    ["Canal preferido", patient.preferred_channel],
    ["Telegram ID", patient.telegram_user_id],
    ["Telegram Chat", patient.telegram_chat_id],
    ["Criado em", formatDateTime(patient.created_at)],
    ["Atualizado em", formatDateTime(patient.updated_at)],
  ];

  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">{patient.full_name}</h3>
          <Badge variant={patient.consented_ai ? "active" : "cancelled"}>
            {patient.consented_ai ? "Consentiu IA" : "Sem consentimento IA"}
          </Badge>
        </div>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3">
          {fields.map(([label, value]) => (
            <div key={label} className="flex justify-between text-sm border-b border-gray-50 pb-2">
              <dt className="text-gray-500">{label}</dt>
              <dd className="text-gray-800 font-medium">{String(value ?? "—")}</dd>
            </div>
          ))}
        </dl>
        {patient.operational_notes && (
          <div className="mt-4 p-3 bg-yellow-50 rounded-md text-sm">
            <span className="text-yellow-700 font-medium">Observacoes: </span>
            <span className="text-yellow-800">{patient.operational_notes}</span>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

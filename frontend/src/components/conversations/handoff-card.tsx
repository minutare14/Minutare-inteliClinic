import type { Handoff } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { formatDateTime } from "@/lib/formatters";

export function HandoffCard({ handoff }: { handoff: Handoff }) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-gray-700">Handoff</h4>
          <Badge variant={handoff.status}>{handoff.status}</Badge>
        </div>
        <dl className="space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-gray-500">Motivo</dt>
            <dd className="text-gray-700">{handoff.reason}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Prioridade</dt>
            <dd><Badge variant={handoff.priority}>{handoff.priority}</Badge></dd>
          </div>
          {handoff.context_summary && (
            <div className="mt-2">
              <dt className="text-gray-500 text-xs">Contexto</dt>
              <dd className="text-gray-600 text-xs mt-1">{handoff.context_summary}</dd>
            </div>
          )}
          <div className="flex justify-between">
            <dt className="text-gray-500">Criado</dt>
            <dd className="text-xs text-gray-600">{formatDateTime(handoff.created_at)}</dd>
          </div>
        </dl>
      </CardBody>
    </Card>
  );
}

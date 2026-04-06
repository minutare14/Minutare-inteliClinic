"use client";

import { useAuditEvents } from "@/hooks/use-audit";
import { AuditTable } from "@/components/audit/audit-table";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";

export default function AuditPage() {
  const { data, loading, error } = useAuditEvents(200);

  return (
    <div>
      <SectionHeader
        title="Auditoria"
        description="Eventos registrados pelo sistema para debug e rastreabilidade"
      />

      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && data && data.length === 0 && (
        <EmptyState message="Nenhum evento de auditoria" />
      )}
      {data && data.length > 0 && <AuditTable events={data} />}
    </div>
  );
}

"use client";

import { useFetch } from "@/hooks/use-fetch";
import { getRagDocuments } from "@/lib/api";
import { RagDocumentsTable } from "@/components/rag/rag-documents-table";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";

export default function RagPage() {
  const { data, loading, error } = useFetch(() => getRagDocuments());

  return (
    <div>
      <SectionHeader
        title="RAG - Base de Conhecimento"
        description="Documentos ingeridos para resposta automatica"
      />

      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && data && data.length === 0 && (
        <EmptyState message="Nenhum documento na base" />
      )}
      {data && data.length > 0 && <RagDocumentsTable documents={data} />}
    </div>
  );
}

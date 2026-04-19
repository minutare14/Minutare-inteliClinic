"use client";

import { useState, useEffect } from "react";
import { getDocuments, deleteDocument } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";

interface DocumentListProps {
  refreshTrigger?: number;
}

const STATUS_COLORS: Record<string, string> = {
  processing: "bg-yellow-100 text-yellow-800",
  ready: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
  archived: "bg-gray-100 text-gray-800",
};

export function DocumentList({ refreshTrigger }: DocumentListProps) {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const limit = 20;

  useEffect(() => {
    loadDocs();
  }, [page, filterCategory, filterStatus, refreshTrigger]);

  async function loadDocs() {
    setLoading(true);
    setError(null);
    try {
      const result = await getDocuments({
        category: filterCategory || undefined,
        status: filterStatus || undefined,
        page,
        limit,
      });
      setDocs(result.items);
      setTotal(result.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(docId: string) {
    if (!confirm("Tem certeza que deseja excluir este documento?")) return;
    try {
      await deleteDocument(docId);
      loadDocs();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <select
          value={filterCategory || ""}
          onChange={(e) => { setFilterCategory(e.target.value || null); setPage(1); }}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">Todas categorias</option>
          <option value="convenio">Convênio</option>
          <option value="protocolo">Protocolo</option>
          <option value="faq">FAQ</option>
          <option value="manual">Manual</option>
          <option value="tabela">Tabela</option>
          <option value="outro">Outro</option>
        </select>
        <select
          value={filterStatus || ""}
          onChange={(e) => { setFilterStatus(e.target.value || null); setPage(1); }}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">Todos status</option>
          <option value="processing">Processando</option>
          <option value="ready">Pronto</option>
          <option value="error">Erro</option>
          <option value="archived">Arquivado</option>
        </select>
      </div>

      {loading && <div className="text-gray-500 text-sm">Carregando...</div>}
      {error && <div className="text-red-600 text-sm">{error}</div>}

      {!loading && docs.length === 0 && (
        <div className="text-gray-500 text-sm py-4">Nenhum documento encontrado.</div>
      )}

      {!loading && docs.length > 0 && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="pb-2">Título</th>
                <th className="pb-2">Categoria</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Chunks</th>
                <th className="pb-2">Extrações</th>
                <th className="pb-2">Criado em</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => (
                <tr key={doc.id} className="border-b hover:bg-gray-50">
                  <td className="py-2 font-medium">{doc.title}</td>
                  <td className="py-2 capitalize">{doc.category}</td>
                  <td className="py-2">
                    <span className={`px-2 py-1 rounded text-xs ${STATUS_COLORS[doc.status] || ""}`}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="py-2">{doc.chunks_count}</td>
                  <td className="py-2">{doc.extractions_count}</td>
                  <td className="py-2 text-gray-500">{new Date(doc.created_at).toLocaleDateString("pt-BR")}</td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="text-red-600 hover:text-red-800 text-xs"
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex gap-2 items-center">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                Anterior
              </button>
              <span className="text-sm text-gray-600">
                Página {page} de {totalPages} ({total} itens)
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                Próxima
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
"use client";
import { useState } from "react";
import { useFetch } from "@/hooks/use-fetch";
import { getRagDocuments, ingestDocument, queryRag } from "@/lib/api";
import { RagQueryResult } from "@/lib/types";
import { RagDocumentsTable } from "@/components/rag/rag-documents-table";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Modal } from "@/components/ui/modal";
import { Card, CardBody } from "@/components/ui/card";

const CATEGORIES = ["convenio", "protocolo", "faq", "manual", "tabela", "outro"] as const;
type Category = typeof CATEGORIES[number];

export default function RagPage() {
  const { data, loading, error, refetch } = useFetch(() => getRagDocuments());

  // Create document modal state
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [form, setForm] = useState({ title: "", category: "" as Category | "", content: "" });

  // Query test panel state
  const [queryOpen, setQueryOpen] = useState(false);
  const [queryInput, setQueryInput] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryResults, setQueryResults] = useState<RagQueryResult[] | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  const setField = (field: string) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => setForm((p) => ({ ...p, [field]: e.target.value }));

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim() || !form.category || !form.content.trim()) {
      setCreateError("Todos os campos são obrigatórios");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      await ingestDocument({ title: form.title, category: form.category, content: form.content });
      setForm({ title: "", category: "", content: "" });
      setShowCreate(false);
      refetch();
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Erro ao adicionar documento");
    } finally {
      setCreating(false);
    }
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim()) return;
    setQuerying(true);
    setQueryError(null);
    setQueryResults(null);
    try {
      const results = await queryRag(queryInput.trim());
      setQueryResults(results);
    } catch (err: unknown) {
      setQueryError(err instanceof Error ? err.message : "Erro ao consultar RAG");
    } finally {
      setQuerying(false);
    }
  };

  const inputCls = "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";
  const labelCls = "block text-xs font-medium text-gray-700 mb-1";

  return (
    <div>
      <SectionHeader
        title="RAG - Base de Conhecimento"
        description="Documentos ingeridos para resposta automatica"
        action={
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Adicionar Documento
          </button>
        }
      />

      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && data && data.length === 0 && (
        <EmptyState message="Nenhum documento na base" />
      )}
      {data && data.length > 0 && <RagDocumentsTable documents={data} />}

      {/* Query Test Panel */}
      <div className="mt-6">
        <button
          onClick={() => setQueryOpen((v) => !v)}
          className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
        >
          <svg
            className={`w-4 h-4 transition-transform ${queryOpen ? "rotate-90" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Testar Query RAG
        </button>

        {queryOpen && (
          <Card className="mt-3">
            <CardBody>
              <form onSubmit={handleQuery} className="flex gap-2 mb-4">
                <input
                  className={`${inputCls} flex-1`}
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  placeholder="Ex: quais convênios são aceitos?"
                />
                <button
                  type="submit"
                  disabled={querying || !queryInput.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors whitespace-nowrap"
                >
                  {querying ? "Buscando..." : "Buscar"}
                </button>
              </form>

              {queryError && (
                <p className="text-sm text-red-600 mb-3">{queryError}</p>
              )}

              {queryResults && queryResults.length === 0 && (
                <p className="text-sm text-gray-500">Nenhum resultado encontrado.</p>
              )}

              {queryResults && queryResults.length > 0 && (
                <div className="space-y-3">
                  {queryResults.map((r) => (
                    <div key={r.chunk_id} className="p-3 border border-gray-200 rounded-lg bg-gray-50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold text-gray-700">{r.title}</span>
                        <span className="text-xs text-gray-400 font-mono">score: {r.score.toFixed(3)}</span>
                      </div>
                      {r.category && (
                        <span className="inline-block text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 mb-1.5">
                          {r.category}
                        </span>
                      )}
                      <p className="text-xs text-gray-600 leading-relaxed line-clamp-4">{r.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        )}
      </div>

      {/* Create Document Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Adicionar Documento" size="lg">
        <form onSubmit={handleCreate} className="space-y-4">
          {createError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{createError}</div>
          )}
          <div>
            <label className={labelCls}>Título *</label>
            <input
              className={inputCls}
              value={form.title}
              onChange={setField("title")}
              placeholder="Ex: Tabela de Convênios 2024"
              required
            />
          </div>
          <div>
            <label className={labelCls}>Categoria *</label>
            <select className={inputCls} value={form.category} onChange={setField("category")} required>
              <option value="">Selecionar categoria</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Conteúdo *</label>
            <textarea
              className={`${inputCls} resize-y min-h-[140px]`}
              value={form.content}
              onChange={setField("content")}
              placeholder="Cole aqui o conteúdo do documento..."
              required
            />
          </div>
          <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={creating}
              className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {creating ? "Adicionando..." : "Adicionar"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

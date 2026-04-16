"use client";
import { useState, useEffect, useCallback } from "react";
import { useFetch } from "@/hooks/use-fetch";
import {
  getRagDocuments,
  getRagDocumentChunks,
  deleteRagDocument,
  ingestDocument,
  queryRag,
  getRagStats,
  reindexRag,
} from "@/lib/api";
import type { RagDocument, RagChunk, RagQueryResult, RagStats, ReindexResult } from "@/lib/types";
import { SectionHeader } from "@/components/ui/section-header";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Modal } from "@/components/ui/modal";
import { Card, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/formatters";

const CATEGORIES = ["convenio", "protocolo", "faq", "manual", "tabela", "outro"] as const;
type Category = typeof CATEGORIES[number];

const inputCls = "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";
const labelCls = "block text-xs font-medium text-gray-700 mb-1";

/* ── Chunk Viewer ── */
function ChunkViewer({ docId, onClose }: { docId: string; onClose: () => void }) {
  const { data: chunks, loading } = useFetch(() => getRagDocumentChunks(docId), [docId]);

  return (
    <Modal open onClose={onClose} title="Chunks do Documento" size="lg">
      {loading && <LoadingState />}
      {!loading && chunks && chunks.length === 0 && (
        <p className="text-sm text-gray-500 py-4">Nenhum chunk encontrado.</p>
      )}
      {chunks && chunks.length > 0 && (
        <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
          {chunks.map((chunk: RagChunk) => (
            <div key={chunk.id} className="border border-gray-200 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-gray-600">
                  Chunk #{chunk.chunk_index}
                  {chunk.page != null && ` · p.${chunk.page}`}
                </span>
                <div className="flex items-center gap-2">
                  {chunk.has_embedding ? (
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 text-green-700">
                      embedding ok
                    </span>
                  ) : (
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-yellow-100 text-yellow-700">
                      sem embedding
                    </span>
                  )}
                  <span className="text-xs text-gray-400 font-mono">{chunk.id.slice(0, 8)}</span>
                </div>
              </div>
              <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{chunk.content}</p>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

/* ── Document Row ── */
function DocumentRow({
  doc,
  onViewChunks,
  onDelete,
}: {
  doc: RagDocument;
  onViewChunks: (id: string) => void;
  onDelete: (id: string, title: string) => void;
}) {
  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3 font-medium text-gray-900 max-w-[200px] truncate">{doc.title}</td>
      <td className="px-4 py-3">
        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
          {doc.category}
        </span>
      </td>
      <td className="px-4 py-3">
        <Badge variant={doc.status}>{doc.status}</Badge>
      </td>
      <td className="px-4 py-3 text-gray-500 text-xs">{doc.version}</td>
      <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(doc.created_at)}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onViewChunks(doc.id)}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            Chunks
          </button>
          <button
            onClick={() => onDelete(doc.id, doc.title)}
            className="text-xs text-red-500 hover:text-red-700 font-medium"
          >
            Excluir
          </button>
        </div>
      </td>
    </tr>
  );
}

/* ── Query Panel ── */
function QueryPanel() {
  const [open, setOpen] = useState(false);
  const [queryInput, setQueryInput] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryResults, setQueryResults] = useState<RagQueryResult[] | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [topK, setTopK] = useState(5);

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim()) return;
    setQuerying(true);
    setQueryError(null);
    setQueryResults(null);
    try {
      const results = await queryRag(queryInput.trim(), topK);
      setQueryResults(results);
    } catch (err: unknown) {
      setQueryError(err instanceof Error ? err.message : "Erro ao consultar RAG");
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="mt-6">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
      >
        <svg
          className={`w-4 h-4 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        Testar Query RAG
      </button>

      {open && (
        <Card className="mt-3">
          <CardBody>
            <form onSubmit={handleQuery} className="flex gap-2 mb-4 items-end">
              <div className="flex-1">
                <label className={labelCls}>Consulta</label>
                <input
                  className={inputCls}
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  placeholder="Ex: quais convênios são aceitos?"
                />
              </div>
              <div className="w-20">
                <label className={labelCls}>Top K</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  className={inputCls}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                />
              </div>
              <button
                type="submit"
                disabled={querying || !queryInput.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {querying ? "Buscando..." : "Buscar"}
              </button>
            </form>

            {queryError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mb-3">
                {queryError}
              </div>
            )}

            {queryResults !== null && queryResults.length === 0 && (
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
                Nenhum resultado encontrado. Verifique se há documentos ingeridos e se o provedor de embedding está configurado.
              </div>
            )}

            {queryResults && queryResults.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs text-gray-500">{queryResults.length} resultado(s) encontrado(s)</p>
                {queryResults.map((r, i) => (
                  <div key={r.chunk_id} className="p-3 border border-gray-200 rounded-lg bg-gray-50">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-gray-400">#{i + 1}</span>
                        <span className="text-xs font-semibold text-gray-700">{r.title}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                          {r.category}
                        </span>
                      </div>
                      <span className="text-xs text-gray-400 font-mono">score: {r.score.toFixed(3)}</span>
                    </div>
                    <p className="text-xs text-gray-600 leading-relaxed line-clamp-4 mt-1">{r.content}</p>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}

/* ── Reindex Banner ── */
function ReindexBanner({
  reindexing,
  result,
  error,
  stats,
}: {
  reindexing: boolean;
  result: ReindexResult | null;
  error: string | null;
  stats: RagStats | null;
}) {
  if (!reindexing && !result && !error) return null;

  if (reindexing) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 mb-4 rounded-lg border border-amber-200 bg-amber-50 text-amber-800 text-sm">
        <svg
          className="w-4 h-4 shrink-0 animate-spin text-amber-600"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <div>
          <span className="font-semibold">Reprocessando embeddings…</span>
          {stats && stats.chunks_without_embedding > 0 && (
            <span className="ml-2 text-amber-700">
              {stats.chunks_without_embedding} chunk(s) sem embedding detectados — gerando vetores com sentence-transformers.
            </span>
          )}
        </div>
      </div>
    );
  }

  if (result) {
    const allOk = result.failed === 0;
    return (
      <div
        className={`flex items-center gap-3 px-4 py-3 mb-4 rounded-lg border text-sm ${
          allOk
            ? "border-green-200 bg-green-50 text-green-800"
            : "border-yellow-200 bg-yellow-50 text-yellow-800"
        }`}
      >
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {allOk ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M12 3a9 9 0 110 18A9 9 0 0112 3z" />
          )}
        </svg>
        <span>
          <span className="font-semibold">Reindexação concluída.</span>{" "}
          {result.embedded} chunk(s) indexados com sucesso
          {result.failed > 0 && `, ${result.failed} falhou(ram)`}.
          {result.config_error && ` Motivo principal: ${result.config_error}.`}
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 mb-4 rounded-lg border border-red-200 bg-red-50 text-red-800 text-sm">
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        <span><span className="font-semibold">Erro na reindexação:</span> {error}</span>
      </div>
    );
  }

  return null;
}

/* ── Main Page ── */
export default function RagPage() {
  const { data, loading, error, refetch } = useFetch(() => getRagDocuments());

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [form, setForm] = useState({ title: "", category: "" as Category | "", content: "" });

  const [chunksDocId, setChunksDocId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);

  const [stats, setStats] = useState<RagStats | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexResult, setReindexResult] = useState<ReindexResult | null>(null);
  const [reindexError, setReindexError] = useState<string | null>(null);

  const runReindex = useCallback(async () => {
    setReindexing(true);
    setReindexResult(null);
    setReindexError(null);
    try {
      const result = await reindexRag();
      setReindexResult(result);
      refetch();
    } catch (err: unknown) {
      setReindexError(err instanceof Error ? err.message : "Falha ao reindexar");
    } finally {
      setReindexing(false);
    }
  }, [refetch]);

  useEffect(() => {
    let cancelled = false;
    getRagStats()
      .then((s) => {
        if (cancelled) return;
        setStats(s);
        if (s.chunks_without_embedding > 0) {
          runReindex();
        }
      })
      .catch(() => {
        // stats unavailable — skip auto-reindex silently
      });
    return () => { cancelled = true; };
  }, [runReindex]);

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

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeletingId(deleteTarget.id);
    try {
      await deleteRagDocument(deleteTarget.id);
      setDeleteTarget(null);
      refetch();
    } catch {
      // noop — keep modal open
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div>
      <SectionHeader
        title="RAG — Base de Conhecimento"
        description="Documentos ingeridos para resposta automática"
        action={
          <div className="flex items-center gap-3">
            {stats && !reindexing && (
              <div className="text-right">
                <div className="text-xs text-gray-500">
                  {stats.coverage_pct}% com embedding ({stats.chunks_with_embedding}/{stats.chunks_total} chunks)
                </div>
                <div className="text-xs text-gray-400">
                  {stats.embedding_provider} · {stats.embedding_model}
                </div>
              </div>
            )}
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              + Adicionar Documento
            </button>
          </div>
        }
      />

      <ReindexBanner
        reindexing={reindexing}
        result={reindexResult}
        error={reindexError}
        stats={stats}
      />

      {stats?.config_error && !reindexing && (
        <div className="mb-4 rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          ConfiguraÃ§Ã£o atual de embedding com aviso: {stats.config_error}
        </div>
      )}

      {loading && <LoadingState />}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && data && data.length === 0 && (
        <EmptyState message="Nenhum documento na base de conhecimento" />
      )}

      {data && data.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Título</th>
                <th className="px-4 py-3 text-left">Categoria</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Versão</th>
                <th className="px-4 py-3 text-left">Criado</th>
                <th className="px-4 py-3 text-left">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  onViewChunks={(id) => setChunksDocId(id)}
                  onDelete={(id, title) => setDeleteTarget({ id, title })}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <QueryPanel />

      {/* Chunk Viewer */}
      {chunksDocId && (
        <ChunkViewer docId={chunksDocId} onClose={() => setChunksDocId(null)} />
      )}

      {/* Delete Confirm Modal */}
      {deleteTarget && (
        <Modal open onClose={() => setDeleteTarget(null)} title="Confirmar exclusão" size="sm">
          <p className="text-sm text-gray-700 mb-4">
            Excluir documento <strong>&ldquo;{deleteTarget.title}&rdquo;</strong> e todos os seus chunks?
            Esta ação não pode ser desfeita.
          </p>
          <div className="flex justify-end gap-3">
            <button
              onClick={() => setDeleteTarget(null)}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
            >
              Cancelar
            </button>
            <button
              onClick={handleDelete}
              disabled={!!deletingId}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              {deletingId ? "Excluindo..." : "Excluir"}
            </button>
          </div>
        </Modal>
      )}

      {/* Create Document Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Adicionar Documento" size="lg">
        <form onSubmit={handleCreate} className="space-y-4">
          {createError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {createError}
            </div>
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
          <p className="text-xs text-gray-500">
            O conteúdo será dividido em chunks e embeds serão gerados automaticamente se um provedor de embedding estiver configurado.
          </p>
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
              {creating ? "Processando..." : "Adicionar e Indexar"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

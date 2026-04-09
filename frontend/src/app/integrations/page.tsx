"use client";
import { useState } from "react";
import { useFetch } from "@/hooks/use-fetch";
import { getTelegramWebhookInfo, setTelegramWebhook } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { Card, CardBody } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";

export default function IntegrationsPage() {
  const { data: webhook, loading, error, refetch } = useFetch(() =>
    getTelegramWebhookInfo().catch(() => null)
  );
  const [newUrl, setNewUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; msg: string } | null>(null);

  const handleSetWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl.trim()) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      await setTelegramWebhook(newUrl.trim());
      setSaveMsg({ ok: true, msg: "Webhook configurado com sucesso!" });
      setNewUrl("");
      refetch();
    } catch (err: unknown) {
      setSaveMsg({ ok: false, msg: err instanceof Error ? err.message : "Erro ao configurar webhook" });
    } finally {
      setSaving(false);
    }
  };

  const inputCls = "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div>
      <SectionHeader
        title="Integrações"
        description="Status e configuração dos canais de atendimento"
      />

      {loading && <LoadingState />}

      <div className="mt-4 space-y-4">
        {/* Telegram Status */}
        <Card>
          <CardBody>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.96 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Telegram</h3>
                <p className="text-xs text-gray-500">Canal principal de atendimento ao paciente</p>
              </div>
              <div className="ml-auto">
                <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full ${webhook?.url ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${webhook?.url ? "bg-green-500" : "bg-gray-400"}`} />
                  {webhook?.url ? "Webhook ativo" : "Não configurado"}
                </span>
              </div>
            </div>

            {webhook && (
              <dl className="space-y-2 text-sm mb-4">
                <div className="flex justify-between items-start gap-4">
                  <dt className="text-gray-500 whitespace-nowrap">URL do webhook</dt>
                  <dd className="font-mono text-xs text-gray-700 break-all text-right">{webhook.url || "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Atualizações pendentes</dt>
                  <dd className="text-gray-700">{webhook.pending_update_count ?? 0}</dd>
                </div>
                {webhook.last_error_message && (
                  <div className="flex justify-between items-start gap-4">
                    <dt className="text-red-500 whitespace-nowrap">Último erro</dt>
                    <dd className="text-red-600 text-xs text-right">{webhook.last_error_message}</dd>
                  </div>
                )}
              </dl>
            )}

            {error && (
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-700 mb-4">
                Não foi possível obter informações do webhook. Verifique o token do Telegram.
              </div>
            )}

            <div className="border-t border-gray-100 pt-4">
              <h4 className="text-xs font-semibold text-gray-700 mb-3">Configurar webhook</h4>
              <form onSubmit={handleSetWebhook} className="flex gap-2">
                <input
                  className={`${inputCls} flex-1`}
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://bot.suaclinica.com.br/api/v1/telegram/webhook"
                  type="url"
                />
                <button
                  type="submit"
                  disabled={saving || !newUrl.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors whitespace-nowrap"
                >
                  {saving ? "Salvando..." : "Configurar"}
                </button>
              </form>
              {saveMsg && (
                <p className={`text-xs mt-2 ${saveMsg.ok ? "text-green-600" : "text-red-600"}`}>{saveMsg.msg}</p>
              )}
            </div>
          </CardBody>
        </Card>

        {/* Future integrations placeholder */}
        <Card>
          <CardBody>
            <div className="flex items-center gap-3 opacity-40">
              <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">WhatsApp Business</h3>
                <p className="text-xs text-gray-500">Fase 2 — canal adicional de atendimento</p>
              </div>
              <span className="ml-auto text-xs font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-400">Em breve</span>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <div className="flex items-center gap-3 opacity-40">
              <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Voz / Telefone (LiveKit)</h3>
                <p className="text-xs text-gray-500">Fase 2 — atendimento por voz automatizado</p>
              </div>
              <span className="ml-auto text-xs font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-400">Em breve</span>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

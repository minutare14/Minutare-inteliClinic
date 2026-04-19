"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/use-fetch";
import {
  getClinicSettings,
  updateClinicProfile,
  updateClinicBranding,
  updateClinicAI,
  getInsurance,
  createInsurance,
  updateInsurance,
  deleteInsurance,
  getPrompts,
  createPrompt,
  updatePrompt,
  getSpecialties,
  createSpecialty,
  updateSpecialty,
  deleteSpecialty,
  getAdminLogs,
  getTelegramStatus,
  reconfigureTelegramWebhook,
} from "@/lib/api";
import type { ClinicSettings, InsuranceItem, PromptItem, ClinicSpecialty, AuditEvent } from "@/lib/types";
import { SectionHeader } from "@/components/ui/section-header";
import { Card, CardBody } from "@/components/ui/card";
import { DocumentUpload } from "@/components/admin/document-upload";
import { DocumentList } from "@/components/admin/document-list";

type Tab = "clinica" | "branding" | "ia" | "convenios" | "especialidades" | "integracoes" | "logs" | "prompts" | "documentos";

const EMBEDDING_MODEL_DEFAULTS: Record<string, string> = {
  local: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  openai: "text-embedding-3-small",
  gemini: "text-embedding-004",
};

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("clinica");

  const tabs: { id: Tab; label: string }[] = [
    { id: "clinica", label: "Clínica" },
    { id: "branding", label: "Branding" },
    { id: "ia", label: "IA & RAG" },
    { id: "convenios", label: "Convênios" },
    { id: "especialidades", label: "Especialidades" },
    { id: "documentos", label: "Documentos" },
    { id: "integracoes", label: "Integrações" },
    { id: "logs", label: "Logs" },
    { id: "prompts", label: "Prompts" },
  ];

  return (
    <div>
      <SectionHeader
        title="Admin"
        description="Configuração operacional da clínica — sem precisar editar .env"
      />

      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "clinica" && <ClinicTab />}
      {tab === "branding" && <BrandingTab />}
      {tab === "ia" && <AITab />}
      {tab === "convenios" && <InsuranceTab />}
      {tab === "especialidades" && <SpecialtiesTab />}
      {tab === "documentos" && <DocumentosTab />}
      {tab === "integracoes" && <IntegracoesTab />}
      {tab === "logs" && <LogsTab />}
      {tab === "prompts" && <PromptsTab />}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  );
}

function Input({
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
    />
  );
}

function Textarea({
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white resize-y font-mono"
    />
  );
}

function SaveButton({
  onClick,
  loading,
  saved,
}: {
  onClick: () => void;
  loading: boolean;
  saved: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
    >
      {loading ? "Salvando..." : saved ? "Salvo!" : "Salvar"}
    </button>
  );
}

// ── Clinic Tab ───────────────────────────────────────────────────────────────

function ClinicTab() {
  const { data, loading, refetch } = useFetch(getClinicSettings, []);
  const [form, setForm] = useState<Partial<ClinicSettings>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const val = (field: keyof ClinicSettings) =>
    (form[field] as string | undefined) ?? (data?.[field] as string | undefined) ?? "";

  const set = (field: keyof ClinicSettings) => (v: string) =>
    setForm((p) => ({ ...p, [field]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await updateClinicProfile(form as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      refetch();
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="text-sm text-gray-400">Carregando...</p>;

  return (
    <Card>
      <CardBody>
        <h2 className="text-sm font-semibold text-gray-800 mb-4">Perfil da Clínica</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Nome da Clínica">
            <Input value={val("name")} onChange={set("name")} placeholder="Ex: Clínica São Lucas" />
          </Field>
          <Field label="Nome curto">
            <Input value={val("short_name")} onChange={set("short_name")} placeholder="Ex: São Lucas" />
          </Field>
          <Field label="Nome do Chatbot">
            <Input value={val("chatbot_name")} onChange={set("chatbot_name")} placeholder="Ex: Assistente" />
          </Field>
          <Field label="CNPJ">
            <Input value={val("cnpj")} onChange={set("cnpj")} placeholder="00.000.000/0001-00" />
          </Field>
          <Field label="Telefone">
            <Input value={val("phone")} onChange={set("phone")} placeholder="(11) 99999-9999" />
          </Field>
          <Field label="Telefone de Emergência">
            <Input value={val("emergency_phone")} onChange={set("emergency_phone")} />
          </Field>
          <Field label="Email">
            <Input value={val("email")} onChange={set("email")} type="email" />
          </Field>
          <Field label="Website">
            <Input value={val("website")} onChange={set("website")} placeholder="https://..." />
          </Field>
          <Field label="Cidade">
            <Input value={val("city")} onChange={set("city")} />
          </Field>
          <Field label="Estado (UF)">
            <Input value={val("state")} onChange={set("state")} placeholder="SP" />
          </Field>
          <div className="md:col-span-2">
            <Field label="Endereço">
              <Input value={val("address")} onChange={set("address")} />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field label="Horário de Atendimento">
              <Input
                value={val("working_hours")}
                onChange={set("working_hours")}
                placeholder="Seg-Sex 8h às 18h, Sáb 8h às 12h"
              />
            </Field>
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <SaveButton onClick={save} loading={saving} saved={saved} />
        </div>
      </CardBody>
    </Card>
  );
}

// ── Branding Tab ─────────────────────────────────────────────────────────────

function BrandingTab() {
  const { data, loading, refetch } = useFetch(getClinicSettings, []);
  const [form, setForm] = useState<Partial<ClinicSettings>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const val = (field: keyof ClinicSettings) =>
    (form[field] as string | undefined) ?? (data?.[field] as string | undefined) ?? "";

  const set = (field: keyof ClinicSettings) => (v: string) =>
    setForm((p) => ({ ...p, [field]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await updateClinicBranding(form as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      refetch();
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="text-sm text-gray-400">Carregando...</p>;

  return (
    <Card>
      <CardBody>
        <h2 className="text-sm font-semibold text-gray-800 mb-4">Branding</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <Field label="URL do Logo">
              <Input value={val("logo_url")} onChange={set("logo_url")} placeholder="https://..." />
            </Field>
          </div>
          <Field label="Cor Primária">
            <div className="flex gap-2 items-center">
              <input
                type="color"
                value={val("primary_color") || "#2563eb"}
                onChange={(e) => set("primary_color")(e.target.value)}
                className="h-9 w-14 rounded border border-gray-200 cursor-pointer"
              />
              <Input
                value={val("primary_color")}
                onChange={set("primary_color")}
                placeholder="#2563eb"
              />
            </div>
          </Field>
          <Field label="Cor Secundária">
            <div className="flex gap-2 items-center">
              <input
                type="color"
                value={val("secondary_color") || "#64748b"}
                onChange={(e) => set("secondary_color")(e.target.value)}
                className="h-9 w-14 rounded border border-gray-200 cursor-pointer"
              />
              <Input
                value={val("secondary_color")}
                onChange={set("secondary_color")}
                placeholder="#64748b"
              />
            </div>
          </Field>
          <Field label="Cor de Destaque">
            <div className="flex gap-2 items-center">
              <input
                type="color"
                value={val("accent_color") || "#f59e0b"}
                onChange={(e) => set("accent_color")(e.target.value)}
                className="h-9 w-14 rounded border border-gray-200 cursor-pointer"
              />
              <Input
                value={val("accent_color")}
                onChange={set("accent_color")}
                placeholder="#f59e0b"
              />
            </div>
          </Field>
        </div>
        <div className="mt-4 flex justify-end">
          <SaveButton onClick={save} loading={saving} saved={saved} />
        </div>
      </CardBody>
    </Card>
  );
}

// ── AI Tab ───────────────────────────────────────────────────────────────────

function AITab() {
  const { data, loading, refetch } = useFetch(getClinicSettings, []);
  const [form, setForm] = useState<Partial<ClinicSettings>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const val = <K extends keyof ClinicSettings>(field: K): ClinicSettings[K] | string =>
    (form[field] as ClinicSettings[K] | undefined) ?? (data?.[field] as ClinicSettings[K]) ?? "";

  const set = (field: keyof ClinicSettings) => (v: string | number | boolean) =>
    setForm((p) => ({ ...p, [field]: v }));

  const defaultEmbeddingModel = (provider: string) =>
    EMBEDDING_MODEL_DEFAULTS[provider] ?? EMBEDDING_MODEL_DEFAULTS.local;

  const selectedEmbeddingProvider = ((val("embedding_provider") as string) || "local").toLowerCase();
  const selectedEmbeddingModel =
    (val("embedding_model") as string) || defaultEmbeddingModel(selectedEmbeddingProvider);

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await updateClinicAI(form as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      refetch();
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Erro ao salvar configurações de embedding");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="text-sm text-gray-400">Carregando...</p>;

  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-4">Provedor de IA</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Provider LLM">
              <select
                value={(val("ai_provider") as string) || ""}
                onChange={(e) => set("ai_provider")(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="">Auto-detect</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
                <option value="groq">Groq</option>
              </select>
            </Field>
            <Field label="Modelo">
              <Input
                value={(val("ai_model") as string) || ""}
                onChange={(v) => set("ai_model")(v)}
                placeholder="gpt-4o / claude-3-5-sonnet / etc"
              />
            </Field>
            <Field label="Provider de Embedding">
              <select
                value={selectedEmbeddingProvider}
                onChange={(e) => {
                  const nextProvider = e.target.value;
                  set("embedding_provider")(nextProvider);
                  set("embedding_model")(defaultEmbeddingModel(nextProvider));
                  setSaveError(null);
                }}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="local">Local (Recomendado)</option>
                <option value="openai">OpenAI</option>
                <option value="gemini">Gemini</option>
              </select>
            </Field>
            <Field label="Modelo de Embedding">
              <Input
                value={selectedEmbeddingModel}
                onChange={(v) => set("embedding_model")(v)}
                placeholder={defaultEmbeddingModel(selectedEmbeddingProvider)}
              />
            </Field>
          </div>
          <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">
            {selectedEmbeddingProvider === "local"
              ? "Local é o caminho oficial deste deploy: usa sentence-transformers no próprio backend e não exige chave externa."
              : "Providers externos exigem chave configurada no backend e compatibilidade entre a dimensão do provider e o schema atual do banco. Se isso não estiver correto, o salvamento será bloqueado com erro explícito."}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-4">Parâmetros RAG</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Field label="Confiança mínima RAG">
              <Input
                type="number"
                value={String(val("rag_confidence_threshold") || 0.75)}
                onChange={(v) => set("rag_confidence_threshold")(parseFloat(v))}
              />
            </Field>
            <Field label="Top-K chunks">
              <Input
                type="number"
                value={String(val("rag_top_k") || 5)}
                onChange={(v) => set("rag_top_k")(parseInt(v))}
              />
            </Field>
            <Field label="Tamanho do chunk">
              <Input
                type="number"
                value={String(val("rag_chunk_size") || 500)}
                onChange={(v) => set("rag_chunk_size")(parseInt(v))}
              />
            </Field>
            <Field label="Overlap do chunk">
              <Input
                type="number"
                value={String(val("rag_chunk_overlap") || 100)}
                onChange={(v) => set("rag_chunk_overlap")(parseInt(v))}
              />
            </Field>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-4">Comportamento do Agente</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Confiança mínima para handoff">
              <Input
                type="number"
                value={String(val("handoff_confidence_threshold") || 0.55)}
                onChange={(v) => set("handoff_confidence_threshold")(parseFloat(v))}
              />
            </Field>
            <div className="flex items-center gap-3 pt-5">
              <input
                type="checkbox"
                id="handoff_enabled"
                checked={Boolean(val("handoff_enabled") ?? true)}
                onChange={(e) => set("handoff_enabled")(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="handoff_enabled" className="text-sm text-gray-700">
                Handoff habilitado
              </label>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="clinical_block"
                checked={Boolean(val("clinical_questions_block") ?? true)}
                onChange={(e) => set("clinical_questions_block")(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="clinical_block" className="text-sm text-gray-700">
                Bloquear perguntas clínicas (CFM)
              </label>
            </div>
          </div>
          <div className="mt-4">
            <Field label="Persona do Bot">
              <Textarea
                value={(val("bot_persona") as string) || ""}
                onChange={(v) => set("bot_persona")(v)}
                placeholder="Descreva a persona e estilo de comunicação do assistente..."
                rows={5}
              />
            </Field>
          </div>
        </CardBody>
      </Card>

      <div className="flex justify-end">
        <SaveButton onClick={save} loading={saving} saved={saved} />
      </div>
      {saveError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {saveError}
        </div>
      )}
    </div>
  );
}

// ── Insurance Tab ─────────────────────────────────────────────────────────────

function InsuranceTab() {
  const { data: items, loading, refetch } = useFetch(() => getInsurance());
  const [newName, setNewName] = useState("");
  const [newCode, setNewCode] = useState("");
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const add = async () => {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      await createInsurance({ name: newName.trim(), code: newCode.trim() || null });
      setNewName("");
      setNewCode("");
      setShowForm(false);
      refetch();
    } finally {
      setAdding(false);
    }
  };

  const toggle = async (item: InsuranceItem) => {
    await updateInsurance(item.id, { active: !item.active });
    refetch();
  };

  const remove = async (id: string) => {
    await deleteInsurance(id);
    refetch();
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">
          {items?.length ?? 0} convênio(s) cadastrado(s)
        </p>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
        >
          + Adicionar
        </button>
      </div>

      {showForm && (
        <Card>
          <CardBody>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Nome do Convênio">
                <Input value={newName} onChange={setNewName} placeholder="Unimed, Amil, etc." />
              </Field>
              <Field label="Código (opcional)">
                <Input value={newCode} onChange={setNewCode} placeholder="ANS ou código interno" />
              </Field>
            </div>
            <div className="mt-3 flex gap-2">
              <button
                onClick={add}
                disabled={adding || !newName.trim()}
                className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
              >
                {adding ? "Salvando..." : "Salvar"}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900"
              >
                Cancelar
              </button>
            </div>
          </CardBody>
        </Card>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="space-y-2">
          {(items ?? []).map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-lg"
            >
              <div>
                <span className="text-sm font-medium text-gray-800">{item.name}</span>
                {item.code && (
                  <span className="ml-2 text-xs text-gray-400 font-mono">{item.code}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    item.active
                      ? "bg-green-50 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {item.active ? "Ativo" : "Inativo"}
                </span>
                <button
                  onClick={() => toggle(item)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {item.active ? "Desativar" : "Ativar"}
                </button>
                <button
                  onClick={() => remove(item.id)}
                  className="text-xs text-red-500 hover:underline"
                >
                  Remover
                </button>
              </div>
            </div>
          ))}
          {(items ?? []).length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              Nenhum convênio cadastrado.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Prompts Tab ───────────────────────────────────────────────────────────────

function PromptsTab() {
  const { data: prompts, loading, refetch } = useFetch(() => getPrompts());
  const [editing, setEditing] = useState<PromptItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newAgent, setNewAgent] = useState("response_builder");
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [saving, setSaving] = useState(false);

  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await updatePrompt(editing.id, { content: editing.content });
      setEditing(null);
      refetch();
    } finally {
      setSaving(false);
    }
  };

  const saveNew = async () => {
    setSaving(true);
    try {
      await createPrompt({ agent: newAgent, name: newName, content: newContent });
      setShowCreate(false);
      setNewName("");
      setNewContent("");
      refetch();
    } finally {
      setSaving(false);
    }
  };

  const agentColor: Record<string, string> = {
    orchestrator: "bg-purple-50 text-purple-700",
    response_builder: "bg-blue-50 text-blue-700",
    guardrails: "bg-red-50 text-red-700",
    intent_router: "bg-yellow-50 text-yellow-700",
  };

  if (editing) {
    return (
      <Card>
        <CardBody>
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => setEditing(null)}
              className="text-sm text-gray-500 hover:text-gray-800"
            >
              ← Voltar
            </button>
            <span className="text-sm font-semibold text-gray-800">{editing.name}</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                agentColor[editing.agent] ?? "bg-gray-100 text-gray-600"
              }`}
            >
              {editing.agent}
            </span>
            <span className="text-xs text-gray-400 ml-auto">v{editing.version}</span>
          </div>
          {editing.description && (
            <p className="text-xs text-gray-500 mb-3">{editing.description}</p>
          )}
          <Textarea
            value={editing.content}
            onChange={(v) => setEditing({ ...editing, content: v })}
            rows={18}
          />
          <div className="mt-3 flex gap-2">
            <SaveButton onClick={saveEdit} loading={saving} saved={false} />
            <button
              onClick={() => setEditing(null)}
              className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900"
            >
              Cancelar
            </button>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">{prompts?.length ?? 0} prompt(s) registrado(s)</p>
        <button
          onClick={() => setShowCreate((s) => !s)}
          className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg"
        >
          + Novo Prompt
        </button>
      </div>

      {showCreate && (
        <Card>
          <CardBody>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">Novo Prompt</h3>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <Field label="Agente">
                <select
                  value={newAgent}
                  onChange={(e) => setNewAgent(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white"
                >
                  <option value="response_builder">response_builder</option>
                  <option value="orchestrator">orchestrator</option>
                  <option value="guardrails">guardrails</option>
                  <option value="intent_router">intent_router</option>
                </select>
              </Field>
              <Field label="Nome">
                <Input value={newName} onChange={setNewName} placeholder="Ex: system_prompt_v2" />
              </Field>
            </div>
            <Field label="Conteúdo do Prompt">
              <Textarea value={newContent} onChange={setNewContent} rows={10} />
            </Field>
            <div className="mt-3 flex gap-2">
              <button
                onClick={saveNew}
                disabled={saving || !newName || !newContent}
                className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
              >
                {saving ? "Salvando..." : "Salvar"}
              </button>
              <button onClick={() => setShowCreate(false)} className="text-sm text-gray-600">
                Cancelar
              </button>
            </div>
          </CardBody>
        </Card>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="space-y-2">
          {(prompts ?? []).map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-lg hover:border-blue-200 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    agentColor[p.agent] ?? "bg-gray-100 text-gray-600"
                  }`}
                >
                  {p.agent}
                </span>
                <span className="text-sm font-medium text-gray-800">{p.name}</span>
                {p.description && (
                  <span className="text-xs text-gray-400 hidden md:inline">{p.description}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">v{p.version}</span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    p.active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {p.active ? "Ativo" : "Inativo"}
                </span>
                <button
                  onClick={() => setEditing(p)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Editar
                </button>
              </div>
            </div>
          ))}
          {(prompts ?? []).length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              Nenhum prompt registrado. Crie o primeiro para sobrescrever os prompts hardcoded.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Specialties Tab ───────────────────────────────────────────────────────────

function SpecialtiesTab() {
  const { data: items, loading, refetch } = useFetch(() => getSpecialties(), []);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const add = async () => {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      await createSpecialty({ name: newName.trim(), description: newDesc.trim() || null });
      setNewName("");
      setNewDesc("");
      setShowForm(false);
      refetch();
    } finally {
      setAdding(false);
    }
  };

  const toggle = async (item: ClinicSpecialty) => {
    await updateSpecialty(item.id, { active: !item.active });
    refetch();
  };

  const remove = async (id: string) => {
    await deleteSpecialty(id);
    refetch();
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">{items?.length ?? 0} especialidade(s) cadastrada(s)</p>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg"
        >
          + Adicionar
        </button>
      </div>

      {showForm && (
        <Card>
          <CardBody>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Nome da Especialidade">
                <Input value={newName} onChange={setNewName} placeholder="Ex: Cardiologia" />
              </Field>
              <Field label="Descrição (opcional)">
                <Input value={newDesc} onChange={setNewDesc} placeholder="Breve descrição" />
              </Field>
            </div>
            <div className="mt-3 flex gap-2">
              <button
                onClick={add}
                disabled={adding || !newName.trim()}
                className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
              >
                {adding ? "Salvando..." : "Salvar"}
              </button>
              <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-600">
                Cancelar
              </button>
            </div>
          </CardBody>
        </Card>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="space-y-2">
          {(items ?? []).map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-lg"
            >
              <div>
                <span className="text-sm font-medium text-gray-800">{item.name}</span>
                {item.description && (
                  <span className="ml-2 text-xs text-gray-400">{item.description}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${item.active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                  {item.active ? "Ativa" : "Inativa"}
                </span>
                <button onClick={() => toggle(item)} className="text-xs text-blue-600 hover:underline">
                  {item.active ? "Desativar" : "Ativar"}
                </button>
                <button onClick={() => remove(item.id)} className="text-xs text-red-500 hover:underline">
                  Remover
                </button>
              </div>
            </div>
          ))}
          {(items ?? []).length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">Nenhuma especialidade cadastrada.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Integrações Tab ───────────────────────────────────────────────────────────

function IntegracoesTab() {
  const { data: status, loading, refetch } = useFetch(getTelegramStatus, []);
  const [reconfig, setReconfig] = useState(false);

  const doReconfig = async () => {
    setReconfig(true);
    try {
      await reconfigureTelegramWebhook();
      refetch();
    } finally {
      setReconfig(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-4">Telegram</h2>
          {loading ? (
            <p className="text-sm text-gray-400">Carregando...</p>
          ) : (
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Token configurado</dt>
                <dd>
                  <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${status?.token_configured ? "text-green-600" : "text-red-600"}`}>
                    <span className={`w-2 h-2 rounded-full ${status?.token_configured ? "bg-green-500" : "bg-red-500"}`} />
                    {status?.token_configured ? "Sim" : "Não"}
                  </span>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Webhook URL</dt>
                <dd className="font-mono text-xs text-gray-700 max-w-xs truncate">
                  {status?.computed_webhook_url || "—"}
                </dd>
              </div>
              {status?.webhook_info && (
                <>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Webhook registrado</dt>
                    <dd className="font-mono text-xs text-gray-700 max-w-xs truncate">
                      {status.webhook_info.url || "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Pendentes</dt>
                    <dd className="text-xs text-gray-700">{status.webhook_info.pending_update_count}</dd>
                  </div>
                </>
              )}
            </dl>
          )}
          <div className="mt-4">
            <button
              onClick={doReconfig}
              disabled={reconfig}
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
            >
              {reconfig ? "Reconfigurando..." : "Reconfigurar Webhook"}
            </button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-2">WhatsApp Business</h2>
          <p className="text-sm text-gray-400">Em breve</p>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-2">Google Calendar</h2>
          <p className="text-sm text-gray-400">Em breve</p>
        </CardBody>
      </Card>
    </div>
  );
}

// ── Documentos Tab ───────────────────────────────────────────────────────────

function DocumentosTab() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  return (
    <div className="space-y-6">
      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-4">Upload de Documento</h2>
          <DocumentUpload onUploadComplete={() => setRefreshTrigger((n) => n + 1)} />
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold text-gray-800 mb-4">Documentos</h2>
          <DocumentList refreshTrigger={refreshTrigger} />
        </CardBody>
      </Card>
    </div>
  );
}

// ── Logs Tab ──────────────────────────────────────────────────────────────────

function LogsTab() {
  const { data: logs, loading } = useFetch(() => getAdminLogs(100), []);

  const actionLabel = (action: string) => {
    const map: Record<string, string> = {
      "document.ingested": "Doc ingerido",
      "message.inbound": "Msg recebida",
      "message.outbound": "Msg enviada",
      "handoff.created": "Handoff criado",
      "slot.booked": "Slot agendado",
      "slot.cancelled": "Slot cancelado",
    };
    return map[action] ?? action;
  };

  const actorColor = (type: string) => {
    if (type === "ai") return "bg-blue-50 text-blue-700";
    if (type === "user") return "bg-green-50 text-green-700";
    return "bg-gray-100 text-gray-600";
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <p className="text-sm text-gray-500">{logs?.length ?? 0} eventos recentes</p>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="space-y-1">
          {(logs ?? []).map((log) => (
            <div
              key={log.id}
              className="flex items-center gap-3 px-4 py-2.5 bg-white border border-gray-100 rounded-lg text-sm"
            >
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${actorColor(log.actor_type)}`}>
                {log.actor_type}
              </span>
              <span className="text-gray-700 flex-1 truncate">{actionLabel(log.action)}</span>
              <span className="text-xs text-gray-400 flex-shrink-0">{log.resource_type}</span>
              <span className="text-xs text-gray-300 flex-shrink-0 hidden md:inline">
                {new Date(log.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
              </span>
            </div>
          ))}
          {(logs ?? []).length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">Nenhum evento registrado.</p>
          )}
        </div>
      )}
    </div>
  );
}

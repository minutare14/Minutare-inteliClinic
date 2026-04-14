"use client";

import { useState, useEffect, ChangeEvent, FormEvent } from "react";
import { Modal } from "@/components/ui/modal";
import { Patient } from "@/lib/types";
import { createPatient, updatePatient } from "@/lib/api";

interface PatientFormModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  patient?: Patient | null;
}

const EMPTY_FORM = {
  full_name: "",
  cpf: "",
  phone: "",
  email: "",
  birth_date: "",
  convenio_name: "",
  insurance_card_number: "",
  preferred_channel: "telegram",
  consented_ai: false,
  operational_notes: "",
  tags: "",
  crm_notes: "",
  stage: "lead",
  source: "",
};

type FormState = typeof EMPTY_FORM;

export function PatientFormModal({ open, onClose, onSuccess, patient }: PatientFormModalProps) {
  const isEdit = !!patient;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  useEffect(() => {
    if (patient) {
      setForm({
        full_name: patient.full_name,
        cpf: patient.cpf ?? "",
        phone: patient.phone ?? "",
        email: patient.email ?? "",
        birth_date: patient.birth_date ?? "",
        convenio_name: patient.convenio_name ?? "",
        insurance_card_number: patient.insurance_card_number ?? "",
        preferred_channel: patient.preferred_channel,
        consented_ai: patient.consented_ai,
        operational_notes: patient.operational_notes ?? "",
        tags: patient.tags ?? "",
        crm_notes: patient.crm_notes ?? "",
        stage: patient.stage ?? "lead",
        source: patient.source ?? "",
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setError(null);
  }, [patient, open]);

  const set = (field: string) => (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const val =
      e.target.type === "checkbox"
        ? (e.target as HTMLInputElement).checked
        : e.target.value;
    setForm((prev) => ({ ...prev, [field]: val }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.full_name.trim()) {
      setError("Nome completo é obrigatório");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { ...form };
      const nullable = [
        "cpf", "phone", "email", "birth_date", "convenio_name",
        "insurance_card_number", "operational_notes", "tags", "crm_notes", "source",
      ];
      nullable.forEach((k) => { if (payload[k] === "") payload[k] = null; });
      if (isEdit && patient) {
        await updatePatient(patient.id, payload);
      } else {
        await createPatient(payload);
      }
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao salvar paciente");
    } finally {
      setSaving(false);
    }
  };

  const inputCls =
    "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";
  const lbl = "block text-xs font-medium text-gray-700 mb-1";

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Editar Paciente" : "Novo Paciente"} size="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        {/* ── Dados pessoais ── */}
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Dados Pessoais</p>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className={lbl}>Nome completo *</label>
            <input className={inputCls} value={form.full_name} onChange={set("full_name")} required />
          </div>
          <div>
            <label className={lbl}>CPF</label>
            <input className={inputCls} value={form.cpf} onChange={set("cpf")} placeholder="000.000.000-00" />
          </div>
          <div>
            <label className={lbl}>Data de nascimento</label>
            <input type="date" className={inputCls} value={form.birth_date} onChange={set("birth_date")} />
          </div>
          <div>
            <label className={lbl}>Telefone</label>
            <input className={inputCls} value={form.phone} onChange={set("phone")} placeholder="(11) 99999-9999" />
          </div>
          <div>
            <label className={lbl}>E-mail</label>
            <input type="email" className={inputCls} value={form.email} onChange={set("email")} />
          </div>
        </div>

        {/* ── Convênio ── */}
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Convênio</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={lbl}>Convênio</label>
            <input className={inputCls} value={form.convenio_name} onChange={set("convenio_name")} placeholder="Unimed, Amil..." />
          </div>
          <div>
            <label className={lbl}>N° carteirinha</label>
            <input className={inputCls} value={form.insurance_card_number} onChange={set("insurance_card_number")} />
          </div>
        </div>

        {/* ── CRM ── */}
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">CRM</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={lbl}>Estágio</label>
            <select className={inputCls} value={form.stage} onChange={set("stage")}>
              <option value="lead">Lead</option>
              <option value="patient">Paciente</option>
              <option value="inactive">Inativo</option>
            </select>
          </div>
          <div>
            <label className={lbl}>Origem</label>
            <select className={inputCls} value={form.source} onChange={set("source")}>
              <option value="">—</option>
              <option value="telegram">Telegram</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="indicacao">Indicação</option>
              <option value="site">Site</option>
              <option value="phone">Telefone</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className={lbl}>Tags (separadas por vírgula)</label>
            <input
              className={inputCls}
              value={form.tags}
              onChange={set("tags")}
              placeholder="vip, urgente, convenio_pendente"
            />
          </div>
          <div className="col-span-2">
            <label className={lbl}>Notas CRM (internas)</label>
            <textarea
              className={`${inputCls} h-16 resize-none`}
              value={form.crm_notes}
              onChange={set("crm_notes")}
              placeholder="Notas do operador sobre este contato"
            />
          </div>
          <div className="col-span-2">
            <label className={lbl}>Notas operacionais</label>
            <textarea
              className={`${inputCls} h-16 resize-none`}
              value={form.operational_notes}
              onChange={set("operational_notes")}
              placeholder="Observações para o atendimento"
            />
          </div>
        </div>

        {/* ── Canal + consentimento ── */}
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Canal</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={lbl}>Canal preferido</label>
            <select className={inputCls} value={form.preferred_channel} onChange={set("preferred_channel")}>
              <option value="telegram">Telegram</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="web">Web</option>
              <option value="phone">Telefone</option>
            </select>
          </div>
          <div className="flex items-center gap-2 pt-5">
            <input
              type="checkbox"
              id="consented_ai"
              checked={form.consented_ai}
              onChange={set("consented_ai")}
              className="rounded"
            />
            <label htmlFor="consented_ai" className="text-sm text-gray-700">
              Consente uso de IA
            </label>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Salvando..." : isEdit ? "Salvar alterações" : "Criar paciente"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

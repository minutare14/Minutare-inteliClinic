"use client";

import { useState, useEffect, ChangeEvent, FormEvent } from "react";
import { Modal } from "@/components/ui/modal";
import { Patient } from "@/lib/types";
import { createPatient, updatePatient } from "@/lib/api";

interface PatientFormModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  patient?: Patient | null; // if provided, edit mode
}

export function PatientFormModal({ open, onClose, onSuccess, patient }: PatientFormModalProps) {
  const isEdit = !!patient;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
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
  });

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
      });
    } else {
      setForm({ full_name: "", cpf: "", phone: "", email: "", birth_date: "", convenio_name: "", insurance_card_number: "", preferred_channel: "telegram", consented_ai: false, operational_notes: "" });
    }
    setError(null);
  }, [patient, open]);

  const set = (field: string) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const val = e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value;
    setForm((prev) => ({ ...prev, [field]: val }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.full_name.trim()) { setError("Nome completo é obrigatório"); return; }
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { ...form };
      // Clean empty strings to null for optional fields
      ["cpf", "phone", "email", "birth_date", "convenio_name", "insurance_card_number", "operational_notes"].forEach(
        (k) => { if (payload[k] === "") payload[k] = null; }
      );
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

  const inputClass = "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";
  const labelClass = "block text-xs font-medium text-gray-700 mb-1";

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Editar Paciente" : "Novo Paciente"} size="lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>}

        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className={labelClass}>Nome completo *</label>
            <input className={inputClass} value={form.full_name} onChange={set("full_name")} placeholder="Nome completo do paciente" required />
          </div>
          <div>
            <label className={labelClass}>CPF</label>
            <input className={inputClass} value={form.cpf} onChange={set("cpf")} placeholder="000.000.000-00" />
          </div>
          <div>
            <label className={labelClass}>Data de nascimento</label>
            <input type="date" className={inputClass} value={form.birth_date} onChange={set("birth_date")} />
          </div>
          <div>
            <label className={labelClass}>Telefone</label>
            <input className={inputClass} value={form.phone} onChange={set("phone")} placeholder="(11) 00000-0000" />
          </div>
          <div>
            <label className={labelClass}>E-mail</label>
            <input type="email" className={inputClass} value={form.email} onChange={set("email")} placeholder="email@exemplo.com" />
          </div>
          <div>
            <label className={labelClass}>Convênio</label>
            <input className={inputClass} value={form.convenio_name} onChange={set("convenio_name")} placeholder="Ex: Unimed, Bradesco Saúde" />
          </div>
          <div>
            <label className={labelClass}>N° carteirinha</label>
            <input className={inputClass} value={form.insurance_card_number} onChange={set("insurance_card_number")} placeholder="Número do cartão" />
          </div>
          <div>
            <label className={labelClass}>Canal preferido</label>
            <select className={inputClass} value={form.preferred_channel} onChange={set("preferred_channel")}>
              <option value="telegram">Telegram</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="web">Web</option>
              <option value="phone">Telefone</option>
            </select>
          </div>
          <div className="flex items-center gap-2 pt-5">
            <input type="checkbox" id="consented_ai" checked={form.consented_ai} onChange={set("consented_ai")} className="rounded" />
            <label htmlFor="consented_ai" className="text-sm text-gray-700">Consente uso de IA</label>
          </div>
          <div className="col-span-2">
            <label className={labelClass}>Notas operacionais</label>
            <textarea className={`${inputClass} h-20 resize-none`} value={form.operational_notes} onChange={set("operational_notes")} placeholder="Observações internas (não enviadas ao paciente)" />
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
            Cancelar
          </button>
          <button type="submit" disabled={saving} className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {saving ? "Salvando..." : isEdit ? "Salvar alterações" : "Criar paciente"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

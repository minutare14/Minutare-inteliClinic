"use client";
import { useState, useEffect } from "react";
import { Modal } from "@/components/ui/modal";
import { Professional } from "@/lib/types";
import { createProfessional, updateProfessional } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  professional?: Professional | null;
}

export function ProfessionalFormModal({ open, onClose, onSuccess, professional }: Props) {
  const isEdit = !!professional;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ full_name: "", specialty: "", crm: "" });

  useEffect(() => {
    if (professional) {
      setForm({ full_name: professional.full_name, specialty: professional.specialty, crm: professional.crm });
    } else {
      setForm({ full_name: "", specialty: "", crm: "" });
    }
    setError(null);
  }, [professional, open]);

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((p) => ({ ...p, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.full_name.trim() || !form.specialty.trim() || (!isEdit && !form.crm.trim())) {
      setError("Todos os campos obrigatórios devem ser preenchidos");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (isEdit && professional) {
        await updateProfessional(professional.id, { full_name: form.full_name, specialty: form.specialty });
      } else {
        await createProfessional({ full_name: form.full_name, specialty: form.specialty, crm: form.crm });
      }
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  const inputCls = "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";
  const labelCls = "block text-xs font-medium text-gray-700 mb-1";

  const SPECIALTIES = ["Cardiologia", "Clínica Geral", "Dermatologia", "Endocrinologia", "Fisioterapia", "Ginecologia", "Neurologia", "Ortopedia", "Pediatria", "Psiquiatria", "Urologia", "Outra"];

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Editar Profissional" : "Novo Profissional"}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>}
        <div>
          <label className={labelCls}>Nome completo *</label>
          <input className={inputCls} value={form.full_name} onChange={set("full_name")} placeholder="Dr. Nome Sobrenome" required />
        </div>
        <div>
          <label className={labelCls}>Especialidade *</label>
          <select className={inputCls} value={form.specialty} onChange={set("specialty")} required>
            <option value="">Selecionar especialidade</option>
            {SPECIALTIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {!isEdit && (
          <div>
            <label className={labelCls}>CRM *</label>
            <input className={inputCls} value={form.crm} onChange={set("crm")} placeholder="CRM-SP 123456" required />
            <p className="text-xs text-gray-500 mt-1">O CRM não pode ser alterado após o cadastro.</p>
          </div>
        )}
        <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancelar</button>
          <button type="submit" disabled={saving} className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {saving ? "Salvando..." : isEdit ? "Salvar alterações" : "Cadastrar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

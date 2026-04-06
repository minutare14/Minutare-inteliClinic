"use client";

import Link from "next/link";
import type { Patient } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/formatters";

export function PatientTable({ patients }: { patients: Patient[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
          <tr>
            <th className="px-4 py-3 text-left">Nome</th>
            <th className="px-4 py-3 text-left">CPF</th>
            <th className="px-4 py-3 text-left">Telefone</th>
            <th className="px-4 py-3 text-left">Convenio</th>
            <th className="px-4 py-3 text-left">IA</th>
            <th className="px-4 py-3 text-left">Canal</th>
            <th className="px-4 py-3 text-left">Criado</th>
            <th className="px-4 py-3 text-left"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {patients.map((p) => (
            <tr key={p.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 font-medium text-gray-900">{p.full_name}</td>
              <td className="px-4 py-3 text-gray-600 font-mono text-xs">{p.cpf || "—"}</td>
              <td className="px-4 py-3 text-gray-600">{p.phone || "—"}</td>
              <td className="px-4 py-3 text-gray-600">{p.convenio_name || "—"}</td>
              <td className="px-4 py-3">
                <Badge variant={p.consented_ai ? "active" : "cancelled"}>
                  {p.consented_ai ? "Sim" : "Nao"}
                </Badge>
              </td>
              <td className="px-4 py-3 text-gray-500">{p.preferred_channel}</td>
              <td className="px-4 py-3 text-gray-500 text-xs">{formatDateTime(p.created_at)}</td>
              <td className="px-4 py-3">
                <Link
                  href={`/patients/${p.id}`}
                  className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                >
                  Detalhe
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

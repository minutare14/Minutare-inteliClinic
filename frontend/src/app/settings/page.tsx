"use client";

import { useFetch } from "@/hooks/use-fetch";
import { getHealth, getHealthDb } from "@/lib/api";
import { SectionHeader } from "@/components/ui/section-header";
import { Card, CardBody } from "@/components/ui/card";
import { API_URL } from "@/lib/constants";

export default function SettingsPage() {
  const { data: health } = useFetch(() =>
    getHealth().catch(() => ({ status: "error", service: "minutare-med" }))
  );
  const { data: dbHealth } = useFetch(() =>
    getHealthDb().catch(() => ({ status: "error", database: "disconnected" }))
  );

  return (
    <div>
      <SectionHeader title="Configuracoes" description="Status do sistema e configuracoes" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardBody>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Conexao com Backend</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">API URL</dt>
                <dd className="font-mono text-xs text-gray-700">{API_URL}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">API Status</dt>
                <dd>
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                      health?.status === "ok" ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        health?.status === "ok" ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    {health?.status === "ok" ? "Online" : "Offline"}
                  </span>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Database</dt>
                <dd>
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                      dbHealth?.status === "ok" ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        dbHealth?.status === "ok" ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    {dbHealth?.status === "ok" ? "Conectado" : "Desconectado"}
                  </span>
                </dd>
              </div>
            </dl>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Informacoes do Sistema</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Servico</dt>
                <dd className="text-gray-700">{health?.service ?? "minutare-med"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Versao</dt>
                <dd className="text-gray-700">MVP v0.1.0</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Frontend</dt>
                <dd className="text-gray-700">Next.js + Tailwind</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Backend</dt>
                <dd className="text-gray-700">FastAPI + PostgreSQL</dd>
              </div>
            </dl>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

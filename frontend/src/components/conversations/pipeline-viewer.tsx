"use client";

import { useState, useEffect } from "react";
import { getPipelineTrace } from "@/lib/api";
import type { PipelineTrace, PipelineStep } from "@/lib/types";
import { formatDateTime } from "@/lib/formatters";
import { Card, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function PipelineViewer({ conversationId }: { conversationId: string }) {
  const [traces, setTraces] = useState<PipelineTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTraces() {
      try {
        const data = await getPipelineTrace(conversationId);
        setTraces(data);
      } catch (err) {
        setError("Falha ao carregar rastro do pipeline.");
      } finally {
        setLoading(false);
      }
    }
    loadTraces();
  }, [conversationId]);

  if (loading) return <div className="p-4 text-sm text-gray-500">Carregando rastro da IA...</div>;
  if (error) return <div className="p-4 text-sm text-red-500">{error}</div>;
  if (traces.length === 0) return <div className="p-4 text-sm text-gray-400">Nenhum dado de pipeline encontrado para esta conversa.</div>;

  return (
    <div className="space-y-6">
      <h3 className="text-sm font-semibold text-gray-700 px-1 italic">Rastro Interno da Orquestração (Últimos Turnos)</h3>
      {traces.map((trace, idx) => (
        <Card key={idx} className="border-l-4 border-l-blue-500 overflow-hidden">
          <CardBody className="p-0">
            <div className="bg-gray-50 px-4 py-2 border-bottom flex justify-between items-center">
              <span className="text-[10px] font-mono text-gray-500">{formatDateTime(trace.created_at)}</span>
              <Badge variant="outline" className="text-[9px] uppercase tracking-wider">PIPELINE TURN</Badge>
            </div>
            <div className="p-4 space-y-4">
              {trace.steps.map((step, sIdx) => (
                <div key={sIdx} className="relative pl-6 pb-2 border-l-2 border-gray-100 last:border-l-transparent">
                  <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-white border-2 border-blue-500 flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs font-bold text-gray-700 uppercase tracking-tight">{step.name.replace(/_/g, " ")}</span>
                    <div className="mt-1 bg-gray-50 rounded p-2 text-[11px] font-mono text-gray-600 overflow-x-auto">
                      <pre>{JSON.stringify(step.payload, null, 2)}</pre>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const API_PREFIX = "/api/v1";

export const INTENT_LABELS: Record<string, string> = {
  agendar: "Agendar",
  remarcar: "Remarcar",
  cancelar: "Cancelar",
  duvida_operacional: "Dúvida",
  falar_com_humano: "Humano",
  politicas: "Políticas",
  listar_profissionais: "Profissionais",
  listar_especialidades: "Especialidades",
  saudacao: "Saudação",
  confirmacao: "Confirmação",
  desconhecida: "Desconhecida",
};

export const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  waiting_input: "bg-yellow-100 text-yellow-800",
  escalated: "bg-red-100 text-red-800",
  closed: "bg-gray-100 text-gray-800",
  open: "bg-orange-100 text-orange-800",
  assigned: "bg-blue-100 text-blue-800",
  resolved: "bg-green-100 text-green-800",
  available: "bg-green-100 text-green-800",
  booked: "bg-blue-100 text-blue-800",
  confirmed: "bg-indigo-100 text-indigo-800",
  cancelled: "bg-red-100 text-red-800",
  completed: "bg-gray-100 text-gray-800",
  no_show: "bg-yellow-100 text-yellow-800",
};

export const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-gray-100 text-gray-700",
  normal: "bg-blue-100 text-blue-700",
  high: "bg-orange-100 text-orange-700",
  urgent: "bg-red-100 text-red-700",
};

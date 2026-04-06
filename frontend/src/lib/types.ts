export interface Patient {
  id: string;
  full_name: string;
  cpf: string | null;
  birth_date: string | null;
  phone: string | null;
  email: string | null;
  telegram_user_id: string | null;
  telegram_chat_id: string | null;
  convenio_name: string | null;
  insurance_card_number: string | null;
  consented_ai: boolean;
  preferred_channel: string;
  operational_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  patient_id: string | null;
  channel: string;
  status: string;
  current_intent: string | null;
  confidence_score: number | null;
  human_assignee: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: string;
  content: string;
  created_at: string;
}

export interface Handoff {
  id: string;
  conversation_id: string;
  reason: string;
  priority: string;
  context_summary: string | null;
  status: string;
  created_at: string;
}

export interface ScheduleSlot {
  id: string;
  professional_id: string;
  patient_id: string | null;
  start_at: string;
  end_at: string;
  status: string;
  slot_type: string;
  source: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Professional {
  id: string;
  full_name: string;
  specialty: string;
  crm: string;
  active: boolean;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  actor_type: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  payload: string | null;
  created_at: string;
}

export interface RagDocument {
  id: string;
  title: string;
  category: string;
  source_path: string | null;
  version: string;
  status: string;
  created_at: string;
}

export interface DashboardSummary {
  total_patients: number;
  total_conversations: number;
  total_handoffs_open: number;
  total_slots: number;
  total_slots_booked: number;
  total_rag_documents: number;
  total_rag_chunks: number;
}

export interface HealthStatus {
  status: string;
  service?: string;
  database?: string;
}

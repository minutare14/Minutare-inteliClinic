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
  tags: string | null;
  crm_notes: string | null;
  stage: string | null;
  source: string | null;
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

export interface RagChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  page: number | null;
  created_at: string;
  embedded: boolean;
  embedding_error: string | null;
  has_embedding: boolean;
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

export interface RagQueryResult {
  chunk_id: string;
  document_id: string;
  title: string;
  content: string;
  score: number;
  category: string;
}

export interface RagIngestRequest {
  title: string;
  content: string;
  category: string;
  source_path?: string;
}

export interface RagIngestResponse {
  document_id: string;
  chunks_created: number;
  chunks_embedded: number;
  chunks_failed: number;
  embedding_provider: string;
  embedding_model: string;
}

export interface RagStats {
  documents: number;
  chunks_total: number;
  chunks_with_embedding: number;
  chunks_without_embedding: number;
  coverage_pct: number;
  embedding_provider: string;
  embedding_model: string;
  embedding_config_source: string;
  config_error: string | null;
}

export interface ReindexResult {
  documents_processed?: number;
  processed: number;
  embedded: number;
  failed: number;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_config_source?: string;
  config_error?: string | null;
  chunks_without_embedding?: number;
  coverage_pct?: number;
}

export interface TelegramWebhookInfo {
  url: string;
  has_custom_certificate: boolean;
  pending_update_count: number;
  last_error_date?: number;
  last_error_message?: string;
}

export interface TelegramStatus {
  token_configured: boolean;
  computed_webhook_url: string;
  webhook_info: TelegramWebhookInfo | null;
}

export interface ProfessionalCreate {
  full_name: string;
  specialty: string;
  crm: string;
}

export interface ProfessionalUpdate {
  full_name?: string;
  specialty?: string;
  active?: boolean;
}

export type UserRole = 'receptionist' | 'manager' | 'admin' | 'support';

// ── Admin ────────────────────────────────────────────────────────────────────

export interface ClinicSettings {
  id: string;
  clinic_id: string;
  name: string;
  short_name: string | null;
  chatbot_name: string;
  cnpj: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  working_hours: string | null;
  emergency_phone: string | null;
  logo_url: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  accent_color: string | null;
  ai_provider: string | null;
  ai_model: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  rag_confidence_threshold: number;
  rag_top_k: number;
  rag_chunk_size: number;
  rag_chunk_overlap: number;
  handoff_enabled: boolean;
  handoff_confidence_threshold: number;
  clinical_questions_block: boolean;
  bot_persona: string | null;
  updated_at: string;
}

export interface InsuranceItem {
  id: string;
  clinic_id: string;
  name: string;
  code: string | null;
  plan_types: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
}

export interface PromptItem {
  id: string;
  clinic_id: string;
  agent: string;
  scope: string;
  name: string;
  description: string | null;
  content: string;
  version: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClinicSpecialty {
  id: string;
  clinic_id: string;
  name: string;
  description: string | null;
  active: boolean;
  created_at: string;
}

// ── CRM ──────────────────────────────────────────────────────────────────────

export interface CrmLead {
  id: string;
  full_name: string;
  phone: string | null;
  stage: string;
  tags: string[];
  source: string | null;
  crm_notes: string | null;
  created_at: string;
}

export interface CrmStats {
  stages: { lead: number; patient: number; inactive: number };
  pending_followups: number;
  open_alerts: number;
}

export interface CrmFollowUp {
  id: string;
  patient_id: string;
  type: string;
  scheduled_at: string;
  notes: string | null;
}

export interface CrmAlert {
  id: string;
  patient_id: string | null;
  type: string;
  message: string;
  priority: string;
  created_at: string;
}

// ── Pipeline ─────────────────────────────────────────────────────────────────

export interface PipelineStep {
  name: string;
  status: 'active' | 'completed' | 'skipped' | 'failed';
  payload: Record<string, any> | null;
}

export interface PipelineTrace {
  conversation_id: string;
  steps: PipelineStep[];
  created_at: string;
}

// ── Document Upload ─────────────────────────────────────────────────────────────

export interface DocumentSummary {
  id: string;
  title: string;
  category: string;
  status: string;
  chunks_count: number;
  extractions_count: number;
  approved_count: number;
  rejected_count: number;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
  page: number;
}

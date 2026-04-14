import { API_URL, API_PREFIX } from "./constants";
import type {
  Patient,
  Conversation,
  Message,
  Handoff,
  ScheduleSlot,
  Professional,
  AuditEvent,
  RagDocument,
  RagChunk,
  DashboardSummary,
  HealthStatus,
  ProfessionalCreate,
  ProfessionalUpdate,
  RagIngestRequest,
  RagQueryResult,
  TelegramWebhookInfo,
  TelegramStatus,
  ClinicSettings,
  InsuranceItem,
  PromptItem,
  ClinicSpecialty,
} from "./types";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// Health
export const getHealth = () => fetchApi<HealthStatus>("/health");
export const getHealthDb = () => fetchApi<HealthStatus>("/health/db");

// Dashboard
export const getDashboardSummary = () =>
  fetchApi<DashboardSummary>(`${API_PREFIX}/dashboard/summary`);

// Patients
export const getPatients = (limit = 100, offset = 0) =>
  fetchApi<Patient[]>(`${API_PREFIX}/patients?limit=${limit}&offset=${offset}`);

export const getPatient = (id: string) =>
  fetchApi<Patient>(`${API_PREFIX}/patients/${id}`);

// Conversations
export const getConversations = (status?: string, patient_id?: string) => {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (patient_id) params.set("patient_id", patient_id);
  return fetchApi<Conversation[]>(`${API_PREFIX}/conversations?${params}`);
};

export const getPatientConversations = (patientId: string) =>
  getConversations(undefined, patientId);

export const getConversation = (id: string) =>
  fetchApi<Conversation>(`${API_PREFIX}/conversations/${id}`);

export const updateConversationStatus = (id: string, status: string) =>
  fetchApi<Conversation>(`${API_PREFIX}/conversations/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });

export const getMessages = (conversationId: string) =>
  fetchApi<Message[]>(`${API_PREFIX}/conversations/${conversationId}/messages`);

// Handoffs
export const getHandoffs = (status?: string) => {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  return fetchApi<Handoff[]>(`${API_PREFIX}/handoff?${params}`);
};

export const updateHandoffStatus = (id: string, status: string) =>
  fetchApi<Handoff>(`${API_PREFIX}/handoff/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });

// Schedules
export const getSchedules = (params?: {
  professional_id?: string;
  patient_id?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
}) => {
  const sp = new URLSearchParams();
  if (params?.professional_id) sp.set("professional_id", params.professional_id);
  if (params?.patient_id) sp.set("patient_id", params.patient_id);
  if (params?.date_from) sp.set("date_from", params.date_from);
  if (params?.date_to) sp.set("date_to", params.date_to);
  if (params?.status) sp.set("status", params.status);
  return fetchApi<ScheduleSlot[]>(`${API_PREFIX}/schedules?${sp}`);
};

export const getPatientSchedules = (patientId: string) =>
  getSchedules({ patient_id: patientId });

export const cancelSlot = (slotId: string) =>
  fetchApi<ScheduleSlot>(`${API_PREFIX}/schedules/${slotId}/cancel`, {
    method: "POST",
  });

// Professionals
export const getProfessionals = (specialty?: string) => {
  const params = new URLSearchParams();
  if (specialty) params.set("specialty", specialty);
  return fetchApi<Professional[]>(`${API_PREFIX}/professionals?${params}`);
};

// RAG
export const getRagDocuments = (category?: string) => {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  return fetchApi<RagDocument[]>(`${API_PREFIX}/rag/documents?${params}`);
};

export const getRagDocumentChunks = (docId: string) =>
  fetchApi<RagChunk[]>(`${API_PREFIX}/rag/documents/${docId}/chunks`);

export const deleteRagDocument = (docId: string) =>
  fetchApi<void>(`${API_PREFIX}/rag/documents/${docId}`, { method: "DELETE" });

// Audit
export const getAuditEvents = (limit = 100, offset = 0) =>
  fetchApi<AuditEvent[]>(`${API_PREFIX}/audit?limit=${limit}&offset=${offset}`);

// Patients — mutations
export const createPatient = (data: Record<string, unknown>) =>
  fetchApi<Patient>(`${API_PREFIX}/patients`, { method: 'POST', body: JSON.stringify(data) });

export const updatePatient = (id: string, data: Record<string, unknown>) =>
  fetchApi<Patient>(`${API_PREFIX}/patients/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

// Professionals — mutations
export const getAllProfessionals = () =>
  fetchApi<Professional[]>(`${API_PREFIX}/professionals/all`);

export const createProfessional = (data: ProfessionalCreate) =>
  fetchApi<Professional>(`${API_PREFIX}/professionals`, { method: 'POST', body: JSON.stringify(data) });

export const updateProfessional = (id: string, data: ProfessionalUpdate) =>
  fetchApi<Professional>(`${API_PREFIX}/professionals/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const deactivateProfessional = (id: string) =>
  fetchApi<Professional>(`${API_PREFIX}/professionals/${id}`, { method: 'DELETE' });

// RAG — mutations
export const ingestDocument = (data: RagIngestRequest) =>
  fetchApi<RagDocument>(`${API_PREFIX}/rag/ingest`, { method: 'POST', body: JSON.stringify(data) });

export const queryRag = (query: string, top_k = 5, category?: string) => {
  const body: Record<string, unknown> = { query, top_k };
  if (category) body.category = category;
  return fetchApi<RagQueryResult[]>(`${API_PREFIX}/rag/query`, { method: 'POST', body: JSON.stringify(body) });
};

// Telegram
export const getTelegramWebhookInfo = () =>
  fetchApi<TelegramWebhookInfo>(`${API_PREFIX}/telegram/webhook-info`);

export const getTelegramStatus = () =>
  fetchApi<TelegramStatus>(`${API_PREFIX}/telegram/status`);

export const reconfigureTelegramWebhook = () =>
  fetchApi<{ ok: boolean; url: string }>(`${API_PREFIX}/telegram/reconfigure-webhook`, {
    method: 'POST',
  });

// Admin — Clinic Settings
export const getClinicSettings = () =>
  fetchApi<ClinicSettings>(`${API_PREFIX}/admin/clinic`);

export const updateClinicProfile = (data: Record<string, unknown>) =>
  fetchApi<ClinicSettings>(`${API_PREFIX}/admin/clinic/profile`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const updateClinicBranding = (data: Record<string, unknown>) =>
  fetchApi<ClinicSettings>(`${API_PREFIX}/admin/clinic/branding`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const updateClinicAI = (data: Record<string, unknown>) =>
  fetchApi<ClinicSettings>(`${API_PREFIX}/admin/clinic/ai`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

// Admin — Insurance
export const getInsurance = (activeOnly = false) =>
  fetchApi<InsuranceItem[]>(`${API_PREFIX}/admin/insurance?active_only=${activeOnly}`);

export const createInsurance = (data: Record<string, unknown>) =>
  fetchApi<InsuranceItem>(`${API_PREFIX}/admin/insurance`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateInsurance = (id: string, data: Record<string, unknown>) =>
  fetchApi<InsuranceItem>(`${API_PREFIX}/admin/insurance/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteInsurance = (id: string) =>
  fetchApi<void>(`${API_PREFIX}/admin/insurance/${id}`, { method: 'DELETE' });

// Admin — Prompts
export const getPrompts = (agent?: string) => {
  const params = new URLSearchParams();
  if (agent) params.set('agent', agent);
  return fetchApi<PromptItem[]>(`${API_PREFIX}/admin/prompts?${params}`);
};

export const createPrompt = (data: Record<string, unknown>) =>
  fetchApi<PromptItem>(`${API_PREFIX}/admin/prompts`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updatePrompt = (id: string, data: Record<string, unknown>) =>
  fetchApi<PromptItem>(`${API_PREFIX}/admin/prompts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

// Admin — Specialties
export const getSpecialties = (activeOnly = false) =>
  fetchApi<ClinicSpecialty[]>(`${API_PREFIX}/admin/specialties?active_only=${activeOnly}`);

export const createSpecialty = (data: Record<string, unknown>) =>
  fetchApi<ClinicSpecialty>(`${API_PREFIX}/admin/specialties`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateSpecialty = (id: string, data: Record<string, unknown>) =>
  fetchApi<ClinicSpecialty>(`${API_PREFIX}/admin/specialties/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteSpecialty = (id: string) =>
  fetchApi<void>(`${API_PREFIX}/admin/specialties/${id}`, { method: 'DELETE' });

// Admin — Audit/Logs (reuse existing audit endpoint)
export const getAdminLogs = (limit = 50) =>
  fetchApi<AuditEvent[]>(`${API_PREFIX}/audit?limit=${limit}&offset=0`);

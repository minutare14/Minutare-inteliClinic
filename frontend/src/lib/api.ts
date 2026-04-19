import { API_URL, API_PREFIX } from "./constants";
import { getToken, clearAuth } from "./auth";
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
  RagStats,
  ReindexResult,
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
  PipelineTrace,
  PipelineStep,
  CrmLead,
  CrmStats,
  CrmFollowUp,
  CrmAlert,
  ServiceRead,
  ServiceCategoryRead,
  ServiceCreate,
  ServiceUpdate,
  ProfessionalServiceLinkRead,
} from "./types";

async function fetchApi<T>(
  path: string,
  options?: RequestInit,
  /** Pass an explicit token (e.g. during login flow before context is set). */
  overrideToken?: string,
): Promise<T> {
  const url = `${API_URL}${path}`;
  const token = overrideToken ?? getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // AbortController timeout: 15 seconds max per request
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15_000);

  let res: Response;
  try {
    res = await fetch(url, { ...options, headers, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }

  const text = await res.text();

  if (res.status === 401) {
    // Token expired or invalid — clear session and redirect to login
    clearAuth();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("Sessão expirada — faça login novamente");
  }

  if (!res.ok) {
    let message = `API ${res.status}: ${res.statusText}`;
    if (text) {
      try {
        const parsed = JSON.parse(text) as { detail?: string | { msg?: string }[] };
        if (typeof parsed.detail === "string" && parsed.detail.trim()) {
          message = parsed.detail;
        } else if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
          const first = parsed.detail[0];
          if (first?.msg) {
            message = first.msg;
          }
        }
      } catch {
        message = text;
      }
    }
    throw new Error(message);
  }
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
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

export const getRagStats = () =>
  fetchApi<RagStats>(`${API_PREFIX}/rag/stats`);

export const reindexRag = (docId?: string) => {
  const params = docId ? `?doc_id=${docId}` : "";
  return fetchApi<ReindexResult>(`${API_PREFIX}/rag/reindex${params}`, { method: "POST" });
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

// Admin — Services
export const getServiceCategories = () =>
  fetchApi<ServiceCategoryRead[]>(`${API_PREFIX}/admin/services/categories`);

export const getServices = () =>
  fetchApi<ServiceRead[]>(`${API_PREFIX}/admin/services`);

export const getService = (id: string) =>
  fetchApi<ServiceRead>(`${API_PREFIX}/admin/services/${id}`);

export const createService = (data: ServiceCreate) =>
  fetchApi<ServiceRead>(`${API_PREFIX}/admin/services`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateService = (id: string, data: ServiceUpdate) =>
  fetchApi<ServiceRead>(`${API_PREFIX}/admin/services/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deactivateService = (id: string) =>
  fetchApi<ServiceRead>(`${API_PREFIX}/admin/services/${id}`, { method: 'DELETE' });

export const upsertServicePrice = (serviceId: string, data: { price: number; insurance_plan_id?: string | null; copay?: number | null }) =>
  fetchApi<{ id: string; price: number; copay: number | null; version: number }>(
    `${API_PREFIX}/admin/services/${serviceId}/prices`,
    { method: 'POST', body: JSON.stringify(data) }
  );

export const linkProfessionalToService = (serviceId: string, data: { professional_id: string; notes?: string | null; priority_order?: number }) =>
  fetchApi<ProfessionalServiceLinkRead>(`${API_PREFIX}/admin/services/${serviceId}/doctors`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const unlinkProfessionalFromService = (serviceId: string, professionalId: string) =>
  fetchApi<void>(`${API_PREFIX}/admin/services/${serviceId}/doctors/${professionalId}`, { method: 'DELETE' });

// Admin — Documents
export interface DocumentUploadResponse {
  document_id: string;
  title: string;
  category: string;
  status: string;
  chunks_created: number;
  message: string;
}

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

export const uploadDocument = async (
  file: File,
  category: string,
  title: string | null,
): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('category', category);
  if (title) formData.append('title', title);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(`${API_URL}${API_PREFIX}/admin/documents/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  return response.json();
};

export const getDocuments = (params?: {
  category?: string;
  status?: string;
  page?: number;
  limit?: number;
}) => {
  const q = new URLSearchParams();
  if (params?.category) q.set('category', params.category);
  if (params?.status) q.set('status', params.status);
  q.set('page', String(params?.page ?? 1));
  q.set('limit', String(params?.limit ?? 20));
  return fetchApi<DocumentListResponse>(`${API_PREFIX}/admin/documents?${q}`);
};

export const deleteDocument = (id: string) =>
  fetchApi<void>(`${API_PREFIX}/admin/documents/${id}`, { method: 'DELETE' });

// Admin — Audit/Logs (reuse existing audit endpoint)
export const getAdminLogs = (limit = 50) =>
  fetchApi<AuditEvent[]>(`${API_PREFIX}/audit?limit=${limit}&offset=0`);

export const getAuditResourceEvents = (resourceType: string, resourceId: string) =>
  fetchApi<AuditEvent[]>(`${API_PREFIX}/audit/resource/${resourceType}/${resourceId}`);

export const getPipelineTrace = (conversationId: string) =>
  fetchApi<PipelineTrace[]>(`${API_PREFIX}/audit/pipeline/${conversationId}`);

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  full_name: string;
}

export interface AuthUserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  active: boolean;
  created_at: string;
}

/** Exchange credentials for a JWT. Does NOT inject stored token (public endpoint). */
export async function loginApi(email: string, password: string): Promise<LoginResponse> {
  const url = `${API_URL}${API_PREFIX}/auth/login`;
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  const text = await res.text();
  if (!res.ok) {
    let message = "Credenciais inválidas";
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) message = parsed.detail;
    } catch { /* ignore */ }
    throw new Error(message);
  }
  return JSON.parse(text) as LoginResponse;
}

/** Fetch the currently authenticated user's profile using the given token. */
export async function getMeApi(token: string): Promise<AuthUserResponse> {
  return fetchApi<AuthUserResponse>(`${API_PREFIX}/auth/me`, {}, token);
}

// ── Auth mutations ─────────────────────────────────────────────────────────────

/** Issue a fresh token, extending the session. Call on every authenticated interaction. */
export const refreshToken = () =>
  fetchApi<LoginResponse>(`${API_PREFIX}/auth/refresh`, { method: "POST" });

/** Logout — client should discard the token after this. */
export const logoutApi = () =>
  fetchApi<{ message: string }>(`${API_PREFIX}/auth/logout`, { method: "POST" });

// ── CRM ───────────────────────────────────────────────────────────────────────

export const getCrmLeads = (stage?: string) => {
  const params = new URLSearchParams();
  if (stage) params.set("stage", stage);
  return fetchApi<CrmLead[]>(`${API_PREFIX}/crm/leads?${params}`);
};

export const updateLeadStage = (patientId: string, stage: string) =>
  fetchApi<{ id: string; stage: string }>(`${API_PREFIX}/crm/leads/${patientId}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage }),
  });

export const addLeadNote = (patientId: string, note: string) =>
  fetchApi<{ id: string; crm_notes: string }>(`${API_PREFIX}/crm/leads/${patientId}/notes`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });

export const getCrmStats = () =>
  fetchApi<CrmStats>(`${API_PREFIX}/crm/stats`);

export const getPendingFollowUps = () =>
  fetchApi<CrmFollowUp[]>(`${API_PREFIX}/crm/followups/pending`);

export const completeFollowUp = (id: string) =>
  fetchApi<{ id: string; completed: boolean }>(`${API_PREFIX}/crm/followups/${id}/complete`, {
    method: "PATCH",
  });

export const getOpenAlerts = () =>
  fetchApi<CrmAlert[]>(`${API_PREFIX}/crm/alerts`);

export const resolveAlert = (id: string) =>
  fetchApi<{ id: string; resolved: boolean }>(`${API_PREFIX}/crm/alerts/${id}/resolve`, {
    method: "PATCH",
  });

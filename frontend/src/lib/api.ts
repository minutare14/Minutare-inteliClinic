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
  DashboardSummary,
  HealthStatus,
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
export const getConversations = (status?: string) => {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  return fetchApi<Conversation[]>(`${API_PREFIX}/conversations?${params}`);
};

export const getConversation = (id: string) =>
  fetchApi<Conversation>(`${API_PREFIX}/conversations/${id}`);

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
  date_from?: string;
  date_to?: string;
  status?: string;
}) => {
  const sp = new URLSearchParams();
  if (params?.professional_id) sp.set("professional_id", params.professional_id);
  if (params?.date_from) sp.set("date_from", params.date_from);
  if (params?.date_to) sp.set("date_to", params.date_to);
  if (params?.status) sp.set("status", params.status);
  return fetchApi<ScheduleSlot[]>(`${API_PREFIX}/schedules?${sp}`);
};

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

// Audit
export const getAuditEvents = (limit = 100, offset = 0) =>
  fetchApi<AuditEvent[]>(`${API_PREFIX}/audit?limit=${limit}&offset=${offset}`);

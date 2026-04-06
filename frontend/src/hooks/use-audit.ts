"use client";

import { useFetch } from "./use-fetch";
import { getAuditEvents } from "@/lib/api";

export function useAuditEvents(limit = 100) {
  return useFetch(() => getAuditEvents(limit));
}

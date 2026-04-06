"use client";

import { useFetch } from "./use-fetch";
import { getSchedules, getProfessionals } from "@/lib/api";

export function useSchedules(params?: {
  professional_id?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
}) {
  return useFetch(
    () => getSchedules(params),
    [params?.professional_id, params?.date_from, params?.date_to, params?.status]
  );
}

export function useProfessionals() {
  return useFetch(() => getProfessionals());
}

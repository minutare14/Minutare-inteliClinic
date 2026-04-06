"use client";

import { useFetch } from "./use-fetch";
import { getPatients, getPatient } from "@/lib/api";

export function usePatients() {
  return useFetch(() => getPatients());
}

export function usePatient(id: string) {
  return useFetch(() => getPatient(id), [id]);
}

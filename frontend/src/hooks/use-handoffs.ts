"use client";

import { useFetch } from "./use-fetch";
import { getHandoffs } from "@/lib/api";

export function useHandoffs(status?: string) {
  return useFetch(() => getHandoffs(status), [status]);
}

"use client";

import { useFetch } from "./use-fetch";
import { getConversations, getConversation, getMessages } from "@/lib/api";

export function useConversations(status?: string) {
  return useFetch(() => getConversations(status), [status]);
}

export function useConversation(id: string) {
  return useFetch(() => getConversation(id), [id]);
}

export function useMessages(conversationId: string) {
  return useFetch(() => getMessages(conversationId), [conversationId]);
}

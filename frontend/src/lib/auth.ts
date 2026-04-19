/**
 * Auth token storage helpers — localStorage-based session persistence.
 * All functions are safe to call during SSR (return null/no-op when window is undefined).
 */

const TOKEN_KEY = "intelliclinic_token";
const USER_KEY = "intelliclinic_user";
const LAST_ACTIVE_KEY = "intelliclinic_last_active";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  active: boolean;
  created_at: string;
}

export function saveToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
  console.debug("[AUTH] token saved at", Date.now());
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(LAST_ACTIVE_KEY);
  console.debug("[AUTH] auth cleared at", Date.now());
}

export function saveUser(user: AuthUser): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  console.debug("[AUTH] user saved:", user.email);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (!payload.exp) return false;
    return Date.now() >= payload.exp * 1000;
  } catch {
    return false;
  }
}

export function getTokenExpiry(token: string): Date | null {
  if (typeof window === "undefined") return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (!payload.exp) return null;
    return new Date(payload.exp * 1000);
  } catch {
    return null;
  }
}

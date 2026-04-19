"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import {
  getToken,
  saveToken,
  clearAuth,
  saveUser,
  getStoredUser,
  type AuthUser,
} from "@/lib/auth";
import { loginApi, getMeApi, refreshToken as refreshTokenApi } from "@/lib/api";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => {},
  logout: () => {},
  refreshSession: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const lastActiveRef = useRef<number>(Date.now());

  // Restore session from localStorage on mount
  useEffect(() => {
    const storedToken = getToken();
    const storedUser = getStoredUser();
    if (storedToken && storedUser) {
      console.debug("[AUTH] restoring session from localStorage");
      setToken(storedToken);
      setUser(storedUser);
    }
    setIsLoading(false);
  }, []);

  // Session refresh: issue fresh token every 20 minutes of active use
  const refreshSession = useCallback(async () => {
    const currentToken = getToken();
    if (!currentToken) return;

    try {
      console.debug("[AUTH] refreshing session at", Date.now());
      const data = await refreshTokenApi();
      saveToken(data.access_token);
      setToken(data.access_token);
      lastActiveRef.current = Date.now();
      console.debug("[AUTH] session refreshed, new token expires in 480min");
    } catch (err) {
      console.warn("[AUTH] refresh failed:", err);
    }
  }, []);

  // Heartbeat: refresh token every 15 minutes if user is active
  useEffect(() => {
    if (!user) return;

    const interval = setInterval(async () => {
      const now = Date.now();
      if (now - lastActiveRef.current < 15 * 60 * 1000) {
        await refreshSession();
      }
    }, 15 * 60 * 1000);

    return () => clearInterval(interval);
  }, [user, refreshSession]);

  const login = useCallback(async (email: string, password: string) => {
    console.debug("[AUTH] login start for", email);
    const data = await loginApi(email, password);
    const me = await getMeApi(data.access_token);
    saveToken(data.access_token);
    saveUser(me);
    setToken(data.access_token);
    setUser(me);
    lastActiveRef.current = Date.now();
    console.debug("[AUTH] login success for", email);
  }, []);

  const logout = useCallback(() => {
    console.debug("[AUTH] logout at", Date.now());
    clearAuth();
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  }, []);

  // Mark activity on user interactions
  useEffect(() => {
    const markActive = () => { lastActiveRef.current = Date.now(); };
    window.addEventListener("click", markActive);
    window.addEventListener("keypress", markActive);
    window.addEventListener("scroll", markActive);
    return () => {
      window.removeEventListener("click", markActive);
      window.removeEventListener("keypress", markActive);
      window.removeEventListener("scroll", markActive);
    };
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, token, isAuthenticated: !!token, isLoading, login, logout, refreshSession }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

"use client";

import { useEffect, useState } from "react";
import { getHealth, getHealthDb } from "@/lib/api";
import { useAuth } from "@/context/auth-context";

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  manager: "Gestor",
  reception: "Recepção",
  handoff_operator: "Operador",
};

export function Topbar() {
  const { user, logout } = useAuth();
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [dbOk, setDbOk] = useState<boolean | null>(null);

  useEffect(() => {
    const check = async () => {
      try {
        const h = await getHealth();
        setApiOk(h.status === "ok");
      } catch {
        setApiOk(false);
      }
      try {
        const d = await getHealthDb();
        setDbOk(d.status === "ok");
      } catch {
        setDbOk(false);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  const dot = (ok: boolean | null) => {
    if (ok === null) return "bg-gray-400";
    return ok ? "bg-green-500" : "bg-red-500";
  };

  return (
    <header className="fixed top-0 left-56 right-0 h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 z-20">
      <div />
      <div className="flex items-center gap-5 text-xs text-gray-500">
        {/* Health indicators */}
        <span className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${dot(apiOk)}`} />
          API
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${dot(dbOk)}`} />
          DB
        </span>

        {/* User info */}
        {user && (
          <>
            <span className="text-gray-300">|</span>
            <span className="text-gray-600 font-medium">
              {user.full_name}
            </span>
            <span className="bg-gray-100 text-gray-500 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide">
              {ROLE_LABELS[user.role] ?? user.role}
            </span>
            <button
              onClick={logout}
              className="text-gray-400 hover:text-red-500 transition-colors text-xs"
              title="Sair"
            >
              Sair
            </button>
          </>
        )}
      </div>
    </header>
  );
}

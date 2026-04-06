"use client";

import { useEffect, useState } from "react";
import { getHealth, getHealthDb } from "@/lib/api";

export function Topbar() {
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
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${dot(apiOk)}`} />
          API
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${dot(dbOk)}`} />
          DB
        </span>
      </div>
    </header>
  );
}

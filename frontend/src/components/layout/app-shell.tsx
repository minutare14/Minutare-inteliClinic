"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { useAuth } from "@/context/auth-context";

const PUBLIC_PATHS = ["/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const pathname = usePathname();

  const isPublic = PUBLIC_PATHS.some((p) => pathname?.startsWith(p));

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !isPublic) {
      // Use window.location for redirect to avoid Next.js router instability
      window.location.href = "/login";
    }
  }, [isLoading, isAuthenticated, isPublic]);

  // Login page — no sidebar/topbar wrapper
  if (isPublic) {
    return <>{children}</>;
  }

  // Auth check in progress — blank screen to avoid flash of unauthenticated UI
  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <Topbar />
      <main className="ml-56 mt-14 p-6">{children}</main>
    </div>
  );
}

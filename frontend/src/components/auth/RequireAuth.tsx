"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSupabaseApp } from "@/components/providers/SupabaseProvider";
import { isPublicRoute } from "@/lib/authRoutes";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, authReady } = useSupabaseApp();

  useEffect(() => {
    if (!authReady) return;
    if (isPublicRoute(pathname)) return;
    if (!session) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [authReady, session, pathname, router]);

  if (!authReady && !isPublicRoute(pathname)) {
    return (
      <div className="warm-page py-16 text-center text-stone-500">加载中…</div>
    );
  }

  if (authReady && !session && !isPublicRoute(pathname)) {
    return (
      <div className="warm-page py-16 text-center text-stone-500">跳转登录…</div>
    );
  }

  return <>{children}</>;
}

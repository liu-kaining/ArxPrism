"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createClient,
  type AuthChangeEvent,
  type Session,
  type SupabaseClient,
} from "@supabase/supabase-js";

type Ctx = { supabase: SupabaseClient; session: Session | null };

const SupabaseAppContext = createContext<Ctx | undefined>(undefined);

function getPublicEnv(): { url: string; anon: string } {
  const url = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim();
  const anon = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").trim();
  return { url, anon };
}

export function SupabaseProvider({ children }: { children: ReactNode }) {
  const { url, anon } = getPublicEnv();
  const supabase = useMemo(() => {
    if (!url || !anon) {
      return createClient("https://placeholder.local", "placeholder", {
        auth: { persistSession: false, autoRefreshToken: false },
      });
    }
    return createClient(url, anon);
  }, [url, anon]);

  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    if (!url || !anon) return;

    let cancelled = false;
    void supabase.auth
      .getSession()
      .then(({ data }: { data: { session: Session | null } }) => {
        if (!cancelled) setSession(data.session ?? null);
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(
      (_event: AuthChangeEvent, nextSession: Session | null) => {
        setSession(nextSession);
      }
    );

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, [supabase, url, anon]);

  const value = useMemo(() => ({ supabase, session }), [supabase, session]);

  return (
    <SupabaseAppContext.Provider value={value}>
      {children}
    </SupabaseAppContext.Provider>
  );
}

export function useSupabaseApp(): Ctx {
  const ctx = useContext(SupabaseAppContext);
  if (!ctx) {
    throw new Error("useSupabaseApp must be used within SupabaseProvider");
  }
  return ctx;
}

/** 与 @supabase/auth-helpers-react 的 useSession 对齐：仅返回 session 或 null */
export function useSession(): Session | null {
  return useSupabaseApp().session;
}

export function useSupabaseClient(): SupabaseClient {
  return useSupabaseApp().supabase;
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";
import { safeNextPath } from "@/lib/authRoutes";

/** Strict Mode runs effects twice; OAuth `code` is single-use — only one exchange may run. */
const exchangeInFlight = new Set<string>();

export default function AuthCallbackClient() {
  const router = useRouter();
  const [hint, setHint] = useState("正在完成登录…");

  useEffect(() => {
    const origin = window.location.origin;
    const url = new URL(window.location.href);
    const q = url.searchParams;
    const hash = new URLSearchParams(url.hash.replace(/^#/, ""));

    const oauthErr =
      q.get("error_description") ||
      q.get("error") ||
      hash.get("error_description") ||
      hash.get("error");

    if (oauthErr) {
      router.replace(
        `/login?error=${encodeURIComponent(oauthErr.replace(/\s+/g, " ").trim().slice(0, 300))}`
      );
      return;
    }

    const code = q.get("code");
    const next = safeNextPath(q.get("next") ?? "/", origin);

    if (!code) {
      router.replace(
        "/login?error=" +
          encodeURIComponent("缺少授权码。请从登录页重新发起 GitHub 登录。")
      );
      return;
    }

    if (exchangeInFlight.has(code)) return;
    exchangeInFlight.add(code);

    const supabase = createSupabaseBrowserClient();
    void (async () => {
      try {
        const { data: existing } = await supabase.auth.getSession();
        if (existing.session) {
          router.replace(next);
          router.refresh();
          return;
        }

        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) {
          router.replace(
            "/login?error=" + encodeURIComponent(error.message.slice(0, 300))
          );
          return;
        }
        router.replace(next);
        router.refresh();
      } finally {
        exchangeInFlight.delete(code);
      }
    })();
  }, [router]);

  useEffect(() => {
    const host = window.location.hostname;
    if (/^[0-9a-f]{12}$/i.test(host)) {
      setHint(
        "正在完成登录…（提示：Docker 下请用浏览器打开 http://localhost:3000，不要用容器 ID 主机名，否则 Cookie 与 OAuth 容易失败。）"
      );
    }
  }, []);

  return (
    <div className="warm-page mx-auto max-w-lg py-16 text-center text-sm text-stone-600">
      {hint}
    </div>
  );
}

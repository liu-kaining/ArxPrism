"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import { useSupabaseApp } from "@/components/providers/SupabaseProvider";
import { safeNextPath } from "@/lib/authRoutes";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ArrowLeft, Github, LogIn } from "lucide-react";

export default function LoginClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/";
  const rawError = searchParams.get("error");
  const { supabase, session, authReady, supabaseConfigured } = useSupabaseApp();
  const errorText = useMemo(() => {
    if (!rawError) return "";
    try {
      return decodeURIComponent(rawError.replace(/\+/g, " "));
    } catch {
      return rawError;
    }
  }, [rawError]);

  const supabasePublicUrl = (
    process.env.NEXT_PUBLIC_SUPABASE_URL || ""
  ).replace(/\/+$/, "");
  const supabaseGithubCallback = supabasePublicUrl
    ? `${supabasePublicUrl}/auth/v1/callback`
    : "";

  const isExchangeExternalError =
    /unable to exchange external code/i.test(errorText) ||
    /exchange external code/i.test(errorText);

  const [loading, setLoading] = useState(false);

  /** 已有会话时 URL 里的 error 多为上次回调失败残留，不应再展示或 toast */
  const showErrorBanner = !!(authReady && !session && errorText);

  useEffect(() => {
    if (!authReady || !session) return;
    const dest = safeNextPath(next, window.location.origin);
    router.replace(dest);
    router.refresh();
  }, [authReady, session, router, next]);

  useEffect(() => {
    if (showErrorBanner) toast.error(errorText);
  }, [showErrorBanner, errorText]);

  const onGithub = async () => {
    if (!supabaseConfigured) {
      toast.error("请先配置 NEXT_PUBLIC_SUPABASE_URL 与 NEXT_PUBLIC_SUPABASE_ANON_KEY");
      return;
    }
    setLoading(true);
    let leaving = false;
    try {
      const origin = window.location.origin;
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: "github",
        options: {
          redirectTo: `${origin}/auth/callback?next=${encodeURIComponent(next)}`,
        },
      });
      if (error) throw error;
      if (data?.url) {
        leaving = true;
        window.location.assign(data.url);
        return;
      }
      toast.error("未能获取 GitHub 授权地址，请检查 Supabase 与 GitHub 应用配置");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg || "GitHub 登录失败");
    } finally {
      if (!leaving) setLoading(false);
    }
  };

  if (authReady && session) {
    return (
      <div className="warm-page mx-auto max-w-md space-y-6 py-10">
        <p className="text-center text-sm text-stone-600">已登录，正在进入…</p>
      </div>
    );
  }

  return (
    <div className="warm-page mx-auto max-w-md space-y-6 py-10">
      <Link href="/">
        <Button
          variant="outline"
          size="sm"
          className="gap-2 rounded-xl border-stone-300"
        >
          <ArrowLeft className="h-4 w-4" />
          返回首页
        </Button>
      </Link>

      <Card className="border border-amber-200/80 shadow-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl text-stone-900">
            <LogIn className="h-6 w-6 text-amber-700" />
            登录 ArxPrism
          </CardTitle>
          <p className="text-sm text-stone-600">
            使用 GitHub 授权登录。请在 Supabase 控制台启用 GitHub 提供商并配置回调 URL。
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {!supabaseConfigured ? (
            <div className="rounded-xl border border-amber-300/80 bg-amber-50 px-4 py-3 text-sm text-amber-950">
              <p className="font-medium">未配置 Supabase 前端环境变量</p>
              <p className="mt-2 text-amber-900/90">
                在 <code className="rounded bg-white/80 px-1">frontend/.env.local</code>{" "}
                或 Docker 的 frontend 服务里设置{" "}
                <code className="rounded bg-white/80 px-1">
                  NEXT_PUBLIC_SUPABASE_URL
                </code>{" "}
                与{" "}
                <code className="rounded bg-white/80 px-1">
                  NEXT_PUBLIC_SUPABASE_ANON_KEY
                </code>
                （与 Supabase 项目 Dashboard 一致）。保存后需重新执行{" "}
                <code className="rounded bg-white/80 px-1">next dev</code>{" "}
                或重建前端镜像。
              </p>
            </div>
          ) : null}
          {showErrorBanner && isExchangeExternalError ? (
            <div className="space-y-3 rounded-xl border border-red-200 bg-red-50/90 px-4 py-3 text-sm text-red-950">
              <p className="font-semibold">
                这是 Supabase 与 GitHub 之间换票失败（多半不是本页代码问题）
              </p>
              <ol className="list-decimal space-y-2 pl-4 text-red-900/95">
                <li>
                  打开{" "}
                  <a
                    className="font-medium underline underline-offset-2"
                    href="https://github.com/settings/developers"
                    target="_blank"
                    rel="noreferrer"
                  >
                    GitHub → Settings → Developer settings → OAuth Apps
                  </a>
                  ，编辑你的应用：「Authorization callback URL」必须<strong>恰好</strong>是
                  Supabase 提供的地址（不是你的 Next 站点）：
                  {supabaseGithubCallback ? (
                    <code className="mt-1 block break-all rounded bg-white/90 px-2 py-1 text-xs text-stone-900">
                      {supabaseGithubCallback}
                    </code>
                  ) : (
                    <span className="mt-1 block text-xs">
                      形如{" "}
                      <code className="rounded bg-white/90 px-1">
                        https://&lt;项目&gt;.supabase.co/auth/v1/callback
                      </code>
                    </span>
                  )}
                </li>
                <li>
                  Supabase 控制台 → Authentication → Providers → GitHub：Client ID /
                  Secret 与上面 GitHub 应用一致；Secret 粘贴时勿带首尾空格。
                </li>
                <li>
                  Authentication → URL：Redirect URLs 包含你实际访问前端的地址，例如{" "}
                  <code className="rounded bg-white/90 px-1">
                    http://localhost:3000/auth/callback
                  </code>
                  ；浏览器请用 <code className="rounded bg-white/90 px-1">localhost</code>{" "}
                  打开，不要用 Docker 容器主机名。
                </li>
              </ol>
              <p className="text-xs text-red-800/90">
                官方说明：{" "}
                <a
                  className="underline underline-offset-2"
                  href="https://supabase.com/docs/guides/auth/social-login/auth-github"
                  target="_blank"
                  rel="noreferrer"
                >
                  Login with GitHub (Supabase)
                </a>
                ；仍不明可在 Dashboard → Authentication → Logs 查看详情。
              </p>
            </div>
          ) : showErrorBanner ? (
            <div className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-2 text-sm text-red-900">
              {errorText}
            </div>
          ) : null}
          <Button
            type="button"
            disabled={loading || !supabaseConfigured}
            onClick={() => void onGithub()}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-stone-900 font-semibold text-white hover:bg-stone-800"
          >
            <Github className="h-5 w-5" />
            {loading ? "跳转中…" : "使用 GitHub 登录"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

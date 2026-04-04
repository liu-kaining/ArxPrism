"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import {
  useSupabaseClient,
  useSupabaseConfigured,
} from "@/components/providers/SupabaseProvider";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ArrowLeft, Github, LogIn } from "lucide-react";

export default function LoginClient() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/";

  const supabase = useSupabaseClient();
  const supabaseConfigured = useSupabaseConfigured();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const msg = searchParams.get("error");
    if (msg) toast.error(msg);
  }, [searchParams]);

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

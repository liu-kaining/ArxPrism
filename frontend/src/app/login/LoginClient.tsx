"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import { useSupabaseClient } from "@/components/providers/SupabaseProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ArrowLeft, Github, LogIn } from "lucide-react";

export default function LoginClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/";

  const supabase = useSupabaseClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const onEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) throw error;
      toast.success("登录成功");
      router.replace(next);
      router.refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  const onGithub = async () => {
    setLoading(true);
    try {
      const origin = window.location.origin;
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "github",
        options: {
          redirectTo: `${origin}/auth/callback?next=${encodeURIComponent(next)}`,
        },
      });
      if (error) throw error;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(msg || "GitHub 登录失败");
      setLoading(false);
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
            使用 Supabase 账号登录后可访问论文库、任务与图谱 API。
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <form onSubmit={(e) => void onEmailLogin(e)} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-800">邮箱</label>
              <Input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-11 rounded-xl"
                placeholder="you@example.com"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-800">密码</label>
              <Input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-11 rounded-xl"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="h-11 w-full rounded-xl bg-amber-700 font-semibold text-white hover:bg-amber-800"
            >
              {loading ? "登录中…" : "邮箱登录"}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-stone-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-stone-500">或</span>
            </div>
          </div>

          <Button
            type="button"
            variant="outline"
            disabled={loading}
            onClick={() => void onGithub()}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-xl border-stone-300 font-semibold"
          >
            <Github className="h-5 w-5" />
            GitHub 登录（需在 Supabase 控制台启用）
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

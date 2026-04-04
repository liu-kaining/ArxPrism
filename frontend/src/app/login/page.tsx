import { Suspense } from "react";
import LoginClient from "./LoginClient";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="warm-page py-16 text-center text-stone-500">加载中…</div>
      }
    >
      <LoginClient />
    </Suspense>
  );
}

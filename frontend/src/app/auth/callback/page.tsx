import { Suspense } from "react";
import AuthCallbackClient from "./AuthCallbackClient";

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="warm-page py-16 text-center text-stone-500">加载中…</div>
      }
    >
      <AuthCallbackClient />
    </Suspense>
  );
}

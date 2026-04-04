import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "@xyflow/react/dist/style.css";
import { Toaster } from "react-hot-toast";
import Navbar from "@/components/ui/Navbar";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { SupabaseProvider } from "@/components/providers/SupabaseProvider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ArxPrism - 学术知识图谱萃取",
  description: "从 arXiv 论文中自动抽取结构化知识，构建学术知识图谱",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${inter.className} min-h-screen bg-background text-foreground antialiased`}
      >
        <SupabaseProvider>
          <div className="flex min-h-screen flex-col">
            <Navbar />
            <main className="container mx-auto flex-1 px-4 py-6">
              <RequireAuth>{children}</RequireAuth>
            </main>
          </div>
        </SupabaseProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            className: "!bg-card !text-card-foreground !border !border-border !shadow-md",
            duration: 4000,
          }}
        />
      </body>
    </html>
  );
}

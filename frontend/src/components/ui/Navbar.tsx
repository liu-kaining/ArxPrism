"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { BookOpen, GitBranch, Home, Network, Sparkles } from "lucide-react";

const navItems = [
  { href: "/papers", label: "论文列表", icon: BookOpen },
  { href: "/tasks", label: "任务管理", icon: Home },
  { href: "/graph", label: "知识图谱", icon: Network },
  { href: "/evolution", label: "进化树", icon: GitBranch },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-amber-200/70 bg-white/85 shadow-[0_1px_0_rgba(251,191,36,0.12)] backdrop-blur-md">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/papers" className="group flex items-center gap-3">
            <div className="relative">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-600 to-orange-700 shadow-sm transition-transform group-hover:scale-105">
                <Sparkles className="h-5 w-5 text-amber-50" />
              </div>
              <div className="absolute -inset-1 rounded-xl bg-amber-400/25 opacity-0 blur-md transition-opacity group-hover:opacity-100" />
            </div>
            <span className="text-xl font-bold tracking-tight text-stone-900">
              ArxPrism
            </span>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                pathname === item.href ||
                pathname.startsWith(`${item.href}/`) ||
                (item.href === "/papers" && pathname === "/");

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-amber-100 text-amber-950 shadow-sm ring-1 ring-amber-200/80"
                      : "text-stone-600 hover:bg-amber-50/90 hover:text-stone-900"
                  )}
                >
                  <Icon className={cn(
                    "w-4 h-4 transition-transform",
                    isActive ? "scale-110" : "group-hover:scale-105"
                  )} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}

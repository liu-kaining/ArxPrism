import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  GitBranch,
  LayoutGrid,
  Network,
  Rocket,
  Sparkles,
} from "lucide-react";

const features = [
  {
    href: "/papers",
    title: "论文列表",
    desc: "浏览已入库论文，按关键词或萃取主题筛选，查看摘要、提出方法与数据集/指标标签，并进入单篇详情与 PDF。",
    icon: BookOpen,
  },
  {
    href: "/tasks",
    title: "抓取任务",
    desc: "从 arXiv 按领域预设或自定义查询拉取论文，经流水线写入 Neo4j；创建后请用任务 ID 打开详情页跟踪进度。",
    icon: Rocket,
  },
  {
    href: "/graph",
    title: "知识图谱",
    desc: "以单篇论文为中心查看 Paper、Task、Method、Author 等节点及关系，支持类型筛选与交互浏览。",
    icon: Network,
  },
  {
    href: "/evolution",
    title: "技术进化树",
    desc: "按方法名沿 EVOLVED_FROM 展开技术血脉；可从论文详情中的「提出方法」再跳转。",
    icon: GitBranch,
  },
] as const;

export default function HomePage() {
  return (
    <div className="warm-page space-y-12 pb-12">
      <section className="relative overflow-hidden rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50 via-orange-50/90 to-amber-100/80 p-8 shadow-sm md:p-10">
        <div className="relative z-10 space-y-4">
          <p className="inline-flex items-center gap-2 rounded-full border border-amber-300/70 bg-white/70 px-3 py-1 text-xs font-medium text-amber-900 shadow-sm">
            <Sparkles className="h-3.5 w-3.5" />
            ArxPrism · 学术知识图谱萃取
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-stone-900 md:text-4xl">
            从 arXiv 到结构化图谱，一条链路走完
          </h1>
          <p className="text-base leading-relaxed text-stone-700 md:text-lg">
            系统自动抓取论文、萃取核心问题与提出方法，并将作者、数据集、指标等写入图数据库。你可以在列表里检索与统计，在图谱里看关联，在进化树里跟方法谱系。
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              href="/papers"
              prefetch={false}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-600 to-orange-700 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-95"
            >
              进入论文列表
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/tasks"
              prefetch={false}
              className="inline-flex items-center gap-2 rounded-xl border border-amber-300/90 bg-white/90 px-5 py-2.5 text-sm font-semibold text-amber-950 shadow-sm transition hover:bg-amber-50"
            >
              创建抓取任务
            </Link>
          </div>
        </div>
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-amber-400/25 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-10 right-1/4 h-32 w-32 rounded-full bg-orange-400/20 blur-2xl" />
      </section>

      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <LayoutGrid className="h-5 w-5 text-amber-700" />
          <h2 className="text-xl font-bold text-stone-900">功能一览</h2>
        </div>
        <p className="text-sm text-stone-600">
          下方入口对应顶部导航；建议新用户先浏览论文列表顶部的图库统计与主题分布，再按需创建任务或打开图谱。
        </p>
        <ul className="grid gap-4 sm:grid-cols-2">
          {features.map(({ href, title, desc, icon: Icon }) => (
            <li key={href}>
              <Link
                href={href}
                prefetch={false}
                className="group flex h-full flex-col rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:border-amber-300/80 hover:shadow-md"
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-amber-200/80 bg-amber-50 text-amber-800">
                    <Icon className="h-5 w-5" />
                  </span>
                  <ArrowRight className="h-5 w-5 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-amber-700" />
                </div>
                <h3 className="text-lg font-semibold text-stone-900">{title}</h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                  {desc}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-dashed border-amber-300/70 bg-amber-50/40 p-6 text-sm text-stone-700">
        <p className="font-medium text-stone-900">典型使用顺序</p>
        <ol className="mt-3 list-decimal space-y-2 pl-5">
          <li>在「抓取任务」中配置 arXiv 查询并创建任务，等待流水线完成。</li>
          <li>在「论文列表」中搜索、按主题筛选或分页浏览入库结果，打开详情。</li>
          <li>在「知识图谱」中输入 arXiv ID 查看单篇子图；在「技术进化树」中按方法名查看改进关系。</li>
        </ol>
      </section>
    </div>
  );
}

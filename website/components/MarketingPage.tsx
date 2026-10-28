import Link from "next/link";
import { ArrowRight, CheckCircle2 } from "lucide-react";

import type { SitePage } from "@/lib/site-content";

export function MarketingPage({ page }: { page: SitePage }) {
  const isRoadmap = page.status === "Roadmap";
  const isReview = page.status === "Publication review";

  return (
    <main className="px-4 py-16 sm:px-6 lg:py-24">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-3xl">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">{page.eyebrow}</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <h1 className="text-balance text-4xl font-semibold tracking-[-0.04em] text-zinc-50 sm:text-6xl">{page.title}</h1>
            {page.status && (
              <span className={`rounded-full px-3 py-1 font-mono text-xs ring-1 ${isRoadmap ? "bg-zinc-800 text-zinc-300 ring-white/10" : isReview ? "bg-amber-400/10 text-amber-200 ring-amber-300/25" : "bg-cyan-400/10 text-cyan-200 ring-cyan-300/25"}`}>
                {page.status}
              </span>
            )}
          </div>
          <p className="mt-6 text-pretty text-lg leading-8 text-zinc-300">{page.description}</p>
        </div>

        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {page.sections.map((section) => (
            <article key={section.title} className="min-h-48 rounded-xl bg-zinc-900 p-6 ring-1 ring-white/10">
              <CheckCircle2 className="size-5 text-cyan-300" aria-hidden="true" />
              <h2 className="mt-6 text-lg font-medium text-zinc-50">{section.title}</h2>
              <p className="mt-3 text-sm leading-6 text-zinc-400">{section.body}</p>
            </article>
          ))}
        </div>

        {page.related && page.related.length > 0 && (
          <nav className="mt-10 flex flex-wrap gap-3" aria-label="Related pages">
            {page.related.map((link) => (
              <Link key={link.href} href={link.href} className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-cyan-200 ring-1 ring-white/10 transition-colors duration-150 ease-in-out hover:bg-zinc-800 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                {link.label}<ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            ))}
          </nav>
        )}
      </div>
    </main>
  );
}

import Link from "next/link";
import { ArrowRight, CheckCircle2 } from "lucide-react";

import type { SitePage } from "@/lib/site-content";

export function MarketingPage({ page }: { page: SitePage }) {
  const isRoadmap = page.status === "Roadmap";
  const isReview = page.status === "Publication review";

  return (
    <main id="main-content" className="marketing-page px-4 py-16 sm:px-6 lg:py-24">
      <div className="mx-auto max-w-[1120px]">
        <div className="max-w-3xl">
          <p className="text-base text-muted-foreground">{page.eyebrow}</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <h1 className="text-balance text-4xl font-semibold tracking-[-0.04em] text-foreground sm:text-6xl">{page.title}</h1>
            {page.status && (
              <span className={`rounded-full px-3 py-1 font-sans text-xs ring-1 ${isRoadmap ? "bg-muted text-foreground ring-border" : isReview ? "bg-muted text-foreground ring-amber-300/25" : "bg-muted text-primary ring-ring"}`}>
                {page.status}
              </span>
            )}
          </div>
          <p className="mt-6 text-pretty text-lg leading-8 text-foreground">{page.description}</p>
        </div>

        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {page.sections.map((section) => (
            <article key={section.title} className="min-h-48 rounded-xl bg-card p-6 ring-1 ring-border">
              <CheckCircle2 className="size-5 text-primary" aria-hidden="true" />
              <h2 className="mt-6 text-lg font-medium text-foreground">{section.title}</h2>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">{section.body}</p>
            </article>
          ))}
        </div>

        {page.related && page.related.length > 0 && (
          <nav className="mt-10 flex flex-wrap gap-3" aria-label="Related pages">
            {page.related.map((link) => (
              <Link key={link.href} href={link.href} className="inline-flex items-center gap-2 rounded-lg bg-card px-4 py-2 text-sm font-medium text-primary ring-1 ring-border transition-colors duration-150 ease-in-out hover:bg-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                {link.label}<ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            ))}
          </nav>
        )}
      </div>
    </main>
  );
}

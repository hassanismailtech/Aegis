import Link from "next/link";

const columns = [
  { title: "Product", links: [["Open Source", "/product/open-source"], ["Proxy", "/product/proxy"], ["Scrubber", "/product/scrubber"], ["Wire Tap", "/product/wire-tap"], ["Design partners", "/company/design-partners"]] },
  { title: "Developers", links: [["Quickstart", "/developers/quickstart"], ["Documentation", "/docs"], ["Playground", "/playground"], ["Community", "/developers/community"], ["Changelog", "/company/changelog"]] },
  { title: "Trust", links: [["Architecture", "/trust/architecture"], ["Methodology", "/trust/methodology"], ["Frameworks", "/trust/frameworks"], ["Security", "/trust/security"], ["Status", "/trust/status"]] },
  { title: "Company", links: [["About", "/company/about"], ["Contact", "/company/contact"], ["Press", "/press"], ["Careers", "/company/careers"], ["Sitemap", "/sitemap"]] },
] as const;

const legalLinks = [["Privacy", "/legal/privacy"], ["Terms", "/legal/terms"], ["DPA", "/legal/dpa"], ["Cookies", "/legal/cookies"], ["Acceptable use", "/legal/acceptable-use"], ["License", "/license"]] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-zinc-950 px-4 py-12 sm:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {columns.map((column) => (
            <div key={column.title}>
              <p className="font-mono text-xs uppercase tracking-[0.16em] text-zinc-500">{column.title}</p>
              <ul className="mt-4 space-y-3">
                {column.links.map(([label, href]) => <li key={href}><Link href={href} className="text-sm text-zinc-400 transition-colors duration-150 ease-in-out hover:text-cyan-200">{label}</Link></li>)}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-col gap-5 border-t border-white/10 pt-6 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Aegis · open source · MIT</span>
          <nav className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Legal navigation">
            {legalLinks.map(([label, href]) => <Link key={href} href={href} className="transition-colors duration-150 ease-in-out hover:text-cyan-200">{label}</Link>)}
          </nav>
        </div>
      </div>
    </footer>
  );
}

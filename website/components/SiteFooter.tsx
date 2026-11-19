import Link from "next/link";
import { BrandMark } from "@/components/BrandMark";

const columns = [
  { title: "Product", links: [["Open Source", "/product/open-source"], ["Proxy", "/product/proxy"], ["Scrubber", "/product/scrubber"], ["Wire Tap", "/product/wire-tap"], ["Design partners", "/company/design-partners"]] },
  { title: "Developers", links: [["Quickstart", "/developers/quickstart"], ["Documentation", "/docs"], ["Playground", "/playground"], ["Community", "/developers/community"], ["Changelog", "/company/changelog"]] },
  { title: "Trust", links: [["Architecture", "/trust/architecture"], ["Methodology", "/trust/methodology"], ["Frameworks", "/trust/frameworks"], ["Security", "/trust/security"]] },
  { title: "Company", links: [["About", "/company/about"], ["Contact", "/company/contact"], ["Press", "/press"], ["Careers", "/company/careers"], ["Sitemap", "/sitemap"]] },
] as const;

const legalLinks = [["Privacy", "/legal/privacy"], ["Terms", "/legal/terms"], ["DPA", "/legal/dpa"], ["Cookies", "/legal/cookies"], ["Acceptable use", "/legal/acceptable-use"], ["License", "/license"]] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-background px-4 py-12 sm:px-6">
      <div className="mx-auto max-w-[1120px]">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {columns.map((column) => (
            <div key={column.title}>
              <p className="font-sans text-xs uppercase tracking-[0.16em] text-muted-foreground">{column.title}</p>
              <ul className="mt-4 space-y-3">
                {column.links.map(([label, href]) => <li key={href}><Link href={href} className="text-sm text-muted-foreground transition-colors duration-150 ease-in-out hover:text-primary">{label}</Link></li>)}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-col gap-5 border-t border-border pt-6 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span className="inline-flex items-center gap-2"><BrandMark className="size-6" />Seclume · open source · Apache-2.0</span>
          <nav className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Legal navigation">
            {legalLinks.map(([label, href]) => <Link key={href} href={href} className="transition-colors duration-150 ease-in-out hover:text-primary">{label}</Link>)}
          </nav>
        </div>
      </div>
    </footer>
  );
}

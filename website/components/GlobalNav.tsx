"use client";

import Link from "next/link";
import { BrandMark } from "@/components/BrandMark";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  ArrowRight,
  Boxes,
  FileCheck2,
  Menu,
  Network,
  ScanSearch,
  ShieldCheck,
  Users,
  Terminal,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from "@/components/ui/navigation-menu";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

type MenuLink = {
  title: string;
  description: string;
  href: string;
  icon: typeof ShieldCheck;
};

const productLinks: MenuLink[] = [
  {
    title: "Open Source",
    description: "Self-host the Proxy, Scrubber, and Wire Tap.",
    href: "/product/open-source",
    icon: Boxes,
  },
  {
    title: "Proxy",
    description: "An OpenAI- and Anthropic-compatible data boundary.",
    href: "/product/proxy",
    icon: Network,
  },
  {
    title: "Scrubber",
    description: "Nigerian-aware detection into Placeholders.",
    href: "/product/scrubber",
    icon: ScanSearch,
  },
  {
    title: "Wire Tap",
    description: "Post-scrub evidence of what Upstream received.",
    href: "/product/wire-tap",
    icon: FileCheck2,
  },
];

const trustLinks: MenuLink[] = [
  {
    title: "Security Architecture",
    description: "The boundary, Session Map, and fail-closed paths.",
    href: "/trust/architecture",
    icon: ShieldCheck,
  },
  {
    title: "Wire Tap & evidence",
    description: "Post-scrub proof for internal review.",
    href: "/trust/wire-tap",
    icon: FileCheck2,
  },
  {
    title: "NDPA 2023",
    description: "Cross-border context, not a compliance certificate.",
    href: "/compliance/ndpa",
    icon: ShieldCheck,
  },
  {
    title: "Responsible disclosure",
    description: "Report vulnerabilities privately.",
    href: "/security",
    icon: Terminal,
  },
];

const solutionLinks: MenuLink[] = [
  {
    title: "For Platform Engineers",
    description: "SDK integration, private deployment, and failure policy.",
    href: "/solutions/platform-engineers",
    icon: Terminal,
  },
  {
    title: "For DPOs & Compliance",
    description: "Technical evidence and explicit limitations.",
    href: "/solutions/dpo-compliance",
    icon: FileCheck2,
  },
  {
    title: "For Security & AppSec",
    description: "Fail-closed paths and disclosure guidance.",
    href: "/solutions/security",
    icon: ShieldCheck,
  },
  {
    title: "For AI Builders",
    description: "Tool-call and tool-result boundaries.",
    href: "/solutions/ai-builders",
    icon: Network,
  },
];

const developerLinks: MenuLink[] = [
  {
    title: "Quickstart",
    description: "Bring up Seclume and change your SDK base URL.",
    href: "/developers/quickstart",
    icon: Terminal,
  },
  {
    title: "OpenAI SDK",
    description: "Chat completions, streaming, and tool calls.",
    href: "/developers/openai",
    icon: Network,
  },
  {
    title: "Anthropic SDK",
    description: "Messages API and streaming through the boundary.",
    href: "/developers/anthropic",
    icon: Network,
  },
  {
    title: "Deploy",
    description: "VPC or on-prem deployment guidance.",
    href: "/developers/deploy",
    icon: Boxes,
  },
];

const companyLinks: MenuLink[] = [
  {
    title: "About Seclume",
    description: "The open-source data-boundary project.",
    href: "/company/about",
    icon: ShieldCheck,
  },
  {
    title: "Design Partners",
    description: "Shape real boundary and evidence needs.",
    href: "/company/design-partners",
    icon: Users,
  },
  {
    title: "Changelog",
    description: "Recent product changes from the repository.",
    href: "/company/changelog",
    icon: FileCheck2,
  },
  {
    title: "Contact",
    description: "Published communication paths and requirements.",
    href: "/company/contact",
    icon: Users,
  },
];

function MegaMenu({
  links,
  eyebrow,
  title,
  href,
}: {
  links: MenuLink[];
  eyebrow: string;
  title: string;
  href: string;
}) {
  return (
    <div className="grid w-[min(44rem,calc(100vw-2rem))] grid-cols-[0.8fr_1.2fr] overflow-hidden rounded-xl bg-card ring-1 ring-border">
      <Link
        href={href}
        className="group flex min-h-72 flex-col justify-between border-r border-border bg-muted p-6 transition-colors duration-150 ease-in-out hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div>
          <p className="font-sans text-xs uppercase tracking-[0.16em] text-primary">
            {eyebrow}
          </p>
          <p className="mt-3 text-xl font-semibold tracking-tight text-foreground">
            {title}
          </p>
        </div>
        <span className="inline-flex items-center gap-2 text-sm font-medium text-primary">
          Explore <ArrowRight className="size-4 transition-transform duration-150 ease-in-out group-hover:translate-x-1" />
        </span>
      </Link>
      <div className="grid content-start gap-1 p-3">
        {links.map(({ title: linkTitle, description, href: linkHref, icon: Icon }) => (
          <NavigationMenuLink
            key={linkHref}
            render={<Link href={linkHref} />}
            closeOnClick
            className="group rounded-lg p-3 hover:bg-muted focus:bg-muted"
          >
            <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <span>
              <span className="block font-medium text-foreground">{linkTitle}</span>
              <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">{description}</span>
            </span>
          </NavigationMenuLink>
        ))}
      </div>
    </div>
  );
}

function MobileLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <SheetClose render={<Link href={href} />} className="rounded-md px-3 py-2 text-sm font-medium text-foreground transition-colors duration-150 ease-in-out hover:bg-muted hover:text-primary">
      {children}
    </SheetClose>
  );
}

export function GlobalNav() {
  const dashboardUrl = process.env.NEXT_PUBLIC_DASHBOARD_ENABLED === "true"
    ? process.env.NEXT_PUBLIC_APP_URL
    : undefined;
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background px-4 sm:px-6">
      <div className="mx-auto flex h-18 max-w-[1120px] items-center justify-between gap-4">
        <Link href="/" className="site-wordmark inline-flex items-center gap-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <BrandMark />
          Seclume
        </Link>

        <NavigationMenu className="hidden lg:flex" align="start">
          <NavigationMenuList className="gap-1">
            <NavigationMenuItem>
              <NavigationMenuTrigger className="text-foreground hover:bg-muted hover:text-foreground focus:bg-muted">Product</NavigationMenuTrigger>
              <NavigationMenuContent>
                <MegaMenu links={productLinks} eyebrow="Product" title="A data boundary for AI systems." href="/product" />
              </NavigationMenuContent>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuTrigger className="text-foreground hover:bg-muted hover:text-foreground focus:bg-muted">Solutions</NavigationMenuTrigger>
              <NavigationMenuContent>
                <MegaMenu links={solutionLinks} eyebrow="Solutions" title="Routes for the people who operate the boundary." href="/solutions" />
              </NavigationMenuContent>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuTrigger className="text-foreground hover:bg-muted hover:text-foreground focus:bg-muted">Developers</NavigationMenuTrigger>
              <NavigationMenuContent>
                <MegaMenu links={developerLinks} eyebrow="Developers" title="Integrate without rewriting your agents." href="/developers" />
              </NavigationMenuContent>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuTrigger className="text-foreground hover:bg-muted hover:text-foreground focus:bg-muted">Trust</NavigationMenuTrigger>
              <NavigationMenuContent>
                <MegaMenu links={trustLinks} eyebrow="Trust" title="Evidence, architecture, and limits." href="/trust" />
              </NavigationMenuContent>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuTrigger className="text-foreground hover:bg-muted hover:text-foreground focus:bg-muted">Company</NavigationMenuTrigger>
              <NavigationMenuContent>
                <MegaMenu links={companyLinks} eyebrow="Company" title="An open-source project with a clear boundary." href="/company" />
              </NavigationMenuContent>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuLink render={<Link href="/docs" />} className="px-2.5 py-1.5 text-foreground hover:bg-muted hover:text-foreground">
                Docs
              </NavigationMenuLink>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuLink render={<Link href="/pricing" />} className="px-2.5 py-1.5 text-foreground hover:bg-muted hover:text-foreground">
                Pricing
              </NavigationMenuLink>
            </NavigationMenuItem>
          </NavigationMenuList>
        </NavigationMenu>

        <div className="flex items-center gap-2"><ThemeToggle /><div className="hidden items-center gap-2 lg:flex">
          {dashboardUrl && <Button variant="ghost" render={<a href={dashboardUrl} />} className="text-foreground hover:bg-muted hover:text-foreground">Dashboard</Button>}
          <Button variant="outline" render={<Link href="/pricing" />} className="border-border bg-card text-foreground hover:bg-muted">
            Design partners
          </Button>
          <Button render={<Link href="/playground" />} className="bg-primary text-primary-foreground hover:bg-primary">
            Playground
          </Button>
        </div>
        <Sheet>
          <SheetTrigger render={<Button variant="outline" size="icon" className="border-border bg-card text-foreground hover:bg-muted lg:hidden" aria-label="Open navigation" />}>
            <Menu className="size-4" />
          </SheetTrigger>
          <SheetContent className="w-[min(22rem,90vw)] border-l border-border bg-background p-0 text-foreground" side="right">
            <SheetHeader className="border-b border-border px-5 py-4">
              <SheetTitle className="text-foreground">Navigate Seclume</SheetTitle>
            </SheetHeader>
            <nav className="flex flex-col gap-1 p-3" aria-label="Mobile navigation">
              <MobileLink href="/product">Product</MobileLink>
              {productLinks.map((link) => <MobileLink key={link.href} href={link.href}>{link.title}</MobileLink>)}
              <MobileLink href="/solutions">Solutions</MobileLink>
              {solutionLinks.map((link) => <MobileLink key={link.href} href={link.href}>{link.title}</MobileLink>)}
              <MobileLink href="/developers">Developers</MobileLink>
              {developerLinks.map((link) => <MobileLink key={link.href} href={link.href}>{link.title}</MobileLink>)}
              <MobileLink href="/trust">Trust &amp; Security</MobileLink>
              {trustLinks.map((link) => <MobileLink key={link.href} href={link.href}>{link.title}</MobileLink>)}
              <MobileLink href="/company">Company</MobileLink>
              {companyLinks.map((link) => <MobileLink key={link.href} href={link.href}>{link.title}</MobileLink>)}
              <MobileLink href="/docs">Docs</MobileLink>
              <MobileLink href="/pricing">Pricing</MobileLink>
              <MobileLink href="/playground">Playground</MobileLink>
              {dashboardUrl && <SheetClose render={<a href={dashboardUrl} />} className="rounded-md px-3 py-2 text-sm font-medium text-foreground transition-colors duration-150 ease-in-out hover:bg-muted hover:text-primary">Dashboard</SheetClose>}
            </nav>
          </SheetContent>
        </Sheet>
        </div>
      </div>
    </header>
  );
}

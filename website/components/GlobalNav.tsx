"use client";

import Link from "next/link";
import {
  ArrowRight,
  Boxes,
  FileCheck2,
  Menu,
  Network,
  ScanSearch,
  ShieldCheck,
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
    <div className="grid w-[min(44rem,calc(100vw-2rem))] grid-cols-[0.8fr_1.2fr] overflow-hidden rounded-xl bg-zinc-900 ring-1 ring-white/10">
      <Link
        href={href}
        className="group flex min-h-72 flex-col justify-between border-r border-white/10 bg-cyan-400/[0.06] p-6 transition-colors duration-150 ease-in-out hover:bg-cyan-400/[0.1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
      >
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">
            {eyebrow}
          </p>
          <p className="mt-3 text-xl font-semibold tracking-tight text-zinc-50">
            {title}
          </p>
        </div>
        <span className="inline-flex items-center gap-2 text-sm font-medium text-cyan-200">
          Explore <ArrowRight className="size-4 transition-transform duration-150 ease-in-out group-hover:translate-x-1" />
        </span>
      </Link>
      <div className="grid content-start gap-1 p-3">
        {links.map(({ title: linkTitle, description, href: linkHref, icon: Icon }) => (
          <NavigationMenuLink
            key={linkHref}
            render={<Link href={linkHref} />}
            closeOnClick
            className="group rounded-lg p-3 hover:bg-white/[0.06] focus:bg-white/[0.06]"
          >
            <Icon className="mt-0.5 size-4 shrink-0 text-cyan-300" aria-hidden="true" />
            <span>
              <span className="block font-medium text-zinc-100">{linkTitle}</span>
              <span className="mt-0.5 block text-xs leading-5 text-zinc-400">{description}</span>
            </span>
          </NavigationMenuLink>
        ))}
      </div>
    </div>
  );
}

function MobileLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <SheetClose render={<Link href={href} />} className="rounded-md px-3 py-2 text-sm font-medium text-zinc-200 transition-colors duration-150 ease-in-out hover:bg-white/[0.06] hover:text-cyan-200">
      {children}
    </SheetClose>
  );
}

export function GlobalNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-zinc-950/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="inline-flex items-center gap-2 font-semibold tracking-tight text-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
          <span className="grid size-7 place-items-center rounded-md bg-cyan-400 font-mono text-sm font-bold text-zinc-950">A</span>
          Aegis
        </Link>

        <NavigationMenu className="hidden lg:flex" align="start">
          <NavigationMenuList className="gap-1">
            <NavigationMenuItem>
              <NavigationMenuTrigger className="text-zinc-300 hover:bg-white/[0.06] hover:text-zinc-50 focus:bg-white/[0.06]">Product</NavigationMenuTrigger>
              <NavigationMenuContent>
                <MegaMenu links={productLinks} eyebrow="Product" title="A data boundary for AI systems." href="/product" />
              </NavigationMenuContent>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuTrigger className="text-zinc-300 hover:bg-white/[0.06] hover:text-zinc-50 focus:bg-white/[0.06]">Trust &amp; Security</NavigationMenuTrigger>
              <NavigationMenuContent>
                <MegaMenu links={trustLinks} eyebrow="Trust" title="Evidence, architecture, and limits." href="/trust" />
              </NavigationMenuContent>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuLink render={<Link href="/docs" />} className="px-2.5 py-1.5 text-zinc-300 hover:bg-white/[0.06] hover:text-zinc-50">
                Docs
              </NavigationMenuLink>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <NavigationMenuLink render={<Link href="/pricing" />} className="px-2.5 py-1.5 text-zinc-300 hover:bg-white/[0.06] hover:text-zinc-50">
                Pricing
              </NavigationMenuLink>
            </NavigationMenuItem>
          </NavigationMenuList>
        </NavigationMenu>

        <div className="hidden items-center gap-2 lg:flex">
          <Button variant="outline" render={<Link href="/pricing" />} className="border-white/10 bg-zinc-900 text-zinc-100 hover:bg-zinc-800">
            Design partners
          </Button>
          <Button render={<Link href="/playground" />} className="bg-cyan-400 text-zinc-950 hover:bg-cyan-300">
            Playground
          </Button>
        </div>

        <Sheet>
          <SheetTrigger render={<Button variant="outline" size="icon" className="border-white/10 bg-zinc-900 text-zinc-100 hover:bg-zinc-800 lg:hidden" aria-label="Open navigation" />}>
            <Menu className="size-4" />
          </SheetTrigger>
          <SheetContent className="w-[min(22rem,90vw)] border-l border-white/10 bg-zinc-950 p-0 text-zinc-50" side="right">
            <SheetHeader className="border-b border-white/10 px-5 py-4">
              <SheetTitle className="text-zinc-50">Navigate Aegis</SheetTitle>
            </SheetHeader>
            <nav className="flex flex-col gap-1 p-3" aria-label="Mobile navigation">
              <MobileLink href="/product">Product</MobileLink>
              {productLinks.map((link) => <MobileLink key={link.href} href={link.href}>{link.title}</MobileLink>)}
              <MobileLink href="/trust">Trust &amp; Security</MobileLink>
              {trustLinks.map((link) => <MobileLink key={link.href} href={link.href}>{link.title}</MobileLink>)}
              <MobileLink href="/docs">Docs</MobileLink>
              <MobileLink href="/pricing">Pricing</MobileLink>
              <MobileLink href="/playground">Playground</MobileLink>
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}

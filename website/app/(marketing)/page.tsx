"use client";

import Link from "next/link";
import {
  ArrowRight,
  Check,
  Container,
  Copy,
  Database,
  Network,
  Server,
  ShieldCheck,
  Terminal,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const composeCommand = "docker compose up";

const problemCards = [
  {
    title: "Transfers need a basis.",
    body: "Section 41 allows personal data to leave Nigeria only on an adequacy basis or a section 43 ground such as informed consent, and requires you to record the basis. Penalties for breach can reach the greater of ₦10m or 2% of annual gross revenue for organisations of major importance.",
  },
  {
    title: "Agents multiply the exposure.",
    body: "Prompts, tool arguments and tool results all carry customer data to an external API.",
  },
  {
    title: "Rewriting prompts by hand does not scale.",
    body: "Custom redaction code is brittle, misses tool calls, and leaves no evidence.",
  },
];

const steps = [
  {
    number: "01",
    title: "Scrub, locally.",
    body: "Rules detect phones, BVN/NIN-format numbers, account numbers (with context) and emails. A name gazetteer and a small local model detect person names. Nothing is sent anywhere for detection.",
    icon: ShieldCheck,
  },
  {
    number: "02",
    title: "Remember, briefly.",
    body: "The mapping from placeholder to real value lives in Redis only, with snapshots and append-only logging disabled and a sliding expiry (default 300 s). Same person, same placeholder, across a conversation.",
    icon: Database,
  },
  {
    number: "03",
    title: "Reinject.",
    body: "Placeholders in the reply, including inside tool-call arguments, are swapped back before your app sees them. If state is lost, Aegis returns placeholders rather than guessing.",
    icon: Network,
  },
];

const evidence = [
  ["Rule layer overhead (60 words)", "p50 0.18 ms, p95 0.68 ms", "bench_scrub.py"],
  ["Model layer overhead (60 words, 4-core CPU)", "p50 429 ms, p95 1271 ms", "bench_scrub.py"],
  ["Leak test", "0 leaks / 35 planted entities across 12 prompts", "test_no_leak.py"],
  ["Per-type recall and precision (held-out set)", "PERSON: 96.9% recall, 61.9% precision", "eval_recall.py"],
];

const deploymentOptions = [
  { icon: Container, label: "Docker image (model included)" },
  { icon: Server, label: "docker compose" },
  { icon: Network, label: "Kubernetes (Helm: roadmap)" },
];

function CopyComposeCommand() {
  async function copyCommand() {
    await navigator.clipboard.writeText(composeCommand);
  }

  return (
    <Button onClick={copyCommand} className="h-10 bg-cyan-400 px-4 font-mono text-sm text-zinc-950 hover:bg-cyan-300">
      <Terminal data-icon="inline-start" />
      {composeCommand}
      <Copy data-icon="inline-end" />
      <span className="sr-only">Copy command</span>
    </Button>
  );
}

export default function HomePage() {
  return (
    <main>
      <section className="relative isolate overflow-hidden px-4 pb-24 pt-24 sm:px-6 lg:pb-32 lg:pt-32">
        <div aria-hidden="true" className="absolute inset-x-0 top-0 -z-10 h-[34rem] bg-[radial-gradient(ellipse_at_top,rgba(6,182,212,0.14),transparent_60%)]" />
        <div className="mx-auto max-w-5xl text-center">
          <p className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-3 py-1 font-mono text-xs text-cyan-200 ring-1 ring-white/10">
            <ShieldCheck className="size-3.5" aria-hidden="true" />
            Open-source PII firewall for AI agents
          </p>
          <h1 className="mx-auto mt-6 max-w-4xl text-balance text-4xl font-semibold tracking-[-0.045em] text-zinc-50 sm:text-6xl lg:text-7xl">
            Keep Nigerian customer identifiers out of your LLM prompts.
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-pretty text-base leading-7 text-zinc-300 sm:text-lg">
            Aegis is an OpenAI-compatible proxy that runs inside your network. It swaps BVNs, NINs, account numbers, phone numbers, emails and names for Placeholders before a request reaches an external model, then puts the real values back in the reply. A Wire Tap shows exactly what left.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <CopyComposeCommand />
            <Button variant="outline" render={<Link href="#evidence" />} className="h-10 border-white/10 bg-zinc-900 px-4 text-zinc-100 hover:bg-zinc-800">
              Read the evidence
              <ArrowRight data-icon="inline-end" />
            </Button>
          </div>
        </div>

        <div className="mx-auto mt-16 max-w-4xl overflow-hidden rounded-xl bg-zinc-900 text-left ring-1 ring-white/10">
          <div className="flex h-10 items-center gap-2 border-b border-white/10 px-4">
            <span className="size-2 rounded-full bg-zinc-600" />
            <span className="size-2 rounded-full bg-zinc-600" />
            <span className="size-2 rounded-full bg-zinc-600" />
            <span className="ml-2 font-mono text-xs text-zinc-500">aegis — Wire Tap preview</span>
          </div>
          <pre className="overflow-x-auto p-5 font-mono text-xs leading-6 sm:p-7 sm:text-sm">
            <code>
              <span className="text-zinc-400"># What your agent sends to Aegis{"\n"}</span>
              <span className="text-rose-300">- [pre-scrub text stays in your network]{"\n"}</span>
              <span className="text-zinc-400"># What the external model receives (Wire Tap){"\n"}</span>
              <span className="text-emerald-300">+ Transfer ₦50,000 to [[PERSON_1]], BVN [[BVN_1]], phone [[PHONE_1]]{"\n"}</span>
              <span className="text-zinc-400"># What your agent gets back{"\n"}</span>
              <span className="text-emerald-300">+ Transfer initiated to Chinedu Okafor.</span>
            </code>
          </pre>
        </div>
      </section>

      <section className="border-y border-white/10 bg-zinc-900/50 px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-7xl">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">NDPA 2023 and GAID 2025</p>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {problemCards.map((card) => (
              <Card key={card.title} className="bg-zinc-900 ring-white/10">
                <CardHeader>
                  <CardTitle className="text-lg text-zinc-50">{card.title}</CardTitle>
                </CardHeader>
                <CardContent className="leading-6 text-zinc-400">{card.body}</CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-7xl">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">How it works</p>
          <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_1.2fr] lg:items-center">
            <div className="space-y-7">
              {steps.map(({ number, title, body, icon: Icon }) => (
                <div key={number} className="grid grid-cols-[2.5rem_1fr] gap-4">
                  <div className="grid size-10 place-items-center rounded-lg bg-zinc-900 font-mono text-xs text-cyan-300 ring-1 ring-white/10">{number}</div>
                  <div>
                    <div className="flex items-center gap-2"><Icon className="size-4 text-cyan-300" /><h2 className="font-medium text-zinc-50">{title}</h2></div>
                    <p className="mt-2 max-w-xl leading-6 text-zinc-400">{body}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="overflow-x-auto rounded-xl bg-zinc-900 p-6 font-mono text-sm leading-8 text-zinc-300 ring-1 ring-white/10 sm:p-8">
              <div className="min-w-[31rem]">
                <p className="text-cyan-300">Agent</p>
                <p className="text-zinc-600">  │ request with identifiers</p>
                <p className="text-cyan-300">  ▼</p>
                <p className="text-zinc-50">Aegis</p>
                <p className="text-zinc-600">  ├─ Scrubber → Placeholders</p>
                <p className="text-zinc-600">  ├─ Session Map → Redis, short expiry</p>
                <p className="text-zinc-600">  └─ Wire Tap → post-scrub evidence</p>
                <p className="text-cyan-300">  ▼</p>
                <p className="text-zinc-50">Upstream</p>
                <p className="text-zinc-600">  │ reply with Placeholders</p>
                <p className="text-cyan-300">  ▼</p>
                <p className="text-zinc-50">Reinjector → Agent</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-white/10 bg-zinc-900/50 px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">One-line integration</p>
            <p className="mt-4 max-w-md leading-7 text-zinc-300">Works with the official OpenAI SDK, including tool calling and stream=True. Anthropic Messages API support: on the roadmap.</p>
          </div>
          <div className="overflow-x-auto rounded-xl bg-zinc-950 p-5 ring-1 ring-white/10 sm:p-7">
            <pre className="font-mono text-sm leading-7 text-zinc-300"><code><span className="text-violet-300">from</span> openai <span className="text-violet-300">import</span> OpenAI{"\n"}client = OpenAI({"\n"}    base_url=<span className="text-emerald-300">{`"http://aegis.internal:8000/v1"`}</span>,   <span className="text-zinc-500"># was https://api.openai.com/v1</span>{"\n"}    api_key=os.environ[<span className="text-emerald-300">{`"OPENAI_API_KEY"`}</span>],{"\n"})</code></pre>
          </div>
        </div>
      </section>

      <section id="evidence" className="px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-5xl">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">Evidence (measured, with hardware and date)</p>
          <div className="mt-7 rounded-xl bg-zinc-900 ring-1 ring-white/10">
            <Table>
              <TableHeader><TableRow><TableHead>Measure</TableHead><TableHead>Result</TableHead><TableHead>Source</TableHead></TableRow></TableHeader>
              <TableBody>{evidence.map(([measure, result, source]) => <TableRow key={measure}><TableCell className="font-medium text-zinc-100">{measure}</TableCell><TableCell className="font-mono tabular-nums text-zinc-300">{result}</TableCell><TableCell className="font-mono text-xs text-cyan-300">{source}</TableCell></TableRow>)}</TableBody>
            </Table>
          </div>
          <p className="mt-5 max-w-3xl text-sm leading-6 text-zinc-400">Numbers are from our own sets on the stated hardware. Deliberate evasion (leetspeak, spelled-out digits) is a known limitation. <Link href="/trust/methodology" className="text-cyan-300 underline-offset-4 hover:underline">Read the methodology.</Link></p>
        </div>
      </section>

      <section className="border-y border-white/10 bg-zinc-900/50 px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-7xl">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">Evidence for the people who sign off.</p>
          <div className="mt-7 grid gap-px overflow-hidden rounded-xl bg-white/10 ring-1 ring-white/10 md:grid-cols-2">
            {[
              "Pseudonymisation as a technical security measure (NDPA s.39(2)(a)).",
              "A record of what crossed the boundary, per request (supports s.41(2) transfer records). Export format: roadmap.",
              "Inputs for your DPIA (s.28) and the cross-border section of your annual compliance audit return. Templates: roadmap.",
              "A live dashboard of counts, timings and post-scrub payloads. It never shows pre-scrub text.",
            ].map((item) => <div key={item} className="flex gap-3 bg-zinc-900 p-5 text-sm leading-6 text-zinc-300"><Check className="mt-0.5 size-4 shrink-0 text-cyan-300" />{item}</div>)}
          </div>
        </div>
      </section>

      <section id="deploy" className="px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-7xl">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-300">Deploy where your data lives</p>
          <div className="mt-7 flex flex-col gap-4 md:flex-row">
            {deploymentOptions.map(({ icon: Icon, label }) => <div key={label} className="flex flex-1 items-center gap-3 rounded-xl bg-zinc-900 p-5 text-zinc-200 ring-1 ring-white/10"><Icon className="size-5 text-cyan-300" />{label}</div>)}
          </div>
          <p className="mt-5 text-zinc-400">Runs in your VPC or on-prem. No telemetry leaves your network.</p>
        </div>
      </section>

      <section className="border-y border-white/10 bg-zinc-900/30 px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-5xl">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-zinc-500">What Aegis does not do</p>
          <div className="mt-7 grid gap-4 md:grid-cols-2">
            {[
              "It does not make a transfer lawful on its own. Pseudonymised data can still be personal data.",
              "Names are detected by a model, so recall is not 100%. Structured IDs are rule-detected.",
              "It does not protect against the upstream provider's own retention. Check your provider terms.",
              "Streaming is currently buffered, not token-by-token.",
            ].map((item) => <div key={item} className="flex gap-3 text-sm leading-6 text-zinc-500"><X className="mt-0.5 size-4 shrink-0" />{item}</div>)}
          </div>
        </div>
      </section>

      <section className="px-4 py-20 sm:px-6 lg:py-28">
        <Card className="mx-auto max-w-5xl bg-zinc-900 ring-cyan-400/50">
          <CardContent className="flex flex-col items-start justify-between gap-6 py-8 sm:flex-row sm:items-end sm:py-10">
            <div>
              <h2 className="max-w-2xl text-2xl font-semibold tracking-tight text-zinc-50 sm:text-3xl">Building with agents in a Nigerian bank, fintech or hospital?</h2>
              <p className="mt-3 max-w-2xl leading-7 text-zinc-400">We are working with a small number of design partners on real formats and real policy needs. Free self-hosted pilot. A human replies within 24 hours.</p>
            </div>
            <Button render={<a href="mailto:?subject=Aegis%20design%20partner&body=[work%20email]%0A[role]%0A[what%20you%20want%20to%20protect]" />} className="bg-cyan-400 text-zinc-950 hover:bg-cyan-300">Apply <ArrowRight data-icon="inline-end" /></Button>
          </CardContent>
        </Card>
      </section>

      <footer className="border-t border-white/10 px-4 py-8 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap gap-x-5 gap-y-2 text-sm text-zinc-500">
          <span>Aegis (open source, MIT)</span><Link href="/security">Security policy</Link><Link href="/trust/methodology">Claims and methodology</Link><a href="https://github.com" rel="noreferrer">GitHub</a><Link href="/trust/status">Status</Link>
        </div>
      </footer>
    </main>
  );
}

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
    body: "Pseudonymisation reduces exposure. It does not make a transfer lawful on its own; each organisation must assess its own requirements.",
  },
  {
    title: "Agents multiply the exposure.",
    body: "Prompts, tool arguments and tool results all carry customer data to an external API.",
  },
  {
    title: "Inspect the boundary.",
    body: "The Wire Tap records what Upstream received after scrubbing.",
  },
];

const steps = [
  {
    number: "1",
    title: "Scrub, locally.",
    body: "Rules detect phones, BVN/NIN-format numbers, account numbers (with context) and emails. A name gazetteer and a small local model detect person names. Nothing is sent anywhere for detection.",
    icon: ShieldCheck,
  },
  {
    number: "2",
    title: "Remember, briefly.",
    body: "The Session Map lives in Redis with snapshots and append-only logging disabled and a sliding expiry. Same person, same Placeholder across a conversation (when the client sends X-Aegis-Session).",
    icon: Database,
  },
  {
    number: "3",
    title: "Reinject.",
    body: "Placeholders in the reply, including inside tool-call arguments, are swapped back before your app sees them. If state is lost, Seclume returns placeholders rather than guessing.",
    icon: Network,
  },
];

const evidence = [
  ["Performance", "Measure rule and model overhead on your own hardware", "bench_scrub.py"],
  ["Leak test", "0 leaks / 35 planted entities across 12 prompts", "test_no_leak.py"],
  ["Per-type recall and precision (synthetic regression set, project-authored)", "PERSON: 96.9% recall, 61.9% precision", "eval_heldout.py"],
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
    <Button onClick={copyCommand} className="h-10 bg-primary px-4 font-sans text-sm text-primary-foreground hover:bg-primary">
      <Terminal data-icon="inline-start" />
      {composeCommand}
      <Copy data-icon="inline-end" />
      <span className="sr-only">Copy command</span>
    </Button>
  );
}

export default function HomePage() {
  return (
    <main id="main-content" className="landing-page">
      <section className="hero-section relative isolate overflow-hidden px-4 pb-24 pt-24 sm:px-6 lg:pb-32 lg:pt-32">        <div className="mx-auto max-w-[1120px] text-left">          <h1 className="hero-title mt-6">
            A data boundary for AI agents.
          </h1>
          <p className="hero-description mt-6 text-muted-foreground">
            An OpenAI- and Anthropic-compatible Proxy that replaces detected Nigerian identifiers with Placeholders before an external model call.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button render={<Link href="/playground" />} className="h-11 bg-primary px-5 text-primary-foreground hover:bg-primary">Try the playground</Button>
            <Button variant="outline" render={<a href="https://github.com/hassanismailtech/seclume" />} className="h-10 border-border bg-card px-4 text-foreground hover:bg-muted">
              View on GitHub
              <ArrowRight data-icon="inline-end" />
            </Button>
          </div>
        </div>

        <div className="mx-auto mt-14 max-w-[1120px] overflow-hidden rounded-xl bg-card text-left ring-1 ring-border">
          <div className="flex h-10 items-center gap-2 border-b border-border px-4">            <span className="ml-2 font-sans text-xs text-muted-foreground">Synthetic Wire Tap example</span>
          </div>
          <pre className="overflow-x-auto p-5 font-mono text-xs leading-6 sm:p-7 sm:text-sm">
            <code>
              <span className="text-muted-foreground"># What the external model receives (Wire Tap){"\n"}</span>
              <span className="text-foreground">+ Transfer ₦50,000 to [[PERSON_1]], BVN [[BVN_1]], phone [[PHONE_1]]{"\n"}</span>
            </code>
          </pre>
        </div>      </section>

      <section className="section-grid bg-muted px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-[1120px]">
          <h2 className="section-title">A boundary you can inspect</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {problemCards.map((card) => (
              <Card key={card.title} className="group bg-card transition-colors duration-150 ease-in-out hover:bg-muted ring-border">
                <CardHeader>
                  <CardTitle className="text-lg text-foreground">{card.title}</CardTitle>
                </CardHeader>
                <CardContent className="leading-6 text-muted-foreground">{card.body}</CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="section-grid px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-[1120px]">
          <h2 className="section-title">How it works</h2>
          <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_1.2fr] lg:items-center">
            <div className="space-y-7">
              {steps.map(({ number, title, body, icon: Icon }) => (
                <div key={number} className="grid grid-cols-[2.5rem_1fr] gap-4">
                  <div className="grid size-10 place-items-center rounded-lg bg-card font-sans text-xs text-primary ring-1 ring-border">{number}</div>
                  <div>
                    <div className="flex items-center gap-2"><Icon className="size-4 text-primary" /><h3 className="text-lg font-medium text-foreground">{title}</h3></div>
                    <p className="mt-2 max-w-xl leading-6 text-muted-foreground">{body}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="overflow-x-auto rounded-xl bg-card p-6 font-sans text-sm leading-8 text-foreground ring-1 ring-border sm:p-8">
              <div className="min-w-0">
                <p className="text-primary">Agent</p>
                <p className="text-muted-foreground">  │ request with identifiers</p>
                <p className="text-primary">  ▼</p>
                <p className="text-foreground">Seclume</p>
                <p className="text-muted-foreground">  ├─ Scrubber → Placeholders</p>
                <p className="text-muted-foreground">  ├─ Session Map → Redis, short expiry</p>
                <p className="text-muted-foreground">  └─ Wire Tap → post-scrub evidence</p>
                <p className="text-primary">  ▼</p>
                <p className="text-foreground">Upstream</p>
                <p className="text-muted-foreground">  │ reply with Placeholders</p>
                <p className="text-primary">  ▼</p>
                <p className="text-foreground">Reinjector → Agent</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className=" bg-muted px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto grid max-w-[1120px] gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div>
            <h2 className="section-title">Start with your SDK</h2>
            <p className="mt-4 max-w-md leading-7 text-foreground">Works with the official OpenAI SDK and Anthropic SDK, including streaming and tool calls.</p><div className="mt-6"><CopyComposeCommand /></div>
          </div>
          <div className="overflow-x-auto rounded-xl bg-background p-5 ring-1 ring-border sm:p-7">
            <pre className="font-mono text-sm leading-7 text-foreground"><code><span className="text-foreground">from</span> openai <span className="text-foreground">import</span> OpenAI{"\n"}client = OpenAI({"\n"}    base_url=<span className="text-foreground">{`"http://aegis.internal:8000/v1"`}</span>,   <span className="text-muted-foreground"># was https://api.openai.com/v1</span>{"\n"}    api_key=os.environ[<span className="text-foreground">{`"OPENAI_API_KEY"`}</span>],{"\n"})</code></pre>
          </div>
        </div>
      </section>

      <section id="evidence" className="px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-5xl">
          <h2 className="section-title">Measured, with limits</h2>
          <div className="mt-7 rounded-xl bg-card ring-1 ring-border">
            <Table>
              <TableHeader><TableRow><TableHead>Measure</TableHead><TableHead>Result</TableHead><TableHead>Source</TableHead></TableRow></TableHeader>
              <TableBody>{evidence.map(([measure, result, source]) => <TableRow key={measure}><TableCell className="font-medium text-foreground">{measure}</TableCell><TableCell className="font-sans tabular-nums text-foreground">{result}</TableCell><TableCell className="font-sans text-xs text-primary"><a href={"https://github.com/hassanismailtech/seclume/blob/main/backend/" + (source.startsWith("test_") ? "tests/" : "scripts/") + source} className="hover:underline">{source}</a></TableCell></TableRow>)}</TableBody>
            </Table>
          </div>
          <p className="mt-5 max-w-3xl text-sm leading-6 text-muted-foreground">Results come from our synthetic, project-authored sets, not an independent audit. Deliberate evasion (leetspeak, spelled-out digits) is a known limitation. <Link href="/trust/methodology" className="text-primary underline-offset-4 hover:underline">Read the methodology.</Link></p>
        </div>
      </section>

      <section className=" bg-muted px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-[1120px]">
          <h2 className="section-title">Security and trust</h2>
          <div className="mt-7 grid gap-px overflow-hidden rounded-xl bg-border ring-1 ring-border md:grid-cols-2">
            {[
              "Authentication is off unless AEGIS_KEYS_FILE is configured.",
              "The Wire Tap records post-scrub requests for internal review.",
              "Session Map state is temporary Redis state; existing audit metadata is persisted separately.",
              "A live dashboard of counts, timings and post-scrub payloads. It never shows pre-scrub text.",
            ].map((item) => <div key={item} className="flex gap-3 bg-card p-5 text-sm leading-6 text-foreground"><Check className="mt-0.5 size-4 shrink-0 text-primary" />{item}</div>)}
          </div>
        </div>
      </section>

      <section id="deploy" className="px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-[1120px]">
          <h2 className="section-title">Deploy inside your network</h2>
          <div className="mt-7 flex flex-col gap-4 md:flex-row">
            {deploymentOptions.map(({ icon: Icon, label }) => <div key={label} className="flex flex-1 items-center gap-3 rounded-xl bg-card p-5 text-foreground ring-1 ring-border"><Icon className="size-5 text-primary" />{label}</div>)}
          </div>
          <p className="mt-5 text-muted-foreground">Runs in your VPC or on-prem. Telemetry is self-hosted; the synthetic playground emits no Telemetry Events.</p>
        </div>
      </section>

      <section className=" bg-muted px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-5xl">
          <h2 className="section-title">Known limitations</h2>
          <div className="mt-7 grid gap-4 md:grid-cols-2">
            {[
              "It does not make a transfer lawful on its own. Pseudonymised data can still be personal data.",
              "Names are detected by a model, so recall is not 100%. Structured IDs are rule-detected.",
              "It does not protect against the upstream provider's own retention. Check your provider terms.",
              "Streaming holds back incomplete Placeholders; it does not wait for the whole reply.",
            ].map((item) => <div key={item} className="flex gap-3 text-sm leading-6 text-muted-foreground"><X className="mt-0.5 size-4 shrink-0" />{item}</div>)}
          </div>
        </div>
      </section>

      <section className="px-4 py-20 sm:px-6 lg:py-28">
        <Card className="mx-auto max-w-5xl bg-card ring-ring">
          <CardContent className="flex flex-col items-start justify-between gap-6 py-8 sm:flex-row sm:items-end sm:py-10">
            <div>
              <h2 className="max-w-2xl text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">Build with Seclume.</h2>
              <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">We are looking for a small number of design partners to test Seclume on real formats and policy needs. Free self-hosted pilot.</p>
            </div>
            <Button render={<Link href="/company/design-partners" />} className="bg-primary text-primary-foreground hover:bg-primary">Explore the pilot <ArrowRight data-icon="inline-end" /></Button>
          </CardContent>
        </Card>
      </section>

    </main>
  );
}

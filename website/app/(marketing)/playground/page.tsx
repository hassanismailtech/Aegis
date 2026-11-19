"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { ENTITY_TYPES, EXAMPLES, MAX_CHARS, playgroundEndpoint, scrubPlayground, splitPlaceholders, type PlaygroundResult } from "@/lib/playground";

const apiBase = process.env.NEXT_PUBLIC_PLAYGROUND_API;

function Output({ title, text }: { title: string; text: string | undefined }) {
  return (
    <section className="min-w-0 rounded-xl border border-border bg-muted p-5">
      <h2 className="mb-4 font-medium text-foreground">{title}</h2>
      <p className="min-h-28 whitespace-pre-wrap break-words font-sans text-sm leading-7 text-foreground">
        {text === undefined ? "Submit a synthetic example to see the result." : splitPlaceholders(text).map((part, index) =>
          part.placeholder ? <mark key={index} className="rounded bg-muted px-1 text-primary">{part.text}</mark> : part.text)}
      </p>
    </section>
  );
}

export default function PlaygroundPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<PlaygroundResult>();
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const active = useRef<AbortController | null>(null);
  const available = playgroundEndpoint(apiBase) !== null;

  useEffect(() => () => {
    active.current?.abort();
    active.current = null;
  }, []);

  function changeText(value: string) {
    setText(value);
    setResult(undefined);
    setMessage("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setPending(true);
    setResult(undefined);
    setMessage("");
    const timeout = setTimeout(() => controller.abort(), 15000);
    const response = await scrubPlayground(apiBase, text, controller.signal);
    clearTimeout(timeout);
    if (active.current !== controller || controller.signal.aborted) {
      if (active.current === controller) {
        setMessage("The request timed out. Please try again.");
        setPending(false);
      }
      return;
    }
    active.current = null;
    if (response.ok) setResult(response.result);
    else setMessage(response.message);
    setPending(false);
  }

  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
      <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">Interactive playground</p>
      <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">See the Scrubber at work.</h1>
      <p className="mt-5 max-w-2xl text-lg leading-8 text-muted-foreground">Try synthetic text, inspect the Placeholders, and see a simulated reply. No model is called to generate the reply.</p>
      <aside className="mt-8 rounded-xl border border-border bg-muted p-5 text-sm leading-6 text-foreground">
        <strong>Synthetic data only.</strong> Do not enter real names, contact details, or identifiers. Use a private, self-hosted instance for real data. Detection has limits; review the output.
      </aside>
      {!available && <p role="status" className="mt-6 rounded-lg border border-border p-4 text-foreground">Coming soon. The playground API is not configured for this site.</p>}
      <form onSubmit={submit} className="mt-8" aria-busy={pending}>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="mr-2 text-sm text-muted-foreground">Load an example</span>
          {EXAMPLES.map(example => <Button key={example.label} type="button" variant="outline" size="sm" disabled={pending} onClick={() => changeText(example.text)}>{example.label}</Button>)}
        </div>
        <label htmlFor="playground-input" className="block font-medium text-foreground">Synthetic input</label>
        <textarea id="playground-input" value={text} onChange={event => changeText(event.target.value)} maxLength={MAX_CHARS} disabled={pending}
          autoComplete="off" spellCheck={false} aria-describedby="input-limit"
          className="mt-3 min-h-44 w-full resize-y rounded-xl border border-input bg-background p-4 text-sm leading-7 text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-60" />
        <div className="mt-3 flex items-center justify-between gap-4">
          <p id="input-limit" className="text-sm text-muted-foreground">{text.length} / {MAX_CHARS} characters</p>
          <Button type="submit" disabled={!available || pending || !text.trim()}>{pending ? "Scrubbing…" : "Scrub example"}</Button>
        </div>
      </form>
      <div className="mt-4 min-h-6 text-sm" aria-live="polite" aria-atomic="true">
        {pending && <p role="status" className="text-muted-foreground">Waiting for the Scrubber…</p>}
        {message && <p role="alert" className="text-foreground">{message}</p>}
        {result && <p className="text-muted-foreground">Result ready · Mode: {result.mode} · Scrubber time: {result.overhead_ms.toFixed(2)} ms</p>}
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <Output title="Scrubbed input" text={result?.scrubbed} />
        <Output title="Simulated reply" text={result?.simulated_reply} />
      </div>
      {result && <section className="mt-6 overflow-hidden rounded-xl border border-border">
        <table className="w-full text-left text-sm">
          <caption className="border-b border-border p-4 text-left font-medium text-foreground">Detected entities</caption>
          <thead className="bg-card text-muted-foreground"><tr><th scope="col" className="px-4 py-3">Type</th><th scope="col" className="px-4 py-3 text-right">Count</th></tr></thead>
          <tbody>{ENTITY_TYPES.map(type => <tr key={type} className="border-t border-border text-foreground"><th scope="row" className="px-4 py-3 font-sans font-normal">{type}</th><td className="px-4 py-3 text-right tabular-nums">{result.counts[type]}</td></tr>)}</tbody>
        </table>
      </section>}
      <p className="mt-6 text-sm leading-6 text-muted-foreground">The API uses a temporary Session Map in Redis and requests cleanup after each call, with a short TTL as a fallback. Playground requests emit no Telemetry Events. This page keeps input and results in memory while open.</p>
    </main>
  );
}

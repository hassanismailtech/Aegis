export function GET() {
  return new Response(
    "Contact: mailto:security@aegisproxy.dev\nPolicy: https://aegisproxy.dev/trust/security\nPreferred-Languages: en\n",
    { headers: { "Content-Type": "text/plain; charset=utf-8" } },
  );
}

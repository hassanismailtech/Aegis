export function GET() {
  return new Response(
    "Contact: https://github.com/hassanismailtech/Aegis/security/advisories/new\nPolicy: https://github.com/hassanismailtech/Aegis/security/policy\nPreferred-Languages: en\n",
    { headers: { "Content-Type": "text/plain; charset=utf-8" } },
  );
}

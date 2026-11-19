export function GET() {
  let canonical = "";
  try {
    const url = new URL("/.well-known/security.txt", process.env.NEXT_PUBLIC_SITE_URL);
    if (url.protocol === "https:" && !url.username && !url.password) canonical = `Canonical: ${url.href}\n`;
  } catch {
    // No verified site origin is configured; do not advertise an invented URL.
  }
  return new Response(
    "Contact: https://github.com/hassanismailtech/Aegis/security/advisories/new\nExpires: 2027-11-18T00:00:00.000Z\nPolicy: https://github.com/hassanismailtech/Aegis/security/policy\nPreferred-Languages: en\n" + canonical,
    { headers: { "Content-Type": "text/plain; charset=utf-8" } },
  );
}

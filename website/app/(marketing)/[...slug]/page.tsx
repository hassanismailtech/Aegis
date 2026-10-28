import { notFound } from "next/navigation";

import { MarketingPage } from "@/components/MarketingPage";
import { marketingPaths, sitePages } from "@/lib/site-content";

export function generateStaticParams() {
  return marketingPaths
    .filter((path) => !["pricing", "playground"].includes(path))
    .map((path) => ({ slug: path.split("/") }));
}

export default async function SitePage({ params }: PageProps<"/[...slug]">) {
  const { slug } = await params;
  const page = sitePages[slug.join("/")];

  if (!page) notFound();

  return <MarketingPage page={page} />;
}

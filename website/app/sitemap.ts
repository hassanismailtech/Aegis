import type { MetadataRoute } from "next";

import { marketingPaths } from "@/lib/site-content";

export default function sitemap(): MetadataRoute.Sitemap {
  const origin = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aegisproxy.dev";
  return ["", ...marketingPaths].map((path) => ({
    url: new URL(path ? `/${path}` : "/", origin).toString(),
    lastModified: new Date(),
  }));
}

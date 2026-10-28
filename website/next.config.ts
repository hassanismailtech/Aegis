import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  async redirects() {
    return [
      { source: "/security", destination: "/trust/security", permanent: true },
      { source: "/compliance/ndpa", destination: "/trust/frameworks/ndpa-2023", permanent: true },
      { source: "/privacy", destination: "/legal/privacy", permanent: true },
      { source: "/terms", destination: "/legal/terms", permanent: true },
      { source: "/acceptable-use", destination: "/legal/acceptable-use", permanent: true },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

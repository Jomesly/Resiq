import type { NextConfig } from "next";

const release = process.env.RESIQ_RELEASE === "true";
const api = process.env.NEXT_PUBLIC_API_URL;
if (release && (process.env.NEXT_PUBLIC_DEMO_MODE === "true" || !api || !/^https:\/\/[^/]+\/?$/.test(api))) {
  throw new Error("Release builds require NEXT_PUBLIC_API_URL as an HTTPS origin and demo mode disabled.");
}

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  devIndicators: false,
  output: process.env.RESIQ_STANDALONE === "true" ? "standalone" : undefined,
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Content-Security-Policy", value: "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'" },
    ] }];
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

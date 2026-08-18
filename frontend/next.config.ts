import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  async redirects() {
    return [{ source: "/index", destination: "/indexing", permanent: false }];
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a minimal standalone build — required for Docker production image.
  // Output: .next/standalone/ + .next/static/
  output: "standalone",
};

export default nextConfig;

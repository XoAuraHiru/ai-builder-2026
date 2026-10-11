import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Trace from this app folder so .next/standalone/server.js sits at the root of the standalone output.
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;

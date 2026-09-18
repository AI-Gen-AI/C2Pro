import webpack from "next/dist/compiled/webpack/webpack-lib.js";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../..");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: repoRoot,
  turbopack: {
    root: repoRoot,
  },
  transpilePackages: ["react-pdf", "pdfjs-dist"],
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    config.resolve.alias["pdfjs-dist$"] = resolve(
      __dirname,
      "node_modules/pdfjs-dist/legacy/build/pdf.mjs",
    );
    config.plugins.push(
      new webpack.IgnorePlugin({
        resourceRegExp: /__mocks__/,
      }),
    );
    return config;
  },
  async rewrites() {
    return [
      {
        source: "/tunnel",
        destination:
          "https://o4510540096077824.ingest.de.sentry.io/api/4510804751089744/envelope/?hsts=0",
      },
    ];
  },
};

export default nextConfig;

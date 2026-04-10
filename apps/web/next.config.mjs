import webpack from "next/dist/compiled/webpack/webpack-lib.js";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../..");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  turbopack: {
    root: repoRoot,
  },
  transpilePackages: ["react-pdf", "pdfjs-dist"],
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    config.plugins.push(
      new webpack.IgnorePlugin({
        resourceRegExp: /__mocks__/,
      }),
    );
    return config;
  },
  async redirects() {
    return [
      {
        source: "/dashboard",
        destination: "/",
        permanent: true,
      },
      {
        source: "/dashboard/:path*",
        destination: "/:path*",
        permanent: true,
      },
    ];
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

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
  webpack: (config, { dev, isServer }) => {
    if (dev && !isServer) {
      // pdfjs-dist ships prebuilt, self-bundled Webpack output (build/pdf.mjs
      // embeds its own nested __webpack_require__). Under Next's dev-mode
      // eval-source-map devtool, webpack's harmony-namespace runtime throws
      // "TypeError: Object.defineProperty called on non-object" evaluating
      // that nested module -- this is webpack/webpack#20095, fixed upstream
      // by webpack/webpack#20097 ("rename nested webpack export"). Next's
      // bundled webpack does not yet include that fix, so the client dev
      // bundle here substitutes a plain SourceMapDevToolPlugin for Next's
      // eval-based one to avoid exercising the broken code path. Re-evaluate
      // and remove this once Next's vendored webpack contains #20097.
      config.plugins = config.plugins.filter(
        (plugin) => plugin?.constructor?.name !== "EvalSourceMapDevToolPlugin",
      );
      config.plugins.push(
        new webpack.SourceMapDevToolPlugin({
          filename: "[file].map",
          moduleFilenameTemplate: config.output?.devtoolModuleFilenameTemplate,
        }),
      );
    }
    config.resolve.alias.canvas = false;
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

const webpack = require("webpack");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
        permanent: false,
      },
      {
        source: "/dashboard/:path*",
        destination: "/:path*",
        permanent: false,
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

module.exports = nextConfig;

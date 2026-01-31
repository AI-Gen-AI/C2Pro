/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["react-pdf", "pdfjs-dist"],
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    return config;
  },
  async rewrites() {
    return [
      {
        source: "/tunnel",
        destination: "https://o4510540096077824.ingest.de.sentry.io/api/4510804751089744/envelope/?hsts=0",
      },
    ];
  },
};

module.exports = nextConfig;

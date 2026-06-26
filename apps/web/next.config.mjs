/** @type {import('next').NextConfig} */
const nextConfig = {
  ...(process.env.NEXT_OUTPUT_STANDALONE === "true" ? { output: "standalone" } : {}),
  transpilePackages: ["@manga-ai/shared"],
  webpack: (config) => {
    config.resolve.alias = {
      ...(config.resolve.alias ?? {}),
      canvas: false
    };
    return config;
  }
};

export default nextConfig;

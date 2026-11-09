/** Static export: the FastAPI container serves the built pages from the same hostname.
 * No node runtime in production — one less process on a host shared with a paying product.
 * Lint is its own gate step (npm run lint, scripts/quality_gate.py), not a build side effect. */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  eslint: { ignoreDuringBuilds: true },
};
export default nextConfig;

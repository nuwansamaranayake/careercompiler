/** Static export: the FastAPI container serves the built pages from the same hostname.
 * No node runtime in production — one less process on a host shared with a paying product. */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};
export default nextConfig;

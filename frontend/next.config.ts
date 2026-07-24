import type { NextConfig } from "next";
import withPWA from "@ducanh2912/next-pwa";

const nextConfig: NextConfig = {};

const pwa = withPWA({
  dest: "public",
});

export default pwa(nextConfig);

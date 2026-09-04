import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['192.168.100.22', '192.168.100.*', '192.168.*.*', '*.local', 'localhost:3000'],
};

export default nextConfig;

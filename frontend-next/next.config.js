/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    const target =
      process.env.NEXT_PUBLIC_DEV_API_PROXY_TARGET ||
      process.env.NEXT_PUBLIC_CONTROL_PLANE_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      'http://localhost:8080'
    return [
      {
        source: '/api/:path*',
        destination: `${target}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig

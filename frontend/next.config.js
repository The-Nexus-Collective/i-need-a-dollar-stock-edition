/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  
  // Proxy WebSocket connections to the backend service
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8081'
    return [
      // WebSocket endpoints - proxy to backend
      {
        source: '/ws/:path*',
        destination: `${backendUrl}/ws/:path*`,
      },
      // Also proxy API calls for consistency
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
    ]
  },
  
  // Make backend URL available at runtime for WebSocket
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.BACKEND_URL || '',
  },
}

module.exports = nextConfig

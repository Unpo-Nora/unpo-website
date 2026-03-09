/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    rewrites: async () => {
        return [
            {
                source: '/api/:path*',
                destination: process.env.BACKEND_URL || 'http://127.0.0.1:8000/:path*', // Docker or Local
            },
        ]
    },
    images: {
        remotePatterns: [
            {
                protocol: 'https',
                hostname: 'images.unsplash.com',
            },
        ],
    },
};

export default nextConfig;

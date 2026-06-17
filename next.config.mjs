/** @type {import('next').NextConfig} */
const nextConfig = {
    // Ensure we can use the Python API
    rewrites: async () => {
        return [
            {
                source: '/api/:path*',
                destination: '/api/:path*',
            },
        ];
    },
};

export default nextConfig;

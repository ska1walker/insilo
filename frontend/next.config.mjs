/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",   // notwendig für Docker-Image-Optimierung

  // Wir wollen unter keinen Umständen versehentlich externe Resources laden
  poweredByHeader: false,

  // Bilder: nur eigene Quellen erlauben
  images: {
    remotePatterns: [
      // Hier nichts eintragen — wir hosten alle Bilder selbst.
    ],
  },

  // Strikte Header für DSGVO/Sicherheit
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(self), geolocation=()",
          },
        ],
      },
    ];
  },

  experimental: {
    // Server Actions für Form-Submits
    serverActions: {
      bodySizeLimit: "500mb",
    },
  },

  // Browser ruft /api/* auf derselben Domain wie das Frontend.
  // Next.js Server (im Pod) proxied über Cluster-DNS zum Backend.
  // Vorteile: kein CORS, kein zweiter Authelia-Hop, kein separater api-Entrance nötig.
  // INSILO_BACKEND_INTERNAL kann im Deployment überschrieben werden; default = K8s-DNS.
  async rewrites() {
    const backend =
      process.env.INSILO_BACKEND_INTERNAL ?? "http://insilo-backend:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
    ];
  },
};

export default nextConfig;

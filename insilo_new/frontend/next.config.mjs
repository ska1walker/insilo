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
};

export default nextConfig;

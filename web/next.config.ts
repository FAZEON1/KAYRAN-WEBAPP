import type { NextConfig } from "next";

// Tarayıcı yalnız bu siteyle konuşur: /api/* istekleri sunucu tarafında KAYRAN API'ye (Render) aktarılır.
// Böylece oturum çerezi bu alan adında kalır, ayrı alan adı / CORS ayarı gerekmez.
const API = process.env.API_URL || "http://127.0.0.1:8000";

const ayar: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:yol*", destination: `${API}/:yol*` }];
  },
  async headers() {
    return [
      {
        source: "/:yol*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default ayar;

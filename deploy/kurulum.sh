#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# KAYRAN WEBAPP — VPS kurulum (tek sefer çalıştırılır, Ubuntu 22.04/24.04)
# Kullanım (sunucuda root olarak):
#   bash <(curl -fsSL https://raw.githubusercontent.com/FAZEON1/KAYRAN-WEBAPP/main/deploy/kurulum.sh)
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="https://github.com/FAZEON1/KAYRAN-WEBAPP.git"
KOK="/opt/kayran"
APP="$KOK/app"

echo "══════ KAYRAN WEBAPP VPS kurulumu ══════"

# ── 1) Docker + git + güvenlik duvarı ──
if ! command -v docker >/dev/null 2>&1; then
    echo "→ Docker kuruluyor…"
    curl -fsSL https://get.docker.com | sh
fi
apt-get update -qq && apt-get install -y -qq git ufw cron >/dev/null

echo "→ Güvenlik duvarı: yalnız SSH(22), HTTP(80), HTTPS(443) açık"
ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

# ── 2) Kodu çek ──
mkdir -p "$KOK"
if [ -d "$APP/.git" ]; then
    echo "→ Kod zaten var, güncelleniyor…"; git -C "$APP" pull --ff-only
else
    echo "→ Kod indiriliyor…"; git clone "$REPO" "$APP"
fi

# ── 3) Alan adı (opsiyonel) ──
echo
read -r -p "Alan adı (örn. app.fazeon.com — HTTPS için; boş bırakılırsa IP+HTTP modu): " DOMAIN || DOMAIN=""
if [ -n "${DOMAIN:-}" ]; then
    cat > "$KOK/Caddyfile" <<EOF
$DOMAIN {
    reverse_proxy app:8501
}
EOF
    echo "  ✓ HTTPS otomatik kurulacak (Let's Encrypt) — DNS A kaydının bu sunucuyu göstermesi şart."
else
    cat > "$KOK/Caddyfile" <<'EOF'
:80 {
    reverse_proxy app:8501
}
EOF
    echo "  ✓ HTTP modu — uygulamaya http://SUNUCU_IP ile girilecek."
fi

# ── 4) docker-compose ──
cat > "$KOK/docker-compose.yml" <<'EOF'
services:
  app:
    build:
      context: /opt/kayran/app
      dockerfile: deploy/Dockerfile
    restart: unless-stopped
    volumes:
      - /opt/kayran/secrets.toml:/app/.streamlit/secrets.toml:ro
    expose:
      - "8501"

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /opt/kayran/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
EOF

# ── 5) Secrets ──
if [ ! -s "$KOK/secrets.toml" ]; then
    cat > "$KOK/secrets.toml" <<'EOF'
# ═══ BURAYA Streamlit Cloud'daki Secrets içeriğini AYNEN yapıştır ═══
# (share.streamlit.io → uygulama → Settings → Secrets → tümünü kopyala)
# [supabase] url/key, [kullanicilar], [sirket] blokları — hepsi.
# Bu satırları silip yerine yapıştır, sonra Ctrl+O Enter Ctrl+X ile kaydet.
EOF
    echo
    echo "→ ŞİMDİ secrets dosyası açılacak. Streamlit Cloud'daki Secrets'ı yapıştır,"
    echo "  kaydet-çık: Ctrl+O, Enter, Ctrl+X"
    read -r -p "  Hazırsan Enter'a bas…" _
    nano "$KOK/secrets.toml"
fi

# ── 6) Başlat ──
echo "→ Uygulama derleniyor ve başlatılıyor (ilk sefer 3-5 dk sürebilir)…"
docker compose -f "$KOK/docker-compose.yml" up -d --build

# ── 7) Otomatik güncelleme: her 5 dk'da GitHub'a bak, commit varsa yeniden kur ──
chmod +x "$APP/deploy/guncelle.sh"
cat > /etc/cron.d/kayran-guncelle <<'EOF'
*/5 * * * * root /opt/kayran/app/deploy/guncelle.sh >> /var/log/kayran-guncelle.log 2>&1
EOF
chmod 644 /etc/cron.d/kayran-guncelle

IP=$(curl -fs ifconfig.me || hostname -I | awk '{print $1}')
echo
echo "══════════════════════ KURULUM TAMAM ══════════════════════"
if [ -n "${DOMAIN:-}" ]; then
    echo "  Adres  : https://$DOMAIN   (DNS yayıldıysa 1-2 dk içinde açılır)"
else
    echo "  Adres  : http://$IP"
fi
echo "  Güncelleme: GitHub'a her commit ~5 dk içinde canlıya alınır (otomatik)"
echo "  Loglar : docker compose -f $KOK/docker-compose.yml logs -f app"
echo "  Yeniden başlat: docker compose -f $KOK/docker-compose.yml restart app"
echo "═══════════════════════════════════════════════════════════"

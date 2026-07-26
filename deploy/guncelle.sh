#!/usr/bin/env bash
# GitHub'da yeni commit varsa çeker ve uygulamayı yeniden kurar.
# /etc/cron.d/kayran-guncelle tarafından 5 dakikada bir çağrılır.
set -euo pipefail

APP="/opt/kayran/app"
COMPOSE="/opt/kayran/docker-compose.yml"
KILIT="/tmp/kayran-guncelle.lock"

# Aynı anda iki güncelleme çalışmasın
exec 9>"$KILIT"
flock -n 9 || exit 0

cd "$APP"
git fetch origin main --quiet

YEREL=$(git rev-parse HEAD)
UZAK=$(git rev-parse origin/main)

if [ "$YEREL" = "$UZAK" ]; then
    exit 0                       # değişiklik yok — sessizce çık
fi

echo "[$(date '+%F %T')] Yeni commit: ${UZAK:0:7} — güncelleniyor…"
git reset --hard origin/main --quiet
docker compose -f "$COMPOSE" up -d --build
echo "[$(date '+%F %T')] ✅ Canlıya alındı: ${UZAK:0:7}"

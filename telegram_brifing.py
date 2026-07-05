"""
telegram_brifing.py — KAYRAN Sabah Brifingi
Her sabah GitHub Actions tarafından çalıştırılır; kasa, bugün vadeli,
gecikmiş ödemeler ve hafta ilerlemesini Telegram'a gönderir.

Veri mantığı UYGULAMANIN KENDİSİNDEN gelir (kayranacc.database +
shared.utils.vade_durumu) → brifing ile ekrandaki rakamlar asla ayrışmaz.

Gerekli ortam değişkenleri (GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN   BotFather'dan alınan token
  TELEGRAM_CHAT_ID     Alıcı chat id (virgülle birden çok kişi olabilir)
Supabase erişimi: iş akışı .streamlit/secrets.toml dosyasını yazar,
uygulamanın kendi get_client() fonksiyonu onu okur.
"""
import os
import sys
import html

# Repo kökünü import yoluna ekle (Actions'ta script kökten çalışır ama garanti olsun)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def fmt(n):
    """1.234.567,89 biçimi (uygulamadaki gösterimle aynı)."""
    try:
        return f"{float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def mesaj_kur(hafta, odemeler, bankalar, bugun_str):
    """Saf fonksiyon: veriden Telegram HTML mesajı üretir (test edilebilir)."""
    from shared.utils import vade_durumu

    e = html.escape

    # ── Kasa ──
    tl = sum(float(b.get("bakiye") or 0) for b in bankalar
             if b.get("para_birimi") == "TL")
    usd = sum(float(b.get("bakiye") or 0) for b in bankalar
              if b.get("para_birimi") == "USD")

    # ── Ödemeler (aktif hafta — dashboard ile aynı kaynak) ──
    bekleyen = [o for o in odemeler if o.get("durum") != "odendi"]
    gecmis = [o for o in bekleyen if vade_durumu(o.get("vade")) == "gecmis"]
    bugun = [o for o in bekleyen if vade_durumu(o.get("vade")) == "bugun"]
    yarin = [o for o in bekleyen if vade_durumu(o.get("vade")) == "yarin"]

    def toplam_tl(liste):
        return sum(float(o.get("tutar_tl") or 0) for o in liste)

    def toplam_usd(liste):
        return sum(float(o.get("tutar_usd") or 0) for o in liste)

    def tutar_str(liste):
        t, u = toplam_tl(liste), toplam_usd(liste)
        parca = []
        if t:
            parca.append(f"₺{fmt(t)}")
        if u:
            parca.append(f"${fmt(u)}")
        return " + ".join(parca) if parca else "—"

    odendi_cnt = sum(1 for o in odemeler if o.get("durum") == "odendi")
    toplam_cnt = len(odemeler)
    pct = round(odendi_cnt / toplam_cnt * 100) if toplam_cnt else 0

    hafta_adi = e((hafta or {}).get("hafta_adi", "") or "Aktif hafta yok")

    satirlar = [
        f"☀️ <b>Günaydın İbrahim</b> — {e(bugun_str)}",
        f"📅 <i>{hafta_adi}</i>",
        "",
        f"🏦 <b>Kasa:</b> ₺{fmt(tl)}  ·  ${fmt(usd)}",
        f"📈 <b>Hafta ilerlemesi:</b> {odendi_cnt}/{toplam_cnt} ödeme (%{pct})",
        "",
    ]

    if gecmis:
        satirlar.append(f"🚨 <b>Gecikmiş:</b> {len(gecmis)} ödeme — {tutar_str(gecmis)}")
    if bugun:
        satirlar.append(f"⚠️ <b>Bugün vadeli:</b> {len(bugun)} ödeme — {tutar_str(bugun)}")
        for o in bugun[:5]:
            satirlar.append(f"   • {e(str(o.get('firma') or '')[:34])} — {tutar_str([o])}")
    if yarin:
        satirlar.append(f"🔵 <b>Yarın vadeli:</b> {len(yarin)} ödeme — {tutar_str(yarin)}")
    if not (gecmis or bugun or yarin):
        satirlar.append("✅ Bugün ve yarın vadesi gelen ödeme yok. Rahat bir gün!")

    satirlar += ["", "— KAYRAN Workspace"]
    return "\n".join(satirlar)


def gonder(mesaj):
    """Mesajı TELEGRAM_CHAT_ID içindeki tüm alıcılara gönderir."""
    import requests

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_ids = [c.strip() for c in os.environ["TELEGRAM_CHAT_ID"].split(",") if c.strip()]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    hata = None
    for cid in chat_ids:
        r = requests.post(url, json={
            "chat_id": cid,
            "text": mesaj,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=20)
        if not r.ok:
            hata = f"chat_id={cid} → {r.status_code}: {r.text[:200]}"
            print("HATA:", hata)
        else:
            print(f"gönderildi → chat_id={cid}")
    if hata:
        raise SystemExit(1)


def main():
    from shared.utils import tr_now
    from kayranacc.database import get_aktif_hafta, get_hafta_odemeler, get_bankalar

    hafta = get_aktif_hafta()
    odemeler = get_hafta_odemeler(hafta["id"]) if hafta else []
    bankalar = get_bankalar() or []

    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    simdi = tr_now()
    bugun_str = f"{simdi.strftime('%d.%m.%Y')} {gunler[simdi.weekday()]}"

    mesaj = mesaj_kur(hafta, odemeler, bankalar, bugun_str)
    print("── MESAJ ──\n" + mesaj + "\n───────────")
    gonder(mesaj)


if __name__ == "__main__":
    main()

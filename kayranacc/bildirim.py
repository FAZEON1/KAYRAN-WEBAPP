"""
bildirim.py — KAYRANACC Email Bildirim Modülü
Vade yaklaşan ve gecikmiş ödemeleri email ile bildirir.
"""
import smtplib
import ssl
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
from io import BytesIO
import pandas as pd


# ── YARDIMCI ──────────────────────────────────────────────────────────

def fmt(n):
    if n is None:
        return "-"
    try:
        return f"{float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_tarih(s):
    if not s:
        return ""
    try:
        return pd.to_datetime(s).strftime("%d.%m.%Y")
    except Exception:
        return str(s)


def vade_durumu(vade_str):
    if not vade_str:
        return "normal"
    try:
        v = pd.to_datetime(vade_str).date()
        today = date.today()
        if v < today:
            return "gecmis"
        elif v == today:
            return "bugun"
        elif v == today + timedelta(days=1):
            return "yarin"
        return "normal"
    except Exception:
        return "normal"


# ── AYARLAR ──────────────────────────────────────────────────────────

def get_bildirim_ayarlari():
    """
    Streamlit secrets'tan bildirim ayarlarını okur.
    Yoksa varsayılan boş yapıyı döner.
    """
    try:
        b = st.secrets.get("bildirim", {})
        return {
            "smtp_host":    b.get("smtp_host",    "smtp.gmail.com"),
            "smtp_port":    int(b.get("smtp_port", 587)),
            "smtp_user":    b.get("smtp_user",    ""),
            "smtp_pass":    b.get("smtp_pass",    ""),
            "alici_email":  b.get("alici_email",  ""),
            "aktif":        b.get("aktif",         False),
        }
    except Exception:
        return {
            "smtp_host":   "smtp.gmail.com",
            "smtp_port":   587,
            "smtp_user":   "",
            "smtp_pass":   "",
            "alici_email": "",
            "aktif":       False,
        }


# ── EMAIL GÖNDER ──────────────────────────────────────────────────────

def email_gonder(konu, html_icerik, ayarlar=None):
    """
    HTML formatında email gönderir.
    Döner: (basarili: bool, mesaj: str)
    """
    if ayarlar is None:
        ayarlar = get_bildirim_ayarlari()

    if not ayarlar.get("smtp_user") or not ayarlar.get("alici_email"):
        return False, "SMTP kullanıcı veya alıcı email adresi tanımlanmamış."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = konu
        msg["From"]    = ayarlar["smtp_user"]
        msg["To"]      = ayarlar["alici_email"]

        part = MIMEText(html_icerik, "html", "utf-8")
        msg.attach(part)

        context = ssl.create_default_context()
        with smtplib.SMTP(ayarlar["smtp_host"], ayarlar["smtp_port"]) as server:
            server.starttls(context=context)
            server.login(ayarlar["smtp_user"], ayarlar["smtp_pass"])
            server.sendmail(ayarlar["smtp_user"], ayarlar["alici_email"], msg.as_string())

        return True, "✅ Email başarıyla gönderildi."

    except smtplib.SMTPAuthenticationError:
        return False, "❌ SMTP kimlik doğrulama hatası. Kullanıcı adı/şifre yanlış."
    except smtplib.SMTPConnectError:
        return False, "❌ SMTP sunucusuna bağlanılamadı. Host/port bilgilerini kontrol edin."
    except Exception as e:
        return False, f"❌ Email gönderilemedi: {str(e)}"


# ── BİLDİRİM OLUŞTURUCULAR ───────────────────────────────────────────

def vade_bildirimi_olustur(odemeler, hafta_adi, kur=38.5):
    """
    Bugün ve yarın vadeli ödemeleri içeren HTML email üretir.
    """
    bugun     = [o for o in odemeler if o.get("durum") != "odendi" and vade_durumu(o.get("vade")) == "bugun"]
    yarin     = [o for o in odemeler if o.get("durum") != "odendi" and vade_durumu(o.get("vade")) == "yarin"]
    gecmis    = [o for o in odemeler if o.get("durum") != "odendi" and vade_durumu(o.get("vade")) == "gecmis"]
    toplam_uyari = len(bugun) + len(yarin) + len(gecmis)

    if toplam_uyari == 0:
        return None, None  # Gönderilecek bir şey yok

    today_str = date.today().strftime("%d.%m.%Y")

    def odeme_satiri(o, badge_renk, badge_txt):
        tl_str  = f"₺{fmt(o['tutar_tl'])}"  if o.get("tutar_tl")  else ""
        usd_str = f"${fmt(o['tutar_usd'])}" if o.get("tutar_usd") else ""
        tutar   = tl_str or usd_str

        return f"""
        <tr style="border-bottom:1px solid #f3f4f6">
          <td style="padding:10px 14px;font-weight:700;font-size:13px">{o.get('firma','')}</td>
          <td style="padding:10px 14px;font-size:12px;color:#6b7280">{o.get('aciklama','')}</td>
          <td style="padding:10px 14px;text-align:center">
            <span style="background:{badge_renk};color:#fff;font-size:11px;
                         padding:2px 9px;border-radius:10px;font-weight:700">{badge_txt}</span>
          </td>
          <td style="padding:10px 14px;font-weight:700;text-align:right;color:#065F46">{tutar}</td>
          <td style="padding:10px 14px;font-size:12px;color:#6b7280;text-align:center">{fmt_tarih(o.get('vade'))}</td>
        </tr>"""

    gecmis_blok = ""
    if gecmis:
        satirlar = "".join(odeme_satiri(o, "#DC2626", "GECİKMİŞ") for o in gecmis)
        gecmis_blok = _tablo_blok("🚨 Gecikmiş Ödemeler", satirlar, "#FFCCCC", "#C62828")

    bugun_blok = ""
    if bugun:
        satirlar = "".join(odeme_satiri(o, "#D97706", "BUGÜN") for o in bugun)
        bugun_blok = _tablo_blok("⚠️ Bugün Vadeli", satirlar, "#FEF3C7", "#92400E")

    yarin_blok = ""
    if yarin:
        satirlar = "".join(odeme_satiri(o, "#2563EB", "YARIN") for o in yarin)
        yarin_blok = _tablo_blok("📅 Yarın Vadeli", satirlar, "#DBEAFE", "#1E40AF")

    konu = f"💳 KAYRANACC — {toplam_uyari} Ödeme Uyarısı ({today_str})"

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F4F5F7;font-family:'Segoe UI',Arial,sans-serif">
<div style="max-width:640px;margin:30px auto;background:#fff;border-radius:12px;
            overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1)">

  <!-- Başlık -->
  <div style="background:linear-gradient(135deg,#0B1437,#162050);padding:24px 28px;color:#fff">
    <div style="font-size:22px;font-weight:800;margin-bottom:4px">💳 KAYRANACC</div>
    <div style="font-size:13px;opacity:0.7">Ödeme Takip Sistemi · {today_str}</div>
  </div>

  <!-- Uyarı özeti -->
  <div style="padding:20px 28px;background:#FFFBEB;border-bottom:1px solid #FDE68A">
    <div style="font-size:15px;font-weight:700;color:#92400E">
      ⚠️ {hafta_adi} — {toplam_uyari} ödeme dikkatinizi gerektiriyor
    </div>
    {f'<div style="font-size:12px;color:#C62828;margin-top:4px;font-weight:600">🚨 {len(gecmis)} gecikmiş ödeme!</div>' if gecmis else ''}
  </div>

  <div style="padding:20px 28px">
    {gecmis_blok}
    {bugun_blok}
    {yarin_blok}
  </div>

  <!-- Footer -->
  <div style="padding:16px 28px;background:#F9FAFB;border-top:1px solid #E5E7EB;
              text-align:center;font-size:11px;color:#9CA3AF">
    Bu email KAYRANACC Ödeme Takip Sistemi tarafından otomatik gönderilmiştir.
  </div>
</div>
</body>
</html>"""

    return konu, html


def ozet_bildirimi_olustur(odemeler, bankalar, hafta_adi, kur=38.5):
    """
    Haftalık özet email üretir.
    """
    tl_toplam  = sum(o.get("tutar_tl")  or 0 for o in odemeler)
    usd_toplam = sum(o.get("tutar_usd") or 0 for o in odemeler)
    odendi_tl  = sum(o.get("tutar_tl")  or 0 for o in odemeler if o.get("durum") == "odendi")
    kalan_tl   = tl_toplam - odendi_tl
    odendi_cnt = sum(1 for o in odemeler if o.get("durum") == "odendi")
    today_str  = date.today().strftime("%d.%m.%Y")

    banka_html = ""
    for b in (bankalar or []):
        sym = "$" if b["para_birimi"] == "USD" else "₺"
        banka_html += f"""
        <tr>
          <td style="padding:8px 14px;font-weight:600">{b['hesap_adi']}</td>
          <td style="padding:8px 14px;text-align:right;font-weight:700;font-family:monospace">{sym}{fmt(b['bakiye'])}</td>
          <td style="padding:8px 14px;text-align:center;color:#6b7280">{b['para_birimi']}</td>
        </tr>"""

    konu = f"💳 KAYRANACC — Haftalık Özet: {hafta_adi} ({today_str})"

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F4F5F7;font-family:'Segoe UI',Arial,sans-serif">
<div style="max-width:600px;margin:30px auto;background:#fff;border-radius:12px;
            overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1)">

  <div style="background:linear-gradient(135deg,#0B1437,#162050);padding:24px 28px;color:#fff">
    <div style="font-size:22px;font-weight:800;margin-bottom:4px">💳 KAYRANACC</div>
    <div style="font-size:13px;opacity:0.7">Haftalık Özet · {today_str}</div>
  </div>

  <div style="padding:20px 28px">
    <div style="font-size:16px;font-weight:700;color:#0B1437;margin-bottom:16px">{hafta_adi}</div>

    <!-- Özet metrikler -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px">
      {_metrik_kart("Toplam TL", f"₺{fmt(tl_toplam)}", "#065F46")}
      {_metrik_kart("Toplam USD", f"${fmt(usd_toplam)}", "#1E40AF")}
      {_metrik_kart("Ödendi", f"{odendi_cnt}/{len(odemeler)}", "#059669")}
      {_metrik_kart("Kalan TL", f"₺{fmt(kalan_tl)}", "#D97706")}
    </div>

    {f'''<!-- Banka bakiyeleri -->
    <div style="font-size:13px;font-weight:700;color:#0B1437;margin-bottom:10px">🏦 Banka Bakiyeleri</div>
    <table style="width:100%;border-collapse:collapse;background:#F9FAFB;border-radius:8px;overflow:hidden;margin-bottom:20px">
      {banka_html}
    </table>''' if banka_html else ''}
  </div>

  <div style="padding:14px 28px;background:#F9FAFB;border-top:1px solid #E5E7EB;
              text-align:center;font-size:11px;color:#9CA3AF">
    KAYRANACC · {today_str}
  </div>
</div>
</body>
</html>"""

    return konu, html


# ── HTML YARDIMCI ─────────────────────────────────────────────────────

def _tablo_blok(baslik, satirlar, header_bg, header_color):
    return f"""
    <div style="margin-bottom:20px">
      <div style="background:{header_bg};padding:10px 14px;border-radius:8px 8px 0 0;
                  font-size:13px;font-weight:700;color:{header_color}">{baslik}</div>
      <table style="width:100%;border-collapse:collapse;border:1px solid #E5E7EB;border-top:none;border-radius:0 0 8px 8px">
        <tr style="background:#F9FAFB">
          <th style="padding:8px 14px;text-align:left;font-size:11px;color:#6b7280;font-weight:700">FİRMA</th>
          <th style="padding:8px 14px;text-align:left;font-size:11px;color:#6b7280;font-weight:700">AÇIKLAMA</th>
          <th style="padding:8px 14px;text-align:center;font-size:11px;color:#6b7280;font-weight:700">DURUM</th>
          <th style="padding:8px 14px;text-align:right;font-size:11px;color:#6b7280;font-weight:700">TUTAR</th>
          <th style="padding:8px 14px;text-align:center;font-size:11px;color:#6b7280;font-weight:700">VADE</th>
        </tr>
        {satirlar}
      </table>
    </div>"""


def _metrik_kart(etiket, deger, renk):
    return f"""
    <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:14px;text-align:center">
      <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">{etiket}</div>
      <div style="font-size:20px;font-weight:700;color:{renk};font-family:monospace">{deger}</div>
    </div>"""


# ── TEST ──────────────────────────────────────────────────────────────

def baglanti_test(ayarlar):
    """
    SMTP bağlantısını test eder, email göndermeden.
    Döner: (basarili: bool, mesaj: str)
    """
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(ayarlar["smtp_host"], ayarlar["smtp_port"], timeout=8) as server:
            server.starttls(context=context)
            server.login(ayarlar["smtp_user"], ayarlar["smtp_pass"])
        return True, "✅ SMTP bağlantısı başarılı! Email gönderilebilir."
    except smtplib.SMTPAuthenticationError:
        return False, "❌ Kimlik doğrulama hatası. Gmail için 'Uygulama Şifresi' kullandığınızdan emin olun."
    except Exception as e:
        return False, f"❌ Bağlantı hatası: {str(e)}"

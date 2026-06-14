import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from .database import get_connection
from shared.utils import tr_today, tr_now, tr_today_iso

def get_bildirim_ayarlari():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bildirim_ayarlari (
            id INTEGER PRIMARY KEY,
            email TEXT,
            smtp_host TEXT,
            smtp_port INTEGER,
            smtp_user TEXT,
            smtp_pass TEXT,
            aktif INTEGER DEFAULT 0,
            son_gonderim TEXT
        )
    """)
    conn.commit()
    c.execute("SELECT * FROM bildirim_ayarlari WHERE id=1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def kaydet_bildirim_ayarlari(email, smtp_host, smtp_port, smtp_user, smtp_pass, aktif=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bildirim_ayarlari (
            id INTEGER PRIMARY KEY,
            email TEXT,
            smtp_host TEXT,
            smtp_port INTEGER,
            smtp_user TEXT,
            smtp_pass TEXT,
            aktif INTEGER DEFAULT 0,
            son_gonderim TEXT
        )
    """)
    c.execute("""
        INSERT INTO bildirim_ayarlari (id, email, smtp_host, smtp_port, smtp_user, smtp_pass, aktif)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            email=excluded.email,
            smtp_host=excluded.smtp_host,
            smtp_port=excluded.smtp_port,
            smtp_user=excluded.smtp_user,
            smtp_pass=excluded.smtp_pass,
            aktif=excluded.aktif
    """, (email, smtp_host, smtp_port, smtp_user, smtp_pass, aktif))
    conn.commit()
    conn.close()

def guncelle_son_gonderim():
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE bildirim_ayarlari SET son_gonderim=? WHERE id=1",
              (tr_now().strftime("%Y-%m-%d %H:%M"),))
    conn.commit()
    conn.close()

def email_gonder(veri):
    """Tüm ürünlerin sipariş durum özetini e-posta olarak gönderir"""
    ayarlar = get_bildirim_ayarlari()
    if not ayarlar or not ayarlar.get("aktif") or not ayarlar.get("email"):
        return False, "E-posta ayarları yapılmamış"

    try:
        acil = [u for u in veri if u.get("siparis_durum") == "acil"]
        yaklasan = [u for u in veri if u.get("siparis_durum") == "yaklasıyor"]
        planlama = [u for u in veri if u.get("siparis_durum") == "planlama"]
        normal = [u for u in veri if u.get("siparis_durum") == "normal"]
        veri_yok = [u for u in veri if u.get("siparis_durum") == "veri_yok"]

        def tablo_satir(u, renk):
            return f"""
            <tr style="background:{renk}">
                <td style="padding:6px 10px;border-bottom:1px solid #eee">{u['sku']}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee">{u['urun_adi']}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:center">{u['bizim_stok']}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:center">{u.get('toplam_haftalik_satis',0)}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:center">{u.get('stok_bitis_gun','-')}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-weight:bold">{u.get('siparis_mesaj','')}</td>
            </tr>"""

        html_satirlar = ""
        for u in acil:
            html_satirlar += tablo_satir(u, "#FFCCCC")
        for u in yaklasan:
            html_satirlar += tablo_satir(u, "#FFE0B2")
        for u in planlama:
            html_satirlar += tablo_satir(u, "#FFF9C4")
        for u in normal:
            html_satirlar += tablo_satir(u, "#F5F5F5")
        for u in veri_yok:
            html_satirlar += tablo_satir(u, "#FAFAFA")

        html = f"""
        <html><body style="font-family:Arial,sans-serif;color:#333">
        <div style="max-width:900px;margin:0 auto">
          <div style="background:#1F4E79;color:white;padding:20px;border-radius:8px 8px 0 0">
            <h1 style="margin:0;font-size:20px">📦 Stok Yönetimi — Günlük Sipariş Özeti</h1>
            <p style="margin:4px 0 0;opacity:0.8;font-size:13px">{tr_now().strftime('%d.%m.%Y %H:%M')}</p>
          </div>

          <div style="background:#f8f8f8;padding:16px;display:flex;gap:16px;flex-wrap:wrap">
            <div style="background:#FFCCCC;padding:10px 20px;border-radius:6px;text-align:center">
              <div style="font-size:24px;font-weight:bold;color:#C62828">{len(acil)}</div>
              <div style="font-size:12px;color:#C62828">🔴 ACİL SİPARİŞ</div>
            </div>
            <div style="background:#FFE0B2;padding:10px 20px;border-radius:6px;text-align:center">
              <div style="font-size:24px;font-weight:bold;color:#E65100">{len(yaklasan)}</div>
              <div style="font-size:12px;color:#E65100">🟠 YAKLAŞIYOR</div>
            </div>
            <div style="background:#FFF9C4;padding:10px 20px;border-radius:6px;text-align:center">
              <div style="font-size:24px;font-weight:bold;color:#F57F17">{len(planlama)}</div>
              <div style="font-size:12px;color:#F57F17">🟡 PLANLAMA</div>
            </div>
            <div style="background:#C8E6C9;padding:10px 20px;border-radius:6px;text-align:center">
              <div style="font-size:24px;font-weight:bold;color:#2E7D32">{len(normal)}</div>
              <div style="font-size:12px;color:#2E7D32">🟢 NORMAL</div>
            </div>
          </div>

          <table style="width:100%;border-collapse:collapse;background:white">
            <thead>
              <tr style="background:#1F4E79;color:white">
                <th style="padding:8px 10px;text-align:left">SKU</th>
                <th style="padding:8px 10px;text-align:left">Ürün Adı</th>
                <th style="padding:8px 10px;text-align:center">Bizim Stok</th>
                <th style="padding:8px 10px;text-align:center">Haftalık Satış</th>
                <th style="padding:8px 10px;text-align:center">Stok Bitis (Gün)</th>
                <th style="padding:8px 10px;text-align:left">Sipariş Durumu</th>
              </tr>
            </thead>
            <tbody>{html_satirlar}</tbody>
          </table>

          <div style="background:#f0f0f0;padding:12px;border-radius:0 0 8px 8px;font-size:11px;color:#666">
            Bu e-posta Stok Yönetim Sistemi tarafından otomatik gönderilmiştir. Üretim süresi: 135 gün (4.5 ay)
          </div>
        </div>
        </body></html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📦 Stok Sipariş Özeti — {len(acil)} ACİL ürün | {tr_now().strftime('%d.%m.%Y')}"
        msg["From"] = ayarlar["smtp_user"]
        msg["To"] = ayarlar["email"]
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(ayarlar["smtp_host"], int(ayarlar["smtp_port"])) as server:
            server.starttls()
            server.login(ayarlar["smtp_user"], ayarlar["smtp_pass"])
            server.sendmail(ayarlar["smtp_user"], ayarlar["email"], msg.as_string())

        guncelle_son_gonderim()
        return True, f"E-posta gönderildi → {ayarlar['email']}"
    except Exception as e:
        return False, f"E-posta gönderilemedi: {str(e)}"

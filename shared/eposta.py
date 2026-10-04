# -*- coding: utf-8 -*-
"""KAYRAN — Kişiye özel e-posta bildirimleri (Ekim 2026).

  · YÜKLEME HATIRLATMALARI (her sabah, otonom/eposta_hatirlatma.py): her sorumluya
    günde EN ÇOK bir toplu mail — son günden 2 gün önce, son gün sabahı, gecikmede
    her iş günü (hafta sonu yok). Gecikme 5 iş gününü geçince yöneticiye kopya.
    Söylenecek bir şey yoksa mail gitmez; aynı gün ikinci kez gitmez.
  · TALEPLER (uygulamadan, arka planda): yeni talep → talep yöneticileri;
    yanıt / durum değişikliği → talep sahibi. Gönderilemese de talep kaydedilir.
  · ADRESLER kodda değil veritabanında (sistem_ayarlari 'kullanici_eposta'),
    Kullanıcı Yönetimi'nden girilir.
  · SMTP: ortam değişkenleri (SMTP_HOST/PORT/USER/PASS — GitHub Actions) ya da
    st.secrets['bildirim'] (smtp_host/port/user/pass — uygulama).
Kurallar saf fonksiyonlardır (tests/test_eposta.py).
"""
import html as _h
import os
import smtplib
import ssl
import threading
from datetime import timedelta
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

UYGULAMA_URL = "https://kayran-corporate.streamlit.app"
ADRES_ANAHTAR = "kullanici_eposta"            # {kullanici: adres}
GONDERIM_ANAHTAR = "eposta_hatirlatma_son"    # {kullanici: 'YYYY-MM-DD'}
YONETICI = "ibrahim"
ESKALASYON_IS_GUNU = 5
TALEP_DURUM_AD = {"bekliyor": "Bekliyor", "inceleniyor": "İnceleniyor", "tamamlandi": "Tamamlandı",
                  "reddedildi": "Reddedildi"}


def _e(v):
    return _h.escape(str(v or ""))


def baglanti(modul=""):
    return f"{UYGULAMA_URL}/?s={modul}" if modul else UYGULAMA_URL


# ── SMTP ────────────────────────────────────────────────────────────
def _secrets():
    try:
        import streamlit as st
        return dict(st.secrets.get("bildirim", {}))
    except Exception:  # noqa: BLE001
        return {}


def ayarlar():
    """Ortam değişkeni (Actions) önce, yoksa uygulama sırları."""
    s = _secrets()
    return {"host": os.environ.get("SMTP_HOST") or s.get("smtp_host") or "smtp.gmail.com",
            "port": int(os.environ.get("SMTP_PORT") or s.get("smtp_port") or 587),
            "user": os.environ.get("SMTP_USER") or s.get("smtp_user") or "",
            "pass": os.environ.get("SMTP_PASS") or s.get("smtp_pass") or ""}


def gonder(alicilar, konu, html, cc=None, ekler=None):
    """Döner: (ok, kod) — kod: 'ok' · 'alici_yok' · 'smtp_yok' · hata metni.
    ekler: [(dosya adı, bayt, mime türü)] — ör. yaşlı stok maili Excel eki."""
    alicilar = [a for a in (alicilar or []) if a]
    cc = [a for a in (cc or []) if a and a not in alicilar]
    if not alicilar:
        return False, "alici_yok"
    a = ayarlar()
    if not a["user"] or not a["pass"]:
        return False, "smtp_yok"
    try:
        msg = mesaj_olustur(a["user"], alicilar, konu, html, cc, ekler=ekler)
        with smtplib.SMTP(a["host"], a["port"], timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(a["user"], a["pass"])
            s.sendmail(a["user"], alicilar + cc, msg.as_string())
        return True, "ok"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP kimlik doğrulama hatası (kullanıcı adı / uygulama şifresi)"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:160]}"


def duz_metin(html):
    """HTML'den okunur düz metin (bağlantılar parantez içinde korunur)."""
    t = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", html, flags=re.S)
    t = re.sub(r"<(br|/p|/div|/tr|/h2|hr)[^>]*>", "\n", t)
    t = _h.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", t)).strip()


def mesaj_olustur(gonderen, alicilar, konu, html, cc=None, ekler=None):
    """Spam filtrelerinin aradığı başlıklarla: Date, Message-ID, düz metin + HTML (multipart/alternative).
    Eskiden yalnız HTML'di, Date ve Message-ID yoktu — üçü de spam puanını artırır."""
    govde = MIMEMultipart("alternative")
    govde.attach(MIMEText(duz_metin(html), "plain", "utf-8"))    # önce düz metin, sonra HTML (RFC 2046)
    govde.attach(MIMEText(html, "html", "utf-8"))
    if ekler:                              # ekli mail: mixed = [alternative gövde, ekler…]
        from email.mime.application import MIMEApplication
        msg = MIMEMultipart("mixed")
        msg.attach(govde)
        for ad, bayt, mime in ekler:
            parca = MIMEApplication(bayt, _subtype=(mime or "octet-stream").split("/")[-1])
            parca.add_header("Content-Disposition", "attachment", filename=("utf-8", "", ad))
            msg.attach(parca)
    else:
        msg = govde
    msg["Subject"] = konu
    msg["From"] = formataddr(("KAYRAN Workspace", gonderen))
    msg["To"] = ", ".join(alicilar)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Reply-To"] = gonderen
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=(gonderen.split("@")[-1] or None))
    return msg


def arka_planda(alicilar, konu, html, cc=None):
    """Ekranı bekletmeden gönderir; hata hata_kayitlari'na yazılır, akışı bozmaz."""
    def _is():
        ok, kod = gonder(alicilar, konu, html, cc)
        if not ok and kod not in ("alici_yok", "smtp_yok"):
            try:
                from shared.hata_log import kaydet
                kaydet("eposta.arka_planda", RuntimeError(kod))
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=_is, daemon=True).start()


# ── Adresler ────────────────────────────────────────────────────────
def adresler():
    try:
        from kayranacc.database import get_ayar
        v = get_ayar(ADRES_ANAHTAR, {})
        return {str(k).lower(): str(a).strip() for k, a in (v or {}).items() if str(a or "").strip()}
    except Exception:  # noqa: BLE001
        return {}


def adres_kaydet(sozluk):
    from kayranacc.database import set_ayar
    return set_ayar(ADRES_ANAHTAR, {str(k).lower(): str(a).strip() for k, a in sozluk.items() if str(a or "").strip()})


def adres_gecerli_mi(a):
    a = str(a or "").strip()
    return bool(a) and "@" in a and "." in a.split("@")[-1] and " " not in a


# ── Şablon ──────────────────────────────────────────────────────────
def sablon(baslik, govde_html, buton=None, url=None, alt=""):
    btn = (f'<p style="margin:20px 0 6px"><a href="{_e(url)}" style="background:#5B5BD6;color:#fff;'
           f'text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;display:inline-block">'
           f'{_e(buton)}</a></p>') if buton and url else ""
    return ('<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#0f172a;line-height:1.55;'
            'max-width:620px">'
            f'<div style="font-size:12px;color:#64748b;letter-spacing:.3px">KAYRAN Workspace</div>'
            f'<h2 style="margin:4px 0 14px;font-size:20px;color:#1e1b4b">{_e(baslik)}</h2>'
            f'{govde_html}{btn}'
            '<hr style="border:none;border-top:1px solid #e2e8f0;margin:18px 0 10px">'
            f'<div style="font-size:12px;color:#94a3b8">{_e(alt) or "Bu mail KAYRAN Workspace tarafından otomatik gönderildi."}'
            '</div></div>')


# ── Yükleme hatırlatmaları (saf) ────────────────────────────────────
def is_gunu_gecikme(bugun, gecikme_gun):
    """Son günden sonra bugüne kadar geçen iş günü (Pzt–Cum)."""
    vade = bugun - timedelta(days=int(gecikme_gun or 0))
    n, g = 0, vade + timedelta(days=1)
    while g <= bugun:
        if g.weekday() < 5:
            n += 1
        g += timedelta(days=1)
    return n


def _bugun_bildirilir(d, bugun):
    if d.get("seviye") == "yaklasiyor":
        return d.get("kalan_gun") in (2, 0)
    if d.get("seviye") == "gecikti":
        return bugun.weekday() < 5                 # gecikme: her iş günü
    return False


def _kalem_html(d, bugun):
    from shared.yukleme_takvimi import eksik_ozeti
    if d["seviye"] == "gecikti":
        ne = (f'<b style="color:#dc2626">{_e(eksik_ozeti(d.get("eksik_adlar"), d.get("siklik")))} eksik</b> · '
              f'{int(d.get("gecikme_gun") or 0)} gün gecikti')
    elif d.get("kalan_gun") == 0:
        ne = f'<b style="color:#d97706">son gün bugün</b> · {_e(d.get("sonraki_adi"))}'
    else:
        ne = (f'<b style="color:#d97706">{d.get("kalan_gun")} gün kaldı</b> · {_e(d.get("sonraki_adi"))} · '
              f'son gün {_e(d.get("vade_metni"))}')
    return (f'<tr><td style="padding:10px 0;border-bottom:1px solid #eef2f7">'
            f'<div style="font-weight:600">{_e(d.get("ad"))}</div>'
            f'<div style="font-size:14px;margin:2px 0">{ne}</div>'
            f'<div style="font-size:13px"><a href="{_e(baglanti(d.get("modul")))}" style="color:#5B5BD6">'
            f'{_e(d.get("sayfa"))} › aç</a></div></td></tr>')


def _hatirlatma_gruplari(durumlar, bugun):
    gr = {}
    for d in durumlar or []:
        if d.get("sorumlu") and _bugun_bildirilir(d, bugun):
            gr.setdefault(str(d["sorumlu"]).lower(), []).append(d)
    return gr


def adressizler(durumlar, bugun, adres_haritasi):
    """Bugün bildirilecek kalemi olup adresi girilmemiş sorumlular (rapor için)."""
    return sorted(k for k in _hatirlatma_gruplari(durumlar, bugun) if not adres_haritasi.get(k))


def hatirlatma_mailleri(durumlar, bugun, adres_haritasi, yonetici=YONETICI):
    """Döner: [{kullanici, kime, cc, konu, html, kalemler}] — kişi başına TEK mail."""
    out = []
    for kul, ds in sorted(_hatirlatma_gruplari(durumlar, bugun).items()):
        adr = adres_haritasi.get(kul)
        if not adr:
            continue
        gec = [d for d in ds if d["seviye"] == "gecikti"]
        yak = [d for d in ds if d["seviye"] == "yaklasiyor"]
        ds = gec + sorted(yak, key=lambda d: d.get("kalan_gun") or 0)
        if gec:
            konu = f"KAYRAN · {len(gec)} yükleme gecikti" + (f", {len(yak)} yaklaşıyor" if yak else "")
        elif any(d.get("kalan_gun") == 0 for d in yak):
            konu = "KAYRAN · son gün bugün: " + ", ".join(d["ad"] for d in yak if d.get("kalan_gun") == 0)
        else:
            konu = "KAYRAN · yaklaşan yükleme: " + ", ".join(d["ad"] for d in yak)
        cc = []
        if (kul != yonetici and adres_haritasi.get(yonetici)
                and any(is_gunu_gecikme(bugun, d.get("gecikme_gun")) > ESKALASYON_IS_GUNU for d in gec)):
            cc = [adres_haritasi[yonetici]]
        ad = ds[0].get("sorumlu_ad") or kul
        govde = (f'<p>Merhaba {_e(ad)},</p><p>Sorumlu olduğun dönemsel yüklemelerin durumu:</p>'
                 f'<table style="width:100%;border-collapse:collapse">{"".join(_kalem_html(d, bugun) for d in ds)}</table>'
                 + ('<p style="font-size:13px;color:#64748b;margin-top:12px">Gecikme 5 iş gününü geçtiği için '
                    'bu mail yöneticiye de gönderildi.</p>' if cc else "")
                 + '<p style="font-size:13px;color:#64748b">O dönem gerçekten veri yoksa ana sayfadaki '
                   '"Bu dönem veri yok" ile işaretleyebilirsin; hatırlatma durur.</p>')
        out.append({"kullanici": kul, "kime": [adr], "cc": cc, "konu": konu, "kalemler": ds,
                    "html": sablon("Yükleme hatırlatması", govde, "KAYRAN'ı aç", baglanti())})
    return out


def gonderilecekler(planlar, son_gonderim, bugun):
    """Aynı gün ikinci kez gitmesin (iş tekrar çalışırsa)."""
    b = bugun.isoformat()
    return [p for p in planlar if (son_gonderim or {}).get(p["kullanici"]) != b]


# ── Talepler ────────────────────────────────────────────────────────
def talep_yeni_mail(gonderen, mesaj, konu, kategori="", oncelik=""):
    govde = (f'<p><b>{_e(gonderen)}</b> yeni bir talep gönderdi.</p>'
             f'<p style="margin:2px 0"><b>Konu:</b> {_e(konu)}</p>'
             + (f'<p style="margin:2px 0"><b>Tür / öncelik:</b> {_e(kategori)} · {_e(oncelik)}</p>' if kategori else "")
             + f'<div style="white-space:pre-wrap;background:#f8fafc;border-radius:8px;padding:12px;margin-top:10px">'
               f'{_e(mesaj)}</div>')
    return (f"[KAYRAN Talep] {konu}",
            sablon("Yeni talep", govde, "Talep Merkezi'ni aç", baglanti("anasayfa")))


def talep_yanit_mail(konu, cevap, durum):
    dad = TALEP_DURUM_AD.get(str(durum or ""), str(durum or ""))
    govde = (f'<p><b>{_e(konu)}</b> başlıklı talebin güncellendi.</p>'
             f'<p style="margin:2px 0"><b>Durum:</b> {_e(dad)}</p>'
             + (f'<div style="white-space:pre-wrap;background:#f8fafc;border-radius:8px;padding:12px;margin-top:10px">'
                f'{_e(cevap)}</div>' if cevap else ""))
    return (f"[KAYRAN Talep] {konu} — {dad}",
            sablon("Talebin yanıtlandı", govde, "Taleplerimi aç", baglanti("anasayfa")))

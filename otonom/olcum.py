# -*- coding: utf-8 -*-
"""
otonom/olcum.py — NÖBETÇİ EŞİK ÖLÇÜMÜ (tek seferlik)

Amaç: veri bütünlüğü nöbetçisi için eşik koymadan önce BUGÜNKÜ değerleri
ölçmek. "Kaç eksi stok alarmdır?" sorusunu tahminle değil, mevcut veriyle
cevaplamak için.

Veri mantığı UYGULAMANIN KENDİSİNDEN gelir (satis.database, kayranpm.analitik
vb.) → ölçüm ile ekrandaki rakamlar asla ayrışmaz.

ÇALIŞTIRMA: GitHub → Actions → "Nöbetçi Eşik Ölçümü" → Run workflow
Sonuç hem Actions kaydına yazılır hem (token varsa) Telegram'a gönderilir.

Ortam değişkenleri:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   (isteğe bağlı)
Supabase erişimi: iş akışı .streamlit/secrets.toml yazar, uygulamanın kendi
get_client() fonksiyonu onu okur (telegram_brifing.py ile aynı yöntem).
"""
import os
import sys
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BUGUN = dt.date.today()
YIL_ILK = BUGUN.replace(month=1, day=1).isoformat()
BUGUN_S = BUGUN.isoformat()

sonuclar = []   # (alan, olcum, deger_str, oneri)


def ekle(alan, olcum, deger, oneri=""):
    sonuclar.append((alan, olcum, str(deger), oneri))


def olc(alan, olcum, fn, oneri_fn=None):
    """Tek ölçüm — patlarsa rapor devam eder, hata satır olarak görünür."""
    try:
        d = fn()
        ekle(alan, olcum, d, oneri_fn(d) if oneri_fn else "")
    except Exception as e:
        ekle(alan, olcum, "HATA", f"{type(e).__name__}: {str(e)[:60]}")


# ══════════════════════════════════════════════════════════════════
# STOK
# ══════════════════════════════════════════════════════════════════
_dash = None


def dash():
    global _dash
    if _dash is None:
        from kayranpm.analitik import dashboard_hesapla
        _dash = dashboard_hesapla() or []
    return _dash


olc("Stok", "Eksi stoktaki ürün sayısı",
    lambda: sum(1 for u in dash() if float(u.get("toplam_stok", 0) or 0) < 0),
    lambda d: "eşik 0 — eksi stok her zaman hatadır" if d == 0
              else f"şu an {d} var; önce temizle, sonra eşik 0")

olc("Stok", "En düşük stok değeri",
    lambda: min([float(u.get("toplam_stok", 0) or 0) for u in dash()] or [0]))

olc("Stok", "Acil sipariş gereken ürün",
    lambda: sum(1 for u in dash() if u.get("siparis_durum") == "acil"),
    lambda d: f"eşik önerisi: {max(5, int(d * 1.5))} (bugünün %50 üstü)")

olc("Stok", "Toplam takip edilen SKU",
    lambda: len(dash()))


# ══════════════════════════════════════════════════════════════════
# SATIŞ VERİSİ
# ══════════════════════════════════════════════════════════════════
_sat_ytd = None


def sat_ytd():
    global _sat_ytd
    if _sat_ytd is None:
        from satis.database import get_satislar
        _sat_ytd = get_satislar(YIL_ILK, BUGUN_S) or []
    return _sat_ytd


_sat_hepsi = None


def sat_hepsi():
    global _sat_hepsi
    if _sat_hepsi is None:
        from satis.database import get_satislar
        _sat_hepsi = get_satislar() or []
    return _sat_hepsi


def _nsku(x):
    import re
    return re.sub(r"[^A-Z0-9]", "", str(x or "").upper())


def maliyetsiz():
    from satis.database import get_pacal_map
    pacal = {}
    for k, v in (get_pacal_map() or {}).items():
        pacal[_nsku(k)] = v
    onarilir = ithalatsiz = 0
    for s in sat_ytd():
        if float(s.get("birim_maliyet") or 0) <= 0 and int(s.get("adet") or 0) > 0:
            if float(pacal.get(_nsku(s.get("sku")), 0) or 0) > 0:
                onarilir += 1
            else:
                ithalatsiz += 1
    return onarilir, ithalatsiz


olc("Satış", "YTD satış satırı", lambda: len(sat_ytd()))
olc("Satış", "Tüm zamanlar satış satırı", lambda: len(sat_hepsi()))

olc("Satış", "Maliyeti 0 — paçal VAR (tek tıkla onarılır)",
    lambda: maliyetsiz()[0],
    lambda d: "eşik 0 önerilir — onarımı tek tık" if d < 50
              else f"şu an {d}; önce onar, sonra eşik 0")

olc("Satış", "Maliyeti 0 — paçal YOK (ithalatsız)",
    lambda: maliyetsiz()[1],
    lambda d: "eşik 0 — bu gerçek veri boşluğu" if d < 20
              else f"şu an {d}; kademeli hedef koy")

olc("Satış", "Gelecek tarihli satış (tarih > bugün)",
    lambda: sum(1 for s in sat_hepsi()
                if str(s.get("tarih") or "")[:10] > BUGUN_S),
    lambda d: "eşik 0 — istisnasız hata")

olc("Satış", "2020 öncesi tarihli satış",
    lambda: sum(1 for s in sat_hepsi()
                if "0000" < str(s.get("tarih") or "")[:10] < "2020-01-01"),
    lambda d: "eşik 0 — istisnasız hata")

olc("Satış", "Adet <= 0 olan satış satırı",
    lambda: sum(1 for s in sat_hepsi() if int(s.get("adet") or 0) <= 0),
    lambda d: "eşik 0")


def zararina():
    from shared.dogrula import zararina_mi
    return sum(1 for s in sat_ytd()
               if zararina_mi(s.get("birim_satis"), s.get("birim_maliyet"))
               and float(s.get("birim_maliyet") or 0) > 0)


olc("Satış", "Zararına satış satırı (YTD, maliyeti girili)",
    zararina,
    lambda d: f"eşik önerisi: {max(10, int(d * 1.3))} — kampanya olabilir, sıfır olmayabilir")


def mukerrer():
    gor, tekrar = set(), 0
    for s in sat_hepsi():
        anahtar = (str(s.get("siparis_no") or "").strip(),
                   _nsku(s.get("sku")), str(s.get("tarih") or "")[:10])
        if anahtar[0] and anahtar[1]:
            if anahtar in gor:
                tekrar += 1
            gor.add(anahtar)
    return tekrar


olc("Satış", "Mükerrer satır (sipariş no + SKU + tarih aynı)",
    mukerrer,
    lambda d: "eşik 0 önerilir" if d < 30 else f"şu an {d}; önce incele")


# ══════════════════════════════════════════════════════════════════
# İADE
# ══════════════════════════════════════════════════════════════════
def iade_ozet():
    from satis.database import iade_satis_net_ozet
    _, top = iade_satis_net_ozet(YIL_ILK, BUGUN_S)
    return top or {}


olc("İade", "YTD iade oranı (adet)",
    lambda: (f"%{(iade_ozet().get('i_adet', 0) / iade_ozet().get('s_adet', 1) * 100):.1f}"
             if iade_ozet().get("s_adet") else "—"),
    lambda d: "devir notunda %25.9 yazıyordu — eşik olarak %35 makul başlangıç")

olc("İade", "YTD iade adedi", lambda: iade_ozet().get("i_adet", 0))
olc("İade", "YTD satış adedi", lambda: iade_ozet().get("s_adet", 0))


def iade_asimi():
    """SKU bazında iade adedi satış adedini geçiyor mu — yetim parti işareti."""
    from satis.database import get_iadeler
    sat = {}
    for s in sat_hepsi():
        sat[_nsku(s.get("sku"))] = sat.get(_nsku(s.get("sku")), 0) + int(s.get("adet") or 0)
    iad = {}
    for r in (get_iadeler() or []):
        k = _nsku(r.get("sku"))
        iad[k] = iad.get(k, 0) + int(r.get("iade_adet") or 0)
    return sum(1 for k, v in iad.items() if v > sat.get(k, 0))


olc("İade", "İadesi satışını aşan SKU sayısı",
    iade_asimi,
    lambda d: "eşik 0 — mantıken imkânsız, yetim parti demektir")


# ══════════════════════════════════════════════════════════════════
# İTHALAT
# ══════════════════════════════════════════════════════════════════
olc("İthalat", "Teslim alındı ama stoğa girmemiş dosya",
    lambda: len(__import__("ithalat.database", fromlist=["x"])
                .teslim_stok_bekleyenler(gercek_stok_kontrol=True) or []),
    lambda d: "eşik 0 — 'ya hep ya hiç' korumasının kaçağı")


def yolda():
    from ithalat.database import get_dosyalar, IN_TRANSIT_DURUMLAR
    return sum(1 for d in (get_dosyalar() or [])
               if str(d.get("durum", "")).strip() in IN_TRANSIT_DURUMLAR)


olc("İthalat", "Yolda / gümrükte dosya", yolda)


# ══════════════════════════════════════════════════════════════════
# ÖDEME
# ══════════════════════════════════════════════════════════════════
def odeme(durum):
    from kayranacc.database import get_aktif_odemeler
    from shared.utils import vade_durumu
    odm, _ = get_aktif_odemeler()
    bek = [o for o in (odm or []) if o.get("durum") == "bekliyor"]
    return sum(1 for o in bek if vade_durumu(o.get("vade")) == durum)


olc("Ödeme", "Gecikmiş ödeme sayısı", lambda: odeme("gecmis"),
    lambda d: f"eşik önerisi: {max(3, d)} — bugünkü değerin altına inmesin")
olc("Ödeme", "Bugün vadeli ödeme", lambda: odeme("bugun"))


# ══════════════════════════════════════════════════════════════════
# TEKNİK SERVİS
# ══════════════════════════════════════════════════════════════════
def sla_asan():
    from teknikservis.database import get_kayitlar, is_gunu_farki, BITMIS_DURUMLAR
    n = 0
    for k in (get_kayitlar() or []):
        if str(k.get("durum", "")) in BITMIS_DURUMLAR:
            continue
        g = is_gunu_farki(k.get("mal_kabul_tarihi") or k.get("kayit_tarihi"))
        if g is not None and g > 21:
            n += 1
    return n


olc("Servis", "SLA aşan açık iş (>21 iş günü)", sla_asan,
    lambda d: f"eşik önerisi: {max(3, int(d * 1.2))}")


# ══════════════════════════════════════════════════════════════════
# DENETİM KAYDI
# ══════════════════════════════════════════════════════════════════
def silme_24s():
    from shared.audit import get_loglar
    dun = (BUGUN - dt.timedelta(days=1)).isoformat()
    return sum(1 for l in (get_loglar(limit=500, baslangic=dun) or [])
               if "sil" in str(l.get("islem", "")).lower())


olc("Denetim", "Son 24 saatte silme işlemi", silme_24s,
    lambda d: "eşik önerisi: 20 — toplu silmede haber ver")


# ══════════════════════════════════════════════════════════════════
# RAPOR
# ══════════════════════════════════════════════════════════════════
def tablo():
    g1 = max((len(s[0]) for s in sonuclar), default=8)
    g2 = max((len(s[1]) for s in sonuclar), default=30)
    g3 = max((len(s[2]) for s in sonuclar), default=8)
    sat = [f"KAYRAN — NÖBETÇİ EŞİK ÖLÇÜMÜ · {BUGUN.strftime('%d.%m.%Y')}", ""]
    sat.append(f"{'ALAN'.ljust(g1)}  {'ÖLÇÜM'.ljust(g2)}  {'DEĞER'.rjust(g3)}  ÖNERİ")
    sat.append("─" * (g1 + g2 + g3 + 30))
    onceki = None
    for a, o, d, n in sonuclar:
        if onceki and a != onceki:
            sat.append("")
        sat.append(f"{a.ljust(g1)}  {o.ljust(g2)}  {d.rjust(g3)}  {n}")
        onceki = a
    return "\n".join(sat)


def telegram(metin):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("\n(Telegram atlandı — token/chat id yok)")
        return
    import requests
    for c in [x.strip() for x in chat.split(",") if x.strip()]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": c, "text": f"<pre>{metin}</pre>",
                      "parse_mode": "HTML"}, timeout=20)
            print(f"Telegram {c}: {r.status_code}")
        except Exception as e:
            print(f"Telegram {c} hata: {e}")


if __name__ == "__main__":
    rapor = tablo()
    print(rapor)
    telegram(rapor)

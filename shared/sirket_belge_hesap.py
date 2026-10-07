# -*- coding: utf-8 -*-
"""Şirket belgeleri — saf hesaplar (Ekim 2026). Streamlit'e ve veritabanına bağlı değil.

Yönetim › Şirket belgeleri sayfası (yalnız Yönetim yetkilileri) şirketin resmi belgelerini
(vergi levhası, sicil gazetesi, faaliyet belgesi, imza sirküleri …) ve şirket künyesini tutar.

  belge_kabul(ad, boyut)        dosya türü ve boyutu uygun mu?
  depo_yolu(tur, ad, an)        dosya alanındaki benzersiz yol
  sure_durumu(bitis, bugun)     geçerlilik: dolmuş / yaklaşıyor / geçerli / süresiz
  gruplandir(kayitlar)          türe göre: güncel sürüm + eski sürümler (tür sırası sabit)
  uyarilar(kayitlar, bugun)     süresi dolmuş ya da 30 gün içinde dolacak GÜNCEL belgeler
  zip_icerik(dosyalar)          [(ad, bytes)] → tek ZIP (aynı adlar numaralanır)
  kunye_birlestir(...)          şirket künyesi: varsayılan < secrets < ekranda kaydedilen
  edefter_kunye(ayar)           e-Defter ayarlarından künye önerisi (ilk açılışta form dolu gelsin)
  kunye_metni(kunye)            kopyalanabilir düz metin
"""
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime

TURLER = [
    "Vergi levhası",
    "Ticaret Sicil Gazetesi",
    "Oda faaliyet belgesi",
    "İmza sirküleri",
    "Oda kayıt belgesi",
    "Vergi borcu yoktur yazısı",
    "SGK borcu yoktur yazısı",
    "Ortak ve yetkili kimlikleri",
    "Banka bilgi yazısı (IBAN)",
    "Bilanço ve gelir tablosu",
    "Marka tescil",
    "Sertifika",
    "Diğer",
]
UZANTILAR = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
             "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "xls": "application/vnd.ms-excel",
             "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "doc": "application/msword"}
EN_FAZLA_MB = 20
UYARI_GUN = 30

KUNYE_ALANLARI = [  # (anahtar, ekran adı) — shared.sirket'in anahtarlarıyla aynı
    ("unvan", "Ticari unvan"), ("marka", "Marka"), ("vd", "Vergi dairesi"), ("vkn", "Vergi no"),
    ("mersis", "MERSİS no"), ("sicil", "Ticaret sicil no"), ("adres", "Adres"), ("tel", "Telefon"),
    ("mail", "E-posta"), ("web", "Web sitesi"),
]

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def uzanti(ad):
    ad = str(ad or "")
    return ad.rsplit(".", 1)[-1].lower() if "." in ad else ""


def belge_kabul(ad, boyut):
    """(uygun_mu, sebep). Sebep ekranda gösterilir."""
    u = uzanti(ad)
    if u not in UZANTILAR:
        return False, f"{ad}: bu dosya türü kabul edilmiyor (PDF, JPG, PNG, Excel, Word)."
    if not boyut:
        return False, f"{ad}: dosya boş."
    if boyut > EN_FAZLA_MB * 1024 * 1024:
        return False, f"{ad}: dosya {EN_FAZLA_MB} MB'tan büyük."
    return True, ""


def guvenli_ad(ad):
    """Dosya alanı için ASCII, boşluksuz ad: 'Vergi Levhası 2026.pdf' → 'vergi-levhasi-2026.pdf'."""
    ad = str(ad or "").translate(_TR)
    ad = unicodedata.normalize("NFKD", ad).encode("ascii", "ignore").decode()
    kok, u = (ad.rsplit(".", 1) + [""])[:2] if "." in ad else (ad, "")
    kok = re.sub(r"[^a-z0-9]+", "-", kok.lower()).strip("-")[:80] or "belge"
    u = re.sub(r"[^a-z0-9]", "", u.lower())[:5]
    return f"{kok}.{u}" if u else kok


def depo_yolu(tur, ad, an):
    """'vergi-levhasi/20261007-143000-vergi-levhasi-2026.pdf' — aynı adla ikinci yükleme ezmesin."""
    return f"{guvenli_ad(tur).split('.')[0]}/{an.strftime('%Y%m%d-%H%M%S')}-{guvenli_ad(ad)}"


def _tarih(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def sure_durumu(bitis, bugun, esik=UYARI_GUN):
    """(durum, kalan_gun). durum: 'suresiz' | 'dolmus' | 'yaklasiyor' | 'gecerli'."""
    b = _tarih(bitis)
    if b is None:
        return "suresiz", None
    kalan = (b - _tarih(bugun)).days
    if kalan < 0:
        return "dolmus", kalan
    if kalan <= esik:
        return "yaklasiyor", kalan
    return "gecerli", kalan


def _yenilik(r):
    """Aynı türde hangisi güncel: belge tarihi yeni olan; eşitse sonra yüklenen."""
    return (str(_tarih(r.get("belge_tarihi")) or ""), str(r.get("zaman") or ""), int(r.get("id") or 0))


def gruplandir(kayitlar):
    """[{tur, guncel, eskiler}] — TURLER sırasıyla, listede olmayan türler sonda (ada göre)."""
    g = {}
    for r in kayitlar or []:
        g.setdefault(str(r.get("tur") or "Diğer"), []).append(r)
    sira = {t: i for i, t in enumerate(TURLER)}
    out = []
    for tur in sorted(g, key=lambda t: (sira.get(t, len(TURLER)), t)):
        s = sorted(g[tur], key=_yenilik, reverse=True)
        out.append({"tur": tur, "guncel": s[0], "eskiler": s[1:]})
    return out


def uyarilar(kayitlar, bugun, esik=UYARI_GUN):
    """Yalnız GÜNCEL sürümler: [{tur, kayit, durum, kalan}] önce dolmuşlar, sonra en az gün kalan.
    Yenisi yüklenmiş eski belgenin süresi dolsa da uyarı vermez."""
    out = []
    for grp in gruplandir(kayitlar):
        durum, kalan = sure_durumu(grp["guncel"].get("bitis_tarihi"), bugun, esik)
        if durum in ("dolmus", "yaklasiyor"):
            out.append({"tur": grp["tur"], "kayit": grp["guncel"], "durum": durum, "kalan": kalan})
    return sorted(out, key=lambda u: u["kalan"])


def zip_icerik(dosyalar):
    """[(ad, bytes)] → ZIP bytes. Aynı ad ikinci kez gelirse 'ad (2).pdf' olur."""
    buf = io.BytesIO()
    goruldu = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for ad, veri in dosyalar:
            ad = str(ad or "belge")
            n = goruldu.get(ad.lower(), 0) + 1
            goruldu[ad.lower()] = n
            if n > 1:
                kok, u = ad.rsplit(".", 1) if "." in ad else (ad, "")
                ad = f"{kok} ({n}).{u}" if u else f"{kok} ({n})"
            z.writestr(ad, veri)
    return buf.getvalue()


def indirme_adi(r):
    """ZIP içindeki ad: 'Vergi levhası - 2026-03-01.pdf' (tür + belge tarihi)."""
    u = uzanti(r.get("ad")) or "pdf"
    t = _tarih(r.get("belge_tarihi"))
    return f"{r.get('tur') or 'Belge'}{' - ' + t.isoformat() if t else ''}.{u}"


def kunye_birlestir(varsayilan, secrets=None, kayitli=None):
    """Boş olmayan değer kazanır; öncelik: ekranda kaydedilen > secrets > varsayılan."""
    out = dict(varsayilan or {})
    for kaynak in (secrets or {}, kayitli or {}):
        for k, v in kaynak.items():
            if str(v or "").strip():
                out[k] = str(v).strip()
    return out


def edefter_kunye(ayar):
    """e-Defter ayarlarından künye önerisi (alan adları edefter_ayarlar tablosundan)."""
    a = ayar or {}
    adres = " ".join(str(a.get(k) or "").strip() for k in ("adres_cadde", "adres_cadde2", "adres_bina"))
    sehir = " ".join(str(a.get(k) or "").strip() for k in ("adres_posta", "adres_il"))
    adres = ", ".join(p for p in (" ".join(adres.split()), " ".join(sehir.split())) if p)
    return {k: v for k, v in {
        "unvan": str(a.get("unvan") or "").strip(), "vkn": str(a.get("vkn") or "").strip(),
        "adres": adres, "tel": str(a.get("telefon") or "").strip(),
        "mail": str(a.get("eposta") or "").strip(), "web": str(a.get("website") or "").strip(),
    }.items() if v}


def kunye_metni(kunye):
    """Kopyalanabilir düz metin; boş alanlar yazılmaz."""
    return "\n".join(f"{ad}: {str(kunye.get(k) or '').strip()}"
                     for k, ad in KUNYE_ALANLARI if str(kunye.get(k) or "").strip())

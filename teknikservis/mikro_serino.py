# -*- coding: utf-8 -*-
"""Teknik servis: seri numarasından Mikro bilgisi (Ekim 2026).

Kullanıcı isteği: seri no dosya yükleme / elle giriş yerine Mikro'dan. Aktarıcı (araclar/mikro_aktarici,
"serino" sorgusu) STOK_SERINO_TANIMLARI'nı mikro_serino tablosuna kopyalar (veritabani/47_mikro_serino.sql).
Bu modül seri no okununca / girilince şunları çıkarır: stok kodu (sku_anahtar), kime satıldı (cari ünvanı),
satış belgesi no ve tarihi, garanti bitişi ve "garantide / garanti dışı".

Kurallar:
  * Okuma birincil anahtar sırasıyla, kopya kayıt gelirse reddedilir (satis.mikro_esitle.kopyasiz).
  * Tablo yoksa (göç kurulmadı) ya da boşsa (aktarıcı henüz doldurmadı) oku() None döner; ekran eski
    davranışına sessizce döner.
  * Kayıtlı veri değiştirilmez: yalnız bilgi gösterilir, toplu mal kabulde BOŞ Stok Kodu / Firma doldurulur;
    dolu ve Mikro'yla çelişen alan değiştirilmez, uyarı verilir.
"""
from __future__ import annotations

from datetime import date, datetime

TABLO = "mikro_serino"
KOLONLAR = ("chz_guid,chz_serino,seri_anahtar,chz_stok_kodu,sto_isim,chz_iptal,chz_al_tarih,chz_al_cari_kodu,"
            "chz_st_tarih,chz_st_evr_seri,chz_st_evr_sira,chz_st_cari_kodu,chz_grn_bas_tarihi,chz_grn_bit_tarihi,"
            "chz_musteri_garanti_baslangic,chz_musteri_garanti_bitis,chz_lastup_date")
PARCA = 100                      # tek sorguda aranan seri no sayısı (URL uzunluğu)

# Seri no yerine yazılan değerler: Mikro'da aranmaz (mal kabuldeki mükerrer muafiyetiyle aynı)
SERISIZ = {"NOSERIALNUMBER", "N/A", "YOK", "-", "SERİYOK", "SERIYOK", ""}

GARANTIDE = "garantide"
GARANTI_DISI = "garanti dışı"
GARANTI_BILINMIYOR = "garanti bilinmiyor"

# Firma alanına yazılan ama bir cariyi göstermeyen değerler: çelişki denetlenmez
_GENEL_FIRMA = {"SON KULLANICI", "DIGER", "KANAL"}


# ── Saf fonksiyonlar ────────────────────────────────────────────────
def seri_anahtar(seri) -> str:
    """Karşılaştırma anahtarı: boşluklar atılır, BÜYÜK harf. Veritabanındaki üretilmiş kolonla aynı kural
    (upper(regexp_replace(chz_serino, '\\s', '', 'g'))). Seri no yerine yazılan değerler için boş döner."""
    s = "".join(str(seri or "").split()).upper()
    return "" if s in SERISIZ else s


def tarih(v):
    """Mikro tarihini date'e çevirir. Mikro boş tarihi 1899-12-30 / 1900-01-01 yazar: 1950 öncesi yok sayılır."""
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        d = v.date()
    elif isinstance(v, date):
        d = v
    else:
        try:
            d = datetime.fromisoformat(str(v).strip()[:10]).date()
        except ValueError:
            return None
    return d if d.year >= 1950 else None


def _iptal(k) -> bool:
    return str(k.get("chz_iptal") or "0").strip().lower() in ("1", "true")


def kayit_sec(kayitlar, stok_kodu=""):
    """Aynı seri no'nun birden çok tanımı olabilir (farklı ürün / yeniden giriş). İptaller atılır; girilen stok
    koduyla uyan tanım önce; sonra satışı en yeni, sonra alışı en yeni, sonra en son güncellenen."""
    from shared.utils import sku_anahtar
    adaylar = [k for k in (kayitlar or []) if not _iptal(k)]
    if not adaylar:
        return None
    hedef = sku_anahtar(stok_kodu) if str(stok_kodu or "").strip() else ""
    en_eski = date(1, 1, 1)

    def _sira(k):
        return (bool(hedef) and sku_anahtar(k.get("chz_stok_kodu")) == hedef,
                tarih(k.get("chz_st_tarih")) or en_eski,
                tarih(k.get("chz_al_tarih")) or en_eski,
                str(k.get("chz_lastup_date") or ""),
                str(k.get("chz_guid") or ""))
    return max(adaylar, key=_sira)


def belge_no(seri, sira) -> str:
    """Mikro belge numarası, uygulamadaki biçimle ('G5F26-2525'; satis.mikro_esitle.fatura_no)."""
    s, n = str(seri or "").strip(), str(sira or "").strip()
    if n.endswith(".0"):
        n = n[:-2]
    if n in ("", "0"):
        return ""
    return f"{s}-{n}" if s else n


def garanti(kayit, bugun):
    """(garanti bitişi, durum). Önce müşteri garantisi, yoksa genel garanti bitişi (Mikro'daki iki alan)."""
    bitis = tarih(kayit.get("chz_musteri_garanti_bitis")) or tarih(kayit.get("chz_grn_bit_tarihi"))
    if bitis is None:
        return None, GARANTI_BILINMIYOR
    return bitis, (GARANTIDE if bitis >= bugun else GARANTI_DISI)


def bilgi(kayit, unvanlar, bugun):
    """Ekranda gösterilecek bilgi. unvanlar: {cari_kod: cari ünvanı}."""
    from shared.utils import sku_anahtar
    if not kayit:
        return None
    cari = str(kayit.get("chz_st_cari_kodu") or "").strip()
    bitis, durum = garanti(kayit, bugun)
    return {
        "seri_no": str(kayit.get("chz_serino") or "").strip(),
        "stok_kodu": sku_anahtar(kayit.get("chz_stok_kodu")),
        "mikro_adi": str(kayit.get("sto_isim") or "").strip(),
        "cari_kodu": cari,
        "cari_unvan": str((unvanlar or {}).get(cari) or "").strip(),
        "satis_belge_no": belge_no(kayit.get("chz_st_evr_seri"), kayit.get("chz_st_evr_sira")),
        "satis_tarihi": tarih(kayit.get("chz_st_tarih")),
        "alis_tarihi": tarih(kayit.get("chz_al_tarih")),
        "garanti_bitis": bitis,
        "garanti_durumu": durum,
    }


def gruplandir(kayitlar):
    """{seri_anahtar: [kayıt]} — anahtar veritabanındaki kolon, yoksa seri no'dan üretilir."""
    out = {}
    for k in kayitlar or []:
        a = str(k.get("seri_anahtar") or "").strip() or seri_anahtar(k.get("chz_serino"))
        if a:
            out.setdefault(a, []).append(k)
    return out


def _norm(ad) -> str:
    from shared.utils import normalize_tr
    return " ".join(normalize_tr(ad).replace(".", " ").replace(",", " ").split())


def _bas_uyar(a, b) -> bool:
    """a ile b aynı ya da biri ötekinin baştan kelime sınırlı kısaltması ('VATAN' ↔ 'VATAN BILGISAYAR …')."""
    return bool(a and b) and (a == b or b.startswith(a + " ") or a.startswith(b + " "))


def _kisa(ad) -> str:
    """Ünvanın ayırt edici kısmı ('… SANAYİ VE TİCARET A.Ş.' atılır; shared.utils.firma_kisa_ad)."""
    from shared.utils import firma_kisa_ad
    return _norm(firma_kisa_ad(ad))


def firma_esle(unvan, liste):
    """Mikro ünvanını teknik servis firma listesindeki yazımda bulur (tek aday varsa); yoksa None.
    Sıra: birebir → biri ötekinin baş kısmı → kısa ad aynı ('… A.Ş.' ↔ '… ANONİM ŞİRKETİ')."""
    u = _norm(unvan)
    if not u:
        return None
    liste = [f for f in (liste or []) if _norm(f) and _norm(f) not in _GENEL_FIRMA]
    for kural in (lambda f: _norm(f) == u, lambda f: _bas_uyar(_norm(f), u), lambda f: _kisa(f) == _kisa(unvan)):
        adaylar = list(dict.fromkeys(f for f in liste if kural(f)))
        if adaylar:
            return adaylar[0] if len(adaylar) == 1 else None
    return None


def firma_uyumlu_mu(girilen, unvan):
    """Girilen firma Mikro'daki alıcıyla uyuşuyor mu. True / False; karşılaştırılamıyorsa (boş, SON KULLANICI,
    DİĞER) None. Firma kodu da kabul edilir ('HB' → D-MARKET, 'ITOPYA' → EERA; shared.utils.FIRMA_GORUNEN_AD)."""
    from shared.utils import FIRMA_GORUNEN_AD, firma_kanonik
    g, u = _norm(girilen), _norm(unvan)
    if not g or not u or g in _GENEL_FIRMA or firma_kanonik(girilen) == "DIGER":
        return None
    adlar = {g}
    kod = firma_kanonik(girilen)
    if kod in FIRMA_GORUNEN_AD:
        adlar.add(_norm(FIRMA_GORUNEN_AD[kod]))
    return any(_bas_uyar(a, u) for a in adlar) or _kisa(girilen) == _kisa(unvan)


def stok_uyumlu_mu(girilen, mikro_stok_kodu):
    from shared.utils import sku_anahtar
    g, m = sku_anahtar(girilen), sku_anahtar(mikro_stok_kodu)
    if not g or not m:
        return None
    return g == m


def satir_tamamla(stok_kodu, firma, b, firma_listesi=()):
    """Toplu mal kabul satırı: BOŞ Stok Kodu / Firma Mikro'dan doldurulur; dolu ve çelişen alan değişmez.
    Döner: (stok_kodu, firma, doldurulan alan adları, uyarılar)."""
    doldu, uyari = [], []
    stok_kodu, firma = str(stok_kodu or "").strip(), str(firma or "").strip()
    if not b:
        return stok_kodu, firma, doldu, uyari
    if not stok_kodu and b.get("stok_kodu"):
        stok_kodu = b["stok_kodu"]
        doldu.append("Stok Kodu")
    elif stok_uyumlu_mu(stok_kodu, b.get("stok_kodu")) is False:
        uyari.append(f"Stok Kodu {stok_kodu}, Mikro'da {b['stok_kodu']}")
    if not firma and b.get("cari_unvan"):
        firma = firma_esle(b["cari_unvan"], firma_listesi) or b["cari_unvan"]
        doldu.append("Firma")
    elif firma_uyumlu_mu(firma, b.get("cari_unvan")) is False:
        uyari.append(f"Firma {firma}, Mikro'da {b['cari_unvan']}")
    return stok_kodu, firma, doldu, uyari


def _gun(d) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


def bilgi_metni(b, firma_ad="", urun_adi=""):
    """Tek satırlık özet (ekran ve toplu önizleme)."""
    if not b:
        return ""
    parca = [f"Stok kodu {b['stok_kodu']}" + (f" ({urun_adi})" if urun_adi else "")]
    if b.get("cari_kodu"):
        satis = f"Satıldığı firma {firma_ad or b.get('cari_unvan') or b['cari_kodu']}"
        if b.get("satis_belge_no"):
            satis += f", belge {b['satis_belge_no']}"
        if b.get("satis_tarihi"):
            satis += f", {_gun(b['satis_tarihi'])}"
        parca.append(satis)
    else:
        parca.append("Mikro'da satışı yok")
    if b.get("garanti_bitis"):
        parca.append(f"Garanti bitişi {_gun(b['garanti_bitis'])} ({b['garanti_durumu']})")
    else:
        parca.append(b.get("garanti_durumu") or GARANTI_BILINMIYOR)
    return " · ".join(parca)


# ── Okuma (Supabase) ────────────────────────────────────────────────
def _cli():
    from teknikservis.database import get_client
    return get_client()


def oku(seriler, cli=None):
    """{seri_anahtar: [kayıt]} — yalnız istenen seri no'lar. Tablo yoksa / boşsa / okuma tutarsızsa None
    (ekran eski davranışına döner). Okuma chz_guid sırasıyla, kopya kayıt reddedilir."""
    from satis.mikro_esitle import kopyasiz
    anahtarlar = sorted({a for a in (seri_anahtar(s) for s in seriler or ()) if a})
    try:
        cli = cli or _cli()
        if not (cli.table(TABLO).select("chz_guid").limit(1).execute().data or []):
            return None
        satirlar = []
        for i in range(0, len(anahtarlar), PARCA):
            satirlar += (cli.table(TABLO).select(KOLONLAR).in_("seri_anahtar", anahtarlar[i:i + PARCA])
                         .order("chz_guid").execute().data or [])
        return gruplandir(kopyasiz(satirlar, "chz_guid"))
    except Exception:  # noqa: BLE001 — göç (47) kurulmadı / okuma tutarsız
        return None


def unvanlari_oku(kodlar, cli=None):
    """{cari_kod: cari_unvan1} — önce mikro_cari_kart, bulunamayanlar mikro_cari_bakiye. Okunamazsa boş."""
    from satis.mikro_esitle import kopyasiz
    kodlar = sorted({str(k or "").strip() for k in kodlar or () if str(k or "").strip()})
    out = {}
    if not kodlar:
        return out
    try:
        cli = cli or _cli()
        for i in range(0, len(kodlar), PARCA):
            for r in kopyasiz(cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1")
                              .in_("cari_kod", kodlar[i:i + PARCA]).order("cari_kod").execute().data or [],
                              "cari_kod"):
                out[str(r.get("cari_kod") or "").strip()] = str(r.get("cari_unvan1") or "").strip()
        eksik = [k for k in kodlar if not out.get(k)]
        for i in range(0, len(eksik), PARCA):
            for r in kopyasiz(cli.table("mikro_cari_bakiye").select("cari_kod,cari_unvan1,doviz")
                              .in_("cari_kod", eksik[i:i + PARCA]).order("cari_kod").order("doviz")
                              .execute().data or [], ("cari_kod", "doviz")):
                k = str(r.get("cari_kod") or "").strip()
                out.setdefault(k, str(r.get("cari_unvan1") or "").strip())
    except Exception:  # noqa: BLE001
        pass
    return out


def bul(seriler, stok_kodlari=None, bugun=None, cli=None):
    """{seri_anahtar: bilgi} — Mikro'da bulunan seri no'lar. stok_kodlari: {seri_anahtar: girilen stok kodu}
    (aynı seri no'nun birden çok tanımı varsa uyan seçilir). Tablo yoksa / boşsa None."""
    gruplar = oku(seriler, cli=cli)
    if gruplar is None:
        return None
    bugun = bugun or date.today()
    secilen = {a: kayit_sec(ks, (stok_kodlari or {}).get(a, "")) for a, ks in gruplar.items()}
    secilen = {a: k for a, k in secilen.items() if k}
    unvan = unvanlari_oku([k.get("chz_st_cari_kodu") for k in secilen.values()], cli=cli)
    return {a: bilgi(k, unvan, bugun) for a, k in secilen.items()}

# -*- coding: utf-8 -*-
"""Teknik servis depolarındaki ürünün satışı Mikro'dan (Ekim 2026). Ekran: Teknik Servis › Depolar.

Kullanıcı (22.10.2026): "Satıldı mevzusu manuel olarak benden tamamen kalksın. Teknik servis depolarından (outlet,
2. el, teknik servis, iade depo) satış yapıldığında Mikro'daki faturadan otomatik satıldı olsun; cari, fiyat, tarih
görünsün, faturayı da görebileyim. Seri no'dan yakalamak en sağlıklısı."

Kaynak: mikro_serino (STOK_SERINO_TANIMLARI kopyası; teknikservis/mikro_serino.py) son satış alanları. Kural:
  * Kayıt SATIS_DEPOLARI'ndan birinde, durumu satıldı / hurda / iptal / gönderildi değil, seri no'su var.
  * Mikro'da aynı seri no'nun son satışı (chz_st_tarih) kaydın depoya giriş tarihinden (depo_tarihi, yoksa mal
    kabul tarihi) SONRA ya da aynı gün ve bir müşteri carisine (120.) yapılmış.
  * Yazılan: durum 'satıldı', satış firması (cari ünvanı), satış fiyatı (Mikro'nun alternatif döviz = USD satış
    fiyatı), satış tarihi, satış fatura no. Stok ve P&L YAZILMAZ: ikisi de zaten Mikro'dan gelir.
"""
from __future__ import annotations

SATIS_DEPOLARI = ("outlet", "ikinci el", "teknik servis", "iade")
KAPALI = {"satıldı", "hurda", "iptal", "gönderildi"}
MUSTERI = "120."
DURUM_ANAHTAR = "ts_mikro_satis_durum"


def _s(v):
    return str(v or "").strip()


def _f(v):
    try:
        x = float(v)
        return x if x == x else 0.0
    except (TypeError, ValueError):
        return 0.0


def giris_gunu(k):
    """Kaydın depoya giriş günü (depo_tarihi, yoksa mal kabul tarihi), 'YYYY-MM-DD' ya da ''."""
    return (_s(k.get("depo_tarihi")) or _s(k.get("mal_kabul_tarihi")))[:10]


def aday_mi(k):
    return (_s(k.get("depo")).lower() in SATIS_DEPOLARI and _s(k.get("mevcut_durum")) not in KAPALI
            and bool(_s(k.get("seri_no"))))


def eslesmeler(kayitlar, serino, unvanlar=None):
    """Döner: [(kayıt, alanlar)]. serino: {seri_anahtar: [mikro_serino kaydı]} (mikro_serino.oku)."""
    from teknikservis.mikro_serino import belge_no, kayit_sec, seri_anahtar, tarih
    unvanlar = unvanlar or {}
    out = []
    for k in kayitlar or []:
        if not aday_mi(k):
            continue
        m = kayit_sec((serino or {}).get(seri_anahtar(k.get("seri_no"))) or [], k.get("stok_kodu"))
        if not m:
            continue
        cari = _s(m.get("chz_st_cari_kodu"))
        gun = tarih(m.get("chz_st_tarih"))
        if not cari.startswith(MUSTERI) or gun is None:
            continue
        giris = giris_gunu(k)
        if not giris or gun.isoformat() < giris:
            continue
        out.append((k, {
            "satis_firma": _s(unvanlar.get(cari)) or cari,
            "satis_fiyati": round(_f(m.get("chz_st_fiati_alt")), 4),
            "satis_tarihi": gun.isoformat(),
            "satis_fatura_no": belge_no(m.get("chz_st_evr_seri"), m.get("chz_st_evr_sira")),
            "bedelsiz": False,
        }))
    return out


def gecmis_metni(alanlar):
    return (f"Mikro satış faturası {alanlar['satis_fatura_no'] or '—'} · {alanlar['satis_firma']}"
            f" · {alanlar['satis_fiyati']:.2f} $")


# ── Veritabanı ─────────────────────────────────────────────────────
_SERINO_KOLON = ("chz_guid,chz_serino,seri_anahtar,chz_stok_kodu,chz_iptal,chz_al_tarih,chz_st_tarih,chz_st_evr_seri,"
                 "chz_st_evr_sira,chz_st_cari_kodu,chz_st_fiati_alt,chz_lastup_date")


def veri_oku():
    from teknikservis import mikro_serino as MS
    from teknikservis.database import get_client
    cli = get_client()
    kayitlar = [k for k in (cli.table("ts_kayitlar").select(
        "id,servis_form_no,stok_kodu,seri_no,depo,mevcut_durum,depo_tarihi,mal_kabul_tarihi").execute().data or [])
        if aday_mi(k)]
    anahtarlar = sorted({MS.seri_anahtar(k.get("seri_no")) for k in kayitlar} - {""})
    serino = {}
    for i in range(0, len(anahtarlar), MS.PARCA):
        for r in (cli.table(MS.TABLO).select(_SERINO_KOLON).in_("seri_anahtar", anahtarlar[i:i + MS.PARCA])
                  .execute().data or []):
            serino.setdefault(_s(r.get("seri_anahtar")) or MS.seri_anahtar(r.get("chz_serino")), []).append(r)
    cariler = {_s(m.get("chz_st_cari_kodu")) for v in serino.values() for m in v}
    return kayitlar, serino, MS.unvanlari_oku(cariler, cli)


def uygula(eslesen, personel="Mikro"):
    from teknikservis.database import durum_guncelle
    n, hata = 0, []
    for k, alanlar in eslesen:
        try:
            if durum_guncelle(k["id"], "satıldı", personel, gecmis_metni(alanlar), alanlar):
                n += 1
        except Exception as e:  # noqa: BLE001
            hata.append(f"{k.get('servis_form_no')}: {type(e).__name__}")
    return n, hata


def otomatik():
    """Eşitleme turu (otonom/mikro_esitle.ISLER). Yazdıysa metin, yoksa None. Hata fırlatmaz."""
    try:
        kayitlar, serino, unvan = veri_oku()
        es = eslesmeler(kayitlar, serino, unvan)
        if not es:
            return None
        n, hata = uygula(es)
        return f"teknik servis: {n} ürün Mikro satışından satıldı" + (f" ({len(hata)} hata)" if hata else "")
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("teknikservis.mikro_satis.otomatik", e)
        return None

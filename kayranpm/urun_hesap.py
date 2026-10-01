# -*- coding: utf-8 -*-
"""Ürün Yönetimi — saf hesaplar (Ekim 2026). Veritabanına gitmez, test edilir.

  dashboard_filtrele   Firma / kategori filtresi (Dashboard metrik ve pencereleri)
  editor_anahtari      st.data_editor anahtarı — gösterilen ürün listesine bağlı
  urun_satiri          Tüm Ürünler satırı (paçal, son maliyet, net kâr, marj…)
  urun_filtrele_sirala Tüm Ürünler arama / filtre / sıralama
  bekleyen_haritasi    Sipariş önerisi: SKU → bekleyen toplam adet
  siparis_durum_adi    'onaylandi' → 'Onaylandı'
  yukleme_ozeti        Veri Yükleme › geçmiş yüklemeler (tek geçişte sayım)
  tarih_tr             ISO tarih → GG.AA.YYYY
"""
import hashlib
from collections import Counter, defaultdict

_ASCII = str.maketrans("İIĞÜŞÇÖığüşçö", "IIGUSCOigusco")


def _asc(s):
    return str(s or "").translate(_ASCII).upper()


def _kucuk(s):
    return str(s or "").strip().replace("I", "ı").replace("İ", "i").lower()


def tarih_tr(v, saat=False):
    s = str(v or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        t = f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
        if saat and len(s) >= 16 and s[10] in "T ":
            t += f" {s[11:16]}"
        return t
    return s


# ── Dashboard ───────────────────────────────────────────────────────
def dashboard_filtrele(veri, firma, kategori, tum_firma="Tüm Firmalar", tum_kat="Tüm Kategoriler"):
    """Firma seçiliyse: o firmada stoğu olan ürünler. Kategori seçiliyse: o kategori."""
    out = []
    hedef = _asc(firma)
    for u in veri or []:
        if kategori != tum_kat and _kucuk(u.get("kategori")) != _kucuk(kategori):
            continue
        if firma != tum_firma and not any(
                (fd.get("stok") or 0) > 0 and hedef in _asc(fd.get("firma"))
                for fd in (u.get("firma_detay") or [])):
            continue
        out.append(u)
    return out


# ── Maliyet Girişi ──────────────────────────────────────────────────
def editor_anahtari(onek, skular):
    """Düzenleyici değişiklikleri satır SIRASIYLA saklar. Anahtar gösterilen listeye
    bağlanır: liste değişince eski değişiklikler hiçbir sürümde başka satıra
    uygulanmaz, açıkça sıfırlanır (ekran ayrıca uyarır)."""
    h = hashlib.md5("\x1f".join(str(s) for s in skular).encode("utf-8")).hexdigest()[:10]
    return f"{onek}_{h}"


# ── Tüm Ürünler ─────────────────────────────────────────────────────
KANALLAR = ("ITOPYA", "HB", "VATAN", "MONDAY", "KANAL")
# Kart etiketleri cümle düzenine indirilir (shared.tasarim.kpi_etiketi): "HB" → "Hb".
# Küçük harf içeren ad olduğu gibi kalır.
KANAL_AD = {"ITOPYA": "İtopya", "HB": "Hepsiburada", "VATAN": "Vatan", "MONDAY": "Monday",
            "KANAL": "Kanal", "DIGER": "Diğer"}


def urun_satiri(u):
    fs = u.get("firma_stoklari") or {}
    satis = float(u.get("satis_fiyati") or 0)
    ith_var = (u.get("ithalat_dosya_sayisi", 0) or 0) > 0
    fcp = float(u.get("final_cost_price") or 0) if ith_var else 0.0
    fob = float(u.get("fob_price") or 0) if ith_var else 0.0
    son_fob = float(u.get("son_fob") or 0) if ith_var else 0.0
    son_fcp = float(u.get("son_final") or 0) if ith_var else 0.0
    maliyet_yuzde = ((fcp / fob - 1) * 100) if (fob > 0 and fcp > 0) else None
    net_kar = (satis - fcp) if (satis > 0 and fcp > 0) else None
    net_marj = (net_kar / satis * 100) if (net_kar is not None and satis > 0) else None
    r = {
        "SKU": u.get("sku", ""),
        "Ürün Adı": u.get("urun_adi", "") or "",
        "Kategori": u.get("kategori", "") or "",
        "Marka": u.get("marka", "") or "",
        "_stok_yas": int(u.get("stok_gun", 0) or 0),
        "_stok_renk": u.get("stok_renk", "yok"),
        "_risk": float(u.get("risk_skor", 0) or 0),
        "_eol": bool(u.get("eol")),
        "G5F Depo": int(u.get("bizim_stok", 0) or 0),
    }
    for k in KANALLAR:
        r[k] = int(fs.get(k, 0) or 0)
    r.update({
        "Toplam": int(u.get("toplam_stok", u.get("bizim_stok", 0)) or 0),
        "FOB ($)": fob if ith_var else None,
        "Son FOB ($)": son_fob if (ith_var and son_fob) else None,
        "Maliyet %": maliyet_yuzde,
        "Final Cost ($)": fcp if ith_var else None,
        "Son Maliyet ($)": son_fcp if (ith_var and son_fcp) else None,
        "Satış ($)": satis,
        "Net Marj (%)": net_marj,
        "Net Kar ($)": net_kar,
    })
    return r


SIRALAR = {"Stok yaşı (gün)": "_stok_yas", "Net kâr ($)": "Net Kar ($)", "Net marj (%)": "Net Marj (%)",
           "Maliyet %": "Maliyet %", "Toplam stok": "Toplam", "Satış ($)": "Satış ($)",
           "FOB ($)": "FOB ($)", "Risk skoru": "_risk", "SKU (A-Z)": "SKU"}


def urun_filtrele_sirala(rows, ara="", kategori="Tümü", marka="Tümü", sadece_zarar=False,
                         sira=None, azalan=True):
    q = str(ara or "").strip().lower()
    out = []
    for r in rows:
        if q and q not in f"{r.get('SKU', '')} {r.get('Ürün Adı', '')}".lower():
            continue
        if kategori != "Tümü" and _kucuk(r.get("Kategori")) != _kucuk(kategori):
            continue
        if marka != "Tümü" and str(r.get("Marka") or "").strip() != marka:
            continue
        if sadece_zarar and not (r.get("Net Kar ($)") is not None and r["Net Kar ($)"] < 0):
            continue
        out.append(r)
    if not sira:
        return out
    if sira == "SKU":
        return sorted(out, key=lambda r: str(r.get("SKU") or "").lower(), reverse=azalan)
    dolu = [r for r in out if r.get(sira) not in (None, "")]
    bos = [r for r in out if r.get(sira) in (None, "")]
    dolu.sort(key=lambda r: float(r.get(sira) or 0), reverse=azalan)
    return dolu + bos                                  # boşlar her zaman sonda


# ── Sipariş Önerisi ─────────────────────────────────────────────────
_DURUM_AD = {"bekliyor": "Bekliyor", "onaylandi": "Onaylandı", "reddedildi": "Reddedildi"}


def siparis_durum_adi(d):
    return _DURUM_AD.get(str(d or ""), str(d or "—"))


def bekleyen_haritasi(oneriler):
    h = defaultdict(int)
    for sp in oneriler or []:
        if sp.get("durum") == "bekliyor":
            h[sp.get("sku")] += int(sp.get("oneri_miktari") or 0)
    return dict(h)


# ── Veri Yükleme ────────────────────────────────────────────────────
def yukleme_ozeti(firma_rows, urun_rows):
    """Eskiden her tarih için tüm satırlar yeniden taranıyordu (tarih × satır)."""
    firma_say = Counter()
    firmalar = defaultdict(set)
    for r in firma_rows or []:
        t = r.get("yukleme_tarihi")
        firma_say[t] += 1
        firmalar[t].add(r.get("firma"))
    urun_say = Counter(r.get("guncelleme_tarihi") for r in urun_rows or [] if r.get("guncelleme_tarihi"))
    tarihler = sorted(set(firma_say) | set(urun_say), key=str, reverse=True)
    return [{"Tarih": tarih_tr(t), "Yüklenen Ürün": urun_say.get(t, 0),
             "Firma Kayıt Sayısı": firma_say.get(t, 0),
             "Firmalar": ", ".join(sorted(f for f in firmalar.get(t, ()) if f)) or "—",
             "_ham": t} for t in tarihler]

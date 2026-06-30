# -*- coding: utf-8 -*-
"""Satış & Kârlılık — veritabanı katmanı (USD bazlı).

Tablo: satislar — her satır bir satış işlemi.
COGS = güncel paçal (ağırlıklı ortalama landed) — İthalat'tan çekilir, kayıt anında
birim_maliyet olarak SABİTLENİR (sonradan maliyet değişse de geçmiş kâr bozulmaz).
Kâr (USD):
  ciro     = adet * birim_satis
  maliyet  = adet * birim_maliyet
  destek   = adet * (birim_firma_destek + birim_ek_destek)
  net_kar  = ciro - maliyet - destek
  marj %   = net_kar / ciro * 100
"""
from datetime import datetime, timezone, timedelta

import streamlit as st
from supabase import create_client, Client

TR_TZ = timezone(timedelta(hours=3))

# Satış kanalları (firma/pazar) — varsayılan; Muhasebe carileri varsa onlar kullanılır.
KANALLAR = ["İTOPYA", "HB", "VATAN", "MONDAY", "KANAL", "Trendyol", "Direkt", "DİGER"]


@st.cache_data(ttl=120, show_spinner=False)
def get_kanallar():
    """Kanal/firma listesi: Muhasebe'deki cari isimleri (varsa); yoksa varsayılan KANALLAR."""
    try:
        from kayranacc.database import get_cari_isimler
        cari = get_cari_isimler() or []
        if cari:
            return cari
    except Exception:
        pass
    return KANALLAR


@st.cache_resource
def _get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    from shared.audit import wrap_client
    return wrap_client(create_client(url, key), "Satış")


def _rows(resp):
    return resp.data if resp.data else []


def _row(resp):
    d = resp.data if resp.data else None
    return d[0] if isinstance(d, list) and d else (d or None)


def _f(v, d=0.0):
    try:
        if v is None or v == "":
            return float(d)
        return float(v)
    except (TypeError, ValueError):
        return float(d)


def _i(v, d=0):
    try:
        return int(round(_f(v, d)))
    except (TypeError, ValueError):
        return int(d)


def _bugun():
    return datetime.now(TR_TZ).date().isoformat()


# ── Maliyet (paçal) ve ürün katalogu — İthalat / Ürün Yönetimi'nden ──
@st.cache_data(ttl=120, show_spinner=False)
def get_pacal_map():
    """{sku: pacal_final} — güncel ağırlıklı ortalama landed maliyet (USD)."""
    try:
        from ithalat.database import get_sku_maliyet_ozet
        ozet = get_sku_maliyet_ozet() or {}
        return {sku: _f(v.get("pacal_final")) for sku, v in ozet.items()}
    except Exception:
        return {}


@st.cache_data(ttl=120, show_spinner=False)
def get_urunler():
    """Ürün katalogu: [{sku, urun_adi, satis_fiyati, satis_fiyat_listesi}]."""
    try:
        rows = _rows(_get_client().table("urunler")
                     .select("sku, urun_adi, satis_fiyati, satis_fiyat_listesi").execute())
        return rows
    except Exception:
        return []


@st.cache_data(ttl=120, show_spinner=False)
def kampanya_destek_bul(sku, kanal, tarih):
    """Verilen SKU + kanal + tarih için aktif kampanyadaki destekleri döndürür.
    Döner: (birim_firma_destek, birim_ek_destek, kampanya_id) veya (0, 0, None)."""
    try:
        sb = _get_client()
        t = str(tarih)[:10]
        kampanyalar = _rows(sb.table("kampanyalar").select("*").execute())
        uygun = [k for k in kampanyalar
                 if str(k.get("firma", "")).strip().upper() == str(kanal).strip().upper()
                 and str(k.get("baslangic_tarihi", ""))[:10] <= t <= str(k.get("bitis_tarihi", "9999"))[:10]]
        if not uygun:
            return 0.0, 0.0, None
        kids = [k["id"] for k in uygun]
        kurunler = _rows(sb.table("kampanya_urunler").select("*").in_("kampanya_id", kids).eq("sku", sku).execute())
        if not kurunler:
            return 0.0, 0.0, None
        ku = kurunler[0]
        return _f(ku.get("birim_firma_destek")), _f(ku.get("birim_ek_destek")), ku.get("kampanya_id")
    except Exception:
        return 0.0, 0.0, None


# ── Satış CRUD ──
def ekle_satis(tarih, kanal, sku, urun_adi, adet, birim_satis, birim_maliyet,
               birim_firma_destek=0, birim_ek_destek=0, kampanya_id=None, notlar="", siparis_no=""):
    try:
        _get_client().table("satislar").insert({
            "tarih": str(tarih)[:10], "kanal": kanal or "", "sku": sku or "",
            "urun_adi": urun_adi or "", "adet": _i(adet),
            "birim_satis": _f(birim_satis), "birim_maliyet": _f(birim_maliyet),
            "birim_firma_destek": _f(birim_firma_destek), "birim_ek_destek": _f(birim_ek_destek),
            "kampanya_id": kampanya_id, "notlar": notlar or "", "siparis_no": siparis_no or "",
            "olusturma_tarihi": datetime.now(TR_TZ).isoformat(timespec="seconds"),
        }).execute()
        _temizle()
        return True, "✅ Satış kaydedildi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def ekle_siparis(tarih, kanal, siparis_no, notlar, kalemler):
    """Tek siparişte birden çok kalemi TEK seferde kaydeder (toplu insert).
    kalemler: [{sku, urun_adi, adet, birim_satis, birim_maliyet,
                birim_firma_destek, birim_ek_destek, kampanya_id}, ...]
    Döner: (ok, mesaj, kalem_sayisi)."""
    rows = []
    zaman = datetime.now(TR_TZ).isoformat(timespec="seconds")
    for k in (kalemler or []):
        sku = str(k.get("sku") or "").strip()
        if not sku or _i(k.get("adet")) <= 0:
            continue
        rows.append({
            "tarih": str(tarih)[:10], "kanal": kanal or "", "siparis_no": siparis_no or "",
            "sku": sku, "urun_adi": k.get("urun_adi") or "", "adet": _i(k.get("adet")),
            "birim_satis": _f(k.get("birim_satis")), "birim_maliyet": _f(k.get("birim_maliyet")),
            "birim_firma_destek": _f(k.get("birim_firma_destek")), "birim_ek_destek": _f(k.get("birim_ek_destek")),
            "kampanya_id": k.get("kampanya_id"), "notlar": notlar or "", "olusturma_tarihi": zaman,
        })
    if not rows:
        return False, "Geçerli kalem yok.", 0
    try:
        _get_client().table("satislar").insert(rows).execute()
        _temizle()
        return True, f"✅ Sipariş kaydedildi — {len(rows)} kalem.", len(rows)
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


def get_mevcut_siparis_nolar():
    """satislar tablosundaki tüm benzersiz sipariş numaraları (mükerrer kontrolü için).
    1000'erli sayfalarla TÜM kayıtlar taranır."""
    try:
        cli = _get_client()
        nolar, adim, bas = set(), 1000, 0
        while True:
            chunk = _rows(cli.table("satislar").select("siparis_no")
                          .order("id", desc=True).range(bas, bas + adim - 1).execute())
            if not chunk:
                break
            for r in chunk:
                s = str(r.get("siparis_no") or "").strip()
                if s:
                    nolar.add(s)
            if len(chunk) < adim:
                break
            bas += adim
        return nolar
    except Exception:
        return set()


def sil_siparisler(siparis_nolar):
    """Verilen sipariş numaralarına ait TÜM satış satırlarını siler (toplu)."""
    nolar = [s for s in {str(x).strip() for x in (siparis_nolar or [])} if s]
    if not nolar:
        return 0, None
    try:
        cli = _get_client()
        B = 100
        for i in range(0, len(nolar), B):
            cli.table("satislar").delete().in_("siparis_no", nolar[i:i + B]).execute()
        _temizle()
        return len(nolar), None
    except Exception as e:
        return 0, f"{type(e).__name__}: {str(e)[:160]}"


def ice_aktar_satislar(satirlar, atla_mevcut=True, temizle_once=False, ilerleme=None):
    """Geçmiş satışları toplu içe aktarır (Excel/Mikro dökümünden).

    satirlar: [{tarih, kanal, sku, urun_adi, adet, birim_satis, siparis_no, notlar}, ...]
    Maliyet (birim_maliyet) güncel PAÇAL haritasından otomatik doldurulur.
    temizle_once=True : dosyadaki fatura no'ları önce silinir (kısmi/bozuk kayıtları temizler), sonra eklenir.
    atla_mevcut=True  : (temizle_once kapalıyken) zaten kayıtlı fatura no'larını atlar.
    Her grup ayrı yazılır; biri patlarsa satır satır denenir, gerçekte eklenen sayılır.
    Döner: {eklendi, atlandi, maliyetsiz, silinen_fatura, hatali, hata}.
    """
    pacal = get_pacal_map()
    zaman = datetime.now(TR_TZ).isoformat(timespec="seconds")

    dosya_faturalar = {str(s.get("siparis_no") or "").strip()
                       for s in (satirlar or []) if str(s.get("siparis_no") or "").strip()}

    silinen = 0
    if temizle_once and dosya_faturalar:
        silinen, sil_hata = sil_siparisler(dosya_faturalar)
        if sil_hata:
            return {"eklendi": 0, "atlandi": 0, "maliyetsiz": 0, "silinen_fatura": 0,
                    "hatali": 0, "hata": "Silme hatası: " + sil_hata}

    mevcut = get_mevcut_siparis_nolar() if (atla_mevcut and not temizle_once) else set()

    rows, atlandi, maliyetsiz = [], 0, 0
    for s in (satirlar or []):
        sno = str(s.get("siparis_no") or "").strip()
        if atla_mevcut and not temizle_once and sno and sno in mevcut:
            atlandi += 1
            continue
        sku = str(s.get("sku") or "").strip()
        if not sku or _i(s.get("adet")) <= 0:
            continue
        tarih = str(s.get("tarih") or "")[:10]
        if not tarih:           # boş tarih insert'i patlatır → atla
            continue
        bm = _f(pacal.get(sku, 0))
        if bm <= 0:
            maliyetsiz += 1
        rows.append({
            "tarih": tarih, "kanal": s.get("kanal") or "",
            "siparis_no": sno, "sku": sku, "urun_adi": s.get("urun_adi") or "",
            "adet": _i(s.get("adet")), "birim_satis": _f(s.get("birim_satis")),
            "birim_maliyet": bm, "birim_firma_destek": 0, "birim_ek_destek": 0,
            "kampanya_id": None, "notlar": s.get("notlar") or "", "olusturma_tarihi": zaman,
        })
    if not rows:
        return {"eklendi": 0, "atlandi": atlandi, "maliyetsiz": 0,
                "silinen_fatura": silinen, "hatali": 0, "hata": None}

    cli = _get_client()
    B = 200
    eklendi, hatali, ilk_hata = 0, 0, None
    for i in range(0, len(rows), B):
        chunk = rows[i:i + B]
        try:
            cli.table("satislar").insert(chunk).execute()
            eklendi += len(chunk)
        except Exception:
            # Grup patladı → satır satır dene, sorunlu satırı izole et
            for row in chunk:
                try:
                    cli.table("satislar").insert(row).execute()
                    eklendi += 1
                except Exception as e2:
                    hatali += 1
                    if ilk_hata is None:
                        ilk_hata = f"{type(e2).__name__}: {str(e2)[:120]}"
        if ilerleme:
            ilerleme(min(i + B, len(rows)), len(rows))
    _temizle()
    return {"eklendi": eklendi, "atlandi": atlandi, "maliyetsiz": maliyetsiz,
            "silinen_fatura": silinen, "hatali": hatali, "hata": ilk_hata}


def guncelle_satis(satis_id, alanlar):
    try:
        _get_client().table("satislar").update(alanlar).eq("id", satis_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def sil_satis(satis_id):
    try:
        _get_client().table("satislar").delete().eq("id", satis_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def sil_siparis(siparis_no):
    """Bir sipariş numarasına ait tüm kalemleri siler."""
    try:
        _get_client().table("satislar").delete().eq("siparis_no", siparis_no).execute()
        _temizle()
        return True
    except Exception:
        return False


@st.cache_data(ttl=30, show_spinner=False)
def get_satislar(baslangic=None, bitis=None):
    """Tarih aralığına göre satışlar (yeni→eski). baslangic/bitis: 'YYYY-MM-DD' veya None.
    Supabase tek sorguda en fazla 1000 satır döndürür; bu yüzden 1000'erli sayfalarla
    TÜM satırlar çekilir (binlerce geçmiş satış için şart)."""
    try:
        cli = _get_client()
        tum, adim, bas = [], 1000, 0
        while True:
            q = cli.table("satislar").select("*")
            if baslangic:
                q = q.gte("tarih", str(baslangic)[:10])
            if bitis:
                q = q.lte("tarih", str(bitis)[:10])
            q = q.order("tarih", desc=True).order("id", desc=True).range(bas, bas + adim - 1)
            chunk = _rows(q.execute())
            if not chunk:
                break
            tum.extend(chunk)
            if len(chunk) < adim:
                break
            bas += adim
        return tum
    except Exception:
        return []


def _temizle():
    try:
        get_satislar.clear()
    except Exception:
        pass
    try:
        get_iadeler.clear()
    except Exception:
        pass


def _normalize_sku_yerel(s):
    """SKU'yu paçal eşleştirmesi için normalize eder ('Fazeon X24F165S' → 'X24F165S')."""
    try:
        from kayranpm.excel_islemler import normalize_sku
        return normalize_sku(s)
    except Exception:
        s = str(s or "").strip()
        for p in ("FAZEON ", "Fazeon ", "fazeon "):
            if s.startswith(p):
                s = s[len(p):]
                break
        return s.strip().upper()


def satis_maliyet_tazele_onizle(sadece_sifir=True):
    """satislar.birim_maliyet'i güncel paçal (normalize SKU eşleşmeli) ile karşılaştırır.
    sadece_sifir=True → yalnız maliyeti 0/eksik olup paçalı bulunan satışlar.
    HİÇBİR ŞEY YAZMAZ. Döner: list[{sku, urun, satir, adet, yeni_birim}] (SKU bazında özet)."""
    pacal = get_pacal_map()
    satislar = get_satislar()
    sku_ozet = {}
    for s in satislar:
        nsku = _normalize_sku_yerel(s.get("sku"))
        p = _f(pacal.get(nsku, 0))
        if p <= 0:
            continue
        mevcut = _f(s.get("birim_maliyet"))
        if sadece_sifir and mevcut > 0:
            continue
        if not sadece_sifir and abs(mevcut - p) < 0.005:
            continue
        o = sku_ozet.setdefault(nsku, {"urun": s.get("urun_adi", "") or "", "satir": 0, "adet": 0, "yeni_birim": p})
        o["satir"] += 1
        o["adet"] += _i(s.get("adet"))
        o["yeni_birim"] = p
    return [{"sku": k, **v} for k, v in sorted(sku_ozet.items())]


def satis_maliyet_tazele_uygula(sadece_sifir=True):
    """satislar.birim_maliyet'i normalize SKU ile eşleşen güncel paçaldan yeniden yazar.
    HAM SKU bazında TOPLU update yapar (her benzersiz SKU için tek istek) — binlerce satır
    için satır-satır yerine saniyeler sürer.
    sadece_sifir=True → yalnız maliyeti 0 olanlar (mevcut doğru maliyetlere dokunmaz).
    Döner: (ok, mesaj)."""
    sb = _get_client()
    pacal = get_pacal_map()
    satislar = get_satislar()
    # Benzersiz HAM SKU → paçal (normalize ile eşleştir). Aynı SKU'nun tüm satırları aynı maliyeti alır.
    ham_pacal = {}
    for s in satislar:
        ham = str(s.get("sku") or "")
        if ham and ham not in ham_pacal:
            ham_pacal[ham] = _f(pacal.get(_normalize_sku_yerel(ham), 0))
    guncellenen_sku = 0
    for ham, p in ham_pacal.items():
        if p <= 0:
            continue
        try:
            q = sb.table("satislar").update({"birim_maliyet": round(p, 4)}).eq("sku", ham)
            if sadece_sifir:
                q = q.lte("birim_maliyet", 0)   # yalnız maliyeti 0 olan satırlar
            q.execute()
            guncellenen_sku += 1
        except Exception:
            pass
    _temizle()
    if not guncellenen_sku:
        return True, "Güncellenecek satış bulunamadı — maliyeti 0 olup paçalı bilinen SKU yok."
    return True, f"✅ {guncellenen_sku} SKU'nun maliyeti paçaldan toplu güncellendi (maliyeti 0 olan satışlar)."


# ── Kâr hesabı ──
def satir_kar(s):
    """Tek satış satırı için kâr metrikleri (USD)."""
    adet = _i(s.get("adet"))
    ciro = adet * _f(s.get("birim_satis"))
    maliyet = adet * _f(s.get("birim_maliyet"))
    destek = adet * (_f(s.get("birim_firma_destek")) + _f(s.get("birim_ek_destek")))
    net = ciro - maliyet - destek
    marj = (net / ciro * 100) if ciro > 0 else 0.0
    return {"adet": adet, "ciro": ciro, "maliyet": maliyet, "destek": destek,
            "net_kar": net, "marj": marj}


def ozet_hesapla(satislar):
    """Liste için toplam P&L + kanal/SKU kırılımı."""
    top = {"ciro": 0.0, "maliyet": 0.0, "destek": 0.0, "net_kar": 0.0, "adet": 0}
    kanal, urun = {}, {}
    for s in satislar:
        k = satir_kar(s)
        for f in ("ciro", "maliyet", "destek", "net_kar", "adet"):
            top[f] += k[f]
        kn = s.get("kanal", "") or "—"
        kanal.setdefault(kn, {"ciro": 0.0, "net_kar": 0.0, "adet": 0})
        kanal[kn]["ciro"] += k["ciro"]; kanal[kn]["net_kar"] += k["net_kar"]; kanal[kn]["adet"] += k["adet"]
        su = s.get("sku", "") or "—"
        urun.setdefault(su, {"urun_adi": s.get("urun_adi", ""), "ciro": 0.0, "net_kar": 0.0, "adet": 0})
        urun[su]["ciro"] += k["ciro"]; urun[su]["net_kar"] += k["net_kar"]; urun[su]["adet"] += k["adet"]
    top["marj"] = (top["net_kar"] / top["ciro"] * 100) if top["ciro"] > 0 else 0.0
    return top, kanal, urun


def siparis_no_var_mi(sipno):
    """Bu sipariş no daha önce kullanılmış mı (mükerrer kontrolü)."""
    try:
        s = (sipno or "").strip()
        if not s:
            return False
        r = _get_client().table("satislar").select("id").eq("siparis_no", s).limit(1).execute()
        return bool(r.data)
    except Exception:
        return False


# ── İADELER · satışı bozmadan ayrı tutulur; rapor Satış / İade / Net ─────────
def ekle_iade(tarih, kanal, sku, urun_adi, iade_adet,
              iade_brut=0, iade_iskonto=0, iade_masraf=0, iade_net=0):
    try:
        _get_client().table("iadeler").insert({
            "tarih": str(tarih)[:10], "kanal": kanal or "", "sku": (sku or "").strip(),
            "urun_adi": urun_adi or "", "iade_adet": _i(iade_adet),
            "iade_brut": _f(iade_brut), "iade_iskonto": _f(iade_iskonto),
            "iade_masraf": _f(iade_masraf), "iade_net": _f(iade_net),
        }).execute()
        _temizle()
        return True, "✅ İade kaydedildi"
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:140]}"


@st.cache_data(ttl=60, show_spinner=False)
def get_iadeler(baslangic=None, bitis=None):
    try:
        cli = _get_client()
        tum, adim, bas = [], 1000, 0
        while True:
            q = cli.table("iadeler").select("*")
            if baslangic:
                q = q.gte("tarih", str(baslangic)[:10])
            if bitis:
                q = q.lte("tarih", str(bitis)[:10])
            q = q.order("tarih", desc=True).order("id", desc=True).range(bas, bas + adim - 1)
            chunk = _rows(q.execute())
            if not chunk:
                break
            tum.extend(chunk)
            if len(chunk) < adim:
                break
            bas += adim
        return tum
    except Exception:
        return []


def sil_iade(iade_id):
    try:
        _get_client().table("iadeler").delete().eq("id", iade_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def guncelle_iade(iade_id, alanlar):
    try:
        _get_client().table("iadeler").update(alanlar).eq("id", iade_id).execute()
        _temizle()
        return True
    except Exception:
        return False


def ice_aktar_iadeler(satirlar, tarih, temizle_once=False):
    """satirlar: [{sku, urun_adi, kanal, iade_adet, iade_brut, iade_iskonto, iade_masraf, iade_net}].
    tarih: dönem tarihi (hepsine yazılır). temizle_once: aynı tarihli iadeleri önce siler.
    Döner: {eklendi, atlandi}."""
    try:
        cli = _get_client()
        if temizle_once and tarih:
            cli.table("iadeler").delete().eq("tarih", str(tarih)[:10]).execute()
        rows, atlandi = [], 0
        for s in satirlar:
            sku = str(s.get("sku") or "").strip()
            adet = _i(s.get("iade_adet"))
            if not sku or adet <= 0:
                atlandi += 1
                continue
            rows.append({
                "tarih": str(tarih)[:10], "kanal": s.get("kanal") or "",
                "sku": sku, "urun_adi": s.get("urun_adi") or "",
                "iade_adet": adet, "iade_brut": _f(s.get("iade_brut")),
                "iade_iskonto": _f(s.get("iade_iskonto")), "iade_masraf": _f(s.get("iade_masraf")),
                "iade_net": _f(s.get("iade_net")),
            })
        eklendi = 0
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            cli.table("iadeler").insert(chunk).execute()
            eklendi += len(chunk)
        _temizle()
        return {"eklendi": eklendi, "atlandi": atlandi}
    except Exception as e:
        return {"eklendi": 0, "atlandi": 0, "hata": f"{type(e).__name__}: {str(e)[:140]}"}


def iade_satis_net_ozet(baslangic=None, bitis=None):
    """SKU bazında Satış / İade / Net özeti. İade kârı paçal maliyetinden hesaplanır.
    Döner: (satirlar:list, toplam:dict)."""
    pacal = get_pacal_map()
    sat = {}
    for s in get_satislar(baslangic, bitis):
        sku = str(s.get("sku") or "").strip()
        if not sku:
            continue
        k = satir_kar(s)
        o = sat.setdefault(sku, {"urun_adi": s.get("urun_adi", "") or "",
                                 "s_adet": 0, "s_ciro": 0.0, "s_kar": 0.0})
        o["s_adet"] += k["adet"]; o["s_ciro"] += k["ciro"]; o["s_kar"] += k["net_kar"]
        if not o["urun_adi"]:
            o["urun_adi"] = s.get("urun_adi", "") or ""
    iad = {}
    for r in get_iadeler(baslangic, bitis):
        sku = str(r.get("sku") or "").strip()
        if not sku:
            continue
        adet = _i(r.get("iade_adet"))
        net = _f(r.get("iade_net"))
        pc = pacal.get(_normalize_sku_yerel(sku), 0.0)
        o = iad.setdefault(sku, {"urun_adi": r.get("urun_adi", "") or "",
                                 "i_adet": 0, "i_tutar": 0.0, "i_maliyet": 0.0})
        o["i_adet"] += adet; o["i_tutar"] += net; o["i_maliyet"] += adet * pc
        if not o["urun_adi"]:
            o["urun_adi"] = r.get("urun_adi", "") or ""
    satirlar = []
    for sku in (set(sat) | set(iad)):
        s = sat.get(sku, {}); i = iad.get(sku, {})
        s_adet = s.get("s_adet", 0); s_ciro = s.get("s_ciro", 0.0); s_kar = s.get("s_kar", 0.0)
        i_adet = i.get("i_adet", 0); i_tutar = i.get("i_tutar", 0.0)
        i_kar = i_tutar - i.get("i_maliyet", 0.0)
        satirlar.append({
            "sku": sku, "urun_adi": s.get("urun_adi") or i.get("urun_adi") or "",
            "s_adet": s_adet, "s_ciro": s_ciro, "s_kar": s_kar,
            "i_adet": i_adet, "i_tutar": i_tutar, "i_kar": i_kar,
            "net_adet": s_adet - i_adet, "net_ciro": s_ciro - i_tutar, "net_kar": s_kar - i_kar,
        })
    satirlar.sort(key=lambda x: -x["i_adet"])
    toplam = {kk: sum(x[kk] for x in satirlar) for kk in
              ("s_adet", "s_ciro", "s_kar", "i_adet", "i_tutar", "i_kar",
               "net_adet", "net_ciro", "net_kar")}
    return satirlar, toplam

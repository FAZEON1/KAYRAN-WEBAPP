# -*- coding: utf-8 -*-
"""Mikro → depoya giriş tarihleri: Happy Life raporu, stok yaşı, satılamayan stok (Ekim 2026, Mikro adım 4).

Kullanıcı: "Happy Life stok raporu — ürünler ithal edilip Happy depoya yerleştirildikten sonra otomatik stok
yaşına kadar tüm datalar Mikro'dan alınsın." Aktarıcının mikro_depo_hareket tablosu (Mikro STOK_HAREKETLERI,
2025'ten beri bir depoya giren ya da depodan çıkan her hareket) ve mikro_stok_miktar (ürün × depo miktarı)
okunur; uygulamaya hiçbir şey kopyalanmaz. Onaydan sonra kaynak değişir, hesap her açılışta Mikro'dan yapılır.

  Depo partileri    bir depoya giren her hareket bir partidir (ithalat, yurt içi alış, iade, sayım fazlası,
                    depolar arası sevk). Tarih: Mikro hareket tarihi. Elde kalan stok (mikro_stok_miktar) en yeni
                    partilerden oluşur (FIFO, kayranpm.stok_yasi.fifo_kalan). Happy Life sayfasındaki "giriş
                    tarihi" budur: Merkez'den Happy Life'a sevk edilen mal sevk gününden yaşlanır (kira).
  Satılabilir stok  (stok yaşı) Merkez + Happy Life tek havuzdur; havuz içindeki sevk yaşı sıfırlamaz. Parti =
                    havuza dışarıdan giriş: ithalat, yurt içi alış ve diğer girişler (iade ve sayım fazlası
                    SAYILMAZ, uygulamadaki kural: partiler alımlardır) + antrepodan havuza sevk. ASEL DEPO 2025'te
                    satılabilir depoydu (Nisan 2026'ya kadar satış çıkışı var): oraya giriş de parti, oradan
                    Merkez / Happy Life'a sevk yeni parti değildir.
  Değer farkı       (sth_cins 9) ve iptal edilmiş hareket sayılmaz.

Mikro'da OLMAYAN: palet etiketi ve palet sayısı (Happy Life'ın kendi deposundaki palet kaydı). Onlar için Happy
Life Excel'i isteğe bağlı yüklenebilir; stok, giriş tarihi ve yaş Mikro'dan gelir.
Durum sistem_ayarlari'nda (DURUM_ANAHTAR). Ekran: kayranpm/mikro_depo_ekran.py.
"""
from collections import defaultdict

DURUM_ANAHTAR = "mikro_depo_durum"
TABLO = "mikro_depo_hareket"
KOLONLAR = ("sth_guid,sth_tarih,sth_tip,sth_cins,sth_evraktip,sth_normal_iade,sth_evrakno_seri,sth_evrakno_sira,"
            "sth_stok_kod,sth_miktar,sth_giris_depo_no,sth_cikis_depo_no,sth_exim_kodu,sth_iptal")
HAPPY_LIFE = "HAPPY LIFE"
DEGER_FARKI = 9                      # sth_cins: tutar düzeltmesi, mal hareketi değil
GECMIS_SATILABILIR = {"ASEL DEPO"}   # 2025'te satılabilir depo; bugün stoğu yok
ON_DEPOLAR = {"ALY ANTREPO"}         # mal stoğa girmeden önce bekler: buradan havuza sevk = depoya giriş
HAVUZ_TURLERI = ("ithalat", "yurtici", "giris")
TUR_AD = {"ithalat": "İthalat", "yurtici": "Yurt içi", "giris": "Diğer giriş", "iade": "İade",
          "sayim": "Sayım fazlası", "sevk": "Depo sevki", "cikis": "Çıkış"}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _i(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _s(v):
    return str(v or "").strip()


def _iptal(v):
    return v is True or _s(v).lower() in ("1", "true")


# ── Saf ────────────────────────────────────────────────────────────
def hareket_turu(tip, cins, iade):
    """Mikro sth_tip / sth_cins / sth_normal_iade → uygulamadaki tür."""
    if tip == 2:
        return "sevk"
    if tip == 1:
        return "cikis"
    if cins == 12:
        return "ithalat"
    if iade == 1:
        return "iade"
    if cins == 10:
        return "sayim"
    if cins in (0, 1, 2):
        return "yurtici"
    return "giris"


def hareketler(satirlar, depo_adlari):
    """mikro_depo_hareket → [{tarih, sku, adet, tur, giris, cikis, belge}] (eski → yeni). giris / cikis: kanonik
    depo adı ya da "". İptal, değer farkı, sıfır miktar, aynı depoya sevk atlanır."""
    from kayranpm.database import depo_kanonik
    from shared.utils import sku_anahtar

    def depo(no):
        n = _i(no, 0)
        if n <= 0:
            return ""
        return depo_kanonik(_s(depo_adlari.get(n)) or f"DEPO {n}")
    out = []
    for r in satirlar or []:
        if _iptal(r.get("sth_iptal")) or _i(r.get("sth_cins"), -1) == DEGER_FARKI:
            continue
        tip, adet = _i(r.get("sth_tip"), -1), _f(r.get("sth_miktar"))
        sku, tarih = sku_anahtar(r.get("sth_stok_kod")), _s(r.get("sth_tarih"))[:10]
        if tip not in (0, 1, 2) or adet <= 0 or not sku or not tarih:
            continue
        giris = depo(r.get("sth_giris_depo_no")) if tip in (0, 2) else ""
        cikis = depo(r.get("sth_cikis_depo_no")) if tip in (1, 2) else ""
        if tip == 2 and (giris == cikis or not giris):
            continue
        seri, sira = _s(r.get("sth_evrakno_seri")), _s(r.get("sth_evrakno_sira"))
        out.append({"tarih": tarih, "sku": sku, "adet": adet,
                    "tur": hareket_turu(tip, _i(r.get("sth_cins"), -1), _i(r.get("sth_normal_iade"), 0)),
                    "giris": giris, "cikis": cikis,
                    "belge": _s(r.get("sth_exim_kodu")) or "-".join(x for x in (seri, sira) if x)})
    out.sort(key=lambda h: h["tarih"])
    return out


def _parti(h):
    return {"tarih": h["tarih"], "adet": h["adet"], "belge": h["belge"], "tur": h["tur"], "depo": h["giris"],
            "kaynak": h["cikis"]}


def depo_partileri(har):
    """{(depo, sku): [parti]} — bir depoya giren her hareket (sevk dahil). Happy Life, satılamayan stok."""
    out = defaultdict(list)
    for h in har or []:
        if h["giris"]:
            out[(h["giris"], h["sku"])].append(_parti(h))
    return dict(out)


def havuz_partileri(har, havuz):
    """{sku: [parti]} — satılabilir havuza (havuz + GECMIS_SATILABILIR) DIŞARIDAN giriş. Havuz içi sevk parti
    değildir (yaşı sıfırlamaz); antrepodan sevk partidir; iade ve sayım fazlası parti değildir."""
    hv = set(havuz) | GECMIS_SATILABILIR
    out = defaultdict(list)
    for h in har or []:
        if h["giris"] not in hv:
            continue
        if h["tur"] == "sevk":
            if h["cikis"] in hv or h["cikis"] not in ON_DEPOLAR:
                continue
        elif h["tur"] not in HAVUZ_TURLERI:
            continue
        out[h["sku"]].append(_parti(h))
    return dict(out)


def depo_yaslari(partiler, kirilim, bugun):
    """{(depo, sku): (özet, kalanlar)} — kirilim: {sku: {depo: miktar}} (mikro_stok.kirilim_yap). Stoğu olmayan
    depo-ürün yok. Özet ve kalanlar kayranpm.stok_yasi.urun_yasi ile aynı biçimde."""
    from kayranpm.stok_yasi import urun_yasi
    out = {}
    for sku, dd in (kirilim or {}).items():
        for depo, mik in (dd or {}).items():
            if _f(mik) > 0:
                out[(depo, sku)] = urun_yasi(mik, (partiler or {}).get((depo, sku), []), bugun)
    return out


def depo_ozet_satirlari(yaslar, depo, adlar=None):
    """Bir deponun ürün özeti: [{sku, ad, stok, parti, ort_gun, en_eski_gun, en_eski_tarih, en_yeni_gun,
    kayitsiz}] — en yaşlı üstte (giriş kaydı olmayan en altta)."""
    out = []
    for (d, sku), (oz, kal) in (yaslar or {}).items():
        if d != depo:
            continue
        out.append({"sku": sku, "ad": (adlar or {}).get(sku, ""), "stok": oz["stok"], "parti": len(kal),
                    "ort_gun": None if oz["ort_gun"] is None else round(oz["ort_gun"]),
                    "en_eski_gun": oz["en_eski_gun"], "en_eski_tarih": oz["en_eski_tarih"] or "",
                    "en_yeni_gun": oz["en_yeni_gun"], "kayitsiz": oz["kapsanmayan"]})
    out.sort(key=lambda r: (-(r["en_eski_gun"] if r["en_eski_gun"] is not None else -1), r["sku"]))
    return out


def depo_parti_satirlari(yaslar, depo, bugun, adlar=None):
    """Elde kalan her parti bir satır (Happy Life Excel'indeki palet satırının Mikro karşılığı): [{sku, ad,
    giris_tarihi, yas, kalan, tur, belge, kaynak}] — en yaşlı üstte."""
    from kayranpm.stok_yasi import _gun
    out = []
    for (d, sku), (_oz, kal) in (yaslar or {}).items():
        if d != depo:
            continue
        for p in kal:
            out.append({"sku": sku, "ad": (adlar or {}).get(sku, ""), "giris_tarihi": p["tarih"],
                        "yas": _gun(p["tarih"], bugun), "kalan": p["kalan"], "tur": TUR_AD.get(p.get("tur"), ""),
                        "belge": p.get("belge") or "", "kaynak": p.get("kaynak") or ""})
    out.sort(key=lambda r: (-(r["yas"] or 0), r["sku"]))
    return out


def toplam(satirlar):
    """Depo özeti satırlarının toplamı: {cesit, stok, kayitsiz, ort_gun, en_eski_gun}."""
    stok = sum(r["stok"] for r in satirlar or [])
    kays = sum(r["kayitsiz"] for r in satirlar or [])
    kapsanan = stok - kays
    agirlik = sum((r["ort_gun"] or 0) * (r["stok"] - r["kayitsiz"]) for r in satirlar or [] if r["ort_gun"] is not None)
    eski = [r["en_eski_gun"] for r in satirlar or [] if r["en_eski_gun"] is not None]
    return {"cesit": len(satirlar or []), "stok": stok, "kayitsiz": kays,
            "ort_gun": round(agirlik / kapsanan) if kapsanan > 0 else None, "en_eski_gun": max(eski) if eski else None}


def excel_karsilastir(excel, mikro_satirlari, bugun):
    """Son Happy Life Excel'i ↔ Mikro, SKU bazında: [{sku, ad, excel_adet, mikro_adet, excel_en_eski,
    mikro_en_eski, excel_yas, mikro_yas}]. excel: happylife_stok satırları (sku, sku_tanim, giris_tarihi,
    miktar2)."""
    from kayranpm.stok_yasi import _gun
    from shared.utils import sku_anahtar
    ex = {}
    for k in excel or []:
        s = sku_anahtar(k.get("sku"))
        if not s:
            continue
        e = ex.setdefault(s, {"ad": _s(k.get("sku_tanim")), "adet": 0.0, "eski": ""})
        e["adet"] += _f(k.get("miktar2"))
        g = _s(k.get("giris_tarihi"))[:10]
        if g and (not e["eski"] or g < e["eski"]):
            e["eski"] = g
    mk = {r["sku"]: r for r in mikro_satirlari or []}
    out = []
    for s in sorted(set(ex) | set(mk)):
        e, m = ex.get(s, {}), mk.get(s, {})
        out.append({"sku": s, "ad": m.get("ad") or e.get("ad") or "", "excel_adet": e.get("adet", 0.0),
                    "mikro_adet": m.get("stok", 0.0), "excel_en_eski": e.get("eski") or "",
                    "mikro_en_eski": m.get("en_eski_tarih") or "",
                    "excel_yas": _gun(e["eski"], bugun) if e.get("eski") else None,
                    "mikro_yas": m.get("en_eski_gun")})
    return out


def yas_karsilastir(stoklar, eski, yeni, bugun):
    """Stok yaşı (satılabilir stok) şimdiki partilerle ↔ Mikro partileriyle. stoklar: {sku: adet};
    eski / yeni: {sku: [parti]}. Döner {once, sonra (stok_yasi.toplam_ozet), urunler: değişenler}."""
    from kayranpm.stok_yasi import toplam_ozet, urun_yasi
    once, sonra, urunler = [], [], []
    for sku in sorted(stoklar or {}):
        a, _ = urun_yasi(stoklar[sku], (eski or {}).get(sku, []), bugun)
        b, _ = urun_yasi(stoklar[sku], (yeni or {}).get(sku, []), bugun)
        once.append(a)
        sonra.append(b)
        ra = None if a["ort_gun"] is None else round(a["ort_gun"])
        rb = None if b["ort_gun"] is None else round(b["ort_gun"])
        if ra != rb or a["kapsanmayan"] != b["kapsanmayan"]:
            urunler.append({"sku": sku, "stok": a["stok"], "ort_once": ra, "ort_sonra": rb,
                            "kayitsiz_once": a["kapsanmayan"], "kayitsiz_sonra": b["kapsanmayan"],
                            "en_eski_once": a["en_eski_gun"], "en_eski_sonra": b["en_eski_gun"]})
    urunler.sort(key=lambda r: (-abs((r["ort_sonra"] or 0) - (r["ort_once"] or 0)), r["sku"]))
    return {"once": toplam_ozet(once), "sonra": toplam_ozet(sonra), "urunler": urunler}


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranpm.database import get_client
    return get_client()


def veri_oku():
    """(hareket satırları, {dep_no: dep_adi}, mikro_stok_miktar satırları). Tablo yoksa / boşsa boş liste."""
    # Sıralı okuma + kopya denetimi (satis.mikro_esitle, 21.10.2026 olayı): sırasız sayfalar satır kaçırıp
    # kopyalayabiliyordu. Tutarsız okumada hareketler boş döner → sayfalar bugünkü kaynaklara düşer.
    from satis.mikro_esitle import kopyasiz
    cli = _cli()
    try:
        har = kopyasiz(cli.table(TABLO).select(KOLONLAR).order("sth_guid").execute().data or [], "sth_guid")
    except Exception:  # noqa: BLE001 — göç (43) uygulanmadıysa tablo yok / okuma tutarsız
        har = []
    depo = {_i(d.get("dep_no")): _s(d.get("dep_adi")) for d in
            (cli.table("mikro_depo_kart").select("dep_no,dep_adi").execute().data or [])}
    try:
        stok = kopyasiz(cli.table("mikro_stok_miktar").select("sto_kod,sto_isim,depo,miktar").order("sto_kod")
                        .order("depo").execute().data or [], ("sto_kod", "depo"))
    except Exception:  # noqa: BLE001
        har, stok = [], []
    return har, depo, stok


def hesapla(bugun=None):
    """Tek okuma: {"bos", "hareket_sayisi", "depo": {(depo, sku): (özet, kalanlar)}, "havuz": {sku: [parti]},
    "depo_partileri", "kirilim", "adlar", "bugun"}."""
    from kayranpm.mikro_stok import kirilim_yap
    from kayranpm.stok_yasi import _bugun
    from kayranpm.database import _SATILABILIR_DEPOLAR
    bugun = bugun or _bugun()
    satir, depo, stok = veri_oku()
    har = hareketler(satir, depo)
    kir, adlar = kirilim_yap(stok, depo)
    dp = depo_partileri(har)
    return {"bos": not har, "hareket_sayisi": len(har), "depo": depo_yaslari(dp, kir, bugun),
            "havuz": havuz_partileri(har, _SATILABILIR_DEPOLAR), "depo_partileri": dp, "kirilim": kir,
            "adlar": adlar, "bugun": bugun}


try:                                      # 5 dk önbellek (stok yaşı ile aynı)
    import streamlit as _st
    hesapla = _st.cache_data(ttl=300, show_spinner=False)(hesapla)
except Exception:  # noqa: BLE001
    pass


def havuz_partileri_oku():
    """Stok yaşı için: {sku: [parti]} ya da Mikro verisi yoksa None."""
    v = hesapla()
    return None if v["bos"] else v["havuz"]


def depo_partileri_oku():
    """Satılamayan stok için: {(depo, sku): [parti]} ya da Mikro verisi yoksa None."""
    v = hesapla()
    return None if v["bos"] else v["depo_partileri"]


def plan_hazirla():
    """Onay ekranı: Happy Life (son Excel ↔ Mikro), stok yaşı (şimdi ↔ Mikro) ve satılamayan stok (depo bazında
    şimdi ↔ Mikro). Hiçbir şey yazmaz."""
    from kayranpm import stok_yasi as Y
    v = hesapla()
    bugun = v["bugun"]
    hl = depo_ozet_satirlari(v["depo"], HAPPY_LIFE, v["adlar"])
    excel, rapor = [], ""
    try:
        r = (_cli().table("happylife_stok").select("rapor_tarihi").order("rapor_tarihi", desc=True).limit(1)
             .execute().data or [])
        if r:
            rapor = _s(r[0].get("rapor_tarihi"))[:10]
            excel = (_cli().table("happylife_stok").select("sku,sku_tanim,giris_tarihi,miktar2")
                     .eq("rapor_tarihi", rapor).execute().data or [])
    except Exception:  # noqa: BLE001
        excel = []
    stoklar, _kartlar, _haric = Y.bizim_stoklari()
    yas = yas_karsilastir(stoklar, Y._alim_partileri_oku(), v["havuz"], bugun)
    try:
        from depo.satilamayan import hesapla as sat_hesapla
        sat = {"once": sat_hesapla(bugun, mikro=False)[1], "sonra": sat_hesapla(bugun, mikro=True)[1]}
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_depo.plan_hazirla", e)
        sat = {"once": [], "sonra": []}
    return {"bos": v["bos"], "hareket_sayisi": v["hareket_sayisi"], "bugun": bugun, "hl": hl, "hl_toplam": toplam(hl),
            "excel_rapor": rapor, "excel": excel_karsilastir(excel, hl, bugun), "yas": yas, "satilamayan": sat}


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    return bool(durum().get("acik"))


def ac(kullanici, ozet=None):
    from kayranacc.database import set_ayar
    from shared.utils import tr_now
    d = durum()
    d.update(acik=True, acan=str(kullanici or ""), acilis=str(tr_now()))
    if ozet:
        d["onay_ozeti"] = ozet
    set_ayar(DURUM_ANAHTAR, d)


def uygula(plan, kullanici=""):
    """Kaynağı Mikro'ya çevirir (yazılan tek şey sistem_ayarlari'ndaki durum; veri kopyalanmaz). Mikro verisi
    boşsa açmaz. Onay anındaki karşılaştırmanın özeti durumda kalır. Döner: açıldı mı."""
    if not plan or plan.get("bos"):
        return False
    y = plan["yas"]
    ac(kullanici, {"hareket": plan["hareket_sayisi"], "hl_stok": plan["hl_toplam"]["stok"],
                   "yas_ort_once": y["once"]["ort_gun"], "yas_ort_sonra": y["sonra"]["ort_gun"],
                   "kayitsiz_once": y["once"]["kapsanmayan"], "kayitsiz_sonra": y["sonra"]["kapsanmayan"]})
    if hasattr(hesapla, "clear"):
        hesapla.clear()
    try:
        from kayranpm.stok_yasi import hesapla as yh
        if hasattr(yh, "clear"):
            yh.clear()
    except Exception:  # noqa: BLE001
        pass
    return True


def son_aktarim():
    """Aktarıcının bu tabloyu son başarıyla çektiği an ("" : hiç çekmedi — göç uygulanmadı ya da yeni sürüm
    henüz çalışmadı)."""
    try:
        r = (_cli().table("mikro_senk_durum").select("son_cekim").eq("tablo", TABLO).execute().data or [])
    except Exception:  # noqa: BLE001
        return ""
    return str((r[0] if r else {}).get("son_cekim") or "")

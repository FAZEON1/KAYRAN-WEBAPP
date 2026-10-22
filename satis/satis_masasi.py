# -*- coding: utf-8 -*-
"""Satış — LİSTE MASALARI (Ekim 2026, tüm program yeni tasarım — ortak masa shared/masa.py).

  siparis_masa_verisi()  Satış › Satışlar (Sipariş görünümü) ve Satış girişi › son siparişler
  kalem_masa_verisi()    Satış › Satışlar (Kalem görünümü)
  iade_masa_verisi()     Satış › İade › İade kayıtları
  siparis_yurutucu()     satıra tıklanınca BUGÜNKÜ sipariş penceresi (satislar_ekran.siparis_dialog)
  iade_yurutucu()        iade kaydı silme: BUGÜNKÜ satis.database.sil_iade (stok geri düşer)

Bu modül yalnız masanın tanımını hazırlar ve isteği bugünkü fonksiyonlara iletir; sipariş düzeltme,
kalem silme, stok farkı ve iade silme kuralları DEĞİŞMEDİ (satis/database.py).
Rakamlar eski ekranla aynı: özet bandı satislar_ekran'daki kartların aynısı (kuruşsuz kısa), satırda tam tutar.
Kâr / marj yalnız kar_ok (shared.kar_gizle.kar_gorunur) iken tanıma girer — gizliyken tarayıcıya hiç gitmez.

Geri almak için: satis/satislar_ekran.py → SATISLAR_MASASI_YENI = False,
satis/main.py → IADE_MASASI_YENI = False (eski ekranlar aynen duruyor).
"""
from . import satis_hesap as H


# ── Biçim ───────────────────────────────────────────────────────────
def usd_kisa(v):
    """Özet kartı: eski ekranın kısa biçimi ('$1,17M', '$12.345') — satislar_ekran._usd ile aynı."""
    from shared.tasarim import sayi
    return "—" if v is None else sayi(v, "$")


def usd_tam(v):
    """Satır tutarı tam: '$1.234,56' (eksi: '-$1.234,56') — satislar_ekran._usd_tam ile aynı."""
    f = float(v or 0)
    s = f"{abs(f):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return ("-" if f < 0 else "") + "$" + s


def usd_birim(v):
    """Birim fiyat: en çok 4 ondalık, en az 2 ('$7,2938', '$12,50')."""
    from shared.tasarim import tr_sayi
    f = float(v or 0)
    tam, ond = tr_sayi(abs(f), 4).split(",")
    ond = ond.rstrip("0")
    ond = (ond + "00")[:2] if len(ond) < 2 else ond
    return ("-" if f < 0 else "") + "$" + tam + "," + ond


def _yuzde(v):
    from shared.tasarim import tr_sayi
    return "" if v is None else f"%{tr_sayi(v, 1)}"


MARJ_SINIR = 999.9


def marj_metni(marj, net_satis):
    """Satırın marj alt yazısı. Bedelsiz çıkış (net satış < 1 sent): "bedelsiz" (yüzde anlamsız; eskiden
    "%-26.069.604,0" görünüyordu, kullanıcı 22.10.2026). Çok küçük satışta ±%999,9'u aşan marj sınırda kesilir:
    "%-999,9'dan düşük"."""
    from .satis_hesap import MARJ_ESIK
    if float(net_satis or 0) < MARJ_ESIK:
        return "bedelsiz" if abs(float(net_satis or 0)) < MARJ_ESIK else ""
    if marj is None:
        return ""
    if marj < -MARJ_SINIR:
        return "%-999,9'dan düşük"
    if marj > MARJ_SINIR:
        return "%999,9'dan yüksek"
    return _yuzde(marj)


def _firma(kanal):
    from shared.utils import firma_kisa_ad
    return firma_kisa_ad(kanal)


def siparis_anahtari(o):
    """Sipariş penceresinin anahtarı: sipariş no ya da '#kalem-<id>' (eski siparis_listesi ile aynı)."""
    return o["siparis_no"] or f"#kalem-{o['kalemler'][0].get('id')}"


# ── Sipariş masası ──────────────────────────────────────────────────
def siparis_ozeti(siparisler, kar_ok):
    """Satışlar özet bandı — eski kpi_serit kartlarının aynısı (aynı değer metni, aynı renk)."""
    from shared.tasarim import tr_sayi
    t = H.toplam(siparisler)
    oz = [{"k": "siparis", "et": "Sipariş", "dg": tr_sayi(t["siparis"]), "renk": "mor",
           "al": f"{tr_sayi(sum(o['kalem'] for o in siparisler))} kalem"},
          {"k": "adet", "et": "Adet", "dg": tr_sayi(t["adet"]), "renk": "cyan"},
          {"k": "ciro", "et": "Ciro", "dg": usd_kisa(t["ciro"]), "renk": "cyan", "ipucu": usd_tam(t["ciro"]),
           "al": f"destek {usd_kisa(t['destek'])}" if t["destek"] > 0.005 else ""}]
    if kar_ok:
        oz.append({"k": "kar", "et": "Net kâr", "dg": usd_kisa(t["net_kar"]),
                   "renk": "yesil" if t["net_kar"] >= 0 else "kirmizi", "ipucu": usd_tam(t["net_kar"]),
                   "al": (f"net marj %{tr_sayi(t['marj'], 1)} · maliyet {usd_kisa(t['maliyet'])}"
                          if t["marj"] is not None else "")})
    return oz


def siparis_satirlari(siparisler, kar_ok, bugun=None):
    from shared.tasarim import tr_sayi
    out = []
    for o in siparisler:
        urunler = ", ".join(dict.fromkeys(str(k.get("sku") or "") for k in o["kalemler"]))
        r = {"id": siparis_anahtari(o), "sno": o["siparis_no"] or "Sipariş no yok",
             "sno_alt": f"{o['kalem']} kalem · {tr_sayi(o['adet'])} adet",
             "kanal": o["kanal"], "firma": _firma(o["kanal"]) or "—",
             "urunler": urunler[:90] + ("…" if len(urunler) > 90 else ""),
             "tarih": o["tarih"], "gun": H.gun_adi(o["tarih"], bugun),
             "ciro": round(float(o["ciro"]), 2), "ciro_m": usd_tam(o["ciro"]), "ciro_m__s": float(o["ciro"]),
             "adet": int(o["adet"]), "maliyetsiz": int(o["maliyetsiz"])}
        if kar_ok:
            r.update({"kar_m": usd_tam(o["net_kar"]), "kar_m__s": float(o["net_kar"]), "marj_m": marj_metni(o["marj"], o["ciro"] - o["destek"]),
                      "kar_renk": "yesil" if o["net_kar"] >= 0 else "kirmizi"})
            if o["maliyetsiz"]:
                r["_durum"] = {"ad": f"{o['maliyetsiz']} maliyetsiz", "renk": "amber"}
        out.append(r)
    return out


def siparis_masa_verisi(siparisler, kar_ok, ozet=True, firma_goster=True, bugun=None):
    """Sipariş listesi: güne göre gruplu (grup başlığında sipariş sayısı ve ciro), en yeni üstte.
    Satıra tıklayınca bugünkü sipariş penceresi açılır (tik = "ac"). Arama, firma süzgeci ve dönem
    sayfanın araç çubuğunda kalır (özet ve Excel/CSV aynı süzgeçten hesaplanır)."""
    sut = [{"alan": "sno", "ad": "Sipariş", "tip": "metin", "alt": "sno_alt", "gen": "170px", "dar": "alt"}]
    if firma_goster:
        sut.append({"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "urunler"})
    else:
        sut.append({"alan": "urunler", "ad": "Ürünler", "tip": "ana"})
    sut.append({"alan": "ciro_m", "ad": "Ciro", "sag": True, "gen": "124px", "dar": "sag"})
    if kar_ok:
        sut.append({"alan": "kar_m", "ad": "Net kâr", "sag": True, "alt": "marj_m", "alt_renk": "kar_renk",
                    "gen": "124px", "genis": True})
        sut.append({"alan": "maliyetsiz", "ad": "Uyarı", "tip": "durum", "gen": "120px"})
    return {
        "ozet": siparis_ozeti(siparisler, kar_ok) if ozet else [],
        "sutunlar": sut,
        "grup": {"alan": "gun", "birim": "sipariş", "toplamlar": [{"alan": "ciro", "on": "$"}]},
        "satirlar": siparis_satirlari(siparisler, kar_ok, bugun),
        "islemler": [{"k": "ac", "ad": "Ayrıntı", "okuma": True}],
        "tik": "ac",
        "bos": {"liste": "Bu dönemde satış yok.", "suzgec": "Aramaya uyan sipariş yok."},
        "baslik_ipucu": "Siparişler",
    }


# ── Kalem masası ────────────────────────────────────────────────────
def kalem_masa_verisi(kalemler, katmap, kar_ok, satir_kar):
    """Kalem görünümü (eski st.dataframe "sat_kalem_tablo" yerine): her satış satırı, aynı sayılar
    (birim fiyat 4 ondalığa kadar, ciro/kâr 2 ondalık). Satıra tıklayınca kalemin siparişi açılır."""
    from shared.ana_veri import kategori_ad, urun_ad
    from shared.tasarim import tr_sayi
    from shared.utils import sku_anahtar
    satirlar = []
    for s in kalemler:
        k = satir_kar(s)
        sno = str(s.get("siparis_no") or "").strip()
        tarih = str(s.get("tarih") or "")[:10]
        r = {"id": s.get("id"), "sip": sno or f"#kalem-{s.get('id')}",
             "tarih_m": (f"{tarih[8:10]}.{tarih[5:7]}.{tarih[:4]}" if len(tarih) == 10 else tarih or "—"),
             "tarih_m__s": tarih, "sno": sno or "—", "kanal": str(s.get("kanal") or "").strip(),
             "firma": _firma(s.get("kanal")) or "—", "sku": str(s.get("sku") or ""),
             "urun": urun_ad(s.get("sku"), s.get("urun_adi")),
             "kategori": kategori_ad(katmap.get(sku_anahtar(s.get("sku")), "")) or "—",
             "adet_m": tr_sayi(int(k["adet"] or 0)), "adet_m__s": int(k["adet"] or 0),
             "bsat_m": usd_birim(s.get("birim_satis")), "bsat_m__s": float(s.get("birim_satis") or 0),
             "ciro_m": usd_tam(k["ciro"]), "ciro_m__s": round(float(k["ciro"]), 2)}
        r["urun_alt"] = " · ".join(x for x in (r["sku"], r["kategori"] if r["kategori"] != "—" else "") if x)
        if kar_ok:
            r.update({"bmal_m": f"maliyet {usd_birim(s.get('birim_maliyet'))}",
                      "kar_m": usd_tam(k["net_kar"]), "kar_m__s": round(float(k["net_kar"]), 2),
                      "marj_m": marj_metni(round(k["marj"], 1), k["net_satis"]), "kar_renk": "yesil" if k["net_kar"] >= 0 else "kirmizi"})
        satirlar.append(r)
    sut = [{"alan": "tarih_m", "ad": "Tarih", "tip": "metin", "alt": "sno", "gen": "132px", "dar": "alt"},
           {"alan": "urun", "ad": "Ürün", "tip": "ana", "alt": "urun_alt"},
           {"alan": "firma", "ad": "Firma", "gen": "170px", "genis": True},
           {"alan": "adet_m", "ad": "Adet", "sag": True, "gen": "64px"},
           {"alan": "bsat_m", "ad": "Birim satış", "sag": True, "gen": "118px", "genis": True}
           | ({"alt": "bmal_m"} if kar_ok else {}),
           {"alan": "ciro_m", "ad": "Ciro", "sag": True, "gen": "118px", "dar": "sag"}]
    if kar_ok:
        sut.append({"alan": "kar_m", "ad": "Net kâr", "sag": True, "alt": "marj_m", "alt_renk": "kar_renk",
                    "gen": "118px"})
    return {"sutunlar": sut, "satirlar": satirlar,
            "islemler": [{"k": "ac", "ad": "Siparişi aç", "okuma": True}], "tik": "ac",
            "bos": {"liste": "Bu dönemde satış yok."}, "baslik_ipucu": "Satış kalemleri"}


def siparis_yurutucu():
    """Satıra tıklanınca bugünkü sipariş penceresini ister (eski satislar_ekran._ac ile aynı:
    B.detay_ac("sip", anahtar)); sayfa masadan sonra siparis_detay_kontrol() ile pencereyi açar."""
    def yurut(temiz):
        from shared import bilesen as B
        anahtar = (temiz["satirlar"][0] or {}).get("sip") or temiz["ids"][0]
        B.detay_ac("sip", anahtar)
        return {"ok": True, "mesaj": "", "yenileme": False, "sessiz": True}
    return yurut


# ── İade kayıtları masası ───────────────────────────────────────────
def iade_masa_verisi(kayitlar, salt=False, bugun=None, esitleme=None):
    """İade kayıtları: aya göre gruplu (grup başlığında iade sayısı ve net tutar), en yeni üstte.
    Satıra tıklayınca sağda ayrıntı; silme onay kutusuyla (eski _iade_detay_dialog ile aynı kural).
    esitleme: satis.database.mikro_esitleme() (açık, başlangıç) — açıkken Mikro'dan gelen iadede "İadeyi sil" yok
    (sil_iade zaten reddediyordu; düğme görünüp "Silinemedi" diyordu, 22.10.2026)."""
    _acik, _bas = esitleme or (False, "")
    from shared.tasarim import tr_sayi
    from shared.utils import gun_ay_yil
    satirlar = []
    for r in sorted(kayitlar or [], key=lambda r: (str(r.get("tarih") or ""), r.get("id") or 0), reverse=True):
        ay = str(r.get("tarih") or "")[:7]
        try:
            ay_ad = f"{H.AY[int(ay[5:7])]} {ay[:4]}"
        except (ValueError, IndexError):
            ay_ad = "Tarihsiz"
        net = float(r.get("iade_net") or 0)
        adet = int(r.get("iade_adet") or 0)
        firma = _firma(r.get("kanal")) or "cari belirsiz"
        sku, ad = str(r.get("sku") or ""), str(r.get("urun_adi") or "")
        satirlar.append({
            "id": r.get("id"), "ay": ay_ad, "tarih_m": H.gun_adi(r.get("tarih"), bugun),
            "mikro": bool(_acik and str(r.get("kaynak") or "") == "mikro" and str(r.get("tarih") or "")[:10] >= _bas),
            "tarih_m__s": str(r.get("tarih") or ""), "sku": sku, "urun_adi": ad,
            "urun": f"{sku} · {ad[:48]}" if ad else sku,
            "kanal": str(r.get("kanal") or "").strip(), "firma": firma,
            "alt": " · ".join(x for x in (firma, str(r.get("depo") or ""), str(r.get("kaynak") or "")) if x),
            "depo": str(r.get("depo") or ""), "kaynak": str(r.get("kaynak") or ""),
            "net": net, "net_m": usd_tam(net), "net_m__s": net, "adet_m": tr_sayi(adet), "adet_m__s": adet,
            "_baslik": sku or "İade", "_alt": ad, "_buyuk": usd_tam(net), "_buyuk_alt": f"{tr_sayi(adet)} adet",
            "_detay": [["Tarih", gun_ay_yil(r.get("tarih"))], ["Firma / cari", _firma(r.get("kanal")) or "—"],
                       ["Adet", tr_sayi(adet)], ["İade net", usd_tam(net)],
                       ["Giren depo", r.get("depo") or "—"], ["Kaynak", r.get("kaynak") or "—"]],
        })
    secenek = lambda alan, ad_fn=None: [{"k": v, "ad": (ad_fn(v) if ad_fn else v) or v}   # noqa: E731
                                        for v in sorted({s[alan] for s in satirlar if s[alan]})]
    return {
        "secimler": [{"alan": "kanal", "ad": "Tüm firmalar", "secenekler": secenek("kanal", _firma)},
                     {"alan": "depo", "ad": "Tüm depolar", "secenekler": secenek("depo")},
                     {"alan": "kaynak", "ad": "Tüm kaynaklar", "secenekler": secenek("kaynak")}],
        "ara": {"alanlar": ["sku", "urun_adi", "kanal", "firma", "depo", "net_m"], "ipucu": "SKU, ürün, firma ya da tutar"},
        "sutunlar": [{"alan": "tarih_m", "ad": "Tarih", "gen": "150px", "dar": "alt"},
                     {"alan": "urun", "ad": "Ürün", "tip": "ana", "alt": "alt"},
                     {"alan": "adet_m", "ad": "Adet", "sag": True, "gen": "72px", "genis": True},
                     {"alan": "net_m", "ad": "İade net", "sag": True, "gen": "124px", "dar": "sag"}],
        "grup": {"alan": "ay", "birim": "iade", "toplamlar": [{"alan": "net", "on": "$"}]},
        "satirlar": satirlar,
        "islemler": [{"k": "sil", "ad": "Sil", "dugme": "İadeyi sil", "tehlike": True, "f": [["mikro", "ne", True]],
                      "ipucu": "Kayıt silinir; iade edilen adet stoktan geri düşülür.",
                      "alanlar": [{"ad": "onay", "et": "Evet, bu iade kaydını sil", "tip": "onay", "zorunlu": True}]}],
        "bos": {"liste": "Bu dönemde iade kaydı yok.", "suzgec": "Bu süzgece uyan iade kaydı yok."},
        "baslik_ipucu": "İade kayıtları",
        "salt": bool(salt),
    }


def iade_yurutucu():
    """Silme: bugünkü sil_iade(int(id)) — iade edilen adet girdiği depodan geri düşülür."""
    def yurut(temiz):
        from .database import sil_iade
        if temiz["islem"] != "sil":
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        if sil_iade(int(temiz["ids"][0])):
            return {"ok": True, "mesaj": "İade kaydı silindi"}
        return {"ok": False, "mesaj": "Silinemedi; ayrıntı Sistem Kayıtları'nda."}
    return yurut

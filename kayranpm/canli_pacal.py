# -*- coding: utf-8 -*-
"""Canlı paçal maliyet (Ekim 2026, kullanıcı kararı A).

Paçal maliyet (satis.get_pacal_map) bir ürünün ŞİMDİYE KADAR alınan bütün partilerinin adet-ağırlıklı
ortalamasıdır; satılıp biten eski partiler de içindedir. Canlı paçal yalnız ELDEKİ malın maliyetidir:

  eldeki adet = bizim satılabilir stok (urunler.bizim_stok) + müşterilerin son raporlarındaki stok
  bu adetler EN YENİ teslim alınmış partiden geriye doğru dağıtılır (satılan mal eski partiden çıkmış
  sayılır — stok yaşı ekranıyla aynı kural); canlı paçal = Σ(kalan × parti final) / Σ kalan.

Yalnız teslim alınmış partiler girer (yoldaki / antrepodaki girmez; "Teslim Alındı" olunca kendiliğinden
girer). Bedelsiz (FOB 0) adetler bugünkü paçalda olduğu gibi ortalamayı düşürür.
  • stok 0 → son teslim alınan partinin birim maliyeti (durum "stok_yok")
  • stok, giriş kayıtlarından fazla → kayıtsız adetler bugünkü paçalla değerlenir
  • hiç parti yok (yurt içi alış fiyatı) → bugünkü paçal (durum "parti_yok")

YALNIZ GÖSTERİMDİR: satışa yazılan maliyet, kâr ve P&L bugünkü paçalla hesaplanmaya devam eder.
"""
import streamlit as st


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _sira(p):
    return (str(p.get("giris") or ""), str(p.get("dosya_id") or ""))


def hesapla(partiler, stok, yedek=0.0):
    """Tek ürünün canlı paçalı.

    partiler: [{"giris": 'YYYY-MM-DD', "adet", "final", "belge", "dosya_id"}] (teslim alınmış);
    stok: eldeki toplam adet (bizim + müşteri); yedek: bugünkü paçal.
    Döner: {"pacal", "stok", "kalanlar": [{giris, belge, kalan, final}] (en yeni önce),
            "kayitsiz": giriş kaydı olmayan adet, "durum": "tamam" | "stok_yok" | "parti_yok"}."""
    stok = max(0.0, _f(stok))
    yedek = _f(yedek)
    lotlar = sorted((p for p in partiler or [] if _f(p.get("adet")) > 0), key=_sira, reverse=True)
    if not lotlar:
        return {"pacal": round(yedek, 4), "stok": stok, "kalanlar": [], "kayitsiz": stok, "durum": "parti_yok"}
    if stok <= 0:
        en_yeni = _sira(lotlar[0])[0]
        son = [p for p in lotlar if _sira(p)[0] == en_yeni]
        adet = sum(_f(p["adet"]) for p in son)
        pacal = sum(_f(p["adet"]) * _f(p.get("final")) for p in son) / adet
        return {"pacal": round(pacal, 4), "stok": 0.0, "kalanlar": [], "kayitsiz": 0.0, "durum": "stok_yok"}
    kalan_stok, kalanlar, toplam = stok, [], 0.0
    for p in lotlar:
        if kalan_stok <= 0:
            break
        al = min(kalan_stok, _f(p["adet"]))
        kalanlar.append({"giris": str(p.get("giris") or ""), "belge": str(p.get("belge") or ""),
                         "kalan": al, "final": round(_f(p.get("final")), 4)})
        toplam += al * _f(p.get("final"))
        kalan_stok -= al
    kayitsiz = max(0.0, kalan_stok)
    toplam += kayitsiz * yedek
    return {"pacal": round(toplam / stok, 4), "stok": stok, "kalanlar": kalanlar,
            "kayitsiz": kayitsiz, "durum": "tamam"}


def eldeki_stoklar(urun_satirlari, kanal):
    """{sku_anahtar: (bizim, müşteri)} — bizim: urunler.bizim_stok (aynı anahtarlı kartlar toplanır),
    müşteri: kanal_stoklari çıktısındaki ({firma: {sku_anahtar: adet}}) bütün firmaların toplamı."""
    from shared.utils import sku_anahtar
    out = {}
    for u in urun_satirlari or []:
        k = sku_anahtar(u.get("sku"))
        if k:
            b, m = out.get(k, (0.0, 0.0))
            out[k] = (b + max(0.0, _f(u.get("bizim_stok"))), m)
    for skular in (kanal or {}).values():
        for k, adet in (skular or {}).items():
            if k and _f(adet) > 0:
                b, m = out.get(k, (0.0, 0.0))
                out[k] = (b, m + _f(adet))
    return out


def teslim_partileri(parti_satirlari):
    """get_parti_satirlari → {sku_anahtar: [parti]} — yalnız teslim alınmış (yoldaki/antrepodaki hariç)."""
    from shared.utils import sku_anahtar
    out = {}
    for p in parti_satirlari or []:
        if p.get("yolda"):
            continue
        k = sku_anahtar(p.get("sku"))
        if k and _f(p.get("adet")) > 0:
            out.setdefault(k, []).append({
                "giris": str(p.get("giris") or p.get("tarih") or "")[:10], "adet": _f(p.get("adet")),
                "final": _f(p.get("final")), "belge": p.get("belge") or "", "dosya_id": p.get("dosya_id")})
    return out


def harita_hesapla(parti_satirlari, urun_satirlari, kanal, pacal_map):
    """Saf: {sku_anahtar: hesapla(...) + {"bizim", "musteri"}} — partisi, stoğu ya da paçalı olan her ürün."""
    partiler = teslim_partileri(parti_satirlari)
    stoklar = eldeki_stoklar(urun_satirlari, kanal)
    out = {}
    for k in set(partiler) | set(stoklar) | set(pacal_map or {}):
        b, m = stoklar.get(k, (0.0, 0.0))
        r = hesapla(partiler.get(k, []), b + m, (pacal_map or {}).get(k, 0.0))
        r.update({"bizim": b, "musteri": m})
        out[k] = r
    return out


@st.cache_data(ttl=3600, show_spinner=False)   # tazelik: shared.veri_surumu (ürün grubu)
def harita():
    """{sku_anahtar: canlı paçal sonucu} — bütün ürünler, tek okuma. Okunamazsa {}."""
    try:
        from ithalat.database import get_parti_satirlari
        from satis.database import get_pacal_map
        from kayranpm.database import _hepsi, kanal_kod_haritasi
        from kayranpm.stok_hesap import kanal_stoklari
        kanal = kanal_stoklari(_hepsi("firma_stok", "firma, sku, stok_miktari, yukleme_tarihi") or [],
                               harita=kanal_kod_haritasi())
        return harita_hesapla(get_parti_satirlari() or [], _hepsi("urunler", "sku, bizim_stok") or [],
                              kanal, get_pacal_map() or {})
    except Exception:  # noqa: BLE001
        return {}


def bul(sku):
    """Tek ürünün canlı paçal sonucu (harita'dan, sku_anahtar ile); yoksa None."""
    from shared.utils import sku_anahtar
    return (harita() or {}).get(sku_anahtar(sku))


def aciklama(r):
    """Kartın alt satırı: 'eldeki 9.397 adet (bizim 9.000 + müşteri 397)' vb."""
    from shared.tasarim import tr_sayi
    if not r:
        return ""
    if r["durum"] == "stok_yok":
        return "stok yok · son teslim alınan parti"
    if r["durum"] == "parti_yok":
        return "giriş partisi yok · paçal"
    m = f" + müşteri {tr_sayi(r.get('musteri', 0))}" if r.get("musteri") else ""
    k = f" · {tr_sayi(r['kayitsiz'])} adet kayıtsız" if r.get("kayitsiz") else ""
    return f"eldeki {tr_sayi(r['stok'])} adet (bizim {tr_sayi(r.get('bizim', 0))}{m}){k}"

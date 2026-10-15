# -*- coding: utf-8 -*-
"""Depo › Satılamayan stok (Ekim 2026) — satılabilir stoğa girmeyen depolardaki mal ve bağlı para.

Satılabilir depolar (Merkez + Happy Life) dışındaki depolar — iade, teknik, ikinci el, outlet,
pazarlama, hurda… — ekranlarda "bizim stok"a girmediği için görünmüyordu. Bu sayfa her depodaki
adedi, paçal maliyetle değerini ve malın ne kadar süredir beklediğini gösterir. SALT OKUNUR.

Bekleme süresi FIFO (kayranpm.stok_yasi ile aynı kural: elde kalan mal en yeni girişlerdendir):
  İADE DEPO       iade kayıtlarının tarihi (iadeler.tarih) + depoya sevk girişleri (stok defteri).
  Diğer depolar   stok defterindeki giriş ve sevk girişleri (stok_hareketleri.zaman).
  Kayıt yok       stok defteri 30.09.2026'da başladı; girişi bulunamayan adet "giriş kaydı yok"
                  sayılır, yaşı tahmin edilmez. G5F sayım farkları (tür 'aktarim') giriş sayılmaz.
Değer: paçal maliyet (satis.database.get_pacal_map, USD), kartın SKU'suyla.
"""
from kayranpm.stok_yasi import KAYITSIZ, fifo_kalan, grup_adi, yas_ozeti

IADE_DEPO = "İADE DEPO"
YASLI_GUN = 90                     # özetteki "90 günü geçen"
_GIRIS_TURLERI = ("giris", "sevk")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ── Saf ─────────────────────────────────────────────────────────────
def partiler(iadeler, hareketler, depo_kanonik, anahtar):
    """{(kanonik depo, anahtar(sku)): [{"tarih", "adet"}]} — depoya giriş partileri.
    İADE DEPO'ya iade girişleri iade kaydından (gerçek iade tarihi; defterdeki zaman toplu aktarım
    günüdür) alınır; o depoya defterdeki 'giris' satırları bu yüzden ayrıca sayılmaz."""
    out = {}
    for r in iadeler or []:
        d = depo_kanonik(str(r.get("depo") or "").strip() or "MERKEZ DEPO")
        if d != IADE_DEPO or not str(r.get("sku") or "").strip():
            continue
        out.setdefault((d, anahtar(r.get("sku"))), []).append(
            {"tarih": str(r.get("tarih") or "")[:10], "adet": _f(r.get("iade_adet"))})
    for h in hareketler or []:
        if h.get("basarili") is False or _f(h.get("degisim")) <= 0 or h.get("tur") not in _GIRIS_TURLERI:
            continue
        d = depo_kanonik(str(h.get("depo") or "").strip() or "MERKEZ DEPO")
        if d == IADE_DEPO and h.get("tur") == "giris":
            continue
        out.setdefault((d, anahtar(h.get("sku"))), []).append(
            {"tarih": str(h.get("zaman") or "")[:10], "adet": _f(h.get("degisim"))})
    return out


def satirlar(urunler, parti_map, bugun, *, kirilim, satilabilir, anahtar, birim, ad):
    """Satılamayan depolardaki her (depo, ürün) için bir satır.
    kirilim(depo_kirilim) → [(kanonik depo, adet)]; birim(sku) → paçal; ad(sku, yedek) → ürün adı."""
    out = []
    for u in urunler or []:
        sku = str(u.get("sku") or "").strip()
        if not sku:
            continue
        for depo, adet in kirilim(u.get("depo_kirilim")):
            adet = _f(adet)
            if depo in satilabilir or adet <= 0:
                continue
            kalanlar, kaps = fifo_kalan(parti_map.get((depo, anahtar(sku))) or [], adet)
            oz = yas_ozeti(kalanlar, kaps, bugun)
            b = _f(birim(sku))
            out.append({
                "depo": depo, "sku": sku, "ad": ad(sku, u.get("urun_adi")), "adet": adet,
                "birim": b, "deger": round(adet * b, 2),
                "ort_gun": None if oz["ort_gun"] is None else round(oz["ort_gun"]),
                "en_eski_gun": oz["en_eski_gun"], "en_eski_tarih": oz["en_eski_tarih"],
                "kayitsiz": oz["kapsanmayan"],
                "grup": grup_adi(oz["en_eski_gun"]) if oz["en_eski_gun"] is not None else KAYITSIZ,
                "yasli": sum(_f(k.get("kalan")) for k in kalanlar
                             if (bugun - _tarih(k.get("tarih"), bugun)).days > YASLI_GUN),
            })
    out.sort(key=lambda r: (-r["deger"], r["depo"], r["sku"]))
    return out


def _tarih(t, yedek):
    from datetime import date
    try:
        return date.fromisoformat(str(t)[:10])
    except (TypeError, ValueError):
        return yedek


def depo_ozeti(rows):
    """Depo başına: {depo, cesit, adet, deger, yasli_adet, yasli_deger, kayitsiz} — değere göre azalan."""
    oz = {}
    for r in rows or []:
        o = oz.setdefault(r["depo"], {"depo": r["depo"], "cesit": 0, "adet": 0.0, "deger": 0.0,
                                      "yasli_adet": 0.0, "yasli_deger": 0.0, "kayitsiz": 0.0})
        o["cesit"] += 1
        o["adet"] += r["adet"]
        o["deger"] += r["deger"]
        o["yasli_adet"] += r["yasli"]
        o["yasli_deger"] += r["yasli"] * r["birim"]
        o["kayitsiz"] += r["kayitsiz"]
    return sorted(oz.values(), key=lambda o: (-o["deger"], o["depo"]))


# ── Okuma ───────────────────────────────────────────────────────────
def hesapla(bugun=None):
    """Canlı veriden (satırlar, depo özeti)."""
    from datetime import date
    from kayranpm.database import _hepsi, _SATILABILIR_DEPOLAR, depo_dagilimi, depo_kanonik
    from satis.database import get_iadeler, get_pacal_map, pacal_bul
    from shared.ana_veri import urun_ad
    from shared.utils import sku_anahtar
    bugun = bugun or date.today()
    urunler = _hepsi("urunler", "sku, urun_adi, depo_kirilim") or []
    try:
        hareketler = _hepsi("stok_hareketleri", "sku, depo, degisim, tur, zaman, basarili") or []
    except Exception:                 # defter tablosu yoksa: iade tarihleri + "giriş kaydı yok"
        hareketler = []
    pmap = partiler(get_iadeler() or [], hareketler, depo_kanonik, sku_anahtar)
    pacal = get_pacal_map() or {}
    rows = satirlar(urunler, pmap, bugun, kirilim=lambda dk: depo_dagilimi(dk)[0],
                    satilabilir=_SATILABILIR_DEPOLAR, anahtar=sku_anahtar,
                    birim=lambda s: pacal_bul(pacal, s), ad=urun_ad)
    return rows, depo_ozeti(rows)


# ── Ekran ───────────────────────────────────────────────────────────
def render():
    import streamlit as st
    from shared.masa_liste import ciz, kolon
    from shared.tasarim import kpi_serit, sayfa_baslik, tr_sayi
    st.markdown(sayfa_baslik("", "Satılamayan stok",
                             "Satılabilir stoğa girmeyen depolardaki mal · paçal değeri · bekleme süresi"),
                unsafe_allow_html=True)
    try:
        rows, ozet = hesapla()
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("depo.satilamayan.hesapla", e)
        st.error("Veri okunamadı; biraz sonra yeniden deneyin.")
        return
    if not rows:
        st.info("Satılabilir depolar dışında stoklu ürün yok.")
        return

    def _usd(v):
        return f"${tr_sayi(round(v))}"
    t_adet = sum(o["adet"] for o in ozet)
    t_deger = sum(o["deger"] for o in ozet)
    y_deger = sum(o["yasli_deger"] for o in ozet)
    kayitsiz = sum(o["kayitsiz"] for o in ozet)
    st.markdown(kpi_serit([
        {"etiket": "Toplam adet", "deger": tr_sayi(round(t_adet)), "alt": f"{len(ozet)} depo · {len(rows)} kalem"},
        {"etiket": "Paçal değeri", "deger": _usd(t_deger), "renk": "mor"},
        {"etiket": f"{YASLI_GUN} günü geçen", "deger": _usd(y_deger), "renk": "amber",
         "alt": "girişi kayıtlı maldan"},
        {"etiket": "Giriş kaydı yok", "deger": tr_sayi(round(kayitsiz)), "renk": "soluk",
         "alt": "stok defteri 30.09.2026'da başladı"},
    ]), unsafe_allow_html=True)

    st.markdown("**Depo bazında**")
    ciz([{"Depo": o["depo"], "Çeşit": o["cesit"], "Adet": o["adet"], "Paçal değeri": o["deger"],
          f"{YASLI_GUN}+ gün adet": o["yasli_adet"], f"{YASLI_GUN}+ gün değer": o["yasli_deger"],
          "Kayıtsız adet": o["kayitsiz"]} for o in ozet],
        [kolon("Depo", ana=True), kolon("Çeşit", "adet", gen="80px"), kolon("Adet", "adet", gen="90px"),
         kolon("Paçal değeri", "usd", gen="120px"), kolon(f"{YASLI_GUN}+ gün adet", "adet", gen="110px"),
         kolon(f"{YASLI_GUN}+ gün değer", "usd", gen="120px"), kolon("Kayıtsız adet", "adet", gen="110px")],
        "dpo_satilamayan_ozet")

    st.markdown("**Ürünler**")
    ciz([{"Ürün": r["ad"] or r["sku"], "SKU": r["sku"], "Depo": r["depo"], "Adet": r["adet"],
          "Birim paçal": r["birim"], "Değer": r["deger"], "Ort. bekleme (gün)": r["ort_gun"],
          "En eski giriş": r["en_eski_tarih"] or None, "Yaş grubu": r["grup"],
          "Kayıtsız adet": r["kayitsiz"]} for r in rows],
        [kolon("Ürün", ana=True, alt="SKU"), kolon("SKU", gizli=True), kolon("Depo", secim=True),
         kolon("Adet", "adet", gen="80px"), kolon("Birim paçal", "usd", gen="100px", genis=True),
         kolon("Değer", "usd", gen="110px"), kolon("Ort. bekleme (gün)", "adet", gen="110px"),
         kolon("En eski giriş", "tarih", gen="110px", genis=True), kolon("Yaş grubu", secim=True, gen="120px"),
         kolon("Kayıtsız adet", "adet", gen="100px", genis=True)],
        "dpo_satilamayan_urun", excel="satilamayan_stok")
    st.caption("Bekleme süresi FIFO: elde kalan mal depoya en son girenlerdendir. İade deposunda iade tarihi, "
               "diğerlerinde stok defterindeki giriş esas alınır. Girişi kayıtlı olmayan adet ayrı yazılır, "
               "yaşı tahmin edilmez. Değer paçal maliyettir (USD).")

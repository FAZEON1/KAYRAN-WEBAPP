# -*- coding: utf-8 -*-
"""Depolar arası sevk Mikro'dan (Ekim 2026).

Depo stoğu Mikro'dan otomatik geliyor (kayranpm.mikro_stok, durum "mikro_stok_durum"). Uygulamadaki sevk formu
kendi sevk kaydını yazıyordu (depo_sevk_log + stok defteri, kaynak 'depo/main.py:_sayfa_sevk'); bir sonraki Mikro
stok eşitlemesi depo kırılımını Mikro'nun rakamıyla baştan yazdığı için o sevk sessizce kayboluyordu. Eşitleme
açıkken sevk Mikro'da yapılır (depo transfer fişi); Depo › Sevk sayfası kayıt yapmaz, sevk geçmişini aktarıcının
mikro_depo_hareket tablosundan (sth_tip 2) gösterir. Eşitleme kapalıyken sayfa eskisi gibi çalışır.

Satır kuralları kayranpm.mikro_depo.hareketler ile aynı: iptal, değer farkı, sıfır miktar ve aynı depoya sevk
atlanır; SKU shared.utils.sku_anahtar ("Fazeon X24F165S" = X24F165S); depo adı mikro_depo_kart → depo_kanonik
(SERVİS DEPO → TEKNİK DEPO, OUTLET → OUTLET DEPO). Okuma sıralı (birincil anahtar sth_guid) ve kopya denetimli
(satis.mikro_esitle.kopyasiz): tutarsız okumada liste gösterilmez.
"""
from kayranpm.mikro_depo import KOLONLAR, TABLO, hareketler

SEVK_TIP = 2


def _s(v):
    return str(v or "").strip()


def _i(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


# ── Saf ────────────────────────────────────────────────────────────
def kayit_serbest(mikro_acik):
    """Uygulamada sevk kaydı yapılabilir mi: yalnız Mikro stok eşitlemesi kapalıyken."""
    return not mikro_acik


def sevk_satirlari(satirlar, depo_adlari, ad_bul=None):
    """mikro_depo_hareket satırları → [{tarih, evrak, sku, urun, adet, cikis, giris}] (yeni → eski).
    Yalnız depolar arası sevk (sth_tip 2). ad_bul: sku → ürün adı (ekranda shared.ana_veri.urun_ad)."""
    out = []
    for h in hareketler(satirlar, depo_adlari):
        if h["tur"] != "sevk":
            continue
        out.append({"tarih": h["tarih"], "evrak": h["belge"], "sku": h["sku"],
                    "urun": (ad_bul(h["sku"]) if ad_bul else "") or "", "adet": h["adet"],
                    "cikis": h["cikis"], "giris": h["giris"]})
    out.reverse()                      # hareketler eski → yeni (tarihe göre kararlı) sıralı
    return out


def eski_uygulama_kayitlari(gecmis, ilk_mikro_tarih):
    """depo_sevk_log satırlarından Mikro sevk geçmişinin başladığı günden ÖNCEKİLER (sevk tarihi; yoksa kayıt
    tarihi). Mikro'da sevk yoksa hepsi."""
    out = []
    for g in gecmis or []:
        t = _s(g.get("sevk_tarihi"))[:10] or _iso(g.get("tarih"))
        if not ilk_mikro_tarih or (t and t < ilk_mikro_tarih):
            out.append(g)
    return out


def _iso(v):
    """'03.07.2026 14:16' ya da ISO → 'YYYY-AA-GG' ("" : çözülemedi)."""
    s = _s(v)
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    p = s[:10].split(".")
    if len(p) == 3 and all(x.isdigit() for x in p):
        return f"{p[2]}-{p[1].zfill(2)}-{p[0].zfill(2)}"
    return ""


def ozet(satirlar):
    """{kalem, adet, evrak, ilk, son} — liste üstündeki kısa bilgi için."""
    return {"kalem": len(satirlar or []), "adet": sum(r["adet"] for r in satirlar or []),
            "evrak": len({(r["tarih"], r["evrak"]) for r in satirlar or []}),
            "ilk": min((r["tarih"] for r in satirlar or []), default=""),
            "son": max((r["tarih"] for r in satirlar or []), default="")}


# ── Veritabanı ─────────────────────────────────────────────────────
def sevk_oku(cli=None):
    """(sevk hareket satırları, {dep_no: dep_adi}). Sıralı okuma (sth_guid) + kopya denetimi: aynı satır iki kez
    gelirse satis.mikro_esitle.OkumaTutarsiz fırlar (sayfalı okuma kaydı; liste yanlış toplam göstermesin)."""
    from satis.mikro_esitle import kopyasiz
    if cli is None:
        from kayranpm.database import get_client
        cli = get_client()
    satir = kopyasiz(cli.table(TABLO).select(KOLONLAR).eq("sth_tip", SEVK_TIP).order("sth_guid").execute().data
                     or [], "sth_guid")
    depo = {_i(d.get("dep_no")): _s(d.get("dep_adi")) for d in
            (cli.table("mikro_depo_kart").select("dep_no,dep_adi").order("dep_no").execute().data or [])}
    return satir, depo


def sevk_gecmisi():
    """Ekran için: Mikro sevk satırları (ürün adı kart adından)."""
    from shared.ana_veri import urun_ad
    satir, depo = sevk_oku()
    return sevk_satirlari(satir, depo, lambda sku: urun_ad(sku))


try:                                      # 5 dk önbellek (aktarıcı 15 dakikada bir çeker)
    import streamlit as _st
    sevk_gecmisi = _st.cache_data(ttl=300, show_spinner=False)(sevk_gecmisi)
except Exception:  # noqa: BLE001
    pass


# ── Ekran ──────────────────────────────────────────────────────────
def ekran():
    """Mikro stok eşitlemesi açıkken Depo › Sevk: kayıt formu yok; bilgi + Mikro'daki sevk geçmişi."""
    import streamlit as st
    from shared.tasarim import tr_sayi
    from shared.masa_liste import kolon as _k, ciz as _liste
    st.info("Depo stoğu Mikro'dan geliyor: depolar arası sevk Mikro'da (depo transfer fişi) yapılır, depo stoğu "
            "oradan gelir. Uygulamada sevk kaydı yapılmaz; yapılsaydı bir sonraki Mikro eşitlemesinde silinirdi.")
    from satis.mikro_esitle import OkumaTutarsiz
    try:
        satirlar = sevk_gecmisi()
    except OkumaTutarsiz:
        st.warning("Mikro sevk kayıtları tutarlı okunamadı (aynı kayıt iki kez geldi; aktarıcı o sırada yazıyor "
                   "olabilir). Liste gösterilmedi; birkaç dakika sonra sayfayı yenile.")
        return
    except Exception as e:  # noqa: BLE001 — tablo yok / bağlantı
        from shared.kayit import sessiz
        sessiz("depo.mikro_sevk.ekran", e)
        st.warning("Mikro sevk kayıtları okunamadı.")
        return
    o = ozet(satirlar)
    from depo.depo_hesap import tarih_tr
    st.markdown('<div style="font-size:14px;font-weight:700;color:var(--k-metin);margin:4px 0 8px">'
                "Mikro'daki sevkler</div>", unsafe_allow_html=True)
    if satirlar:
        st.caption(f"{tr_sayi(o['evrak'])} sevk fişi · {tr_sayi(o['kalem'])} kalem · {tr_sayi(o['adet'])} adet · "
                   f"{tarih_tr(o['ilk'])} – {tarih_tr(o['son'])}")
    _liste([{"Tarih": r["tarih"], "Evrak No": r["evrak"], "SKU": r["sku"], "Ürün": r["urun"] or r["sku"],
             "Çıkış deposu": r["cikis"], "Giriş deposu": r["giris"], "Adet": r["adet"]} for r in satirlar],
           [_k("Ürün", ana=True, alt="SKU"), _k("SKU", gizli=True), _k("Tarih", "tarih", gen="104px"),
            _k("Evrak No", gen="100px"), _k("Çıkış deposu", secim=True, gen="150px"),
            _k("Giriş deposu", secim=True, gen="150px"), _k("Adet", "adet", gen="80px")],
           "dpo_mikro_sevk_masa", toplam=["Adet"], bos="Mikro'da depolar arası sevk kaydı yok.",
           baslik_ipucu="Mikro'daki sevkler", ara_ipucu="Ürün, SKU, depo ya da evrak no", excel="mikro_sevkler")

    # Mikro geçmişinden önceki uygulama kayıtları (varsa) — salt okunur
    from kayranpm.database import get_depo_sevk_gecmisi
    from shared.ana_veri import urun_ad
    eski = eski_uygulama_kayitlari(get_depo_sevk_gecmisi(1000), o["ilk"])
    if eski:
        with st.expander(f"Mikro öncesi uygulama sevk kayıtları ({tr_sayi(len(eski))})"):
            _liste([{"Sevk Tarihi": g.get("sevk_tarihi") or _iso(g.get("tarih")), "Belge No": g.get("belge_no") or "",
                     "SKU": g.get("sku", ""), "Ürün": urun_ad(g.get("sku"), g.get("urun_adi")),
                     "Kaynak": g.get("kaynak_depo", ""), "Hedef": g.get("hedef_depo", ""), "Adet": g.get("adet", ""),
                     "Kullanıcı": g.get("kullanici", "")} for g in eski],
                   [_k("Ürün", ana=True, alt="SKU"), _k("SKU", gizli=True), _k("Sevk Tarihi", "tarih", gen="104px"),
                    _k("Kaynak", secim=True, gen="150px"), _k("Hedef", secim=True, gen="150px"),
                    _k("Adet", "adet", gen="80px"), _k("Belge No", genis=True), _k("Kullanıcı", secim=True, genis=True)],
                   "dpo_eski_sevk_masa", toplam=["Adet"], bos="Kayıt yok.", baslik_ipucu="Uygulama kayıtları")

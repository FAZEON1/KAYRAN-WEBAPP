# -*- coding: utf-8 -*-
"""Veri sağlığı sayfası (Ekim 2026) — dağınık veri kontrolleri tek ekranda.

SALT OKUNUR: hiçbir kaydı değiştirmez. Her kontrol uygulamadaki MEVCUT fonksiyonları kullanır
(kendi hesabını yazmaz); her kartın "Düzelt" düğmesi o sorunun düzeltildiği mevcut ekrana götürür.
Herkes yalnız yetkili olduğu modüllerin kontrollerini görür; sistem kontrolleri yalnız yöneticiye.

Hazır olup ekranı olmayan onarım aracı (mükerrer kart birleştirme) burada yalnız LİSTELENİR —
stok rakamını değiştirdiği için düğmesi ayrı onay ister.

Kontroller saf fonksiyonlardır (veriyi alır, sorunlu satırları döndürür) — tests/test_veri_sagligi.py.
"""
from datetime import date, timedelta

ESKI_GUN = 1100          # bundan eski tarihli satış şüpheli (~3 yıl; içe aktarma önizlemesiyle aynı)
MUSTERI_GUN = 56         # müşteri raporu eşleşme kontrolü: son 8 hafta
SISTEM_GUN = 7


# ── Saf kontroller ──────────────────────────────────────────────────
def _s(v):
    return str(v or "").strip()


def kategorisiz_markasiz(urunler):
    """Kategorisi ya da markası boş ürün kartları."""
    out = []
    for u in urunler or []:
        eksik = [ad for ad, alan in (("kategori", "kategori"), ("marka", "marka")) if not _s(u.get(alan))]
        if _s(u.get("sku")) and eksik:
            out.append({"SKU": _s(u.get("sku")), "Ürün": _s(u.get("urun_adi")), "Eksik": ", ".join(eksik)})
    return sorted(out, key=lambda r: r["SKU"])


def mukerrer_kartlar(gruplar):
    """mukerrer_sku_bul() çıktısı → satırlar (her grup bir satır)."""
    return [{"SKU": g.get("kanonik"), "Kart sayısı": len(g.get("kartlar") or []),
             "Yazımlar": " · ".join(_s(k.get("sku")) for k in g.get("kartlar") or []),
             "Toplam stok": sum(int(float(k.get("bizim_stok") or 0)) for k in g.get("kartlar") or [])}
            for g in gruplar or []]


def ithalat_kartsiz(eklenecek, ith_ozet):
    """İthalatta geçip ürün kartı olmayan SKU'lar (ithalat_senkron_onizleme)."""
    out = []
    for sku in sorted(eklenecek or []):
        o = (ith_ozet or {}).get(sku) or {}
        out.append({"SKU": sku, "Ürün": _s(o.get("urun_adi") if isinstance(o, dict) else "")})
    return out


def maliyetsiz_satislar(satislar, pacal, anahtar):
    """Maliyeti 0 olan satışlar (adet > 0), SKU bazında: paçaldan onarılabilir mi, ithalatı yok mu.
    Tanım Patron panosundaki 'Veri kalitesi' ile aynı (shared/patron._veri_kalitesi)."""
    gr = {}
    for s in satislar or []:
        try:
            if float(s.get("birim_maliyet") or 0) > 0 or int(float(s.get("adet") or 0)) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        sku = _s(s.get("sku"))
        g = gr.setdefault(sku, {"SKU": sku, "Ürün": _s(s.get("urun_adi")), "Satır": 0, "Adet": 0})
        g["Satır"] += 1
        g["Adet"] += int(float(s.get("adet") or 0))
    for g in gr.values():
        g["Durum"] = "paçaldan onarılır" if float((pacal or {}).get(anahtar(g["SKU"]), 0) or 0) > 0 \
            else "ithalatı yok"
    return sorted(gr.values(), key=lambda r: (r["Durum"] != "paçaldan onarılır", -r["Adet"]))


def anormal_tarihli_satislar(satislar, bugun):
    """Tarihi boş, gelecekte ya da ESKI_GUN'den eski satış satırları."""
    bugun_s = str(bugun)
    eski_s = str(date.fromisoformat(bugun_s) - timedelta(days=ESKI_GUN))
    out = []
    for s in satislar or []:
        t = _s(s.get("tarih"))[:10]
        neden = "tarih yok" if not t else "gelecek tarih" if t > bugun_s else "çok eski" if t < eski_s else ""
        if neden:
            out.append({"Tarih": t or "—", "Sipariş": _s(s.get("siparis_no")) or "—", "Firma": _s(s.get("kanal")),
                        "SKU": _s(s.get("sku")), "Adet": s.get("adet"), "Neden": neden})
    return sorted(out, key=lambda r: r["Tarih"], reverse=True)


def zararina_urunler(dash):
    """Satış fiyatı paçal maliyetin altında olan ürünler (dashboard kar_durum = 'zarar')."""
    return [{"SKU": _s(u.get("sku")), "Ürün": _s(u.get("urun_adi")), "Stok": u.get("toplam_stok")}
            for u in dash or [] if u.get("kar_durum") == "zarar"]


def eksi_stok(dash):
    out = []
    for u in dash or []:
        try:
            st_ = float(u.get("toplam_stok") or 0)
        except (TypeError, ValueError):
            continue
        if st_ < 0:
            out.append({"SKU": _s(u.get("sku")), "Ürün": _s(u.get("urun_adi")), "Stok": st_})
    return sorted(out, key=lambda r: r["Stok"])


def satilabilir_farklari(urunler, kontrol):
    """Depo kırılımından hesaplanan satılabilir ≠ kayıtlı stok (kontrol = satilabilir_kontrol)."""
    out = []
    for u in urunler or []:
        if not u.get("depo_kirilim"):
            continue
        r = kontrol(u.get("depo_kirilim"), u.get("bizim_stok"))
        if r and r.get("fark"):
            out.append({"SKU": _s(u.get("sku")), "Ürün": _s(u.get("urun_adi")), "Kırılımdan": r.get("hesap"),
                        "Kayıtlı": r.get("kayitli"), "Fark": r.get("fark")})
    return sorted(out, key=lambda r: -abs(r["Fark"] or 0))


def eslesmeyen_rapor_kodlari(rows, meta):
    """Müşteri raporunda kartla eşleşmeyen ya da birden çok karta benzeyen kodlar (meta_hazirla)."""
    gr = {}
    for r in rows or []:
        ham = _s(r.get("sku"))
        m = (meta or {}).get(ham) or {}
        if m.get("kart_kaynak") not in ("belirsiz", ""):
            continue
        g = gr.setdefault(ham, {"Rapor kodu": ham, "Ürün adı (rapor)": _s(r.get("urun_adi")), "Firma": set(),
                                "Durum": "birden çok aday" if m.get("kart_kaynak") == "belirsiz" else "kart yok"})
        g["Firma"].add(_s(r.get("firma")))
    return [dict(g, Firma=", ".join(sorted(x for x in g["Firma"] if x))) for g in
            sorted(gr.values(), key=lambda g: g["Rapor kodu"])]


def iadesi_satisini_asan(satirlar):
    """iade_satis_net_ozet satırları → iade adedi satış adedini geçen SKU'lar."""
    return [{"SKU": _s(r.get("sku")), "Ürün": _s(r.get("urun_adi")), "Satış": r.get("s_adet"),
             "İade": r.get("i_adet"), "Fark": r.get("net_adet")}
            for r in satirlar or [] if (r.get("net_adet") or 0) < 0]


def teslim_bekleyen(dosyalar):
    return [{"Dosya": _s(d.get("dosya_no")), "Teslim deposu": _s(d.get("teslim_deposu")),
             "Kalem": d.get("kalem_sayisi"), "Adet": d.get("toplam_adet")} for d in dosyalar or []]


def son_gunler(kayitlar, alan, bugun, gun=SISTEM_GUN):
    sinir = str(date.fromisoformat(str(bugun)) - timedelta(days=gun))
    return [k for k in kayitlar or [] if _s(k.get(alan))[:10] >= sinir]


# ── Veri (mevcut fonksiyonlar) ─────────────────────────────────────
def _bugun():
    return date.today().isoformat()


def _urunler():
    from kayranpm.database import _hepsi
    return _hepsi("urunler", "sku, urun_adi, kategori, marka, bizim_stok, depo_kirilim")


def _k_kategori():
    return kategorisiz_markasiz(_urunler())


def _k_mukerrer():
    from kayranpm.database import mukerrer_sku_bul
    return mukerrer_kartlar(mukerrer_sku_bul())


def _k_ithalat_kartsiz():
    from kayranpm.database import ithalat_senkron_onizleme
    ekle, _sil, _kor, ith, _mev = ithalat_senkron_onizleme()
    return ithalat_kartsiz(ekle, ith)


def _k_maliyetsiz():
    from satis.database import get_satislar, get_pacal_map
    from shared.utils import sku_anahtar
    pacal = {sku_anahtar(k): v for k, v in (get_pacal_map() or {}).items()}
    return maliyetsiz_satislar(get_satislar() or [], pacal, sku_anahtar)


def _k_tarih():
    from satis.database import get_satislar
    return anormal_tarihli_satislar(get_satislar() or [], _bugun())


def _k_zararina():
    from kayranpm.analitik import dashboard_hesapla
    return zararina_urunler(dashboard_hesapla() or [])


def _k_eksi_stok():
    from kayranpm.analitik import dashboard_hesapla
    return eksi_stok(dashboard_hesapla() or [])


def _k_satilabilir():
    from kayranpm.database import satilabilir_kontrol
    return satilabilir_farklari(_urunler(), satilabilir_kontrol)


def _k_eslesme():
    from kayranpm import musteri_hesap as H
    from kayranpm.database import (KATEGORI_LISTE, MARKA_KURALLAR, get_musteri_haftalik_satis, get_sku_eslesme,
                                   get_urun_marka_kategori, kategori_oner, marka_oner)
    from shared.utils import sku_anahtar
    bit = date.today()
    rows = get_musteri_haftalik_satis(str(bit - timedelta(days=MUSTERI_GUN)), str(bit)) or []
    es = get_sku_eslesme()
    meta = H.meta_hazirla(rows, get_urun_marka_kategori() or {}, sku_fn=sku_anahtar, oner=kategori_oner,
                          kategori_liste=KATEGORI_LISTE, marka_oner=marka_oner,
                          marka_liste=[m for m, _ in MARKA_KURALLAR],
                          eslesme={r.get("dis_kod"): r.get("kart_sku") for r in (es or [])})
    return eslesmeyen_rapor_kodlari(rows, meta)


def _k_iade():
    from satis.database import iade_satis_net_ozet
    satirlar, _t = iade_satis_net_ozet(f"{date.today().year}-01-01", _bugun())
    return iadesi_satisini_asan(satirlar)


def _k_teslim():
    from ithalat.database import teslim_stok_bekleyenler
    return teslim_bekleyen(teslim_stok_bekleyenler())


def teslim_notu(kayitsiz_sayi):
    if not kayitsiz_sayi:
        return ""
    from shared.tasarim import tr_sayi
    return (f"İşlenme kaydı olmayan {tr_sayi(kayitsiz_sayi, 0)} teslim dosyası listelenmez: kayıt tutulmaya "
            "başlamadan önce teslim alınmışlar, stoklarının nasıl girdiği bilinmiyor.")


def _n_teslim():
    from ithalat.database import teslim_stok_kayitsiz
    return teslim_notu(len(teslim_stok_kayitsiz() or []))


def _k_sistem():
    from shared.hata_log import son_hatalar
    from shared.stok_defteri import gecmis
    out = [{"Zaman": _s(h.get("zaman"))[:16].replace("T", " "), "Tür": "başarısız stok hareketi",
            "Ayrıntı": f"{_s(h.get('sku'))} · {_s(h.get('depo'))} · {_s(h.get('aciklama') or h.get('hata'))}"[:160]}
           for h in son_gunler(gecmis(limit=500, yalniz_basarisiz=True), "zaman", _bugun())]
    out += [{"Zaman": _s(h.get("zaman"))[:16].replace("T", " "), "Tür": "hata kaydı",
             "Ayrıntı": f"{_s(h.get('yer'))}: {_s(h.get('mesaj'))}"[:160]}
            for h in son_gunler(son_hatalar(limit=300), "zaman", _bugun())]
    return sorted(out, key=lambda r: r["Zaman"], reverse=True)


# kod, başlık, modül (yetki), açıklama, (düzelt hedefi, düğme), hesap, not (metin: sorun varsa;
# fonksiyon: her zaman, boş değilse)
KONTROLLER = [
    ("kategori", "Kategorisi ya da markası boş ürün", "kayranpm",
     "Raporlarda 'Kategorisiz' / 'DİĞER' satırına düşer.", ("kayranpm/veri_yukleme", "Toplu kategori ve marka"),
     _k_kategori, ""),
    ("mukerrer", "Mükerrer ürün kartı", "kayranpm",
     "Aynı SKU büyük / küçük harf farkıyla iki kart; stok ve satış ikiye bölünür.", None, _k_mukerrer,
     "Birleştirme aracı hazır ama stok rakamını değiştirdiği için ayrı onayla açılacak."),
    ("ithalat_kartsiz", "İthalatta olup kartı olmayan SKU", "kayranpm",
     "İthal edilmiş ama ürün kartı açılmamış; Tüm Ürünler'de görünmez.", ("kayranpm/tum_urunler", "Tüm ürünler"),
     _k_ithalat_kartsiz, ""),
    ("eslesme", "Kartla eşleşmeyen müşteri raporu kodu", "kayranpm",
     f"Son {MUSTERI_GUN // 7} haftanın müşteri raporlarında hiçbir karta (ya da birden çok karta) uyan kodlar.",
     ("kayranpm/musteri_satislari", "Müşteri satışları"), _k_eslesme, ""),
    ("maliyetsiz", "Maliyeti 0 olan satış", "satis",
     "Kâr ve marj olduğundan yüksek görünür. 'Paçaldan onarılır' olanlar tek tıkla düzelir.",
     ("satis/pnl", "Kâr / P&L"), _k_maliyetsiz, ""),
    ("tarih", "Tarihi boş, gelecekte ya da çok eski satış", "satis",
     "Dönem raporlarında görünmez ya da yanlış döneme düşer.", ("satis/satislar", "Satışlar"), _k_tarih, ""),
    ("iade", "İadesi satışını aşan ürün (bu yıl)", "satis",
     "İade adedi satış adedinden fazla; satış ya da iade kaydı eksik / yanlış olabilir.", ("satis/iade", "İade"),
     _k_iade, ""),
    ("zararina", "Satış fiyatı maliyetin altında olan ürün", "kayranpm",
     "Ürün kartındaki satış fiyatı paçal maliyetin altında.", ("kayranpm/genel_bakis", "Genel bakış"),
     _k_zararina, ""),
    ("eksi_stok", "Eksi stoktaki ürün", "depo", "Stok sıfırın altına inmiş; bir hareket eksik ya da fazla işlenmiş.",
     ("depo/sku_hareket", "SKU hareketleri"), _k_eksi_stok, ""),
    ("satilabilir", "Satılabilir stok ≠ depo kırılımı", "depo",
     "Kayıtlı stok, depo kırılımından hesaplanan satılabilir stokla tutmuyor.", ("depo/stok", "Depo stok"),
     _k_satilabilir, "Genellikle son G5F sayımını yeniden yüklemek düzeltir."),
    ("teslim", "Teslim alındı ama stoğa girmemiş ithalat", "ithalat",
     "Dosya 'Teslim Alındı' ama kalemleri depoya işlenirken hata olmuş.", ("ithalat/gecmis", "Geçmiş ithalatlar"),
     _k_teslim, _n_teslim),
    ("sistem", f"Son {SISTEM_GUN} günde başarısız stok hareketi ya da hata kaydı", "sistem",
     "Uygulamanın kaydettiği hatalar.", ("sistem/sistem_kayitlari", "Sistem kayıtları"), _k_sistem, ""),
]


def gorunur_kontroller(yetkiler, yonetici):
    """Kullanıcının göreceği kontroller: yetkili olduğu modüller; 'sistem' yalnız yöneticiye."""
    return [k for k in KONTROLLER
            if (k[2] == "sistem" and yonetici) or (k[2] != "sistem" and (yonetici or (yetkiler or {}).get(k[2])))]


# ── Sayfa ───────────────────────────────────────────────────────────
def _hesapla_ham(kod, _gun):
    fn = next(k[5] for k in KONTROLLER if k[0] == kod)
    return fn()


try:                                     # 5 dk önbellek; gün değişince yeniden
    import streamlit as _st
    _hesapla_ham = _st.cache_data(ttl=300, show_spinner=False)(_hesapla_ham)
except Exception:  # noqa: BLE001
    pass


def _hesapla(kod):
    return _hesapla_ham(kod, _bugun())


def sayfa(aktif_kullanici, yetkiler, yonetici):
    import streamlit as st
    from shared.tasarim import baslik as _sb
    from shared.tablo import tablo

    st.markdown(_sb("Veri sağlığı", "Kontroller",
                    aciklama="verideki tutarsızlıklar tek ekranda · salt okunur · düzeltme ilgili ekranda"),
                unsafe_allow_html=True)
    liste = gorunur_kontroller(yetkiler, yonetici)
    if not liste:
        st.info("Yetkili olduğun modüllerde gösterilecek kontrol yok.")
        return
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    c1.caption(f"{len(liste)} kontrol · sonuçlar 5 dakika önbellekte")
    if c2.button("Yenile", key="vs_yenile", icon=":material/refresh:", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    sonuc = {}
    with st.spinner("Kontroller çalışıyor…"):
        for k in liste:
            try:
                sonuc[k[0]] = (_hesapla(k[0]), None)
            except Exception as e:  # noqa: BLE001
                sonuc[k[0]] = (None, f"{type(e).__name__}: {str(e)[:120]}")

    sorunlu = [k for k in liste if sonuc[k[0]][0]]
    temiz = [k for k in liste if sonuc[k[0]][0] == []]
    hatali = [k for k in liste if sonuc[k[0]][1]]
    st.markdown(_ozet_html(len(sorunlu), len(temiz), len(hatali)), unsafe_allow_html=True)

    for k in sorunlu + hatali + temiz:
        kod, ad, _mod, aciklama, duzelt, _fn, notu = k
        satirlar, hata = sonuc[kod]
        with st.container(border=True):
            sol, sag = st.columns([5, 1.4], vertical_alignment="center")
            sol.markdown(_kart_html(ad, aciklama, satirlar, hata), unsafe_allow_html=True)
            if duzelt and satirlar:
                if sag.button(f"{duzelt[1]}", key=f"vs_git_{kod}", icon=":material/arrow_forward:",
                              use_container_width=True, help="Düzeltmenin yapıldığı ekrana git"):
                    from shared.palet import git
                    git(duzelt[0])
            if callable(notu):
                try:
                    _n = notu()
                except Exception:  # noqa: BLE001
                    _n = ""
                if _n:
                    st.caption(_n)
            if satirlar:
                if notu and not callable(notu):
                    st.caption(notu)
                with st.expander(f"Listeyi göster ({len(satirlar)})"):
                    tablo(satirlar[:1000], key=f"vs_tablo_{kod}", dosya_adi=f"veri_sagligi_{kod}")
                    if len(satirlar) > 1000:
                        from shared.tasarim import tr_sayi
                        st.caption(f"İlk 1.000 satır gösteriliyor ({tr_sayi(len(satirlar), 0)} satır).")


def _ozet_html(n_sorun, n_temiz, n_hata):
    def kutu(sayi, etiket, renk):
        return (f'<div style="flex:1;min-width:120px;background:var(--k-yuzey1);border:1px solid var(--k-kenar);'
                f'border-radius:12px;padding:12px 16px"><div style="font-size:12px;color:var(--k-soluk)">{etiket}</div>'
                f'<div style="font-size:24px;font-weight:650;color:{renk}">{sayi}</div></div>')
    return ('<div style="display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 14px">'
            + kutu(n_sorun, "Sorun var", "var(--k-kirmizi)" if n_sorun else "var(--k-metin)")
            + kutu(n_temiz, "Temiz", "var(--k-yesil)" if n_temiz else "var(--k-metin)")
            + (kutu(n_hata, "Okunamadı", "var(--k-amber)") if n_hata else "") + "</div>")


def _kart_html(ad, aciklama, satirlar, hata):
    import html as _h
    from shared.tasarim import tr_sayi
    if hata:
        rozet = ('<span style="background:color-mix(in srgb,var(--k-amber) 16%,transparent);color:var(--k-amber);'
                 'border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600">okunamadı</span>')
    elif satirlar:
        rozet = ('<span style="background:color-mix(in srgb,var(--k-kirmizi) 16%,transparent);color:var(--k-kirmizi);'
                 f'border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600">{tr_sayi(len(satirlar), 0)}</span>')
    else:
        rozet = ('<span style="background:color-mix(in srgb,var(--k-yesil) 16%,transparent);color:var(--k-yesil);'
                 'border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600">temiz</span>')
    alt = _h.escape(hata) if hata else _h.escape(aciklama)
    return (f'<div style="display:flex;align-items:center;gap:10px;font-size:15px;font-weight:600">'
            f'{_h.escape(ad)} {rozet}</div>'
            f'<div style="font-size:13px;color:var(--k-soluk);margin-top:3px">{alt}</div>')

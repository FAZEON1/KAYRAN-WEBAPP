# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Tüm Ürünler — liste (Ekim 2026).

Eskiden sayfa açılınca TEK bir ürünün detayı geliyordu; asıl liste en alttaki
bir düğmenin arkasındaki pencerede duruyordu ve iki ayrı ürün seçici vardı
(gösterilen ürün ≠ düzenlenen ürün olabiliyordu). Artık sayfa listedir:
satıra tıklayınca main.py'deki sayfa içi detay açılır (B.sec("pm_urun", sku)).
Hesaplar urun_hesap.py'de (testli).
"""
import hashlib
import html as _h
import os
import tempfile
from functools import partial

import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi
from shared.utils import tr_now

from .urun_hesap import urun_satiri, urun_filtrele_sirala, KANALLAR

ON_EK = "pm_urun"
ADIM = 50
FILTRE_KEYS = ["pm_ul_ara", "pm_ul_sira", "pm_ul_kat", "pm_ul_mar", "pm_ul_zarar"]

# (etiket, satır alanı, azalan)
SIRALAMA = [
    ("Stok yaşı · en eski önce", "_stok_yas", True),
    ("Net kâr · yüksekten", "Net Kar ($)", True),
    ("Net kâr · düşükten", "Net Kar ($)", False),
    ("Net marj · yüksekten", "Net Marj (%)", True),
    ("Net marj · düşükten", "Net Marj (%)", False),
    ("Toplam stok · çoktan", "G5F Depo", True),
    ("Satış fiyatı · yüksekten", "Satış ($)", True),
    ("Maliyet % · yüksekten", "Maliyet %", True),
    ("Risk skoru · yüksekten", "_risk", True),
    ("SKU · A-Z", "SKU", False),
]
_YAS_RENK = {"yesil": "yesil", "sari": "amber", "turuncu": "amber", "kirmizi": "kirmizi"}


def _e(v):
    return _h.escape(str(v or "").strip())


def _usd(v):
    return f"&#36;{tr_sayi(float(v), 2)}"        # düz "$" iki kez geçerse LaTeX sanılır


def uretilen_bayt(uzanti, yaz):
    """yaz(yol) → (ok, mesaj): rapor.py fonksiyonları DOSYAYA yazar; burada bayta
    çevrilir, geçici dosya her durumda silinir. download_button(data=callable) ile
    yalnız tıklanınca, ayrı iş parçacığında çalışır (session_state okunamaz)."""
    fd, yol = tempfile.mkstemp(suffix=uzanti)
    os.close(fd)
    try:
        ok, msg = yaz(yol)
        if not ok:
            raise RuntimeError(msg)
        with open(yol, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(yol)
        except OSError:
            pass


def _tum_urun_yaz(uret, rows, meta, yol):
    return uret(rows, yol, meta)


def _satir(r, secili=False):
    sku = r["SKU"]
    nk, marj, fcp, satis = r.get("Net Kar ($)"), r.get("Net Marj (%)"), r.get("Final Cost ($)"), r.get("Satış ($)")
    yas_renk = _YAS_RENK.get(r.get("_stok_renk"))
    kanallar = " · ".join(f"{k} {r[k]}" for k in KANALLAR if r.get(k))
    meta = B.meta(
        B.cip(f"{r['_stok_yas']} gün", yas_renk, title="Stok yaşı") if yas_renk else "",
        f"G5F {tr_sayi(r['G5F Depo'])}" if r.get("G5F Depo") else "",
        kanallar,
        str(r.get("Kategori") or "").strip(),
        str(r.get("Marka") or "").strip(),
        B.cip("EOL", "silik") if r.get("_eol") else "")
    if fcp and satis:
        fiyat = f"{_usd(fcp)} → {_usd(satis)}"
    elif satis:
        fiyat = f"satış {_usd(satis)}"
    elif fcp:
        fiyat = f"paçal {_usd(fcp)}"
    else:
        fiyat = '<span style="color:var(--k-silik)">fiyat yok</span>'
    if nk is not None:
        renk = "kirmizi" if nk < 0 else "yesil"
        alt = (f'<div style="font-size:12px;font-weight:700;color:var(--k-{renk});margin-top:3px">'
               f'{"zarar" if nk < 0 else "marj"} %{tr_sayi(abs(marj or 0), 1)}</div>')
    else:
        alt = ""
    serit = "kirmizi" if (nk is not None and nk < 0) else ("silik" if r.get("_eol") else (yas_renk or "mor"))
    # Anahtar CSS sınıf adına dönüşür; SKU'da boşluk / özel karakter olabilir
    _k = hashlib.md5(str(sku).encode("utf-8")).hexdigest()[:12]
    B.tiklanir(
        f"{ON_EK}_{_k}",
        f'<div class="pu-sr{" secili" if secili else ""}"><div class="pu-sol"><div style="font-family:var(--k-mono);font-size:12.5px;'
        f'font-weight:700;color:var(--k-mor2);overflow:hidden;text-overflow:ellipsis">{_e(sku)}</div>'
        f'<div style="font-size:11.5px;color:var(--k-silik)">stok {tr_sayi(r.get("G5F Depo") or 0)}</div></div>'
        f'<div class="pu-orta"><div style="font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;'
        f'text-overflow:ellipsis">{_e(r.get("Ürün Adı")) or _e(sku)}</div>{meta}</div>'
        f'<div class="pu-sag"><div style="font-family:var(--k-mono);font-size:13px;font-weight:600">{fiyat}</div>'
        f'{alt}</div></div>',
        B.sec, (ON_EK, sku), tur="satir", renk=serit, etiket="Ürünü aç")


SATIR_CSS = (
    "<style>.pu-sr{display:grid;grid-template-columns:150px minmax(0,1fr) auto;gap:4px 16px;align-items:center}"
    ".pu-orta{min-width:0}.pu-sol{min-width:0}.pu-sag{text-align:right;white-space:nowrap}"
    "@media (max-width:640px){.pu-sr{grid-template-columns:minmax(0,1fr) auto}"
    ".pu-sag{order:2}.pu-orta{order:3;grid-column:1 / -1}}"
    ".pu-sr.secili{box-shadow:inset 3px 0 0 var(--k-mor);margin-left:-8px;padding-left:8px}</style>")

# Liste ve detay yan yana (shared.tasarim.YAN_YANA): dar sütunda satır telefon düzenine
# geçer; 900 px altında liste gizlenir ve eskisi gibi "Listeye dön" görünür.
YAN_YANA_CSS = (
    "<style>.st-key-pm_liste_sol{container-type:inline-size}"
    "@container (max-width:620px){.st-key-pm_liste_sol .pu-sr{grid-template-columns:minmax(0,1fr) auto}"
    ".st-key-pm_liste_sol .pu-sag{order:2}.st-key-pm_liste_sol .pu-orta{order:3;grid-column:1 / -1}}</style>"
    + B.yan_yana_css("pm_urun", liste_key="pm_liste_sol"))


def liste(urun_data, dar=False, secili=None):
    """dar=True: detayın yanındaki sütun (Excel/PDF düğmeleri yok); secili: vurgulanacak SKU."""
    tum = [urun_satiri(u) for u in urun_data]
    kategoriler = sorted({str(r["Kategori"]).strip() for r in tum if str(r["Kategori"]).strip()},
                         key=str.lower)
    markalar = sorted({str(r["Marka"]).strip() for r in tum if str(r["Marka"]).strip()}, key=str.lower)

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2.6, 1.8, 0.9], vertical_alignment="bottom")
    ara = c1.text_input("Ara", key="pm_ul_ara", label_visibility="collapsed",
                        placeholder="SKU ya da ürün adı…")
    sira_et = c2.selectbox("Sıralama", [s[0] for s in SIRALAMA], key="pm_ul_sira",
                           label_visibility="collapsed")
    ff = B.filtre(c3, [{"etiket": "Kategori", "secenekler": kategoriler, "key": "pm_ul_kat"},
                       {"etiket": "Marka", "secenekler": markalar, "key": "pm_ul_mar"}])
    _, alan, azalan = next(s for s in SIRALAMA if s[0] == sira_et)
    zarar_say = sum(1 for r in tum if r.get("Net Kar ($)") is not None and r["Net Kar ($)"] < 0)

    r1, r2, r3, r4 = st.columns([2.4, 1.5, 1.05, 1.05], vertical_alignment="center")
    sadece_zarar = r1.toggle((f"Zararına ({zarar_say})" if dar else f"Yalnız zararına satılanlar ({zarar_say})"),
                             key="pm_ul_zarar",
                             help="Satış fiyatı paçal maliyetin altında olan ürünler")
    goster = urun_filtrele_sirala(tum, ara=ara, kategori=ff["pm_ul_kat"], marka=ff["pm_ul_mar"],
                                  sadece_zarar=sadece_zarar, sira=alan, azalan=azalan)
    r2.caption(f"{tr_sayi(len(goster))} / {tr_sayi(len(tum))} ürün")
    if goster and not dar:
        from .rapor import tum_urunler_excel, tum_urunler_pdf
        meta = (f"Kategori: {ff['pm_ul_kat']} · Marka: {ff['pm_ul_mar']} · Sıra: {sira_et}"
                + (" · Yalnız zararına" if sadece_zarar else ""))
        zaman = tr_now().strftime("%Y%m%d_%H%M")
        r3.download_button("Excel", data=partial(uretilen_bayt, ".xlsx", partial(_tum_urun_yaz, tum_urunler_excel, list(goster), meta)),
                           file_name=f"Tum_Urunler_{zaman}.xlsx", key="pm_ul_xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/download:", use_container_width=True,
                           help="Ekrandaki filtre ve sıralamayla, tüm sütunlar")
        r4.download_button("PDF", data=partial(uretilen_bayt, ".pdf", partial(_tum_urun_yaz, tum_urunler_pdf, list(goster), meta)),
                           file_name=f"Tum_Urunler_{zaman}.pdf", key="pm_ul_pdf", mime="application/pdf",
                           icon=":material/download:", use_container_width=True)
    if not goster:
        st.info("Filtreyle eşleşen ürün yok.")
        return

    st.markdown(SATIR_CSS, unsafe_allow_html=True)
    limit = int(st.session_state.get("pm_ul_limit", ADIM))
    for r in goster[:limit]:
        _satir(r, secili=(secili is not None and r["SKU"] == secili))
    if len(goster) > limit:
        st.button(f"Daha fazla göster ({tr_sayi(len(goster) - limit)} ürün daha)", key="pm_ul_daha",
                  type="tertiary", use_container_width=True, on_click=_arttir)
    st.caption("Paçal = adet-ağırlıklı ithalat maliyeti · marj ve kâr paçala göre · "
               "son FOB/maliyet ve kanal kırılımı Excel'de.")


def _arttir():
    st.session_state["pm_ul_limit"] = int(st.session_state.get("pm_ul_limit", ADIM)) + ADIM

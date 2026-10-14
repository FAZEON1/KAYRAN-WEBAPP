# -*- coding: utf-8 -*-
"""GİRİŞ FORMLARI ORTAK PARÇALARI (Ekim 2026, formlar yeni düzen — onaylı taslak
https://claude.ai/artifact/Gg3qW4gpk7XXYEbiJYdx7N).

Düzen: üstte belge bilgileri tek satır · ortada kalem ekleme ve liste · sağda (telefonda altta sabit) özet ve
Kaydet. Satış girişi, Yurt içi alış ve Yeni ithalat bunu kullanır. Hesap yapmaz: gösterilen rakamlar formun
bugünkü hesaplarından gelir.

Sayı kutusu: st.number_input ondalığı noktayla gösteriyordu ("26.0000"). Para alanları artık Türkçe yazılır
ve gösterilir ("26,00", "1.234,56"); nokta ile yazılan ("26.5") de anlaşılır."""
import html as _html
import re

_SAYI = re.compile(r"^[+-]?[\d.,]+$")


def tr_sayi_oku(metin):
    """'1.234,56' / '1234,56' / '1234.56' / '26' → float; boş → None; okunamazsa ValueError.
    Kural: virgül varsa ondalık virgüldür (noktalar binlik); yalnız nokta varsa ve noktadan sonra tam üç rakam
    yoksa ondalık noktadır ('26.5', '41.2000'); '1.234' gibi tek noktalı üç haneli yazım binliktir."""
    s = str(metin if metin is not None else "").strip().replace(" ", "").replace(" ", "")
    s = s.replace("$", "").replace("₺", "").replace("€", "").replace("%", "")
    if not s:
        return None
    if not _SAYI.match(s):
        raise ValueError(metin)
    if "," in s:
        if s.count(",") > 1:
            raise ValueError(metin)
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif "." in s and len(s.split(".")[1]) == 3 and s.split(".")[0].lstrip("+-") not in ("", "0"):
        s = s.replace(".", "")                     # '1.234' → 1234 (Türkçe binlik)
    return float(s)


def tr_sayi_yaz(deger, basamak=2):
    """26 → '26,00' (kutunun içi; binlik nokta)."""
    if deger is None or deger == "":
        return ""
    from shared.tasarim import tr_sayi
    return tr_sayi(float(deger), basamak)


def sayi_kutusu(etiket, key, deger=None, *, basamak=2, en_az=0.0, kap=None, placeholder="0,00", yardim=None,
                disabled=False, label_visibility="visible"):
    """Türkçe para / sayı kutusu (text_input). Döner: float (boşsa 0.0); okunamazsa kutunun altında uyarı ve
    0.0. deger yalnız ilk açılışta kutuya yazılır (key oturumda yoksa)."""
    import streamlit as st
    kap = kap or st
    if key not in st.session_state and deger not in (None, ""):
        st.session_state[key] = tr_sayi_yaz(deger, basamak)
    metin = kap.text_input(etiket, key=key, placeholder=placeholder, help=yardim, disabled=disabled,
                           label_visibility=label_visibility)
    try:
        v = tr_sayi_oku(metin)
    except ValueError:
        kap.caption(f":red[Sayı okunamadı: {_html.escape(str(metin))} — örnek 1.234,56]")
        return 0.0
    if v is None:
        return 0.0
    if en_az is not None and v < en_az:
        kap.caption(f":red[{etiket}: en az {tr_sayi_yaz(en_az, basamak)}]")
        return float(en_az)
    return v


def ozet_paneli(baslik, satirlar, *, vurgu=None, uyarilar=()):
    """Sağdaki özet kartı (HTML). satirlar: [(etiket, değer)]; vurgu: (etiket, değer, renk) büyük satır
    (renk: yesil | kirmizi | metin); uyarilar: kısa metinler (sarı kutu). Değerler hazır biçimli gelir."""
    e = _html.escape
    h = [f'<div class="kf-ozet"><div class="kf-ozet-bas">{e(baslik)}</div>']
    for et, dg in satirlar:
        h.append(f'<div class="kf-sat"><span>{e(et)}</span><b>{e(str(dg))}</b></div>')
    if vurgu:
        et, dg, renk = vurgu
        h.append(f'<div class="kf-ayr"></div><div class="kf-sat kf-buyuk"><span>{e(et)}</span>'
                 f'<b style="color:var(--k-{e(renk or "metin")})">{e(str(dg))}</b></div>')
    for u in uyarilar or ():
        h.append(f'<div class="kf-uyari">{e(u)}</div>')
    h.append("</div>")
    return "".join(h)


def css():
    """Form düzeni stili: özet kartı; telefonda özet + Kaydet alt kenarda sabit (kaydırınca kaybolmaz).
    Özet sütunu st.container(key="kf_ozet_…") ile işaretlenir."""
    return """<style>
.kf-ozet{display:flex;flex-direction:column;gap:9px;padding:14px 16px;border:1px solid var(--k-kenar);
  border-radius:12px;background:var(--k-yuzey1);font-size:14px}
.kf-ozet-bas{font-weight:600;font-size:14px;color:var(--k-metin);margin-bottom:2px}
.kf-sat{display:flex;justify-content:space-between;gap:12px;color:var(--k-soluk)}
.kf-sat b{color:var(--k-metin);font-weight:500;font-variant-numeric:tabular-nums;white-space:nowrap}
.kf-buyuk span{align-self:flex-end}.kf-buyuk b{font-size:21px;font-weight:600}
.kf-ayr{height:1px;background:var(--k-kenar)}
.kf-uyari{font-size:12px;line-height:1.45;padding:8px 10px;border-radius:9px;
  background:color-mix(in srgb,var(--k-amber) 12%,transparent);
  border:1px solid color-mix(in srgb,var(--k-amber) 35%,transparent);color:var(--k-metin)}
@media (max-width: 640px){
  /* Sütunlar alt alta dizilince özet sütunu, iki sütunun ortak kutusu içinde alta yapışır: sepette
     gezinirken toplam ve Kaydet görünür kalır (kendi kutusuna sticky verilse yalnız kendi içinde kalırdı). */
  /* Pencerenin kutusu overflow:hidden; sticky'nin kaydırılan pencereye bağlanması için açılır (yalnız formda) */
  [data-testid="stDialog"] div[data-rac]:has([class*="st-key-kf_ozet_"]){overflow:visible !important}
  [data-testid="stColumn"]:has([class*="st-key-kf_ozet_"]){position:sticky;bottom:0;z-index:5;
    background:var(--k-yuzey0);padding:8px 0 10px;border-top:1px solid var(--k-kenar);
    box-shadow:0 80px 0 0 var(--k-yuzey0)}   /* pencerenin alt boşluğunu da örter */
  [class*="st-key-kf_ozet_"] .kf-ozet .kf-sat:not(.kf-buyuk),
  [class*="st-key-kf_ozet_"] .kf-ozet .kf-uyari{display:none}
  [class*="st-key-kf_ozet_"] .kf-ozet{padding:6px 12px;gap:2px;border:0;background:transparent}
  [class*="st-key-kf_ozet_"] .kf-ozet-bas{display:none}
  [class*="st-key-kf_ikincil_"]{display:none}
}
</style>"""

# -*- coding: utf-8 -*-
"""Ekip (Ekim 2026) — programın dijital çalışanları tek yerde, yalnız yöneticiler.

Üst şeritte modül (yalnız yöneticiler). Sekmeler: Çalışanlar (her çalışanın kartı: ne yapar, ne zaman
çalışır, şu anki durumu) ve her çalışanın kendi sayfası:
  Serkan · Bilgi işlem          shared.bt_ekran.sayfa
  Elif · Telegram asistanı      shared.asistan_ekran.telegram_bolumu
  Kerem · Pazar araştırmacısı   shared.asistan_ekran.pazar_bolumu
  Hakan · Gümrük danışmanı      shared.gumruk_ekran.sayfa (İthalat'ta da açık, ithalatçılar kullanır)
İsimler ve görev tanımları shared.ofis.CALISANLAR'da.
"""
import html as _h

import streamlit as st

from shared import bilesen as B
from shared.ofis import CALISANLAR, durumlar

DURUM_RENK = {"calisiyor": "yesil", "sirada": "mavi", "bekliyor": "silik", "kurulum": "amber"}
DURUM_AD = {"calisiyor": "Çalışıyor", "sirada": "İş var", "bekliyor": "Bekliyor", "kurulum": "Kurulum bekliyor"}


def _css():
    return """<style>
.ofis-kart{background:var(--k-yuzey1);border:1px solid color-mix(in srgb,var(--k-metin) 10%,transparent);
  border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:6px;min-height:260px;margin-bottom:6px;box-sizing:border-box}
.ofis-ust{display:flex;align-items:center;gap:10px}
.ofis-ikon{font-family:'Material Symbols Rounded';font-size:22px;width:38px;height:38px;border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  background:color-mix(in srgb,var(--k-mor) 14%,transparent);color:var(--k-mor)}
.ofis-ad{font-weight:600;font-size:16px;color:var(--k-metin);line-height:1.2}
.ofis-unvan{font-size:12px;color:var(--k-silik)}
.ofis-is{font-size:13px;color:var(--k-metin);opacity:.85;line-height:1.4}
.ofis-alt{font-size:12px;color:var(--k-silik);margin-top:auto}
</style>"""


def _kart(c, d):
    cip = B.cip(DURUM_AD[d["durum"]], DURUM_RENK[d["durum"]])
    return (f'<div class="ofis-kart"><div class="ofis-ust"><span class="ofis-ikon">{c["ikon"]}</span>'
            f'<div><div class="ofis-ad">{_h.escape(c["ad"])}</div>'
            f'<div class="ofis-unvan">{_h.escape(c["unvan"])}</div></div></div>'
            f'<div class="ofis-is">{_h.escape(c["is"])}</div>'
            f'<div>{cip}</div>'
            f'<div class="ofis-alt">{_h.escape(d["metin"])} · {_h.escape(c["ne_zaman"])}</div></div>')


def _veri():
    from shared import asistan as A
    try:
        from shared.bt_olcum import raporlar
        bt = raporlar(50)
    except Exception:  # noqa: BLE001
        bt = None
    return bt, A.telegram_haritasi(), A.raporlar(), A.gumruk_sorgulari()


def _git(secenek):
    st.session_state["ekip_sayfa"] = secenek


def _calisanlar():
    B.baslik_eylem("Ekip", "Çalışanlar",
                   aciklama="Programın dijital çalışanları. Her biri kendi işini zamanında yapar, raporunu buraya "
                            "bırakır; rakam değiştiren hiçbir şeyi sana sormadan yapmaz.")
    d = durumlar(*_veri())
    st.markdown(_css(), unsafe_allow_html=True)
    kol = st.columns(len(CALISANLAR))
    for k, c in zip(kol, CALISANLAR):
        k.markdown(_kart(c, d[c["kod"]]), unsafe_allow_html=True)
        k.button("Sayfayı aç", key=f'ekip_git_{c["kod"]}', icon=":material/arrow_forward:", use_container_width=True,
                 on_click=_git, args=(c["ad"],))


def run(kullanici, yonetici):
    """Üst şeritteki Ekip modülü: sekmeler Çalışanlar · Serkan · Elif · Kerem · Hakan (shared/gezinme)."""
    if not yonetici:
        st.error("Bu sayfaya erişim yetkiniz yok.")
        return
    from shared.gezinme import sayfa_menusu, secenekler
    from shared.tasarim import menu_etiketi as _me
    with st.sidebar:
        secim = sayfa_menusu("Bölüm", secenekler("ekip"), modul="ekip", key="ekip_sayfa", format_func=_me)
    c = next((c for c in CALISANLAR if c["ad"] == secim), None)
    if c is None:
        _calisanlar()
        return
    B.baslik_eylem("Ekip", f'{c["ad"]} · {c["unvan"]}', aciklama=f'{c["is"]} {c["ne_zaman"]}.')
    if c["kod"] == "serkan":
        from shared.bt_ekran import sayfa as serkan
        serkan(kullanici, yonetici, baslik=False)
    elif c["kod"] == "elif":
        from shared.asistan_ekran import telegram_bolumu
        telegram_bolumu()
    elif c["kod"] == "kerem":
        from shared.asistan_ekran import pazar_bolumu
        pazar_bolumu()
    else:
        from shared.gumruk_ekran import sayfa as hakan
        hakan(baslik=False)
        st.caption("Hakan'a İthalat › Gümrük danışmanı sayfasından da sorulabilir (ithalat yetkisi olanlar).")

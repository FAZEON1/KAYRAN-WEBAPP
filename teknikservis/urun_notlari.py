# -*- coding: utf-8 -*-
"""Ürün notları (Ekim 2026, teknik servis isteği).

İthalat modeli seçilir, o ürün hakkında not yazılır; notlar herkese açıktır (Teknik servis › Ürün notları).
Arıza eğilimleri, tasarım ve kullanıcı deneyimi gözlemleri, eleştiriler. Tablo: ts_urun_notlari
(veritabani/36_ts_urun_notlari.sql). Tablo kurulmamışsa sayfa bunu söyler, kayıt yapılamaz.
"""
from shared.kayit import sessiz

KONULAR = ["Arıza eğilimi", "Tasarım", "Kullanıcı deneyimi", "Eleştiri / öneri", "Diğer"]
TABLO = "ts_urun_notlari"


def not_satiri(stok_kodu, urun_adi, konu, metin, yazan):
    """Kaydedilecek satır; eksikse (None, hata)."""
    sk, m = str(stok_kodu or "").strip(), str(metin or "").strip()
    if not sk:
        return None, "Önce ürünü (ithalat modeli) seç."
    if len(m) < 3:
        return None, "Not boş olamaz."
    return {"stok_kodu": sk, "urun_adi": str(urun_adi or "").strip(), "konu": str(konu or "").strip(),
            "not_metni": m, "yazan": str(yazan or "").strip()}, ""


def notlari_sirala(satirlar, stok_kodu=None):
    """Seçili ürünün (verilirse) notları, en yeni üstte."""
    from shared.utils import sku_anahtar
    a = sku_anahtar(stok_kodu) if stok_kodu else None
    l = [r for r in satirlar or [] if a is None or sku_anahtar(r.get("stok_kodu")) == a]
    return sorted(l, key=lambda r: str(r.get("olusturma") or ""), reverse=True)


def _client():
    from .database import get_client
    return get_client()


def notlari_oku():
    """Bütün notlar; tablo yoksa None."""
    try:
        r = _client().table(TABLO).select("*").order("olusturma", desc=True).limit(2000).execute()
        return list(r.data or [])
    except Exception as e:  # noqa: BLE001
        sessiz("teknikservis.urun_notlari.notlari_oku", e)
        return None


def not_ekle(satir):
    try:
        _client().table(TABLO).insert(satir).execute()
        return True
    except Exception as e:  # noqa: BLE001
        sessiz("teknikservis.urun_notlari.not_ekle", e)
        return False


def not_sil(not_id):
    try:
        _client().table(TABLO).delete().eq("id", not_id).execute()
        return True
    except Exception as e:  # noqa: BLE001
        sessiz("teknikservis.urun_notlari.not_sil", e)
        return False


def sayfa():
    """Teknik servis › Ürün notları."""
    import html
    import streamlit as st
    from .database import ithalat_model_listesi
    st.markdown("### Ürün notları")
    st.caption("Ürün hakkında tespit ve görüşler: arıza eğilimleri, tasarım, kullanıcı deneyimi, eleştiri. "
               "Notlar herkese açıktır.")
    modeller = ithalat_model_listesi() or []
    secenek = ["— Ürün seç (ithalat modeli · yazarak ara) —"] + [(f"{s} — {a}" if a else s) for s, a in modeller]
    sec = st.selectbox("Ürün", secenek, key="un_urun", label_visibility="collapsed")
    sku = "" if sec == secenek[0] else sec.split(" — ")[0].strip()
    ad = next((a for s, a in modeller if s == sku), "") if sku else ""

    tum = notlari_oku()
    if tum is None:
        st.warning("Ürün notları tablosu henüz kurulmamış (veritabani/36_ts_urun_notlari.sql).")
        return
    if sku:
        with st.form("un_form", clear_on_submit=True, enter_to_submit=False):
            konu = st.selectbox("Konu", KONULAR, key="un_konu")
            metin = st.text_area("Not", key="un_metin", height=120,
                                 placeholder="örn. 34 inç modelde panel sol alt köşede yanık sık görülüyor")
            if st.form_submit_button("Notu ekle", type="primary", icon=":material/note_add:"):
                satir, hata = not_satiri(sku, ad, konu, metin, st.session_state.get("aktif_kullanici", ""))
                if hata:
                    st.error(hata)
                elif not_ekle(satir):
                    st.success("Not eklendi.")
                    st.rerun()
                else:
                    st.error("Not kaydedilemedi.")
    liste = notlari_sirala(tum, sku or None)
    st.caption(f"{len(liste)} not" + (f" · {sku}" if sku else " · bütün ürünler"))
    for r in liste:
        with st.container(border=True):
            st.markdown(
                f"**{html.escape(str(r.get('stok_kodu') or ''))}** · {html.escape(str(r.get('konu') or ''))}"
                f" · <span style='color:var(--k-silik);font-size:12px'>{html.escape(str(r.get('yazan') or '—'))}"
                f" · {str(r.get('olusturma') or '')[:16].replace('T', ' ')}</span>", unsafe_allow_html=True)
            st.markdown(html.escape(str(r.get("not_metni") or "")).replace("\n", "  \n"))
            if (r.get("yazan") or "") == st.session_state.get("aktif_kullanici", "") and r.get("id"):
                if st.button("Sil", key=f"un_sil_{r['id']}", type="tertiary", icon=":material/delete:"):
                    if not_sil(r["id"]):
                        st.rerun()

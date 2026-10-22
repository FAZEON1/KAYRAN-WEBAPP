# -*- coding: utf-8 -*-
"""Toplam Aktifler — Yönetim panosundaki ayrıntı (Ekim 2026). Hesap: kayranacc/toplam_aktif.py.

Muhasebe › Toplam Aktifler sayfası kalktı (kullanıcı, 22.10.2026: "upload edilecek dosya olmadığı için muhasebe
modülünden toplam aktifleri kaldır"). Toplam her Mikro eşitleme turunda kendiliğinden hesaplanır; panodaki pencerenin
altında yalnız Toplam Aktifler yetkisi olanlar şunları görür:
  · Mikro defter kalemlerinin dökümü (hangi Mikro hesabından; "Mikro defter (kasa, avans…)" rakamının kaynağı)
  · Manuel kalemler (Mikro'da olmayan ekleme / çıkarma: ekle, düzelt, sil) — değişince toplam hemen yeniden yazılır
"""
import streamlit as st

from shared.tasarim import tr_sayi


def _usd(v):
    return f"${tr_sayi(v, 2)}"


def yetkili_mi():
    try:
        from kayranacc.main import _toplam_aktifler_yetkilileri
        return str(st.session_state.get("aktif_kullanici", "")).lower().strip() in _toplam_aktifler_yetkilileri()
    except Exception:  # noqa: BLE001
        return False


def _yeniden_hesapla():
    from kayranacc import database as db
    from kayranacc.toplam_aktif import guncelle
    db._cache_temizle()
    try:
        sonuc, _ = guncelle(zorla=True)
        if sonuc["eksik"]:
            return "Kaydedildi; toplam yazılmadı (eksik kaynak: " + ", ".join(sonuc["eksik"]) + ")."
        return f"Kaydedildi · toplam aktifler {_usd(sonuc['toplam'])}"
    except Exception as e:  # noqa: BLE001
        return f"Kaydedildi; toplam bir sonraki eşitleme turunda yenilenecek ({type(e).__name__})."


def _defter(kur, stok_ham):
    from kayranacc import mikro_aktif as M
    from kayranacc.mikro_aktif_ekran import _dokum
    if not M.acik_mi():
        st.caption("Mikro defter kalemleri kapalı.")
        return
    kayit = M.kayitli()
    if not kayit:
        st.caption("Mikro defter kalemleri ilk eşitleme turunda hesaplanacak.")
        return
    ozet = M.usd_ozeti(kayit, kur, stok_ham * M.stok_carpani(True))
    _dokum(kayit, ozet, kur, [])


def _manuel(kalemler, cakisan):
    from kayranacc import database as db
    st.caption("Mikro'da olmayan kalemler. Mikro'dan da gelen bir kalem (kasa, KDV, kargo…) toplama girmez.")
    for k in kalemler:
        kid = k.get("id")
        isaret = "+" if k.get("tip") == "ekle" else "−"
        sembol = "$" if str(k.get("para_birimi") or "USD").upper() == "USD" else "₺"
        c1, c2, c3 = st.columns([8, 1, 1], vertical_alignment="center")
        c1.markdown(f"**{k.get('aciklama') or ''}** · {isaret} {sembol}{tr_sayi(float(k.get('tutar') or 0), 2)}"
                    + (" · *Mikro'dan geliyor, sayılmadı*" if kid in cakisan else ""))
        if c2.button("", key=f"ta_duz_{kid}", icon=":material/edit:", help="Düzelt"):
            st.session_state["_ta_duz"] = kid
        if c3.button("", key=f"ta_sil_{kid}", icon=":material/delete:", help="Sil"):
            db.aktif_manuel_sil(kid)
            st.session_state["_ta_mesaj"] = _yeniden_hesapla()
            st.rerun()
        if st.session_state.get("_ta_duz") == kid:
            _form(k)
    if st.session_state.get("_ta_duz") is None:
        with st.popover("Yeni kalem", icon=":material/add:"):
            _form(None)


def _form(k):
    from kayranacc import database as db
    on = "ta_yeni" if k is None else f"ta_f_{k.get('id')}"
    with st.form(on, border=k is not None):
        a1, a2, a3, a4 = st.columns([1.2, 3, 1.5, 1])
        tip = a1.selectbox("Tip", ["ekle", "cikar"], index=0 if (k or {}).get("tip", "ekle") == "ekle" else 1,
                           format_func=lambda x: "Ekle" if x == "ekle" else "Çıkar")
        ack = a2.text_input("Açıklama", value=(k or {}).get("aciklama") or "")
        tutar = a3.number_input("Tutar", min_value=0.0, step=0.01, format="%.2f",
                                value=float((k or {}).get("tutar") or 0))
        pb = a4.selectbox("Para", ["USD", "TL"],
                          index=0 if str((k or {}).get("para_birimi") or "USD").upper() == "USD" else 1)
        kaydet = st.form_submit_button("Kaydet", type="primary")
    if not kaydet:
        return
    if not ack.strip() or tutar <= 0:
        st.error("Açıklama boş olamaz, tutar 0'dan büyük olmalı.")
        return
    if k is None:
        ok = db.aktif_manuel_ekle("ortak", ack.strip(), tutar, pb, tip)
    else:
        ok = db.aktif_manuel_guncelle(k.get("id"), ack.strip(), tutar, pb, tip)
    st.session_state.pop("_ta_duz", None)
    st.session_state["_ta_mesaj"] = _yeniden_hesapla() if ok else "Kaydedilemedi; kayıt değişmedi."
    st.rerun()


def ayrinti(snap):
    """Yönetim panosunda Toplam aktifler penceresinin altı (yalnız yetkili)."""
    if not yetkili_mi():
        return
    from kayranacc import database as db
    from kayranacc.mikro_aktif import kayitli, manuel_cakisan
    msg = st.session_state.pop("_ta_mesaj", None)
    if msg:
        st.toast(msg)
    kur = float((snap or {}).get("kur") or 0) or float(db.get_kur() or 0)
    carpan = float((snap or {}).get("stok_carpan") or 1.0) or 1.0
    stok_ham = float((snap or {}).get("stok") or 0) / carpan
    with st.expander("Toplam aktifler ayrıntısı · Mikro defter kalemleri ve manuel kalemler", icon=":material/list:"):
        st.caption("Toplam her Mikro eşitleme turunda (15 dakikada bir) kendiliğinden hesaplanır; yükleme yok.")
        st.markdown("##### Manuel kalemler")
        kalemler = db.aktif_manuel_listele("ortak") or []
        try:
            cakisan = manuel_cakisan(kalemler, kayitli())
        except Exception:  # noqa: BLE001
            cakisan = {}
        _manuel(kalemler, cakisan)
        if kur > 0:
            _defter(kur, stok_ham)

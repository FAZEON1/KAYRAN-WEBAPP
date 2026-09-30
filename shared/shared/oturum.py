# -*- coding: utf-8 -*-
"""KAYRAN — Oturum yönetimi (tek kaynak).

NEDEN: Programda 6 ayrı "Çıkış Yap" düğmesi vardı. Yalnız Ana Sayfa'daki
doğru çalışıyordu; modüllerdeki 5 tanesi oturumu sadece EKRANDA kapatıyor,
URL'deki oturum anahtarını yakmıyordu. Sonuç: "çıkış yaptım" diyen kullanıcı
sayfayı yenileyince 7 gün boyunca yeniden içerideydi. Paylaşılan
bilgisayarlarda ciddi bir açık.

ŞİMDİ: Oturum deposu ve çıkış işlemi burada, tek yerde. Bütün düğmeler
cikis_yap()'ı çağırır.
"""
import streamlit as st


def _hata(yer, e, kritik=False):
    """Hata kaydı; hata_log yüklenemezse bile çıkış akışını bozmaz."""
    try:
        from shared.hata_log import kaydet
        kaydet(yer, e, kritik=kritik)
    except Exception as ic:  # kayıt sistemi de çöktüyse en azından logla
        print(f"[oturum] {yer}: {e!r} (hata_log: {ic!r})")


@st.cache_resource
def oturum_store():
    """Sunucu tarafı oturum deposu: {token: {"u", "cihaz", "ts"}}.
    Token URL'de taşınır ama yalnız onu oluşturan tarayıcıda geçerlidir
    (cihaz imzası) — link paylaşımıyla oturum devredilemez."""
    return {}


def oturum_kapat():
    """URL'deki oturum anahtarını sunucu deposundan siler (yakar)."""
    try:
        tok = st.query_params.get("t", "")
        if tok:
            oturum_store().pop(tok, None)
    except Exception as e:
        # Anahtar yakılamadıysa kullanıcı yenileyince içeride kalabilir → kritik.
        _hata("oturum.oturum_kapat", e, kritik=True)


def cikis_yap(yeniden_calistir=True):
    """TAM çıkış: anahtarı yak, URL'yi temizle, oturum bilgilerini sıfırla."""
    oturum_kapat()
    st.session_state.giris_yapildi = False
    st.session_state.aktif_kullanici = ""
    st.session_state["salt_okur"] = False
    st.session_state.aktif_uygulama = "anasayfa"
    try:
        st.query_params.clear()
    except Exception as e:
        _hata("oturum.cikis_yap", e)
    if yeniden_calistir:
        st.rerun()

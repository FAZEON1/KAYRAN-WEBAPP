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


OTURUM_SURESI_SN = 7 * 86400        # kullanılmayan oturum 7 günde düşer (her kullanımda kayar)


def oturum_olustur(kullanici, cihaz):
    """Yeni rastgele oturum anahtarı üretir, depoya cihaz imzasıyla yazar, anahtarı döndürür.
    Anahtar imzalı DEĞİL, tahmin edilemez rastgele değerdir; geçerliliği depodaki kayıttır."""
    import secrets as _sec
    import time as _t
    tok = _sec.token_urlsafe(24)
    oturum_store()[tok] = {"u": kullanici, "cihaz": cihaz, "ts": _t.time()}
    return tok


def oturum_dogrula(tok, cihaz, simdi=None):
    """URL'deki anahtar geçerliyse kullanıcı adını döndürür ve süreyi kaydırır; değilse None.
    Başka tarayıcıdan (cihaz imzası tutmayan) gelen anahtar yakılır — link paylaşımı."""
    import time as _t
    if not tok:
        return None
    _st = oturum_store()
    rec = _st.get(tok)
    simdi = _t.time() if simdi is None else simdi
    if not rec or simdi - rec.get("ts", 0) >= OTURUM_SURESI_SN:
        return None
    if rec.get("cihaz") and cihaz and rec["cihaz"] == cihaz:
        rec["ts"] = simdi            # kaydır: aktif kullanım süreyi tazeler
        return rec["u"]
    _st.pop(tok, None)
    return None


def oturum_anahtari():
    """Oturum işlerinde kullanılacak sunucu sırrı. Sabit/varsayılan değer YOKTUR.
      1. st.secrets["oturum"]["secret"] varsa o,
      2. yoksa Supabase service_role anahtarından HMAC ile türetilmiş değer,
      3. ikisi de yoksa None (çağıran imza gerektiren işi yapmamalı).
    Eskiden public (anon) anahtar, o da yoksa koda yazılı sabit bir metin kullanılıyordu."""
    import hashlib
    import hmac
    try:
        _sec = st.secrets
    except Exception:
        return None
    try:
        _s = str(_sec["oturum"]["secret"] or "").strip()
    except Exception:
        _s = ""
    if _s:
        return _s
    try:
        _srk = str(_sec["supabase"]["service_role_key"] or "").strip()
    except Exception:
        _srk = ""
    if _srk:
        return hmac.new(_srk.encode("utf-8"), b"kayran/oturum-anahtari/v1",
                        hashlib.sha256).hexdigest()
    return None


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

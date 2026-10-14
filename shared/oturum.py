# -*- coding: utf-8 -*-
"""KAYRAN — Oturum yönetimi (tek kaynak).

NEDEN: Programda 6 ayrı "Çıkış Yap" düğmesi vardı. Yalnız Ana Sayfa'daki
doğru çalışıyordu; modüllerdeki 5 tanesi oturumu sadece EKRANDA kapatıyor,
URL'deki oturum anahtarını yakmıyordu. Sonuç: "çıkış yaptım" diyen kullanıcı
sayfayı yenileyince 7 gün boyunca yeniden içerideydi. Paylaşılan
bilgisayarlarda ciddi bir açık.

ŞİMDİ: Oturum deposu ve çıkış işlemi burada, tek yerde. Bütün düğmeler
cikis_yap()'ı çağırır.

KALICI DEPO (Ekim 2026): Oturumlar yalnız sunucu belleğindeydi; Streamlit yeniden başlayınca
(güncelleme, uyku, Reboot) herkes çıkış yapmış oluyordu. Artık her oturum `oturumlar` tablosuna
da yazılır (veritabani/33_oturumlar.sql). Bellek hızlı yol olarak kalır; bellekte olmayan anahtar
(yeniden başlatma sonrası) tablodan okunur. Tabloda anahtarın KENDİSİ değil SHA-256 özeti tutulur:
tablo okunsa bile oturum ele geçirilemez. Tablo yoksa ya da okunamazsa bugünkü gibi yalnız bellek.
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

# ── Kalıcı depo (oturumlar tablosu) ──────────────────────────────────
TABLO = "oturumlar"
_KAYDIRMA_ARALIK_SN = 3600          # kayan süre tabloya en çok saatte bir yazılır (her tıklamada değil)
_YOK_BEKLE_SN = 600                 # tablo yoksa 10 dk tekrar denenmez
_durum = {"yok_ts": 0.0}


def _ozet(tok):
    import hashlib
    return hashlib.sha256(str(tok).encode("utf-8")).hexdigest()


def _db():
    """Yetkili istemci (shared.auth — denetim sarmalayıcısız: oturum kaydı denetim izini doldurmasın).
    Tablo yakın zamanda 'yok' çıktıysa ya da istemci yoksa None."""
    import time as _t
    if _durum["yok_ts"] and _t.time() - _durum["yok_ts"] < _YOK_BEKLE_SN:
        return None
    try:
        from shared.auth import _get_supabase
        return _get_supabase()
    except Exception:
        return None


def _db_hata(yer, e, kritik=False):
    """Tablo kurulmamışsa sessizce bekler (bellek yeterli). Silme hatası KRİTİK: çıkış yapanın
    anahtarı tabloda kalırsa yeniden başlatmadan sonra oturumu geri gelebilir."""
    import time as _t
    m = str(e)
    if "oturumlar" in m and ("does not exist" in m or "PGRST205" in m or "Could not find" in m
                             or "42P01" in m):
        _durum["yok_ts"] = _t.time()
        return
    if kritik:
        _hata(f"oturum.{yer}", e, kritik=True)
        return
    try:
        from shared.kayit import sessiz
        sessiz(f"oturum.{yer}", e)
    except Exception as ic:
        print(f"[oturum] {yer}: {e!r} (kayit: {ic!r})")


def _db_yaz(tok, rec):
    sb = _db()
    if sb is None:
        return
    try:
        sb.table(TABLO).upsert({"tok_ozet": _ozet(tok), "kullanici": rec["u"], "cihaz": rec.get("cihaz") or "",
                                "ts": float(rec["ts"])}, on_conflict="tok_ozet").execute()
        rec["db_ts"] = rec["ts"]
        # süresi dolmuşları ara sıra temizle (yalnız yeni oturumda)
        import time as _t
        sb.table(TABLO).delete().lt("ts", _t.time() - OTURUM_SURESI_SN).execute()
    except Exception as e:
        _db_hata("yaz", e)


def _db_oku(tok):
    sb = _db()
    if sb is None:
        return None
    try:
        r = sb.table(TABLO).select("kullanici,cihaz,ts").eq("tok_ozet", _ozet(tok)).limit(1).execute()
        d = (r.data or [None])[0]
        if not d:
            return None
        return {"u": d.get("kullanici"), "cihaz": d.get("cihaz") or "", "ts": float(d.get("ts") or 0),
                "db_ts": float(d.get("ts") or 0)}
    except Exception as e:
        _db_hata("oku", e)
        return None


def _db_kaydir(tok, rec):
    if rec.get("ts", 0) - rec.get("db_ts", 0) < _KAYDIRMA_ARALIK_SN:
        return
    sb = _db()
    if sb is None:
        return
    try:
        sb.table(TABLO).update({"ts": float(rec["ts"])}).eq("tok_ozet", _ozet(tok)).execute()
        rec["db_ts"] = rec["ts"]
    except Exception as e:
        _db_hata("kaydir", e)


def _db_sil(tok=None, kullanici=None):
    sb = _db()
    if sb is None:
        return
    try:
        q = sb.table(TABLO).delete()
        q = q.eq("tok_ozet", _ozet(tok)) if tok else q.eq("kullanici", kullanici)
        q.execute()
    except Exception as e:
        _db_hata("sil", e, kritik=True)


def kullanici_oturumlarini_sil(kullanici):
    """Kalıcı depodaki bütün oturumlarını siler (hesap pasife alındı / şifre sıfırlandı).
    Bellekteki anahtarlar app.oturumlari_sonlandir'da yakılır."""
    k = str(kullanici or "").strip()
    if k:
        _db_sil(kullanici=k)


def oturum_olustur(kullanici, cihaz):
    """Yeni rastgele oturum anahtarı üretir, depoya cihaz imzasıyla yazar, anahtarı döndürür.
    Anahtar imzalı DEĞİL, tahmin edilemez rastgele değerdir; geçerliliği depodaki kayıttır."""
    import secrets as _sec
    import time as _t
    tok = _sec.token_urlsafe(24)
    rec = {"u": kullanici, "cihaz": cihaz, "ts": _t.time()}
    oturum_store()[tok] = rec
    _db_yaz(tok, rec)
    return tok


def oturum_dogrula(tok, cihaz, simdi=None):
    """URL'deki anahtar geçerliyse kullanıcı adını döndürür ve süreyi kaydırır; değilse None.
    Başka tarayıcıdan (cihaz imzası tutmayan) gelen anahtar yakılır — link paylaşımı."""
    import time as _t
    if not tok:
        return None
    _st = oturum_store()
    rec = _st.get(tok)
    if rec is None:
        rec = _db_oku(tok)           # yeniden başlatma sonrası: bellekte yok, tabloda olabilir
        if rec is not None:
            _st[tok] = rec
    simdi = _t.time() if simdi is None else simdi
    if not rec or simdi - rec.get("ts", 0) >= OTURUM_SURESI_SN:
        return None
    if rec.get("cihaz") and cihaz and rec["cihaz"] == cihaz:
        rec["ts"] = simdi            # kaydır: aktif kullanım süreyi tazeler
        _db_kaydir(tok, rec)
        return rec["u"]
    _st.pop(tok, None)
    _db_sil(tok=tok)                 # başka tarayıcıdan gelen anahtar her iki depoda da yakılır
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
            _db_sil(tok=tok)
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

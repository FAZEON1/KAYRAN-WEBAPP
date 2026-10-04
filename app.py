"""
KAYRAN WORKSPACE — Çatı Uygulama
Sol sidebar navigation ile çoklu uygulama portalı.
Modüller: kayranacc, kayranpm

Mimari:
  Login → Welcome Dashboard (ana sayfa)
  Sidebar: GÖRÜNÜM (Ana Sayfa) · UYGULAMALAR (ACC/PM) · AYARLAR (Çıkış)
  Yetkisiz uygulamalar gri + 🔒 görünür, tıklanamaz
  Hamburger ile sidebar açılır-kapanır
"""
# Bayat modül koruması (shared/modul_tazele.bayatlari_tazele): güncellemeden sonra bellekte eski
# kalan proje modülleri, başka hiçbir şey içe aktarılmadan ÖNCE tazelenir. Kayıt sys üzerinde
# tutulur (proje modülleri silinse de süreç boyunca yaşar).
import sys as _sys_bt, os as _os_bt  # noqa: E401
try:
    from shared.modul_tazele import bayatlari_tazele as _bayatlari_tazele
    if not hasattr(_sys_bt, "_kayran_modul_zaman"):
        _sys_bt._kayran_modul_zaman = {}
    _bayatlari_tazele(_sys_bt.modules, _os_bt.path.dirname(_os_bt.path.abspath(__file__)),
                      _sys_bt._kayran_modul_zaman)
except Exception:  # noqa: BLE001  (koruma hiçbir zaman uygulamayı durdurmaz)
    pass
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
from shared.tasarim import kisi_adi, ikon as k_ikon, MODUL_IKON, MODUL_RENK, rv, mesaj as k_mesaj
import streamlit as st
from datetime import datetime, timedelta
import traceback
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from urllib.parse import quote
from shared.auth import kullanici_dogrula, kullanici_dogrula_v2, sifre_dogrula, sifre_hash_uret, supabase_sifre_kaydet, _get_supabase


# ─────────────────────────────────────────────────────────────────────
# AKILLI CACHE TEMİZLİK (tek dosyalık optimizasyon — modüllere dokunmaz)
#
# SORUN : st.cache_data.clear() TÜM uygulamanın cache'ini siliyordu.
#         Biri satış kaydedince muhasebe/ithalat/ana sayfa dahil herkesin
#         verisi Supabase'den yeniden çekiliyordu.
# ÇÖZÜM : clear() çağrısının HANGİ dosyadan geldiğine bakılır; yalnızca o
#         modülün ve ona bağımlı modüllerin cache'i silinir. Eşleşme
#         olmazsa güvenli eski davranışa (global temizlik) düşülür.
# ─────────────────────────────────────────────────────────────────────
import sys as _sys, os as _os, inspect as _inspect

_CACHE_CLEAR_ORJINAL = st.cache_data.clear

# Klasör → temizlenecek modül grupları (çapraz bağımlılıklar dahil)
_CACHE_GRUPLARI = {
    # ithalat: ürün kartı (urunler) değişince İthalat'ın ürün önbellekleri de (katalog, kategori,
    # barkod haritası, paçal) temizlensin — eskiden kayranpm/satis/depo yazmaları onları atlıyordu.
    "satis":          ("satis", "kayranpm", "ithalat", "shared"),
    "kayranpm":       ("kayranpm", "satis", "depo", "ithalat", "shared"),
    "depo":           ("depo", "kayranpm", "satis", "ithalat", "shared"),
    "ithalat":        ("ithalat", "kayranpm", "satis", "shared"),
    "kayranacc":      ("kayranacc", "satis", "shared"),
    "teknikservis":   ("teknikservis", "shared"),
    "hesap_makinesi": ("hesap_makinesi", "shared"),
    # Kök dosyalar (app.py, gunluk.py, yonetim.py): bildirim/talep/duyuru
    "_kok":           ("__main__", "app", "gunluk", "yonetim", "database",
                       "kayranpm", "shared"),
}


def _grup_cache_sil(gruplar):
    """Verilen modül gruplarındaki @st.cache_data fonksiyonlarını temizler."""
    silinen = 0
    for _mod_adi, _mod in list(_sys.modules.items()):
        if _mod is None:
            continue
        if not any(_mod_adi == g or _mod_adi.startswith(g + ".") for g in gruplar):
            continue
        for _attr in list(vars(_mod).values()):
            if type(_attr).__name__ == "CachedFunc" and hasattr(_attr, "clear"):
                try:
                    _attr.clear()
                    silinen += 1
                except Exception:
                    pass
    return silinen


def _akilli_cache_clear():
    """st.cache_data.clear() yerine geçer: çağıranı bulur, hedefli temizler."""
    try:
        _kok = _os.path.dirname(_os.path.abspath(__file__))
        for _fr in _inspect.stack()[1:8]:
            _dosya = _os.path.abspath(_fr.filename)
            if not _dosya.startswith(_kok) or "streamlit" in _dosya:
                continue
            _rel = _os.path.relpath(_dosya, _kok)
            _parcalar = _rel.split(_os.sep)
            _anahtar = _parcalar[0] if len(_parcalar) > 1 else "_kok"
            _gruplar = _CACHE_GRUPLARI.get(_anahtar)
            if _gruplar and _grup_cache_sil(_gruplar) > 0:
                return
            break  # proje içi ilk kare eşleşmediyse emniyete düş
    except Exception:
        pass
    _CACHE_CLEAR_ORJINAL()  # emniyet ağı: eski global davranış


st.cache_data.clear = _akilli_cache_clear


# ─────────────────────────────────────────────────────────────────────
# OTOMATİK TABLO BİÇİMİ (tek dosyalık optimizasyon — modüllere dokunmaz)
#
# SORUN : 74 st.dataframe çağrısının çoğu ham sayı gösteriyordu —
#         596699.4595 · 36.9231 · 21813. Binlik ayraç yok, para birimi yok,
#         sola yaslı, ve sayısal olmayan biçimlendirme yüzünden sıralama da
#         alfabetik bozuluyordu.
# ÇÖZÜM : st.dataframe sarmalanır; kolon adına göre biçim otomatik verilir.
#         ELLE yazılmış column_config her zaman kazanır (ezilmez), yalnız
#         eksik kolonlar tamamlanır. Native kalan tablolar ve st.data_editor
#         ortak ızgara ayarıyla çizilir (shared/izgara.py; kayıt değerleri aynı).
# ─────────────────────────────────────────────────────────────────────
# TÜM BLOK try İÇİNDE: burada atılan bir istisna uygulamayı TAMAMEN çökertir.
# İlk sürümde `st.dataframe.__self__` yazmıştım; bazı Streamlit sürümlerinde
# st.dataframe bağlı metot DEĞİL, düz fonksiyondur ve __self__ yoktur →
# AttributeError → uygulama hiç açılmaz. Artık varsa kullanılır, yoksa yalnız
# sınıf yaması uygulanır (kolon/konteyner çağrıları zaten onunla kapsanır).
try:
    from streamlit.delta_generator import DeltaGenerator as _DG

    # ÖZYİNELEME KORUMASI — app.py Streamlit'in GİRİŞ BETİĞİ, her etkileşimde
    # baştan çalışır. Koruma olmadan ikinci çalıştırmada _ORIJ_DATAFRAME
    # ZATEN YAMALI fonksiyonu yakalıyor ve _akilli_dataframe kendini
    # çağırıyordu → RecursionError, sayfa hiç açılmıyordu.
    # İşaret fonksiyonun ÜSTÜNDE tutulur: modül yeniden yüklense de kalır.
    if getattr(_DG.dataframe, "_kayran_yamali", False):
        raise RuntimeError("zaten yamalı")   # aşağıdaki except'e düşer, atlanır

    _ORIJ_DATAFRAME = _DG.dataframe

    # Sıralanabilir HTML tabloya çevirmeyi ENGELLEYEN durumlar
    _OZEL_KOLON = ("link", "image", "progress", "bar_chart", "line_chart",
                   "area_chart", "button", "checkbox", "selectbox", "multiselect",
                   "json", "list", "markdown", "audio", "video")

    def _html_uygun_mu(data, kw):
        """Muhafazakâr uygunluk testi. Şüphe varsa native st.dataframe kalır."""
        if kw.get("on_select") or kw.get("key") or kw.get("column_order"):
            return None
        try:
            import pandas as _pd
            # `_pd.io.formats.style.Styler` YAZILAMAZ — alt modül ayrıca içe
            # aktarılmadan AttributeError verir ve try onu yutup TÜM tabloları
            # native'e düşürür. Sınıf adıyla test etmek güvenli.
            if type(data).__name__ == "Styler":
                return None
            if isinstance(data, _pd.DataFrame):
                df = data
            elif isinstance(data, (list, tuple)) and data and isinstance(data[0], dict):
                df = _pd.DataFrame(list(data))
            else:
                return None
            if len(df) == 0 or len(df) > 3000:
                return None
            for v in (kw.get("column_config") or {}).values():
                t = ((v or {}).get("type_config") or {}).get("type")
                if t in _OZEL_KOLON:
                    return None
            # Önce object: sayı sütununda where(..., None) NaN'ı None'a ÇEVİRMİYOR
            # (pandas 2.3 / 3.0) ve boş hücrede "nan" yazıyordu (Happy Life "Fark").
            return df.astype(object).where(_pd.notna(df), None).to_dict("records")
        except Exception:
            return None

    def _akilli_dataframe(self, data=None, *a, **kw):
        """st.dataframe / kolon.dataframe yerine geçer.

        KISA ve salt-okur tablolar → sıralanabilir HTML (tasarım kontrolü bizde).
        UZUN, seçimli ya da özel kolonlu tablolar → native st.dataframe.
        Her iki yolda da sayı biçimleri otomatik tamamlanır.
        """
        try:
            from shared.tasarim import otomatik_kolonlar, tablo_sirali
            kayitlar = _html_uygun_mu(data, kw)
            if kayitlar is not None:
                tablo_sirali(kayitlar, kap=self)
                return None
            from shared.tasarim import IZGARA_YENI
            if IZGARA_YENI:          # ortak ızgara ayarı (shared/izgara.py)
                from shared.izgara import dataframe_hazirla
                dataframe_hazirla(data, kw)
            else:
                kw["column_config"] = otomatik_kolonlar(data, kw.get("column_config"))
        except Exception:
            pass          # biçimlendirme/çeviri başarısızsa tablo yine çizilsin
        return _ORIJ_DATAFRAME(self, data, *a, **kw)

    _akilli_dataframe._kayran_yamali = True      # ikinci kez yamalanmasın
    _DG.dataframe = _akilli_dataframe

    # Modül seviyesindeki st.dataframe'i yeniden bağla — ancak bağlı metotsa.
    _kok_dg = getattr(st.dataframe, "__self__", None)
    if _kok_dg is not None:
        st.dataframe = _akilli_dataframe.__get__(_kok_dg, _DG)
except Exception:
    pass          # zaten yamalıysa ya da kurulamazsa: tablolar çalışmaya devam

# Emoji → çizgi ikon (mesaj, pencere, sekme, açılır bölüm, düğme). Geri alma:
# shared/tasarim.py → IKON_YENI = False. Modüller içe aktarılmadan ÖNCE kurulmalı.
from shared.ikon import kur as _ikon_kur
_ikon_kur(st)
# Düzenlenebilir tablolar (st.data_editor) ortak ızgara ayarıyla. Geri alma: IZGARA_YENI = False.
from shared.izgara import kur as _izgara_kur
_izgara_kur(st)


# ─────────────────────────────────────────────────────────────────────
# HAFİF SAYIM SORGULARI (ana sayfa rozetleri)
#
# SORUN : Ana sayfa, sadece bir SAYI göstermek için tüm tabloyu indiriyordu
#         (ithalat_dosyalari 1000'er sayfalanarak, ts_kayitlar tamamı...).
# ÇÖZÜM : count="exact", head=True → Postgres sayıyı döner, TEK SATIR bile
#         indirilmez. Hata olursa eski yönteme düşülür (rozet kaybolmaz).
# ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _hizli_sayim(tablo: str, kolon: str = None, degerler=None):
    """Satır indirmeden COUNT döner. Başarısızsa None (çağıran eski yola düşer)."""
    try:
        sb = _get_supabase()
        if not sb:
            return None
        q = sb.table(tablo).select("id", count="exact", head=True)
        if kolon and degerler:
            q = q.in_(kolon, list(degerler))
        return q.execute().count
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────
# YETKİ TANIMLARI
# ─────────────────────────────────────────────────────────────────────
KAYRANACC_KULLANICILAR = {"ibrahim", "derman", "cem", "pamuk", "serkan", "yilmaz", "korkut", "caglar",
                          "serdar"}
KAYRANPM_KULLANICILAR  = {"ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"}
HESAP_MAKINESI_KULLANICILAR = {"ibrahim"}
ITHALAT_KULLANICILAR = {"ibrahim", "kemal", "serkan", "derya", "gokhan", "korkut", "caglar", "cem", "pamuk",
                        "serdar"}
TEKNIKSERVIS_KULLANICILAR = {"ibrahim", "berkay", "gokhan", "cem", "pamuk", "derya", "samet", "serkan", "korkut",
                             "serdar"}
SATIS_KULLANICILAR = {"ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"}
DEPO_KULLANICILAR = KAYRANPM_KULLANICILAR | {"samet", "berkay", "selcuk", "serdar"}
YONETIM_KULLANICILAR = {"ibrahim", "korkut", "serkan", "caglar", "cem"}
# Patron Panosu — sabah kokpiti YALNIZCA bu kullanıcı(lar)a render edilir.
# Başka biri girince blok kodu hiç çalışmaz, DOM'a inmez.
PATRON_PANEL_KULLANICILAR = {"ibrahim"}

# ── SALT-OKUR (read-only) KULLANICILAR ───────────────────────────────
# Bu kullanicilar TUM modulleri gorur ama hicbir veriyi degistiremez.
# Yazma engeli tek noktada: shared/audit.py -> wrap_client proxy'si.
SALT_OKUR_KULLANICILAR = {"ahmet"}

# Salt-okur kullanicilar butun modul setlerine otomatik eklenir
# (tek tek listeye yazmaya gerek yok; yeni modul eklenince de calisir).
for _k in SALT_OKUR_KULLANICILAR:
    for _set in (KAYRANACC_KULLANICILAR, KAYRANPM_KULLANICILAR, HESAP_MAKINESI_KULLANICILAR,
                 ITHALAT_KULLANICILAR, TEKNIKSERVIS_KULLANICILAR, SATIS_KULLANICILAR,
                 DEPO_KULLANICILAR, YONETIM_KULLANICILAR):
        _set.add(_k)


# Kullanıcı Yönetimi ekranını görebilenler (DB yoksa geçerli sabit liste)
KULLANICI_YONETIMI_KULLANICILAR = {"ibrahim"}


def salt_okur_mu(kullanici):
    """DB'de tanımlıysa oradan, değilse sabit listeden (bkz. shared/yetki.py)."""
    try:
        from shared.yetki import salt_okur as _so
        return _so(kullanici, SALT_OKUR_KULLANICILAR)
    except Exception:
        return (kullanici or "").lower().strip() in SALT_OKUR_KULLANICILAR

DUYURU_AKTIF = False
DUYURU_METNI = ""


def _statik_yetkiler(kullanici):
    """Koddaki SABİT listelerden yetki — veritabanı yoksa/okunamazsa kullanılır.
    Bu listeler artık yalnız GÜVENLİK AĞI; asıl kaynak 'kullanici_yetkileri'
    tablosu ve 👥 Kullanıcı Yönetimi ekranı."""
    k = (kullanici or "").lower().strip()
    return {
        "kayranacc": k in KAYRANACC_KULLANICILAR,
        "kayranpm":  k in KAYRANPM_KULLANICILAR,
        "depo":      k in DEPO_KULLANICILAR,
        "hesap_makinesi": k in HESAP_MAKINESI_KULLANICILAR,
        "ithalat": k in ITHALAT_KULLANICILAR,
        "teknikservis": k in TEKNIKSERVIS_KULLANICILAR,
        "satis": k in SATIS_KULLANICILAR,
    }


def kullanici_yetkileri(kullanici):
    """Modül yetkileri. Kaynak: Supabase 'kullanici_yetkileri' tablosu.
    Tablo yoksa/okunamazsa _statik_yetkiler'e düşer — kimse kilitlenmez."""
    try:
        from shared.yetki import moduller as _mod
        return _mod(kullanici, _statik_yetkiler(kullanici))
    except Exception:
        return _statik_yetkiler(kullanici)


def _ozel_statik():
    return {"yonetim": YONETIM_KULLANICILAR,
            "patron_panel": PATRON_PANEL_KULLANICILAR,
            "talep_yonetici": TALEP_YONETICILERI,
            "kullanici_yonetimi": KULLANICI_YONETIMI_KULLANICILAR}


def ozel_yetki(kullanici, ad):
    """Özel yetki (yonetim / patron_panel / talep_yonetici / kullanici_yonetimi)."""
    statik = _ozel_statik().get(ad, set())
    try:
        from shared.yetki import ozel_yetki as _oy
        return _oy(kullanici, ad, statik)
    except Exception:
        return (kullanici or "").lower().strip() in statik


def talep_yoneticileri():
    try:
        from shared.yetki import ozel_sahipleri
        return ozel_sahipleri("talep_yonetici", TALEP_YONETICILERI)
    except Exception:
        return set(TALEP_YONETICILERI)


def tum_kullanicilar():
    """Aktif kullanıcılar (bildirim alıcı listesi vb.)."""
    _statik = set().union(KAYRANACC_KULLANICILAR, KAYRANPM_KULLANICILAR, ITHALAT_KULLANICILAR,
                          TEKNIKSERVIS_KULLANICILAR, SATIS_KULLANICILAR, DEPO_KULLANICILAR,
                          HESAP_MAKINESI_KULLANICILAR)
    try:
        from shared.yetki import aktif_kullanicilar
        return aktif_kullanicilar(_statik)
    except Exception:
        return _statik


# ─────────────────────────────────────────────────────────────────────
# TALEP / GERİ BİLDİRİM — Mail gönderimi
# ─────────────────────────────────────────────────────────────────────
TALEP_ALICI = "ibrahim.kayran@g5fteknoloji.com"   # hiçbir talep yöneticisinin adresi yoksa yedek alıcı

# ─────────────────────────────────────────────────────────────────────
# ONLINE KULLANICI TAKİP
def _sayfaya_git(mod):
    """Düğme on_click'i: hedef sayfayı oturuma yazar. Streamlit bunu betik
    çalışmadan önce çağırır, sayfa tek seferde doğru çizilir (st.rerun yok)."""
    st.session_state.aktif_uygulama = mod


@st.cache_data(ttl=60, show_spinner=False)
def get_son_girisler():
    """{kullanici: son_aktivite} — Yönetici araçları paneli için (60 sn önbellekli)."""
    try:
        sb = _get_supabase()
        if not sb:
            return {}
        res = sb.table("kullanici_durum").select("kullanici_adi, son_aktivite").execute()
        return {r["kullanici_adi"]: r["son_aktivite"] for r in (res.data or [])}
    except Exception as e:
        from shared.hata_log import kaydet as _hk
        _hk("anasayfa.son_girisler", e)
        return {}


# ─────────────────────────────────────────────────────────────────────
def online_durum_guncelle(kullanici_adi: str):
    """Kullanıcının son aktivite zamanını Supabase'e kaydeder (en fazla 60 sn'de bir)."""
    try:
        import time as _t
        if _t.time() - st.session_state.get("_son_online_upsert", 0) < 60:
            return
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return
        sb.table("kullanici_durum").upsert({
            "kullanici_adi": kullanici_adi,
            "son_aktivite": _dt.datetime.utcnow().isoformat(),
        }, on_conflict="kullanici_adi").execute()
        st.session_state["_son_online_upsert"] = _t.time()
    except Exception:
        pass

@st.cache_data(ttl=60, show_spinner=False)
def get_online_kullanicilar():
    """Son 180 dk içinde aktif kullanıcılar (60 sn önbellekli — her tıklamada sorgu atmaz)."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return []
        bitis = _dt.datetime.utcnow()
        baslangic = bitis - _dt.timedelta(minutes=180)
        res = sb.table("kullanici_durum").select("kullanici_adi, son_aktivite").gte("son_aktivite", baslangic.isoformat()).execute()
        return res.data if res.data else []
    except Exception:
        return []

# ─────────────────────────────────────────────────────────────────────
# GÜNLÜK GİRİŞ / SERİ / LİDERLİK
# ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────
# DUYURU YÖNETİMİ — Supabase'den oku / yaz
# ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def get_duyuru():
    """sistem_ayarlari tablosundan duyuru aktif/metin bilgisini döner."""
    try:
        sb = _get_supabase()
        if not sb:
            return False, ""
        res = sb.table("sistem_ayarlari").select("anahtar, deger").in_("anahtar", ["duyuru_aktif", "duyuru_metni"]).execute()
        d = {r["anahtar"]: r["deger"] for r in (res.data or [])}
        aktif = d.get("duyuru_aktif", "false") == "true"
        metni = d.get("duyuru_metni", "")
        return aktif, metni
    except Exception:
        return False, ""

def set_duyuru(aktif: bool, metni: str):
    """sistem_ayarlari tablosuna duyuru durumu yazar."""
    try:
        import datetime as _dt
        sb = _get_supabase()
        if not sb:
            return False
        now = _dt.datetime.utcnow().isoformat()
        sb.table("sistem_ayarlari").upsert({"anahtar": "duyuru_aktif", "deger": "true" if aktif else "false", "guncelleme_tarihi": now}, on_conflict="anahtar").execute()
        sb.table("sistem_ayarlari").upsert({"anahtar": "duyuru_metni", "deger": metni, "guncelleme_tarihi": now}, on_conflict="anahtar").execute()
        try:
            get_duyuru.clear()
        except Exception:
            pass
        return True
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────────────
# BİLDİRİM SİSTEMİ — Gönder / Oku / Okundu işaretle
# ─────────────────────────────────────────────────────────────────────
def bildirim_gonder(alici: str, mesaj: str):
    """Ibrahim'den belirtilen alıcıya bildirim gönderir."""
    try:
        sb = _get_supabase()
        if not sb:
            return False
        sb.table("bildirimler").insert({"gonderen": "ibrahim", "alici": alici, "mesaj": mesaj, "okundu": False}).execute()
        return True
    except Exception:
        return False

def bildirim_gonder_herkese(mesaj: str, kullanici_listesi: list):
    """Tüm kullanıcılara aynı mesajı gönderir (ibrahim hariç)."""
    try:
        sb = _get_supabase()
        if not sb:
            return False
        rows = [{"gonderen": "ibrahim", "alici": k, "mesaj": mesaj, "okundu": False} for k in kullanici_listesi if k.lower() != "ibrahim"]
        if rows:
            sb.table("bildirimler").insert(rows).execute()
        return True
    except Exception:
        return False

@st.cache_data(ttl=20, show_spinner=False)
def get_okunmamis_bildirimler(kullanici_adi: str):
    """Kullanıcının okunmamış bildirimlerini döner."""
    try:
        sb = _get_supabase()
        if not sb:
            return []
        res = sb.table("bildirimler").select("*").eq("alici", kullanici_adi).eq("okundu", False).order("olusturma_tarihi", desc=True).execute()
        return res.data if res.data else []
    except Exception:
        return []

def tumunu_okundu_isaretle(kullanici_adi: str):
    """Kullanıcının tüm bildirimlerini okundu yap."""
    try:
        sb = _get_supabase()
        if not sb:
            return
        sb.table("bildirimler").update({"okundu": True}).eq("alici", kullanici_adi).eq("okundu", False).execute()
    except Exception:
        pass
    try:
        get_okunmamis_bildirimler.clear()
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────
# GÖREV ATAMA VE TAKİP SİSTEMİ
# ─────────────────────────────────────────────────────────────────────
# ── Talep Merkezi sabitleri ──────────────────────────────────────────
# Gelen talepleri görebilen ve cevaplayabilen kullanıcılar (küçük harf).
TALEP_YONETICILERI = {"ibrahim"}

TALEP_KATEGORILERI = ["🐞 Hata bildirimi", "✨ Yeni özellik", "⚡ İyileştirme",
                      "❓ Soru / destek", "📊 Rapor talebi", "🔧 Diğer"]


# Talep e-postaları shared/eposta.py'de (Ekim 2026). Eskiden burada talep_gonder()
# vardı ama HİÇ çağrılmıyordu — yeni talepte kimseye mail gitmiyordu.


# ─────────────────────────────────────────────────────────────────────
# Sayfa ayarları
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KAYRAN | Workspace",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="auto",          # telefonda kapalı, bilgisayarda açık
)

# ══════════════════════════════════════════════════════════════════════
# AÇILIŞ SAĞLIK KONTROLÜ — "Oh no." beyaz ekranına karşı
# Streamlit Cloud, uygulama bir süre kullanılmayınca (örn. hafta sonu)
# uykuya alır. Uyanışta önbellekteki Supabase bağlantısı ölü olabiliyor ya
# da ağ geç geliyor; ilk sorgu patlayınca uygulama açılışta çöküyordu.
# Burada bağlantı canlılığı sınanır; ölüyse otomatik yeniden kurulur.
# Onarılamazsa kullanıcıya beyaz ekran yerine anlaşılır bir mesaj + buton.
# ══════════════════════════════════════════════════════════════════════
if not st.session_state.get("_db_saglik_ok"):
    try:
        from kayranpm.database import db_saglik_kontrol as _db_saglik
        _ok, _mesaj = _db_saglik()
    except Exception:
        # Kontrolün KENDİSİ patlarsa uygulamayı kilitleme — aç, hata varsa
        # ilgili ekranda görünsün (fail-open).
        _ok, _mesaj = True, ""
    if _ok:
        st.session_state["_db_saglik_ok"] = True
    else:
        st.markdown(
            '<div style="max-width:640px;margin:80px auto;padding:28px 32px;'
            'background:var(--k-yuzey3);border:1px solid var(--k-kenar2);border-radius:14px;'
            'font-family:Inter,sans-serif;color:var(--k-metin)">'
            '<div style="font-size:23px;margin-bottom:10px">🔌</div>'
            '<div style="font-size:19px;font-weight:700;margin-bottom:8px">'
            'Veritabanına bağlanılamadı</div>'
            '<div style="color:var(--k-soluk);line-height:1.6;margin-bottom:6px">'
            'Uygulama bir süre kullanılmadığında uyku moduna geçer; uyanırken '
            'bağlantı bazen geç kurulur. Genellikle birkaç saniye sonra '
            '<b>Yeniden Dene</b> demek yeterlidir.</div>'
            f'<div style="color:var(--k-silik);font-size:13px;font-family:monospace;'
            f'margin-top:10px">{_mesaj}</div></div>',
            unsafe_allow_html=True,
        )
        _c1, _c2, _c3 = st.columns([1, 1, 1])
        if _c2.button("Yeniden Dene", type="primary", use_container_width=True, icon=":material/refresh:"):
            try:
                from kayranpm.database import db_yeniden_baglan as _yb
                _yb()
            except Exception:
                pass
            st.session_state.pop("_db_saglik_ok", None)
            st.rerun()
        st.stop()

# ── Global işlem göstergesi: her işlemde üstte progress bar + "İşleniyor" kapsülü ──
from shared.tasarim import cekirdek_css, islem_gosterge_css
from shared.tasarim import genel_tema_css
# token_css() kaldırıldı — CSS değişkenlerini cekirdek_css() basıyor.

# ── GLOBAL PLOTLY TEMASI: tüm modüllerdeki grafikler bu görünümü miras alır ──
# (şeffaf zemin, Inter, yumuşak grid, alt yatay lejant, uygulama hover kutusu)
@st.cache_resource(show_spinner=False)
def _kayran_plotly_tema():
    """Global grafik teması — süreç başına bir kez kaydolur."""
    import plotly.io as _pio
    import plotly.graph_objects as _pgo
    _pio.templates["kayran"] = _pgo.layout.Template(layout=dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=trenk("metin"), size=12),
        colorway=[trenk("mor"), trenk("yesil"), trenk("amber"), trenk("cyan"),
                  trenk("pembe"), trenk("mor"), trenk("amber"), trenk("mavi")],
        xaxis=dict(gridcolor="rgba(148,163,184,0.10)",
                   linecolor="rgba(148,163,184,0.18)", zerolinecolor="rgba(148,163,184,0.22)"),
        yaxis=dict(gridcolor="rgba(148,163,184,0.10)",
                   linecolor="rgba(148,163,184,0.18)", zerolinecolor="rgba(148,163,184,0.22)"),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=trenk("mor2"))),
        hoverlabel=dict(bgcolor=trenk("yuzey2"), bordercolor="rgba(129,140,248,0.4)",
                        font=dict(family="Inter, sans-serif", color=trenk("mavi"))),
        margin=dict(t=24, b=8, l=8, r=8),
    ))
    _pio.templates.default = "plotly_dark+kayran"
    return True

try:
    _kayran_plotly_tema()
except Exception:
    pass

# ── Grafiklerde Türkçe sayı ayracı ──────────────────────────────────
# Plotly varsayılanı İngilizce: eksende "1.5M", etikette "1,234,567.8".
# separators=",." → "1,5M" ve "1.234.567,8". Tek ayar, bütün grafikler
# (Streamlit'in grafik teması bu ayarı ezmiyor — tarayıcıda doğrulandı).
try:
    import plotly.io as _pio
    import plotly.graph_objects as _pgo
    if "kayran_tr" not in _pio.templates:
        _pio.templates["kayran_tr"] = _pgo.layout.Template(layout={"separators": ",."})
        _pio.templates.default = _pio.templates.default + "+kayran_tr"
except Exception as _pe:  # plotly yoksa grafik de yoktur; kaydet, devam et
    try:
        from shared.hata_log import kaydet as _hk
        _hk("app.plotly_tr", _pe)
    except Exception:
        print("[app] plotly TR ayracı kurulamadı:", _pe)

# Plotly araç çubuğunu (modebar) program genelinde gizle — temiz görünüm
st.markdown(
    "<style>"
    ".modebar{display:none !important;}"
    # Material ikonları: hiçbir font zorlaması ikon fontunu ezemesin.
    # (Sidebar buton span'lerine Inter dayatan kurallar ikon ligatürünü
    #  düz metne çeviriyordu — 'logout' yazısı olayı. Bileşik seçici,
    #  o kuralların özgüllüğünü aşar.)
    'section[data-testid="stSidebar"] .stButton > button span[data-testid="stIconMaterial"],'
    'section[data-testid="stSidebar"] [data-testid="stIconMaterial"],'
    '[data-testid="stIconMaterial"],'
    # Menü/etiket içindeki :material/..: ikonları (st.radio format_func=menu_etiketi).
    # Muhasebe'nin 'section[data-testid=stSidebar] *{font-family:Inter !important}'
    # kuralı bunları ezip ikon yerine 'dashboard' gibi DÜZ METİN gösteriyordu.
    # 'html body' + öznitelikler o kuraldan daha özgül → her modülde ikon kalır.
    'html body span[translate="no"][aria-label$=" icon"],'
    'html body section[data-testid="stSidebar"] span[translate="no"][aria-label$=" icon"]{'
    'font-family:"Material Symbols Rounded" !important;'
    'font-weight:normal !important;'
    'letter-spacing:normal !important;'
    'text-transform:none !important;'
    'line-height:1 !important;'
    '}'
    # Açılır listeler (selectbox/multiselect) PENCERENİN ÜSTÜNDE açılsın.
    # (BaseWeb popover'ı body'ye portal olarak çizilir; katmanı dialog'un
    #  altında kalırsa seçenekler arka planda kalır ve tıklanamaz.)
    'div[data-baseweb="popover"], div[data-baseweb="select"] ~ div,'
    'ul[data-testid="stSelectboxVirtualDropdown"], [data-baseweb="menu"]{'
    'z-index:2147483000 !important;'
    '}'
    # Pencere (st.dialog) açıkken kenar çubuğu aç/kapat düğmesi görünmesin. Betik de gizler
    # (dialogAcik); bu kural betik eskimiş/çalışmıyor olsa bile geçerli.
    'body:has(div[data-testid="stDialog"]) #kayran-sb-toggle{display:none !important;}'
    "</style>", unsafe_allow_html=True)
st.markdown(cekirdek_css(), unsafe_allow_html=True)      # TEK tasarım kaynağı (aktif temayla)
_css_tema = st.session_state.get("tema") or "koyu"      # oturum yüklenince farklıysa rerun (aşağıda)
st.markdown(islem_gosterge_css(), unsafe_allow_html=True)
from shared.islem import kur as _islem_kur              # yükleniyor / işlem sürüyor kapsülü (Ekim 2026)
_islem_kur()
from shared.ceviri import kur as _ceviri_kur            # Streamlit'in İngilizce kalıp yazıları → Türkçe
_ceviri_kur()
from shared.ipucu import kur as _ipucu_kur              # tıklamadan sonra takılı kalan ipucu kutuları
_ipucu_kur()
st.markdown(genel_tema_css(), unsafe_allow_html=True)
# Sayfa genişliği TEK yerden — modül başına farklı max-width, modüller arası
# geçişte sayfanın gözle görülür şekilde daralmasına yol açıyordu.
st.markdown("<style>.stApp [data-testid='stMainBlockContainer'],"
            ".stApp .block-container{max-width:1440px !important;}</style>",
            unsafe_allow_html=True)

# ── Mobil uyum: shared/tasarim.py → MOBIL_CSS (cekirdek_css içinde, TEK yer).
#    Eski dağınık kurallar oraya taşındı; tablo yazısını 11px'e küçülten
#    kural kaldırıldı (telefonda okunmuyordu).

# ── SIDEBAR AÇ/KAPAT + tema temizliği: TEK enjekte script ───────────────────
# PERFORMANS TASARIMI: sürekli zamanlayıcı YOK. Konum yalnız gerçek olaylarda
# hesaplanır (ResizeObserver sidebar boyutu değişince, pencere resize, tık).
# getBoundingClientRect asla periyodik çağrılmaz → zorla-reflow maliyeti sıfır.
# Dialog algısı: childList MutationObserver + rAF birleştirme; tüm yazımlar
# yalnız değer değişince (döngü yapısal olarak imkânsız).
import streamlit.components.v1 as _sb_comp
_sb_comp.html(
    """
<script>
(function () {
  const w = window.parent, doc = w.document;

  // ── Sayfa dili: Türkçe ──
  // Streamlit <html lang="en"> basıyor. Tarayıcı büyük harfe çevirirken
  // (text-transform:uppercase — 140+ yerde) İngilizce kuralı uyguluyordu:
  // "Gecikmiş" → "GECIKMIŞ", "İthalat" etiketleri noktasız I. lang="tr" ile
  // i→İ, ı→I doğru çevrilir; ekran okuyucu da Türkçe okur.
  try { if (doc.documentElement.lang !== "tr") doc.documentElement.lang = "tr"; } catch (e) {}

  // ── Tablo sayıları: Türkçe ──
  // st.dataframe'in "localized"/"dollar" sütunları tarayıcının DİLİNE göre
  // biçimlenir (navigator.languages). İngilizce kurulu bir bilgisayarda
  // "1,234.56" çıkıyordu. Programın dili Türkçe olduğu için tablo sayıları
  // her bilgisayarda "1.234,56" olsun. Yalnız dil LİSTESİNİN başına tr-TR
  // eklenir; tarayıcının kendisi ya da başka siteler etkilenmez.
  try {
    const dl = Array.from(w.navigator.languages || []);
    if (!dl.length || !String(dl[0]).toLowerCase().startsWith("tr")) {
      Object.defineProperty(w.navigator, "languages",
        { get: () => ["tr-TR", "tr"].concat(dl), configurable: true });
    }
  } catch (e) {}

  // ── Klavye kısayolu: Ctrl+K (Mac'te ⌘K) ya da "/" → aramaya atla ──
  // Her sayfadan çalışır: arama kutusu ekrandaysa ona odaklanır, değilse üst
  // menüdeki "Arama" sekmesini açar ve kutu belirince imleci içine koyar.
  // "/" yalnız bir kutuya YAZMIYORKEN çalışır (yazılan metne karışmasın).
  // Dinleyici sayfa başına BİR kez kurulur; her basışta güncel DOM'a bakar.
  try {
    if (!w.__kayranKisayol) {
      w.__kayranKisayol = true;
      const kutu = () => doc.querySelector('[class*="st-key-global_arama_"] input');
      const odakla = (n) => {
        const i = kutu();
        if (i) { i.focus(); try { i.select(); } catch (e) {} return; }
        if (n > 0) w.setTimeout(() => odakla(n - 1), 120);
      };
      doc.addEventListener("keydown", (e) => {
        const a = doc.activeElement, t = ((a && a.tagName) || "").toUpperCase();
        const yaziyor = t === "INPUT" || t === "TEXTAREA" || (a && a.isContentEditable);
        const ctrlK = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === "k" || e.key === "K");
        const egik = e.key === "/" && !yaziyor && !e.ctrlKey && !e.metaKey && !e.altKey;
        if (!ctrlK && !egik) return;
        e.preventDefault();
        // Komut paleti varsa onu aç (shared/palet.py); yoksa eski arama kutusu
        if (w.__kayranPaletAc) { w.__kayranPaletAc(); return; }
        if (kutu()) { odakla(0); return; }
        const d = doc.querySelector(".st-key-top_arama button");
        if (d) { d.click(); odakla(25); }
      }, true);
    }
  } catch (e) {}

  // Düğme zaten varsa (her rerun bu betik yeniden çalışır): ÇIKMADAN önce
  // güncel menüye yeniden bağlan + konumla. Eskiden burada yalnız `return` vardı;
  // menü yeniden kurulduğunda izleyiciler eski (sayfadan kalkmış) menüde kalıyor,
  // düğme yanlış yerde (menünün üstünde) takılı kalıyordu.
  if (doc.getElementById('kayran-sb-toggle')) {
    try { if (w.__kayranSbYenile) w.__kayranSbYenile(); } catch (e) {}
    return;
  }

  const SVG_SOL = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>';
  const SVG_SAG = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';

  const btn = doc.createElement('button');
  btn.id = 'kayran-sb-toggle';
  btn.type = 'button';
  btn.setAttribute('aria-label', 'Menüyü aç/kapat');
  // Görünüm: sade, temaya uygun (eskiden parlak sarı halka). KAYMA ANİMASYONU
  // YOK: konum değişince doğrudan yerine oturur (eskiden 'left' kayıyordu).
  btn.style.cssText = [
    'position:fixed','top:50%','transform:translateY(-50%)','left:10px',
    'z-index:2147483647','width:26px','height:26px','border-radius:50%',
    'cursor:pointer','border:1px solid var(--k-kenar2,rgba(148,163,184,.18))',
    'background:var(--k-yuzey1,#0F172A)','color:var(--k-soluk,#94A3B8)',
    'padding:0','display:flex','align-items:center','justify-content:center',
    'box-shadow:0 1px 3px rgba(0,0,0,0.18)',
    'transition:color .12s ease, border-color .12s ease, box-shadow .12s ease'
  ].join(';');
  btn.innerHTML = SVG_SOL;
  btn.dataset.yon = 'sol';
  btn.title = 'Menüyü daralt / genişlet';
  btn.onmouseenter = () => {
    btn.style.color = 'var(--k-mor,#818CF8)';
    btn.style.borderColor = 'var(--k-mor,#818CF8)';
    btn.style.boxShadow = '0 0 0 3px color-mix(in srgb,var(--k-mor,#818CF8) 18%,transparent)';
  };
  btn.onmouseleave = () => {
    btn.style.color = 'var(--k-soluk,#94A3B8)';
    btn.style.borderColor = 'var(--k-kenar2,rgba(148,163,184,.18))';
    btn.style.boxShadow = '0 1px 3px rgba(0,0,0,0.18)';
  };

  function sbEl() { return doc.querySelector('section[data-testid="stSidebar"]'); }

  // TEK DOĞRULUK KAYNAĞI = EKRANDAKİ GERÇEK: sınıf/kayıt değil, ölçülen genişlik.
  function gorunurMu() {
    const sb = sbEl();
    return !!sb && sb.getBoundingClientRect().width > 40;
  }

  const KAPAT_OZ = [['width','0'], ['min-width','0'], ['flex','0 0 0px'],
                    ['overflow','hidden'], ['border-right','none']];
  // KURAL: kapsayıcıya ASLA yazılmaz (tüm sayfayı yok eder — yaşandı).
  function zorlaKapat(sb) {
    for (const [p, v] of KAPAT_OZ) sb.style.setProperty(p, v, 'important');
  }
  function inlineTemizle(sb) {
    for (const [p] of KAPAT_OZ) sb.style.removeProperty(p);
    sb.style.removeProperty('display');
    sb.style.removeProperty('transform');
    sb.style.removeProperty('visibility');
  }
  // Streamlit'in KENDİ kapalı durumunu açmak için native genişletme kontrolleri
  function nativeAc() {
    const sels = ['[data-testid="stExpandSidebarButton"]',
                  '[data-testid="stSidebarCollapsedControl"] button',
                  '[data-testid="stSidebarCollapsedControl"]',
                  '[data-testid="collapsedControl"] button',
                  '[data-testid="collapsedControl"]'];
    for (const s of sels) {
      const el = doc.querySelector(s);
      if (el) { try { el.click(); return true; } catch (e) {} }
    }
    return false;
  }
  // Son çare: section'ı satır-içi important ile görünür kıl (yalnız section!)
  function zorlaAc(sb) {
    const gw = w.__kayranSbW || '246px';
    sb.style.setProperty('display', 'flex', 'important');
    sb.style.setProperty('visibility', 'visible', 'important');
    sb.style.setProperty('transform', 'none', 'important');
    sb.style.setProperty('width', gw, 'important');
    sb.style.setProperty('min-width', gw, 'important');
    sb.style.setProperty('overflow', 'visible', 'important');
  }

  function konumla() {
    try {
      const sb = sbEl();
      // Menünün HİÇ olmadığı sayfa (Streamlit boş sidebar'ı kaldırır): düğme işe
      // yaramaz → gizle. Dialog açıkken de gizli (dialogAcik).
      const gizle = !sb || dialogAcik();
      const hedefD = gizle ? 'none' : 'flex';
      if (btn.style.display !== hedefD) btn.style.display = hedefD;
      if (gizle) return;
      const acik = gorunurMu();
      const hedefLeft = acik
        ? Math.max(10, Math.round(sb.getBoundingClientRect().right - 13)) + 'px'
        : '10px';
      if (btn.style.left !== hedefLeft) btn.style.left = hedefLeft;
      const yon = acik ? 'sol' : 'sag';
      if (btn.dataset.yon !== yon) {
        btn.dataset.yon = yon;
        btn.innerHTML = acik ? SVG_SOL : SVG_SAG;
      }
    } catch (e) {}
  }

  function dialogAcik() {
    return !!doc.querySelector('div[data-testid="stDialog"]');
  }

  // Menü yeniden kurulduysa (aynı eleman değilse) boyut izleyicisini YENİ menüye bağla.
  function bagla() {
    const sb = sbEl();
    if (!sb || sb === w.__kayranSbIzlenen || !w.ResizeObserver) return;
    if (w.__kayranSbRO) { try { w.__kayranSbRO.disconnect(); } catch (e) {} }
    w.__kayranSbRO = new w.ResizeObserver(() => konumla());
    w.__kayranSbRO.observe(sb);
    sb.addEventListener('transitionend', konumla);
    w.__kayranSbIzlenen = sb;
  }
  w.__kayranSbYenile = function () { bagla(); konumla(); };

  btn.onclick = function () {
    const sb = sbEl();
    if (!sb) return;
    if (gorunurMu()) {
      // ── KAPAT ──
      const rw = sb.getBoundingClientRect().width;
      if (rw > 40) w.__kayranSbW = Math.round(rw) + 'px';
      doc.body.classList.add('kyr-sb-kapali');
      zorlaKapat(sb);
      try { w.localStorage.setItem('kayran-sb', 'kapali'); } catch (e) {}
      w.setTimeout(() => {  // etki doğrulaması → son çare
        try {
          if (gorunurMu()) sb.style.setProperty('display', 'none', 'important');
          konumla();
        } catch (e) {}
      }, 240);
    } else {
      // ── AÇ: iki mekanizmayı birden aç ──
      doc.body.classList.remove('kyr-sb-kapali');
      inlineTemizle(sb);
      try { w.localStorage.setItem('kayran-sb', 'acik'); } catch (e) {}
      nativeAc();                       // Streamlit kendi tarafında kapalıysa
      w.setTimeout(() => {              // hâlâ görünmüyorsa son çare zorla aç
        try { if (!gorunurMu()) zorlaAc(sbEl()); konumla(); } catch (e) {}
      }, 300);
      w.setTimeout(konumla, 600);
    }
    w.setTimeout(konumla, 60);
  };

  // Kayıtlı "kapalı" tercihi yüklemede uygula (yalnız kapalı yönde)
  try {
    if (w.localStorage.getItem('kayran-sb') === 'kapali') {
      const sb = sbEl();
      if (sb && gorunurMu()) { doc.body.classList.add('kyr-sb-kapali'); zorlaKapat(sb); }
    }
  } catch (e) {}

  doc.body.appendChild(btn);
  konumla();

  // ── OLAY KAYNAKLARI (yoklama yok) ──
  w.__kayranSbIzlenen = null;
  bagla();
  w.addEventListener('resize', konumla);

  let planli = false;
  if (w.__kayranSbMO) { try { w.__kayranSbMO.disconnect(); } catch (e) {} }
  w.__kayranSbMO = new w.MutationObserver(() => {
    if (planli) return;
    planli = true;
    w.requestAnimationFrame(() => {
      planli = false;
      bagla();          // menü yeniden kurulduysa yeni menüye bağlan
      konumla();        // görünürlük + konum (yalnız değer değişince yazar)
      // Kapalı tercih rerun'da silindiyse yeniden uygula (ucuz string kontrolü)
      if (doc.body.classList.contains('kyr-sb-kapali')) {
        const sb = sbEl();
        if (sb && sb.style.width !== '0px' && sb.style.display !== 'none') zorlaKapat(sb);
      }
    });
  });
  w.__kayranSbMO.observe(doc.body, { childList: true, subtree: true });

  if (w.__kayranSbInt) { w.clearInterval(w.__kayranSbInt); w.__kayranSbInt = null; }
})();
</script>
""",
    height=0,
)

# ── TIKLA-YAZ: tüm giriş kutularında odaklanınca mevcut metni SEÇ ──────────
# Sorun: selectbox/text_input'a tıklayıp yazınca eski değerin ("—", "1-2",
# SKU vb.) ÜZERİNE ekleniyordu; arama "—401A..." gibi bozuk metinle yapılıyor
# ve eşleşme çıkmıyordu. Çözüm: odak anında mevcut metin komple seçilir →
# ilk tuş vuruşu eski değeri silip yerine yazar. Uygulama genelinde geçerli
# (tüm modüller bu sayfadan render edildiği için tek nokta yeter).
_sb_comp.html(
    """
<script>
(function () {
  const w = window.parent, doc = w.document;
  if (w.__kayranTiklaYaz) return;            // tek sefer kur
  w.__kayranTiklaYaz = true;

  const UYGUN = ["text", "search", "number", "tel", "email", "url"];

  doc.addEventListener("focusin", function (e) {
    const t = e.target;
    if (!t || t.tagName !== "INPUT") return;
    const tip = (t.getAttribute("type") || "text").toLowerCase();
    if (UYGUN.indexOf(tip) === -1) return;

    // Odaklanma anındaki değeri sakla. 60 ms sonraki select() YALNIZ bu
    // değer DEĞİŞMEMİŞSE çalışır.
    //
    // SORUN: kullanıcı boş arama kutusuna hızlı yazınca ("F11"), 60 ms'de
    // select() araya giriyor ve o ana kadar yazılan "F" seçili hale geliyor;
    // sonraki tuş onu siliyordu → "11" kalıyordu.
    // ÇÖZÜM: kullanıcı yazmaya başladıysa dokunma. Ayrıca alan BOŞSA
    // seçilecek bir şey yok, zamanlayıcıyı hiç kurma.
    const bas_deger = t.value;
    if (!bas_deger) return;          // boş alan → select() gereksiz

    // Fare ile odaklanmada tarayıcı, mouseup'ta seçimi bozup imleci koyar;
    // ilk mouseup'ı bir kez engelle → seçim korunur.
    const koru = function (ev) { ev.preventDefault(); };
    t.addEventListener("mouseup", koru, { once: true });

    // Kullanıcı yazmaya başlarsa seçimi iptal et
    let yazdi = false;
    const yazma_izle = function () { yazdi = true; };
    t.addEventListener("input", yazma_izle, { once: true });
    t.addEventListener("keydown", yazma_izle, { once: true });

    w.setTimeout(function () {
      try {
        t.removeEventListener("input", yazma_izle);
        t.removeEventListener("keydown", yazma_izle);
        if (yazdi) return;                       // kullanıcı yazıyor → dokunma
        if (t.value !== bas_deger) return;       // değer değişmiş → dokunma
        if (doc.activeElement === t && t.value) t.select();
      } catch (err) {}
    }, 60);
  }, true);
})();
</script>
""",
    height=0,
)


# Session state defaults
def _oturum_secret():
    try:
        return str(st.secrets["supabase"]["key"])
    except Exception:
        return "kayran-oturum-varsayilan-anahtar"


def _oturum_store():
    """Sunucu tarafı oturum deposu — artık shared/oturum.py'de (tek kaynak).
    Token yalnız onu oluşturan tarayıcıda geçerlidir (cihaz imzası)."""
    from shared.oturum import oturum_store
    return oturum_store()


def _cihaz_imzasi():
    """Tarayıcıya özgü imza (Streamlit'in _xsrf çerezi). Link başka tarayıcıda
    açıldığında imza tutmaz → oturum reddedilir."""
    try:
        import hashlib
        _ck = dict(st.context.cookies or {})
        _v = _ck.get("_xsrf") or _ck.get("_streamlit_xsrf") or ""
        if not _v:
            _v = str(dict(st.context.headers or {}).get("User-Agent", ""))
        return hashlib.sha256(str(_v).encode()).hexdigest()[:24] if _v else ""
    except Exception:
        return ""


def _oturum_ac(kullanici):
    """Girişte rastgele oturum token'ı üretir, cihaza bağlar, URL'ye yalnız token yazar."""
    import secrets as _sec
    import time as _t
    tok = _sec.token_urlsafe(24)
    _oturum_store()[tok] = {"u": kullanici, "cihaz": _cihaz_imzasi(), "ts": _t.time()}
    try:
        st.query_params.clear()
        st.query_params["t"] = tok
    except Exception:
        pass


def oturumlari_sonlandir(kullanici):
    """Kullanıcının bu sunucudaki TÜM açık oturum token'larını yakar.
    Hesap pasife alındığında ya da şifresi sıfırlandığında çağrılır."""
    k = (kullanici or "").strip().lower()
    if not k:
        return 0
    try:
        _st = _oturum_store()
        _yak = [t for t, r in list(_st.items()) if str(r.get("u", "")).strip().lower() == k]
        for t in _yak:
            _st.pop(t, None)
        return len(_yak)
    except Exception:
        return 0


def _hesap_hala_aktif_mi(kullanici):
    """Açık oturum sırasında hesap PASİFE alındıysa False.
    Veritabanına ulaşılamazsa ya da kullanıcı tabloda yoksa True (kimseyi
    yanlışlıkla atmayalım — giriş kontrolü zaten ayrıca yapılıyor)."""
    try:
        from shared.yetki import kullanici_kaydi
        _db_var, _kayit = kullanici_kaydi(kullanici)
        return not (_db_var and _kayit is not None and not _kayit.get("aktif", True))
    except Exception:
        return True


def _oturum_token(kullanici):
    import hmac, hashlib
    return hmac.new(_oturum_secret().encode(),
                    (kullanici or "").lower().strip().encode(),
                    hashlib.sha256).hexdigest()[:32]


if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
if "aktif_kullanici" not in st.session_state:
    st.session_state.aktif_kullanici = ""
if "salt_okur" not in st.session_state:
    st.session_state["salt_okur"] = False

# Tarayıcı yenilendiğinde (yeni oturum) girişi URL'deki güvenli token'dan geri yükle
# → otomatik çıkışı önler. Token = HMAC(kullanıcı, sunucu_secret); başkası için taklit edilemez.
if not st.session_state.giris_yapildi:
    try:
        import time as _t
        if st.query_params.get("u", ""):
            # ESKİ format (u+deterministik t): güvensiz — paylaşılan tüm eski linkler geçersiz.
            st.query_params.clear()
        else:
            _qt = st.query_params.get("t", "")
            _rec = _oturum_store().get(_qt) if _qt else None
            if _rec and (_t.time() - _rec.get("ts", 0) < 7 * 86400):
                _imza = _cihaz_imzasi()
                if _rec.get("cihaz") and _imza and _rec["cihaz"] == _imza:
                    st.session_state.giris_yapildi = True
                    st.session_state.aktif_kullanici = _rec["u"]
                    st.session_state["salt_okur"] = salt_okur_mu(_rec["u"])
                    _rec["ts"] = _t.time()  # kaydır: aktif kullanım süreyi tazeler
                else:
                    # Farklı tarayıcı/cihaz → token'ı yak (link paylaşımı girişimi)
                    _oturum_store().pop(_qt, None)
                    st.query_params.clear()
            elif _qt:
                st.query_params.clear()
    except Exception:
        pass
# ── GÖRÜNÜM TEMASI (koyu/açık) ────────────────────────────────────────
# Tercih kullanıcı bazlı (Supabase kullanici_tercih). Oturum başına bir kez
# okunur. Streamlit'in KENDİ parçaları (giriş kutuları, tablolar, sidebar)
# tarayıcıdaki stActiveTheme anahtarını okur; bizim CSS değişkenlerimiz de
# session'daki temayı. İkisi aynı olsun diye aşağıdaki script anahtarı
# tercihe göre yazar ve gerekirse sayfayı bir kez yeniler.
if st.session_state.get("giris_yapildi") and "tema" not in st.session_state:
    from shared.tercih import tema_oku as _tema_oku
    st.session_state["tema"] = _tema_oku(st.session_state.get("aktif_kullanici", ""))
    if st.session_state["tema"] != _css_tema:
        st.rerun()   # CSS koyu basıldı, tercih açık: doğru temayla yeniden çiz
if st.session_state.get("giris_yapildi"):
    _tema_ad = "Light" if st.session_state.get("tema") == "acik" else "Dark"
    _sb_comp.html(
        "<script>(function(){var w=window.parent;try{"
        "var key='stActiveTheme-'+w.location.pathname+'-v2';"
        f"var want=JSON.stringify('{_tema_ad}');"
        "if(w.localStorage.getItem(key)!==want){w.localStorage.setItem(key,want);w.location.reload();}"
        "}catch(e){}})();</script>", height=0)

if "aktif_uygulama" not in st.session_state:
    # Sayfa yenilenince son sayfada kal (URL'deki 's' parametresinden geri yükle)
    try:
        st.session_state.aktif_uygulama = st.query_params.get("s") or "anasayfa"
    except Exception:
        st.session_state.aktif_uygulama = "anasayfa"
    from shared.gezinme import adres_oku
    adres_oku()                     # ?p= → modül menüsü o sayfada açılır


# ─────────────────────────────────────────────────────────────────────
# KURUMSAL KIMLIK
# ─────────────────────────────────────────────────────────────────────
KAYRAN_LOGO_SVG = '<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="kgS" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#818CF8"/><stop offset="50%" stop-color="#818CF8"/><stop offset="100%" stop-color="#A5B4FC"/></linearGradient></defs><rect width="40" height="40" rx="10" fill="url(#kgS)"/><polygon points="9,8 15,8 15,19 24,8 32,8 21,21 32,32 24,32 15,21 15,32 9,32" fill="white"/></svg>'

KAYRAN_LOGO_BIG = '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="kgB" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#818CF8"/><stop offset="50%" stop-color="#818CF8"/><stop offset="100%" stop-color="#A5B4FC"/></linearGradient></defs><rect width="64" height="64" rx="16" fill="url(#kgB)"/><polygon points="14,13 24,13 24,30 38,13 51,13 34,34 51,51 38,51 24,34 24,51 14,51" fill="white"/></svg>'


# ─────────────────────────────────────────────────────────────────────
# CSS — Login + Portal
# ─────────────────────────────────────────────────────────────────────
def login_css():
    """Giriş ekranı. Arka plan: muhasebe defteri çizgileri + solda ince kırmızı
    'kenar boşluğu' çizgisi (defter sayfası) — konuya ait, kenarlara doğru
    silinen sakin bir doku. Eskiden iki büyük renk lekesi vardı ama z-index:-1
    yüzünden sayfa zemininin ARKASINDA kalıyor, hiç görünmüyordu.
    Düğme ve kutular ortak tasarım dilinden gelir (DUGME_CSS); burada yalnız
    sahne ve kart tanımlanır."""
    from shared.tasarim import css_tek_satir
    return "<style>" + css_tek_satir("""
html,body{background:var(--k-yuzey0) !important;}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:transparent !important;}
[data-testid="stAppViewContainer"]{position:relative;z-index:1;}
[data-testid="stHeader"]{background:transparent !important;height:0 !important;}
[data-testid="stToolbar"],[data-testid="stDecoration"],.stDeployButton,#MainMenu,footer{display:none !important;}
section[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none !important;}
.stApp [data-testid="stMainBlockContainer"]{padding-top:0 !important;padding-bottom:0 !important;max-width:1180px !important;}
.kayran-bg{position:fixed;inset:0;z-index:0;pointer-events:none;background:var(--k-yuzey0);}
.kayran-bg::before{content:"";position:absolute;inset:0;
  background-image:linear-gradient(to bottom,color-mix(in srgb,var(--k-metin) 7%,transparent) 1px,transparent 1px);
  background-size:100% 34px;
  -webkit-mask-image:radial-gradient(ellipse 70% 65% at 32% 45%,#000 0%,transparent 75%);
          mask-image:radial-gradient(ellipse 70% 65% at 32% 45%,#000 0%,transparent 75%);}
.kayran-bg::after{content:"";position:absolute;top:0;bottom:0;left:max(24px,calc(50% - 560px));width:1px;
  background:linear-gradient(to bottom,transparent,color-mix(in srgb,var(--k-kirmizi) 35%,transparent) 30%,
  color-mix(in srgb,var(--k-kirmizi) 35%,transparent) 70%,transparent);}
.st-key-giris_sahne{min-height:100vh;justify-content:center;padding:40px 0;}
.st-key-giris_sahne > [data-testid="stHorizontalBlock"]{align-items:center !important;}
.k-gr-sol{padding:0 28px 0 18px;animation:k-gr-belir .6s cubic-bezier(.2,.7,.2,1) both;}
.k-gr-marka{display:flex;align-items:center;gap:14px;margin-bottom:40px;}
.k-gr-marka svg{width:48px;height:48px;}
.k-gr-marka b{display:block;font-size:20px;font-weight:700;letter-spacing:4px;color:var(--k-metin);line-height:1;}
.k-gr-marka span{display:block;font-size:12px;color:var(--k-silik);margin-top:6px;}
.stApp h1.k-gr-baslik{font-size:clamp(28px,3.4vw,40px) !important;font-weight:650 !important;letter-spacing:-1px !important;
  line-height:1.1 !important;color:var(--k-metin) !important;margin:0 0 14px !important;padding:0 !important;max-width:15ch;}
.k-gr-metin{font-size:14px;line-height:1.65;color:var(--k-soluk);max-width:46ch;margin:0 0 30px;}
.k-gr-moduller{display:grid;grid-template-columns:1fr 1fr;gap:16px 24px;max-width:540px;}
.k-gr-mod{display:flex;gap:11px;align-items:flex-start;min-width:0;}
.k-gr-mod .k-ikon{font-size:20px;color:var(--c);margin-top:1px;flex-shrink:0;}
.k-gr-mod b{display:block;font-size:13px;font-weight:600;color:var(--k-metin);line-height:1.3;}
.k-gr-mod span{display:block;font-size:12px;color:var(--k-silik);line-height:1.4;margin-top:1px;}
.k-gr-imza{margin-top:40px;font-size:12px;color:var(--k-silik);}
.k-gr-imza b{color:var(--k-soluk);font-weight:600;}
.st-key-giris_kart{background:var(--k-yuzey1) !important;border:1px solid var(--k-kenar2) !important;
  border-radius:16px !important;padding:30px 30px 24px !important;gap:0 !important;
  box-shadow:0 1px 2px rgba(15,23,42,.10),0 24px 60px -28px rgba(15,23,42,.40);
  animation:k-gr-belir .6s .08s cubic-bezier(.2,.7,.2,1) both;}
@keyframes k-gr-belir{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
@media (prefers-reduced-motion:reduce){.k-gr-sol,.st-key-giris_kart{animation:none;}}
.k-gr-kart-bas b{display:block;font-size:20px;font-weight:650;letter-spacing:-.3px;color:var(--k-metin);}
.k-gr-kart-bas span{display:block;font-size:13px;color:var(--k-soluk);margin:4px 0 22px;}
.st-key-giris_kart [data-testid="stForm"]{border:0 !important;padding:0 !important;background:transparent !important;}
.st-key-giris_kart [data-testid="stWidgetLabel"] p{font-size:13px !important;font-weight:500 !important;color:var(--k-soluk) !important;}
.st-key-giris_kart input{font-size:14px !important;}
.st-key-giris_kart [data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
.st-key-giris_kart [data-testid="stTextInputRootElement"]{min-height:42px;border-radius:10px !important;
  background:var(--k-yuzey0) !important;border:1px solid var(--k-kenar2) !important;
  transition:border-color .12s ease,box-shadow .12s ease;}
.st-key-giris_kart [data-testid="stTextInputRootElement"] *{background:transparent !important;}
.st-key-giris_kart [data-testid="stTextInputRootElement"]:focus-within{border-color:var(--k-mor) !important;
  box-shadow:0 0 0 3px color-mix(in srgb,var(--k-mor) 22%,transparent) !important;}
.st-key-giris_kart [data-testid="stFormSubmitButton"] button,.st-key-giris_kart .stFormSubmitButton button{
  min-height:44px !important;font-size:14px !important;margin-top:6px;}
.k-gr-guven{display:flex;flex-direction:column;gap:6px;margin-top:22px;padding-top:16px;border-top:1px solid var(--k-kenar);}
.k-gr-guven div{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--k-silik);}
.k-gr-guven .k-ikon{font-size:16px;color:var(--k-yesil);}
.duyuru-band{position:fixed;top:0;left:0;right:0;z-index:100;padding:9px 24px;text-align:center;font-size:13px;
  color:var(--k-metin);background:color-mix(in srgb,var(--k-mor) 14%,var(--k-yuzey1));border-bottom:1px solid var(--k-kenar2);}
.k-gr-mobil-marka{display:none;align-items:center;gap:10px;margin-bottom:22px;}
.k-gr-mobil-marka svg{width:30px;height:30px;}
.k-gr-mobil-marka b{font-size:15px;font-weight:700;letter-spacing:2.5px;color:var(--k-metin);}
@media (max-width:820px){
  .k-gr-sol{display:none;}
  .k-gr-mobil-marka{display:flex;}
  .st-key-giris_sahne{padding:24px 0;}
  .st-key-giris_kart{padding:24px 20px 20px !important;}
  .kayran-bg::after{display:none;}
}
""") + '</style><div class="kayran-bg"></div>'


def portal_css():
    """Ana sayfa + sidebar CSS (alt uygulamalar yüklenmedikçe geçerli)"""
    return """
    <style>
    /* Font @import kaldırıldı — tek kaynak config.toml */

    .stApp {
        background: var(--k-yuzey0) !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    [data-testid="stHeader"] { background: transparent !important; }
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { display: none !important; }

    /* Sol menü: shared/tasarim.SIDEBAR_CSS (tek kaynak) */

    /* ── STREAMLIT TOOLBAR (sağ üstteki Deploy, Share, kebab menü) ── */
    header[data-testid="stHeader"] *,
    .stAppToolbar *,
    .stAppDeployButton *,
    .stMainMenu *,
    [data-testid="stToolbar"] * {
        color: color-mix(in srgb,var(--k-metin) 65%,transparent) !important;
    }
    header[data-testid="stHeader"] button:hover,
    .stAppToolbar button:hover,
    .stAppDeployButton button:hover {
        color: var(--k-metin) !important;
        background: color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
    }
    header[data-testid="stHeader"] svg,
    .stAppToolbar svg,
    .stMainMenu svg {
        fill: color-mix(in srgb,var(--k-metin) 65%,transparent) !important;
    }
    /* Sidebar collapse butonu (hamburger) — beyaz arka planda beyazdı, koyu yapıyoruz */
    [data-testid="stSidebarCollapsedControl"],
    button[aria-label*="Close"],
    button[aria-label*="Open"],
    [data-testid="stBaseButton-headerNoPadding"] {
        background: color-mix(in srgb,var(--k-metin) 5%,transparent) !important;
        color: color-mix(in srgb,var(--k-metin) 80%,transparent) !important;
    }
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] span {
        color: color-mix(in srgb,var(--k-metin) 80%,transparent) !important;
        fill: color-mix(in srgb,var(--k-metin) 80%,transparent) !important;
    }
    [data-testid="stSidebarCollapsedControl"]:hover,
    [data-testid="stBaseButton-headerNoPadding"]:hover {
        background: color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
    }
    /* Material Icons ligature fix - text gözükmesin */
    button[data-testid="stBaseButton-headerNoPadding"] span:not(.material-symbols-rounded):not(.material-symbols-outlined),
    [data-testid="stSidebarCollapsedControl"] span:not(.material-symbols-rounded):not(.material-symbols-outlined) {
        font-size: 0 !important;
    }
    button[data-testid="stBaseButton-headerNoPadding"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        width: 18px !important;
        height: 18px !important;
    }

    /* ── SCROLLBAR koyu tema ── */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: color-mix(in srgb,var(--k-metin) 2%,transparent); }
    ::-webkit-scrollbar-thumb {
        background: color-mix(in srgb,var(--k-metin) 15%,transparent);
        border-radius: 6px;
        border: 2px solid transparent;
        background-clip: padding-box;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: color-mix(in srgb,var(--k-metin) 25%,transparent);
        background-clip: padding-box;
    }

    /* ── TOOLTIP & POPOVER ──
       .stTooltipIcon BURADA YOK: help= verilen her düğmenin etiketi o kaba
       sarılır; çerçeve kuralı üst menüdeki sekmeleri ana sayfada kutu kutu
       gösteriyordu (modüllerde çerçevesizdi). Yalnız açılan baloncuk boyanır. */
    [role="tooltip"], [data-baseweb="tooltip"] {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
    }

    /* Ana içerik alanı */
    .main .block-container {
        padding-top: 2.5rem !important;
        max-width: 1200px !important;
    }

    /* Arka plan 'blob' animasyonu kaldırıldı: z-index:-1 yüzünden sayfa
       zemininin ARKASINDA kalıyor, hiç görünmüyordu — ama 120px bulanıklıkla
       sürekli oynayarak işlemciyi boşuna yoruyordu. */
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    </style>
    """


@st.cache_resource(show_spinner=False)
def _kur_kayit_zamani():
    """Süreç (sunucu) başına tek sözlük: son kur kaydının zamanı."""
    return {"t": 0.0}


def _kur_kaydi_gerekli(aralik_sn=3600):
    """Günün kuru en fazla SAATTE BİR yazılsın.

    HIZ: Eskiden ana sayfa her çizildiğinde (her tıklamada, herkes için)
    kur_gunluk'a upsert + audit_log'a insert gidiyordu — 2 yazma, ~2 ağ
    gidiş-dönüşü ve günde yüzlerce gereksiz denetim kaydı. Kur gün içinde
    güncellenmeye devam eder (saatte bir), tarihsel kur kaybolmaz."""
    import time as _t
    _z = _kur_kayit_zamani()
    if _t.time() - _z["t"] < aralik_sn:
        return False
    _z["t"] = _t.time()
    return True


def _ana_css():
    """Ana sayfaya özel sınıflar: karşılama, piyasa şeridi, bölüm başlıkları,
    modül kartları, alt bilgi. Renkler yalnız tema değişkenlerinden."""
    from shared.tasarim import css_tek_satir
    return "<style>" + css_tek_satir("""
.k-ana-karsila{margin:4px 0 6px;animation:k-belir .55s cubic-bezier(.2,.7,.2,1) both;}
@keyframes k-belir{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:none;}}
@media (prefers-reduced-motion:reduce){.k-ana-karsila{animation:none;}}
.k-ana-bas{display:flex;align-items:baseline;justify-content:space-between;gap:6px 16px;flex-wrap:wrap;}
.stApp .k-ana-bas h1{font-size:clamp(24px,3vw,30px) !important;font-weight:650 !important;
  letter-spacing:-.6px !important;line-height:1.15 !important;margin:0 !important;padding:0 !important;
  color:var(--k-metin) !important;}
.k-ana-bas > span{color:var(--k-soluk);font-size:13px;white-space:nowrap;}
.k-ana-serit{display:flex;flex-wrap:wrap;margin-top:14px;background:var(--k-yuzey1);
  border:1px solid var(--k-kenar);border-radius:12px;overflow:hidden;}
.k-ana-hucre{flex:1 1 150px;min-width:0;padding:10px 16px 11px;display:flex;flex-direction:column;gap:1px;
  border-left:1px solid var(--k-kenar);margin-left:-1px;}
.k-ana-hucre span,.k-ana-hucre small{font-size:11.5px;line-height:1.35;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;}
.k-ana-hucre span{color:var(--k-silik);}
.k-ana-hucre small{color:var(--k-soluk);}
.k-ana-hucre b{font-family:var(--k-mono);font-variant-numeric:tabular-nums;font-size:17px;font-weight:600;
  letter-spacing:-.3px;color:var(--k-metin);line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.k-ana-bolum{display:flex;align-items:baseline;gap:10px;margin:26px 0 10px;font-size:15px;font-weight:650;
  letter-spacing:-.1px;color:var(--k-metin);}
.k-ana-bolum span{font-size:12.5px;font-weight:400;color:var(--k-silik);}
.k-ana-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;}
.k-ana-kpi .k-kart{padding:11px 14px;}
.k-ana-kpi-ad{font-size:12px;font-weight:500;color:var(--k-soluk);line-height:1.3;}
.k-ana-kpi .k-deger{font-size:20px;margin-top:4px;}
[class*="st-key-hz_"]{position:relative;gap:0 !important;min-height:138px;padding:14px 16px 16px !important;
  border-radius:12px !important;background:var(--k-yuzey1) !important;border:1px solid var(--k-kenar) !important;
  transition:border-color .15s ease,background-color .15s ease;}
[class*="st-key-hz_"]:hover{border-color:color-mix(in srgb,var(--c) 55%,transparent) !important;
  background:color-mix(in srgb,var(--c) 5%,var(--k-yuzey1)) !important;}
[class*="st-key-hz_"]:has(button:focus-visible){outline:2px solid var(--c);outline-offset:2px;}
[class*="st-key-hz_"] [data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
[class*="st-key-hz_"] [data-testid="stElementContainer"]:has(.stButton){position:absolute !important;inset:0 !important;
  margin:0 !important;z-index:3;width:auto !important;height:auto !important;}
html body [class*="st-key-hz_"] .stButton{width:100% !important;height:100% !important;}
html body [data-testid="stMain"] [class*="st-key-hz_"] [data-testid="stButton"].stButton > button[data-testid]{
  width:100% !important;height:100% !important;min-height:100% !important;opacity:0 !important;cursor:pointer;
  border:0 !important;padding:0 !important;}
.k-hz-ust{display:flex;align-items:center;gap:8px;}
.k-hz-ust i{width:36px;height:36px;border-radius:10px;flex-shrink:0;display:flex;align-items:center;
  justify-content:center;font-style:normal;background:color-mix(in srgb,var(--c) 14%,transparent);}
.k-hz-ust i .k-ikon{color:var(--c);}
.k-hz-ust em{font-style:normal;font-size:11px;font-weight:600;line-height:1;padding:4px 8px;border-radius:999px;
  color:var(--c);background:color-mix(in srgb,var(--c) 12%,transparent);white-space:nowrap;}
.k-hz-ust > .k-ikon{margin-left:auto;color:var(--k-silik);transition:transform .18s ease,color .18s ease;}
[class*="st-key-hz_"]:hover .k-hz-ust > .k-ikon{transform:translateX(3px);color:var(--c);}
.k-hz-ad{margin-top:14px;font-size:14px;font-weight:650;color:var(--k-metin);line-height:1.3;}
.k-hz-ac{margin-top:3px;font-size:12.5px;color:var(--k-soluk);line-height:1.45;}
.k-ana-alt{display:flex;justify-content:space-between;align-items:center;gap:8px 16px;flex-wrap:wrap;
  margin:36px 0 4px;padding-top:14px;border-top:1px solid var(--k-kenar);font-size:12px;color:var(--k-silik);}
.k-ana-alt a{color:var(--k-soluk) !important;text-decoration:none;margin-left:16px;}
.k-ana-alt a:hover{color:var(--k-metin) !important;}
@media (max-width:640px){
  .k-ana-hucre{flex:1 1 45%;}
  [class*="st-key-hz_"]{min-height:0;}
}
""") + "</style>"


# ─────────────────────────────────────────────────────────────────────
# 1) LOGIN EKRANI
# ─────────────────────────────────────────────────────────────────────
def giris_ekrani():
    st.markdown(login_css(), unsafe_allow_html=True)
    _duyuru_aktif2, _duyuru_metni2 = get_duyuru()
    if _duyuru_aktif2 and _duyuru_metni2:
        st.markdown(f'<div class="duyuru-band">{_duyuru_metni2}</div>', unsafe_allow_html=True)

    # Modül listesi: kutusuz, sakin; ikon + ad + kısa açıklama. İkonlar ve
    # renkler üst menü / ana sayfa kartlarıyla AYNI (tasarim.MODUL_IKON/RENK).
    _moduller = [
        ("kayranacc", "Muhasebe & Finans", "Nakit akış, banka, cari"),
        ("satis", "Satış", "Kâr / P&L, marj, iade"),
        ("ithalat", "İthalat", "Dosya, masraf, paçal maliyet"),
        ("kayranpm", "Ürün Yönetimi", "Stok, sipariş önerisi, kampanya"),
        ("depo", "Depo", "Depo stoku, sevk, irsaliye"),
        ("teknikservis", "Teknik Servis", "Arıza kaydı, servis formu"),
        ("yonetim", "Yönetim", "Toplam aktifler, özet"),
        ("hesap_makinesi", "Hesap Makinesi", "Maliyet ve fiyat"),
    ]
    _liste = "".join(
        f'<div class="k-gr-mod" style="--c:{rv(MODUL_RENK.get(_k, "mor"))}">'
        f'{k_ikon(MODUL_IKON.get(_k, "apps"), 20)}<div><b>{_ad}</b><span>{_alt}</span></div></div>'
        for _k, _ad, _alt in _moduller)

    with st.container(key="giris_sahne"):
        col_l, col_r = st.columns([1.15, 0.85], gap="large")
        with col_l:
            st.markdown(
                '<div class="k-gr-sol">'
                f'<div class="k-gr-marka">{KAYRAN_LOGO_BIG}<div><b>KAYRAN</b><span>Workspace</span></div></div>'
                '<h1 class="k-gr-baslik">Satıştan muhasebeye, tek defter.</h1>'
                '<p class="k-gr-metin">Sekiz modül aynı veriyle çalışır: bir satış girildiğinde stok, '
                'kâr ve cari aynı anda güncellenir; rakamlar her ekranda birbirini tutar.</p>'
                f'<div class="k-gr-moduller">{_liste}</div>'
                '<div class="k-gr-imza"><b>G5F Teknoloji</b> ve <b>Fazeon</b> için, '
                'İbrahim Kayran tarafından geliştirildi.</div>'
                '</div>',
                unsafe_allow_html=True)

        with col_r:
            with st.container(key="giris_kart"):
                st.markdown('<div class="k-gr-mobil-marka">' + KAYRAN_LOGO_SVG + '<b>KAYRAN</b></div>'
                            '<div class="k-gr-kart-bas"><b>Oturum aç</b>'
                            '<span>KAYRAN hesabınla devam et.</span></div>',
                            unsafe_allow_html=True)
                with st.form("giris_form", clear_on_submit=False, border=False):
                    kullanici = st.text_input("Kullanıcı adı", placeholder="kullanici_adi",
                                              key="login_user")
                    sifre = st.text_input("Şifre", type="password", placeholder="Şifren",
                                          key="login_pass")
                    giris_btn = st.form_submit_button("Giriş yap", type="primary",
                                                      use_container_width=True)
                # GÜVENLİK NOTU — yalnızca GERÇEKTEN uygulanan korumalar yazılır.
                # (Eski metin "256-bit SSL" diyordu; uygulama HTTP üzerinden de
                #  çalışabildiği için bu iddia yanıltıcıydı.)
                st.markdown(
                    '<div class="k-gr-guven">'
                    + "".join(f'<div>{k_ikon("check_circle", 16)}{_t}</div>' for _t in (
                        "Şifreler PBKDF2 ile şifrelenerek saklanır",
                        "Art arda hatalı denemede hesap geçici kilitlenir",
                        "Her işlem kimin yaptığıyla kayda geçer"))
                    + '</div>',
                    unsafe_allow_html=True)

            if giris_btn:
                try:
                    kullanicilar = st.secrets.get("kullanicilar", {})
                    if not kullanicilar:
                        st.warning("⚠️ Kullanıcı ayarları yapılandırılmamış.")
                        return
                    from shared.auth import giris_kontrol, giris_basarisiz, giris_basarili
                    _izin, _kalan = giris_kontrol(kullanici)
                    if not _izin:
                        st.error(f"🔒 Çok fazla hatalı deneme. Lütfen {_kalan // 60} dk {_kalan % 60} sn sonra tekrar deneyin.")
                    elif kullanici_dogrula_v2(kullanici, sifre, kullanicilar):
                        giris_basarili(kullanici)
                        st.session_state.giris_yapildi = True
                        st.session_state.aktif_kullanici = kullanici
                        st.session_state["salt_okur"] = salt_okur_mu(kullanici)
                        st.session_state.aktif_uygulama = "anasayfa"
                        _oturum_ac(kullanici)
                        st.rerun()
                    else:
                        _sayi, _kilit = giris_basarisiz(kullanici)
                        _kalan_hak = max(0, 5 - _sayi)
                        if _kilit > 0:
                            st.error(f"🔒 Çok fazla hatalı deneme. Hesap {_kilit // 60} dakika kilitlendi.")
                        elif _sayi >= 3:
                            st.error(f"❌ Kullanıcı adı veya şifre hatalı. {_kalan_hak} deneme hakkınız kaldı.")
                        else:
                            st.error("❌ Kullanıcı adı veya şifre hatalı.")
                except Exception as e:
                    st.error(f"Giriş sistemi hatası: {e}")


def ust_navigasyon():
    """Modüller arası geçiş — sayfanın üstünde kompakt, modern yatay şerit (yetkiye göre)."""
    aktif = st.session_state.get("aktif_uygulama", "anasayfa")
    ak = st.session_state.get("aktif_kullanici", "")
    yet = kullanici_yetkileri(ak)
    # Herkes TÜM modülleri görür; yetkisi olmayan tıklarsa yönlendirmede
    # "🔒 ... erişim yetkiniz yok" uyarısı alır (dispatch guard'ları).
    # (etiket, modül_kodu, material ikon) — emoji değil gerçek vektör ikon
    # Arama artık modül değil: "Ana Sayfa"nın yanında komut paleti (shared/palet.py)
    moduller = [("Ana Sayfa", "anasayfa", ":material/home:"),
                ("Yönetim", "yonetim", ":material/monitoring:"),
                ("Muhasebe", "kayranacc", ":material/account_balance_wallet:"),
                ("İthalat", "ithalat", ":material/directions_boat:"),
                ("Ürün Yönetimi", "kayranpm", ":material/inventory_2:"),
                ("Depo", "depo", ":material/warehouse:"),
                ("Satış", "satis", ":material/point_of_sale:"),
                ("Teknik Servis", "teknikservis", ":material/construction:"),
                ("Hesap Makinesi", "hesap_makinesi", ":material/calculate:")]

    # ── Üst menü stili ─────────────────────────────────────────────────
    # TEK SATIR · her modülde AYNI aktif renk · mobilde yatay kaydırmalı şerit.
    # Seçiciler 'html body' ile güçlendirildi: modüllerin kendi birincil düğme
    # renkleri (Muhasebe mor degrade, Ürün Yön. mavi…) artık menüyü EZEMEZ.
    N = 'html body .st-key-ustnav'
    from shared.tasarim import _OPT, _DAIRE          # radyo seçicileri (eski + 1.64 yapısı)
    st.markdown(f"""<style>
    /* Tek ŞERİT + çerçevesiz sekmeler (eskiden 10 ayrı çerçeveli kutu, eşit
       genişlikte → kalabalık ve amatör görünüyordu). Gruplar: [Ana Sayfa · Arama]
       | [modüller] ......... [Hesap Makinesi] (yardımcı araç, sağa yaslı). */
    html body .st-key-ustnav{{container-type:inline-size;container-name:ustnav;}}
    {N} [data-testid="stHorizontalBlock"]{{gap:2px !important;margin:0 !important;padding:4px !important;
        flex-wrap:nowrap !important;overflow-x:auto !important;scrollbar-width:none;align-items:center !important;
        -webkit-overflow-scrolling:touch;background:var(--k-yuzey2) !important;
        border:1px solid var(--k-kenar) !important;border-radius:12px !important;}}
    {N} [data-testid="stHorizontalBlock"]::-webkit-scrollbar{{display:none;}}
    /* Sütun yazının genişliğini alır (eşit dağıtım yok); hiçbir etiket KESİLMEZ,
       sığmazsa şerit yana kayar. */
    {N} [data-testid="stColumn"]{{padding:0 !important;flex:0 0 auto !important;
        width:auto !important;min-width:max-content !important;}}
    /* Grup ayracı: modüllerden önce ince dikey çizgi · Hesap Makinesi en sağda */
    {N} [data-testid="stColumn"]:has(.st-key-top_yonetim){{margin-left:6px !important;padding-left:8px !important;
        border-left:1px solid var(--k-kenar2) !important;}}
    {N} [data-testid="stColumn"]:has(.st-key-top_hesap_makinesi){{margin-left:auto !important;}}
    /* Talep: en sağda, ince ayraçla; mor çerçeve + ikon her genişlikte görünür
       (eskiden sağ altta yüzüyordu ve Streamlit Cloud'un "Manage app" rozetinin
       arkasında kalıyordu — rozet uygulamanın dışında çizildiği için gizlenemez). */
    {N} [data-testid="stColumn"]:has(.st-key-ust_talep){{margin-left:6px !important;padding-left:8px !important;
        border-left:1px solid var(--k-kenar2) !important;}}
    {N} .st-key-ust_talep button{{color:var(--k-mor2) !important;font-weight:600 !important;
        box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--k-mor) 34%,transparent) !important;}}
    {N} .st-key-ust_talep button p{{color:var(--k-mor2) !important;}}
    {N} .st-key-ust_talep button span:has(> [data-testid="stIconMaterial"]){{display:inline-flex !important;}}
    {N} .st-key-ust_talep button [data-testid="stIconMaterial"]{{display:inline !important;color:var(--k-mor2) !important;}}
    /* Talep HER genişlikte şeridin sağ ucuna yapışık: sekmeler sığmayıp şerit
       kaydığında bile görünür (eskiden yalnız telefonda; küçük monitörde kesiliyordu). */
    {N} [data-testid="stColumn"]:has(.st-key-ust_talep){{position:sticky !important;right:-4px !important;
        z-index:2 !important;background:var(--k-yuzey2) !important;padding-right:4px !important;
        box-shadow:-10px 0 10px -6px var(--k-yuzey2) !important;}}
    {N} button{{
        min-height:34px !important;height:34px !important;padding:0 12px !important;gap:6px !important;
        border-radius:8px !important;font-size:13px !important;font-weight:500 !important;
        letter-spacing:0 !important;line-height:1 !important;white-space:nowrap !important;
        justify-content:center !important;border:0 !important;background:transparent !important;
        color:var(--k-soluk) !important;box-shadow:none !important;transform:none !important;
        transition:background .12s ease,color .12s ease !important;}}
    {N} button p{{font-size:13px !important;font-weight:inherit !important;white-space:nowrap !important;
        overflow:visible !important;text-overflow:clip !important;margin:0 !important;color:inherit !important;}}
    {N} button [data-testid="stIconMaterial"]{{font-size:17px !important;color:var(--k-silik) !important;}}
    {N} button:hover{{background:var(--k-ortu2) !important;color:var(--k-metin) !important;transform:none !important;}}
    {N} button:hover [data-testid="stIconMaterial"]{{color:var(--k-soluk) !important;}}
    {N} button:focus-visible{{outline:2px solid var(--k-mor) !important;outline-offset:1px !important;}}
    /* Seçili sekme: hafif mor zemin + ince mor çerçeve + mor ikon (dolgu düğme değil) */
    {N} button[kind="primary"], {N} button[data-testid="stBaseButton-primary"]{{
        background:color-mix(in srgb,var(--k-mor) 13%,var(--k-yuzey1)) !important;color:var(--k-metin) !important;
        font-weight:650 !important;box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--k-mor) 32%,transparent) !important;}}
    {N} button[kind="primary"] p, {N} button[data-testid="stBaseButton-primary"] p{{
        color:var(--k-metin) !important;font-weight:650 !important;}}
    {N} button[kind="primary"] [data-testid="stIconMaterial"],
    {N} button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"]{{color:var(--k-mor) !important;}}
    /* Dar şeritte ikonları gizle. İkonun KUTUSU da gizlenmeli; yalnız
       ikon gizlenince boş kutu yazıyı sağa itip "…" ile kesiyordu.
       Eşikler EKRANA değil ŞERİDİN kendi genişliğine bakar (container query):
       kenar çubuğu açıkken şerit ekrandan dardır; ekran genişliğine bakan eski
       kural küçük monitörde ikonları gösterip şeridi taşırıyordu.
       Ölçülen içerik: ikonlu ≈1195 px, ikonsuz ≈955 px. */
    @container ustnav (max-width:1260px){{
        {N} button span:has(> [data-testid="stIconMaterial"]),
        {N} button [data-testid="stIconMaterial"]{{display:none !important;}}
        {N} button{{padding:0 9px !important;}} }}
    @container ustnav (max-width:1020px){{
        {N} button{{padding:0 7px !important;}}
        {N} button p{{font-size:12.5px !important;}} }}
    /* Mobil: Streamlit sütunları alt alta dizer (10 düğme = yarım ekran).
       Bunun yerine tek satırlık, yana kaydırılan bir şerit. */
    @media (max-width:640px){{
        {N} [data-testid="stHorizontalBlock"]{{flex-direction:row !important;}}
        {N} [data-testid="stColumn"]{{flex:0 0 auto !important;width:auto !important;}}
        {N} [data-testid="stColumn"]:has(.st-key-top_hesap_makinesi){{margin-left:0 !important;}}
        {N} button{{padding:0 12px !important;}}
    }}

    /* Sayfa içi radyolar: shared/tasarim.SIDEBAR_CSS (iki Streamlit yapısını da tanır) */

    /* ── Sayfa sekmeleri (modül şeridinin altı) — radyo, sekme gibi çizilir ──
       Daire gizli; seçili sekmenin altında mor çizgi. Sığmazsa satır yana kayar.
       Seçiciler eski yapıyı (> label) ve 1.64 yapısını (stRadioOption) birlikte tanır
       — shared/tasarim._OPT / _DAIRE ile aynı kalıp. */
    html body .st-key-sayfa_seridi{{margin:-4px 0 12px !important;}}
    html body .st-key-sayfa_seridi [role="radiogroup"]{{flex-wrap:nowrap !important;overflow-x:auto;scrollbar-width:none;
        gap:2px !important;border-bottom:1px solid var(--k-kenar);padding:0 28px 0 2px;-webkit-overflow-scrolling:touch;
        width:100% !important;box-sizing:border-box;
        -webkit-mask-image:linear-gradient(to right,var(--k-metin) calc(100% - 36px),transparent);
        mask-image:linear-gradient(to right,var(--k-metin) calc(100% - 36px),transparent);}}
    html body .st-key-sayfa_seridi [data-testid="stRadio"],html body .st-key-sayfa_seridi [data-testid="stRadio"] > div{{width:100% !important;}}
    html body .st-key-sayfa_seridi [role="radiogroup"]::-webkit-scrollbar{{display:none;}}
    html body .st-key-sayfa_seridi {_OPT}{{margin:0 !important;padding:9px 12px 10px !important;
        border-radius:0 !important;background:transparent !important;border:0 !important;cursor:pointer;
        white-space:nowrap;flex:0 0 auto;box-shadow:none !important;min-height:0 !important;}}
    html body .st-key-sayfa_seridi {_DAIRE}{{display:none !important;}}
    html body .st-key-sayfa_seridi {_OPT} p{{font-size:13.5px !important;color:var(--k-soluk) !important;
        font-weight:500 !important;margin:0 !important;white-space:nowrap !important;}}
    html body .st-key-sayfa_seridi {_OPT}:hover p{{color:var(--k-metin) !important;}}
    html body .st-key-sayfa_seridi {_OPT}:has(input:checked){{box-shadow:inset 0 -2px 0 var(--k-mor) !important;
        background:transparent !important;}}
    html body .st-key-sayfa_seridi {_OPT}:has(input:checked) *{{background:transparent !important;}}
    html body .st-key-sayfa_seridi {_OPT}:has(input:checked) p{{color:var(--k-metin) !important;font-weight:600 !important;}}
    /* Odak çerçevesi yok: fareyle tıklanınca da (Chrome radyoda :focus-visible sayıyor)
       sekmede kutu kalıyordu. Radyo grubunda ok tuşları seçimi anında değiştirir;
       seçili sekmenin alt çizgisi klavye odağını da gösterir. */
    html body .st-key-sayfa_seridi {_OPT},html body .st-key-sayfa_seridi {_OPT} *{{outline:none !important;}}
    html body .st-key-sayfa_seridi [data-testid="stElementContainer"]{{width:100% !important;}}
    /* İki katlı (çok sayfalı modül): altta seçili grubun sayfaları — hap düğmeler */
    html body .st-key-sayfa_seridi .st-key-sayfa_alt{{margin-top:8px !important;}}
    html body .st-key-sayfa_seridi .st-key-sayfa_alt [role="radiogroup"]{{border-bottom:0 !important;gap:6px !important;
        -webkit-mask-image:none !important;mask-image:none !important;padding:0 2px !important;}}
    html body .st-key-sayfa_seridi .st-key-sayfa_alt {_OPT}{{padding:5px 12px !important;border-radius:999px !important;
        border:1px solid var(--k-kenar2) !important;box-shadow:none !important;}}
    html body .st-key-sayfa_seridi .st-key-sayfa_alt {_OPT} p{{font-size:12.5px !important;}}
    html body .st-key-sayfa_seridi .st-key-sayfa_alt {_OPT}:has(input:checked){{box-shadow:none !important;
        background:color-mix(in srgb,var(--k-mor) 16%,transparent) !important;
        border-color:color-mix(in srgb,var(--k-mor) 40%,transparent) !important;}}
    html body .st-key-sayfa_seridi .st-key-sayfa_alt {_OPT}:has(input:checked) p{{color:var(--k-metin) !important;}}

    /* === Üstteki ve sidebar'daki fazla boşlukları komple kaldır === */
    /* Streamlit üst barı/araç çubuğu/dekorasyon: gizle */
    header[data-testid="stHeader"]{{display:none !important;height:0 !important;}}
    [data-testid="stToolbar"]{{display:none !important;}}
    [data-testid="stDecoration"]{{display:none !important;}}
    /* Ana içerik üst boşluğu ~0'a (yüksek spesifiklik ile Streamlit'in kendi padding'ini ez) */
    .stApp [data-testid="stMainBlockContainer"],
    .stApp .block-container,
    section.main > div.block-container,
    [data-testid="stAppViewBlockContainer"]{{padding-top:0.4rem !important;}}
    /* Üst menü kaydırmada üstte SABİT kalsın */
    [data-testid="stMainBlockContainer"]{{overflow:visible !important;}}
    [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"]{{overflow:visible !important;}}
    [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] > div:has(.st-key-ustnav),
    .st-key-ustnav{{position:sticky !important;top:0 !important;z-index:999 !important;
        background:var(--k-yuzey0) !important;}}
    .st-key-ustnav{{padding:8px 0 10px !important;margin-bottom:8px !important;}}
    /* Sol sidebar: üstteki collapse-header boşluğunu kaldır */
    [data-testid="stSidebarHeader"]{{padding-top:0.4rem !important;padding-bottom:0 !important;
        min-height:0 !important;height:auto !important;}}
    [data-testid="stSidebarUserContent"]{{padding-top:0.4rem !important;}}
    section[data-testid="stSidebar"] .block-container{{padding-top:0.6rem !important;}}
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{{gap:0.5rem !important;}}
    </style>""", unsafe_allow_html=True)

    with st.container(key="ustnav"):
        cols = st.columns(len(moduller) + 2, gap="small")
        _yer = [moduller[0], None] + moduller[1:]          # None = komut paleti
        for c, m in zip(cols, _yer):
            if m is None:
                with c:
                    _palet_ciz(ak, yet)
                continue
            ad, mod, ikon = m
            # on_click: tıklama, sayfa çizilmeden ÖNCE işlenir → hedef sayfa
            # TEK çalışmada çizilir. Eskiden düğme ardından yeniden çalıştırma deseni her
            # geçişte programı iki kez baştan sona çalıştırıyordu.
            c.button(ad, key=f"top_{mod}", icon=ikon, help=ad,
                     type="primary" if aktif == mod else "secondary",
                     use_container_width=True, on_click=_sayfaya_git, args=(mod,))
        with cols[-1]:
            _talep_dugmesi()            # Talep Merkezi: üst menünün en sağında

    # Sayfa sekmeleri: modüllerin sayfa menüsü buraya çizilir (shared/gezinme.sayfa_menusu).
    # Geri almak için shared/gezinme.py → MENU_UST = False (menüler kenar çubuğuna döner).
    from shared.gezinme import serit_kur, MENU_UST
    if MENU_UST:
        serit_kur(st.container(key="sayfa_seridi"))


def _palet_kosul(kosul, kullanici):
    """Kayıt defterindeki koşullu sayfalar (shared/gezinme.py) — modüllerin kendi
    menü süzgeçleriyle aynı kural."""
    try:
        if kosul == "kar":
            from shared.kar_gizle import kar_gorunur
            return bool(kar_gorunur())
        if kosul == "toplam_aktifler":
            from kayranacc.main import _toplam_aktifler_yetkilileri
            return str(kullanici or "").lower().strip() in _toplam_aktifler_yetkilileri()
    except Exception:
        return False
    return True


def _palet_ciz(ak, yet):
    """Ctrl+K komut paleti (shared/palet.py). Çizilemezse eski Arama sekmesi."""
    try:
        from shared.palet import palet
        _ozel = {o for o in ("yonetim", "kullanici_yonetimi") if ozel_yetki(ak, o)}
        palet(yet, _ozel, ak, _palet_kosul)
    except Exception:
        st.button("Arama", key="top_arama", icon=":material/search:",
                  type="primary" if st.session_state.get("aktif_uygulama") == "arama" else "secondary",
                  use_container_width=True, on_click=_sayfaya_git, args=("arama",))

def portal_sidebar(kompakt=False):
    """Streamlit'in resmi sidebar'ina KAYRAN'in navigasyonunu cizer."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    aktif_sayfa = st.session_state.get("aktif_uygulama", "anasayfa")
    # Aktif sayfayı URL'ye yaz → tarayıcı yenilense de aynı sayfada kal
    try:
        if st.query_params.get("s") != aktif_sayfa:
            st.query_params["s"] = aktif_sayfa
    except Exception:
        pass
    from shared.gezinme import adres_yaz
    adres_yaz(aktif_sayfa)          # ?p= seçili sayfa (shared/gezinme.py)
    yetkiler = kullanici_yetkileri(aktif_kullanici)
    st.markdown(
        """<style>
@media (max-width: 768px) {
section[data-testid="stSidebar"] { width: 85vw !important; min-width: 0 !important; }
.main .block-container { padding-top: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
}
@media (max-width: 480px) {
input, textarea, select { font-size: 16px !important; }
}
</style>""",
        unsafe_allow_html=True
    )
    st.markdown(
        '<style>'
        # Sol menü zemini, yazı rengi ve düğmeleri: shared/tasarim.SIDEBAR_CSS
        # (eskiden burada her yazı mavi boyanıyordu: '* {color:mavi}').
        'button[data-testid="stBaseButton-headerNoPadding"],'
        '[data-testid="stSidebarCollapsedControl"]{'
        'background:color-mix(in srgb,var(--k-metin) 5%,transparent) !important;'
        '}'
        'button[data-testid="stBaseButton-headerNoPadding"] *,'
        '[data-testid="stSidebarCollapsedControl"] *{'
        'color:color-mix(in srgb,var(--k-metin) 70%,transparent) !important;'
        'fill:color-mix(in srgb,var(--k-metin) 70%,transparent) !important;'
        '}'
        'button[data-testid="stBaseButton-headerNoPadding"] span:not(.material-symbols-rounded):not(.material-symbols-outlined),'
        '[data-testid="stSidebarCollapsedControl"] span:not(.material-symbols-rounded):not(.material-symbols-outlined){'
        'font-size:0 !important;'
        '}'
        'button[data-testid="stBaseButton-headerNoPadding"] svg,'
        '[data-testid="stSidebarCollapsedControl"] svg{'
        'font-size:initial !important;'
        'width:18px !important;'
        'height:18px !important;'
        '}'
        'header[data-testid="stHeader"] *,'
        '.stAppToolbar *,'
        '.stAppDeployButton *{'
        'color:color-mix(in srgb,var(--k-metin) 65%,transparent) !important;'
        '}'
        'header[data-testid="stHeader"] svg,'
        '.stAppToolbar svg{'
        'fill:color-mix(in srgb,var(--k-metin) 65%,transparent) !important;'
        '}'
        '::-webkit-scrollbar{width:10px;height:10px;}'
        '::-webkit-scrollbar-track{background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));}'
        '::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--k-metin) 15%,transparent);border-radius:6px;}'
        '::-webkit-scrollbar-thumb:hover{background:color-mix(in srgb,var(--k-metin) 25%,transparent);}'
        '</style>',
        unsafe_allow_html=True
    )

    with st.sidebar:
        # Logo + KAYRAN başlığı (stil: tasarim.SIDEBAR_CSS → .k-sb-marka)
        st.markdown('<div class="k-sb-marka">' + KAYRAN_LOGO_SVG +
                    '<div><b>KAYRAN</b><br><span>Workspace</span></div></div>',
                    unsafe_allow_html=True)


        # ── Yeni sekmede aç: native <details> (Streamlit expander ikon fontu sorununu önler) ──
        _u = aktif_kullanici
        _t = _oturum_token(_u)
        # Herkes tüm bağlantıları görür; yetkisizler tıklayınca 🔒 uyarısı alır.
        _yeni_sekme = [("🏠 Anasayfa", "anasayfa"), ("🔍 Arama", "arama"),
                       ("📊 Yönetim P&L", "yonetim"), ("💰 Muhasebe", "kayranacc"),
                       ("📦 Ürün Yönetimi", "kayranpm"), ("🏬 Depo", "depo"),
                       ("🚢 İthalat", "ithalat"), ("🛒 Satış", "satis"),
                       ("🔧 Teknik Servis", "teknikservis")]
        _lh = ('<details style="margin:0 0 10px"><summary style="cursor:pointer;color:var(--k-silik);'
               'font-size:11px;font-weight:600;letter-spacing:.4px;'
               'padding:2px 2px 6px;outline:none;list-style-position:inside">↗ Yeni sekmede aç</summary>'
               '<div style="display:flex;flex-direction:column;gap:8px;margin-top:8px">')
        # ÖNEMLİ: Yeni oturum sistemi ?u parametreli ESKİ linkleri güvenlik gereği
        # geçersiz sayar; link artık MEVCUT oturum token'ıyla (?t=...) üretilir.
        # Böylece yeni sekme, aynı tarayıcıda TEKRAR GİRİŞ İSTEMEDEN açılır.
        _tok_aktif = ""
        try:
            _tok_aktif = st.query_params.get("t", "")
        except Exception:
            pass
        for _ad, _mod in _yeni_sekme:
            _lh += (f'<a href="?t={_tok_aktif}&s={_mod}" target="_blank" '
                    f'style="display:block;padding:8px 12px;background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));'
                    f'border:1px solid color-mix(in srgb,var(--k-metin) 7%,transparent);border-radius:8px;color:var(--k-mor2);'
                    f'text-decoration:none;font-size:13px;font-weight:400">{_ad} ↗</a>')
        _lh += ('</div><div style="color:var(--k-silik);font-size:11px;margin-top:8px;padding:0 8px;'
                'line-height:1.4">Tek tık veya fare orta tuşu (scroll) ile yeni sekmede açılır.</div></details>')
        st.markdown(_lh, unsafe_allow_html=True)

        if aktif_sayfa in ("anasayfa", "kayrantsw", "sifre_degistir", "hesap_makinesi", "kullanici_yonetimi", "sistem_kayitlari", "tasarim_rehberi", "cop_kutusu", "yukleme_gecmisi", "veri_sagligi", "soru"):
            # Kişi satırı + çıkış (modül sol menüleriyle AYNI düzen: shared.utils.sidebar_ust)
            from shared.utils import sidebar_kullanici as _sb_kisi
            _kc1, _kc2 = st.columns([3, 1.4], gap="small", vertical_alignment="center")
            _kc1.markdown(_sb_kisi(aktif_kullanici), unsafe_allow_html=True)
            if _kc2.button("Çıkış", key="nav_cikis", icon=":material/logout:", use_container_width=True):
                from shared.oturum import cikis_yap
                cikis_yap()

            # Görünüm: koyu / açık (kullanıcı bazlı, kullanici_tercih tablosu)
            from shared.tasarim import aktif_tema as _aktif_tema
            _tema_sec = st.segmented_control(
                "Görünüm", ["Koyu", "Açık"], key="tema_secim",
                default="Açık" if _aktif_tema() == "acik" else "Koyu",
                label_visibility="collapsed")
            _tema_yeni = "acik" if _tema_sec == "Açık" else "koyu"
            if _tema_yeni != _aktif_tema():
                from shared.tercih import tema_yaz as _tema_yaz
                st.session_state["tema"] = _tema_yeni
                _tema_yaz(aktif_kullanici, _tema_yeni)
                st.rerun()

            # Soru sor: Türkçe soru → programın kendi hesaplarından cevap (shared/soru_ekran)
            st.button("Soru sor", icon=":material/forum:", key="nav_soru",
                      type="primary" if aktif_sayfa == "soru" else "secondary",
                      use_container_width=True, on_click=_sayfaya_git, args=("soru",))

            st.markdown('<div class="k-sb-baslik">Hesap</div>', unsafe_allow_html=True)

            # on_click → tek çalışmada sayfa değişir (st.rerun yok)
            st.button("Şifremi Değiştir", icon=":material/key:", key="nav_sifre_degistir",
                      type="primary" if aktif_sayfa == "sifre_degistir" else "secondary",
                      use_container_width=True, on_click=_sayfaya_git, args=("sifre_degistir",))

            # Çöp kutusu: herkes KENDİ sildiğini, sistem yöneticisi herkesinkini görür
            st.button("Çöp kutusu", icon=":material/delete:", key="nav_cop_kutusu",
                      type="primary" if aktif_sayfa == "cop_kutusu" else "secondary",
                      use_container_width=True, on_click=_sayfaya_git, args=("cop_kutusu",))

            # Yükleme geçmişi: herkes KENDİ yüklemelerini, sistem yöneticisi herkesinkini görür / geri alır
            st.button("Yükleme geçmişi", icon=":material/history:", key="nav_yukleme_gecmisi",
                      type="primary" if aktif_sayfa == "yukleme_gecmisi" else "secondary",
                      use_container_width=True, on_click=_sayfaya_git, args=("yukleme_gecmisi",))

            # Veri sağlığı: herkes yetkili olduğu modüllerin kontrollerini, sistem yöneticisi hepsini görür
            st.button("Veri sağlığı", icon=":material/health_and_safety:", key="nav_veri_sagligi",
                      type="primary" if aktif_sayfa == "veri_sagligi" else "secondary",
                      use_container_width=True, on_click=_sayfaya_git, args=("veri_sagligi",))

            if ozel_yetki(aktif_kullanici, "kullanici_yonetimi"):
                st.button("Kullanıcı Yönetimi", icon=":material/group:", key="nav_kullanici_yonetimi",
                          type="primary" if aktif_sayfa == "kullanici_yonetimi" else "secondary",
                          use_container_width=True, on_click=_sayfaya_git, args=("kullanici_yonetimi",))

            if ozel_yetki(aktif_kullanici, "kullanici_yonetimi"):
                st.button("Sistem Kayıtları", icon=":material/receipt_long:", key="nav_sistem_kayitlari",
                          type="primary" if aktif_sayfa == "sistem_kayitlari" else "secondary",
                          use_container_width=True, on_click=_sayfaya_git, args=("sistem_kayitlari",))

            if ozel_yetki(aktif_kullanici, "kullanici_yonetimi"):
                st.button("Tasarım Rehberi", icon=":material/palette:", key="nav_tasarim_rehberi",
                          type="primary" if aktif_sayfa == "tasarim_rehberi" else "secondary",
                          use_container_width=True, on_click=_sayfaya_git, args=("tasarim_rehberi",))

        else:
            uyg_adi_map = {"kayranacc": "Muhasebe & Finans", "kayranpm": "Ürün Yönetimi", "depo": "Depo Yönetimi", "ithalat": "İthalat", "teknikservis": "Teknik Servis", "satis": "Satış", "hesap_makinesi": "Hesap Makinesi"}
            uyg_adi = uyg_adi_map.get(aktif_sayfa, aktif_sayfa.capitalize())
            uyg_renk_map = {"kayranacc": trenk("mor2"), "kayranpm": trenk("pembe"), "depo": trenk("yesil2"), "ithalat": trenk("mavi"), "teknikservis": trenk("kirmizi"), "hesap_makinesi": trenk("amber2")}
            uyg_renk = uyg_renk_map.get(aktif_sayfa, trenk("mor2"))
            # Modül adı artık modülün kendi kimlik çipinde — mükerrer etiket kaldırıldı
            # Modüle tıklayınca soldaki menünün kayacağı hedef
            st.markdown('<div id="kayran-submenu-anchor"></div>', unsafe_allow_html=True)


def _arama_kutusu(yer="anasayfa"):
    """Global arama kutusu + gruplu sonuçlar (özet + git/stok kartı).

    HIZ: Arama kendi içinde yenilenen bir parça (st.fragment). Eskiden kutuya
    her yazışta TÜM program baştan çalışıyordu (menü, sidebar, ana sayfa
    kartları, Bugün paneli…); artık yalnız arama sonuçları yenilenir.
    Sonuçtan bir modüle geçiş tüm sayfayı yeniler (st.rerun(scope="app"))."""
    _arama_parcasi(yer)


@st.fragment
def _arama_parcasi(yer):
    terim = st.text_input(
        "🔍 Ara",
        key=f"global_arama_{yer}",
        placeholder="Ara ya da sor: SKU, firma, sipariş no… ya da 'geçen ay en çok satan 5 ürün'   (Ctrl+K)",
        label_visibility="collapsed",
    )
    if terim and yer == "anasayfa":
        # Soru gibi okunuyorsa: önce "Programa sor" (shared/soru_ekran), veri araması altta sürer
        from shared.soru_ekran import anlasilir_mi, sor
        if anlasilir_mi(terim):
            _q1, _q2 = st.columns([5, 1.4], vertical_alignment="center")
            _q1.caption("Bu bir soru gibi görünüyor; program kendi hesaplarından cevaplayabilir.")
            if _q2.button("Programa sor", icon=":material/forum:", key=f"ara_sor_{yer}", type="primary",
                          use_container_width=True):
                sor(terim)
                st.rerun(scope="app")
    if not terim or len(terim.strip()) < 2:
        if yer == "sayfa":
            st.caption("En az 2 karakter yazın. Ürün (SKU/ad/barkod), cari, sipariş no, "
                       "seri no, servis no ve tedarikçi aranır.")
        return
    from shared.arama import ara
    sonuclar = ara(terim)
    if not sonuclar:
        st.info("Sonuç bulunamadı.")
        return
    _toplam = sum(len(v) for v in sonuclar.values())
    st.caption(f"{_toplam} sonuç")

    def _git(modul):
        st.session_state.aktif_uygulama = modul
        st.rerun(scope="app")      # parça içinden: tüm sayfa yeni modülle çizilsin

    # 📦 Ürünler — özet + Stok Kartı (modal)
    if sonuclar.get("urunler"):
        st.markdown(f"**Ürünler ({len(sonuclar['urunler'])})**")
        for u in sonuclar["urunler"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"`{u.get('sku','')}` — {u.get('urun_adi','') or '—'}  ·  "
                        f"{u.get('marka','') or ''} · ₺{u.get('satis_fiyati') or 0}")
            if c2.button("Stok Kartı", key=f"ara_u_{yer}_{u.get('sku')}", use_container_width=True):
                try:
                    from kayranpm.stok_karti import goster
                    goster(u.get("sku"))
                except Exception:
                    _git("kayranpm")

    # 🏢 Cariler → Muhasebe
    if sonuclar.get("cariler"):
        st.markdown(f"**Cariler ({len(sonuclar['cariler'])})**")
        for f in sonuclar["cariler"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{f.get('firma_adi','') or '—'}  ·  kod: {f.get('firma_kodu','') or '—'}")
            if c2.button("→ Muhasebe", key=f"ara_c_{yer}_{f.get('id', f.get('firma_kodu'))}",
                         use_container_width=True):
                _git("kayranacc")

    # 🧾 Satışlar → Satış
    if sonuclar.get("satislar"):
        st.markdown(f"**Satışlar ({len(sonuclar['satislar'])})**")
        for s in sonuclar["satislar"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{str(s.get('tarih',''))[:10]} · {s.get('kanal','') or '—'} · "
                        f"`{s.get('sku','')}` · sipariş: {s.get('siparis_no','') or '—'} · "
                        f"{s.get('adet',0)} ad")
            if c2.button("→ Satış", key=f"ara_s_{yer}_{s.get('id')}", use_container_width=True):
                _git("satis")

    # 🚢 İthalat → İthalat
    if sonuclar.get("ithalat"):
        st.markdown(f"**İthalat ({len(sonuclar['ithalat'])})**")
        for d in sonuclar["ithalat"]:
            c1, c2 = st.columns([5, 1])
            _belge = d.get("pi_no") or d.get("dosya_no") or d.get("ithalat_takip_no") or "—"
            c1.markdown(f"{str(d.get('tarih',''))[:10]} · belge: {_belge} · "
                        f"{d.get('tedarikci','') or '—'} · {d.get('mense_ulke','') or ''}")
            if c2.button("→ İthalat", key=f"ara_i_{yer}_{d.get('id', _belge)}", use_container_width=True):
                _git("ithalat")

    # 🔧 Servis → Teknik Servis
    if sonuclar.get("servis"):
        st.markdown(f"**Teknik Servis ({len(sonuclar['servis'])})**")
        for t in sonuclar["servis"]:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"servis: {t.get('servis_form_no','') or '—'} · seri: {t.get('seri_no','') or '—'} · "
                        f"{t.get('stok_adi','') or t.get('sku','') or ''} · {t.get('musteri','') or ''}")
            if c2.button("→ Servis", key=f"ara_t_{yer}_{t.get('kayit_id', t.get('servis_form_no'))}",
                         use_container_width=True):
                _git("teknikservis")


def _bugun_panel(aktif_kullanici, yetkiler):
    """Ana sayfa 'Bugün' paneli — veri shared/bugun.py'de, burada yalnız çizim.
    Her madde ilgili modülü açan bir düğmeyle gelir."""
    from shared import bugun as _bgn
    _maddeler = _bgn.topla(
        yetkiler,
        talep_yoneticisi=ozel_yetki(aktif_kullanici, "talep_yonetici"),
        sistem_yoneticisi=ozel_yetki(aktif_kullanici, "kullanici_yonetimi"),
    )
    _kritik = sum(1 for m in _maddeler if m["oncelik"] == "kritik")
    _ozet = (f'{len(_maddeler)} konu' + (f' · <span style="color:var(--k-kirmizi)">{_kritik} acil</span>' if _kritik else '')
             ) if _maddeler else "her şey yolunda"
    st.markdown(_bgn.css(), unsafe_allow_html=True)
    st.markdown(
        f'<div class="k-ana-bolum">Bugün<span>{_ozet}</span></div>',
        unsafe_allow_html=True)
    with st.container(key="bugun_panel"):
        if not _maddeler:
            st.markdown(_bgn.bos_html(), unsafe_allow_html=True)
        for _m in _maddeler:
            _c1, _c2 = st.columns([12, 2], vertical_alignment="center")
            _c1.markdown(_bgn.satir_html(_m), unsafe_allow_html=True)
            if _m["hedef"] == "talep":
                # Talep Merkezi her sayfada sağ alttaki ✉️ düğmesinde açılır
                _c2.markdown('<div style="color:var(--k-silik);font-size:11px;text-align:center">'
                             'sağ alttaki Talep</div>', unsafe_allow_html=True)
            else:
                _c2.button("Aç", key=f"bgn_{_m['anahtar']}", icon=":material/arrow_forward:",
                           use_container_width=True, on_click=_sayfaya_git, args=(_m["hedef"],))


def _veri_guncelligi(aktif_kullanici, yetkiler):
    """Dönemsel Excel yüklemeleri: her kaynak için geri sayım kartı — HERKES görür.
    Veri ve hesap shared/yukleme_takvimi.py'de; burada yalnız çizim ve iki eylem:
    'bu dönem veri yok' (modül yetkilisi / sistem yöneticisi) ve ayarlar (sistem yöneticisi)."""
    try:
        from shared import yukleme_takvimi as _yt
        _bg = _yt._bugun()
        _dl = _yt.tum_durumlar(_bg.isoformat())
    except Exception as _e:  # noqa: BLE001
        try:
            from shared.hata_log import kaydet as _hk
            _hk("anasayfa.veri_guncelligi", _e)
        except Exception:
            pass
        return
    if not _dl:
        return
    _say = {s: sum(1 for d in _dl if d["seviye"] == s) for s in ("gecikti", "yaklasiyor", "guncel")}
    _oz = " · ".join(p for p in (
        f'<span style="color:var(--k-kirmizi)">{_say["gecikti"]} gecikti</span>' if _say["gecikti"] else "",
        f'<span style="color:var(--k-amber)">{_say["yaklasiyor"]} yaklaşıyor</span>' if _say["yaklasiyor"] else "",
        f'{_say["guncel"]} güncel' if _say["guncel"] else "") if p)
    st.markdown(f'<div class="k-ana-bolum">Veri güncelliği<span>{_oz}</span></div>', unsafe_allow_html=True)
    _sira = {"gecikti": 0, "yaklasiyor": 1, "guncel": 2}
    _dl = sorted(_dl, key=lambda d: (_sira[d["seviye"]], d.get("kalan_gun") or 0))
    _kol = st.columns(3)
    for _i, _d in enumerate(_dl):
        _kol[_i % 3].markdown(_yt.kart_html(_d), unsafe_allow_html=True)

    _sistem = ozel_yetki(aktif_kullanici, "kullanici_yonetimi")
    _e1, _e2, _ = st.columns([1.3, 1, 2.2])
    _isaretlenebilir = [d for d in _dl if d["seviye"] == "gecikti"
                        and (_sistem or yetkiler.get(d["modul"]) or d.get("sorumlu") == aktif_kullanici)]
    if _isaretlenebilir:
        with _e1.popover("Bu dönem veri yok", icon=":material/event_busy:", use_container_width=True):
            st.caption("Bir dönemde gerçekten yüklenecek veri yoksa (ör. o ay iade olmadı) işaretle; "
                       "o dönem eksik sayılmaz, hatırlatma kalkar.")
            _sec = st.selectbox("Kaynak", _isaretlenebilir, key="yt_atla_kaynak",
                                format_func=lambda d: d["ad"])
            _don = st.selectbox("Dönem", _sec["eksik"], key=f"yt_atla_donem_{_sec['anahtar']}",
                                format_func=lambda p: _yt.donem_adi(_sec["siklik"], p))
            if st.button("Veri yok olarak işaretle", key="yt_atla_btn", type="primary",
                         use_container_width=True):
                _yt.atla(_sec["anahtar"], _don)
                st.toast(f'{_sec["ad"]} · {_yt.donem_adi(_sec["siklik"], _don)}: veri yok olarak işaretlendi')
                st.rerun()
    if _sistem:
        # Pencere: açılır menü dar kalıyor, tablonun "Takipte" sütunu kesiliyordu
        @st.dialog("Veri güncelliği · takvim ayarları", width="large")
        def _yt_ayar_penceresi():
            st.caption("Sıklık, son gün ve sorumlu. Haftalık: son gün hafta günü (0 = Pazartesi) · aylık / "
                       "çeyreklik: ayın kaçı (1–28). Sorumlunun adı uyarılarda görünür; sorumlu kendi "
                       "kaynağı için \"bu dönem veri yok\" işaretleyebilir.")
            import pandas as _pd
            _ay = _yt._ayar(_yt.AYAR_ANAHTAR, {})
            _df = _pd.DataFrame([{
                "anahtar": k["anahtar"], "Kaynak": k["ad"],
                "Sıklık": _yt.SIKLIKLAR[_yt.kaynak_ayari(k["anahtar"], _ay)["siklik"]],
                "Son gün": int(_yt.kaynak_ayari(k["anahtar"], _ay)["son_gun"]),
                "Sorumlu": _yt.kaynak_ayari(k["anahtar"], _ay)["sorumlu"],
                "Takipte": _yt.kaynak_ayari(k["anahtar"], _ay)["aktif"]} for k in _yt.KAYNAKLAR])
            _ed = st.data_editor(
                _df, hide_index=True, key="yt_ayar_editor", use_container_width=True,
                column_order=["Kaynak", "Sıklık", "Son gün", "Sorumlu", "Takipte"],
                column_config={
                    "Kaynak": st.column_config.TextColumn(disabled=True),
                    "Sıklık": st.column_config.SelectboxColumn(options=list(_yt.SIKLIKLAR.values()), required=True),
                    "Son gün": st.column_config.NumberColumn(min_value=0, max_value=28, step=1,
                                                             help="Haftalık: 0=Pazartesi … 6=Pazar"),
                    "Sorumlu": st.column_config.TextColumn(help="Kullanıcı adı (ör. serdar) — uyarılarda adı görünür"),
                    "Takipte": st.column_config.CheckboxColumn()})
            if st.button("Kaydet", key="yt_ayar_kaydet", type="primary", icon=":material/save:"):
                _ters = {v: k for k, v in _yt.SIKLIKLAR.items()}
                _yt.ayar_kaydet({r["anahtar"]: {"siklik": _ters.get(r["Sıklık"], "aylik"),
                                                "son_gun": int(r["Son gün"] or 0), "aktif": bool(r["Takipte"]),
                                                "sorumlu": str(r["Sorumlu"] or "").strip().lower()}
                                 for _, r in _ed.iterrows()})
                st.toast("Takvim ayarları kaydedildi")
                st.rerun()

        if _e2.button("Takvim ayarları", icon=":material/tune:", use_container_width=True, key="yt_ayar_ac"):
            _yt_ayar_penceresi()



def _bildirim_karti(b):
    """Tek bildirim kartı — açılır pencere ve ana sayfa listesi aynı görünümü kullanır."""
    _gnd = kisi_adi(b.get("gonderen") or "Sistem")
    _zmn = str(b.get("olusturma_tarihi", ""))[:16].replace("T", " ")
    return (f'<div class="k-kart" style="margin:8px 0;padding:12px 16px">'
            f'<div style="color:var(--k-metin);font-size:13px;line-height:1.6">{b.get("mesaj", "")}</div>'
            f'<div class="k-alt" style="margin-top:8px">{_gnd} · {_zmn}</div></div>')

def anasayfa():
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    yetkiler = kullanici_yetkileri(aktif_kullanici)

    st.markdown(portal_css(), unsafe_allow_html=True)

    # Duyuruyu Supabase'den dinamik oku
    _duyuru_aktif, _duyuru_metni = get_duyuru()
    if _duyuru_aktif and _duyuru_metni:
        st.markdown(
            f'<div style="background:linear-gradient(90deg,color-mix(in srgb,var(--k-mavi) 12%,transparent),color-mix(in srgb,var(--k-mor) 12%,transparent),color-mix(in srgb,var(--k-pembe) 12%,transparent));border:1px solid color-mix(in srgb,var(--k-mor) 20%,transparent);border-radius:12px;padding:8px 16px;text-align:center;color:var(--k-mor2);font-size:13px;font-weight:400;margin-bottom:24px;animation:fadeUp 0.5s ease-out">{_duyuru_metni}</div>',
            unsafe_allow_html=True
        )

    # Global arama kutusu
    _arama_kutusu("anasayfa")

    # Saate göre selamlama — İstanbul saat dilimi (UTC+3)
    _ist_now = datetime.utcnow() + timedelta(hours=3)
    saat = _ist_now.hour
    if saat < 12: selamlama = "Günaydın"
    elif saat < 18: selamlama = "İyi günler"
    else: selamlama = "İyi akşamlar"

    # ─────────────────────────────────────────────────────────────────────
    # KULLANICIYA BİLDİRİM — zorunlu popup + üst şerit (herkes, ibrahim dahil)
    # ─────────────────────────────────────────────────────────────────────
    _bildirimler = get_okunmamis_bildirimler(aktif_kullanici)
    _dlg = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if _bildirimler and _dlg:
        @_dlg("🔔 Yeni Bildirimler")
        def _zorunlu_bildirim_modal():
            st.markdown(f"**{len(_bildirimler)} okunmamış bildirimin var — lütfen oku:**")
            for _bm in _bildirimler:
                st.markdown(_bildirim_karti(_bm), unsafe_allow_html=True)
            if st.button("✓ Okudum, kapat", type="primary", use_container_width=True, key="_modal_okundu_btn"):
                tumunu_okundu_isaretle(aktif_kullanici)
                st.rerun()
        _zorunlu_bildirim_modal()
    _frag = getattr(st, "fragment", None)
    if _frag:
        @_frag(run_every="15s")
        def _bildirim_izleyici():
            try:
                _yeni_say = len(get_okunmamis_bildirimler(aktif_kullanici))
            except Exception:
                return
            _eski = st.session_state.get("_bildirim_say_izle")
            st.session_state["_bildirim_say_izle"] = _yeni_say
            if _eski is not None and _yeni_say > _eski:
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                try:
                    st.rerun(scope="app")
                except TypeError:
                    st.rerun()
        _bildirim_izleyici()

    # (📬 Gelen Talepler — aşağıya, istatistik kartlarının altına taşındı ve kapalı panel yapıldı)

    # ─────────────────────────────────────────────────────────────────────
    # ─── KARŞILAMA: selam + tarih + günün piyasa şeridi ───
    # Sayfanın TEK hareketli anı burası: oturumun ilk açılışında selam ve
    # şerit bir kez yumuşakça belirir (Streamlit aynı öğeyi yeniden çizmez,
    # sonraki tıklamalarda tekrar oynamaz). Eskiden her bölüm ayrı ayrı
    # kayarak geliyordu.
    _gunler_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    _aylar_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
                 "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    _now_h = _ist_now
    _tarih_str = f"{_now_h.day} {_aylar_tr[_now_h.month-1]} {_now_h.year}, {_gunler_tr[_now_h.weekday()]}"
    st.markdown(_ana_css(), unsafe_allow_html=True)

    # Günün kuru / altın / hava / tatil (şeritte gösterilir)
    try:
        from gunluk import get_doviz, get_gram_altin, get_hava, get_yaklasan_tatil
        _dv = get_doviz()
        # Tarihsel kur için: o günün USD/TL kurunu kaydet (idempotent, günde 1)
        try:
            if _dv.get("USD") and _kur_kaydi_gerekli():
                from kayranacc.database import kur_kaydet
                from shared.utils import tr_today
                kur_kaydet(tr_today(), _dv["USD"])
        except Exception as _ke:
            from shared.hata_log import kaydet as _hk
            _hk("anasayfa.kur_kaydet", _ke)
        _altin = get_gram_altin()
        _hava = get_hava()
        _tatil = get_yaklasan_tatil()
    except Exception as _ge:
        from shared.hata_log import kaydet as _hk
        _hk("anasayfa.gunluk", _ge)
        _dv, _altin, _hava, _tatil = {}, None, None, None

    def _hucre(ad, deger, alt="", baslik=""):
        _t = f' title="{baslik}"' if baslik else ""
        _a = f"<small>{alt}</small>" if alt else ""
        return f'<div class="k-ana-hucre"{_t}><span>{ad}</span><b>{deger}</b>{_a}</div>'

    _serit = []
    if _dv.get("USD"):
        _serit.append(_hucre("Dolar", f"₺{tr_sayi(_dv['USD'], 2)}",
                             f"Euro ₺{tr_sayi(_dv['EUR'], 2)}" if _dv.get("EUR") else ""))
    if _altin:
        _serit.append(_hucre("Gram altın", f"₺{tr_sayi(_altin)}"))
    if _hava and _hava.get("sicaklik") is not None:
        _serit.append(_hucre("Hava", f"{_hava['sicaklik']}°",
                             f"{_hava.get('durum', '')} · {_hava.get('sehir', '')}".strip(" ·")))
    if _tatil:
        _td = _tatil["tarih"]
        _ttar = f"{_td.day} {_aylar_tr[_td.month-1]}"
        if _tatil["bugun"]:
            _serit.append(_hucre("Bugün tatil", _tatil["ad"]))
        else:
            _serit.append(_hucre(_tatil["ad"], f"{_tatil['kalan_gun']} gün", _ttar,
                                 baslik=f"{_tatil['ad']} · {_ttar}"))
    st.markdown(
        '<div class="k-ana-karsila">'
        f'<div class="k-ana-bas"><h1>{selamlama}, {kisi_adi(aktif_kullanici)}</h1>'
        f'<span>{_tarih_str}</span></div>'
        + (f'<div class="k-ana-serit">{"".join(_serit)}</div>' if _serit else "")
        + '</div>',
        unsafe_allow_html=True)

    # ─── SALT-OKUR ŞERİDİ ───
    if st.session_state.get("salt_okur"):
        from shared.tasarim import mesaj as _mesaj
        st.markdown(_mesaj("uyari", "Salt-okur oturum: tüm modülleri görebilirsin; "
                                    "veri ekleme, değiştirme ve silme kapalı."),
                    unsafe_allow_html=True)

    # ─── BUGÜN — dikkat gerektiren işler (D2) ───
    _bugun_panel(aktif_kullanici, yetkiler)

    # ─── VERİ GÜNCELLİĞİ — dönemsel Excel'ler, geri sayım (herkes görür) ───
    _veri_guncelligi(aktif_kullanici, yetkiler)

    # ─── PATRON PANOSU — yalnızca yetkili kullanıcıya (sabah kokpiti) ───
    _patron_gor = ozel_yetki(aktif_kullanici, "patron_panel")
    if _patron_gor:
        try:
            # Yeniden tasarım (Ekim 2026): shared/patron.py — tek kaynak, kıyaslı kartlar,
            # takvim günlü grafik, kanal payı, tıklanır veri kalitesi
            from shared.patron import render as _patron_panosu
            _patron_panosu(_sayfaya_git)
        except Exception as _pe:
            from shared.hata_log import kaydet as _hk
            _hk("anasayfa.patron_panosu", _pe)

    # ─────────────────────────────────────────────────────────────────────
    # ─── İŞ KPI KARTLARI (gerçek veriden, yetkiye göre, güvenli) ───

    def _kpi_card(label, value, sub, accent):
        # Ortak KPI kartı (tasarim.kpi_serit ile aynı dil: k-kart + renkli sol şerit).
        # `accent` RENK anahtarıdır ("yesil"); tema değişince renk de değişir.
        _c = rv(accent)
        return (f'<div class="k-kart" data-akscent style="border-left-color:{_c}">'
                f'<div class="k-ana-kpi-ad">{label}</div>'
                f'<div class="k-deger">{value}</div>'
                f'<div class="k-alt" style="color:var(--k-soluk)">{sub}</div></div>')

    import datetime as _kdt
    _ay_ilk = _kdt.date.today().replace(day=1).isoformat()
    _bugun_iso = _kdt.date.today().isoformat()
    # Finansal rakamları (net kâr, ciro, marj) yalnızca yetkili görür — diğer personele gösterilmez
    _finans_gor = (aktif_kullanici or "").lower() == "ibrahim"
    _rozet = {}
    # "Erişim x/y" kartı kaldırıldı (bilgi değil süs). Net Kâr, Patron
    # Panosu'nda zaten var; aynı rakam iki yerde (üstelik farklı hesapla)
    # görünmesin diye yalnız pano GÖRÜNMEYEN yetkiliye gösterilir.
    kpi_html = []

    if _finans_gor and not _patron_gor:
        try:
            from satis.database import get_satislar_yalin, ozet_hesapla
            _top, _, _ = ozet_hesapla(get_satislar_yalin(_ay_ilk, _bugun_iso))
            # + Alınan destekler (sellout/marketing/rebate — ay bazlı gelir)
            _ad_usd = 0.0
            try:
                from kayranpm.ref_no import alinan_destek_ay_usd
                _ad_usd = float(alinan_destek_ay_usd() or 0)
            except Exception:
                _ad_usd = 0.0
            _genel_kar = _top["net_kar"] + _ad_usd
            _alt = f"Ciro ${tr_sayi(_top['ciro'])} · %{tr_sayi(_top['marj'], 1)}"
            if _ad_usd:
                _alt += f" · destek ${tr_sayi(_ad_usd)} dahil"
            kpi_html.append(_kpi_card("Bu ay net kâr", f"${tr_sayi(_genel_kar)}",
                                      _alt, "yesil" if _genel_kar >= 0 else "kirmizi"))
        except Exception:
            pass
    if yetkiler.get("ithalat"):
        try:
            from ithalat.database import IN_TRANSIT_DURUMLAR
            # Hafif: satır indirmeden COUNT. Başarısızsa eski tam-tablo yoluna düş.
            _yol = _hizli_sayim("ithalat_dosyalari", "durum", IN_TRANSIT_DURUMLAR)
            if _yol is None:
                from ithalat.database import get_dosyalar
                _yol = sum(1 for d in get_dosyalar()
                           if str(d.get("durum", "")).strip() in IN_TRANSIT_DURUMLAR)
            kpi_html.append(_kpi_card("Yoldaki ithalat", f"{_yol}", "dosya yolda", "mavi"))
            if _yol:
                _rozet["ithalat"] = f"{_yol} yolda"
        except Exception:
            pass
    if yetkiler.get("teknikservis"):
        try:
            _ts_n = _hizli_sayim("ts_kayitlar")
            if _ts_n is None:
                from teknikservis.database import get_kayitlar
                _ts_n = len(get_kayitlar())
            kpi_html.append(_kpi_card("Teknik servis", f"{_ts_n}", "açık kayıt", "kirmizi2"))
            if _ts_n:
                _rozet["teknikservis"] = f"{_ts_n} açık"
        except Exception:
            pass
    if yetkiler.get("kayranpm"):
        try:
            _kmp_n = _hizli_sayim("kampanyalar", "durum", ["aktif"])
            if _kmp_n is None:
                from kayranpm.database import get_kampanyalar
                _kmp_n = len(get_kampanyalar(durum='aktif'))
            kpi_html.append(_kpi_card("Kampanya", f"{_kmp_n}", "aktif kampanya", "pembe"))
            if _kmp_n:
                _rozet["kayranpm"] = f"{_kmp_n} kampanya"
        except Exception:
            pass

    if kpi_html:
        st.markdown('<div class="k-ana-bolum">İş özeti</div>'
                    '<div class="k-ana-kpi">' + "".join(kpi_html) + '</div>',
                    unsafe_allow_html=True)

    if _bildirimler:
        if True:
            _bil_html = (
                '<div style="background:linear-gradient(135deg,color-mix(in srgb,var(--k-mor) 12%,transparent),color-mix(in srgb,var(--k-mor) 8%,transparent));'
                'border:1px solid color-mix(in srgb,var(--k-mor) 30%,transparent);border-radius:16px;'
                'padding:16px 20px;margin-bottom:24px;animation:fadeUp 0.4s ease-out">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
                f'<div style="width:28px;height:28px;border-radius:8px;background:color-mix(in srgb,var(--k-mor) 25%,transparent);'
                f'display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0">🔔</div>'
                f'<span style="color:var(--k-mor2);font-size:13px;font-weight:700">'
                f'{len(_bildirimler)} yeni bildirim</span>'
                f'</div>'
            )
            for _b in _bildirimler:
                _bil_html += _bildirim_karti(_b)
            _bil_html += '</div>'
            st.markdown(_bil_html, unsafe_allow_html=True)
            if st.button("✓ Tümünü Okundu İşaretle", key="okundu_btn", use_container_width=False):
                tumunu_okundu_isaretle(aktif_kullanici)
                st.rerun()

    # ─── MODÜLLER — kartın TAMAMI tıklanır ───
    # Eskiden her kartın altında ayrı bir "Aç →" düğmesi vardı (7 düğme alt
    # alta, hepsi aynı ağırlıkta). Artık kartın kendisi düğme: görünmez bir
    # düğme kartı kaplar (klavyeyle Tab + Enter de çalışır), üstüne gelince
    # kart modül renginde belirginleşir ve ok ileri kayar.
    _mod_meta = [
        ("kayranacc", "Muhasebe & Finans", "Ödeme, çek, banka, cari ve aktifler"),
        ("satis", "Satış", "Sipariş girişi, kâr / P&L ve iade"),
        ("kayranpm", "Ürün Yönetimi", "Stok, sipariş önerisi, kampanya ve rapor"),
        ("ithalat", "İthalat", "Dosya, masraf, paçal maliyet ve teslim"),
        ("depo", "Depo", "Depo bazlı stok ve depolar arası sevk"),
        ("teknikservis", "Teknik Servis", "Servis, iade, değişim ve servis deposu"),
        ("yonetim", "Yönetim", "Toplam aktifler ve yönetim P&L"),
        ("hesap_makinesi", "Hesap Makinesi", "Maliyet ve fiyat hesapları"),
    ]
    _yonetim_gor = ozel_yetki(aktif_kullanici, "yonetim")
    _acik_mod = [m for m in _mod_meta
                 if (_yonetim_gor if m[0] == "yonetim" else yetkiler.get(m[0]))]
    if _acik_mod:
        st.markdown('<div class="k-ana-bolum">Modüller</div>', unsafe_allow_html=True)
        st.markdown("<style>" + "".join(
            f".st-key-hz_{_mk}{{--c:{rv(MODUL_RENK.get(_mk, 'mor'))};}}" for _mk, _, _ in _acik_mod)
            + "</style>", unsafe_allow_html=True)
        _sutun = 4
        for _ri in range(0, len(_acik_mod), _sutun):
            _cols = st.columns(_sutun, gap="small")
            for _ci, (_mk, _ad, _ds) in enumerate(_acik_mod[_ri:_ri + _sutun]):
                with _cols[_ci]:
                    with st.container(border=True, key=f"hz_{_mk}"):
                        _rz = _rozet.get(_mk)
                        st.markdown(
                            '<div class="k-hz-ust">'
                            f'<i>{k_ikon(MODUL_IKON.get(_mk, "apps"), 20)}</i>'
                            + (f'<em>{_rz}</em>' if _rz else "")
                            + f'{k_ikon("arrow_forward", 18)}</div>'
                            f'<div class="k-hz-ad">{_ad}</div><div class="k-hz-ac">{_ds}</div>',
                            unsafe_allow_html=True)
                        st.button(f"{_ad} modülünü aç", key=f"home_open_{_mk}",
                                  on_click=_sayfaya_git, args=(_mk,))
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    # GÜNLÜK GİRİŞ SERİSİ kullanıcı talebiyle KALDIRILDI.
    # 📬 Gelen Talepler HER SAYFADA sağ alttaki Talep düğmesinde (_talep_merkezi).

    # ─── YÖNETİM (sadece ibrahim) — kompakt kapalı paneller ───
    if aktif_kullanici.lower() == "ibrahim":
        st.markdown('<div class="k-ana-bolum">Yönetici araçları</div>', unsafe_allow_html=True)

        # 1) Aktif kullanıcılar & son giriş zamanları
        with st.expander("Aktif kullanıcılar ve son girişler", expanded=False, icon=":material/group:"):
            online_listesi = get_online_kullanicilar()
            # Kapalı açılır panelin içi de her çizimde çalışır; bu sorgu her
            # ana sayfa tıklamasında gidiyordu → 60 sn önbellekli.
            _son_giris_map = get_son_girisler()
            if not online_listesi:
                st.caption("Şu an aktif kullanıcı yok.")
            else:
                import datetime as _dt
                simdi = _dt.datetime.utcnow()
                cards_html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px;margin-bottom:4px">'
                for u in online_listesi:
                    k_adi = u.get("kullanici_adi", "?")
                    son_akt = u.get("son_aktivite", "")
                    try:
                        son_dt = _dt.datetime.fromisoformat(son_akt.replace("Z", ""))
                        fark_sn = int((simdi - son_dt).total_seconds())
                        zaman_str = f"{fark_sn}sn önce" if fark_sn < 60 else f"{fark_sn // 60}dk önce"
                    except Exception:
                        zaman_str = "az önce"
                    from shared.tasarim import bas_harf as _bh
                    ilk = _bh(k_adi)
                    cards_html += (
                        f'<div style="background:color-mix(in srgb,var(--k-yesil) 6%,transparent);border:1px solid color-mix(in srgb,var(--k-yesil) 20%,transparent);border-radius:10px;padding:8px 12px;display:flex;align-items:center;gap:8px">'
                        f'<div style="width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--k-yesil),var(--k-yesil));display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:13px;flex-shrink:0">{ilk}</div>'
                        f'<div style="overflow:hidden"><div style="color:var(--k-metin);font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{kisi_adi(k_adi)}</div>'
                        f'<div style="color:var(--k-yesil2);font-size:11px;font-weight:400">● {zaman_str}</div></div></div>'
                    )
                cards_html += '</div>'
                st.markdown(
                    f'<div style="margin-bottom:8px"><span style="color:var(--k-yesil2);font-size:13px;font-weight:600">{len(online_listesi)} kullanıcı aktif (son 5 dk)</span></div>'
                    + cards_html, unsafe_allow_html=True)
            if _son_giris_map:
                import datetime as _dt3
                sg_html = '<div style="margin-top:12px"><div style="font-size:11px;color:var(--k-silik);letter-spacing:1px;font-weight:700;text-transform:uppercase;margin-bottom:8px">Son giriş zamanları</div>'
                sg_html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px">'
                for _kg, _sa in sorted(_son_giris_map.items()):
                    _zs = "—"
                    try:
                        _raw = str(_sa).replace("Z", "+00:00")
                        _sdt = _dt3.datetime.fromisoformat(_raw)
                        if _sdt.tzinfo is not None:
                            _sdt = _sdt.astimezone(_dt3.timezone.utc).replace(tzinfo=None)
                        _ist = _sdt + _dt3.timedelta(hours=3)
                        _zs = _ist.strftime("%d.%m.%Y %H:%M")
                    except Exception:
                        _zs = "—"
                    _online_su = any(u.get("kullanici_adi") == _kg for u in online_listesi)
                    _renk = trenk("yesil") if _online_su else trenk("silik")
                    _bg = "rgba(16,185,129,0.06)" if _online_su else "rgba(255,255,255,0.02)"
                    _border = "rgba(16,185,129,0.15)" if _online_su else "rgba(255,255,255,0.06)"
                    sg_html += (
                        f'<div style="background:{_bg};border:1px solid {_border};border-radius:8px;padding:8px 12px;display:flex;align-items:center;justify-content:space-between">'
                        f'<span style="color:var(--k-metin);font-size:13px;font-weight:600">{kisi_adi(_kg)}</span>'
                        f'<span style="color:{_renk};font-size:11px;font-weight:600;font-family:JetBrains Mono,monospace;white-space:nowrap">{_zs}</span></div>'
                    )
                sg_html += '</div></div>'
                st.markdown(sg_html, unsafe_allow_html=True)

        # 2) Sistem duyurusu
        with st.expander("Sistem duyurusu", expanded=False, icon=":material/campaign:"):
            _mevcut_aktif, _mevcut_metni = get_duyuru()
            _durum_etiketi = "🟢 Aktif" if _mevcut_aktif else "🔴 Kapalı"
            st.caption(f"Durum: {_durum_etiketi}" + ((" — " + _mevcut_metni[:60] + ("..." if len(_mevcut_metni) > 60 else "")) if _mevcut_metni else ""))
            with st.form("duyuru_form", clear_on_submit=False):
                _yeni_aktif = st.checkbox("Duyuruyu aktifleştir", value=bool(_mevcut_aktif))
                _yeni_metni = st.text_input("Duyuru metni", value=_mevcut_metni, placeholder="Örn: Sistem bugün 18:00-19:00 arası bakımda.")
                _duyuru_kaydet = st.form_submit_button("Kaydet", type="primary", icon=":material/save:")
                if _duyuru_kaydet:
                    if set_duyuru(_yeni_aktif, _yeni_metni or ""):
                        st.success("✅ Duyuru kaydedildi.")
                        st.rerun()
                    else:
                        st.error("❌ Kayıt başarısız.")

        # 3) Bildirim gönder
        with st.expander("Bildirim gönder", expanded=False, icon=":material/notifications:"):
            _tum_kullanicilar = sorted(tum_kullanicilar() - {(aktif_kullanici or "").strip().lower()})
            with st.form("bildirim_form", clear_on_submit=True):
                _alici_sec = st.selectbox("Alıcı", ["Herkese Gönder"] + [k.capitalize() for k in _tum_kullanicilar])
                _bildirim_mesaj = st.text_area("Mesaj", placeholder="Kullanıcılara göndermek istediğin mesajı yaz...", height=90)
                _bildirim_gonder_btn = st.form_submit_button("Gönder", type="primary", icon=":material/campaign:")
                if _bildirim_gonder_btn:
                    if not _bildirim_mesaj or not _bildirim_mesaj.strip():
                        st.warning("⚠️ Mesaj boş olamaz.")
                    else:
                        if _alici_sec == "Herkese Gönder":
                            _ok2 = bildirim_gonder_herkese(_bildirim_mesaj.strip(), list(_tum_kullanicilar))
                            _alici_str = "herkese"
                        else:
                            _ok2 = bildirim_gonder(_alici_sec.lower(), _bildirim_mesaj.strip())
                            _alici_str = _alici_sec + " kişisine"
                        if _ok2:
                            st.success(f"✅ Bildirim {_alici_str} gönderildi!")
                        else:
                            st.error("❌ Bildirim gönderilemedi.")

    # ─── ALT BİLGİ — tek sakin satır ───
    # Kaldırılanlar: "Sistem Aktif" yeşil ışığı (hiçbir şeyi ölçmeden hep
    # yeşil yanıyordu — yanıltıcıydı), tanıtım cümleleri şeridi, kurumsal
    # açılır panel (iki bağlantısı buraya alındı) ve "✉️ düğmesini kullan" notu.
    yil = datetime.now().year
    st.markdown(
        '<div class="k-ana-alt">'
        f'<span>KAYRAN Workspace · © {yil} G5F Teknoloji</span>'
        '<span><a href="https://g5fteknoloji.com" target="_blank" rel="noopener noreferrer">g5fteknoloji.com</a>'
        '<a href="https://fazeon.com" target="_blank" rel="noopener noreferrer">fazeon.com</a></span>'
        '</div>',
        unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# 3.5) KAYRANTS&W — YAKINDA SİZLERLE
# ─────────────────────────────────────────────────────────────────────
def sistem_kayitlari():
    """🧾 Sistem Kayıtları — stok hareket defteri + hata kaydı (yönetici)."""
    import pandas as pd
    ben = (st.session_state.get("aktif_kullanici", "") or "").strip().lower()
    if not ozel_yetki(ben, "kullanici_yonetimi"):
        st.error("🔒 Bu sayfaya erişim yetkiniz yok.")
        return
    from shared.stok_defteri import gecmis
    from shared.hata_log import son_hatalar

    from shared.tasarim import baslik as _bsl
    st.markdown(_bsl(":material/receipt_long: Sistem kayıtları", "Stok ve hata kayıtları",
                     aciklama="Stok neden değişti, hangi işlem başarısız oldu, sistem nerede hata verdi · "
                              "kayıtlar kurulumdan sonraki olayları kapsar"), unsafe_allow_html=True)

    t1, t2, t3 = st.tabs([":material/warning: Başarısız stok işlemleri", ":material/history: Stok hareketleri",
                          ":material/bug_report: Hatalar"])

    def _tablo(rows):
        return pd.DataFrame([{
            "Zaman": str(r.get("zaman") or "")[:16].replace("T", " "),
            "SKU": r.get("sku") or "", "Depo": r.get("depo") or "", "Tür": r.get("tur") or "",
            "Önce": r.get("onceki"), "Sonra": r.get("sonraki"), "Değişim": r.get("degisim"),
            "Açıklama": r.get("aciklama") or "", "Kaynak": r.get("kaynak") or "",
            "Kullanıcı": r.get("kullanici") or "", "Hata": r.get("hata") or "",
        } for r in rows])

    with t1:
        rows = gecmis(limit=500, yalniz_basarisiz=True)
        if not rows:
            st.success("✅ Kayıtlı başarısız stok işlemi yok.")
        else:
            st.error(f"{len(rows)} stok işlemi uygulanamadı — bu satırlarda stok DEĞİŞMEDİ. "
                     "Genellikle ürün kartı eksikliği ya da bağlantı hatasıdır.")
            st.dataframe(_tablo(rows), hide_index=True, use_container_width=True)

    with t2:
        c1, c2 = st.columns([2, 1])
        _sku = c1.text_input("SKU", placeholder="boş bırakırsan son 300 hareket",
                             key="sk_sku").strip()
        _tur = c2.selectbox("Tür", ["Tümü", "cikis", "giris", "sevk", "aktarim", "sifirlama", "hata"],
                            key="sk_tur")
        rows = gecmis(sku=_sku or None, limit=300, tur=None if _tur == "Tümü" else _tur)
        if not rows:
            st.info("Kayıt yok.")
        else:
            st.dataframe(_tablo(rows), hide_index=True, use_container_width=True)

    with t3:
        _kr = st.toggle("Yalnız kritik", key="sk_kritik")
        rows = son_hatalar(limit=300, yalniz_kritik=_kr)
        if not rows:
            st.success("✅ Kayıtlı hata yok.")
        else:
            st.dataframe(pd.DataFrame([{
                "Zaman": str(r.get("zaman") or "")[:16].replace("T", " "),
                "Kritik": "🔴" if r.get("kritik") else "",
                "Yer": r.get("yer") or "", "Tür": r.get("tur") or "",
                "Mesaj": r.get("mesaj") or "", "Kullanıcı": r.get("kullanici") or "",
            } for r in rows]), hide_index=True, use_container_width=True)
            with st.expander("Ayrıntı (son hata)"):
                st.code(rows[0].get("ayrinti") or "—")


def kullanici_yonetimi():
    """👥 Kullanıcı Yönetimi — yetkileri ekrandan yönetir.

    Değişiklikler 'kullanici_yetkileri' tablosuna yazılır; kod yüklemeleri
    onları etkilemez. Yeni kullanıcı için Secrets'a dokunmaya gerek yok:
    şifre hash'i mevcut 'kullanici_sifreler' tablosuna yazılır.
    """
    import pandas as pd
    from shared.yetki import (MODULLER, MODUL_ADI, OZEL, OZEL_ADI, yetki_tablosu,
                              kaydet, temizle, tablo_var_mi,
                              kullanici_adi_gecerli_mi, sifre_gecerli_mi)
    from shared.auth import sifre_hash_uret, supabase_sifre_kaydet

    ben = (st.session_state.get("aktif_kullanici", "") or "").strip().lower()
    if not ozel_yetki(ben, "kullanici_yonetimi"):
        st.error("🔒 Bu sayfaya erişim yetkiniz yok.")
        return

    from shared.tasarim import baslik as _bsl
    st.markdown(_bsl(":material/group: Kullanıcı yönetimi", "Yetkiler ve kullanıcılar",
                     aciklama="Yetkiler veritabanında tutulur · değişiklik anında geçerli olur, "
                              "kod yüklemeleri etkilemez"), unsafe_allow_html=True)

    if not tablo_var_mi():
        st.error("⚠️ `kullanici_yetkileri` tablosu henüz oluşturulmamış. Supabase SQL "
                 "Editor'de kurulum betiğini çalıştır. O zamana kadar sistem koddaki "
                 "sabit listelerle çalışmaya devam ediyor.")
        return

    db = yetki_tablosu()
    if db is None:
        st.warning("Tablo boş. Kurulum betiğinin başlangıç verisini (INSERT) çalıştır.")
        return

    _mesaj = st.session_state.pop("_ky_mesaj", None)
    if _mesaj:
        (st.success if _mesaj.startswith("✅") else st.error)(_mesaj)

    # ── 1) Yetki tablosu ─────────────────────────────────────────────
    st.markdown("#### Yetkiler")
    satirlar = []
    for k in sorted(db):
        v = db[k]
        r = {"Kullanıcı": k, "Aktif": v["aktif"], "Salt-okur": v["salt_okur"]}
        for m in MODULLER:
            r[MODUL_ADI[m]] = m in v["moduller"]
        for o in OZEL:
            r[OZEL_ADI[o]] = o in v["ozel"]
        satirlar.append(r)
    df = pd.DataFrame(satirlar)
    _cfg = {"Kullanıcı": st.column_config.TextColumn(disabled=True)}
    for c in df.columns[1:]:
        _cfg[c] = st.column_config.CheckboxColumn(c, width="small")
    duz = st.data_editor(df, hide_index=True, use_container_width=True,
                         column_config=_cfg, key="ky_editor",
                         height=min(600, 42 + 35 * len(df)))
    st.caption("Salt-okur: tüm modülleri görür, hiçbir veriyi değiştiremez. "
               "Aktif işareti kaldırılan kullanıcı giriş yapamaz.")

    if st.button("Yetki değişikliklerini kaydet", type="primary", key="ky_kaydet", icon=":material/save:"):
        degisen = []
        for _, r in duz.iterrows():
            k = r["Kullanıcı"]
            eski = db[k]
            mod = [m for m in MODULLER if bool(r[MODUL_ADI[m]])]
            oz = [o for o in OZEL if bool(r[OZEL_ADI[o]])]
            yeni = (sorted(mod), sorted(oz), bool(r["Salt-okur"]), bool(r["Aktif"]))
            if yeni != (eski["moduller"], eski["ozel"], eski["salt_okur"], eski["aktif"]):
                degisen.append((k, *yeni))
        # Kendini kilitleme koruması
        for k, mod, oz, so, ak in degisen:
            if k == ben and ("kullanici_yonetimi" not in oz or not ak):
                st.error("⛔ Kendi Kullanıcı Yönetimi yetkini kaldıramaz ya da kendi "
                         "hesabını kapatamazsın — kendini sistemden kilitlerdin.")
                return
        yoneticiler = {k for k, v in db.items() if v["aktif"] and "kullanici_yonetimi" in v["ozel"]}
        for k, mod, oz, so, ak in degisen:
            if not ak or "kullanici_yonetimi" not in oz:
                yoneticiler.discard(k)
            elif ak and "kullanici_yonetimi" in oz:
                yoneticiler.add(k)
        if not yoneticiler:
            st.error("⛔ En az bir aktif Kullanıcı Yönetimi yetkilisi kalmalı.")
            return
        if not degisen:
            st.info("Değişiklik yok.")
        else:
            hatalar = []
            for k, mod, oz, so, ak in degisen:
                ok, msg = kaydet(k, mod, oz, so, ak, guncelleyen=ben)
                if not ok:
                    hatalar.append(f"{k}: {msg}")
                elif not ak:
                    oturumlari_sonlandir(k)      # pasife alınan anında düşsün
            st.session_state["_ky_mesaj"] = (
                f"❌ Kaydedilemedi — {'; '.join(hatalar)}" if hatalar
                else f"✅ {len(degisen)} kullanıcının yetkisi güncellendi: "
                     + ", ".join(d[0] for d in degisen))
            st.rerun()

    # ── 2) E-posta bildirimleri (Ekim 2026) ──────────────────────────
    # Adresler kodda değil veritabanında; yükleme hatırlatmaları ve talep
    # bildirimleri bu adreslere gider (shared/eposta.py).
    st.markdown("---")
    st.markdown("#### E-posta bildirimleri")
    st.caption("Yükleme hatırlatmaları (sorumluya; 5 iş günü gecikmede yöneticiye kopya) ve talep "
               "bildirimleri (yeni talep → talep yöneticileri, yanıt → talep sahibi) bu adreslere gider.")
    from shared import eposta as _E
    _sa = _E.ayarlar()
    if _sa["user"] and _sa["pass"]:
        st.markdown(f'<div style="font-size:13px;color:var(--k-yesil)">✓ SMTP ayarlı · {_sa["user"]} · '
                    f'{_sa["host"]}:{_sa["port"]}</div>', unsafe_allow_html=True)
    else:
        st.warning("SMTP ayarlı değil: uygulama sırlarına `[bildirim]` bölümünde `smtp_user` ve `smtp_pass` "
                   "eklenmeli (Google Workspace için uygulama şifresi). Sabah hatırlatmaları için GitHub "
                   "sırlarına `SMTP_USER` ve `SMTP_PASS` eklenmeli.")
    _adr = _E.adresler()
    _edf = pd.DataFrame([{"Kullanıcı": k, "E-posta": _adr.get(k, "")} for k in sorted(db)])
    _eed = st.data_editor(_edf, hide_index=True, use_container_width=True, key="ky_eposta",
                          column_config={"Kullanıcı": st.column_config.TextColumn(disabled=True),
                                         "E-posta": st.column_config.TextColumn(width="large")},
                          height=min(560, 42 + 35 * len(_edf)))
    if st.button("E-posta adreslerini kaydet", key="ky_eposta_kaydet", icon=":material/save:"):
        _yeni = {r["Kullanıcı"]: str(r["E-posta"] or "").strip() for _, r in _eed.iterrows()}
        _hatali = [f"{k}: {v}" for k, v in _yeni.items() if v and not _E.adres_gecerli_mi(v)]
        if _hatali:
            st.error("Geçersiz adres — kaydedilmedi: " + " · ".join(_hatali))
        else:
            _ok = _E.adres_kaydet(_yeni)
            st.session_state["_ky_mesaj"] = ("✅ E-posta adresleri kaydedildi" if _ok
                                              else "❌ E-posta adresleri kaydedilemedi")
            st.rerun()
    _dk = [k for k in sorted(db) if _adr.get(k)]
    if _dk:
        d1, d2 = st.columns([2, 1], vertical_alignment="bottom")
        _dkim = d1.selectbox("Deneme maili gönderilecek kişi", _dk, key="ky_deneme_kisi",
                             format_func=lambda k: f"{k} · {_adr[k]}")
        if d2.button("Deneme maili gönder", key="ky_deneme", use_container_width=True, icon=":material/send:"):
            with st.spinner("Gönderiliyor…"):
                _ok, _kod = _E.gonder([_adr[_dkim]], "KAYRAN · deneme maili",
                                      _E.sablon("Deneme maili", "<p>E-posta bildirimleri çalışıyor. "
                                                "Yükleme hatırlatmaları ve talep bildirimleri bu adrese gelecek.</p>"))
            if _ok:
                st.success(f"✅ Gönderildi: {_adr[_dkim]} — gelen kutusunu (ve gereksiz klasörünü) kontrol et.")
            elif _kod == "smtp_yok":
                st.error("SMTP ayarlı değil — yukarıdaki uyarıya bak.")
            else:
                st.error(f"Gönderilemedi: {_kod}")

    st.markdown("---")
    c1, c2 = st.columns(2)

    # ── 2) Yeni kullanıcı ────────────────────────────────────────────
    with c1:
        st.markdown("#### Yeni kullanıcı")
        with st.form("ky_yeni", clear_on_submit=True):
            ad = st.text_input("Kullanıcı adı", placeholder="örn. serdar",
                               help="Küçük harf, rakam ve _ ; 2-20 karakter")
            s1 = st.text_input("Şifre", type="password",
                               help="En az 8 karakter, harf ve rakam içermeli")
            s2 = st.text_input("Şifre (tekrar)", type="password")
            mod = st.multiselect("Modüller", MODULLER, format_func=MODUL_ADI.get, placeholder="Modül seç…")
            oz = st.multiselect("Özel yetkiler", OZEL, format_func=OZEL_ADI.get, placeholder="Yetki seç…")
            gonder = st.form_submit_button("Kullanıcıyı oluştur", type="primary")
        if gonder:
            ad_n = (ad or "").strip().lower()
            if not kullanici_adi_gecerli_mi(ad_n):
                st.error("Kullanıcı adı geçersiz: küçük harf, rakam, _ ; 2-20 karakter.")
            elif ad_n in db:
                st.error(f"'{ad_n}' zaten var.")
            elif s1 != s2:
                st.error("Şifreler aynı değil.")
            elif not sifre_gecerli_mi(s1):
                st.error("Şifre en az 8 karakter olmalı, harf ve rakam içermeli.")
            else:
                ok1 = supabase_sifre_kaydet(ad_n, sifre_hash_uret(s1))
                ok2, msg = kaydet(ad_n, mod, oz, False, True, guncelleyen=ben) if ok1 else (False, "şifre yazılamadı")
                st.session_state["_ky_mesaj"] = (
                    f"✅ '{ad_n}' oluşturuldu. İlk girişte şifresini değiştirmesini öner."
                    if ok1 and ok2 else f"❌ Oluşturulamadı: {msg}")
                st.rerun()

    # ── 3) Şifre sıfırla ─────────────────────────────────────────────
    with c2:
        st.markdown("#### Şifre sıfırla")
        with st.form("ky_sifre", clear_on_submit=True):
            kim = st.selectbox("Kullanıcı", sorted(db))
            y1 = st.text_input("Yeni şifre", type="password")
            y2 = st.text_input("Yeni şifre (tekrar)", type="password")
            sifirla = st.form_submit_button("Şifreyi sıfırla")
        if sifirla:
            if y1 != y2:
                st.error("Şifreler aynı değil.")
            elif not sifre_gecerli_mi(y1):
                st.error("Şifre en az 8 karakter olmalı, harf ve rakam içermeli.")
            else:
                ok = supabase_sifre_kaydet(kim, sifre_hash_uret(y1))
                _n = oturumlari_sonlandir(kim) if ok and kim != ben else 0
                st.session_state["_ky_mesaj"] = (
                    f"✅ '{kim}' şifresi güncellendi"
                    + (f" · {_n} açık oturumu kapatıldı." if _n else ".")
                    if ok else "❌ Şifre kaydedilemedi.")
                st.rerun()

    if st.button("Listeyi yenile", key="ky_yenile", icon=":material/refresh:"):
        temizle()
        st.rerun()


def sifre_degistir():
    """Kullanıcının kendi şifresini değiştirebileceği sayfa."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    from shared.tasarim import bas_harf as _bh
    ilk_harf = _bh(aktif_kullanici) if aktif_kullanici else "U"

    st.markdown(portal_css(), unsafe_allow_html=True)
    from shared.tasarim import baslik as _bsl
    st.markdown(_bsl(":material/key: Hesap", "Şifremi değiştir",
                     aciklama="Yeni şifren Supabase'de güvenli şekilde saklanır; Streamlit Secrets'tan bağımsızdır"),
                unsafe_allow_html=True)

    # ─── FORM ─────────────────────────────────────────────────────────────────
    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0 10px">'
            f'<div style="width:30px;height:30px;border-radius:8px;background:var(--k-mor);display:flex;'
            f'align-items:center;justify-content:center;font-weight:700;color:#fff;font-size:13px">{ilk_harf}</div>'
            f'<div style="color:var(--k-metin);font-weight:600;font-size:14px">{kisi_adi(aktif_kullanici)}</div></div>',
            unsafe_allow_html=True)
        with st.form("sifre_degistir_form", clear_on_submit=True):
            mevcut = st.text_input("Mevcut şifre", type="password", placeholder="Mevcut şifrenizi girin")
            yeni   = st.text_input("Yeni şifre",   type="password", placeholder="En az 6 karakter")
            tekrar = st.text_input("Yeni şifre (tekrar)", type="password", placeholder="Yeni şifreyi tekrar girin")
            kaydet = st.form_submit_button("Şifreyi güncelle", type="primary", use_container_width=True, icon=":material/key:")

        if kaydet:
            # Validasyonlar
            if not mevcut or not yeni or not tekrar:
                st.error("❌ Tüm alanları doldurun.")
            elif len(yeni) < 6:
                st.error("❌ Yeni şifre en az 6 karakter olmalı.")
            elif yeni != tekrar:
                st.error("❌ Yeni şifreler eşleşmiyor.")
            else:
                # Mevcut şifreyi doğrula (Supabase öncelikli)
                try:
                    kullanicilar = st.secrets.get("kullanicilar", {})
                    from shared.auth import kullanici_dogrula_v2, sifre_hash_uret, supabase_sifre_kaydet
                    if not kullanici_dogrula_v2(aktif_kullanici, mevcut, kullanicilar):
                        st.error("❌ Mevcut şifreniz hatalı.")
                    else:
                        yeni_hash = sifre_hash_uret(yeni)
                        if supabase_sifre_kaydet(aktif_kullanici, yeni_hash):
                            st.success("✅ Şifreniz başarıyla güncellendi! Bir sonraki girişte yeni şifreniz geçerli olacak.")
                            st.balloons()
                        else:
                            st.error("❌ Şifre kaydedilemedi. Lütfen tekrar deneyin veya yöneticiye bildirin.")
                except Exception as e:
                    st.error(f"❌ Bir hata oluştu: {e}")

        st.markdown(k_mesaj("bilgi", "Yeni şifren Supabase'de güvenli hash olarak saklanır. Sadece sen "
                                     "değiştirebilirsin — yönetici dahil kimse eski şifreni göremez."),
                    unsafe_allow_html=True)

def kayrantsw_yakinda():
    """KAYRANTS&W modülü için 'Yakında Sizlerle' bilgilendirme sayfası."""
    st.markdown(portal_css(), unsafe_allow_html=True)

    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
        'text-align:center;padding:48px 20px 24px;animation:fadeUp 0.6s ease-out">'
        # İkon rozeti
        '<div style="width:96px;height:96px;border-radius:24px;'
        'background:linear-gradient(135deg,color-mix(in srgb,var(--k-mor) 25%,transparent),color-mix(in srgb,var(--k-pembe) 20%,transparent));'
        'border:1px solid color-mix(in srgb,var(--k-mor) 35%,transparent);display:flex;align-items:center;justify-content:center;'
        'font-size:23px;margin-bottom:28px;box-shadow:0 10px 40px color-mix(in srgb,var(--k-mor) 25%,transparent)">🚧</div>'
        # Uygulama adı rozeti
        '<div style="display:inline-block;padding:8px 16px;background:color-mix(in srgb,var(--k-mor) 12%,transparent);'
        'border:1px solid color-mix(in srgb,var(--k-mor) 25%,transparent);border-radius:20px;margin-bottom:20px">'
        '<span style="color:var(--k-mor2);font-size:13px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase">KAYRANTS&amp;W</span>'
        '</div>'
        # Başlık
        '<h1 style="font-family:Inter,sans-serif;font-size:clamp(26px,5vw,44px);font-weight:700;color:var(--k-metin);'
        'letter-spacing:1px;margin:0;line-height:1.1">'
        '<span style="background:linear-gradient(90deg,var(--k-mavi),var(--k-mor),var(--k-pembe));'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">YAKINDA SİZLERLE</span>'
        '</h1>'
        # Alt açıklama
        '<p style="color:var(--k-soluk);font-size:14px;margin-top:16px;max-width:480px;line-height:1.7;font-weight:400">'
        'Depo & Teknik Servis üzerinde çalışıyoruz. Çok yakında bu modül de KAYRAN Workspace ailesine katılacak. '
        'Gelişmelerden haberdar olmak için takipte kalın.'
        '</p>'
        # Dekoratif çizgi
        '<div style="width:80px;height:3px;margin:28px auto 0;'
        'background:linear-gradient(90deg,var(--k-mor),var(--k-mor),var(--k-pembe));border-radius:2px"></div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Ana sayfaya dön butonu (ortalı)
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        if st.button("Ana Sayfaya Dön", key="tsw_ana_don", use_container_width=True, icon=":material/home:"):
            st.session_state.aktif_uygulama = "anasayfa"
            st.rerun()


# ─────────────────────────────────────────────────────────────────────
# 4) GLOBAL HATA KARTI
# ─────────────────────────────────────────────────────────────────────
def _global_hata_kart(uygulama_adi, hata):
    st.markdown(
        '<div style="background:color-mix(in srgb,var(--k-kirmizi) 10%,transparent);border:1px solid color-mix(in srgb,var(--k-kirmizi) 25%,transparent);border-left:4px solid var(--k-kirmizi);border-radius:12px;padding:24px 28px;margin:30px auto;max-width:700px">'
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">'
        '<span style="font-size:23px">️</span>'
        f'<b style="color:var(--k-kirmizi2);font-size:19px">{uygulama_adi} Uygulamasında Bir Sorun Oluştu</b>'
        '</div>'
        '<div style="color:var(--k-kirmizi);font-size:14px;line-height:1.6;margin-bottom:16px">'
        'Üzgünüz, beklenmedik bir hata oluştu. Verileriniz güvende — sadece bu işlem tamamlanamadı.'
        '</div>'
        '<div style="background:rgba(0,0,0,0.25);border:1px solid color-mix(in srgb,var(--k-kirmizi) 25%,transparent);border-radius:8px;padding:12px 16px;font-family:monospace;font-size:13px;color:var(--k-kirmizi2);margin-bottom:16px;overflow-x:auto">'
        f'<b>Hata:</b> {type(hata).__name__}: {str(hata)[:300]}'
        '</div>'
        '<div style="font-size:13px;color:var(--k-kirmizi)">'
        '💡 <b>Ne yapabilirim?</b> Tarayıcı önbelleğini temizle (Ctrl+F5) · Ana sayfaya dön · Sorun devam ederse yöneticiye bildir'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    with st.expander("🔧 Teknik Detay"):
        st.code(traceback.format_exc(), language="python")

    if st.button("Ana Sayfaya Dön", key="hata_ana_don", type="primary", icon=":material/home:"):
        st.session_state.aktif_uygulama = "anasayfa"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────
# 5) ANA ROUTING
# ─────────────────────────────────────────────────────────────────────
def _talep_merkezi():
    """Talep merkezi penceresi (düğmesi üst menünün en sağında: _talep_dugmesi).

    · Herkes: talep gönderir ve KENDİ taleplerinin durumunu görür.
    · Yönetici: gelen tüm talepleri görür, cevaplar, durum değiştirir.
      Rozet açık talep sayısını gösterir — hangi sayfada olursa olsun.

    Ekim 2026: düğme eskiden sağ altta yüzüyordu (position:fixed) ve Streamlit
    Cloud'un "Manage app" rozetinin arkasında kalıyordu; üst menüye taşındı.
    """
    _kul = st.session_state.get("aktif_kullanici", "") or ""
    if not _kul:
        return
    _yonetici = ozel_yetki(_kul, "talep_yonetici")
    _acik = 0                                   # "Gelen Talepler (N)" sekme başlığı için
    if _yonetici:
        try:
            from kayranpm.database import acik_talep_sayisi
            _acik = acik_talep_sayisi()
        except Exception:
            _acik = 0

    @st.dialog("Talep Merkezi", width="large")
    def _dlg_talep():
        from kayranpm.database import (ekle_talep, get_talepler,
                                       get_talepler_kullanici, guncelle_talep_cevap)

        _DURUM_ETIKET = {"bekliyor": ("🟡", "Bekliyor"),
                         "inceleniyor": ("🔵", "İnceleniyor"),
                         "tamamlandi": ("🟢", "Tamamlandı"),
                         "reddedildi": ("⚪", "Kapatıldı")}

        def _durum_rozet(d):
            _i, _a = _DURUM_ETIKET.get(str(d or "bekliyor"), ("🟡", "Bekliyor"))
            return f"{_i} {_a}"

        _sekmeler = ["📝 Yeni Talep", "📋 Taleplerim"]
        if _yonetici:
            _sekmeler.append(f"📬 Gelen Talepler ({_acik})")
        _tabs = st.tabs(_sekmeler)

        # ── Yeni talep ──
        with _tabs[0]:
            st.caption("Geliştirme, hata bildirimi veya yeni özellik isteklerini "
                       "doğrudan ekibe ilet. Talebin kaydedilir ve durumunu "
                       "**Taleplerim** sekmesinden takip edebilirsin.")
            with st.form("talep_form_fab", clear_on_submit=True):
                f1, f2 = st.columns([1, 1])
                _kat = f1.selectbox("Kategori", TALEP_KATEGORILERI, key="fab_kat")
                _onc = f2.selectbox("Öncelik", ["Normal", "Yüksek", "Acil", "Düşük"],
                                    key="fab_onc")
                _konu = st.text_input(
                    "Konu *", placeholder="Kısa ve net — örn. 'Depo raporuna transfer tarihi eklensin'")
                _mesaj = st.text_area(
                    "Açıklama *", height=150,
                    placeholder="Ne olmasını istiyorsun? Hangi ekranda? Hata ise hangi "
                                "adımlarda oluşuyor? Örnek verirsen daha hızlı çözülür.")
                _gonder = st.form_submit_button("Talebi Gönder", type="primary",
                                                use_container_width=True, icon=":material/send:")
            if _gonder:
                if not (_mesaj or "").strip():
                    st.warning("⚠️ Açıklama alanı zorunlu.")
                elif not (_konu or "").strip():
                    st.warning("⚠️ Konu alanı zorunlu.")
                else:
                    _ok = ekle_talep(_kul.capitalize(), _konu.strip(), _mesaj.strip(),
                                     kategori=_kat, oncelik=_onc)
                    if _ok:
                        st.cache_data.clear()
                        for _yn in talep_yoneticileri():
                            if _kul.lower() != _yn:
                                try:
                                    bildirim_gonder(
                                        _yn, f"📨 Yeni talep — {_konu.strip()} "
                                             f"· {_kul.capitalize()} ({_onc})")
                                except Exception:
                                    pass
                        # E-posta: talep yöneticilerine (arka planda; gidemese de talep kayıtlı)
                        try:
                            from shared.eposta import adresler, talep_yeni_mail, arka_planda
                            _adr = adresler()
                            _alici = [_adr[y] for y in talep_yoneticileri()
                                      if y != _kul.lower() and _adr.get(y)] or [TALEP_ALICI]
                            from shared.yukleme_takvimi import sorumlu_adi as _tad   # gokhan → Gökhan
                            _mk, _mh = talep_yeni_mail(_tad(_kul), _mesaj.strip(), _konu.strip(),
                                                       _kat, _onc)
                            arka_planda(_alici, _mk, _mh)
                        except Exception:
                            pass
                        st.success("✅ Talebin kaydedildi. Teşekkürler!")
                    else:
                        st.error("❌ Kaydedilemedi, tekrar dener misin?")

        # ── Kendi taleplerim ──
        with _tabs[1]:
            _benim = get_talepler_kullanici(_kul.capitalize())
            if not _benim:
                st.info("Henüz talep göndermemişsin.")
            else:
                st.caption(f"{len(_benim)} talep · en yeni üstte")
                for _t in _benim[:40]:
                    _bas = (f"{_durum_rozet(_t.get('durum'))} · "
                            f"{_t.get('konu') or 'Konusuz'}")
                    with st.expander(_bas):
                        _ust = []
                        if _t.get("kategori"):
                            _ust.append(f"🏷️ {_t['kategori']}")
                        if _t.get("oncelik"):
                            _ust.append(f"⚡ {_t['oncelik']}")
                        if _t.get("olusturma_tarihi"):
                            _ust.append(f"📅 {str(_t['olusturma_tarihi'])[:10]}")
                        if _ust:
                            st.caption(" · ".join(_ust))
                        st.markdown(_t.get("mesaj") or "—")
                        if (_t.get("cevap") or "").strip():
                            st.success(f"**Cevap:** {_t['cevap']}")
                        _claude_et = _claude_etiket(_t)
                        if _claude_et:
                            st.caption(f":material/smart_toy: Geliştirme: {_claude_et}")

        # ── Yönetici: gelen talepler ──
        if _yonetici:
            with _tabs[2]:
                _hepsi = get_talepler() or []
                _f = st.radio("Filtre", ["Açık olanlar", "Tümü"], horizontal=True,
                              key="fab_filtre", label_visibility="collapsed")
                _liste = ([t for t in _hepsi if t.get("durum") != "tamamlandi"]
                          if _f == "Açık olanlar" else _hepsi)
                if not _liste:
                    st.success("🎉 Açık talep yok.")
                for _t in _liste[:60]:
                    _tid = _t.get("id")
                    _bas = (f"{_durum_rozet(_t.get('durum'))} · "
                            f"{_t.get('konu') or 'Konusuz'} — "
                            f"{_t.get('gonderen') or '?'}")
                    if str(_t.get("oncelik") or "").lower() in ("acil", "yüksek"):
                        _bas = "🔴 " + _bas
                    with st.expander(_bas):
                        _ust = [f":material/person: {_t.get('gonderen') or '?'}"]
                        if _t.get("kategori"):
                            _ust.append(f":material/sell: {_t['kategori']}")
                        if _t.get("oncelik"):
                            _ust.append(f":material/bolt: {_t['oncelik']}")
                        if _t.get("olusturma_tarihi"):
                            _ust.append(f":material/calendar_month: {str(_t['olusturma_tarihi'])[:10]}")
                        st.caption(" · ".join(_ust))
                        st.markdown(_t.get("mesaj") or "—")
                        _c1, _c2 = st.columns([3, 1])
                        _cev = _c1.text_area("Cevap", value=(_t.get("cevap") or ""),
                                             key=f"fab_cevap_{_tid}", height=90)
                        _dur = _c2.selectbox(
                            "Durum", ["bekliyor", "inceleniyor", "tamamlandi", "reddedildi"],
                            index=["bekliyor", "inceleniyor", "tamamlandi",
                                   "reddedildi"].index(str(_t.get("durum") or "bekliyor"))
                            if str(_t.get("durum") or "bekliyor") in
                               ("bekliyor", "inceleniyor", "tamamlandi", "reddedildi") else 0,
                            key=f"fab_durum_{_tid}")
                        if _c2.button("Kaydet", key=f"fab_kaydet_{_tid}",
                                      use_container_width=True, icon=":material/save:"):
                            try:
                                guncelle_talep_cevap(_tid, _cev.strip(), _dur)
                                st.cache_data.clear()
                                _gnd = str(_t.get("gonderen") or "").strip().lower()
                                if _gnd and _cev.strip():
                                    try:
                                        bildirim_gonder(
                                            _gnd, f"💬 Talebine cevap geldi — "
                                                  f"{_t.get('konu') or 'Talep'}")
                                    except Exception:
                                        pass
                                # E-posta: talep sahibine (yanıt geldiyse ya da durum değiştiyse)
                                _degisti = (_cev.strip() != (_t.get("cevap") or "").strip()
                                            or _dur != str(_t.get("durum") or "bekliyor"))
                                if _gnd and _degisti and _gnd != (_kul or "").lower():
                                    try:
                                        from shared.eposta import adresler, talep_yanit_mail, arka_planda
                                        _ga = adresler().get(_gnd)
                                        if _ga:
                                            _mk, _mh = talep_yanit_mail(_t.get("konu") or "Talep", _cev.strip(), _dur)
                                            arka_planda([_ga], _mk, _mh)
                                    except Exception:
                                        pass
                                st.toast("✅ Kaydedildi")      # rerun'dan önce basılan success kayboluyordu
                                st.rerun()
                            except Exception as _e:
                                st.error(f"❌ {type(_e).__name__}")
                        _claude_bolumu(_t, _kul)

    # Pencere üst menüdeki düğmenin bayrağıyla, sayfa çizildikten SONRA açılır
    # (modül hata verse bile talep açılabilsin).
    if st.session_state.pop("_talep_ac", False):
        _dlg_talep()


def _claude_etiket(t):
    try:
        from shared.claude_talep import etiket
        return etiket(t)
    except Exception:
        return ""


def _claude_bolumu(t, kul):
    """Gelen talepler: Claude durumu, notu, PR linki ve onaycıya "Claude'a gönder" (Ekim 2026).
    Akış: shared/claude_talep.py — onaylanan talebi zamanlanmış Claude görevi kodlar, PR açar."""
    from shared import claude_talep as C
    _et = C.etiket(t)
    if _et:
        _sat = f":material/smart_toy: Claude: {_et}"
        if t.get("claude_pr_url"):
            _sat += f" · [PR'ı aç]({t['claude_pr_url']})"
        st.caption(_sat)
    if (t.get("claude_not") or "").strip():
        st.info(f"Claude'un notu: {t['claude_not']}")
    if not C.onaylayabilir_mi(kul, ozel_yetki) or not C.gonderilebilir_mi(t):
        return
    _tid = t.get("id")
    _ilk = not C.claude_durumu(t)
    _not = st.text_area("Claude'a not (isteğe bağlı)" if _ilk else "Claude'a cevap / yeni not",
                        value="" if _ilk else (t.get("claude_onay_notu") or ""),
                        key=f"claude_not_{_tid}", height=80,
                        placeholder="Örn: yalnız Satış sayfasında olsun; mevcut rakamlar değişmesin")
    if st.button("Claude'a gönder", key=f"claude_gonder_{_tid}", icon=":material/send:",
                 help="Claude bir saat içinde başlar, PR açar; PR hazır olunca mail gelir. "
                      "Birleştirmeyi sen yaparsın."):
        from kayranpm.database import get_client
        from shared.utils import tr_now
        _ok, _msj = C.onaya_gonder(get_client(), _tid, kul, _not, tr_now())
        if _ok:
            st.cache_data.clear()
            st.toast(_msj)
            st.rerun()
        else:
            st.error(_msj)


def _talep_ac_isaretle():
    st.session_state["_talep_ac"] = True


def _talep_dugmesi():
    """Üst menünün en sağındaki Talep düğmesi. Yönetici açık talep sayısını görür."""
    _kul = st.session_state.get("aktif_kullanici", "") or ""
    if not _kul:
        return
    _acik = 0
    if ozel_yetki(_kul, "talep_yonetici"):
        try:
            from kayranpm.database import acik_talep_sayisi
            _acik = acik_talep_sayisi()
        except Exception:
            _acik = 0
    st.button(f"Talep · {_acik}" if _acik else "Talep", key="ust_talep", icon=":material/forum:",
              help=(f"Talep Merkezi — {_acik} açık talep" if _acik else "Talep / geri bildirim gönder"),
              on_click=_talep_ac_isaretle)


def main():
    # Login yapılmamışsa giriş ekranı
    if not st.session_state.giris_yapildi:
        giris_ekrani()
        return

    # Hızlandırma (Ekim 2026): her sayfada gereken küçük okumalar AYNI ANDA (shared/paralel).
    # Program ABD'de, veritabanı Frankfurt'ta; her istek ~0,2-0,3 sn. Önbellek süresi dolduğunda
    # bunlar sırayla ~1-1,5 sn tutuyordu. Hepsi önbellekli: aşağıdaki asıl çağrılar sonucu hazır bulur.
    try:
        from shared.paralel import hepsi as _paralel
        from shared.yetki import yetki_tablosu as _yt
        from shared.veri_surumu import _surumler as _vs
        from kayranpm.database import get_talepler as _gt
        _paralel([_yt, _vs, _gt, (get_okunmamis_bildirimler, st.session_state.aktif_kullanici)])
    except Exception:  # noqa: BLE001
        pass

    # Hesap açık oturum SIRASINDA pasife alındıysa hemen çıkış yaptır.
    # (Eskiden pasif kontrolü yalnız girişte yapılıyordu; tarayıcısı açık olan
    # kullanıcı erişmeye devam ediyordu. Yetki tablosu 60 sn önbellekli —
    # pasife alınan hesap en geç 1 dakika içinde düşer.)
    if not _hesap_hala_aktif_mi(st.session_state.aktif_kullanici):
        oturumlari_sonlandir(st.session_state.aktif_kullanici)
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.session_state.giris_yapildi = False
        st.session_state.aktif_kullanici = ""
        st.warning("🔒 Hesabınız devre dışı bırakıldı. Yöneticinizle görüşün.")
        giris_ekrani()
        return

    # Sidebar her zaman görünür (login sonrası)
    portal_sidebar()

    # Aktif kullanıcının online durumunu güncelle — arka planda (yazma; sayfa beklemesin)
    try:
        from shared.paralel import basla as _arkada
        _arkada([(online_durum_guncelle, st.session_state.aktif_kullanici)])
    except Exception:  # noqa: BLE001
        online_durum_guncelle(st.session_state.aktif_kullanici)

    aktif = st.session_state.aktif_uygulama
    yetkiler = kullanici_yetkileri(st.session_state.aktif_kullanici)

    # Modül değişince soldaki menüyü ilgili alt menüye (SAYFALARI) kaydır
    if st.session_state.get("_nav_onceki") != aktif:
        if aktif in ("kayranacc", "kayranpm", "ithalat", "teknikservis", "hesap_makinesi"):
            st.session_state["_sidebar_kaydir"] = True
        st.session_state["_nav_onceki"] = aktif

    # Yetki kontrolü — yetkisizse anasayfaya DÖN + rerun (üst menü kaybolmasın)
    def _yetki_reddi(_mesaj):
        st.session_state["_yetki_uyari"] = _mesaj
        st.session_state.aktif_uygulama = "anasayfa"
        st.rerun()

    if aktif == "yonetim" and not ozel_yetki(st.session_state.get("aktif_kullanici", ""), "yonetim"):
        _yetki_reddi("🔒 Yönetim Panosu'na erişim yetkiniz yok.")
    if aktif == "hesap_makinesi" and not yetkiler["hesap_makinesi"]:
        _yetki_reddi("🔒 Hesap Makinesi uygulamasına erişim yetkiniz yok.")
    if aktif == "kayranacc" and not yetkiler["kayranacc"]:
        _yetki_reddi("🔒 Muhasebe & Finans uygulamasına erişim yetkiniz yok.")
    if aktif == "kayranpm" and not yetkiler["kayranpm"]:
        _yetki_reddi("🔒 Ürün Yönetimi uygulamasına erişim yetkiniz yok.")
    if aktif == "depo" and not yetkiler["depo"]:
        _yetki_reddi("🔒 Depo Yönetimi uygulamasına erişim yetkiniz yok.")
    if aktif == "ithalat" and not yetkiler["ithalat"]:
        _yetki_reddi("🔒 İthalat uygulamasına erişim yetkiniz yok.")
    if aktif == "teknikservis" and not yetkiler["teknikservis"]:
        _yetki_reddi("🔒 Teknik Servis uygulamasına erişim yetkiniz yok.")
    if aktif == "satis" and not yetkiler["satis"]:
        _yetki_reddi("🔒 Satış uygulamasına erişim yetkiniz yok.")

    # Global modern form-alanı stili (tüm modüllere uygulanır): +/- gizli, modern kutular
    try:
        from shared.utils import modern_input_stil
        st.markdown(modern_input_stil(), unsafe_allow_html=True)
    except Exception:
        pass

    # Üst yatay modül navigasyonu (modüller arası hızlı geçiş)
    ust_navigasyon()

    # Tarayıcı sekme başlığı = aktif modül (yeni sekmede hangi bölümde olduğun görünsün)
    _sekme_basliklari = {
        "anasayfa": "Ana Sayfa", "arama": "Arama", "yonetim": "Yönetim P&L",
        "kayranacc": "Muhasebe", "ithalat": "İthalat", "kayranpm": "Ürün Yönetimi",
        "depo": "Depo Yönetimi",
        "satis": "Satış", "teknikservis": "Teknik Servis",
        "hesap_makinesi": "Hesap Makinesi", "sifre_degistir": "Şifre Değiştir", "kullanici_yonetimi": "Kullanıcı Yönetimi", "sistem_kayitlari": "Sistem Kayıtları",
        "tasarim_rehberi": "Tasarım Rehberi", "cop_kutusu": "Çöp Kutusu", "yukleme_gecmisi": "Yükleme Geçmişi", "veri_sagligi": "Veri Sağlığı",
        "soru": "Soru sor",
    }
    try:
        import streamlit.components.v1 as _comp
        import json as _json
        _tb = _sekme_basliklari.get(aktif, "Workspace")
        _comp.html(f"<script>window.parent.document.title={_json.dumps(_tb + ' | KAYRAN')};</script>",
                   height=0)
    except Exception:
        pass

    # Veri sürümü (shared/veri_surumu): izlenen tablolar değiştiyse ağır önbellekleri (Tüm Ürünler,
    # Genel bakış, paçal) temizle — en fazla 15 sn'de bir küçük bir sorgu, hata fırlatmaz.
    try:
        from shared.veri_surumu import tazelik_kontrol
        tazelik_kontrol()
    except Exception:
        pass

    # Sayfa dispatch
    try:
        if aktif == "anasayfa":
            _uyari = st.session_state.pop("_yetki_uyari", None)
            if _uyari:
                st.error(_uyari + " Ana sayfaya yönlendirildiniz.")
            anasayfa()
        elif aktif == "arama":
            from shared.tasarim import sayfa_baslik as _sb_ara
            st.markdown(_sb_ara("🔍", "Arama", "Tüm modüllerde ara — sonuç kartına tıkla, ilgili modüle git"), unsafe_allow_html=True)
            _arama_kutusu("sayfa")
        elif aktif == "kayranacc":
            from kayranacc.main import run as kayranacc_run
            kayranacc_run()
        elif aktif == "kayranpm":
            from kayranpm.main import run as kayranpm_run
            kayranpm_run()
        elif aktif == "depo":
            from depo.main import run as depo_run
            depo_run()
        elif aktif == "ithalat":
            from ithalat.main import run as ithalat_run
            ithalat_run()
        elif aktif == "teknikservis":
            from teknikservis.main import run as teknikservis_run
            teknikservis_run()
        elif aktif == "satis":
            from satis.main import run as satis_run
            satis_run()
        elif aktif == "yonetim":
            if ozel_yetki(st.session_state.get("aktif_kullanici", ""), "yonetim"):
                from yonetim import run as yonetim_run
                yonetim_run()
            else:
                st.error("Bu sayfaya erişim yetkiniz yok.")
        elif aktif == "hesap_makinesi":
            from hesap_makinesi.main import run as hesap_makinesi_run
            hesap_makinesi_run()
        elif aktif == "kayrantsw":
            kayrantsw_yakinda()
        elif aktif == "kullanici_yonetimi":
            kullanici_yonetimi()
        elif aktif == "sistem_kayitlari":
            sistem_kayitlari()
        elif aktif == "yukleme_gecmisi":
            from shared.yukleme_gecmisi import sayfa as _yukleme_gecmisi_sayfa
            _yg_kul = st.session_state.get("aktif_kullanici", "")
            _yukleme_gecmisi_sayfa(_yg_kul, ozel_yetki(_yg_kul, "kullanici_yonetimi"))
        elif aktif == "veri_sagligi":
            from shared.veri_sagligi import sayfa as _veri_sagligi_sayfa
            _vs_kul = st.session_state.get("aktif_kullanici", "")
            _veri_sagligi_sayfa(_vs_kul, kullanici_yetkileri(_vs_kul), ozel_yetki(_vs_kul, "kullanici_yonetimi"))
        elif aktif == "soru":
            from shared.soru_ekran import sayfa as _soru_sayfa
            from shared.kar_gizle import kar_gorunur as _kar_gorunur
            _sq_kul = st.session_state.get("aktif_kullanici", "")
            _soru_sayfa(_sq_kul, kullanici_yetkileri(_sq_kul), _kar_gorunur())
        elif aktif == "cop_kutusu":
            from shared.cop_kutusu import sayfa as _cop_kutusu_sayfa
            _ck_kul = st.session_state.get("aktif_kullanici", "")
            _cop_kutusu_sayfa(_ck_kul, ozel_yetki(_ck_kul, "kullanici_yonetimi"))
        elif aktif == "tasarim_rehberi":
            if ozel_yetki(st.session_state.get("aktif_kullanici", ""), "kullanici_yonetimi"):
                from shared.rehber import goster as tasarim_rehberi_goster
                tasarim_rehberi_goster()
            else:
                st.error("🔒 Bu sayfaya erişim yetkiniz yok.")
        elif aktif == "sifre_degistir":
            sifre_degistir()
        else:
            st.error(f"Bilinmeyen sayfa: {aktif}")
            st.session_state.aktif_uygulama = "anasayfa"
            if st.button("← Ana Sayfaya Dön"):
                st.rerun()
    except Exception as hata:
        # Bayat modül koruması (shared/modul_tazele): güncelleme sonrası bellekte eski kalan bir
        # proje modülü 'cannot import name' / eksik ad / çağrı imzası hatası verdiyse modülleri tazeleyip
        # BİR KEZ yeniden çalıştır.
        try:
            import os as _os_mt, sys as _sys_mt
            from shared.modul_tazele import tazelenmeli, proje_modullerini_sil
            _kok_mt = _os_mt.path.dirname(_os_mt.path.abspath(__file__))
            if tazelenmeli(hata, _kok_mt) and not st.session_state.get("_modul_tazelendi"):
                st.session_state["_modul_tazelendi"] = True
                proje_modullerini_sil(_sys_mt.modules, _kok_mt)
                st.rerun()
        except ImportError:
            pass
        # Sayfa çökmesi hata kaydına (hata_kayitlari, Sistem Kayıtları) — eskiden yalnız ekranda
        # görünüyordu, sonradan iz kalmıyordu. kaydet aynı hatayı kısa sürede bir kez yazar.
        try:
            from shared.hata_log import kaydet
            kaydet(f"sayfa.{aktif}", hata)
        except Exception:  # noqa: BLE001
            pass
        ad = "KAYRAN" if aktif == "kayranacc" else ("KAYRAN" if aktif == "kayranpm" else aktif)
        _global_hata_kart(ad, hata)
    else:
        st.session_state.pop("_modul_tazelendi", None)   # sayfa sorunsuz çizildi → koruma yeniden kurulur

    # Talep düğmesi HER SAYFADA görünür — sayfa içeriği çizildikten sonra
    # eklenir ki modül hata verse bile erişilebilir kalsın.
    try:
        _talep_merkezi()
    except Exception:
        pass

    # Modül değiştiyse soldaki menüyü ilgili "SAYFALARI" alt menüsüne kaydır
    if st.session_state.pop("_sidebar_kaydir", False):
        import streamlit.components.v1 as _components
        # ── ARAMA KUTUSU HATASININ KAYNAĞI BURASIYDI ──────────────────
        # Eski script sayfa çizildikten sonra 20 kez × 120ms = ~2,4 saniye
        # boyunca deneme yapıp 'smooth' (animasyonlu) kaydırma tetikliyordu.
        # Kullanıcı sayfaya girip HEMEN yazmaya başladığında bu kaydırma
        # araya giriyor, odaktaki input/selectbox yeniden bağlanıyor ve
        # yazılan ilk karakter SEÇİLİ kalıyordu — sonraki tuş onu siliyordu.
        # ("F11 yazıyorum, F gidiyor." İkinci denemede script bittiği için
        #  sorun kendiliğinden kayboluyordu.)
        #
        # Düzeltme üç parçalı:
        #   1) Kullanıcı bir alana yazıyorsa kaydırma HİÇ yapılmaz.
        #   2) İlk tuşa/tıklamaya basıldığı anda deneme döngüsü iptal edilir.
        #   3) Animasyonsuz ('auto') ve daha kısa deneme penceresi (~0,7 sn).
        _components.html(
            "<script>"
            "(function(){"
            " var d=window.parent.document, iptal=false;"
            " function yaziyorMu(){"
            "  try{var e=d.activeElement; if(!e)return false;"
            "   var t=(e.tagName||'').toUpperCase();"
            "   return t==='INPUT'||t==='TEXTAREA'||e.isContentEditable===true;"
            "  }catch(e){return false;}}"
            " function dur(){iptal=true;}"
            " try{"
            "  d.addEventListener('keydown',dur,{once:true,capture:true});"
            "  d.addEventListener('pointerdown',dur,{once:true,capture:true});"
            " }catch(e){}"
            " function go(n){"
            "  if(iptal||yaziyorMu())return;"          # kullanıcı yazıyorsa dokunma
            "  try{var a=d.querySelector('#kayran-submenu-anchor');"
            "   if(a){a.scrollIntoView({behavior:'auto',block:'start'});return;}"
            "  }catch(e){}"
            "  if(n>0)setTimeout(function(){go(n-1);},100);"
            " }"
            " go(7);"                                   # ~0,7 sn, eskiden 2,4 sn
            "})();"
            "</script>",
            height=0,
        )




if __name__ == "__main__":
    main()
else:
    main()

# Bayat modül koruması: bu çalıştırmada yüklenen proje modüllerinin dosya zamanı (başta tazele).
try:
    from shared.modul_tazele import yuklenenleri_kaydet as _yuklenenleri_kaydet
    _yuklenenleri_kaydet(_sys_bt.modules, _os_bt.path.dirname(_os_bt.path.abspath(__file__)),
                         getattr(_sys_bt, "_kayran_modul_zaman", {}))
except Exception:  # noqa: BLE001
    pass

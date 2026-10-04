"""
Muhasebe & Finans — Ödeme Takip Sistemi
Modüler olarak KAYRAN portal içinden çağrılır.

Kullanım:
    from kayranacc.main import run
    run()
"""
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
import html as _html
import streamlit as st
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_today, tr_now, tr_today_iso, tr_now_str, tr_tomorrow, tr_yesterday as _tr_today_iso_dummy
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici
from shared.utils import metrik_satiri, metric_css
from shared.tasarim import baslik as _sb, tablo_kolonlari, tablo_h, tablo_html, Ham, rozet_html, renkli, kisalt, mesaj as k_mesaj
from shared.tasarim import para as _tpara
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import os
from datetime import datetime, date, timedelta
from io import BytesIO
from .database import (
    initialize_db, get_tum_haftalar, get_aktif_hafta,
    hafta_ekle, hafta_aktif_yap, hafta_sil,
    get_hafta_odemeler, odeme_ekle_bulk, odeme_ekle_manuel,
        odeme_durum_guncelle, odeme_sil, odeme_kismi_ode, odeme_vade_guncelle, odeme_tutar_guncelle, odeme_kategori_guncelle, odeme_aciklama_guncelle,
    get_bankalar, banka_ekle, banka_guncelle, banka_sil,
    get_cekler, cek_ekle_bulk, cek_sil, cek_sil_hepsi, cek_tutarlari, cek_durum_norm,
    get_ertelenen_odemeler, get_virmanlar, virman_yap, virman_geri_al,
    tahsilat_ekle, get_tahsilatlar, tahsilat_geri_al,
    aktif_excel_kaydet, aktif_excel_oku, aktif_excel_sil, aktif_excel_meta_oku,
    aktif_manuel_ekle, aktif_manuel_listele, aktif_manuel_sil,
    aktif_manuel_guncelle, get_cek_toplamlari,
    set_ayar, get_ayar,
)
from .excel_islemler import (
    excel_yukle_odeme_listesi, excel_yukle_cek_listesi,
    export_excel, create_sample_excel
)
from .rapor import haftalik_excel_raporu, haftalik_html_raporu, nakit_akis_excel
from .bildirim import (mask_email,
    get_bildirim_ayarlari, email_gonder, baglanti_test,
    vade_bildirimi_olustur, ozet_bildirimi_olustur,
)


# ── Toplam Aktifler yetkisi — TEK KAYNAK ─────────────────────────────
# Bu liste ESKİDEN İKİ AYRI YERDE tekrar yazılıyordu: biri sol menüyü
# süzen kısımda, diğeri sayfanın kendi gövdesinde. Sadece birine kullanıcı
# eklenince sayfa menüde görünüyor ama açılınca "erişim yetkiniz yok"
# diyordu. Artık tek yerde duruyor; her iki kontrol de buradan okuyor.
TOPLAM_AKTIFLER_YETKILI = {"ibrahim", "cem", "yilmaz", "derman", "pamuk", "serdar"}


def _toplam_aktifler_yetkilileri():
    """Toplam Aktifler'i görebilenler. Kaynak: 'kullanici_yetkileri' tablosu
    (özel yetki: toplam_aktifler). Tablo yoksa yukarıdaki sabit listeye düşer."""
    try:
        from shared.yetki import ozel_sahipleri
        return ozel_sahipleri("toplam_aktifler", TOPLAM_AKTIFLER_YETKILI)
    except Exception:
        return set(TOPLAM_AKTIFLER_YETKILI)


# ══════════════════ DOSYA KAPISI GÖVDELERİ (Ekim 2026) ══════════════════
# Ödeme listesi ve çek dökümü (eskiden "Veri Yükleme" sayfası) ile Toplam Aktifler'in üç Excel'i
# (eskiden sayfadaki yükleme penceresi) artık üst menüdeki Dosya kapısında (shared/dosya_kapisi)
# yüklenir. Okuyucular aynı; düzeltmeler: aynı adlı hafta iki kez açılmadan önce onay, çeklerin
# yerine konacağı kayıttan ÖNCE gösterilip onaylanır, Toplam Aktifler dosyası seçilir seçilmez
# değil "Kaydet" ile yazılır ve son yükleyen gerçek kullanıcı olarak kaydedilir.


def sablon_odeme_listesi():
    return create_sample_excel(), "ornek_odeme_listesi.xlsx"


_AKTIF_TURLER = {
    "stok": ("Stok değeri raporu", "Mikro → Stok → Stok değeri raporu"),
    "ithalat": ("İthalat ödeme takip", "'Ödenen / USD' sütunu içeren takip dosyası"),
    "cari": ("Cari alacaklar listesi", "Mikro → Cari → Alacaklar listesi (Döviz + Bakiye sütunlu)"),
}


def _kapi_aktif(dosya, kapi, tip):
    from kayranacc.aktif_excel import (parse_cari, parse_ithalat, parse_stok, ExcelBicimHatasi,
                                       parse_stok_excel, aktif_kaydet)
    from shared.yukleme_takvimi import serit as _yt_serit
    baslik, yardim = _AKTIF_TURLER[tip]
    _yt_serit(f"aktif_{tip}")     # aktif_stok · aktif_ithalat · aktif_cari
    st.caption(yardim)
    parser = {"stok": lambda b: parse_stok(b, parse_stok_excel), "ithalat": parse_ithalat,
              "cari": parse_cari}[tip]
    ham = dosya.getvalue()
    try:
        deger, detay = parser(ham)
    except ExcelBicimHatasi as e:
        st.error(f"**Dosya biçimi beklenenden farklı.**\n\n{e}")
        return
    with st.container(border=True):
        st.markdown("**Okunan değerler** (kaydetmeden önce kontrol et)")
        for satir in (detay or {}).get("ozet", []):
            st.markdown(f"- {satir}")
        if (detay or {}).get("satir"):
            st.caption(f"{detay['satir']} satır işlendi")
        if (detay or {}).get("uyari"):
            st.warning(detay["uyari"])
    if st.button("Kaydet", type="primary", use_container_width=True, key=kapi.anahtar(f"aktif_{tip}_kaydet"),
                 icon=":material/save:"):
        _kul = st.session_state.get("aktif_kullanici", "") or "?"
        if not aktif_kaydet(tip, deger, ham, _kul, detay):
            st.error("Kaydedilemedi (veritabanına yazılamadı). Bağlantıyı kontrol edip yeniden dene.")
            return
        from shared.yukleme_gecmisi import kaydet as _yg_kaydet
        _yg_kaydet("aktif_excel", 1, f"{tip}: {dosya.name}")
        from shared.yukleme_takvimi import _temizle as _yt_tazele
        _yt_tazele()          # geri sayım yeni yükleme zamanını görsün
        kapi.bitti(f"{baslik} kaydedildi; Toplam Aktifler kartları güncellendi.",
                   ayrinti=" · ".join((detay or {}).get("ozet", [])))


def kapi_aktif_stok(dosya, kapi):
    _kapi_aktif(dosya, kapi, "stok")


def kapi_aktif_ithalat(dosya, kapi):
    _kapi_aktif(dosya, kapi, "ithalat")


def kapi_aktif_cari(dosya, kapi):
    _kapi_aktif(dosya, kapi, "cari")


def kapi_odeme_listesi(dosya, kapi):
    """Haftalık ödeme listesi → yeni hafta + ödemeler; hafta aktif yapılır."""
    from shared.yukleme_takvimi import serit as _yt_serit
    from .excel_islemler import ayni_hafta
    _yt_serit("odeme_listesi")
    st.caption("Sütun sırası: A=HAFTA · B=FİRMA · C=AÇIKLAMA · D=CARİ BANKA / IBAN · E=VADE · F=TUTAR TL · "
               "G=TUTAR USD · H=KATEGORİ (isteğe bağlı). Hafta adı A1 hücresinden alınır.")
    hafta_adi, odemeler, hatalar = excel_yukle_odeme_listesi(dosya.getvalue())
    for h in hatalar:
        st.warning(h)
    if not odemeler:
        st.warning("Ödeme listesinde işlenebilir veri bulunamadı.")
        return
    haftalar = get_tum_haftalar() or []
    ad = hafta_adi or f"Hafta {len(haftalar) + 1}"
    _tl = sum(float(o.get("tl") or 0) for o in odemeler)
    _usd = sum(float(o.get("usd") or 0) for o in odemeler)
    _vadeler = sorted(str(o.get("vade") or "") for o in odemeler if o.get("vade"))
    st.success(f"**{ad}** · {len(odemeler)} ödeme · ₺{tr_sayi(_tl)} · ${tr_sayi(_usd)}"
               + (f" · vade {_vadeler[0]} – {_vadeler[-1]}" if _vadeler else ""))
    st.dataframe(pd.DataFrame([{"Firma": o["firma"], "Açıklama": o.get("aciklama", ""), "Vade": o.get("vade"),
                                "TL": o.get("tl"), "USD": o.get("usd"), "Kategori": o.get("kategori")}
                               for o in odemeler[:200]]), hide_index=True, use_container_width=True, height=240)
    onay = True
    _ayni = ayni_hafta(ad, haftalar)
    if _ayni:
        st.warning(f"**'{ad}'** adında bir hafta zaten var ({_ayni.get('yuklendi_tarih') or 'tarih yok'} yüklendi). "
                   "Aynı listeyi ikinci kez yüklersen ödemeler iki ayrı haftada görünür.")
        onay = st.checkbox("Bu farklı bir liste — yine de yeni hafta olarak yükle", key=kapi.anahtar("odeme_ayni_onay"))
    if st.button("Yükle ve aktif hafta yap", type="primary", use_container_width=True, disabled=not onay,
                 key=kapi.anahtar("odeme_yukle"), icon=":material/check_circle:"):
        hafta_id = hafta_ekle(ad)
        hafta_aktif_yap(hafta_id)
        odeme_ekle_bulk(hafta_id, odemeler)
        from shared.yukleme_takvimi import kaydet as _yt_kaydet
        _yt_kaydet("odeme_listesi", st.session_state.get("aktif_kullanici", ""), len(odemeler))
        from shared.yukleme_gecmisi import kaydet as _yg_kaydet
        _yg_kaydet("odeme_listesi", len(odemeler), dosya.name)
        kapi.bitti(f"{len(odemeler)} ödeme yüklendi — '{ad}' aktif hafta yapıldı.")


def kapi_cek_listesi(dosya, kapi):
    """Firma çek dökümü. Dosyadaki para birimlerinin MEVCUT çekleri silinip dosyadakiler yazılır
    (döküm her seferinde tam liste; aynı dosya iki kez yüklenince çift kayıt olmasın diye)."""
    tl_cekler, usd_cekler, hatalar = excel_yukle_cek_listesi(dosya.getvalue())
    for h in hatalar:
        st.warning(h)
    if not (tl_cekler or usd_cekler):
        st.warning("Çek dosyasında veri bulunamadı.")
        return
    from .excel_islemler import cek_degisim_ozeti
    oz = cek_degisim_ozeti(tl_cekler, usd_cekler,
                           {pb: get_cekler(pb) for pb, c in (("TL", tl_cekler), ("USD", usd_cekler)) if c})
    st.success(" · ".join(f"{pb}: dosyada {o['yeni']} çek ({tr_sayi(o['yeni_tutar'])})" for pb, o in oz.items()))
    st.dataframe(pd.DataFrame([{"Para": pb, "Çek No": c.get("cek_no"), "Vade": c.get("vade"),
                                "Meblağ": c.get("meblagh"), "Kalan": c.get("kalan"), "C/H": c.get("ch_ismi")}
                               for pb, cl in (("TL", tl_cekler), ("USD", usd_cekler)) for c in cl[:150]]),
                 hide_index=True, use_container_width=True, height=220)
    onay = True
    silinecek = {pb: o for pb, o in oz.items() if o["mevcut"]}
    if silinecek:
        st.warning("Kaydedince şu çekler **silinip** dosyadakilerle değiştirilir: "
                   + " · ".join(f"{pb}: {o['mevcut']} çek ({tr_sayi(o['mevcut_tutar'])})" for pb, o in silinecek.items())
                   + ". Yanlış dosyaysa Yükleme geçmişinden geri alınabilir.")
        onay = st.checkbox("Mevcut çeklerin bu dosyayla değiştirileceğini gördüm", key=kapi.anahtar("cek_onay"))
    if st.button("Çekleri kaydet", type="primary", use_container_width=True, disabled=not onay,
                 key=kapi.anahtar("cek_kaydet"), icon=":material/save:"):
        from shared.yukleme_gecmisi import Kayit as _YKayit
        _yk_cek = _YKayit("cek_listesi", dosya.name)   # TL + USD tek kayıt
        if tl_cekler:
            cek_ekle_bulk(tl_cekler, "TL", yukleme=_yk_cek)
        if usd_cekler:
            cek_ekle_bulk(usd_cekler, "USD", yukleme=_yk_cek)
        _yk_cek.kaydet(len(tl_cekler) + len(usd_cekler))
        kapi.bitti(f"Çekler yüklendi: TL {len(tl_cekler)} · USD {len(usd_cekler)}.")


def run():
    """Muhasebe & Finans ana çalıştırıcı. Portal tarafından çağrılır."""
    initialize_db()

    # ── Cache kontrol meta etiketleri ────────────────────────────────────
    APP_VERSION = tr_now().strftime("%Y%m%d%H%M")
    st.markdown(f"""
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <!-- app-version: {APP_VERSION} -->
    """, unsafe_allow_html=True)
    
    # ── CSS ──────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    /* Font @import kaldırıldı — tek kaynak config.toml */
    
    /* ── GLOBAL ── */
    *, *::before, *::after { box-sizing: border-box; }
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        background: var(--k-yuzey0) !important;
        color: var(--k-metin) !important;
    }
    
    .main,
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .stApp {
        background: var(--k-yuzey0) !important;
        min-height: 100vh;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--k-yuzey2); }
    ::-webkit-scrollbar-thumb { background: var(--k-kenar2); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--k-mor2); }
    
    /* ── SIDEBAR ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--k-yuzey1) 0%, var(--k-yuzey2) 40%, var(--k-yuzey1) 100%) !important;
        border-right: 1px solid color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] * {
        color: var(--k-metin) !important;
        font-family: 'Inter', sans-serif !important;
    }
    /* Sidebar nav stili shared/utils.py → sidebar_stil() tarafından yönetilir */
    section[data-testid="stSidebar"] .stNumberInput input {
        background: color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 12%,transparent) !important;
        color: var(--k-mavi) !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size:14px !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] .stButton button {
        background: color-mix(in srgb,var(--k-mavi) 15%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-mavi) 30%,transparent) !important;
        color: var(--k-mavi) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size:13px !important;
        transition: all .2s !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: color-mix(in srgb,var(--k-mavi) 25%,transparent) !important;
        color: var(--k-mavi) !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
    }
    section[data-testid="stSidebar"] a {
        color: var(--k-mavi) !important;
    }
    
    /* ── METRİK KARTLARI ── (eski: metric-container, yeni: stMetric) */
    [data-testid="metric-container"],
    [data-testid="stMetric"] {
        background: var(--k-yuzey2) !important;
        border-radius: 14px !important;
        padding: 20px 22px !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04) !important;
        transition: transform .2s, box-shadow .2s !important;
    }
    [data-testid="metric-container"]:hover,
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08) !important;
    }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] * {
        font-size: 12px !important;
        font-weight: 500 !important;
        letter-spacing: 0 !important;
        text-transform: none !important;
        color: var(--k-soluk) !important;
    }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        font-family: 'JetBrains Mono', monospace !important;
        font-size:23px !important;
        font-weight: 700 !important;
        color: var(--k-metin) !important;
        letter-spacing: -.5px !important;
    }
    
    /* ── BUTONLAR ── */
    /* Tüm butonlar: beyaz zemin, koyu yazı (eski seçici güncel sürümde
       ikon butonlarda tutmuyordu, siyah çıkıyorlardı). Sidebar kendi
       daha spesifik kuralıyla bunu eziyor, dokunulmaz. */
    .stButton > button,
    [data-testid="stButton"] button,
    [data-testid="stBaseButton-secondary"] {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        border-radius: 10px !important;
        padding: 8px 16px !important;
        transition: all .2s !important;
        letter-spacing: .1px !important;
        background: var(--k-yuzey2) !important;
        border: 1.5px solid var(--k-kenar2) !important;
        color: var(--k-soluk) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
    }
    .stButton > button:hover,
    [data-testid="stButton"] button:hover,
    [data-testid="stBaseButton-secondary"]:hover {
        border-color: var(--k-soluk) !important;
        background: var(--k-yuzey3) !important;
        color: var(--k-mavi) !important;
    }
    /* Primary (mavi) butonlar — her yerde geçerli */
    .stButton > button[kind="primary"],
    [data-testid="stButton"] button[kind="primary"],
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, var(--k-mor2), var(--k-mor2)) !important;
        border: none !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
        color: var(--k-metin) !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="stButton"] button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, var(--k-mor2), var(--k-mavi)) !important;
        box-shadow: 0 4px 16px rgba(37,99,235,0.4) !important;
        transform: translateY(-1px) !important;
        color: var(--k-metin) !important;
    }
    /* Popover / Vadeyi Ötele gibi açılır buton tetikleyicileri */
    [data-testid="stPopover"] button {
        background: color-mix(in srgb,var(--k-metin) 5%,transparent) !important;
        border: 1.5px solid color-mix(in srgb,var(--k-metin) 12%,transparent) !important;
        color: var(--k-mavi) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    [data-testid="stPopover"] button:hover {
        border-color: var(--k-soluk) !important;
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
    }
    
    /* ── INPUT ALANLARI (sidebar hariç) ── */
    .stTextInput input, .stNumberInput input, .stSelectbox select,
    .stDateInput input, .stTextArea textarea {
        font-family: 'Inter', sans-serif !important;
        border-radius: 10px !important;
        border: 1.5px solid var(--k-metin) !important;
        font-size: 13px !important;
        padding: 10px 14px !important;
        transition: border-color .2s, box-shadow .2s !important;
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
    }
    /* Sidebar'daki inputs için override (yukarıdaki kural ezilsin) */
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stNumberInput input,
    section[data-testid="stSidebar"] .stSelectbox select,
    section[data-testid="stSidebar"] .stDateInput input {
        background: color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-soluk) 25%,transparent) !important;
        color: var(--k-mavi) !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size:14px !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stNumberInput input:focus {
        background: color-mix(in srgb,var(--k-metin) 9%,transparent) !important;
        border-color: color-mix(in srgb,var(--k-mavi) 50%,transparent) !important;
        box-shadow: 0 0 0 2px color-mix(in srgb,var(--k-mavi) 20%,transparent) !important;
    }
    /* Sidebar number input +/- butonları */
    section[data-testid="stSidebar"] .stNumberInput button {
        background: color-mix(in srgb,var(--k-metin) 5%,transparent) !important;
        border-color: color-mix(in srgb,var(--k-soluk) 20%,transparent) !important;
        color: var(--k-soluk) !important;
    }
    section[data-testid="stSidebar"] .stNumberInput button:hover {
        background: color-mix(in srgb,var(--k-mavi) 20%,transparent) !important;
        color: var(--k-mavi) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus,
    .stSelectbox select:focus, .stDateInput input:focus {
        border-color: var(--k-mor2) !important;
        box-shadow: 0 0 0 3px color-mix(in srgb,var(--k-mavi) 12%,transparent) !important;
        outline: none !important;
    }
    .stTextInput label, .stNumberInput label, .stSelectbox label,
    .stDateInput label, .stTextArea label {
        font-size:13px !important;
        font-weight: 600 !important;
        color: var(--k-soluk) !important;
        letter-spacing: .3px !important;
        margin-bottom: 4px !important;
    }
    
    /* ── EXPANDER ── */
    /* Eski sürüm sınıfı (geriye dönük uyumluluk için kalsın) */
    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        color: var(--k-mavi) !important;
        background: var(--k-yuzey2) !important;
        border-radius: 12px !important;
        border: 1.5px solid var(--k-metin) !important;
        padding: 14px 18px !important;
    }
    .streamlit-expanderContent {
        background: var(--k-yuzey0) !important;
        border: 1.5px solid var(--k-metin) !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
        padding: 16px !important;
    }
    /* Yeni sürüm: [data-testid="stExpander"] + <summary> yapısı */
    [data-testid="stExpander"] details {
        border: 1.5px solid var(--k-metin) !important;
        border-radius: 12px !important;
        background: var(--k-yuzey2) !important;
    }
    [data-testid="stExpander"] summary {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        background: var(--k-yuzey2) !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
    }
    /* Başlık yazısı — açık zeminde kayboluyordu, koyu yap */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary div,
    [data-testid="stExpander"] summary label {
        color: var(--k-mavi) !important;
    }
    /* +/- aç-kapa ikonu görünür olsun */
    [data-testid="stExpander"] summary svg,
    [data-testid="stExpanderToggleIcon"] {
        color: var(--k-mor) !important;
        fill: currentColor !important;
        opacity: 1 !important;
    }
    /* Expander içeriği */
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background: var(--k-yuzey0) !important;
        border-radius: 0 0 12px 12px !important;
        padding: 8px !important;
    }
    
    /* ── DATAFRAME ── */
    div[data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    }
    
    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--k-yuzey2) !important;
        border-radius: 12px !important;
        padding: 4px !important;
        gap: 2px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        color: var(--k-silik) !important;
        padding: 8px 18px !important;
        transition: all .2s !important;
    }
    .stTabs [aria-selected="true"] {
        background: var(--k-yuzey2) !important;
        color: var(--k-mavi) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
    }
    
    /* ── BAŞLIKLAR ── */
    .baslik {
        display: flex !important; align-items: center !important; gap: 11px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 19px !important;
        font-weight:700 !important;
        color: var(--k-mavi) !important;
        letter-spacing: -0.3px !important;
        margin: 2px 0 0 !important;
        line-height: 1.25 !important;
    }
    .baslik-ikon {
        width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
        background: linear-gradient(135deg, color-mix(in srgb,var(--k-mor) 28%,transparent), color-mix(in srgb,var(--k-mor) 16%,transparent));
        border: 1px solid color-mix(in srgb,var(--k-mor) 28%,transparent);
        display: flex; align-items: center; justify-content: center;
        font-size: 14px; letter-spacing: 0;
    }
    .alt-baslik {
        font-size:13px !important;
        color: var(--k-soluk) !important;
        font-weight:400 !important;
        letter-spacing: .1px !important;
        margin: 7px 0 18px !important;
        padding: 0 0 12px 41px !important;
        border-bottom: 1px solid color-mix(in srgb,var(--k-soluk) 10%,transparent) !important;
        position: relative !important;
    }
    .alt-baslik::before {
        content: ""; position: absolute; left: 41px; bottom: -1px;
        width: 40px; height: 2px; border-radius: 2px;
        background: linear-gradient(90deg, var(--k-mor), var(--k-mor));
    }
    
    /* ── BADGE / TAG ── */
    .tag-kirmizi { background:color-mix(in srgb,var(--k-kirmizi) 15%,transparent); color:var(--k-kirmizi2); padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid var(--k-kirmizi); }
    .tag-turuncu { background:color-mix(in srgb,var(--k-amber) 15%,transparent); color:var(--k-amber2); padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid var(--k-amber2); }
    .tag-sari    { background:color-mix(in srgb,var(--k-amber) 15%,transparent); color:#854D0E; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid var(--k-amber2); }
    .tag-yesil   { background:color-mix(in srgb,var(--k-yesil) 15%,transparent); color:var(--k-yesil2); padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid var(--k-yesil2); }
    .tag-mavi    { background:color-mix(in srgb,var(--k-mavi) 15%,transparent); color:var(--k-mavi); padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; letter-spacing:.3px; border:1px solid var(--k-mavi); }
    .tag-gri     { background: var(--k-yuzey2); color:var(--k-silik); padding:4px 12px; border-radius:20px; font-size:11px; font-weight:600; border:1px solid color-mix(in srgb,var(--k-metin) 12%,transparent); }
    
    /* ── ALERT KUTULARI ── */
    .uyari-box {
        background: linear-gradient(135deg, color-mix(in srgb,var(--k-amber) 15%,transparent), color-mix(in srgb,var(--k-amber) 15%,transparent));
        border-left: 4px solid var(--k-amber);
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
        color: var(--k-amber2);
        box-shadow: 0 1px 4px color-mix(in srgb,var(--k-amber) 10%,transparent);
    }
    .info-box {
        background: linear-gradient(135deg, color-mix(in srgb,var(--k-mavi) 15%,transparent), color-mix(in srgb,var(--k-mavi) 15%,transparent));
        border-left: 4px solid var(--k-mor2);
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
        color: var(--k-mavi);
        box-shadow: 0 1px 4px color-mix(in srgb,var(--k-mavi) 10%,transparent);
    }
    .ok-box {
        background: linear-gradient(135deg, color-mix(in srgb,var(--k-yesil) 15%,transparent), color-mix(in srgb,var(--k-yesil) 15%,transparent));
        border-left: 4px solid var(--k-yesil2);
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
        color: var(--k-yesil2);
        box-shadow: 0 1px 4px color-mix(in srgb,var(--k-yesil) 10%,transparent);
    }
    .alarm-box {
        background: color-mix(in srgb,var(--k-kirmizi) 9%,var(--k-yuzey1));
        border-left: 4px solid var(--k-kirmizi);
        padding: 12px 16px;
        border-radius: 0 10px 10px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
        color: var(--k-kirmizi2);
        box-shadow: 0 1px 4px color-mix(in srgb,var(--k-kirmizi) 10%,transparent);
    }
    
    /* ── FORM ALANLARI ── */
    div[data-testid="stForm"] {
        background: var(--k-yuzey2) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    }
    
    /* ── DIVIDER ── */
    hr {
        border: none !important;
        border-top: 1px solid var(--k-mavi) !important;
        margin: 20px 0 !important;
    }
    
    /* ── SUCCESS / ERROR / WARNING / INFO ── */
    /* Zemin + çerçeve TEK katmanda (stAlertContainer). Eskiden dış kutuya
       çerçeve, iç kutuya zemin veriliyordu → "kutu içinde kutu" + ince şerit.
       Genel kutu ölçüsü shared/tasarim.py'de; burada yalnız modül renkleri. */
    div[data-testid="stAlertContainer"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        font-weight:400 !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
        background: color-mix(in srgb,var(--k-amber) 12%,var(--k-yuzey1)) !important;
        color: var(--k-amber2) !important;
        border-color: color-mix(in srgb,var(--k-amber2) 45%,transparent) !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
        background: color-mix(in srgb,var(--k-kirmizi) 10%,var(--k-yuzey1)) !important;
        color: var(--k-kirmizi2) !important;
        border-color: color-mix(in srgb,var(--k-kirmizi2) 45%,transparent) !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
        background: color-mix(in srgb,var(--k-mavi) 10%,var(--k-yuzey1)) !important;
        color: var(--k-mavi) !important;
        border-color: color-mix(in srgb,var(--k-mavi) 45%,transparent) !important;
    }
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
        background: color-mix(in srgb,var(--k-yesil) 12%,var(--k-yuzey1)) !important;
        color: var(--k-yesil2) !important;
        border-color: color-mix(in srgb,var(--k-yesil2) 45%,transparent) !important;
    }
    
    /* Tüm alert içindeki text - parent'tan inherit etsin */
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] div {
        color: inherit !important;
    }
    
    /* Alert içindeki bold yazıları daha koyu yap */
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] b {
        font-weight: 700 !important;
        color: inherit !important;
    }
    
    /* ── SPINNER ── */
    .stSpinner > div {
        border-top-color: var(--k-mor2) !important;
    }
    
    /* ── MONO FONT ── */
    .mono {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
        letter-spacing: -.3px !important;
    }
    
    /* ── KART ── */
    .pro-kart {
        background: var(--k-yuzey2);
        border-radius: 16px;
        padding: 20px 24px;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent);
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.04);
        transition: all .2s;
        margin-bottom: 12px;
    }
    .pro-kart:hover {
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }
    
    /* ── DOWNLOAD BUTON ── */
    .stDownloadButton button {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
    }
    
    /* ── MARKDOWN ── */
    .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
        font-size: 14px !important;
        color: var(--k-mavi) !important;
        line-height: 1.6 !important;
    }
    
    /* ── STREAMLIT ÜST BAR (HEADER) — yüksek kontrast, net ikonlar ── */
    header[data-testid="stHeader"],
    [data-testid="stHeader"] {
        background: var(--k-metin) !important;
        backdrop-filter: blur(10px) !important;
        border-bottom: 1px solid var(--k-metin) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    /* Metin ve linkler koyu olsun (fill'i ZORLA dayatma — ikonları bozuyordu) */
    [data-testid="stHeader"] span,
    [data-testid="stHeader"] a,
    [data-testid="stHeader"] p,
    [data-testid="stToolbar"] span,
    [data-testid="stToolbarActions"] span {
        color: var(--k-mavi) !important;
        opacity: 1 !important;
    }
    /* Buton zemini şeffaf, yazı koyu */
    [data-testid="stHeader"] button,
    [data-testid="stToolbar"] button,
    [data-testid="stToolbarActions"] button,
    [data-testid="stMainMenu"] button {
        background: transparent !important;
        color: var(--k-mavi) !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        opacity: 1 !important;
    }
    [data-testid="stHeader"] button:hover,
    [data-testid="stToolbar"] button:hover {
        background: var(--k-yuzey2) !important;
        border-color: var(--k-mavi) !important;
        color: var(--k-metin) !important;
    }
    /* İkonlar: yalnızca SVG'yi currentColor ile boya — arka plan şekillerini doldurma */
    [data-testid="stHeader"] svg,
    [data-testid="stToolbar"] svg,
    [data-testid="stToolbarActions"] svg,
    [data-testid="stMainMenu"] svg {
        color: var(--k-mavi) !important;
        fill: currentColor !important;
        opacity: 1 !important;
    }
    /* Share / deploy butonu — net çerçeveli, okunur */
    [data-testid="stHeader"] [data-testid="stBaseButton-header"],
    [data-testid="stHeader"] [data-testid="stBaseButton-headerNoPadding"] {
        color: var(--k-metin) !important;
        background: var(--k-yuzey2) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    
    /* ── DARK MODE OVERRIDE — TÜM YAZILARI ZORLA DÜZELT ── */
    .stApp, .stApp * {
        color-scheme: light !important;
    }
    .stApp {
        background: var(--k-yuzey0) !important;
    }
    /* Ana içerik yazıları — login sayfasını eziyordu, kaldırıldı */
    /* Yazı renkleri her sayfa için kendi spesifik kurallarında ayarlandı */
    /* Tab yazıları */
    .stTabs [data-baseweb="tab"] span { color: var(--k-silik) !important; }
    .stTabs [aria-selected="true"] span { color: var(--k-mavi) !important; }
    /* Info / success / warning / error kutuları */
    /* DataFrame içi */
    .stDataFrame * { color: var(--k-metin) !important; }
    /* Expander */
    .streamlit-expanderHeader p, .streamlit-expanderHeader span { color: var(--k-mavi) !important; }
    /* Selectbox, input */
    .stSelectbox div, .stTextInput div, .stNumberInput div { color: var(--k-metin) !important; }
    
    /* ─── LOGIN SAYFASI — global override'ları ez ─── */
    /* Sol panel: tüm elementler default BEYAZ — yüksek specificity */
    .stApp .login-left-panel,
    .stApp .login-left-panel *,
    .stApp .login-left-panel div,
    .stApp .login-left-panel p,
    .stApp .login-left-panel span,
    .stApp .login-left-panel h1,
    .stApp .login-left-panel h2,
    body .login-left-panel,
    body .login-left-panel * {
        color: var(--k-metin) !important;
    }
    /* Açık gri (muted) yazılar için ayrı kural */
    .stApp .login-left-panel .login-muted,
    body .login-left-panel .login-muted {
        color: var(--k-mavi) !important;
    }
    .stApp .login-left-panel .login-accent,
    body .login-left-panel .login-accent {
        color: var(--k-mor2) !important;
    }
    /* "profesyonelce" gradient — color:transparent koruyalım */
    .stApp .login-left-panel h1 .login-gradient-text,
    body .login-left-panel h1 .login-gradient-text {
        background: linear-gradient(135deg,var(--k-mavi),var(--k-mor2),var(--k-mor)) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        color: transparent !important;
        display: inline-block !important;
    }
    
    /* Sağ panel kart: BEYAZ kart, içinde KOYU yazılar */
    .stApp .login-right-card,
    .stApp .login-right-card *,
    .stApp .login-right-card div,
    .stApp .login-right-card p,
    .stApp .login-right-card span,
    .stApp .login-right-card h2,
    body .login-right-card,
    body .login-right-card * {
        color: var(--k-metin) !important;
    }
    .stApp .login-right-card .login-card-muted,
    body .login-right-card .login-card-muted { color: var(--k-silik) !important; }
    .stApp .login-right-card .login-card-success,
    body .login-right-card .login-card-success { color: #047857 !important; }
    
    /* ── FILE UPLOADER — KARANLIK ALAN DÜZELTMESİ ── */
    [data-testid="stFileUploader"] {
        background: var(--k-yuzey2) !important;
        border-radius: 14px !important;
    }
    [data-testid="stFileUploader"] > div,
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] section > div {
        background: var(--k-yuzey2) !important;
        border-radius: 12px !important;
    }
    [data-testid="stFileUploader"] section {
        border: 2px dashed var(--k-mavi) !important;
        padding: 16px !important;
    }
    [data-testid="stFileUploader"] button {
        background: color-mix(in srgb,var(--k-mavi) 15%,transparent) !important;
        color: var(--k-mavi) !important;
        border: 1.5px solid var(--k-mavi) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] p,
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] p {
        color: var(--k-silik) !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: var(--k-yuzey2) !important;
        border: 2px dashed var(--k-mavi) !important;
        border-radius: 12px !important;
    }
    
    /* ── DOWNLOAD BUTONU ── */
    [data-testid="stDownloadButton"] button {
        background: var(--k-yuzey2) !important;
        border: 1.5px solid var(--k-metin) !important;
        color: var(--k-mavi) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        background: var(--k-yuzey2) !important;
        border-color: var(--k-mavi) !important;
    }
    
    /* ── SELECTBOX DROPDOWN — Karanlık açılır paneli düzelt ── */
    [data-baseweb="select"] > div {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
        border: 1.5px solid var(--k-metin) !important;
        border-radius: 10px !important;
    }
    [data-baseweb="select"] > div:hover {
        border-color: var(--k-mavi) !important;
    }
    [data-baseweb="select"] span {
        color: var(--k-metin) !important;
        font-weight:400 !important;
    }
    [data-baseweb="select"] svg {
        color: var(--k-silik) !important;
        fill: var(--k-silik) !important;
    }
    
    /* Açılır liste popover */
    [data-baseweb="popover"] {
        background: var(--k-yuzey2) !important;
        border-radius: 10px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.08) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
    }
    [data-baseweb="popover"] * {
        background-color: transparent !important;
        color: var(--k-metin) !important;
    }
    [data-baseweb="menu"] {
        background: var(--k-yuzey2) !important;
        padding: 4px !important;
        border-radius: 8px !important;
    }
    [data-baseweb="menu"] * {
        color: var(--k-metin) !important;
    }
    [data-baseweb="menu"] li,
    [role="option"] {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
        padding: 8px 12px !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight:400 !important;
        transition: background .15s !important;
    }
    [data-baseweb="menu"] li:hover,
    [role="option"]:hover,
    [role="option"][aria-selected="true"] {
        background: color-mix(in srgb,var(--k-mavi) 15%,transparent) !important;
        color: var(--k-mavi) !important;
    }
    [data-baseweb="option"] {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
    }
    [data-baseweb="option"]:hover {
        background: color-mix(in srgb,var(--k-mavi) 15%,transparent) !important;
        color: var(--k-mavi) !important;
    }
    /* Açık bir şekilde koyu renk oluşumlarını engelle */
    ul[role="listbox"] {
        background: var(--k-yuzey2) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent) !important;
    }
    ul[role="listbox"] li {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
    }
    
    /* ── NUMBER / TEXT / DATE INPUT (sidebar dışı) ── */
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stDateInput"] input,
    textarea {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
    }
    /* Sidebar'da bu kuralı ez */
    section[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
    section[data-testid="stSidebar"] [data-testid="stTextInput"] input,
    section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
        background: color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
        color: var(--k-mavi) !important;
    }
    
    /* ── CHECKBOX ── */
    /* ── CHECKBOX ── (etiket okunur + kutu açık zeminli, siyah çıkmasın) */
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] label p,
    [data-testid="stCheckbox"] label div,
    [data-testid="stCheckbox"] label span,
    [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] {
        color: var(--k-mavi) !important;
    }
    /* Kutucuğun kendisi: beyaz zemin, belirgin kenarlık */
    [data-testid="stCheckbox"] [data-baseweb="checkbox"] span[aria-hidden="true"],
    [data-testid="stCheckbox"] [role="checkbox"] {
        background-color: var(--k-metin) !important;
        border: 1.5px solid var(--k-soluk) !important;
        border-radius: 5px !important;
    }
    /* İşaretliyken mavi dolgu, beyaz tik */
    [data-testid="stCheckbox"] [aria-checked="true"] span[aria-hidden="true"],
    [data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"] {
        background-color: var(--k-mor2) !important;
        border-color: var(--k-mor2) !important;
        color: var(--k-metin) !important;
    }
    [data-testid="stCheckbox"] [aria-checked="true"] svg { fill: var(--k-metin) !important; }
    
    /* ── SIDEBAR HARİÇ TUT ── */
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] label {
        color: var(--k-metin) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] * {
        color: var(--k-metin) !important;
        background: color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
    }
    
    /* ── HTML TABLE IN stMarkdown (dark theme) ── */
    .stMarkdown table { border-collapse: collapse !important; width: 100% !important; background: var(--k-yuzey1) !important; }
    .stMarkdown table tr { background: var(--k-yuzey2) !important; }
    .stMarkdown table tr:nth-child(odd) { background: var(--k-yuzey1) !important; }
    .stMarkdown table td { color: var(--k-mavi) !important; }
    .stMarkdown table th { color: var(--k-soluk) !important; background: var(--k-yuzey0) !important; }
    .stMarkdown table tr:nth-child(even) td { background: color-mix(in srgb,var(--k-metin) 3%,transparent) !important; }
</style>
    """, unsafe_allow_html=True)
    

    # ── ANA İÇERİK ────────────────────────────────────────────────────
    # ── YARDIMCI FONKSİYONLAR ────────────────────────────────────────────
    GUNLER = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"]
    
    # Renkler shared.tasarim.GRAFIK_PALET'ten: koyu zeminde birbirinden ayırt
    # edilebilir tonlar. (Eskiden Çek=Kredi aynı kırmızı, SGK≈İthalat aynı
    # camgöbeği, Maaş/Masraf gibi koyu tonlar zeminde görünmüyordu.)
    from shared.tasarim import GRAFIK_PALET as _GP
    KATEGORILER = {
        "cek":      {"label": "Çek",         "oncelik": 1,  "renk": _GP[3]},
        "kredi":    {"label": "Kredi",        "oncelik": 2,  "renk": _GP[7]},
        "kart":     {"label": "K.Kartı",      "oncelik": 3,  "renk": _GP[2]},
        "vergi":    {"label": "Vergi",        "oncelik": 4,  "renk": _GP[0]},
        "sgk":      {"label": "SGK",          "oncelik": 5,  "renk": _GP[4]},
        "kira":     {"label": "Kira",         "oncelik": 6,  "renk": _GP[1]},
        "sabit":    {"label": "Sabit Gider",  "oncelik": 7,  "renk": _GP[9]},
        "cari":     {"label": "Cari Hesap",   "oncelik": 8,  "renk": _GP[5]},
        "ithalat":  {"label": "İthalat",      "oncelik": 9,  "renk": _GP[6]},
        "ihracat":  {"label": "İhracat",      "oncelik": 10, "renk": _GP[8]},
        "masraf":   {"label": "Masraf",       "oncelik": 11, "renk": _GP[11]},
        "maas":     {"label": "Maaş",         "oncelik": 12, "renk": _GP[10]},
        "diger":    {"label": "Diğer",        "oncelik": 13, "renk": _GP[12]},
    }
    
    
    def fmt(n):
        if n is None or (isinstance(n, float) and pd.isna(n)):
            return "-"
        return f"{float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    
    def fmt_tarih(s):
        if not s:
            return ""
        try:
            d = pd.to_datetime(s)
            return d.strftime("%d.%m.%Y")
        except Exception:
            return str(s)
    
    
    def today_iso():
        return tr_today_iso()
    
    
    def get_kur():
        """
        USD/TL Kurunu döndürür.
        İlk çağrıda (session başladığında) otomatik olarak API'den günceli çeker.
        Başarısız olursa 38.50 fallback kullanır.
        Bir kez çekildikten sonra session boyunca aynı değeri kullanır (manuel güncellenirse değişir).
        """
        if "kur" not in st.session_state:
            # İlk defa çağrılıyor — API'den otomatik çek
            st.session_state.kur = 38.50  # önce fallback değer
            try:
                kur_cekilen, basarili = _fetch_kur_ilk_yukleme()
                if basarili and kur_cekilen and kur_cekilen > 1:
                    st.session_state.kur = kur_cekilen
                    st.session_state.kur_otomatik_cekildi = True
            except Exception:
                pass  # hata olsa da uygulama çalışsın, fallback kullanılır
        return st.session_state.kur
    
    
    def _fetch_kur_ilk_yukleme():
        """İlk yüklemede kur çekmek için ayrı fonksiyon — toast/spinner olmadan sessizce çalışır."""
        apis = [
            ("https://open.er-api.com/v6/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://api.exchangerate-api.com/v4/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", lambda d: round(d["usd"]["try"], 2)),
            ("https://api.frankfurter.app/latest?from=USD&to=TRY", lambda d: round(d["rates"]["TRY"], 2)),
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        for url, parser in apis:
            try:
                r = requests.get(url, timeout=5, headers=headers)
                d = r.json()
                kur = parser(d)
                if kur and kur > 1:
                    return kur, True
            except Exception:
                continue
        return 38.50, False
    
    
    def fetch_kur_live():
        """Birden fazla API kaynağından USD/TL kurunu çeker."""
        apis = [
            ("https://open.er-api.com/v6/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://api.exchangerate-api.com/v4/latest/USD", lambda d: round(d["rates"]["TRY"], 2)),
            ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", lambda d: round(d["usd"]["try"], 2)),
            ("https://api.frankfurter.app/latest?from=USD&to=TRY", lambda d: round(d["rates"]["TRY"], 2)),
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        for url, parser in apis:
            try:
                r = requests.get(url, timeout=8, headers=headers)
                d = r.json()
                kur = parser(d)
                if kur and kur > 1:
                    st.session_state.kur = kur
                    return kur, True
            except Exception:
                continue
        return get_kur(), False
    
    
    def get_aktif_odemeler():
        hafta = get_aktif_hafta()
        if not hafta:
            return [], None
        return get_hafta_odemeler(hafta["id"]), hafta
    
    
    def vade_durumu(vade_str):
        """Vade tarihine göre alarm durumu döndürür."""
        if not vade_str:
            return "normal"
        try:
            v = pd.to_datetime(vade_str).date()
            today = tr_today()
            if v < today:
                return "gecmis"
            elif v == today:
                return "bugun"
            elif v == today + timedelta(days=1):
                return "yarin"
            return "normal"
        except Exception:
            return "normal"
    
    
    # ── SIDEBAR ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<script>var s=window.parent.document.querySelector("[data-testid=stSidebar] > div");if(s)s.scrollTop=0;</script>', unsafe_allow_html=True)
        from shared.utils import sidebar_ust
        sidebar_ust("💳", "Muhasebe & Finans", "kayranacc")
        aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    
        # Aktif hafta göster
        hafta = get_aktif_hafta()
        if hafta:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:8px;
                background:rgba(37,99,235,0.10);
                border:1px solid color-mix(in srgb,var(--k-mavi) 22%,transparent);
                border-radius:999px;
                padding:6px 12px;margin-bottom:12px;">
                <span style="font-size:13px">📅</span>
                <span style="font-size:11px;color:var(--k-mavi);font-weight:600;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                    letter-spacing:.2px">{hafta['hafta_adi'].title()}</span>
            </div>
            """, unsafe_allow_html=True)
    
        # ─── Sayfa listesi (kullanıcıya göre dinamik) ───
        aktif_kullanici_lower = st.session_state.get("aktif_kullanici", "").lower().strip()
        # Toplam Aktifler sayfasına yetkili kullanıcılar (yeni eklemek için bu set'e ekle)
        YETKILI_KULLANICILAR_TOPLAM_AKTIFLER = _toplam_aktifler_yetkilileri()
        KISITLI_SAYFALAR = ["💰 Toplam Aktifler"]
    
        from shared.gezinme import secenekler
        tum_sayfalar = secenekler("kayranacc")
    
        # Yetkili olmayan kullanıcılar için kısıtlı sayfaları menüden çıkar
        if aktif_kullanici_lower not in YETKILI_KULLANICILAR_TOPLAM_AKTIFLER:
            gosterilen_sayfalar = [s for s in tum_sayfalar if s not in KISITLI_SAYFALAR]
        else:
            gosterilen_sayfalar = tum_sayfalar
    
        from shared.tasarim import menu_etiketi as _me
        from shared.gezinme import sayfa_menusu
        sayfa = sayfa_menusu("Sayfa", gosterilen_sayfalar, modul="kayranacc", label_visibility="collapsed",
                         format_func=_me, key="acc_sayfa")     # palet / adres çubuğu bu anahtarla gider
    
        st.markdown("---")
    
        # Kur paneli
        st.markdown("**USD/TL Kur**")
    
        # get_kur() çağır — session yeni ise otomatik API'den çekilir
        mevcut_kur = get_kur()
    
        # İlk otomatik çekim olduysa küçük bildirim
        if st.session_state.get("kur_otomatik_cekildi") and not st.session_state.get("kur_bildirim_gosterildi"):
            st.markdown(k_mesaj("basari", "Güncel kur otomatik alındı"), unsafe_allow_html=True)
            st.session_state.kur_bildirim_gosterildi = True
    
        yeni_kur = st.number_input("USD/TL Kur",
            value=float(mevcut_kur),
            step=0.01,
            min_value=1.0,
            format="%.4f",
            label_visibility="collapsed",
        )
        st.session_state.kur = yeni_kur
    
        if st.button("Güncel Kur", use_container_width=True, icon=":material/refresh:"):
            with st.spinner("Alınıyor..."):
                kur_cekilen, basarili = fetch_kur_live()
            if basarili:
                st.session_state.kur = kur_cekilen
                st.success(f"✅ {kur_cekilen} ₺")
                st.rerun()
            else:
                st.error("❌ Bağlanamadı, manuel girin.")
    
        st.markdown(f"<small>{tr_now().strftime('%d.%m.%Y %H:%M')}</small>", unsafe_allow_html=True)
    
        st.markdown("---")
    
        # ── Uygulamayı Yenile (Browser cache'i temizle + veri yenile) ──
        st.markdown("**Sistem**")
        if st.button("Uygulamayı Yenile", use_container_width=True, help="Verileri ve arayüzü tazele", icon=":material/refresh:"):
            # Session state'i temizle (kullanıcı bilgisi hariç)
            korunacak = {"giris_yapildi", "aktif_kullanici"}
            for k in list(st.session_state.keys()):
                if k not in korunacak:
                    del st.session_state[k]
            # Streamlit cache'lerini temizle
            try:
                st.cache_data.clear()
            except Exception:
                pass
            # JavaScript ile tarayıcı hard-reload (cache bypass)
            st.markdown("""
            <script>
                if (window.parent && window.parent.location) {
                    window.parent.location.reload(true);
                } else {
                    location.reload(true);
                }
            </script>
            """, unsafe_allow_html=True)
            st.rerun()
    
        # Versiyon bilgisi (küçük, alt köşe)
        st.markdown(
            f'<div style="font-size:11px;color:var(--k-silik);margin-top:8px;text-align:center;'
            f'letter-spacing:.5px;font-family:monospace;opacity:0.6;">v{APP_VERSION}</div>',
            unsafe_allow_html=True
        )
    
    
    # ════════════════════════════════════════════════════════════════════
    # 1) DASHBOARD
    # ════════════════════════════════════════════════════════════════════
    @st.dialog("🔁 Bankalar Arası Virman", width="large")
    def _dlg_virman():
    
        bankalar = get_bankalar()
        kur = get_kur()

        if len(bankalar) < 2:
            st.warning("⚠️ Virman için en az 2 banka hesabınız olmalı. Önce 'Banka Bakiyeleri' sayfasından hesap ekleyin.")
            st.stop()

        # ── 🏦 Banka bakiyeleri (üstte tek bakışta — virman öncesi durumu gör) ──
        _renk_pb_v = {"USD": trenk("mavi"), "TL": trenk("mor"), "EUR": trenk("mor")}
        metrik_satiri([{
            "label": b["hesap_adi"],
            "value": (("$" if b["para_birimi"] == "USD" else ("€" if b["para_birimi"] == "EUR" else "₺"))
                      + f"{tr_sayi(float(b['bakiye']), 2)}"),
            "renk": _renk_pb_v.get(b["para_birimi"], trenk("mor")),
            "alt": b["para_birimi"],
        } for b in bankalar])
        _v_tl = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "TL")
        _v_usd = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "USD")
        _v_eur = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "EUR")
        _v_usd_esde = _v_usd + (_v_tl / kur if kur else 0) + (_v_eur * 1.08)
        st.markdown(
            '<div style="background:color-mix(in srgb,var(--k-mor) 6%,transparent);border:1px solid color-mix(in srgb,var(--k-mor) 20%,transparent);'
            'border-radius:10px;padding:8px 16px;margin:8px 0 16px;display:flex;gap:24px;flex-wrap:wrap;'
            'align-items:center;font-size:13px">'
            '<span style="color:var(--k-soluk);font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:1px">Toplam</span>'
            f'<span style="color:var(--k-mor)">TL <b style="color:var(--k-metin);font-family:monospace">₺{tr_sayi(_v_tl, 2)}</b></span>'
            f'<span style="color:var(--k-mavi)">USD <b style="color:var(--k-metin);font-family:monospace">${tr_sayi(_v_usd, 2)}</b></span>'
            + (f'<span style="color:var(--k-mor)">EUR <b style="color:var(--k-metin);font-family:monospace">€{tr_sayi(_v_eur, 2)}</b></span>' if _v_eur else '')
            + f'<span style="color:var(--k-yesil)">≈ USD karşılığı <b style="font-family:monospace">${tr_sayi(_v_usd_esde, 2)}</b></span>'
            '</div>', unsafe_allow_html=True)

        # ─── Yeni Virman Formu ───
        st.markdown("### ➕ Yeni Virman")
    
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Kaynak Hesap**")
            kaynak_options = {f"{b['hesap_adi']} ({b['para_birimi']}) — Bakiye: {tr_sayi(float(b['bakiye']), 2)}": b['id'] for b in bankalar}
            kaynak_secim = st.selectbox("Kaynak", list(kaynak_options.keys()), key="virman_kaynak")
            kaynak_id = kaynak_options[kaynak_secim]
            kaynak_banka = next(b for b in bankalar if b['id'] == kaynak_id)
    
        with col2:
            st.markdown("**Hedef Hesap**")
            hedef_options = {f"{b['hesap_adi']} ({b['para_birimi']}) — Bakiye: {tr_sayi(float(b['bakiye']), 2)}": b['id']
                             for b in bankalar if b['id'] != kaynak_id}
            if not hedef_options:
                st.warning("Başka hesap yok.")
                st.stop()
            hedef_secim = st.selectbox("Hedef", list(hedef_options.keys()), key="virman_hedef")
            hedef_id = hedef_options[hedef_secim]
            hedef_banka = next(b for b in bankalar if b['id'] == hedef_id)
    
        # Para birimi farklılığı uyarısı + kur input
        farkli_pb = kaynak_banka['para_birimi'] != hedef_banka['para_birimi']
    
        col_t, col_k = st.columns([2, 1])
        with col_t:
            kaynak_bakiye_val = float(kaynak_banka.get('bakiye') or 0)
            tutar = st.number_input(
                f"Tutar ({kaynak_banka['para_birimi']})",
                min_value=0.0,
                max_value=max(kaynak_bakiye_val, 0.01),  # 0 ise input'u kullanılabilir tut
                step=0.01,
                format="%.4f",
                key="virman_tutar",
                disabled=(kaynak_bakiye_val <= 0)
            )
            if kaynak_bakiye_val <= 0:
                st.caption("Bu hesabın bakiyesi 0 veya negatif. Virman yapılamaz.")
        with col_k:
            if farkli_pb:
                kullanilan_kur = st.number_input(
                    f"Kur ({kaynak_banka['para_birimi']}/{hedef_banka['para_birimi']})",
                    value=float(kur),
                    min_value=0.01,
                    step=0.01,
                    format="%.4f",
                    key="virman_kur",
                    help=f"1 USD = {kur} TL kullanılıyor"
                )
            else:
                kullanilan_kur = None
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption("Aynı para birimi, kur gerekmez")
    
        # Hedefe gidecek hesaplanmış tutar (önizleme)
        if farkli_pb and kullanilan_kur and tutar > 0:
            if kaynak_banka['para_birimi'] == "TL" and hedef_banka['para_birimi'] == "USD":
                hedef_tutar_onizleme = tutar / kullanilan_kur
            elif kaynak_banka['para_birimi'] == "USD" and hedef_banka['para_birimi'] == "TL":
                hedef_tutar_onizleme = tutar * kullanilan_kur
            else:
                hedef_tutar_onizleme = tutar
            st.info(f"➡️ Hedef hesaba **{tr_sayi(hedef_tutar_onizleme, 2)} {hedef_banka['para_birimi']}** eklenecek (Kur: {kullanilan_kur})")
        elif tutar > 0:
            st.info(f"➡️ Hedef hesaba **{tr_sayi(tutar, 2)} {hedef_banka['para_birimi']}** eklenecek")
    
        aciklama = st.text_input("Açıklama (opsiyonel)", placeholder="Örn: Maaş ödemeleri için TL transferi", key="virman_aciklama")
    
        if st.button("Virmanı Yap", type="primary", use_container_width=True, icon=":material/sync_alt:"):
            if tutar <= 0:
                st.error("Tutar 0'dan büyük olmalı.")
            elif tutar > kaynak_bakiye_val:
                st.error(f"Yetersiz bakiye! Maksimum: {tr_sayi(kaynak_bakiye_val, 2)} {kaynak_banka['para_birimi']}")
            else:
                with st.spinner("İşleniyor..."):
                    basarili, mesaj = virman_yap(kaynak_id, hedef_id, tutar, aciklama, kullanilan_kur)
                if basarili:
                    st.success(mesaj)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {mesaj}")
    
        st.markdown("---")
    
        # ─── Geçmiş Virmanlar ───
        st.markdown("### 📜 Son Virmanlar")
        virmanlar = get_virmanlar(limit=30)
    
        if not virmanlar:
            st.info("Henüz virman kaydı yok.")
        else:
            for v in virmanlar:
                kaynak_pb = v.get('kaynak_para_birimi') or 'TL'
                hedef_pb = v.get('hedef_para_birimi') or 'TL'
                kaynak_sym = "$" if kaynak_pb == "USD" else "₺"
                hedef_sym = "$" if hedef_pb == "USD" else "₺"
    
                # Float dönüşümleri (string olabilir)
                try:
                    v_tutar = float(v.get('tutar') or 0)
                except (TypeError, ValueError):
                    v_tutar = 0.0
                try:
                    v_hedef_tutar = float(v.get('hedef_tutar') or 0)
                except (TypeError, ValueError):
                    v_hedef_tutar = 0.0
                v_kur = v.get('kur_kullanilan')
                try:
                    v_kur_float = float(v_kur) if v_kur else None
                except (TypeError, ValueError):
                    v_kur_float = None
    
                col_a, col_b = st.columns([8, 1])
                with col_a:
                    kur_str = f" • Kur: {v_kur_float:.2f}" if v_kur_float else ""
                    tarih_str = v.get('tarih', '')
                    aciklama_str = f"<br><small style='color:var(--k-soluk)'>📝 {v.get('aciklama')}</small>" if v.get('aciklama') else ""
    
                    st.markdown(f"""
                    <div style="background:var(--k-yuzey2);border:1px solid color-mix(in srgb,var(--k-metin) 12%,transparent);border-radius:10px;padding:12px 16px;margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <span style="font-size:13px;font-weight:700;color:var(--k-metin)">{v.get('kaynak_hesap_adi','?')}</span>
                                <span style="margin:0 8px;color:var(--k-soluk);font-size:14px">→</span>
                                <span style="font-size:13px;font-weight:700;color:var(--k-metin)">{v.get('hedef_hesap_adi','?')}</span>
                            </div>
                            <div style="text-align:right">
                                <span style="font-family:monospace;color:var(--k-kirmizi);font-weight:600">-{kaynak_sym}{tr_sayi(v_tutar, 2)}</span>
                                &nbsp;&nbsp;
                                <span style="font-family:monospace;color:var(--k-yesil);font-weight:600">+{hedef_sym}{tr_sayi(v_hedef_tutar, 2)}</span>
                            </div>
                        </div>
                        <div style="font-size:11px;color:var(--k-silik);margin-top:4px">
                            🗓️ {tarih_str}{kur_str}
                            {aciklama_str}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("", key=f"virman_geri_{v['id']}", help="Bu virmanı geri al", icon=":material/undo:"):
                        basarili, mesaj = virman_geri_al(v['id'])
                        if basarili:
                            st.success(mesaj)
                            st.rerun()
                        else:
                            st.error(mesaj)
    
    
    # ════════════════════════════════════════════════════════════════════
    # 12) ERTELENEN ÖDEMELER
    # ════════════════════════════════════════════════════════════════════

    # ── Sayfa gövdesi: KENDİ İÇİNDE YENİLENEN PARÇA (st.fragment) ───────────
    # HIZ: Sayfadaki filtre, seçim kutusu, sekme ya da onay kutusu değişince
    # yalnız bu gövde yeniden çizilir; üst menü, sol menü, oturum kontrolü ve
    # ortak CSS yeniden çalışmaz. Kayıt sonrası st.rerun() çağrıları ESKİSİ
    # GİBİ tüm sayfayı yeniler (Streamlit 1.64'te parça içi st.rerun() tam
    # yenilemedir). Blok ile dış kapsamın paylaştığı değişkenler nonlocal ile
    # aynen korunur (otomatik hesaplandı; tests/test_parca.py denetler).
    @st.fragment
    def _sayfa_parcasi():
        nonlocal basarili, hafta, k
        if sayfa == "📊 Dashboard":
            st.markdown(_sb("📊 Muhasebe", "Genel Bakış", aciklama="Haftalık ödeme durumu ve finansal özet"), unsafe_allow_html=True)
    
            kur = get_kur()
            odemeler, hafta = get_aktif_odemeler()
            bankalar = get_bankalar()
    
            if not odemeler:
                st.info("📂 Henüz veri yüklenmemiş. üst menüdeki **Dosya** düğmesinden Excel dosyanızı yükleyin veya manuel ödeme ekleyin.")
                st.stop()
    
            # Alarmlar
            alarmlar = [o for o in odemeler if o["durum"] == "bekliyor" and vade_durumu(o.get("vade")) in ("bugun", "yarin", "gecmis")]
            bugun_alarmlar = [o for o in alarmlar if vade_durumu(o.get("vade")) == "bugun"]
            yarin_alarmlar = [o for o in alarmlar if vade_durumu(o.get("vade")) == "yarin"]
            gecmis_alarmlar = [o for o in alarmlar if vade_durumu(o.get("vade")) == "gecmis"]
    
            if gecmis_alarmlar:
                isimler = ", ".join(o["firma"] for o in gecmis_alarmlar[:3])
                st.markdown(k_mesaj("hata", f"<b>Gecikmiş ödeme</b> · {len(gecmis_alarmlar)} ödeme vadesi geçmiş: {_html.escape(isimler)}", ham=True),
                            unsafe_allow_html=True)
            if bugun_alarmlar:
                isimler = ", ".join(o["firma"] for o in bugun_alarmlar[:3])
                st.markdown(k_mesaj("uyari", f"<b>Bugün vadeli</b> · {len(bugun_alarmlar)} ödeme — {_html.escape(isimler)}", ham=True),
                            unsafe_allow_html=True)
            if yarin_alarmlar:
                isimler = ", ".join(o["firma"] for o in yarin_alarmlar[:3])
                st.markdown(k_mesaj("bilgi", f"<b>Yarın vadeli</b> · {len(yarin_alarmlar)} ödeme — {_html.escape(isimler)}", ham=True),
                            unsafe_allow_html=True)
    
            # Özet metrikler
            tl_toplam = sum(o["tutar_tl"] or 0 for o in odemeler)
            usd_toplam = sum(o["tutar_usd"] or 0 for o in odemeler)
            odendi_tl = sum(o["tutar_tl"] or 0 for o in odemeler if o["durum"] == "odendi")
            odendi_usd = sum(o["tutar_usd"] or 0 for o in odemeler if o["durum"] == "odendi")
            bekleyen_tl = tl_toplam - odendi_tl
            bekleyen_usd = usd_toplam - odendi_usd
            odendi_cnt = sum(1 for o in odemeler if o["durum"] == "odendi")
            banka_tl = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "TL")
            banka_usd = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "USD")
            hafta_sonu_tl = banka_tl - bekleyen_tl - (bekleyen_usd * kur)
            ilerleme_pct = int((odendi_cnt / len(odemeler)) * 100) if odemeler else 0
    
            # ── Bugünün özeti ──
            today = today_iso()
            bugun_odemeler = [o for o in odemeler if (o.get("vade") or "")[:10] == today]
            bugun_tl_toplam  = sum(o.get("tutar_tl") or 0 for o in bugun_odemeler)
            bugun_usd_toplam = sum(o.get("tutar_usd") or 0 for o in bugun_odemeler)
            bugun_odendi_tl  = sum(o.get("tutar_tl") or 0 for o in bugun_odemeler if o["durum"] == "odendi")
            bugun_odendi_usd = sum(o.get("tutar_usd") or 0 for o in bugun_odemeler if o["durum"] == "odendi")
            bugun_kalan_tl   = bugun_tl_toplam - bugun_odendi_tl
            bugun_kalan_usd  = bugun_usd_toplam - bugun_odendi_usd
    
            # ── Profesyonel Metrik Kartları ──
            nakit_bg    = trenk("yesil2") if hafta_sonu_tl >= 0 else trenk("kirmizi2")
            nakit_renk  = trenk("yesil2") if hafta_sonu_tl >= 0 else trenk("kirmizi2")
            nakit_label = "Hafta Sonu Kalan" if hafta_sonu_tl >= 0 else "Nakit Açığı"
            nakit_alt   = "Tahmini bakiye" if hafta_sonu_tl >= 0 else "Tahmini açık"
            nakit_emoji = "✅" if hafta_sonu_tl >= 0 else "⚠️"

            from shared.tasarim import KART_YENI as _kart_yeni
            if _kart_yeni:
                # Ortak kartlar (Ekim 2026): ana kart hafta sonu kalan / nakit açığı
                from kayranacc.genel_kartlar import haftalik_ozet_kartlari, bugun_kartlari
                st.markdown('<style>.section-mini-title{font-size:14px;font-weight:650;color:var(--k-metin);'
                            'margin:18px 0 8px;}</style><div class="section-mini-title">Haftalık özet</div>',
                            unsafe_allow_html=True)
                metrik_satiri(haftalik_ozet_kartlari(
                    tl_toplam=tl_toplam, odendi_tl=odendi_tl, usd_toplam=usd_toplam, kur=kur,
                    odendi_cnt=odendi_cnt, toplam_cnt=len(odemeler), bekleyen_tl=bekleyen_tl,
                    hafta_sonu_tl=hafta_sonu_tl, fmt=fmt))
                st.markdown('<div class="section-mini-title">Bugünün bekleyen ödemeleri</div>', unsafe_allow_html=True)
                metrik_satiri(bugun_kartlari(bugun_kalan_tl=bugun_kalan_tl, bugun_kalan_usd=bugun_kalan_usd, fmt=fmt))
            else:
              st.markdown(f"""
            <style>
            /* .kart ailesi ortak katmanın takma adı — HTML değişmedi. */
            .kart-grid {{ display:flex;flex-wrap:wrap;gap:var(--k-gap);margin-bottom:var(--k-gap) }}
            .kart {{
                flex:1;min-width:132px;background:var(--k-yuzey1);
                border:1px solid var(--k-kenar);border-left:2px solid var(--k-mor);
                border-radius:var(--k-r);padding:var(--k-pad);text-align:left;
                transition:background .12s ease,border-color .12s ease;
            }}
            .kart:hover {{ background:var(--k-yuzey2);border-color:var(--k-kenar2) }}
            .kart-label {{ font-size:12px;font-weight:500;color:var(--k-soluk); }}
            .kart-deger {{ font-size:19px;font-weight:700;font-family:var(--k-mono);
                font-variant-numeric:tabular-nums;letter-spacing:-0.2px;
                line-height:1.25;color:var(--k-metin); }}
            .kart-alt {{ font-size:11px;margin-top:2px;color:var(--k-silik);font-weight:400 }}
            .section-mini-title {{ font-size:14px;font-weight:650;color:var(--k-metin);margin:18px 0 8px; }}
            </style>
    
            <div class="section-mini-title">Haftalık özet</div>
            <div class="kart-grid">
    
              <div class="kart" style="border-left-color:var(--k-mor2)">
                <div class="kart-label">Toplam TL</div>
                <div class="kart-deger">₺{fmt(tl_toplam)}</div>
                <div class="kart-alt">Ödendi: ₺{fmt(odendi_tl)}</div>
              </div>
    
              <div class="kart" style="border-left-color:var(--k-mor)">
                <div class="kart-label">Toplam USD</div>
                <div class="kart-deger">${fmt(usd_toplam)}</div>
                <div class="kart-alt">≈ ₺{fmt(usd_toplam * kur)}</div>
              </div>
    
              <div class="kart" style="border-left-color:var(--k-yesil)">
                <div class="kart-label">İlerleme</div>
                <div class="kart-deger" style="color:var(--k-yesil)">{odendi_cnt} <span style="font-size:14px;color:var(--k-soluk);font-weight:600">/ {len(odemeler)}</span></div>
                <div style="background:color-mix(in srgb,var(--k-metin) 10%,transparent);border-radius:4px;height:5px;margin-top:8px;overflow:hidden">
                  <div style="background:var(--k-yesil);height:100%;width:{ilerleme_pct}%"></div>
                </div>
                <div class="kart-alt" style="margin-top:4px">%{ilerleme_pct} tamamlandı</div>
              </div>
    
              <div class="kart" style="border-left-color:var(--k-amber)">
                <div class="kart-label">Bekleyen TL</div>
                <div class="kart-deger">₺{fmt(bekleyen_tl)}</div>
                <div class="kart-alt">Ödenmesi gereken</div>
              </div>
    
              <div class="kart" style="border-left-color:{trenk('yesil') if hafta_sonu_tl >= 0 else trenk('kirmizi')}">
                <div class="kart-label">{nakit_label}</div>
                <div class="kart-deger" style="color:{trenk('yesil') if hafta_sonu_tl >= 0 else trenk('kirmizi')}">₺{fmt(abs(hafta_sonu_tl))}</div>
                <div class="kart-alt">{nakit_alt}</div>
              </div>
    
            </div>
    
            <div class="section-mini-title">Bugünün bekleyen ödemeleri</div>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:24px">
              <div class="kart" style="border-left-color:var(--k-amber)">
                <div class="kart-label">Bugün Kalan TL</div>
                <div class="kart-deger">{"₺" + fmt(bugun_kalan_tl) if bugun_kalan_tl else "—"}</div>
                <div class="kart-alt">Ödenmemiş TL</div>
              </div>
              <div class="kart" style="border-left-color:var(--k-amber)">
                <div class="kart-label">Bugün Kalan USD</div>
                <div class="kart-deger">{"$" + fmt(bugun_kalan_usd) if bugun_kalan_usd else "—"}</div>
                <div class="kart-alt">Ödenmemiş USD</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
    
            # ── Toplam Varlıklar (Banka Bakiyelerinden) ──
            banka_eur = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "EUR")
            toplam_varlik_tl = banka_tl + (banka_usd * kur)
            toplam_varlik_usd = banka_usd + (banka_tl / kur if kur > 0 else 0)
            st.markdown('<div class="section-mini-title">Toplam varlıklar</div>', unsafe_allow_html=True)
            metrik_satiri([
                {"label": "Toplam TL Varlık", "value": f"₺{fmt(banka_tl)}", "renk": trenk("mor"), "alt": "Tüm TL hesaplar"},
                {"label": "Toplam USD Varlık", "value": f"${fmt(banka_usd)}", "renk": trenk("mor"), "alt": f"≈ ₺{fmt(banka_usd * kur)}"},
                {"label": "Toplam Varlık (TL)", "value": f"₺{fmt(toplam_varlik_tl)}", "renk": trenk("mor"), "alt": f"≈ ${fmt(toplam_varlik_usd)}"},
                {"label": "Toplam Varlık (USD)", "value": f"${fmt(toplam_varlik_usd)}", "renk": trenk("mor"), "alt": f"≈ ₺{fmt(toplam_varlik_tl)}"},
            ])
    
            st.markdown("---")
    
            # Kategori dağılımı ve durum grafikleri
            col1, col2 = st.columns(2)
    
            with col1:
                st.markdown('<div class="section-mini-title" style="margin:4px 0 2px">Kategoriye göre ödemeler</div>', unsafe_allow_html=True)
                kat_data = {}
                for o in odemeler:
                    kat = o.get("kategori") or "diger"
                    label = KATEGORILER.get(kat, {}).get("label", "Diğer")
                    tl = (o.get("tutar_tl") or 0) + (o.get("tutar_usd") or 0) * kur
                    kat_data[label] = kat_data.get(label, 0) + tl
    
                if kat_data:
                    fig = go.Figure(go.Pie(
                        labels=list(kat_data.keys()),
                        values=list(kat_data.values()),
                        hole=0.72,                              # ince modern halka
                        sort=True, direction="clockwise",
                        marker=dict(
                            colors=[KATEGORILER.get(k, {}).get("renk", trenk("silik"))
                                        for k in [next((key for key, v in KATEGORILER.items() if v["label"] == lab), "diger")
                                                  for lab in kat_data.keys()]],
                            # Dilim arası boşluk hissi: zeminle aynı renkte kalın ayraç
                            line=dict(color=trenk("yuzey0"), width=3),
                        ),
                        # Açık renkli dilim üstünde koyu yazı okunur (eskiden açık mavi
                        # yazı açık dilimde kayboluyordu).
                        textfont=dict(family="Inter, sans-serif", size=12, color=trenk("yuzey0")),
                        textposition="inside",
                        textinfo="percent",
                        insidetextorientation="horizontal",
                        customdata=[f"₺{tr_sayi(v, 2)}" for v in kat_data.values()],
                        hovertemplate="<b>%{label}</b><br>%{customdata}<br>%{percent}<extra></extra>",
                    ))
                    _kat_toplam = sum(kat_data.values())
                    # Ortak halka düzeni (shared/grafik.py). Kategori renkleri korunur: burada
                    # renk kategoriyi ayırır (renk kuralının tek istisnası).
                    from shared.grafik import halka as _halka, goster as _goster
                    _halka(fig, "Toplam", (f"₺{tr_sayi(_kat_toplam/1e6, 1)}M" if _kat_toplam >= 1e6
                                           else f"₺{tr_sayi(_kat_toplam)}"), yukseklik=330)
                    _goster(fig)
    
            with col2:
                st.markdown('<div class="section-mini-title" style="margin:4px 0 2px">Ödeme durumu</div>', unsafe_allow_html=True)
                odendi_tutar = sum((o.get("tutar_tl") or 0) + (o.get("tutar_usd") or 0) * kur
                                   for o in odemeler if o["durum"] == "odendi")
                bekleyen_tutar = sum((o.get("tutar_tl") or 0) + (o.get("tutar_usd") or 0) * kur
                                     for o in odemeler if o["durum"] == "bekliyor")
                # ORTADAKİ YÜZDE HALKAYLA AYNI ÖLÇÜDE olmalı. Eskiden halka TUTARA,
                # ortadaki "%x TAMAMLANAN" ise ADEDE göre hesaplanıyordu: halka
                # yarı yeşilken ortada %0 yazabiliyordu. Artık ikisi de tutar.
                _durum_toplam = odendi_tutar + bekleyen_tutar
                if _durum_toplam <= 0:
                    st.markdown(
                        '<div style="height:300px;display:flex;align-items:center;justify-content:center;'
                        'color:var(--k-soluk);font-size:13px;border:1px dashed color-mix(in srgb,var(--k-soluk) 18%,transparent);'
                        'border-radius:10px">Bu dönemde ödeme kaydı yok</div>',
                        unsafe_allow_html=True)
                else:
                    _odenen_pct = round(odendi_tutar / _durum_toplam * 100)
                    fig2 = go.Figure(go.Pie(
                        labels=["Ödendi", "Bekliyor"],
                        values=[odendi_tutar, bekleyen_tutar],
                        hole=0.72, sort=False, direction="clockwise",
                        marker=dict(
                            colors=[trenk("yesil"), trenk("amber")],   # anlam: ödenen / bekleyen
                        ),
                        textfont=dict(family="Inter, sans-serif", size=12, color=trenk("yuzey0")),
                        textposition="inside",
                        textinfo="percent",
                        customdata=[f"₺{tr_sayi(v, 2)}" for v in (odendi_tutar, bekleyen_tutar)],
                        hovertemplate="<b>%{label}</b><br>%{customdata}<br>%{percent}<extra></extra>",
                    ))
                    from shared.grafik import halka as _halka, goster as _goster
                    _halka(fig2, "Ödenen (tutar)", f"%{_odenen_pct}", f"{odendi_cnt}/{len(odemeler)} ödeme",
                           yukseklik=330)
                    _goster(fig2)
    
            # Günlük ödeme takvimi özeti (varsayılan kapalı — simge durumunda)
            from collections import defaultdict
            by_day = defaultdict(list)
            for o in odemeler:
                day = (o.get("vade") or "")[:10] or "?"
                by_day[day].append(o)
    
            tablo_rows = []
            for day in sorted(by_day.keys()):
                try:
                    d = pd.to_datetime(day)
                    gun_adi = GUNLER[d.dayofweek + 1] if d.dayofweek < 6 else GUNLER[0]
                    tarih_str = d.strftime("%d.%m.%Y")
                except Exception:
                    gun_adi = ""
                    tarih_str = day
    
                gun_odemeler = by_day[day]
                gun_tl = sum(o.get("tutar_tl") or 0 for o in gun_odemeler)
                gun_usd = sum(o.get("tutar_usd") or 0 for o in gun_odemeler)
                gun_odendi = sum(1 for o in gun_odemeler if o["durum"] == "odendi")
                vd = vade_durumu(day)
    
                tablo_rows.append({
                    "Gün": gun_adi,
                    "Tarih": tarih_str,
                    "Ödeme Sayısı": len(gun_odemeler),
                    "Ödendi": gun_odendi,
                    "Bekliyor": len(gun_odemeler) - gun_odendi,
                    "Tutar TL (₺)": f"₺{fmt(gun_tl)}" if gun_tl else "-",
                    "Tutar USD ($)": f"${fmt(gun_usd)}" if gun_usd else "-",
                    "Firma": ", ".join(sorted(set(o.get("firma") or "-" for o in gun_odemeler))),
                    "Açıklama": " | ".join(o.get("aciklama") or "-" for o in gun_odemeler),
                    "Durum": "⏰ BUGÜN" if vd == "bugun" else ("📅 YARIN" if vd == "yarin" else ("🚨 GECİKMİŞ" if vd == "gecmis" else "—")),
                })
    
            df_tablo = pd.DataFrame(tablo_rows)

            # ── Takvim tablosu: ortak tablo_html (Aşama 4b — elle yazılmış HTML kaldırıldı) ──
            def render_takvim_tablosu(df):
                if df.empty:
                    st.info("Veri yok.")
                    return
                _ROZET = {"GECİKMİŞ": ("🚨 GECİKMİŞ", "kirmizi"), "BUGÜN": ("⏰ BUGÜN", "amber"), "YARIN": ("📅 YARIN", "mavi")}

                def _durum(d):
                    for anahtar, (etiket, renk) in _ROZET.items():
                        if anahtar in str(d):
                            return rozet_html(etiket, renk)
                    return None

                def _vurgu(r):
                    for anahtar, (_, renk) in _ROZET.items():
                        if anahtar in str(r.get("Durum", "")):
                            return renk
                    return None

                satirlar = []
                for _, row in df.iterrows():
                    bekliyor = int(row.get("Bekliyor", 0) or 0)
                    satirlar.append({
                        "Gün": renkli(row.get("Gün", ""), "mavi", kalin=True),
                        "Tarih": row.get("Tarih", ""),
                        "Ödeme": int(row.get("Ödeme Sayısı", 0) or 0),
                        "Ödendi": renkli(int(row.get("Ödendi", 0) or 0), "yesil", kalin=True),
                        "Bekliyor": renkli(bekliyor, "kirmizi" if bekliyor > 0 else "yesil", kalin=True),
                        "Tutar TL (₺)": row.get("Tutar TL (₺)", ""),
                        "Tutar USD ($)": row.get("Tutar USD ($)", ""),
                        "Firma": kisalt(row.get("Firma", "")),
                        "Açıklama": kisalt(row.get("Açıklama", "")),
                        "Durum": _durum(row.get("Durum", "")),
                    })
                st.html(tablo_html(
                    ["Gün", ("Tarih", "mono"), ("Ödeme", "adet", "$", "orta"), ("Ödendi", "adet", "$", "orta"),
                     ("Bekliyor", "adet", "$", "orta"), ("Tutar TL (₺)", "mono", "$", "sag"),
                     ("Tutar USD ($)", "mono", "$", "sag"), "Firma", "Açıklama", ("Durum", "metin", "$", "orta")],
                    satirlar, vurgu=_vurgu))


            @st.dialog("📅 Günlük Ödeme Takvimi", width="large")
            def _dlg_odeme_takvimi():
                render_takvim_tablosu(df_tablo)
            if st.button("Günlük Ödeme Takvimi", key="btn_acc_takvim", use_container_width=True, icon=":material/calendar_month:"):
                _dlg_odeme_takvimi()
    
    
        # ════════════════════════════════════════════════════════════════════
        # 2) BU HAFTA
        # ════════════════════════════════════════════════════════════════════
        elif sayfa == "💳 Bu Hafta":
            # Ekim 2026: ödeme masası (kayranacc/odeme_ekran.py). İş kuralları
            # (bakiye düşme/iade, kısmi ödeme, öteleme) database.py'de, değişmedi.
            from .odeme_ekran import render_bu_hafta
            render_bu_hafta(KATEGORILER, export_excel, get_kur())


        # ════════════════════════════════════════════════════════════════════
        # 3) BANKA BAKİYELERİ
        # ════════════════════════════════════════════════════════════════════
        elif sayfa == "🏦 Banka Bakiyeleri":
            # Ekim 2026: eylemler başlıkta; hesaplar tıklanır kart (bakiye kesilmez);
            # ekle/düzenle formları pencerede, silme ONAYLI (eskiden onaysızdı).
            from shared import bilesen as _Bb
            from .banka_ekran import banka_kartlari, banka_toplam, banka_yeni_dialog, banka_detay_kontrol
            _bey = _Bb.baslik_eylem(
                "🏦 Muhasebe", "Banka Bakiyeleri",
                aciklama="Hesap bakiyeleri, hafta sonu tahmini, para girişi ve hesaplar arası transfer.",
                eylemler=[{"etiket": "Virman", "key": "bnk_virman", "icon": ":material/sync_alt:",
                           "help": "Bankalar arası para transferi"},
                          {"etiket": "Arbitraj", "key": "bnk_arb", "icon": ":material/currency_exchange:",
                           "help": "Aynı bankada TL / USD / EUR çevrimi"},
                          {"etiket": "Hesap", "key": "bnk_yeni", "icon": ":material/add_card:",
                           "help": "Yeni banka hesabı ekle"},
                          {"etiket": "Tahsilat", "key": "bnk_tahsilat", "icon": ":material/payments:",
                           "birincil": True, "help": "Bankaya para girişi"}])
    
            kur = get_kur()
            bankalar = get_bankalar()
            odemeler, hafta = get_aktif_odemeler()
    
            bekleyen_tl = sum(o.get("tutar_tl") or 0 for o in odemeler if o["durum"] == "bekliyor")
            bekleyen_usd = sum(o.get("tutar_usd") or 0 for o in odemeler if o["durum"] == "bekliyor")
    
            if bankalar:
                banka_toplam(bankalar, kur, bekleyen_tl, bekleyen_usd)
                banka_kartlari(bankalar, kur, bekleyen_tl, bekleyen_usd)
            else:
                st.info("Henüz banka hesabı eklenmemiş.")

            # ── 💰 Gelen Tahsilat (bankaya para girişi) ──
            if bankalar:
                @st.dialog("💰 Tahsilat Ekle — Bankaya Para Girişi", width="large")
                def _dlg_tahsilat():
                    st.caption("Müşteriden/dışarıdan gelen ödemeyi seçtiğin banka hesabına ekler.")
                    _opts = {f"{b['hesap_adi']} ({b['para_birimi']}) — Bakiye: {tr_sayi(float(b['bakiye']), 2)}": b
                             for b in bankalar}
                    _sec = st.selectbox("Hangi hesaba girdi?", list(_opts))
                    _bank = _opts[_sec]
                    _pb = _bank["para_birimi"]
                    _sym = "$" if _pb == "USD" else ("€" if _pb == "EUR" else "₺")

                    with st.form("tahsilat_form"):
                        _tutar = st.number_input(f"Tutar ({_pb})", min_value=0.0, step=0.0001, format="%.4f")
                        _kaynak = st.text_input("Kimden / Kaynak", placeholder="Örn: Hepsiburada hakediş, ABC Ltd.")
                        _acik = st.text_input("Açıklama (opsiyonel)", placeholder="Örn: Haziran satış ödemesi")
                        _tarih = st.date_input("Tarih", value=tr_today(), format="DD.MM.YYYY")
                        _onay = st.form_submit_button(f"{_sym} Tahsilatı İşle", type="primary", use_container_width=True, icon=":material/payments:")
                        if _onay:
                            if _tutar <= 0:
                                st.error("Tutar 0'dan büyük olmalı.")
                            else:
                                ok, msg = tahsilat_ekle(_bank["id"], _tutar, _kaynak, _acik, _tarih)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

                    # Son tahsilatlar — geri alma imkânıyla
                    _son = get_tahsilatlar(limit=8)
                    if _son:
                        st.markdown("---")
                        st.markdown("**Son tahsilatlar**")
                        for t in _son:
                            _ts = "$" if t.get("para_birimi") == "USD" else ("€" if t.get("para_birimi") == "EUR" else "₺")
                            c1, c2 = st.columns([5, 1])
                            _knk = f" · {t['kaynak']}" if t.get("kaynak") else ""
                            c1.markdown(
                                f"<div style='font-size:13px'>{str(t.get('tarih',''))[:10]} — "
                                f"<b>{_ts}{tr_sayi(float(t.get('tutar') or 0), 2)}</b> → {t.get('hesap_adi','')}"
                                f"<span style='color:var(--k-soluk)'>{_knk}</span></div>",
                                unsafe_allow_html=True)
                            if c2.button("", key=f"tahsilat_geri_{t['id']}", help="Geri al", icon=":material/undo:"):
                                ok, msg = tahsilat_geri_al(t["id"])
                                st.toast(msg)
                                st.rerun()

                if _bey.get("bnk_tahsilat"):
                    _dlg_tahsilat()


            if _bey.get("bnk_yeni"):
                banka_yeni_dialog()
            banka_detay_kontrol(kur)

            # ─── Virman / Arbitraj pencereleri (başlıktaki düğmelerden açılır) ───

            # ─── ARBİTRAJ: aynı banka içinde TL ↔ USD çevrimi ───
            # Mekanik olarak virman ile aynı yola gider (virman_yap bakiyeleri
            # günceller ve 'virmanlar' tablosuna kayıt atar). Ayrı bir veri yolu
            # AÇILMADI — tek kayıt kaynağı korunur. Fark arayüzde: banka bir kez
            # seçilir, yön düğmeyle belirlenir, karşılık anında hesaplanır.
            # ─── ARBİTRAJ: aynı banka içinde TL / USD / EUR çevrimi ───
            # Altı yönün hepsi desteklenir: TL↔USD, TL↔EUR, USD↔EUR.
            #
            # KUR YORUMU — tek kural: "1 <güçlü birim> = kur <zayıf birim>".
            # Güçlülük sırası EUR > USD > TL. Böylece kullanıcı kuru her zaman
            # piyasada konuşulduğu gibi girer (1 USD = 48,68 TL / 1 EUR = 1,08 USD)
            # ve yön karışıklığı olmaz. Hesaplanan karşılık virman_yap'a AÇIKÇA
            # hedef_tutar olarak geçilir — çevrim tek yerde, burada yapılır.
            _PB_SIRA = {"TL": 0, "TRY": 0, "USD": 1, "EUR": 2}
            _PB_SIM = {"TL": "₺", "TRY": "₺", "USD": "$", "EUR": "€"}

            def _pb_std(p):
                p = str(p or "").upper()
                return "TL" if p == "TRY" else p

            @st.dialog("💱 Arbitraj — Aynı Banka (TL / USD / EUR)", width="large")
            def _dlg_arbitraj():
                _bnk = get_bankalar() or []
                if not _bnk:
                    st.warning("Kayıtlı banka hesabı yok.")
                    return

                def _kok(ad):
                    """'YAPI KREDİ BANKASI - USD' → 'YAPI KREDİ BANKASI'."""
                    s = str(ad or "").strip()
                    for _ayr in (" - ", " – ", " — ", " -", "- "):
                        if _ayr in s:
                            s = s.split(_ayr)[0]
                            break
                    for _son in ("USD", "TRY", "TL", "EUR", "$", "₺", "€"):
                        if s.upper().endswith(_son):
                            s = s[: -len(_son)]
                    return " ".join(s.split()).rstrip("-–— ").strip()

                # Aynı bankanın TL / USD / EUR hesaplarını grupla
                _grup = {}
                for b in _bnk:
                    _pb = _pb_std(b.get("para_birimi"))
                    if _pb in _PB_SIRA:
                        _grup.setdefault(_kok(b.get("hesap_adi")), {})[_pb] = b

                # En az İKİ farklı para birimi olan bankalar
                _uygun = {k: v for k, v in _grup.items() if len(v) >= 2}
                if not _uygun:
                    st.warning("Arbitraj için aynı bankada **en az iki farklı para "
                               "biriminde** hesap gerekiyor (TL / USD / EUR).")
                    st.caption("Hesap adları 'BANKA ADI - TL', 'BANKA ADI - USD' "
                               "biçiminde olursa otomatik eşleşir.")
                    return

                _banka_ad = st.selectbox("🏦 Banka", sorted(_uygun.keys()), key="arb_banka")
                _hesaplar = _uygun[_banka_ad]

                # Mevcut bakiyeler
                _mcols = st.columns(len(_hesaplar))
                for _c, _pb in zip(_mcols, sorted(_hesaplar, key=lambda x: _PB_SIRA[x])):
                    _c.metric(f"{_pb} Hesap",
                              f"{tr_sayi(float(_hesaplar[_pb].get('bakiye') or 0), 2)} {_PB_SIM[_pb]}")

                _pblar = sorted(_hesaplar.keys(), key=lambda x: _PB_SIRA[x])
                y1, y2 = st.columns(2)
                _kpb = y1.selectbox("Bozulacak (kaynak)", _pblar, key="arb_kaynak_pb")
                _hedefler = [p for p in _pblar if p != _kpb]
                _hpb = y2.selectbox("Alınacak (hedef)", _hedefler, key="arb_hedef_pb")

                _kaynak, _hedef = _hesaplar[_kpb], _hesaplar[_hpb]
                _k_bak = float(_kaynak.get("bakiye") or 0)
                _h_bak = float(_hedef.get("bakiye") or 0)

                # Kur her zaman güçlü birim üzerinden sorulur
                _guclu, _zayif = (_kpb, _hpb) if _PB_SIRA[_kpb] > _PB_SIRA[_hpb] else (_hpb, _kpb)
                _usd_tl = float(get_kur() or 1)
                _vars = {("USD", "TL"): _usd_tl, ("EUR", "TL"): _usd_tl * 1.08,
                         ("EUR", "USD"): 1.08}.get((_guclu, _zayif), 1.0)

                a1, a2 = st.columns([2, 1])
                _tutar = a1.number_input(
                    f"Bozulacak tutar ({_kpb})", min_value=0.0, step=0.01, format="%.4f",
                    max_value=max(_k_bak, 0.01), key="arb_tutar", disabled=(_k_bak <= 0))
                _kur = a2.number_input(f"Kur — 1 {_guclu} = ? {_zayif}", min_value=0.0001,
                                       step=0.01, format="%.4f", value=float(_vars),
                                       key=f"arb_kur_{_guclu}_{_zayif}",
                                       help="Bankanın uyguladığı gerçek kuru gir")
                if _k_bak <= 0:
                    st.caption(f"{_kpb} hesabının bakiyesi 0 veya negatif.")

                # Zayıf → güçlü ise BÖL, güçlü → zayıf ise ÇARP
                _karsilik = (_tutar / _kur) if _PB_SIRA[_kpb] < _PB_SIRA[_hpb] else (_tutar * _kur)

                if _tutar > 0:
                    st.success(f"➡️ **{tr_sayi(_tutar, 2)} {_kpb}** bozulacak, "
                               f"**{tr_sayi(_karsilik, 2)} {_hpb}** alınacak  ·  "
                               f"1 {_guclu} = {tr_sayi(_kur, 4)} {_zayif}")
                    z1, z2 = st.columns(2)
                    z1.metric(f"{_kpb} Hesap (sonra)", f"{tr_sayi(_k_bak - _tutar, 2)} {_PB_SIM[_kpb]}",
                              delta=f"{-_tutar:+,.2f}")
                    z2.metric(f"{_hpb} Hesap (sonra)", f"{tr_sayi(_h_bak + _karsilik, 2)} {_PB_SIM[_hpb]}",
                              delta=f"{_karsilik:+,.2f}")

                _not = st.text_input("Açıklama", key="arb_not",
                                     placeholder="örn. 14.09 arbitraj, banka kuru 48,92")

                if st.button("Arbitrajı Gerçekleştir", type="primary",
                             use_container_width=True, key="arb_btn",
                             disabled=(_tutar <= 0 or _k_bak <= 0), icon=":material/currency_exchange:"):
                    _ack = (f"Arbitraj · {_banka_ad} · {_kpb}→{_hpb} · "
                            f"1 {_guclu}={tr_sayi(_kur, 4)} {_zayif}"
                            + (f" · {_not.strip()}" if (_not or "").strip() else ""))
                    # Karşılık BURADA hesaplandı; virman_yap'a açıkça geçiliyor ki
                    # çevrim iki yerde ayrı ayrı yapılmasın.
                    _ok, _msg = virman_yap(_kaynak["id"], _hedef["id"], float(_tutar),
                                           _ack, float(_kur), hedef_tutar=float(_karsilik))
                    if _ok:
                        st.success(f"✅ {_msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {_msg}")

            if _bey.get("bnk_virman"):
                _dlg_virman()
            if _bey.get("bnk_arb"):
                _dlg_arbitraj()
        elif sayfa == "💸 Nakit Akış":
            st.markdown(_sb("💸 Muhasebe", "Nakit Akış", aciklama="Bekleyen ödemeler baz alınmıştır"), unsafe_allow_html=True)
    
            kur = get_kur()
            odemeler, hafta = get_aktif_odemeler()
            bankalar = get_bankalar()
    
            if not odemeler:
                st.info("Veri yok.")
                st.stop()
    
            banka_tl = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "TL")
            banka_usd = sum(b["bakiye"] for b in bankalar if b["para_birimi"] == "USD")
    
            from collections import defaultdict
            by_day = defaultdict(list)
            for o in odemeler:
                if o["durum"] == "bekliyor":
                    day = (o.get("vade") or "")[:10] or "?"
                    by_day[day].append(o)
    
            kum_tl = 0
            kum_usd = 0
            tablo_rows = []
    
            for day in sorted(by_day.keys()):
                gun_tl = sum(o.get("tutar_tl") or 0 for o in by_day[day])
                gun_usd = sum(o.get("tutar_usd") or 0 for o in by_day[day])
                kum_tl += gun_tl
                kum_usd += gun_usd
                kalan = banka_tl - kum_tl - (kum_usd * kur)
    
                tablo_rows.append({
                    "Tarih": day,
                    "Günlük TL (₺)": gun_tl or None,
                    "Günlük USD ($)": gun_usd or None,
                    "Kümülatif TL (₺)": kum_tl,
                    "Kümülatif USD ($)": kum_usd,
                    "TL Bakiye Kalan (₺)": kalan,
                    "_kalan": kalan,
                })
    
            net_tl = banka_tl - kum_tl - (kum_usd * kur)
            tablo_rows.append({
                "Tarih": "TOPLAM",
                "Günlük TL (₺)": kum_tl,
                "Günlük USD ($)": kum_usd,
                "Kümülatif TL (₺)": kum_tl,
                "Kümülatif USD ($)": kum_usd,
                "TL Bakiye Kalan (₺)": net_tl,
                "_kalan": net_tl,
            })
    
            df_nakit = pd.DataFrame(tablo_rows)
    
            # --- Nakit Akış tablosu: ortak tablo_html (Aşama 4b) ---
            def _kalan_hucre(v, kalin=False):
                return renkli(_tpara(v, "₺", 2), "yesil" if (v or 0) >= 0 else "kirmizi", kalin=kalin)

            _nk_kol = [("Tarih", "mono"), ("Günlük TL", "para", "₺"), ("Günlük USD", "para", "$"),
                       ("Küm. TL", "para", "₺"), ("Küm. USD", "para", "$"), ("TL Bakiye", "para", "₺")]
            _nk_satir, _nk_toplam = [], None
            for row in tablo_rows:
                kayit = {
                    "Tarih": row["Tarih"] if row["Tarih"] == "TOPLAM" else fmt_tarih(row["Tarih"]),
                    "Günlük TL": row.get("Günlük TL (₺)") or None,
                    "Günlük USD": row.get("Günlük USD ($)") or None,
                    "Küm. TL": row.get("Kümülatif TL (₺)") or None,
                    "Küm. USD": row.get("Kümülatif USD ($)") or None,
                    "TL Bakiye": _kalan_hucre(row.get("_kalan") or 0, kalin=row["Tarih"] == "TOPLAM"),
                }
                if row["Tarih"] == "TOPLAM":
                    kayit["Tarih"] = "Σ TOPLAM"
                    _nk_toplam = kayit
                else:
                    _nk_satir.append(kayit)
            st.html(tablo_html(_nk_kol, _nk_satir, toplam=_nk_toplam,
                               vurgu=lambda r: "kirmizi" if "k-kirmizi" in str(r["TL Bakiye"]) else None))
    
            # Grafik
            df_grafik = pd.DataFrame([r for r in tablo_rows if r["Tarih"] != "TOPLAM"])
            if len(df_grafik) > 1:
                # Eksen: GÜN etiketi (kategori). Eskiden gerçek tarih verildiği için
                # eksen İngilizce ve saat çizgiliydi ("Sep 27, 2026 · 12:00").
                # Üzerine gelince çıkan kutu: TR biçimli hazır metin (customdata).
                # Eskiden şablona Python fonksiyonu (tr_sayi) yazılmıştı — grafik bunu anlamaz,
                # tutar hiç görünmüyordu.
                from .odeme_hesap import GUN_KISA as _GUN
                def _gx(t):
                    try:
                        _d = pd.to_datetime(t).date()
                        return f"{_d.day:02d}.{_d.month:02d} {_GUN[_d.weekday()]}"
                    except Exception:
                        return str(t)
                _x = [_gx(t) for t in df_grafik["Tarih"]]
                _gun_tl = df_grafik["Günlük TL (₺)"].fillna(0)
                _kalan = df_grafik["TL Bakiye Kalan (₺)"]
                # Ortak grafik dili (shared/grafik.py): ödeme çubukları ana renk, kalan bakiye
                # nötr çizgi; bakiye eksiye düştüğü gün kırmızı nokta (nakit açığı).
                from shared.grafik import goster as _goster, rol as _rol
                st.markdown('<div class="section-mini-title">Günlük ödeme ve kalan bakiye</div>',
                            unsafe_allow_html=True)
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=_x, y=_gun_tl, name="Günlük TL ödemesi",
                    marker_color=_rol("ana"), marker_line=dict(width=0),
                    customdata=[f"₺{tr_sayi(v, 2)}" for v in _gun_tl],
                    hovertemplate="Günlük: %{customdata}<extra></extra>",
                ))
                _kal = list(_kalan.fillna(0))
                fig.add_trace(go.Scatter(
                    x=_x, y=_kalan, name="Kalan bakiye", mode="lines+markers", yaxis="y2",
                    line=dict(color=_rol("ikincil"), width=2),
                    marker=dict(size=[8 if v < 0 else 5 for v in _kal],
                                color=[_rol("kotu") if v < 0 else _rol("ikincil") for v in _kal]),
                    customdata=[f"₺{tr_sayi(v, 2)}" for v in _kal],
                    hovertemplate="Kalan: %{customdata}<extra></extra>",
                ))
                _goster(fig, key="nakit_akis_grafik", yukseklik=380, hovermode="x unified", bargap=0.45,
                        barcornerradius=4, xaxis=dict(type="category"), yaxis=dict(tickprefix="₺"),
                        yaxis2=dict(overlaying="y", side="right", showgrid=False, zeroline=False,
                                    tickprefix="₺", tickfont=dict(size=11, color=_rol("ikincil"))))
    
    
        # ════════════════════════════════════════════════════════════════════
        # 5) FİRMA ÇEKLERİ
        # ════════════════════════════════════════════════════════════════════
        elif sayfa == "📋 Firma Çekleri":
            st.markdown(_sb("📋 Muhasebe", "Firma Çekleri", aciklama="TL ve USD bazında çek takibi"), unsafe_allow_html=True)
    
            def cek_ozet_kart(cekler, cur):
                if not cekler:
                    return
                sym = "$" if cur == "USD" else "₺"
    
                toplam_meblagh = toplam_odenen = toplam_kalan = 0.0
                odendi_cnt = bekleyen_cnt = 0
                for c in cekler:
                    t = cek_tutarlari(c)          # tablo ve arşivle AYNI kural
                    toplam_meblagh += t["meblag"]
                    toplam_odenen += t["odenen"]
                    toplam_kalan += t["kalan"]
                    if t["odendi"]:
                        odendi_cnt += 1
                    else:
                        bekleyen_cnt += 1
    
                metrik_satiri([
                    {"label": "Toplam Meblağ", "value": f"{sym}{fmt(toplam_meblagh)}", "renk": trenk("mavi"), "alt": f"{len(cekler)} çek (tümü)"},
                    {"label": "Toplam Ödenen", "value": f"{sym}{fmt(toplam_odenen)}", "renk": trenk("yesil"), "alt": f"{odendi_cnt} adet ödendi"},
                    {"label": "Toplam Kalan", "value": f"{sym}{fmt(toplam_kalan)}", "renk": trenk("amber"), "alt": f"{bekleyen_cnt} bekleyen/ciro"},
                ])
    
            def cek_tablo(cekler, cur):
                if not cekler:
                    st.info(f"{cur} çeki bulunamadı.")
                    return
                sym = "$" if cur == "USD" else "₺"
    
                cek_ozet_kart(cekler, cur)
    
                rows = []
                for c in cekler:
                    vd = vade_durumu(c.get("vade"))
                    _t = cek_tutarlari(c)
                    rows.append({
                        "Ref No":       c.get("ref_no") or c.get("ref", ""),
                        "Çek No":       c.get("cek_no", ""),
                        "Tarih":        fmt_tarih(c.get("tarih")),
                        "Vade Tarihi":  fmt_tarih(c.get("vade")),
                        f"Meblağ ({sym})": c.get("meblagh", 0),
                        f"Ödenen ({sym})": _t["odenen"],
                        f"Kalan ({sym})":  _t["kalan"],
                        "_odendi":      _t["odendi"],
                        "Son Pozisyon": c.get("durum", "Bekliyor"),
                        "C/H Kodu":     c.get("ch_kodu", ""),
                        "C/H İsmi":     c.get("ch_ismi", ""),
                        "Banka":        c.get("banka", ""),
                        "Şube":         c.get("sube", ""),
                        "Hesap No":     c.get("hesap_no", ""),
                        "_vd": vd,
                    })
                # --- Firma Çekleri tablosu: ortak tablo_html (Aşama 4b) ---
                def _durum_rozet(pozisyon, ham):
                    if pozisyon == "odendi":
                        return rozet_html("✓ ÖDENDİ", "yesil")
                    if "bekliyor" in pozisyon:
                        return rozet_html("⏳ BEKLİYOR", "amber")
                    if "gecmis" in pozisyon:
                        return rozet_html("⚠ GECİKMİŞ", "kirmizi")
                    return rozet_html(ham or "—", "soluk")

                def _vurgu(row):
                    """Gecikmiş → kırmızı · bugün vadeli → sarı · ödenmiş → yeşil.
                    (vade_durumu() sonucu; eskiden bugünün tarih METNİYLE karşılaştırılıyordu,
                    'gecmis' < '2026-…' hep yanlış → gecikmiş çek hiç kırmızı olmuyordu.)"""
                    if row["_odendi"]:
                        return "yesil"
                    if row["_kalan"] > 0 and row["_vd"] == "gecmis":
                        return "kirmizi"
                    if row["_kalan"] > 0 and row["_vd"] == "bugun":
                        return "amber"
                    return None

                satirlar = []
                for row in rows:
                    pozisyon = cek_durum_norm(row.get("Son Pozisyon", ""))   # 'Ödendi' → 'odendi'
                    kalan_v = row.get(f"Kalan ({sym})", 0) or 0
                    satirlar.append({
                        "Ref No": renkli(row.get("Ref No", ""), "mavi", kalin=True),
                        # Firma ve banka eskiden hazırlanıp tabloya KONMUYORDU:
                        # "Firma Çekleri" sayfasında çekin kime verildiği görünmüyordu.
                        "Firma": row.get("C/H İsmi", "") or "—",
                        "Banka": row.get("Banka", "") or "—",
                        "Çek No": row.get("Çek No", ""),
                        "Tarih": row.get("Tarih", ""),
                        "Vade": row.get("Vade Tarihi", ""),
                        "Meblağ": row.get(f"Meblağ ({sym})", 0) or None,
                        "Ödenen": row.get(f"Ödenen ({sym})", 0) or None,
                        "Kalan": renkli(_tpara(kalan_v, sym, 2), "kirmizi" if kalan_v > 0 else "yesil", kalin=True) if kalan_v else None,
                        "Durum": _durum_rozet(pozisyon, row.get("Son Pozisyon", "")),
                        "_odendi": bool(row.get("_odendi")), "_kalan": kalan_v, "_vd": row.get("_vd", ""),
                    })
                st.html(tablo_html(
                    ["Ref No", "Firma", "Banka", ("Çek No", "mono"), ("Vade", "mono"),
                     ("Meblağ", "para", sym), ("Ödenen", "para", sym), ("Kalan", "para", sym),
                     ("Durum", "metin", "$", "orta")],
                    satirlar, vurgu=_vurgu))
    
            tab1, tab2 = st.tabs([":material/payments: TL çekleri", ":material/attach_money: USD çekleri"])
            with tab1:
                cek_tablo(get_cekler("TL"), "TL")
            with tab2:
                cek_tablo(get_cekler("USD"), "USD")
    
    
        # ════════════════════════════════════════════════════════════════════
        # 6) ÖDENENLEr
        # ════════════════════════════════════════════════════════════════════
        elif sayfa == "🕐 Ödenenler & Geçmiş":
            # Ekim 2026: kayranacc/gecmis_ekran.py — sekme yerine görünüm seçici
            # (eskiden ödenen yoksa st.stop() diğer sekmeleri de boş bırakıyordu);
            # hafta ve çek silme ONAYLI (eskiden tek tıkla, hafta tüm ödemeleriyle gidiyordu).
            from .gecmis_ekran import render_gecmis
            render_gecmis()


        # ════════════════════════════════════════════════════════════════════
        # 7b) GELENLER GEÇMİŞİ — para girişleri (tahsilatlar)
        # ════════════════════════════════════════════════════════════════════
        elif sayfa == "💵 Gelenler Geçmişi":
            # Ekim 2026: aya göre gruplu liste, her giriş KENDİ para birimiyle
            # (eskiden TL tahsilatlar "$" ile görünüyordu); onaylı geri alma.
            from .gelen_ekran import render_gelenler
            render_gelenler()


        # ════════════════════════════════════════════════════════════════════
        # 7c) e-DEFTER — GİB uyumluluk standartlarına göre (şimdilik PASİF)
        # ════════════════════════════════════════════════════════════════════
        elif sayfa == "📚 e-Defter":
            st.markdown(_sb("📚 Muhasebe", "e-Defter",
                            aciklama="Faz 1: hesap planı · muhasebe fişi · yevmiye · kebir · mizan"),
                        unsafe_allow_html=True)
            from kayranacc.edefter import render as _edefter_render
            _edefter_render()


        # ════════════════════════════════════════════════════════════════════
        # 9) RAPORLAR
        # ════════════════════════════════════════════════════════════════════
        elif sayfa == "📄 Raporlar & Bildirim":
            st.markdown(_sb("📄 Muhasebe", "Raporlar & Bildirim", aciklama="Excel ve PDF formatında haftalık raporlar"), unsafe_allow_html=True)
            _tab_rapor, _tab_bildirim = st.tabs(["📄 Raporlar", "🔔 Bildirim Ayarları"])
            with _tab_rapor:
    
                kur      = get_kur()
                odemeler, hafta = get_aktif_odemeler()
                bankalar = get_bankalar()
    
                if not odemeler:
                    st.info("Rapor oluşturmak için önce veri yükleyin.")
                    st.stop()
    
                hafta_adi = hafta["hafta_adi"] if hafta else "Haftalık Rapor"
    
                st.markdown(f"**Aktif hafta:** `{hafta_adi}` — {len(odemeler)} ödeme")
                st.markdown("---")
    
                # ── TAB: Excel / HTML ──
                tab1, tab2, tab3 = st.tabs(["📊 Tam Excel Raporu", "🖨️ PDF / Yazdır", "💸 Nakit Akış Excel"])
    
                with tab1:
                    st.markdown("**Özet + Günlük Detay + Kategori Analizi** üç sayfalı Excel dosyası.")
                    st.markdown("")
    
                    tl_top = sum(o.get("tutar_tl")  or 0 for o in odemeler)
                    usd_top = sum(o.get("tutar_usd") or 0 for o in odemeler)
                    odendi = sum(1 for o in odemeler if o.get("durum") == "odendi")
                    metrik_satiri([
                        {"label": "Toplam TL", "value": f"₺{fmt(tl_top)}", "renk": trenk("mor")},
                        {"label": "Toplam USD", "value": f"${fmt(usd_top)}", "renk": trenk("yesil")},
                        {"label": "Ödendi", "value": f"{odendi}/{len(odemeler)}", "renk": trenk("amber")},
                    ])
    
                    st.markdown("")
                    try:
                        excel_buf = haftalik_excel_raporu(odemeler, hafta_adi, bankalar, kur)
                        st.download_button(
                            label="📥 Excel Raporu İndir",
                            data=excel_buf,
                            file_name=f"MuhasebeFin_{hafta_adi.replace(' ','_')}_{tr_today()}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Excel oluşturulamadı: {e}")
    
                with tab2:
                    st.markdown("Tarayıcınızda açılır — **Ctrl+P / Cmd+P** ile yazdırabilir ya da PDF olarak kaydedebilirsiniz.")
                    st.markdown("")
    
                    try:
                        html_bytes = haftalik_html_raporu(odemeler, hafta_adi, bankalar, kur)
                        st.download_button(
                            label="🖨️ HTML Rapor İndir (Yazdır/PDF)",
                            data=html_bytes,
                            file_name=f"MuhasebeFin_{hafta_adi.replace(' ','_')}_{tr_today()}.html",
                            mime="text/html",
                            type="primary",
                            use_container_width=True,
                        )
                        st.markdown("")
                        st.markdown(
                            '<div class="info-box"><b>Nasıl PDF yapılır?</b><br>HTML dosyasını indirip tarayıcıda açın - Ctrl+P (veya Cmd+P) - "Hedef" olarak <b>PDF Olarak Kaydet</b> secin - Kaydet.</div>',
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        st.error(f"HTML rapor oluşturulamadı: {e}")
    
                    # Önizleme
                    @st.dialog("👁️ Rapor Önizleme", width="large")
                    def _dlg_rapor_onizleme():
                        try:
                            preview = haftalik_html_raporu(odemeler, hafta_adi, bankalar, kur)
                            st.components.v1.html(preview.decode("utf-8"), height=500, scrolling=True)
                        except Exception as e:
                            st.warning(f"Önizleme yüklenemedi: {e}")
                    if st.button("Rapor Önizleme", key="btn_acc_rapor_on", use_container_width=True, icon=":material/visibility:"):
                        _dlg_rapor_onizleme()
    
                with tab3:
                    st.markdown("Nakit akış tablosunu Excel dosyası olarak indirin.")
                    st.markdown("")
                    try:
                        nakit_buf = nakit_akis_excel(odemeler, bankalar, hafta_adi, kur)
                        st.download_button(
                            label="📥 Nakit Akış Excel İndir",
                            data=nakit_buf,
                            file_name=f"MuhasebeFin_NakitAkis_{tr_today()}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Nakit akış raporu oluşturulamadı: {e}")
    
    
            # ════════════════════════════════════════════════════════════════════
            # 10) BİLDİRİM AYARLARI
            # ════════════════════════════════════════════════════════════════════
            with _tab_bildirim:
                st.markdown(_sb("🔔", "Bildirim Ayarları", aciklama="Vade yaklaşan ödemeler için email bildirimleri"), unsafe_allow_html=True)
    
                ayarlar  = get_bildirim_ayarlari()
                odemeler, hafta = get_aktif_odemeler()
                bankalar = get_bankalar()
    
                # Secrets konfigürasyonu
                @st.dialog("⚙️ SMTP Ayarları (Streamlit Secrets)", width="large")
                def _dlg_smtp_ayar():
                    st.markdown(
                        "Email bildirimleri icin Streamlit Cloud > Settings > Secrets bolumune ekleyin:\n\n"
                        "```toml\n[bildirim]\nsmtp_host = \"smtp.gmail.com\"\nsmtp_port = 587\n"
                        "smtp_user = \"sizin@gmail.com\"\nsmtp_pass = \"uygulama-sifresi\"\n"
                        "alici_email = \"alici@firma.com\"\naktif = true\n```"
                    )
                    st.markdown(
                        '<div class="info-box">Gmail Uygulama Sifresi: Google Hesabim > Guvenlik > 2 Adimli Dogrulama > Uygulama Sifreleri > Yeni olustur > Posta secin > Kopyalayin.</div>',
                        unsafe_allow_html=True
                    )
                if st.button("SMTP Ayarları (Streamlit Secrets)", key="btn_acc_smtp", use_container_width=True, icon=":material/settings:"):
                    _dlg_smtp_ayar()
    
                # Mevcut ayar durumu
                st.markdown("---")
    
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Mevcut Konfigürasyon**")
                    if ayarlar.get("smtp_user"):
                        st.markdown(f'<div class="ok-box">SMTP: {ayarlar["smtp_host"]}:{ayarlar["smtp_port"]}<br>Kullanıcı: {mask_email(ayarlar["smtp_user"])}<br>Alıcı: {mask_email(ayarlar["alici_email"])}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="uyari-box">SMTP ayarları henüz yapılandırılmamış.<br>Secrets bölümünden ekleyin.</div>', unsafe_allow_html=True)
    
                with col2:
                    st.markdown("**Bağlantı Testi**")
                    if ayarlar.get("smtp_user"):
                        if st.button("Bağlantıyı Test Et", use_container_width=True, icon=":material/power:"):
                            with st.spinner("Test ediliyor..."):
                                basarili, mesaj = baglanti_test(ayarlar)
                            if basarili:
                                st.success(mesaj)
                            else:
                                st.error(mesaj)
                    else:
                        st.info("Önce SMTP ayarlarını yapılandırın.")
    
                st.markdown("---")
                st.markdown("### 📨 Manuel Bildirim Gönder")
    
                if not ayarlar.get("smtp_user"):
                    st.warning("Email göndermek için önce SMTP ayarlarını yapılandırın.")
                elif not odemeler:
                    st.info("Göndermek için önce veri yükleyin.")
                else:
                    hafta_adi = hafta["hafta_adi"] if hafta else "Bu Hafta"
    
                    tab1, tab2 = st.tabs(["⚠️ Vade Uyarısı", "📊 Haftalık Özet"])
    
                    with tab1:
                        konu, html_icerik = vade_bildirimi_olustur(odemeler, hafta_adi)
                        if not konu:
                            st.markdown('<div class="ok-box">Bugün ve yarın vadeli bekleyen ödeme yok. Bildirim gönderilecek bir durum yok.</div>', unsafe_allow_html=True)
                        else:
                            bugun_cnt  = sum(1 for o in odemeler if o.get("durum") != "odendi" and (o.get("vade") or "")[:10] == tr_today_iso())
                            yarin_cnt  = sum(1 for o in odemeler if o.get("durum") != "odendi" and (o.get("vade") or "")[:10] == (tr_today() + timedelta(days=1)).isoformat())
                            gecmis_cnt = sum(1 for o in odemeler if o.get("durum") != "odendi" and (o.get("vade") or "")[:10] < tr_today_iso() and (o.get("vade") or "")[:10])
    
                            if gecmis_cnt:
                                st.markdown(f'<div class="alarm-box">{gecmis_cnt} gecikmiş ödeme!</div>', unsafe_allow_html=True)
                            if bugun_cnt:
                                st.markdown(f'<div class="uyari-box">Bugün vadeli: {bugun_cnt} ödeme</div>', unsafe_allow_html=True)
                            if yarin_cnt:
                                st.markdown(f'<div class="info-box">Yarın vadeli: {yarin_cnt} ödeme</div>', unsafe_allow_html=True)
    
                            st.markdown(f"**Konu:** `{konu}`")
                            st.markdown(f"**Alıcı:** `{mask_email(ayarlar['alici_email'])}`")
    
                            @st.dialog("👁️ Email Önizleme", width="large")
                            def _dlg_email_on_vade():
                                st.components.v1.html(html_icerik, height=400, scrolling=True)
                            if st.button("Email Önizleme", key="btn_acc_eml_vade", use_container_width=True, icon=":material/visibility:"):
                                _dlg_email_on_vade()
    
                            if st.button("Vade Uyarısı Gönder", type="primary", use_container_width=True, icon=":material/send:"):
                                with st.spinner("Gönderiliyor..."):
                                    basarili, mesaj = email_gonder(konu, html_icerik, ayarlar)
                                if basarili:
                                    st.success(mesaj)
                                else:
                                    st.error(mesaj)
    
                    with tab2:
                        konu_ozet, html_ozet = ozet_bildirimi_olustur(odemeler, bankalar, hafta_adi)
                        st.markdown(f"**Konu:** `{konu_ozet}`")
                        st.markdown(f"**Alıcı:** `{mask_email(ayarlar['alici_email'])}`")
    
                        @st.dialog("👁️ Email Önizleme", width="large")
                        def _dlg_email_on_hafta():
                            st.components.v1.html(html_ozet, height=400, scrolling=True)
                        if st.button("Email Önizleme", key="btn_acc_eml_hft", use_container_width=True, icon=":material/visibility:"):
                            _dlg_email_on_hafta()
    
                        if st.button("Haftalık Özet Gönder", type="primary", use_container_width=True, icon=":material/send:"):
                            with st.spinner("Gönderiliyor..."):
                                basarili, mesaj = email_gonder(konu_ozet, html_ozet, ayarlar)
                            if basarili:
                                st.success(mesaj)
                            else:
                                st.error(mesaj)
    
    
            # ════════════════════════════════════════════════════════════════════
            # 11) BANKALAR ARASI VİRMAN
            # ════════════════════════════════════════════════════════════════════
        elif sayfa == "⏳ Ertelenen Ödemeler":
            # Ekim 2026: KALICI kayıttan okunur (eskiden yalnız tarayıcı oturumu).
            from .odeme_ekran import render_ertelenenler
            render_ertelenenler(KATEGORILER)

        elif sayfa == "🧾 Cari Ekstre":
            st.markdown(_sb("🧾 Muhasebe", "Cari Ekstre", aciklama="Firma bazında ödeme ekstresi ve vade yaşlandırma"),
                        unsafe_allow_html=True)
            from kayranacc.cari_ekstre import render as _cari_ekstre_render
            _cari_ekstre_render()

        elif sayfa == "💰 Toplam Aktifler":
            st.markdown(_sb("💰 Muhasebe", "Toplam Aktifler", aciklama="Stok + Yoldaki Mal + Banka + Alacaklar − Borçlar − Çekler (USD)"), unsafe_allow_html=True)
            # ─── Yetki kontrolü: Sadece yetkili kullanıcılar erişebilir ───
            aktif_kul = st.session_state.get("aktif_kullanici", "").lower().strip()
            YETKILI_TOPLAM_AKTIFLER = _toplam_aktifler_yetkilileri()
            if aktif_kul not in YETKILI_TOPLAM_AKTIFLER:
                st.error("🔒 Bu sayfaya erişim yetkiniz yok.")
                st.stop()
    
    
            kur = get_kur()
    
            # ─── Yardımcı: Excel parse fonksiyonları ───
            # ─── Session state init + Supabase'den önceki kayıtları yükle ───
            # NOT: Toplam Aktifler verileri paylaşımlıdır — yetki verilen tüm kullanıcılar (ibrahim, cem) aynı veriyi görür.
            # Bu yüzden kayıtlar sabit "ortak" anahtarıyla saklanır.
            aktif_kul = "ortak"  # Paylaşımlı veri anahtarı
    
            # Paylaşımlı veri HER render'da DB'den okunur — böylece başka bir kullanıcı
            # (pamuk vb.) yüklediğinde diğer oturumlar da anında en güncel veriyi görür.
            # (Tek seferlik session cache KULLANILMAZ; aksi halde başkasının yüklemesi yansımaz.)
            if True:
                # İlk açılış — Supabase'den önceki kayıtları çek (tablo yoksa None döner, sorun değil)
                # MIGRATION: "ortak" boşsa "ibrahim"den oku ve "ortak"a kopyala (eski veriler için)
                try:
                    stok_v = aktif_excel_oku(aktif_kul, "stok")
                    if stok_v is None:
                        # Eski "ibrahim" kayıtlarını ara
                        eski = aktif_excel_oku("ibrahim", "stok")
                        if eski is not None:
                            aktif_excel_kaydet(aktif_kul, "stok", eski)
                            stok_v = eski
                    st.session_state.aktif_stok_data = stok_v
                except Exception:
                    st.session_state.aktif_stok_data = None
                try:
                    ith_v = aktif_excel_oku(aktif_kul, "ithalat")
                    if ith_v is None:
                        eski = aktif_excel_oku("ibrahim", "ithalat")
                        if eski is not None:
                            aktif_excel_kaydet(aktif_kul, "ithalat", eski)
                            ith_v = eski
                    st.session_state.aktif_ithalat_data = ith_v
                except Exception:
                    st.session_state.aktif_ithalat_data = None
                try:
                    cari_v = aktif_excel_oku(aktif_kul, "cari")
                    if cari_v is None:
                        eski = aktif_excel_oku("ibrahim", "cari")
                        if eski is not None:
                            aktif_excel_kaydet(aktif_kul, "cari", eski)
                            cari_v = eski
                    st.session_state.aktif_cari_data = cari_v
                except Exception:
                    st.session_state.aktif_cari_data = None
    
                # JSON list olarak gelirse tuple'a çevir (parser tuple bekler)
                try:
                    if isinstance(st.session_state.aktif_stok_data, list) and len(st.session_state.aktif_stok_data) == 2:
                        usd_stok_v, pazar_dict = st.session_state.aktif_stok_data
                        if not isinstance(pazar_dict, dict):
                            pazar_dict = {}
                        st.session_state.aktif_stok_data = (float(usd_stok_v or 0), pazar_dict)
                except Exception:
                    st.session_state.aktif_stok_data = None
                try:
                    if isinstance(st.session_state.aktif_cari_data, list) and len(st.session_state.aktif_cari_data) == 3:
                        st.session_state.aktif_cari_data = tuple(float(x or 0) for x in st.session_state.aktif_cari_data)
                except Exception:
                    st.session_state.aktif_cari_data = None
                st.session_state.aktif_excel_yuklendi = True
    
            # ─── Excel yükleme bölümü — kompakt: durum kartları + pencereden yükleme ───
    
            col1, col2, col3 = st.columns(3)
    
            # Meta bilgileri al
            stok_meta = None
            ithalat_meta = None
            cari_meta = None
            try:
                stok_meta = aktif_excel_meta_oku("stok")
                ithalat_meta = aktif_excel_meta_oku("ithalat")
                cari_meta = aktif_excel_meta_oku("cari")
            except Exception:
                pass
    
            def _meta_str(meta):
                """Meta bilgiyi kısa string'e çevir."""
                if not meta:
                    return ""
                kim = (meta.get("son_yukleyen") or "?").capitalize()
                zaman = (meta.get("yukleme_zamani") or "")[:16]
                return f"👤 {kim} · 🕐 {zaman}"
    
            with col1:
                st.markdown("**1 · Stok Değeri Raporu**")
                if st.session_state.aktif_stok_data:
                    try:
                        usd_v, pzr = st.session_state.aktif_stok_data
                        # Kartta AKTİFLERE GİREN değer gösterilir (KDV dahil = ham × 1.20);
                        # ham değer alt satırda kalır ki iki rakam da doğrulanabilsin.
                        _ham_v = float(usd_v or 0)
                        metrik_satiri([{"label": "✅ Yüklendi (KDV dahil)",
                                        "value": f"${tr_sayi(_ham_v * 1.20)}",
                                        "renk": trenk("yesil"),
                                        "alt": f"ham ${tr_sayi(_ham_v)} × 1.20 · {_meta_str(stok_meta)}"}])
                    except Exception:
                        st.session_state.aktif_stok_data = None
    
            with col2:
                st.markdown("**2 · İthalat Ödeme Takip**")
                if st.session_state.aktif_ithalat_data:
                    try:
                        metrik_satiri([{"label": "✅ Yüklendi", "value": f"${tr_sayi(float(st.session_state.aktif_ithalat_data))}",
                                        "renk": trenk("yesil"), "alt": _meta_str(ithalat_meta)}])
                    except Exception:
                        st.session_state.aktif_ithalat_data = None
    
            with col3:
                st.markdown("**3 · Cari Alacaklar Listesi**")
                if st.session_state.aktif_cari_data:
                    try:
                        cari = st.session_state.aktif_cari_data
                        if isinstance(cari, dict) and "borc" in cari:
                            _b = cari.get("borc", {}) or {}
                            _a = cari.get("alacak", {}) or {}

                            def _usd_kar(d):
                                return (float(d.get("usd") or 0)
                                        + (float(d.get("tl") or 0) / kur if kur > 0 else 0)
                                        + float(d.get("eur") or 0) * 1.10)
                            b_tot = _usd_kar(_b)
                            a_tot = _usd_kar(_a)
                            metrik_satiri([
                                {"label": "Borç", "value": f"${tr_sayi(b_tot)}", "renk": trenk("kirmizi"), "anlam": "notr",
                                 "alt": f"USD {tr_sayi(float(_b.get('usd') or 0))} · TL {tr_sayi(float(_b.get('tl') or 0))} · EUR {tr_sayi(float(_b.get('eur') or 0))}"},
                                {"label": "Alacak", "value": f"${tr_sayi(a_tot)}", "renk": trenk("yesil"),
                                 "alt": f"USD {tr_sayi(float(_a.get('usd') or 0))} · TL {tr_sayi(float(_a.get('tl') or 0))} · EUR {tr_sayi(float(_a.get('eur') or 0))}"},
                            ])
                        elif isinstance(cari, (tuple, list)) and len(cari) == 3:
                            metrik_satiri([{"label": "✅ Yüklendi (eski format)", "value": f"${tr_sayi(float(cari[0]))}",
                                            "renk": trenk("yesil"), "alt": "USD borç"}])
                        else:
                            st.session_state.aktif_cari_data = None
                        if cari_meta:
                            st.caption(_meta_str(cari_meta))
                    except Exception:
                        st.session_state.aktif_cari_data = None
    

            st.caption("Stok değeri raporu, ithalat ödeme takip ve cari alacaklar listesi üst menüdeki "
                       "**Dosya** düğmesinden yüklenir; kartlar kayıttan hemen sonra güncellenir.")

            st.markdown("---")
    
            # ─── Hesaplama ───
            bankalar = get_bankalar()
            banka_tl = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "TL")
            banka_usd = sum(float(b["bakiye"]) for b in bankalar if b["para_birimi"] == "USD")
            banka_usd_eqv = banka_usd + (banka_tl / kur if kur > 0 else 0)
    
            # Stok kalemleri
            usd_stok, pazaryerleri = 0.0, {}
            try:
                if st.session_state.aktif_stok_data:
                    data = st.session_state.aktif_stok_data
                    if isinstance(data, (tuple, list)) and len(data) == 2:
                        usd_stok = float(data[0] or 0)
                        pazaryerleri = data[1] if isinstance(data[1], dict) else {}
            except Exception:
                usd_stok, pazaryerleri = 0.0, {}
    
            # %20 KDV dahil stok (formül: değer × 1.20)
            stok_marjli = usd_stok * 1.20 if usd_stok else 0
    
            # İthalat
            try:
                odenen_ithalat = float(st.session_state.aktif_ithalat_data or 0)
            except (TypeError, ValueError):
                odenen_ithalat = 0.0
    
            # Cari Borçlar ve Alacaklar
            usd_borc = tl_borc = eur_borc = 0.0
            usd_alacak = tl_alacak = eur_alacak = 0.0
            try:
                if st.session_state.aktif_cari_data:
                    cari = st.session_state.aktif_cari_data
                    # Yeni format: dict{'borc': {...}, 'alacak': {...}}
                    if isinstance(cari, dict) and "borc" in cari:
                        b = cari.get("borc") or {}
                        a = cari.get("alacak") or {}
                        usd_borc = float(b.get("usd") or 0)
                        tl_borc = float(b.get("tl") or 0)
                        eur_borc = float(b.get("eur") or 0)
                        usd_alacak = float(a.get("usd") or 0)
                        tl_alacak = float(a.get("tl") or 0)
                        eur_alacak = float(a.get("eur") or 0)
                    # Eski format: tuple/list (sadece borçlar) - geriye dönük uyumluluk
                    elif isinstance(cari, (tuple, list)) and len(cari) == 3:
                        usd_borc = float(cari[0] or 0)
                        tl_borc = float(cari[1] or 0)
                        eur_borc = float(cari[2] or 0)
            except Exception:
                usd_borc = tl_borc = eur_borc = 0.0
                usd_alacak = tl_alacak = eur_alacak = 0.0
    
            tl_borc_usd = tl_borc / kur if kur > 0 else 0
            eur_borc_usd = eur_borc * 1.10 if eur_borc > 0 else 0
            tl_alacak_usd = tl_alacak / kur if kur > 0 else 0
            eur_alacak_usd = eur_alacak * 1.10 if eur_alacak > 0 else 0
            toplam_alacak_usd = usd_alacak + tl_alacak_usd + eur_alacak_usd
    
            # ─── Çekler (Sistemden) ───
            cek_tl, cek_usd, cek_adet_tl, cek_adet_usd = get_cek_toplamlari()
            cek_tl_usd_eqv = cek_tl / kur if kur > 0 else 0
            cek_toplam_usd = cek_tl_usd_eqv + cek_usd
    
            # ─── Manuel Kalemler (Supabase + session_state fallback) ───
            # Önce Supabase'den dene, başarısızsa session_state kullan
            if "manuel_kalemler_local" not in st.session_state:
                st.session_state.manuel_kalemler_local = []
    
            manuel_kalemler_db = []
            try:
                manuel_kalemler_db = aktif_manuel_listele(aktif_kul) or []
                # MIGRATION: "ortak"ta yoksa "ibrahim"den çek ve kopyala
                if not manuel_kalemler_db:
                    eski_kalemler = aktif_manuel_listele("ibrahim") or []
                    for kalem in eski_kalemler:
                        try:
                            aktif_manuel_ekle(
                                aktif_kul,
                                kalem.get("aciklama", ""),
                                float(kalem.get("tutar") or 0),
                                kalem.get("para_birimi") or "USD",
                                kalem.get("tip") or "ekle"
                            )
                        except Exception:
                            pass
                    # Migration sonrası tekrar oku
                    if eski_kalemler:
                        manuel_kalemler_db = aktif_manuel_listele(aktif_kul) or []
            except Exception:
                manuel_kalemler_db = []
    
            # Eğer Supabase'den veri geldiyse onu kullan, yoksa session'dan
            if manuel_kalemler_db:
                manuel_kalemler = manuel_kalemler_db
            else:
                manuel_kalemler = st.session_state.manuel_kalemler_local
    
            manuel_ekle_toplam = 0.0
            manuel_cikar_toplam = 0.0
            for k in manuel_kalemler:
                try:
                    tutar = float(k.get("tutar") or 0)
                    pb = (k.get("para_birimi") or "USD").upper()
                    tutar_usd = tutar if pb == "USD" else (tutar / kur if kur > 0 else 0)
                    if k.get("tip") == "ekle":
                        manuel_ekle_toplam += tutar_usd
                    else:
                        manuel_cikar_toplam += tutar_usd
                except (TypeError, ValueError):
                    pass
    
            # ─── HAVUZ BÜTÇE KALDIRILDI (27.07.2026) ───
            # Kayıt türü kullanımdan çıkarıldı; aktiflere artık girmiyor.
            havuz_butce_usd = 0.0

            # TOPLAM AKTİFLER
            toplam_aktif = (
                stok_marjli
                + odenen_ithalat
                + banka_usd_eqv
                + toplam_alacak_usd
                + manuel_ekle_toplam
                + havuz_butce_usd
                - usd_borc
                - tl_borc_usd
                - eur_borc_usd
                - cek_toplam_usd
                - manuel_cikar_toplam
            )
    
            # ─── Sonuç kaydı (gösterim Yönetim panosunda) ───
            # NOT: Toplam aktif sonucu burada GÖSTERİLMEZ; sadece kaydedilir ve
            # yalnızca Yönetim Panosu (P&L) navigasyonunda görüntülenir.
            _snap_ok = False
            _snap_hata = ""
            # DÜZELTME (Ekim 2026): eskiden sayfa HER açılışta sonucu Yönetim
            # Panosu'na yazıyordu — Excel'ler eksikken de (eksikler 0 sayılıyordu).
            # Dosyasız açmak, panodaki toplam aktifi eksik değerle eziyor ve yine
            # "✅ işlendi ve kaydedildi" diyordu. Artık: dosya eksikse YAZILMAZ
            # (eski doğru kayıt korunur); tamsa yalnız rakam değiştiyse yazılır.
            _snap_eksik = [ad for ad, v in (("Stok Değeri Raporu", st.session_state.get("aktif_stok_data")),
                                            ("İthalat Ödeme Takip", st.session_state.get("aktif_ithalat_data")),
                                            ("Cari Alacaklar Listesi", st.session_state.get("aktif_cari_data")))
                           if not v]
            _snap_eski = get_ayar("toplam_aktif_snapshot", {}) or {}
            _snap_ayni = (round(float(_snap_eski.get("toplam") or 0), 2) == round(toplam_aktif, 2)
                          and str(_snap_eski.get("tarih")) == str(__import__("datetime").date.today()))
            try:
                import datetime as _dt_acc
                if _snap_eksik:
                    raise RuntimeError("eksik dosya: " + ", ".join(_snap_eksik))
                _snap_ok = True if _snap_ayni else set_ayar("toplam_aktif_snapshot", {
                    "toplam": round(toplam_aktif, 2),
                    "kur": kur,
                    "tarih": str(_dt_acc.date.today()),
                    "stok": round(stok_marjli, 2),
                    "ithalat": round(odenen_ithalat, 2),
                    "banka": round(banka_usd_eqv, 2),
                    "alacak": round(toplam_alacak_usd, 2),
                    "borc": round(usd_borc + tl_borc_usd + eur_borc_usd, 2),
                    "cek": round(cek_toplam_usd, 2),
                    "manuel_ekle": round(manuel_ekle_toplam, 2),
                    "manuel_cikar": round(manuel_cikar_toplam, 2),
                    "havuz": round(havuz_butce_usd, 2),
                })
            except Exception as _e:
                _snap_ok = False
                _snap_hata = str(_e)[:200]
            if _snap_eksik:
                _tarih_eski = _snap_eski.get("tarih")
                from shared.tasarim import mesaj as _mesaj_kutu
                from shared.utils import gun_ay_yil as _gay
                st.markdown(_mesaj_kutu("uyari", "Eksik dosya var (" + ", ".join(_snap_eksik) + "): aşağıdaki toplam eksik "
                                  "hesaplandı ve Yönetim Panosu'na KAYDEDİLMEDİ. "
                                  + (f"Panoda {_gay(_tarih_eski)} tarihli son tam hesap duruyor."
                                     if _tarih_eski else "Panoda henüz kayıtlı toplam yok.")),
                            unsafe_allow_html=True)
            if _snap_ok or _snap_eksik:
                if _snap_ok:
                    st.success("Veriler işlendi; Yönetim Panosu güncel.")
                # ── 💎 Genel toplam BURADA da göster (Yönetim Panosu'na gitmeye gerek yok) ──
                from shared.tasarim import kpi_serit as _ks_ta
                st.markdown(_ks_ta([
                    {"etiket": "Toplam aktifler" + (" (eksik hesap)" if _snap_eksik else ""),
                     "deger": f"${tr_sayi(toplam_aktif)}", "renk": "amber" if _snap_eksik else "mor",
                     "alt": f"≈ ₺{tr_sayi(toplam_aktif * kur)} · kur {tr_sayi(kur, 4)}"},
                ]), unsafe_allow_html=True)
                # Kısa hesap dökümü
                _dk = [
                    ("📦 Stok (×1.20)", stok_marjli, "+"), ("🚢 İthalat (ödenen)", odenen_ithalat, "+"),
                    ("🏦 Banka (USD)", banka_usd_eqv, "+"), ("📥 Cari alacak", toplam_alacak_usd, "+"),
                    ("➕ Manuel ekleme", manuel_ekle_toplam, "+"),
                    ("📤 Cari borç", usd_borc + tl_borc_usd + eur_borc_usd, "−"),
                    ("🧾 Çekler", cek_toplam_usd, "−"), ("➖ Manuel çıkarma", manuel_cikar_toplam, "−"),
                ]
                _chips = "".join(
                    f'<span style="display:inline-flex;gap:4px;align-items:center;background:color-mix(in srgb,var(--k-metin) 4%,transparent);'
                    f'border:1px solid color-mix(in srgb,var(--k-soluk) 18%,transparent);border-radius:8px;padding:4px 8px;font-size:13px;margin:4px 4px 4px 0">'
                    f'<span style="color:{trenk("yesil") if y=="+" else trenk("kirmizi")}">{y}</span>'
                    f'<span style="color:var(--k-soluk)">{k}</span>'
                    f'<b style="color:var(--k-metin);font-family:monospace">${tr_sayi(float(v or 0))}</b></span>'
                    for k, v, y in _dk if float(v or 0))
                st.markdown(f'<div style="display:flex;flex-wrap:wrap;margin-bottom:8px">{_chips}</div>',
                            unsafe_allow_html=True)
            else:
                _h = st.session_state.get("_son_ayar_hata", "") or _snap_hata
                st.error("⚠️ Veriler işlendi ama sonuç **kaydedilemedi** — bu yüzden Yönetim Panosu'na yansımıyor. "
                         "Genellikle `sistem_ayarlari` tablosu eksik/yanlış olduğunda olur.")
                if _h:
                    st.code(_h, language="text")
                    st.caption("Bu hata mesajını yöneticine ilet — kesin çözüm için bu lazım.")

            # ─── Manuel Ekleme/Çıkarma ───
            st.markdown("---")
            st.markdown("#### Manuel ekleme / çıkarma")
            st.caption("Excel'lerde olmayan ek kalemler için manuel giriş yap. Kayıtlar kalıcıdır.")
    
            @st.dialog("➕ Yeni Kalem Ekle", width="large")
            def _dlg_yeni_kalem():
                col_t, col_a, col_tu, col_pb, col_b = st.columns([1, 3, 1.5, 1, 1])
                with col_t:
                    yeni_tip = st.selectbox("Tip", ["ekle", "cikar"],
                                             format_func=lambda x: "➕ Ekle" if x == "ekle" else "➖ Çıkar",
                                             key="manuel_tip")
                with col_a:
                    yeni_aciklama = st.text_input("Açıklama", key="manuel_aciklama",
                                                   placeholder="Örn: Kasa nakit, Yatırım fonu, Henüz fatura kesilmemiş alacak")
                with col_tu:
                    yeni_tutar = st.number_input("Tutar", min_value=0.0, step=0.0001, format="%.4f", key="manuel_tutar")
                with col_pb:
                    yeni_pb = st.selectbox("PB", ["USD", "TL"], key="manuel_pb")
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Ekle", type="primary", use_container_width=True, key="manuel_kaydet", icon=":material/save:"):
                        if not yeni_aciklama.strip():
                            st.error("Açıklama boş olamaz")
                        elif yeni_tutar <= 0:
                            st.error("Tutar 0'dan büyük olmalı")
                        else:
                            # Önce Supabase'e kaydetmeyi dene
                            supabase_basarili = False
                            try:
                                supabase_basarili = aktif_manuel_ekle(aktif_kul, yeni_aciklama.strip(), yeni_tutar, yeni_pb, yeni_tip)
                            except Exception:
                                supabase_basarili = False
    
                            # Supabase başarısızsa session_state'e ekle (fallback)
                            if not supabase_basarili:
                                import time as _time
                                st.session_state.manuel_kalemler_local.append({
                                    "id": f"local_{int(_time.time() * 1000)}",
                                    "kullanici": aktif_kul,
                                    "aciklama": yeni_aciklama.strip(),
                                    "tutar": float(yeni_tutar),
                                    "para_birimi": yeni_pb,
                                    "tip": yeni_tip,
                                    "olusturuldu": str(tr_today()),
                                })
                                st.warning("⚠️ Supabase'e kaydedilemedi (tablo yok), oturum belleğine kaydedildi.")
                            else:
                                st.success("✅ Kalem eklendi (kalıcı)")
                            st.rerun()
            if st.button("Yeni Kalem Ekle", key="btn_acc_kalem", use_container_width=True, icon=":material/add:"):
                _dlg_yeni_kalem()

            # ─── Kayıtlı bir kalemi REVİZE et ───
            # Kalem silinip yeniden eklenmez; id ve oluşturma tarihi korunur.
            @st.dialog("✏️ Kalemi Düzenle", width="large")
            def _dlg_kalem_duzenle(_k):
                _kid = _k["id"]
                _yerel = isinstance(_kid, str) and str(_kid).startswith("local_")
                st.caption(f"Oluşturulma: {(_k.get('olusturuldu') or '')[:10]}"
                           + ("  ·  ⚠️ oturum belleğinde (kalıcı değil)" if _yerel else ""))
                d1, d2, d3 = st.columns([1, 3, 1])
                with d1:
                    _d_tip = st.selectbox(
                        "Tip", ["ekle", "cikar"],
                        index=0 if (_k.get("tip", "ekle") == "ekle") else 1,
                        format_func=lambda x: "➕ Ekle" if x == "ekle" else "➖ Çıkar",
                        key=f"duz_tip_{_kid}")
                with d2:
                    _d_ack = st.text_input("Açıklama", value=_k.get("aciklama", "") or "",
                                           key=f"duz_ack_{_kid}")
                with d3:
                    _d_pb = st.selectbox(
                        "PB", ["USD", "TL"],
                        index=0 if (_k.get("para_birimi", "USD") or "USD").upper() == "USD" else 1,
                        key=f"duz_pb_{_kid}")
                _d_tutar = st.number_input("Tutar", min_value=0.0, step=0.0001, format="%.4f",
                                           value=float(_k.get("tutar") or 0),
                                           key=f"duz_tutar_{_kid}")

                _eski = float(_k.get("tutar") or 0)
                if abs(_d_tutar - _eski) > 0.0001:
                    _fark = _d_tutar - _eski
                    st.info(f"Tutar {tr_sayi(_eski, 2)} → **{tr_sayi(_d_tutar, 2)}**  "
                            f"({'+' if _fark > 0 else ''}{tr_sayi(_fark, 2)})")

                b1, b2 = st.columns([1, 1])
                if b1.button("Değişiklikleri Kaydet", type="primary",
                             use_container_width=True, key=f"duz_kaydet_{_kid}", icon=":material/save:"):
                    if not (_d_ack or "").strip():
                        st.error("Açıklama boş olamaz.")
                    elif _d_tutar <= 0:
                        st.error("Tutar 0'dan büyük olmalı.")
                    else:
                        if _yerel:
                            for _kk in st.session_state.manuel_kalemler_local:
                                if _kk.get("id") == _kid:
                                    _kk.update({"aciklama": _d_ack.strip(),
                                                "tutar": float(_d_tutar),
                                                "para_birimi": _d_pb, "tip": _d_tip})
                            st.session_state["_manuel_mesaj"] = "✅ Kalem güncellendi (oturum belleği)."
                        else:
                            _ok = False
                            try:
                                _ok = aktif_manuel_guncelle(_kid, _d_ack.strip(), _d_tutar,
                                                            _d_pb, _d_tip)
                            except Exception:
                                _ok = False
                            st.session_state["_manuel_mesaj"] = (
                                "✅ Kalem güncellendi." if _ok
                                else "⚠️ Güncellenemedi — kayıt değişmedi.")
                        st.session_state.pop("_manuel_duzenle_id", None)
                        st.rerun()
                if b2.button("Vazgeç", use_container_width=True, key=f"duz_vazgec_{_kid}"):
                    st.session_state.pop("_manuel_duzenle_id", None)
                    st.rerun()

            _mmsg = st.session_state.pop("_manuel_mesaj", None)
            if _mmsg:
                (st.success if _mmsg.startswith("✅") else st.warning)(_mmsg)

            # Düzenleme isteği varsa ilgili kalemi bul ve diyaloğu aç
            _duz_id = st.session_state.pop("_manuel_duzenle_id", None)
            if _duz_id is not None:
                _hedef_k = next((x for x in (manuel_kalemler or [])
                                 if str(x.get("id")) == str(_duz_id)), None)
                if _hedef_k:
                    _dlg_kalem_duzenle(_hedef_k)
    
            # Mevcut kalemleri listele
            if manuel_kalemler:
                st.markdown(f"**Kayıtlı Kalemler ({len(manuel_kalemler)})**")
                for k in manuel_kalemler:
                    tip = k.get("tip", "ekle")
                    renk = trenk("yesil") if tip == "ekle" else trenk("kirmizi")
                    isaret = "+" if tip == "ekle" else "-"
                    sembol = "$" if (k.get("para_birimi") or "USD").upper() == "USD" else "₺"
                    tutar_v = float(k.get("tutar") or 0)
                    col_a, col_b, col_c = st.columns([10, 1, 1])
                    with col_a:
                        st.markdown(
                            f'<div style="background:var(--k-yuzey2);border:1px solid color-mix(in srgb,var(--k-metin) 12%,transparent);border-left:3px solid {renk};border-radius:8px;padding:8px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">'
                            f'<div><b style="color:var(--k-metin);font-size:13px">{k.get("aciklama","")}</b><div style="font-size:11px;color:var(--k-soluk)">{(k.get("olusturuldu") or "")[:10]}</div></div>'
                            f'<div style="color:{renk};font-weight:700;font-family:monospace;font-size:14px">{isaret}{sembol}{tr_sayi(tutar_v, 2)}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    with col_b:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("", key=f"manuel_duzenle_{k['id']}",
                                     help="Tutarı / açıklamayı revize et", icon=":material/edit:"):
                            st.session_state["_manuel_duzenle_id"] = k["id"]
                            st.rerun()
                    with col_c:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("", key=f"manuel_sil_{k['id']}", help="Sil", icon=":material/delete:"):
                            kalem_id = k['id']
                            # Local kalem ise (id "local_" ile başlar) session'dan sil
                            if isinstance(kalem_id, str) and kalem_id.startswith("local_"):
                                st.session_state.manuel_kalemler_local = [
                                    kk for kk in st.session_state.manuel_kalemler_local
                                    if kk.get("id") != kalem_id
                                ]
                            else:
                                try:
                                    aktif_manuel_sil(kalem_id)
                                except Exception:
                                    pass
                            st.rerun()
    
            # ─── Eksik dosya uyarıları ───
            st.markdown("---")
            eksikler = []
            if not st.session_state.aktif_stok_data:
                eksikler.append("📦 Stok Değeri Raporu yüklenmedi")
            if not st.session_state.aktif_ithalat_data:
                eksikler.append("🚢 İthalat Ödeme Takip yüklenmedi")
            if not st.session_state.aktif_cari_data:
                eksikler.append("⚠️ Cari Alacaklar Listesi yüklenmedi")
            # Eksik dosyalar artık sonucun hemen üstünde (Yönetim Panosu'na yazılmadığı
            # bilgisiyle birlikte) gösteriliyor; burada ikinci kez yazılmıyor.
    
            # ─── Temizleme ───
            @st.dialog("🗑️ Yüklenen verileri temizle", width="large")
            def _dlg_veri_temizle():
                st.warning("⚠️ Bu işlem **kalıcı kayıtları da siler**. Yeniden Excel yüklemeniz gerekir.")
                if st.button("Tüm Excel verilerini sıfırla", type="secondary"):
                    st.session_state.aktif_stok_data = None
                    st.session_state.aktif_ithalat_data = None
                    st.session_state.aktif_cari_data = None
                    aktif_excel_sil(aktif_kul)  # Supabase'ten de sil
                    st.success("Temizlendi.")
                    st.rerun()
            if st.button("Yüklenen verileri temizle", key="btn_acc_temizle", use_container_width=True, icon=":material/delete:"):
                _dlg_veri_temizle()
    
            # ─── Formül açıklaması ───
            with st.popover("📐 Hesaplama Formülü"):
                st.markdown(f"""
                **Toplam Aktifler (USD) =**
    
                - **G5F Stok Değeri × 1.20** — Stok Excel'inden USD STOK DEĞERİ toplamı (%20 KDV dahil)
                - **+ İthalat Ödenmiş Tutar** — İthalat Excel "Ödenen / USD" toplamı
                - **+ Banka Hesapları USD eşdeğeri** — Uygulamadaki TL hesapları kur ile USD'ye çevrilir
                - **+ Cari Alacaklar** — Cari Excel'inden POZİTİF bakiyeler (size borçlular)
                - **+ Manuel Eklemeler** — Kullanıcının elle eklediği kalemler
                - **− Cari Borçlar** — Cari Excel'inden NEGATİF bakiyeler (sizin borçlu olduklarınız)
                - **− Sistemdeki Çekler** — Uygulamadaki bekleyen + ciro çek kalanları
                - **− Manuel Çıkarmalar** — Kullanıcının elle çıkardığı kalemler
    
                Kullanılan kur: **{kur} TL/USD** (sidebar'daki güncel kur — sidebar'da değiştirirsen burası da değişir)
                """)

    _sayfa_parcasi()

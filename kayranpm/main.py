"""
KAYRAN — Ürün & Stok Yönetim Sistemi
Modüler olarak KAYRAN portal içinden çağrılır.

Kullanım:
    from kayranpm.main import run
    run()
"""
from shared.tasarim import renk as trenk  # aktif temanın rengi (hex)
from shared.tasarim import df_tablo_html
from kayranpm.stok_ara import stok_karti_ara
from shared.tasarim import tr_sayi  # TR sayı biçimi (1.234,56)
import streamlit as st
import logging
_log = logging.getLogger(__name__)
# Türkiye saat dilimi için ortak yardımcılar
from shared.utils import tr_now
from shared.utils import metrik_satiri
from shared.tasarim import baslik as _sb
import pandas as pd
from functools import partial
from shared import bilesen as B
from .urun_hesap import yukleme_ozeti
from shared.utils import firma_gorunen_ad   # kanal = cari adı (Faz 4)

# Modül bazlı importlar (relative)
from .database import (initialize_db, get_tum_sku_listesi, get_client,
                      sku_fazeon_temizle_onizle, sku_fazeon_temizle_uygula)
from .analitik import dashboard_hesapla, tum_urunler_listesi
from .excel_islemler import excel_yukle_g5f_depolar, excel_yukle_haftalik_stok_satis


_RK_RENK = {"rk-grn": "yesil", "rk-red": "kirmizi", "rk-yel": "amber", "rk-org": "amber", "rk-dim": None}


def render_renkli_tablo(df, para=None, yuzde=None, kar=None, sol=None,
                        kisalt=None, gizle=None, satir_durum=None):
    """DataFrame'i ORTAK tabloda çizer (Aşama 4b — shared.tasarim.df_tablo_html).
    satir_durum: (kolon, {değer: "rk-grn"/"rk-red"/"rk-yel"}) eski adlar da kabul edilir
    → satır zemini yeşil/kırmızı/sarı vurgulanır."""
    vurgu = None
    if satir_durum:
        kol, harita = satir_durum
        vurgu = (kol, {k: _RK_RENK.get(v, v) for k, v in harita.items()})
    st.html(df_tablo_html(df, para=para, yuzde=yuzde, kar=kar, sol=sol, kisa=kisalt,
                          gizle=gizle, satir_vurgu=vurgu))


# ══════════════════ DOSYA KAPISI GÖVDELERİ (Ekim 2026) ══════════════════
# Haftalık müşteri stok + satış (eskiden Müşteri Satışları'ndaki pencere) ve G5F depo sayımı
# (eskiden Veri Yükleme sayfası) artık üst menüdeki Dosya kapısında (shared/dosya_kapisi).
# İkisi de eskiden önizlemesiz yazıyordu; artık önce salt okunur özet, sonra Kaydet.
def kapi_musteri_haftalik(dosya, kapi):
    from shared.yukleme_takvimi import serit as _yt_serit
    _yt_serit("musteri_haftalik")        # haftalık müşteri dosyası: geri sayım şeridi
    st.caption("Firma başına iki sekme: `ITOPYA STOK` · `ITOPYA SATIŞ` · `VATAN STOK` · `VATAN SATIŞ` … "
               "Her firmanın kendi portal başlıkları olduğu gibi kalır (STOKKODU/Kod/Sku/Malzeme/Ürün Kodu…). "
               "Satışlar SKU ile stokun yanına bağlanır; kategori dosyada gerekmez, ürün kartından eşlenir.")
    ok, oz = excel_yukle_haftalik_stok_satis(dosya, dosya_adi=dosya.name, onizle=True)
    if not ok:
        st.error(oz)
        return
    _dd = "/".join(str(oz["rapor_tarihi"])[:10].split("-")[::-1])
    st.success(f"Rapor haftası **{_dd}** · {len(oz['firmalar'])} firma")
    st.dataframe(pd.DataFrame([{"Firma": firma_gorunen_ad(k), "SKU": v["sku"], "Stok": v["stok"], "Satış": v["satis"],
                                "Bu haftada kayıtlı satır": v["mevcut"] if v["mevcut"] is not None else "?"}
                               for k, v in oz["firmalar"].items()]), hide_index=True, use_container_width=True)
    if any(v["mevcut"] for v in oz["firmalar"].values()):
        st.info("Bu hafta için kayıtlı satırı olan firmalarda eski satırlar dosyadakilerle değiştirilir "
                "(aynı haftanın dosyası tekrar yüklenince şişmesin). Yükleme geçmişinden geri alınabilir.")
    if oz.get("atlanan"):
        st.warning("Atlanacak sekmeler: " + ", ".join(oz["atlanan"]))
    if st.button("Haftalık stok + satışı kaydet", type="primary", use_container_width=True,
                 key=kapi.anahtar("mhs_hss_btn"), disabled=not oz["firmalar"], icon=":material/upload:"):
        dosya.seek(0)
        with st.spinner("İçe aktarılıyor…"):
            _ok2, _msg2 = excel_yukle_haftalik_stok_satis(dosya, dosya_adi=dosya.name)
        st.cache_data.clear()          # geri sayım da tazelenir (önbellekli)
        if _ok2:
            kapi.bitti(_msg2.replace("✅ ", ""), uyari="⚠️" in _msg2)
        else:
            st.error(_msg2)


def kapi_g5f(dosya, kapi):
    from shared.yukleme_takvimi import serit as _yt_serit
    _yt_serit("g5f_sayim")
    st.caption("Bizim depo stoğu — tek sayfa, her satır bir depo-ürün: Depo adı · Stok kodu · Stok ismi · Miktar. "
               "Genel toplam ve depo kırılımı tüm depolardan; \"bizim stok\" = Merkez depo + Happy Life. "
               "Fiyat / kategori / marka bilgisine dokunmaz.")
    st.warning("**Bu yükleme SAYIM / DÜZELTMEDİR:** ithalat teslimi, satış ve iadeler depo stoğunu zaten "
               "otomatik günceller. Bu dosya canlı stoğu Excel'deki değerlere **eşitler** (üzerine yazar); "
               "yalnız fiziksel sayımdan sonra ya da düzeltme için yükle.")
    ok, oz = excel_yukle_g5f_depolar(dosya, onizle=True)
    if not ok:
        st.error(oz)
        return
    st.success(f"{oz['urun']} ürün · {oz['eslesen']} mevcut güncellenecek, {oz['yeni']} yeni · "
               f"{len(oz['depolar'])} depo ({', '.join(oz['depolar'])}) · toplam {tr_sayi(oz['toplam_adet'])} adet")
    if oz["sifirlanacak"]:
        with st.expander(f"Excel'de olmayan {len(oz['sifirlanacak'])} ürünün depo stoğu SIFIRLANACAK", expanded=True):
            st.caption(", ".join(oz["sifirlanacak"][:300]))
    if st.button("G5F sayımını kaydet", type="primary", use_container_width=True,
                 key=kapi.anahtar("g5f_depo_btn"), icon=":material/upload:"):
        dosya.seek(0)
        from shared.yukleme_gecmisi import Kayit as _YKayit
        _yk_g5f = _YKayit("g5f_sayim", dosya.name)
        _yk_g5f.anahtar("g5f")   # sonraki sayım öncekini geçersiz kılar (sayım mutlak değer yazar)
        _oz = {}
        with st.spinner("G5F depo kırılımlı stok işleniyor — ürünler senkronlanıyor…"), \
                _yk_g5f.stok():          # stok hareketleri bu yüklemeyle işaretlenir
            basari_g, mesaj_g = excel_yukle_g5f_depolar(dosya, ozet=_oz)
        st.cache_data.clear()
        if basari_g or _oz.get("guncellenen"):
            # Yarıda kalsa da güncellenenler kayda geçer → Yükleme geçmişinden geri alınabilir
            _yk_g5f.kaydet(_oz.get("guncellenen", 0))
        if basari_g:
            from shared.yukleme_takvimi import kaydet as _yt_kaydet
            _yt_kaydet("g5f_sayim", st.session_state.get("aktif_kullanici", ""))
            kapi.bitti(mesaj_g.replace("✅ ", ""))
        else:
            st.error(mesaj_g)


def run():
    """KAYRAN ana çalıştırıcı. Portal tarafından çağrılır."""
    initialize_db()

    # İthalat'taki tüm modeller Ürün Yönetimi'ne otomatik yansısın (oturumda bir kez · ekleme-only, silme yok)
    if not st.session_state.get("_ith_autosync"):
        try:
            from .database import ithalat_eksikleri_ekle
            _yeni = ithalat_eksikleri_ekle()
            if _yeni:
                st.toast(f"🚢 İthalat'tan {_yeni} model ürünlere eklendi")
        except Exception:
            pass
        st.session_state["_ith_autosync"] = True

    st.markdown("""
    <style>
    /* ── GLOBAL ─────────────────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: var(--k-yuzey0) !important;
    }

    /* ── METRIC KARTLARI (modern · sade · profesyonel) ───────────────── */
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, color-mix(in srgb,var(--k-metin) 4%,transparent), color-mix(in srgb,var(--k-metin) 2%,transparent));
        border: 1px solid color-mix(in srgb,var(--k-metin) 7%,transparent);
        border-radius: 16px;
        padding: 16px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.22);
        transition: border-color .15s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: color-mix(in srgb,var(--k-mor) 32%,transparent);
    }
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p,
    div[data-testid="stMetricLabel"] div {
        color: var(--k-soluk) !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        letter-spacing: .2px !important;
    }
    div[data-testid="stMetricValue"] {
        color: var(--k-mavi) !important;
        font-size:23px !important;
        font-weight: 700 !important;
        font-variant-numeric: tabular-nums;
        line-height: 1.22 !important;
        margin-top: 3px;
        white-space: normal !important;
        word-break: break-word;
    }
    div[data-testid="stMetricDelta"] { font-size:13px !important; }

    /* ── ALERT BOX'LARI (warning/error/info/success) ─────────────────── */
    /* Streamlit'in default renkleri dark tema'da okunmuyor. Manuel override. */
    div[data-testid="stAlert"] {
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        font-weight:400 !important;
        padding: 0 !important;
        border: 1px solid transparent !important;
        box-shadow: none !important;
    }
    div[data-testid^="stAlertContent"] {
        background: transparent !important;
        border: none !important;
        padding: 11px 15px !important;
        color: var(--k-metin) !important;
    }
    div.stAlert:has([data-testid="stAlertContentWarning"]) {
        background: color-mix(in srgb,var(--k-amber) 7%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-amber) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-amber) 60%,transparent) !important;
    }
    div.stAlert:has([data-testid="stAlertContentError"]) {
        background: color-mix(in srgb,var(--k-kirmizi) 7%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-kirmizi) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-kirmizi) 60%,transparent) !important;
    }
    div.stAlert:has([data-testid="stAlertContentInfo"]) {
        background: color-mix(in srgb,var(--k-mavi) 6%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-mavi) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-mavi) 55%,transparent) !important;
    }
    div.stAlert:has([data-testid="stAlertContentSuccess"]) {
        background: color-mix(in srgb,var(--k-yesil) 6%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-yesil) 20%,transparent) !important;
        border-left: 3px solid color-mix(in srgb,var(--k-yesil) 50%,transparent) !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] div {
        color: var(--k-metin) !important;
    }
    div[data-testid="stAlert"] strong,
    div[data-testid="stAlert"] b {
        font-weight: 700 !important;
    }
    
    /* ── METRIC KARTLARI (özet barlar) ── eski 'metric-container' + yeni 'stMetric' */
    [data-testid="metric-container"],
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, color-mix(in srgb,var(--k-metin) 7%,transparent) 0%, color-mix(in srgb,var(--k-metin) 3%,transparent) 100%);
        border-radius: 14px;
        padding: 16px 16px;
        border: 1px solid color-mix(in srgb,var(--k-metin) 10%,transparent);
        transition: border-color 0.2s;
        min-width: 0;
        overflow: hidden;
    }
    [data-testid="metric-container"]:hover,
    [data-testid="stMetric"]:hover { border-color: rgba(66,165,245,0.4); }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] * {
        color: var(--k-silik) !important; font-size:11px !important; font-weight:700 !important;
        letter-spacing:0.2px;
        white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
    }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        color: var(--k-metin) !important; font-weight:700 !important; font-size:23px !important;
        white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important;
        line-height:1.15 !important;
    }
    [data-testid="stMetricDelta"] { font-size:13px !important; }
    
    /* ── BAŞLIK STİLLERİ ─────────────────────────────────────────────────── */
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
    .sayfa-baslik-cizgi {
        height: 3px;
        background: linear-gradient(90deg, var(--k-mavi), var(--k-mavi), transparent);
        border-radius: 2px;
        margin-bottom: 24px;
    }
    
    /* ── ETİKET KUTUCUKLARI ──────────────────────────────────────────────── */
    .tag-kirmizi { background:color-mix(in srgb,var(--k-kirmizi) 25%,transparent); color:var(--k-kirmizi); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-turuncu { background:color-mix(in srgb,var(--k-amber) 30%,transparent); color:var(--k-amber); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-sari    { background:var(--k-amber); color:var(--k-amber2); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-yesil   { background:color-mix(in srgb,var(--k-yesil) 25%,transparent); color:var(--k-yesil2); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-mavi    { background:color-mix(in srgb,var(--k-mavi) 30%,transparent); color:var(--k-mavi); padding:4px 8px; border-radius:20px; font-size:11px; font-weight:700; }
    .tag-gri     { background:color-mix(in srgb,var(--k-soluk) 20%,transparent); color:var(--k-soluk); padding:4px 8px; border-radius:20px; font-size:11px; }
    
    /* ── BİLGİ KUTULARI ─────────────────────────────────────────────────── */
    .uyari-box {
        background: color-mix(in srgb,var(--k-amber) 10%,var(--k-yuzey1));
        border-left: 3px solid var(--k-amber);
        color: var(--k-amber);
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
    }
    .info-box {
        background: color-mix(in srgb,var(--k-mavi) 10%,var(--k-yuzey1));
        border-left: 3px solid var(--k-mavi);
        color: var(--k-mavi);
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
    }
    .basari-box {
        background: color-mix(in srgb,var(--k-yesil) 10%,var(--k-yuzey1));
        border-left: 3px solid var(--k-yesil2);
        color: var(--k-yesil2);
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
        font-weight:400;
    }
    
    /* ── SIDEBAR ─────────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--k-yuzey0) 0%, var(--k-yuzey1) 100%) !important;
        border-right: 1px solid color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
    }
    section[data-testid="stSidebar"] * { color: var(--k-metin) !important; }
    /* ── Stok Kartı kutusu — her Ürün Yönetimi sayfasının sağ üstünde (Ekim 2026; eskiden
       sol kenar çubuğundaydı). Arama kutusu hep görünür; sonuçlar kutunun altında AÇILIR
       LİSTE olarak sayfanın üstünde durur (sayfayı aşağı itmez): kutuya odaklanınca ya da
       yazı varken görünür. */
    html body .st-key-pm_arac { margin: -6px 0 2px !important; }
    html body .st-key-stok_karti_kutu {
        position: relative !important; max-width: 100% !important; gap: 0 !important; overflow: visible !important;
    }
    html body .st-key-sk_sonuc {
        display: none !important; position: absolute !important; top: calc(100% + 4px) !important; left: 0; right: 0;
        z-index: 60 !important; background: var(--k-yuzey1) !important; border: 1px solid var(--k-kenar2) !important;
        border-radius: 12px !important; padding: 8px !important; gap: 2px !important;
        box-shadow: 0 14px 36px rgba(0,0,0,.38) !important; max-height: 60vh; overflow-y: auto !important;
    }
    html body .st-key-stok_karti_kutu:focus-within .st-key-sk_sonuc,
    html body .st-key-stok_karti_kutu:has(input:not(:placeholder-shown)) .st-key-sk_sonuc { display: flex !important; }
    /* Streamlit metnin altına -1rem koyar (paragraf boşluğunu telafi için); genel
       kural paragraf boşluğunu sıfırladığından başlık 16px "kısalıyor", arama kutusu
       başlığın ÜSTÜNE biniyordu. Bu kutudaki yazı blokları için sıfırla. */
    html body .st-key-stok_karti_kutu [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] {
        margin-bottom: 0 !important;
    }
    /* Sonuç satırındaki ipucu (tam ürün adı) kabı: genel kural ona zemin+çerçeve
       veriyordu → her satır ayrı kutu gibi görünüyordu. Şeffaf, tam genişlik. */
    html body .st-key-stok_karti_kutu [data-testid="stTooltipIcon"],
    html body .st-key-stok_karti_kutu [data-testid="stTooltipHoverTarget"] {
        background: transparent !important; border: 0 !important; padding: 0 !important;
        border-radius: 0 !important; box-shadow: none !important; display: block !important; width: 100% !important;
    }
    html body .st-key-stok_karti_kutu .sk-bas {
        display: flex; align-items: baseline; justify-content: space-between; padding: 0 2px 8px;
        line-height: 1.3 !important;
    }
    html body .st-key-stok_karti_kutu .sk-bas-ad {
        font-size: 13px !important; font-weight: 650 !important; color: var(--k-metin) !important;
    }
    html body .st-key-stok_karti_kutu .sk-bas-say,
    html body .st-key-stok_karti_kutu .sk-alt {
        font-size: 11px !important; color: var(--k-silik) !important; font-weight: 500 !important;
    }
    html body .st-key-stok_karti_kutu .sk-alt {
        padding: 10px 2px 4px; letter-spacing: .2px; font-size: 11px !important;
        font-weight: 600 !important; line-height: 1.2 !important;
    }
    html body .st-key-stok_karti_kutu .sk-not {
        font-size: 11.5px !important; line-height: 1.5 !important; color: var(--k-silik) !important; padding: 8px 2px 0;
    }
    html body .st-key-stok_karti_kutu .sk-not b { color: var(--k-soluk) !important; }
    /* Arama kutusu */
    /* Çerçeve DIŞ katmanda (ikon + yazı aynı kutuda); iç alan şeffaf */
    html body .st-key-stok_karti_kutu [data-testid="stTextInputRootElement"] {
        background: var(--k-yuzey0) !important; border: 1px solid var(--k-kenar2) !important;
        border-radius: 9px !important; min-height: 38px !important; padding-left: 10px !important;
        align-items: center !important; gap: 6px !important;
    }
    html body .st-key-stok_karti_kutu [data-testid="stTextInputRootElement"]:focus-within {
        border-color: var(--k-mor) !important; box-shadow: 0 0 0 3px color-mix(in srgb,var(--k-mor) 18%,transparent) !important;
    }
    html body .st-key-stok_karti_kutu input {
        font-size: 13px !important; background: transparent !important; border: 0 !important;
        box-shadow: none !important; padding-left: 0 !important;
    }
    html body .st-key-stok_karti_kutu [data-testid="stTextInputIcon"] [data-testid="stIconMaterial"] {
        color: var(--k-silik) !important; font-size: 18px !important;
    }
    /* Sonuç satırları: liste görünümü (düğme değil) — SKU mono+mor, ad tek satır '…' */
    html body .st-key-stok_karti_kutu .stButton { margin: 0 !important; }
    html body .st-key-stok_karti_kutu [data-testid="stElementContainer"]:has([data-testid="stTextInput"]) {
        margin-bottom: 4px !important;
    }
    /* İki satırlı liste: üstte SKU (mono, mor), altta ürün adı (tek satır '…') */
    html body .st-key-stok_karti_kutu .stButton button {
        justify-content: flex-start !important; text-align: left !important; min-height: 0 !important;
        height: auto !important; padding: 5px 8px !important; border: 0 !important; border-radius: 7px !important;
        background: transparent !important; box-shadow: none !important; gap: 6px !important;
    }
    html body .st-key-stok_karti_kutu .stButton button:hover {
        background: var(--k-ortu2) !important;
    }
    html body .st-key-stok_karti_kutu .stButton button > div,
    html body .st-key-stok_karti_kutu .stButton button [data-testid="stMarkdownContainer"] {
        min-width: 0 !important; overflow: hidden !important; width: 100% !important; justify-content: flex-start !important;
    }
    html body .st-key-stok_karti_kutu .stButton button p {
        font-size: 12px !important; font-weight: 400 !important; color: var(--k-soluk) !important;
        white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
        text-align: left !important; margin: 0 !important;
    }
    html body .st-key-stok_karti_kutu .stButton button code {
        display: block !important; font-family: var(--k-mono) !important; font-size: 12px !important;
        font-weight: 600 !important; line-height: 1.35 !important; color: var(--k-mor) !important;
        background: transparent !important; padding: 0 !important; border: 0 !important;
    }
    html body .st-key-stok_karti_kutu .stButton button p { line-height: 1.4 !important; }
    html body .st-key-stok_karti_kutu .stButton button [data-testid="stIconMaterial"] {
        color: var(--k-silik) !important; font-size: 15px !important;
    }

    /* Sidebar nav stili shared/utils.py → sidebar_stil() tarafından yönetilir */
    section[data-testid="stSidebar"] .stButton button {
        background: var(--k-yuzey2) !important;
        color: var(--k-metin) !important;
        border: 1px solid var(--k-kenar2) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
        margin: 12px 0 !important;
    }

    /* Sol menü aç/kapat düğmesi: app.py'deki ortak düğme (tema renkli, sade).
       Burada eskiden parlak mavi kare + gölge veriliyordu; yalnız bu modülde
       sol üstte mavi bir kutu çıkıyordu. */

    /* ── BUTONLAR ────────────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg,var(--k-mavi),var(--k-mavi)) !important;
        border: none !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(21,101,192,0.3) !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(21,101,192,0.5) !important;
        transform: translateY(-1px) !important;
    }
    
    /* ── FORM ALANLARI ───────────────────────────────────────────────────── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background: color-mix(in srgb,var(--k-metin) 5%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 12%,transparent) !important;
        border-radius: 8px !important;
        color: var(--k-metin) !important;
        font-size: 13px !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--k-mavi) !important;
        box-shadow: 0 0 0 2px rgba(66,165,245,0.15) !important;
    }
    label[data-testid="stWidgetLabel"] p {
        color: var(--k-silik) !important;
        font-size:13px !important;
        font-weight: 600 !important;
        letter-spacing: 0.3px !important;
    }
    
    /* ── EXPANDER ────────────────────────────────────────────────────────── */
    .streamlit-expanderHeader {
        background: color-mix(in srgb,var(--k-metin) 4%,transparent) !important;
        border-radius: 10px !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
        color: var(--k-mavi) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    .streamlit-expanderContent {
        background: color-mix(in srgb,var(--k-metin) 2%,transparent) !important;
        border: 1px solid color-mix(in srgb,var(--k-metin) 6%,transparent) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
    }
    
    /* ── TABS ────────────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: color-mix(in srgb,var(--k-metin) 3%,transparent) !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 2px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        color: var(--k-silik) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        padding: 6px 16px !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(21,101,192,0.4) !important;
        color: var(--k-mavi) !important;
    }
    
    /* ── DATAFRAME ───────────────────────────────────────────────────────── */
    .stDataFrame { border-radius: 10px !important; overflow: hidden !important; }
    .stDataFrame [data-testid="stDataFrameResizable"] {
        border: 1px solid color-mix(in srgb,var(--k-metin) 8%,transparent) !important;
        border-radius: 10px !important;
    }
    
    /* ── DIVIDER ─────────────────────────────────────────────────────────── */
    hr { border-color: color-mix(in srgb,var(--k-metin) 6%,transparent) !important; margin: 20px 0 !important; }
    
    /* ── TABLO HÜCRE RENKLERİ ────────────────────────────────────────────── */
    .hucre-acil    { background:color-mix(in srgb,var(--k-kirmizi) 25%,transparent) !important; color:var(--k-kirmizi) !important; font-weight:700; }
    .hucre-turuncu { background:color-mix(in srgb,var(--k-amber) 30%,transparent) !important; color:var(--k-amber) !important; font-weight:600; }
    .hucre-sari    { background:color-mix(in srgb,var(--k-amber) 35%,transparent) !important; color:var(--k-amber) !important; font-weight:600; }
    .hucre-yesil   { background:color-mix(in srgb,var(--k-yesil) 25%,transparent) !important; color:var(--k-yesil2) !important; font-weight:600; }
    .hucre-gri     { background:color-mix(in srgb,var(--k-soluk) 20%,transparent) !important; color:var(--k-metin) !important; }
    .fcp-vurgu { color:var(--k-amber2); font-weight:700; font-size:14px; }
    
    /* ── SCROLLBAR ───────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: color-mix(in srgb,var(--k-metin) 2%,transparent); }
    ::-webkit-scrollbar-thumb { background: color-mix(in srgb,var(--k-metin) 15%,transparent); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: color-mix(in srgb,var(--k-metin) 25%,transparent); }
    </style>
    """, unsafe_allow_html=True)
    
    # ── Yardımcı fonksiyonlar ────────────────────────────────────────────
    # ── Sidebar navigasyon ───────────────────────────────────────────────
    # Stok kartı kutusunun yeri: sayfanın sağ üstü (kenar çubuğu kalktı, Ekim 2026)
    _pm_arac = st.container(key="pm_arac", horizontal=True, horizontal_alignment="right")
    with st.sidebar:
        st.markdown('<script>var sidebarEl=window.parent.document.querySelector("[data-testid=stSidebar] > div");if(sidebarEl)sidebarEl.scrollTop=0;</script>', unsafe_allow_html=True)
        from shared.utils import sidebar_ust
        sidebar_ust("📦", "Ürün Yönetimi", "kayranpm")
        from shared.tasarim import menu_etiketi as _me
        from shared.gezinme import secenekler, sayfa_menusu
        sayfa = sayfa_menusu("Sayfa", secenekler("kayranpm"), modul="kayranpm", label_visibility="collapsed",
           format_func=_me, key="pm_sayfa")    # anahtar: Genel Bakış'tan sayfaya geçiş

        # ── STOK KARTI — hızlı erişim (Ürün Yön.'nin en sık kullanılan eylemi) ──
        # Eskiden başlık ayrı bir HTML kutusuydu; arama kutusu ve sonuçlar onun
        # DIŞINDA kalıyordu (kopuk görünüm). Şimdi hepsi tek kap (st.container).
        #
        # Korunan dersler (önceki iki hata — yeniden yaşanmasın):
        # 1) Selectbox YOK: kendi anahtarına yazınca ilk karakter siliniyordu.
        # 2) Bayrak dansı YOK: sonuca basmak kartı HER ZAMAN açar.
        # Yeni: Enter'da tek/tam eşleşme varsa kart doğrudan açılır — ama yalnız
        # arama METNİ DEĞİŞTİYSE (_sk_acilan): yoksa sonraki her yenilemede açılırdı.
        _skl = get_tum_sku_listesi() or []
        _hedef = st.session_state.pop("_stok_gec_sku", None)   # modal içi geçiş
        with _pm_arac, st.container(key="stok_karti_kutu", width=440):
            _ara = st.text_input(
                "Stok kartı ara", key="stok_karti_ara", icon=":material/search:",
                placeholder=f"Stok kartı · SKU, model ya da ürün adı ({tr_sayi(len(_skl))} ürün)",
                label_visibility="collapsed")
            with st.container(key="sk_sonuc"):        # açılır liste (CSS: odak / yazı varken)
                _q = (_ara or "").strip()
                if not _hedef and _q:
                    _bul = stok_karti_ara(_skl, _q)
                    if not _bul:
                        st.markdown('<div class="sk-not">Eşleşen ürün yok. SKU\'nun bir kısmını '
                                    'ya da modeli yazmayı dene.</div>', unsafe_allow_html=True)
                    else:
                        _tam = [r for r in _bul if str(r.get("sku") or "").strip().upper() == _q.upper()]
                        _tek = _tam[0] if _tam else (_bul[0] if len(_bul) == 1 else None)
                        if _tek and st.session_state.get("_sk_acilan") != _q:
                            st.session_state["_sk_acilan"] = _q           # aynı aramada bir kez
                            _hedef = _tek["sku"]
                        for _r in _bul[:6]:
                            _ad = (_r.get("urun_adi") or "").strip()
                            # help (ipucu) YOK: tıklanınca stok kartı penceresi açılıyor, Streamlit'in
                            # ipucu pencerenin üstünde takılı kalıyordu (Ekim 2026). Ad zaten düğmede.
                            if st.button(f"`{_r['sku']}` {_ad}" if _ad else f"`{_r['sku']}`",
                                         key=f"stok_ac_{_r['sku']}", use_container_width=True):
                                _hedef = _r["sku"]
                        if len(_bul) > 6:
                            st.markdown(f'<div class="sk-not">+{tr_sayi(len(_bul) - 6)} sonuç daha — '
                                        f'aramayı daralt.</div>', unsafe_allow_html=True)
                elif not _hedef:
                    _son = st.session_state.get("_sk_son", [])
                    if _son:
                        st.markdown('<div class="sk-alt">Son açılanlar</div>', unsafe_allow_html=True)
                        for _s in _son:
                            if st.button(f"`{_s}`", key=f"stok_son_{_s}", use_container_width=True,
                                         icon=":material/history:"):
                                _hedef = _s
                    else:
                        st.markdown('<div class="sk-not">Yaz ve <b>Enter</b>\'a bas — tam SKU '
                                    'yazarsan kart doğrudan açılır.</div>', unsafe_allow_html=True)

        if _hedef:
            _son = [x for x in st.session_state.get("_sk_son", []) if x != _hedef]
            st.session_state["_sk_son"] = ([_hedef] + _son)[:4]
            from kayranpm.stok_karti import goster as _stok_goster
            _stok_goster(_hedef)


        st.markdown(f"""
        <div style="text-align:center; margin-top:20px; padding-bottom:8px;">
            <div style="color:var(--k-silik); font-size:11px;">{tr_now().strftime('%d.%m.%Y  %H:%M')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # ════════════════════════════════════════════════════════════════════
    # 1) DASHBOARD
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
        if sayfa == "📊  Dashboard":
            # Ekran: kayranpm/genel_bakis.py (yeniden tasarım, Ekim 2026)
            from .genel_bakis import render as _genel_bakis
            _genel_bakis(_sb)

        elif sayfa == "📋  Tüm Ürünler":
            st.markdown(_sb("📋 Ürün Yönetimi", "Tüm Ürünler", aciklama="Ürün listesi · paçal maliyet · satış · marj · stok dağılımı · ayrıntı için satıra tıkla"), unsafe_allow_html=True)
    
            # Ürün verilerini yükle
            try:
                from shared.islem import bekle as _bekle
                with _bekle("Ürün listesi hazırlanıyor…"):
                    urun_data = tum_urunler_listesi()
            except Exception as e:
                _log.error("Hata: %s", e)
                st.error(f"Veri yüklenemedi: {e}")
                return
    
            if not urun_data:
                st.info("Henüz ürün yüklenmemiş. üst menüdeki Dosya düğmesinden G5F stok dosyasını yükleyin.")
                return
    
            # ── Liste ↔ sayfa içi detay (Ekim 2026) ──
            # Sayfa artık LİSTE: satıra tıklayınca bu ürünün detayı açılır, düzenleme
            # de aynı ürün için yapılır (eskiden iki ayrı ürün seçici vardı).
            _sec_u = B.secili("pm_urun")
            secilen = next((u for u in urun_data if u["sku"] == _sec_u), None) if _sec_u else None
            if secilen is None:
                B.birak("pm_urun")
                from .urunler_ekran import FILTRE_KEYS as _UFK
                B.geri_yukle(_UFK + ["pm_ul_limit"])     # detaydan dönüşte filtreler yerinde
                # Özet metrikler
                toplam_stok_degeri = sum(u.get("stok_degeri_fcp", 0) for u in urun_data)
                toplam_satis_degeri = sum(u.get("stok_degeri_satis", 0) for u in urun_data)
                toplam_genel_stok = sum(u.get("toplam_stok", u.get("bizim_stok", 0)) for u in urun_data)
                toplam_kanal_stok = sum(u.get("kanal_stok", 0) or 0 for u in urun_data)
    
                metrik_satiri([
                    {"label": "📦 Toplam Ürün", "value": f"{tr_sayi(len(urun_data))}", "renk": trenk("mor")},
                    {"label": "🏭 Toplam Stok", "value": f"{tr_sayi(toplam_genel_stok)} adet", "renk": trenk("cyan"),
                     "alt": (f"Merkez + Happy Life · kanallarda {tr_sayi(toplam_kanal_stok)}" if toplam_kanal_stok
                             else "Merkez + Happy Life")},
                    {"label": "💰 Depo Stok Değeri (Maliyet)", "value": f"${tr_sayi(toplam_stok_degeri)}", "renk": trenk("amber")},
                    {"label": "💵 Depo Stok Değeri (Satış)", "value": f"${tr_sayi(toplam_satis_degeri)}", "renk": trenk("yesil")},
                ])

                # 🩺 Veri sağlığı (tek satır · eksik alanlar)
                _eksik_kat = sum(1 for u in urun_data if not (u.get("kategori") or "").strip())
                _eksik_mar = sum(1 for u in urun_data if not (u.get("marka") or "").strip())
                _eksik_fiy = sum(1 for u in urun_data if not (u.get("satis_fiyati") or 0))
                _eksik_mal = sum(1 for u in urun_data if not (u.get("final_cost_price") or 0))
                _sg = []
                if _eksik_kat: _sg.append(f'<span style="color:var(--k-amber)">{_eksik_kat} kategorisiz</span>')
                if _eksik_mar: _sg.append(f'<span style="color:var(--k-amber)">{_eksik_mar} markasız</span>')
                if _eksik_fiy: _sg.append(f'<span style="color:var(--k-kirmizi)">{_eksik_fiy} satış fiyatsız</span>')
                if _eksik_mal: _sg.append(f'<span style="color:var(--k-soluk)">{_eksik_mal} İthalat maliyeti yok</span>')
                if _sg:
                    st.markdown('<div style="font-size:13px;color:var(--k-soluk);margin:8px 0 0px"><b>Veri sağlığı:</b> '
                                + '  ·  '.join(_sg)
                                + ' <span style="color:var(--k-silik)">— Toplu İşlemler’deki düzenleme araçlarından doldurabilirsin</span></div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown('<div style="font-size:13px;color:var(--k-yesil);margin:8px 0 0px"><b>Veri sağlığı:</b> ✓ tüm alanlar dolu</div>',
                                unsafe_allow_html=True)
                from .urunler_ekran import liste as _urun_liste
                _urun_liste(urun_data)
                return

            from .urunler_ekran import FILTRE_KEYS as _UFK
            from shared.tasarim import YAN_YANA as _yy
            B.koru(_UFK + ["pm_ul_limit"])
            # Liste ve detay yan yana (YAN_YANA): geniş ekranda liste solda (her şey tıklanabilir,
            # pencere yok); 900 px altında CSS listeyi gizler, eskisi gibi "Listeye dön".
            if _yy:
                from .urunler_ekran import liste as _urun_liste, YAN_YANA_CSS as _YY_CSS
                st.markdown(_YY_CSS, unsafe_allow_html=True)
                _sol, _sag = st.columns([1, 1.35], gap="medium")
                with _sol, st.container(key="pm_liste_sol"):
                    _urun_liste(urun_data, dar=True, secili=secilen["sku"])
                _sag_kap = _sag.container(key="pm_detay_sag")
            else:
                _sag_kap = st.container(key="pm_detay_sag")
            with _sag_kap:
                B.listeye_don("pm_urun")
                if _yy:
                    B.kapat("pm_urun")
                secilen_sku = secilen["sku"]
                firma_st = secilen.get("firma_stoklari", {})
    
                # ── Ürün Başlığı (modern kart) ──
                st.markdown(f"""<div style="display:flex;align-items:center;gap:16px;padding:16px 16px;margin:4px 0 16px;background:linear-gradient(135deg,color-mix(in srgb,var(--k-mor) 10%,transparent),color-mix(in srgb,var(--k-mavi) 4%,transparent));border:1px solid color-mix(in srgb,var(--k-mor) 18%,transparent);border-radius:16px;">
     <div style="width:48px;height:48px;border-radius:13px;flex-shrink:0;background:linear-gradient(135deg,var(--k-mor),var(--k-mor));display:flex;align-items:center;justify-content:center;font-size:23px;box-shadow:0 6px 18px color-mix(in srgb,var(--k-mor) 35%,transparent);">📦</div>
     <div style="min-width:0;">
     <div style="font-family:'Manrope','Inter',sans-serif;font-size:19px;font-weight:700;color:var(--k-mavi);line-height:1.3;letter-spacing:-0.3px;">{secilen["urun_adi"]}</div>
     <div style="margin-top:8px;"><span style="display:inline-block;padding:4px 12px;border-radius:7px;background:color-mix(in srgb,var(--k-mor) 15%,transparent);border:1px solid color-mix(in srgb,var(--k-mor) 25%,transparent);color:var(--k-mor2);font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;letter-spacing:0.5px;">{secilen["sku"]}</span></div>
     </div></div>""", unsafe_allow_html=True)
    
                bizim_stok = secilen.get("bizim_stok", 0)
                toplam_firma = secilen.get("toplam_firma_stok", 0)
                toplam = secilen.get("toplam_stok", bizim_stok)          # bizim satılabilir (stok_hesap)
                _zincir = secilen.get("zincir_stok", bizim_stok + toplam_firma)
    
                # Stok kartları — ortak tema (renkli sol şeritli kart)
                _stok_cards = [{"label": "G5F depo", "value": f"{tr_sayi(bizim_stok)}", "alt": "adet", "renk": trenk("mavi")}]
                for firma, adet in firma_st.items():
                    if adet > 0:
                        _stok_cards.append({"label": firma_gorunen_ad(firma), "ozel_ad": True, "value": f"{tr_sayi(adet)}", "alt": "adet · kanalda"})
                st.markdown(
                    f'<div style="display:flex; justify-content:space-between; align-items:center; margin:8px 0 8px;">'
                    f'<span style="color:var(--k-metin); font-size:14px; font-weight:700;">Stok dağılımı</span>'
                    f'<span><span style="color:var(--k-amber); font-size:19px; font-weight:700;">{tr_sayi(toplam)} adet</span>'
                    + (f'<span style="color:var(--k-silik); font-size:12px;"> · kanal dahil {tr_sayi(_zincir)}</span>'
                       if toplam_firma else '')
                    + '</span></div>',
                    unsafe_allow_html=True)
                metrik_satiri(_stok_cards)

                # G5F depo kırılımı (tüm depolar) — bizim deponun depo bazlı dağılımı + genel toplam
                # depo_dagilimi: aynı depo tek rozet (MERKEZ = MERKEZ DEPO), "3.0" gibi değer çökertmez
                from .database import depo_dagilimi as _depo_dagilimi
                _dk_satir, _dk_toplam = _depo_dagilimi(secilen.get("depo_kirilim"))
                if _dk_satir:
                    # Kayıtlı bizim_stok kırılımla tutmuyorsa fark yazılır (değer değiştirilmez)
                    from .database import satilabilir_kontrol as _sat_kontrol
                    _sk = _sat_kontrol(secilen.get("depo_kirilim"), bizim_stok)
                    _sat_fark_html = (
                        f' <span style="color:var(--k-amber);font-weight:600">· kırılıma göre {tr_sayi(_sk["hesap"])}, '
                        f'fark {"+" if _sk["fark"] > 0 else "−"}{tr_sayi(abs(_sk["fark"]))} — G5F sayımını yeniden yükle</span>'
                        if _sk["fark"] else "")
                    _chips = "".join(
                        f'<span style="display:inline-flex;gap:8px;align-items:center;background:color-mix(in srgb,var(--k-metin) 4%,transparent);'
                        f'border:1px solid color-mix(in srgb,var(--k-soluk) 20%,transparent);border-radius:8px;padding:4px 12px;font-size:13px;color:var(--k-mavi)">'
                        f'{_d} <b style="color:var(--k-mavi);font-family:monospace">{tr_sayi(_v)}</b></span>'
                        for _d, _v in _dk_satir)
                    st.markdown(
                        f'<div style="margin:0px 0 12px">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                        f'<span style="color:var(--k-metin);font-size:14px;font-weight:700">G5F depo kırılımı</span>'
                        f'<span style="color:var(--k-yesil);font-size:14px;font-weight:700;font-family:monospace">Tüm depolar: {tr_sayi(_dk_toplam)} adet</span></div>'
                        f'<div style="display:flex;flex-wrap:wrap;gap:8px">{_chips}</div>'
                        f'<div style="color:var(--k-silik);font-size:11px;margin-top:8px">Satılabilir '
                        f'(Merkez + Happy Life) = toplam stok: <b style="color:var(--k-mavi)">{tr_sayi(bizim_stok)}</b>'
                        + _sat_fark_html +
                        '</div></div>', unsafe_allow_html=True)
    
                # Fiyat ve karlılık kartı
                fob = secilen.get("fob_price") or 0
                cost = secilen.get("cost") or 0
                fcp = secilen.get("final_cost_price") or 0
                son_fob = secilen.get("son_fob") or 0
                son_fcp = secilen.get("son_final") or 0
                son_tarih = secilen.get("son_tarih") or ""
                ithalat_dosya = secilen.get("ithalat_dosya_sayisi", 0) or 0
                satis = secilen.get("satis_fiyati") or 0
                mal_y = secilen.get("mal_yuzde") or secilen.get("son_mal_yuzde") or 0
    
                if fob > 0 or fcp > 0:
                    _son_alt = f"En yeni dosya · {son_tarih}" if son_tarih else "En yeni ithalat dosyası"
                    _fiyat_cards = [
                        {"label": "Paçal FOB", "value": f"${tr_sayi(fob, 2)}", "renk": trenk("mavi"),
                         "alt": "Adet-ağırlıklı ortalama"},
                        {"label": "Son FOB", "value": f"${tr_sayi(son_fob, 2)}" if son_fob else "—", "renk": trenk("mavi"),
                         "alt": _son_alt},
                        {"label": f"Maliyet (%{tr_sayi(mal_y, 1)})", "value": f"${tr_sayi(cost, 2)}", "renk": trenk("amber")},
                        {"label": "⭐ Paçal maliyet", "value": f"${tr_sayi(fcp, 2)}", "renk": trenk("amber"),
                         "alt": "Landed · İthalat"},
                        {"label": "Son maliyet", "value": f"${tr_sayi(son_fcp, 2)}" if son_fcp else "—", "renk": trenk("amber2"),
                         "alt": _son_alt},
                    ]
                    if satis > 0:
                        _fiyat_cards.append({"label": "Satış fiyatı", "value": f"${tr_sayi(satis, 2)}", "renk": trenk("cyan")})
                        if fcp > 0:
                            _kar = satis - fcp
                            _marj = (_kar / satis * 100) if satis else 0
                            if _kar >= 0:
                                _fiyat_cards.append({"label": "Kâr", "value": f"${tr_sayi(_kar, 2)}",
                                                     "renk": trenk("yesil"), "alt": f"Marj %{tr_sayi(_marj, 1)} · paçala göre"})
                            else:
                                _fiyat_cards.append({"label": "⚠️ Zarar", "value": f"${tr_sayi(_kar, 2)}",
                                                     "renk": trenk("kirmizi"), "alt": "Satış, paçal maliyetin altında"})
                    st.markdown(
                        f'<div style="display:flex;align-items:center;justify-content:space-between;margin:8px 0 8px">'
                        f'<div style="color:var(--k-metin);font-size:14px;font-weight:700">Fiyat analizi</div>'
                        f'<div style="color:var(--k-yesil2);font-size:11px;font-weight:600;background:color-mix(in srgb,var(--k-yesil) 12%,transparent);border:1px solid color-mix(in srgb,var(--k-yesil) 25%,transparent);border-radius:6px;padding:4px 8px">İthalat · {ithalat_dosya} parti</div></div>',
                        unsafe_allow_html=True)
                    metrik_satiri(_fiyat_cards)
                else:
                    st.markdown('<div style="background:color-mix(in srgb,var(--k-soluk) 6%,transparent);border:1px dashed color-mix(in srgb,var(--k-soluk) 25%,transparent);border-radius:12px;padding:16px;text-align:center;color:var(--k-soluk);font-size:13px;margin-bottom:16px">Bu ürün için İthalat maliyet verisi yok — İthalat modülünden bu SKU ile dosya girilince maliyet/paçal otomatik gelecek.</div>', unsafe_allow_html=True)

                # EOL rozeti
                if secilen.get("eol"):
                    st.markdown(
                        '<div style="background:color-mix(in srgb,var(--k-kirmizi) 10%,transparent);border:1px solid color-mix(in srgb,var(--k-kirmizi) 35%,transparent);'
                        'border-radius:10px;padding:8px 16px;margin:4px 0 8px;color:var(--k-kirmizi);font-size:13px;font-weight:700">'
                        '⛔ EOL — Bu ürün üretimi/satışı sonlandı olarak işaretli; sipariş önerisine girmez.</div>',
                        unsafe_allow_html=True)

                # Müşteri bazlı satış fiyat listesi
                _fl = secilen.get("satis_fiyat_listesi") or {}
                if _fl:
                    st.markdown(B.grup_basligi("🏷️ Müşteri bazlı satış fiyatları"), unsafe_allow_html=True)
                    metrik_satiri([{"label": _m, "value": f"${tr_sayi(_v, 2)}", "renk": trenk("cyan")}
                                   for _m, _v in _fl.items()])

                st.markdown("---")

                # Detayli Gorunum (satis trendi - siparis - yoldaki)
                try:
                    _veri_detay = dashboard_hesapla()
                    urun = next((u for u in _veri_detay if u["sku"] == secilen_sku), secilen)
                except Exception:
                    urun = secilen
                # Üst bilgi kartları
                toplam_stok_ud = urun.get("toplam_stok", urun.get("bizim_stok", 0))
                stok_bitis = urun.get('stok_bitis_gun')
                stok_bitis_str = f"{stok_bitis} gün" if stok_bitis is not None and stok_bitis != 0 else "Veri yok"
                _risk = urun.get('risk_skor', 0) or 0
                _risk_renk = trenk("kirmizi") if _risk >= 70 else (trenk("amber") if _risk >= 40 else trenk("yesil"))
                metrik_satiri([
                    {"label": "📦 Toplam Stok", "value": f"{tr_sayi(toplam_stok_ud)}", "renk": trenk("mor")},
                    {"label": "📊 Ort. Hft. Satış", "value": f"{tr_sayi(round(urun.get('ortalama_haftalik_satis', 0)))}", "renk": trenk("cyan")},
                    {"label": "⚡ Risk Skoru", "value": f"{_risk}/100", "renk": _risk_renk},
                    {"label": "📅 Stok Biter", "value": stok_bitis_str, "renk": trenk("mor"), "alt": "kanal dahil stokla"},
                    {"label": "📦 Sipariş Önerisi", "value": f"{urun.get('oneri_miktar',0)} adet", "renk": trenk("amber")},
                ])
    
                # Sipariş durumu banner (yumuşak, tek katman)
                siparis_durum = urun.get("siparis_durum", "veri_yok")
                siparis_mesaj = urun.get("siparis_mesaj", "")
                _oneri_mesaj = urun.get("oneri_mesaj", "")
                _durum_stil = {
                    "acil":       ("rgba(239,68,68,0.07)", "rgba(239,68,68,0.55)", "🚨", trenk("kirmizi")),
                    "yaklasıyor": ("rgba(245,158,11,0.07)", "rgba(245,158,11,0.5)", "⚠️", trenk("amber")),
                    "planlama":   ("rgba(59,130,246,0.07)", "rgba(59,130,246,0.5)", "📋", trenk("mavi")),
                    "veri_yok":   ("rgba(34,197,94,0.06)", "rgba(34,197,94,0.45)", "✅", trenk("yesil2")),
                }
                _bg, _brd, _ik, _tc = _durum_stil.get(siparis_durum, _durum_stil["veri_yok"])
                _detay = f' <span style="color:var(--k-soluk);font-weight:400;">· {_oneri_mesaj}</span>' if _oneri_mesaj else ""
                st.markdown(
                    f'<div style="background:{_bg};border-left:3px solid {_brd};border-radius:8px;padding:12px 16px;margin:8px 0;font-size:13px;">'
                    f'<span style="color:{_tc};font-weight:700;">{_ik} {siparis_mesaj}</span>{_detay}</div>',
                    unsafe_allow_html=True
                )
    
                st.markdown("---")
    
                st.markdown(B.grup_basligi("🚢 Yoldaki ürün durumu"), unsafe_allow_html=True)
                _yr = urun.get("yol_renk", "yok")
                _ymik = urun.get("yol_miktar", 0)
                _ymsg = urun.get("yol_mesaj", "")
                _yol_map = {"yesil": ("rgba(34,197,94,0.10)", trenk("yesil2"), "🟢", f"{_ymik} adet yolda · {_ymsg}"), "sari": ("rgba(245,158,11,0.10)", trenk("amber"), "🟡", f"{_ymik} adet yolda · {_ymsg}"), "kirmizi": ("rgba(239,68,68,0.10)", trenk("kirmizi"), "🔴", _ymsg)}
                _yb, _yc, _yi, _yt = _yol_map.get(_yr, ("rgba(148,163,184,0.08)", trenk("soluk"), "⚪", "Yolda ürün kaydı bulunmuyor."))
                st.markdown(f'<div style="background:{_yb};border-left:3px solid {_yc};border-radius:7px;padding:8px 12px;font-size:13px;color:{_yc};font-weight:600;display:inline-block">{_yi} {_yt}</div>', unsafe_allow_html=True)

                # Ayrıntılı geçmiş (alım, satış, kampanya, iade, stok hareketleri) Stok Kartı'nda
                if st.button("Stok kartını aç · alım, satış, kampanya geçmişi", key="pm_urun_stok_karti",
                             icon=":material/inventory_2:"):
                    from kayranpm.stok_karti import goster as _sk_ac
                    _sk_ac(secilen_sku)
                st.markdown("---")

                # KALICI PANEL — @st.dialog DEĞİL.
                # Dialog, st.rerun() çağrıldığında kapanıyordu; her kayıttan sonra
                # düğmeye basıp yeniden açmak gerekiyordu. Normal panel açık kalır,
                # kaydettikten sonra listeden başka ürün seçip devam edebilirsin.
                def _dlg_urun_duzenle():
                    st.caption("Alanları düzenle, **Kaydet**'e bas. Başka ürünü düzenlemek için listeye dön.")
                    _sec_sku = secilen_sku
                    _u = secilen
                    if _u:
                        with st.form("urun_duzen_form"):
                            fc1, fc2, fc3, fc4 = st.columns([3, 1.5, 1.2, 1])
                            with fc1:
                                d_ad = st.text_input("Ürün Adı", value=_u.get("urun_adi", "") or "")
                            with fc2:
                                d_kat = st.text_input("Kategori", value=_u.get("kategori", "") or "")
                            with fc3:
                                d_satis = st.number_input("Genel Satış ($)", value=float(_u.get("satis_fiyati", 0) or 0), min_value=0.0, step=1.0, format="%.4f",
                                                          help="Genel/liste fiyatı — kâr marjı ve dashboard bundan hesaplanır.")
                            with fc4:
                                d_stok = st.number_input("G5F Depo", value=int(_u.get("bizim_stok", 0) or 0), min_value=0, step=1)

                            # ── YURT İÇİ ALIM MALİYETİ ──
                            # Kaspersky, mouse pad gibi ithalatı olmayan ürünlerin
                            # maliyeti hiçbir yerden gelmiyordu; raporlarda marj %100
                            # çıkıyordu. Burası tüm raporları besleyen tek giriş noktası.
                            from shared.utils import sku_anahtar as _skn_kart
                            _ith_pacal = 0.0
                            try:
                                from ithalat.database import get_sku_maliyet_ozet as _gsmo
                                for _s2, _v2 in (_gsmo() or {}).items():
                                    if _skn_kart(_s2) == _skn_kart(_sec_sku):
                                        _ith_pacal = float(_v2.get("pacal_final") or 0)
                                        break
                            except Exception:
                                _ith_pacal = 0.0

                            _alis_mevcut = float(_u.get("alis_fiyati", 0) or 0)
                            st.markdown("**\U0001F4B5 Birim Maliyet ($)**")
                            if _ith_pacal > 0:
                                st.info(
                                    "Bu ürünün **ithalat paçalı** var: "
                                    "**${}**. Raporlarda o kullanılır — aşağıdaki alan "
                                    "yalnız yurt içinden alınan, ithalatı olmayan ürünler "
                                    "içindir.".format(tr_sayi(_ith_pacal, 4)))
                                d_alis = st.number_input(
                                    "Yurt içi alış maliyeti ($) — bu üründe kullanılmıyor",
                                    value=_alis_mevcut, min_value=0.0, step=0.01,
                                    format="%.4f", key="urun_alis_f")
                            else:
                                d_alis = st.number_input(
                                    "Yurt içi alış maliyeti ($) — birim başına, nakliye dahil",
                                    value=_alis_mevcut, min_value=0.0, step=0.01,
                                    format="%.4f", key="urun_alis_f",
                                    help="Bu ürünün ithalat dosyası yok. Buraya girdiğin maliyet "
                                         "Kâr/P&L, marka/kategori kırılımı ve tüm satış "
                                         "raporlarında kullanılır. 0 bırakırsan marj %100 "
                                         "görünmeye devam eder.")
                                if _alis_mevcut <= 0:
                                    st.warning(
                                        "\u26a0\ufe0f Maliyet girilmemiş — bu ürünün satışları "
                                        "raporlarda **%100 marj** gösterir.")

                            # Müşteri bazlı satış fiyat listesi (ana müşteriler hazır + satır ekleyerek yeni müşteri)
                            from .database import ANA_MUSTERILER as _ANA_MUST
                            _mevcut_liste = _u.get("satis_fiyat_listesi") or {}
                            _musteriler = list(_ANA_MUST) + [m for m in _mevcut_liste if m not in _ANA_MUST]
                            _liste_df = pd.DataFrame(
                                [{"Müşteri": m, "Fiyat ($)": float(_mevcut_liste.get(m, 0) or 0)} for m in _musteriler]
                            )
                            st.markdown("**Satış Fiyat Listesi (müşteri bazlı)** — ana müşteriler hazır gelir; "
                                        "müşteriye özel fiyat gir. **Satır ekleyip** yeni müşteri de yazabilirsin (0 bıraktığın satır kaydedilmez).")
                            _liste_edit = st.data_editor(
                                _liste_df, num_rows="dynamic", use_container_width=True, key="urun_fiyat_liste",
                                column_config={
                                    "Müşteri": st.column_config.TextColumn("Müşteri", required=False),
                                    "Fiyat ($)": st.column_config.NumberColumn("Fiyat ($)", min_value=0.0, step=1.0, format="%.4f"),
                                },
                            )
                            d_eol = st.checkbox(
                                "⛔ EOL — üretimi/satışı sonlandı (bu ürüne sipariş ÖNERİLMESİN)",
                                value=bool(_u.get("eol")))

                            if st.form_submit_button("Kaydet", type="primary", use_container_width=True, icon=":material/save:"):
                                from .database import upsert_urun as _upsert_urun
                                # Fiyat listesini editörden topla
                                _yeni_liste = {}
                                try:
                                    for _, _r in _liste_edit.iterrows():
                                        _m = str(_r.get("Müşteri", "") or "").strip()
                                        _fy = float(_r.get("Fiyat ($)", 0) or 0)
                                        if _m and _fy != 0:
                                            _yeni_liste[_m] = _fy
                                except Exception:
                                    _yeni_liste = {}
                                try:
                                    _upsert_urun(
                                        _sec_sku, d_ad.strip(), d_kat.strip(),
                                        _u.get("marka", "") or "", float(d_satis or 0),
                                        float(d_alis or 0), float(_u.get("hedef_kar_marji", 0) or 0),
                                        _u.get("ozellikler", "") or "", int(d_stok or 0),
                                        int(_u.get("trendyol_stok", 0) or 0),
                                        satis_fiyat_listesi=_yeni_liste, eol=d_eol,
                                    )
                                    st.cache_data.clear()
                                    # Panel AÇIK kalsın: bayrağı koru, seçili ürünü
                                    # hatırla. rerun listeyi tazeler ama panel kapanmaz.
                                    st.session_state["urun_duz_acik"] = True
                                    st.session_state["_urun_duz_son"] = _sec_sku
                                    st.toast(f"✅ {_sec_sku} güncellendi", icon="✅")
                                    st.rerun()
                                except Exception as _e:
                                    st.error(f"Kaydedilemedi: {_e}")

                        # ── Yanlış girilen stok kartını sil ──
                        st.markdown("<div style='height:1px;background:color-mix(in srgb,var(--k-metin) 6%,transparent);margin:12px 0 8px'></div>",
                                    unsafe_allow_html=True)
                        _sil_onay = st.checkbox(f"⚠️ '{_sec_sku}' stok kartını kalıcı olarak sil", key="urun_sil_onay")
                        if st.button("Stok Kartını Sil", key="urun_sil_btn",
                                     disabled=not _sil_onay, use_container_width=True, icon=":material/delete:"):
                            from .database import sil_urun as _sil_urun
                            try:
                                _sil_urun(_sec_sku)
                                st.cache_data.clear()
                                st.session_state.pop("_urun_duz_son", None)   # silinen ürünü unutma
                                st.session_state["urun_duz_acik"] = False
                                B.birak("pm_urun")                             # listeye dön
                                st.toast(f"🗑️ {_sec_sku} silindi", icon="🗑️")
                                st.rerun()
                            except Exception as _e:
                                st.error(f"Silinemedi: {_e}")
                # Panel durumu session_state'te tutulur → rerun'da kaybolmaz.
                _duz_acik = st.session_state.get("urun_duz_acik", False)
                if st.button(("✖️ Ürün Düzenle — kapat" if _duz_acik else "✏️ Ürün Düzenle"),
                             key="btn_urun_duz", use_container_width=True,
                             type=("secondary" if _duz_acik else "primary")):
                    st.session_state["urun_duz_acik"] = not _duz_acik
                    st.rerun()
                if st.session_state.get("urun_duz_acik"):
                    with st.container(border=True):
                        _dlg_urun_duzenle()

        elif sayfa == "Stok Yaşı":
            from .stok_yasi_ekran import goster as _stok_yasi
            _stok_yasi()

        elif sayfa == "💵  Yurt İçi Alış":
            st.markdown(_sb("💵 Ürün Yönetimi", "Yurt içi alış",
                            aciklama="yurt içi satın alma · ithalat gibi girilir · paçal, stok kartı ve stok yaşı buradan beslenir"), unsafe_allow_html=True)
            # Yedek maliyet sekmesi (kart alış fiyatı düzenleyicisi) kullanıcı isteğiyle kaldırıldı (Ekim 2026);
            # kartta kayıtlı alış fiyatları paçalda yedek olarak okunmaya devam eder (get_pacal_map).
            from .yurtici_ekran import goster as _yurtici
            _yurtici()

        elif sayfa == "📈  Müşteri Satışları":
            st.markdown(_sb("📈 Ürün Yönetimi", "Müşteri Satışları", aciklama="Müşteri raporlarından haftalık satış ve kanal stoğu · müşteriye, markaya, ürüne ya da kategoriye göre · aynı haftada yalnız en güncel yükleme sayılır"), unsafe_allow_html=True)
            from shared.yukleme_takvimi import serit as _yt_serit
            _yt_serit("musteri_haftalik")        # haftalık müşteri dosyası: geri sayım şeridi
            # Liste + detay ekranı (Ekim 2026): kayranpm/musteri_ekran.py · hesap: musteri_hesap.py
            from .musteri_ekran import render as _musteri_ekrani
            _musteri_ekrani()      # dosya yükleme: üst menüdeki Dosya kapısı (kapi_musteri_haftalik)

        elif sayfa == "🎯  Kampanya Takip":
            # Yeni ekran: kayranpm/kampanya.py (hesaplar kampanya_hesap.py'de, testli)
            from .kampanya import render as _kampanya_ekrani
            _kampanya_ekrani()

        elif sayfa == "📦  Sipariş Önerisi":
            # Ekran: kayranpm/siparis_ekran.py (satır içi onay/red, geçmiş her zaman görünür)
            from .siparis_ekran import render as _siparis_ekrani
            _siparis_ekrani(_sb)

        elif sayfa == "🔖  Ref No Takibi":
            from .ref_no import render as _ref_render
            _ref_render()

        elif sayfa == "Toplu İşlemler":
            st.markdown(_sb("📂 Ürün Yönetimi", "Toplu İşlemler", aciklama="Toplu fiyat, kategori ve SKU düzenleme · dışa aktar · geçmiş yüklemeler. Excel dosyaları üst menüdeki Dosya düğmesinden yüklenir."), unsafe_allow_html=True)

            # 💲 Toplu Satış Fiyatı & Marj
            @st.dialog("💲 Toplu Satış Fiyatı & Marj — paçal maliyetten fiyat öner", width="large")
            def _dlg_toplu_fiyat():
                from .database import toplu_satis_kaydet as _satis_kaydet, _hepsi as _hepsi_s
                from shared.utils import sku_anahtar as _skn_tf       # özet anahtarı normalize (Faz 2b)
                try:
                    from ithalat.database import get_sku_maliyet_ozet as _ith_maliyet
                    _pacal_map = _ith_maliyet() or {}
                except Exception:
                    _pacal_map = {}
                try:
                    _ur_s = _hepsi_s("urunler", "sku, urun_adi, satis_fiyati, hedef_kar_marji",
                                     "urun_adi") or []
                except Exception as _e_s:
                    _ur_s = []
                    st.warning(f"Ürünler okunamadı: {_e_s}")
                if not _ur_s:
                    st.info("Henüz ürün yok.")
                else:
                    _fiyatsiz = sum(1 for u in _ur_s if not (u.get("satis_fiyati") or 0))
                    st.caption(f"Toplam {len(_ur_s)} ürün · satış fiyatı girilmemiş {_fiyatsiz}. "
                               "Hedef marjı gir → 🪄 Öner ile paçaldan satış fiyatı hesapla → düzelt → 💾 Kaydet.")
                    _sc1, _sc2, _sc3 = st.columns([1, 1, 1])
                    _hedef_marj = _sc1.number_input("Hedef marj (%)", min_value=0.0, max_value=500.0,
                                                    value=25.0, step=5.0, key="satis_marj")
                    _sadece_fiyatsiz = _sc2.checkbox("Sadece fiyatsız ürünler", value=False, key="satis_sadece")
                    if _sc3.button("Marj'dan Satış Öner", use_container_width=True, key="satis_oner", icon=":material/auto_fix_high:"):
                        _on = {}
                        for u in _ur_s:
                            _p = (_pacal_map.get(_skn_tf(u["sku"]), {}) or {}).get("pacal_final", 0) or 0
                            if _p > 0:
                                _on[u["sku"]] = round(_p * (1 + _hedef_marj / 100.0), 2)
                        st.session_state["_satis_oneri"] = _on
                        st.session_state["_satis_oneri_v"] = st.session_state.get("_satis_oneri_v", 0) + 1
                        st.toast(f"🪄 {len(_on)} ürün için satış fiyatı önerildi (marj %{tr_sayi(_hedef_marj)})", icon="🪄")
                        st.rerun(scope="fragment")      # pencere açık kalsın (tam yenileme kapatıyordu)
                    _son = st.session_state.get("_satis_oneri", {})
                    st.caption("Satış ($) hücresini elle de değiştirebilirsin. Paçal = İthalat maliyeti · "
                               "Marj % satışı değiştirince kaydederken yeniden hesaplanır.")
                    _liste_s = [u for u in _ur_s if not (u.get("satis_fiyati") or 0)] if _sadece_fiyatsiz else _ur_s
                    _rows_s = []
                    for u in _liste_s:
                        _p = (_pacal_map.get(_skn_tf(u["sku"]), {}) or {}).get("pacal_final", 0) or 0
                        _ps = (_pacal_map.get(_skn_tf(u["sku"]), {}) or {}).get("son_final", 0) or 0
                        _satis = _son.get(u["sku"]) if u["sku"] in _son else (u.get("satis_fiyati") or 0)
                        _marj = ((_satis / _p - 1) * 100) if (_p > 0 and _satis) else 0.0
                        _rows_s.append({
                            "SKU": u["sku"], "Ürün Adı": u.get("urun_adi", ""),
                            "Paçal ($)": round(_p, 2), "Son ($)": round(_ps, 2),
                            "Satış ($)": round(float(_satis or 0), 2),
                            "Marj %": round(_marj, 1),
                        })
                    _df_s = pd.DataFrame(_rows_s)
                    _ed_s_key = f"satis_editor_{int(_sadece_fiyatsiz)}_{st.session_state.get('_satis_oneri_v', 0)}"
                    _edited_s = st.data_editor(
                        _df_s, use_container_width=True, height=420, hide_index=True, key=_ed_s_key,
                        column_config={
                            "SKU": st.column_config.TextColumn("SKU", disabled=True, width="small"),
                            "Ürün Adı": st.column_config.TextColumn("Ürün Adı", disabled=True, width="large"),
                            "Paçal ($)": st.column_config.NumberColumn("Paçal ($)", disabled=True, format="dollar", step=0.01),
                            "Son ($)": st.column_config.NumberColumn("Son ($)", disabled=True, format="dollar", step=0.01, help="En yeni ithalat dosyasındaki maliyet (referans · öneri paçala göre)"),
                            "Satış ($)": st.column_config.NumberColumn("Satış ($)", min_value=0.0, step=0.01, format="dollar"),   # step = gösterilen hane (kuruş)
                            "Marj %": st.column_config.NumberColumn("Marj %", disabled=True, format="localized", step=0.1),
                        },
                    )
                    if st.button("Satış Fiyatlarını Kaydet", type="primary", key="satis_kaydet_btn", icon=":material/save:"):
                        _map_s = {}
                        for _, r in _edited_s.iterrows():
                            _satis_v = float(r.get("Satış ($)") or 0)
                            _p = float(r.get("Paçal ($)") or 0)
                            _marj_v = ((_satis_v / _p - 1) * 100) if (_p > 0 and _satis_v) else 0.0
                            _map_s[str(r["SKU"])] = {"satis_fiyati": _satis_v, "hedef_kar_marji": round(_marj_v, 1)}
                        with st.spinner("Kaydediliyor..."):
                            _oks, _hts = _satis_kaydet(_map_s)
                        st.session_state.pop("_satis_oneri", None)
                        st.toast(f"✅ {_oks} ürün fiyatı kaydedildi" + (f" · {_hts} hata" if _hts else ""), icon="✅")
                        st.rerun()
            if st.button("Toplu Satış Fiyatı & Marj — paçal maliyetten fiyat öner", key="btn_top_fiy", use_container_width=True, icon=":material/attach_money:"):
                _dlg_toplu_fiyat()

            # 🏷️ Toplu Kategori & Marka — markası/kategorisi boş ürünleri tek tabloda etiketle
            @st.dialog("🏷️ Toplu Kategori & Marka — ürünleri tek tabloda etiketle", width="large")
            def _dlg_toplu_kat_marka():
                from .database import (kategori_oner as _kat_oner,
                                       marka_oner as _marka_oner,
                                       toplu_kategori_marka_kaydet as _km_kaydet,
                                       kategori_standartlastir as _kat_std,
                                       _hepsi as _hepsi_kat)
                try:
                    # _hepsi → sayfalamalı; 1000'den fazla üründe liste kesilmesin
                    _ur_kat = _hepsi_kat("urunler", "sku, urun_adi, kategori, marka", "urun_adi") or []
                except Exception as _e_kat:
                    _ur_kat = []
                    st.warning(f"Ürünler okunamadı: {type(_e_kat).__name__}: {_e_kat}")
                if not _ur_kat:
                    st.info("Henüz ürün yok.")
                    return
                _kbos = sum(1 for u in _ur_kat if not (u.get("kategori") or "").strip())
                _mbos = sum(1 for u in _ur_kat if not (u.get("marka") or "").strip())
                st.caption(f"Toplam {len(_ur_kat)} ürün · kategorisiz **{_kbos}** · markasız **{_mbos}**. "
                           "Önce 🪄 Otomatik Öner'e bas, kalanları elle yaz, 💾 Kaydet. "
                           "Markası boş ürünler Satış → P&L'de **DİĞER** grubuna düşer.")
                _kc1, _kc2, _kc3 = st.columns([1, 1, 1])
                _sadece_bos = _kc1.checkbox("Sadece eksik olanlar", value=True, key="kat_sadece_bos",
                                            help="Kategorisi veya markası boş olan ürünleri gösterir.")
                if _kc2.button("Otomatik Öner (kategori + marka)", use_container_width=True, key="kat_oto", icon=":material/auto_fix_high:"):
                    _onk = {u["sku"]: _kat_oner(u.get("urun_adi", "")) for u in _ur_kat
                            if _kat_oner(u.get("urun_adi", ""))}
                    _onm = {u["sku"]: _marka_oner(u.get("urun_adi", "")) for u in _ur_kat
                            if _marka_oner(u.get("urun_adi", ""))}
                    st.session_state["_kat_oneri"] = _onk
                    st.session_state["_marka_oneri"] = _onm
                    st.session_state["_kat_oneri_v"] = st.session_state.get("_kat_oneri_v", 0) + 1
                    st.toast(f"🪄 {len(_onk)} kategori · {len(_onm)} marka önerildi", icon="🪄")
                    st.rerun(scope="fragment")      # pencere açık kalsın
                if _kc3.button("Kategori Standartlaştır", use_container_width=True, key="kat_std_btn",
                               help="Aynı kategorinin farklı yazımlarını tek biçime indirger (MONİTÖR / Monitör → monitör).", icon=":material/shuffle:"):
                    with st.spinner("Birleştiriliyor..."):
                        _ds, _hrt = _kat_std()
                    if _ds:
                        st.session_state["_kat_std_ozet"] = " · ".join(f"{e}→{y}" for e, y in list(_hrt.items())[:6])
                        st.toast(f"🔀 {_ds} ürün standart yazıma çevrildi", icon="🔀")
                    else:
                        st.session_state["_kat_std_ozet"] = "Zaten standart — birleştirilecek bir şey yok."
                    st.rerun(scope="fragment")      # pencere açık kalsın
                if st.session_state.get("_kat_std_ozet"):
                    st.caption("🔀 " + st.session_state.pop("_kat_std_ozet"))
                _onk = st.session_state.get("_kat_oneri", {})
                _onm = st.session_state.get("_marka_oneri", {})
                st.caption("**Kategori ve Marka hücrelerine tıklayıp serbestçe yazabilirsin.** "
                           "🪄 Otomatik Öner bilinenleri doldurur; üzerine kendi değerini yazabilirsin.")
                if _sadece_bos:
                    _liste = [u for u in _ur_kat
                              if not (u.get("kategori") or "").strip() or not (u.get("marka") or "").strip()]
                else:
                    _liste = _ur_kat
                if not _liste:
                    st.success("✅ Tüm ürünlerin kategorisi ve markası dolu.")
                    return
                _df_kat = pd.DataFrame([{
                    "SKU": u["sku"],
                    "Ürün Adı": u.get("urun_adi", ""),
                    "Kategori": (_onk.get(u["sku"]) or (u.get("kategori") or "")),
                    "Marka": (_onm.get(u["sku"]) or (u.get("marka") or "")),
                } for u in _liste])
                _ed_key = f"kat_editor_{int(_sadece_bos)}_{st.session_state.get('_kat_oneri_v', 0)}"
                _edited_kat = st.data_editor(
                    _df_kat, use_container_width=True, height=430, hide_index=True, key=_ed_key,
                    column_config={
                        "SKU": st.column_config.TextColumn("SKU", disabled=True, width="small"),
                        "Ürün Adı": st.column_config.TextColumn("Ürün Adı", disabled=True, width="large"),
                        "Kategori": st.column_config.TextColumn(
                            "Kategori", help="Serbest yaz (kasa, monitör, ekran kartı...)"),
                        "Marka": st.column_config.TextColumn(
                            "Marka", help="Serbest yaz (FAZEON, INNO3D, NZXT, MIO, AGI...)"),
                    },
                )
                if st.button("Kategori & Marka Kaydet", type="primary", key="kat_kaydet_btn", icon=":material/save:"):
                    _map = {str(r["SKU"]): {"kategori": str(r.get("Kategori", "") or "").strip(),
                                            "marka": str(r.get("Marka", "") or "").strip()}
                            for _, r in _edited_kat.iterrows()}
                    with st.spinner("Kaydediliyor..."):
                        _okk, _htk = _km_kaydet(_map)
                    st.session_state.pop("_kat_oneri", None)
                    st.session_state.pop("_marka_oneri", None)
                    st.toast(f"✅ {_okk} ürün kaydedildi" + (f" · {_htk} hata" if _htk else ""), icon="✅")
                    st.rerun()

            if st.button("Toplu Kategori & Marka — markasız ürünleri etiketle",
                         key="btn_top_kat_marka", use_container_width=True, icon=":material/sell:"):
                _dlg_toplu_kat_marka()

            # 🧹 'Fazeon ' önekli SKU temizliği — satislar'daki "Fazeon X24F165S" ile
            # urunler'deki "X24F165S" aynı ürün; önek yüzünden eşleşmeyip P&L'de
            # DİĞER'e düşüyor. Arka uç fonksiyonları hazırdı, arayüzü buradan bağlandı.
            @st.dialog("🧹 'Fazeon' Önekli SKU Temizliği", width="large")
            def _dlg_fazeon_sku():
                st.caption("Satış/stok kayıtlarında **'Fazeon ' önekiyle** yazılmış SKU'ları bulur ve "
                           "öneksiz gerçek koduna taşır (örn. `Fazeon X24F165S` → `X24F165S`). "
                           "8 tabloda birden çalışır: ürünler, satışlar, firma stok, kampanyalar, "
                           "yoldaki ürünler, stok yaşı, ithalat kalemleri, sipariş önerileri.")
                with st.spinner("Taranıyor — hiçbir şey yazılmıyor..."):
                    try:
                        _onz = sku_fazeon_temizle_onizle() or []
                    except Exception as _e_fz:
                        st.error(f"Önizleme alınamadı: {type(_e_fz).__name__}: {_e_fz}")
                        return
                if not _onz:
                    st.success("✅ Temizlenecek 'Fazeon' önekli SKU yok — sistem zaten temiz.")
                    return
                _top_kayit = sum(int(i.get("toplam_kayit") or 0) for i in _onz)
                _catisan = sum(1 for i in _onz if i.get("catisma"))
                st.markdown(f"**{len(_onz)} SKU** bulundu · toplam **{tr_sayi(_top_kayit)} kayıt** etkilenecek · "
                            f"**{_catisan}** tanesinin öneksiz hedefi zaten kayıtlı (birleştirilecek).")
                st.dataframe(pd.DataFrame([{
                    "Eski SKU": i["eski"], "Yeni SKU": i["yeni"],
                    "Durum": "🔗 Mevcutla birleşir" if i.get("catisma") else "✏️ Yeniden adlanır",
                    "Kayıt": int(i.get("toplam_kayit") or 0),
                    "Tablolar": ", ".join(f"{t}:{n}" for t, n in (i.get("tablolar") or {}).items()),
                } for i in _onz]), hide_index=True, use_container_width=True, height=300)
                st.warning("⚠️ Bu işlem **geri alınamaz** — 8 tabloda SKU'ları kalıcı olarak değiştirir. "
                           "Uygulamadan önce GitHub → Actions → **Gece Yedeği** iş akışını elle çalıştırıp "
                           "güncel bir yedek indirmen önerilir.")
                _onay = st.checkbox(f"Önizlemeyi inceledim; {len(_onz)} SKU'nun ({tr_sayi(_top_kayit)} kayıt) "
                                    "kalıcı olarak taşınacağını anladım.", key="fz_sku_onay")
                if st.button("Temizliği Uygula", type="primary", disabled=not _onay,
                             use_container_width=True, key="fz_sku_uygula", icon=":material/cleaning_services:"):
                    with st.spinner("Uygulanıyor — tablo tablo taşınıyor..."):
                        _ok_fz, _msg_fz = sku_fazeon_temizle_uygula()
                    st.cache_data.clear()
                    if _ok_fz:
                        st.success(_msg_fz)
                        st.caption("Satış → P&L sayfasını yenilediğinde bu satırlar FAZEON altında görünecek.")
                    else:
                        st.error(_msg_fz)

            if st.button("'Fazeon' Önekli SKU Temizliği — mükerrer SKU'ları birleştir",
                         key="btn_fz_sku", use_container_width=True, icon=":material/cleaning_services:"):
                _dlg_fazeon_sku()

    
            # Dışa aktar — tek adım: dosya yalnız indir'e basılınca üretilir
            # (eskiden "Oluştur" → "İndir" iki adımdı).
            from .rapor import excel_rapor_olustur, pdf_rapor_olustur
            from .urunler_ekran import uretilen_bayt as _ub
            st.markdown(B.grup_basligi("📤 Dışa aktar"), unsafe_allow_html=True)
            _zaman = tr_now().strftime('%Y%m%d_%H%M')
            _de1, _de2 = st.columns(2)
            _de1.download_button("Excel raporu", data=partial(_ub, ".xlsx", excel_rapor_olustur),
                                 file_name=f"Stok_Raporu_{_zaman}.xlsx", key="vy_excel_dl",
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 use_container_width=True, icon=":material/download:",
                                 help="Dashboard, stok yayılımı ve sipariş önerileri — 3 sekme")
            _de2.download_button("PDF raporu", data=partial(_ub, ".pdf", pdf_rapor_olustur),
                                 file_name=f"Stok_Raporu_{_zaman}.pdf", key="vy_pdf_dl", mime="application/pdf",
                                 use_container_width=True, icon=":material/download:",
                                 help="A4 yatay, yazdırmaya hazır özet")

            st.markdown("---")
            st.markdown(B.grup_basligi("📅 Geçmiş yüklemeler"), unsafe_allow_html=True)
            st.markdown('<div style="color:var(--k-soluk);font-size:13px;line-height:1.6;margin-bottom:8px">Hangi tarihlerde veri yüklendiğini gör, gerekirse sil.</div>', unsafe_allow_html=True)
    
            try:
                sb_vy = get_client()
    
                firma_tarihler = sb_vy.table("firma_stok").select("yukleme_tarihi, firma").execute().data or []
                urun_tarihler = sb_vy.table("urunler").select("guncelleme_tarihi").execute().data or []
                # Tek geçişte sayım (eskiden her tarih için tüm satırlar yeniden taranıyordu)
                rows_vy = yukleme_ozeti(firma_tarihler, urun_tarihler)
                if not rows_vy:
                    st.info("Henüz veri yüklenmemiş.")
                else:
                    render_renkli_tablo(pd.DataFrame(rows_vy).drop(columns=["_ham"]),
                                        sol=["Firmalar"], kisalt={"Firmalar": 60})

                    # Bir tarihin firma stok verisini sil — ONAYLI (eskiden tek tıkla
                    # siliniyor, önbellek de boşaltılmıyordu)
                    _sil_sec = [r for r in rows_vy if r["Firma Kayıt Sayısı"]]
                    if _sil_sec:
                        with st.expander("🗑️ Bir tarihin firma stok verisini sil"):
                            st.caption("Seçilen tarihe ait firma stok satırları silinir. Ürün listesi ve "
                                       "satın alma geçmişi etkilenmez. Geri alınamaz.")
                            _sil_r = st.selectbox(
                                "Silinecek tarih", _sil_sec, key="vy_sil_tarih",
                                format_func=lambda r: f'{r["Tarih"]} · {tr_sayi(r["Firma Kayıt Sayısı"])} kayıt · {r["Firmalar"]}')
                            if B.onayli_sil(f'{_sil_r["Tarih"]} tarihli {tr_sayi(_sil_r["Firma Kayıt Sayısı"])} '
                                            f'firma stok kaydını kalıcı olarak sil',
                                            # Onay anahtarı TARİHE bağlı: silmeden sonra seçici sıradaki
                                            # tarihe geçince onay kutusu işaretli kalıyordu (görüldü)
                                            key=f"vy_tarih_{_sil_r['_ham']}",
                                            dugme="Bu tarihin verisini sil"):
                                from .database import sil_firma_stok_tarihi
                                _n_sil = sil_firma_stok_tarihi(_sil_r["_ham"])
                                st.toast(f'🗑️ {_sil_r["Tarih"]} · {tr_sayi(_n_sil)} kayıt silindi')
                                st.rerun()

            except Exception as e:
                _log.warning("Hata: %s", e)
                st.warning(f"Geçmiş yüklemeler yüklenemedi: {e}")

    _sayfa_parcasi()

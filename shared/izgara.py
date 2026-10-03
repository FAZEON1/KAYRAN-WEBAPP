# -*- coding: utf-8 -*-
"""Streamlit tablo ızgarasının ortak görünümü (Ekim 2026).

Kısa, salt okunur tablolar zaten kendi tablomuza (shared/tablo.py) çevriliyor (app.py,
_akilli_dataframe). Bu modül KALANLARI düzenler: düzenlenebilir tablolar (st.data_editor) ve
anahtarlı / seçimli / uzun st.dataframe tabloları. Bu ızgara tuvale çizildiği için stil koduyla
değiştirilemez; yalnız Streamlit'in verdiği ayarlar kullanılır:

  • Satır yüksekliği biraz daha ferah (SATIR_YUKSEKLIGI).
  • Para: "$149,00" — Streamlit ondalık sayısını "adım"dan (step) alıyor; birim fiyat
    sütunlarına verilen 0,0001 adım "$149,0000" gösteriyordu. Küçük adım görünümden kaldırılır.
    KAYIT AYNI: düzenlenen hücre eskisi gibi o adımın hassasiyetine yuvarlanır (izgara_sonuc);
    dokunulmayan hücreye dokunulmaz (kayıt yolları "değişti mi" diye karşılaştırıyor).
  • Salt okunur sayı sütunları Türkçe: adet "1.234", oran "31,1", para "$1.234,56".
  • SKU sütunu dar kalmaz, ürün / açıklama sütunu geniş açılır (yalnız büyütülür, elle
    verilen daha geniş ayar ezilmez). Çok sütunlu tablolarda SKU solda sabit kalır.

Elle yazılmış ayarlar kazanır; bu modül yalnız eksikleri tamamlar ve yukarıdaki üç düzeltmeyi
yapar. Hata olursa tablo eski ayarlarla çizilir (görünüm katmanı; çalışmayı asla durdurmaz).
Geri alma: shared/tasarim.py → IZGARA_YENI = False.
"""
import copy

SATIR_YUKSEKLIGI = 40          # Streamlit varsayılanı 35 px
_ESKI_SATIR = 35
_BASLIK = 38                   # ekranlar yüksekliği "38 + 35 × satır" diye hesaplıyor
_KUCUK_ADIM = 0.01             # bundan küçük adım para sütununda görünümden kalkar
_GENISLIK_SIRA = {"small": 0, "medium": 1, "large": 2}
_SKU_AD = ("sku",)
_AD_AD = ("ürün", "urun", "açıklama", "aciklama", "ürün adı", "model")


def _ad(sutun):
    return str(sutun or "").strip().lower()


def _sku_mu(sutun):
    return _ad(sutun) in _SKU_AD


def _genis_mi(sutun):
    a = _ad(sutun)
    return a in _AD_AD or a.startswith(("ürün adı", "urun adi", "açıklama", "aciklama"))


def _ondalik(adim):
    """0.0001 → 4, 0.01 → 2, 1 → 0."""
    try:
        s = f"{float(adim):.10f}".rstrip("0")
        return len(s.split(".")[1]) if "." in s else 0
    except (TypeError, ValueError):
        return None


def _sutunlar(data):
    try:
        k = getattr(data, "columns", None)
        if k is not None:
            return list(k)
        if isinstance(data, (list, tuple)) and data and isinstance(data[0], dict):
            return list(data[0].keys())
    except Exception:  # noqa: BLE001
        pass
    return []


def _sayisal(data, sutun):
    try:
        import pandas as pd
        return pd.api.types.is_numeric_dtype(data[sutun]) and not pd.api.types.is_bool_dtype(data[sutun])
    except Exception:  # noqa: BLE001
        return False


def _genislet(cfg, en_az):
    """Sütunu en az 'en_az' genişliğe çıkarır; elle verilen daha geniş ayara dokunmaz."""
    w = cfg.get("width")
    if isinstance(w, int) and not isinstance(w, bool):
        return
    if _GENISLIK_SIRA.get(w, -1) < _GENISLIK_SIRA[en_az]:
        cfg["width"] = en_az


def izgara_ayar(data, column_config=None, duzenleme=False, kilitli=False):
    """(yeni column_config, yuvarla) döner.
    duzenleme: st.data_editor için. kilitli: data_editor'un disabled değeri (True ya da liste).
    yuvarla: {sütun: ondalık} — görünümden kaldırılan adımlar; data_editor sonucunda
    düzenlenen hücreler bu hassasiyete yuvarlanır (izgara_sonuc)."""
    from shared.tasarim import _tablo_kolon_tipi
    mevcut = dict(column_config or {})
    sutunlar = _sutunlar(data)
    yeni, yuvarla = {}, {}
    for sutun in sutunlar:
        v = mevcut.get(sutun)
        if v is None and sutun in mevcut:          # None → sütun gizli; dokunma
            continue
        if isinstance(v, str):                     # yalnız başlık verilmiş
            v = {"label": v}
        cfg = copy.deepcopy(v) if isinstance(v, dict) else {}
        tc = cfg.get("type_config")
        tip = _tablo_kolon_tipi(sutun)

        # 1) Para sütununda küçük adım → görünümden kaldır; kayıtta hassasiyet korunur
        if isinstance(tc, dict) and tc.get("type") == "number" and tip == "para":
            adim = tc.get("step")
            if adim is not None and 0 < float(adim) < _KUCUK_ADIM \
                    and tc.get("format") in ("dollar", "euro", "localized", None):
                tc["step"] = None
                if duzenleme:
                    yuvarla[sutun] = _ondalik(adim)

        # 2) Ayarı olmayan sütun → Türkçe biçim
        if not tc:
            _bicim_ver(cfg, data, sutun, tip, duzenleme, duzenleme and not _kilitli(sutun, cfg, kilitli))

        # 3) Genişlik: SKU dar kalmasın, ad / açıklama geniş açılsın
        if _sku_mu(sutun):
            _genislet(cfg, "medium")
        elif _genis_mi(sutun):
            _genislet(cfg, "large")

        if cfg:
            yeni[sutun] = cfg
    for sutun, v in mevcut.items():                # tabloda olmayan ayarlar (index vb.) aynen
        yeni.setdefault(sutun, v)
    return yeni, yuvarla


def _bicim_ver(cfg, data, sutun, tip, editor, duzenlenir):
    """Biçimi verilmemiş sütuna Türkçe biçim. Düzenlenebilir sütunda adım verilmez (Streamlit
    adımı girişi yuvarlamak için de kullanıyor). Düzenlenebilir tablolarda para "localized": bu
    tabloların bir kısmı TL tutar taşıyor, "$" basılmasın. Salt okunur tablolarda "dollar" (eski
    otomatik biçimle aynı)."""
    try:
        import pandas as pd
        seri = data[sutun]
        if pd.api.types.is_datetime64_any_dtype(seri):
            cfg["type_config"] = {"type": "date", "format": "DD.MM.YYYY"}
            return
    except Exception:  # noqa: BLE001
        return
    if not _sayisal(data, sutun) or tip not in ("para", "adet", "oran"):
        return
    if tip == "para":
        cfg["type_config"] = {"type": "number", "format": "localized" if editor else "dollar"}
    elif duzenlenir:
        return
    else:
        cfg["type_config"] = {"type": "number", "format": "localized", "step": 1 if tip == "adet" else 0.1}
    cfg.setdefault("alignment", "right")


def _kilitli(sutun, cfg, kilitli):
    if cfg.get("disabled"):
        return True
    return kilitli is True or (isinstance(kilitli, (list, tuple, set)) and sutun in kilitli)


def izgara_sonuc(girdi, cikti, yuvarla):
    """data_editor sonucunda yalnız DEĞİŞEN hücreleri eski adım hassasiyetine yuvarlar
    (adım görünümden kalkınca Streamlit girişi yuvarlamaz; kayıt eskisi gibi kalsın)."""
    if not yuvarla:
        return cikti
    try:
        import pandas as pd
        if not isinstance(cikti, pd.DataFrame) or not isinstance(girdi, pd.DataFrame):
            return cikti
        cikti = cikti.copy()
        for sutun, ond in yuvarla.items():
            if ond is None or sutun not in cikti.columns:
                continue
            yeni = pd.to_numeric(cikti[sutun], errors="coerce")
            eski = pd.to_numeric(girdi[sutun], errors="coerce").reindex(cikti.index) \
                if sutun in girdi.columns else pd.Series(index=cikti.index, dtype=float)
            degisen = yeni.notna() & ~(yeni == eski)
            if degisen.any():
                cikti.loc[degisen, sutun] = yeni[degisen].round(ond)
        return cikti
    except Exception:  # noqa: BLE001
        return cikti


# ── Kurulum (app.py) ────────────────────────────────────────────────
def _satir_ayari(kw):
    """Satır yüksekliğini verir; ekranın 35 px satıra göre verdiği sabit yüksekliği aynı satır
    sayısı görünecek şekilde büyütür. Satır yüksekliğini ekran kendisi verdiyse dokunmaz."""
    if kw.get("row_height") is not None:
        return kw
    kw["row_height"] = SATIR_YUKSEKLIGI
    h = kw.get("height")
    if isinstance(h, int) and not isinstance(h, bool) and h > _BASLIK:
        kw["height"] = h + (SATIR_YUKSEKLIGI - _ESKI_SATIR) * ((h - _BASLIK) // _ESKI_SATIR + 1)
    return kw


def dataframe_hazirla(data, kw):
    """Native st.dataframe çağrısının ayarlarını tamamlar (kw yerinde güncellenir)."""
    cfg, _ = izgara_ayar(data, kw.get("column_config"), duzenleme=False)
    kw["column_config"] = cfg
    return _satir_ayari(kw)


def kur(st):
    """st.data_editor'u sarar. Hata olursa sessizce eski davranışta kalır."""
    try:
        from shared.tasarim import IZGARA_YENI
        if not IZGARA_YENI:
            return
        from streamlit.delta_generator import DeltaGenerator as DG
        if getattr(DG.data_editor, "_kayran_izgara", False):
            orij = DG.data_editor._kayran_orij
        else:
            orij = DG.data_editor

        def data_editor(self, data, *a, **kw):
            yuvarla = {}
            try:
                cfg, yuvarla = izgara_ayar(data, kw.get("column_config"), duzenleme=True,
                                           kilitli=kw.get("disabled", False))
                kw = _satir_ayari(dict(kw, column_config=cfg))
            except Exception:  # noqa: BLE001
                yuvarla = {}
            sonuc = orij(self, data, *a, **kw)
            return izgara_sonuc(data, sonuc, yuvarla)

        data_editor._kayran_izgara = True
        data_editor._kayran_orij = orij
        DG.data_editor = data_editor
        kok = getattr(st.data_editor, "__self__", None)
        if kok is not None:
            st.data_editor = data_editor.__get__(kok, DG)
    except Exception:  # noqa: BLE001
        pass

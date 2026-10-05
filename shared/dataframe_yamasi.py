# -*- coding: utf-8 -*-
"""st.dataframe yaması: kısa tablolar ortak tabloya (shared.tablo), kalanlar biçimli native tabloya.

SORUN : 74 st.dataframe çağrısının çoğu ham sayı gösteriyordu — 596699.4595 · 36.9231 · 21813.
        Binlik ayraç yok, para birimi yok, sola yaslı; sıralama da alfabetik bozuluyordu.
ÇÖZÜM : st.dataframe sarmalanır; kolon adına göre biçim otomatik verilir. ELLE yazılmış column_config
        her zaman kazanır (ezilmez), yalnız eksik kolonlar tamamlanır. Native kalan tablolar ve
        st.data_editor ortak ızgara ayarıyla çizilir (shared/izgara.py; kayıt değerleri aynı).

YAMA HER ÇALIŞMADA GÜNCEL KODLA KURULUR (Ekim 2026). Yama Streamlit'in DeltaGenerator SINIFINA
yazılır ve süreç boyunca kalır; Streamlit Cloud yeni kodu çekince süreci yeniden başlatmaz. Eskiden
app.py "zaten yamalı" görünce atlıyordu: canlı süreç ilk açılıştaki ESKİ yamayı kullanmaya devam etti
ve pencere içi tablo düzeltmesi hiç devreye girmedi (stok kartı · Satışlar'daki Kanal / Firma Kırılımı
pencerede değil arkadaki sayfada çiziliyordu). Şimdi her çalışmada asıl Streamlit fonksiyonu bulunur
(_kayran_orij, eski yamalarda modül değişkeni _ORIJ_DATAFRAME) ve yama onun üstüne yeniden kurulur;
yamanın kendini sarması (özyineleme) bu yüzden olmaz.
"""

# Sıralanabilir HTML tabloya çevirmeyi ENGELLEYEN durumlar
_OZEL_KOLON = ("link", "image", "progress", "bar_chart", "line_chart",
               "area_chart", "button", "checkbox", "selectbox", "multiselect",
               "json", "list", "markdown", "audio", "video")


def html_uygun_mu(data, kw):
    """Muhafazakâr uygunluk testi: kayıt listesi ya da None (şüphe varsa native st.dataframe kalır)."""
    if kw.get("on_select") or kw.get("key") or kw.get("column_order"):
        return None
    try:
        import pandas as _pd
        # `_pd.io.formats.style.Styler` YAZILAMAZ — alt modül ayrıca içe aktarılmadan AttributeError
        # verir ve try onu yutup TÜM tabloları native'e düşürür. Sınıf adıyla test etmek güvenli.
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
        # Önce object: sayı sütununda where(..., None) NaN'ı None'a ÇEVİRMİYOR (pandas 2.3 / 3.0)
        # ve boş hücrede "nan" yazıyordu (Happy Life "Fark").
        return df.astype(object).where(_pd.notna(df), None).to_dict("records")
    except Exception:  # noqa: BLE001
        return None


def asil_fonksiyon(mevcut):
    """Yamasız Streamlit dataframe fonksiyonu: mevcut yamalıysa altındaki asıl."""
    for _ in range(10):                  # yama üstüne yama (eski sürümler) zinciri
        if not getattr(mevcut, "_kayran_yamali", False):
            return mevcut
        alt = getattr(mevcut, "_kayran_orij", None)
        if alt is None:                  # Ekim 2026 öncesi yama: asıl, modül değişkeninde
            alt = (getattr(mevcut, "__globals__", None) or {}).get("_ORIJ_DATAFRAME")
        if alt is None:
            return None
        mevcut = alt
    return None


def kur(st_modul=None, dg_sinif=None):
    """Yamayı GÜNCEL kodla kurar (app.py her çalışmada çağırır). Kurulamazsa sessizce geçer."""
    try:
        if st_modul is None:
            import streamlit as st_modul
        if dg_sinif is None:
            from streamlit.delta_generator import DeltaGenerator as dg_sinif
        orij = asil_fonksiyon(dg_sinif.dataframe)
        if orij is None:
            return False
        kok = getattr(st_modul.dataframe, "__self__", None)   # modül düzeyi st.dataframe'in kabı

        def _akilli_dataframe(self, data=None, *a, **kw):
            """st.dataframe / kolon.dataframe yerine geçer. KISA ve salt-okur tablolar → ortak tablo;
            UZUN, seçimli ya da özel kolonlu tablolar → biçimli native st.dataframe."""
            try:
                from shared.tasarim import otomatik_kolonlar, tablo_sirali
                kayitlar = html_uygun_mu(data, kw)
                if kayitlar is not None:
                    # Modül düzeyi st.dataframe kök sayfa kabına bağlı: kap olarak verilirse tablo
                    # "with kök:" ile SAYFAYA yazılıyor, pencere (st.dialog) içindeyken pencerede değil
                    # arkadaki sayfada çıkıyordu. Kök kapta kap=None → tablo bulunduğu yere çizilir.
                    tablo_sirali(kayitlar, kap=None if (kok is not None and self is kok) else self)
                    return None
                from shared.tasarim import IZGARA_YENI
                if IZGARA_YENI:          # ortak ızgara ayarı (shared/izgara.py)
                    from shared.izgara import dataframe_hazirla
                    dataframe_hazirla(data, kw)
                else:
                    kw["column_config"] = otomatik_kolonlar(data, kw.get("column_config"))
            except Exception:  # noqa: BLE001 — biçimlendirme başarısızsa tablo yine çizilsin
                pass
            return orij(self, data, *a, **kw)

        _akilli_dataframe._kayran_yamali = True
        _akilli_dataframe._kayran_orij = orij
        dg_sinif.dataframe = _akilli_dataframe
        # Modül düzeyindeki st.dataframe'i yeniden bağla — ancak bağlı metotsa (bazı sürümlerde düz
        # fonksiyon, __self__ yok: o zaman yalnız sınıf yaması yeter).
        if kok is not None:
            st_modul.dataframe = _akilli_dataframe.__get__(kok, dg_sinif)
        return True
    except Exception:  # noqa: BLE001 — burada atılan istisna uygulamayı tamamen çökertirdi
        return False

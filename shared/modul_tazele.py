# -*- coding: utf-8 -*-
"""Bayat modül koruması (Ekim 2026).

SORUN: Streamlit Cloud güncellemeyi alırken bazı modülleri yeniden yükleyip bazılarını
BELLEKTE eski hâliyle bırakabiliyor. Yeni bir sayfa dosyası, eski bellekteki modülde
olmayan bir adı içe aktarınca 'ImportError: cannot import name …' çıkıyordu (3 Ekim:
'urun_ad' from 'shared.ana_veri' — dosyada vardı, bellekte yoktu). Tek çare uygulamayı
yeniden başlatmaktı.

ÇÖZÜM: Hata PROJE dosyasından gelen bir içe aktarma hatasıysa proje modülleri bellekten
silinir ve sayfa bir kez yeniden çalıştırılır (app.py). Aynı oturumda bir kez denenir;
hata sürerse normal hata kartı görünür (döngü yok).
"""
import os


def _proje_icinde(yol, kok):
    try:
        return bool(yol) and os.path.abspath(str(yol)).startswith(os.path.abspath(kok) + os.sep)
    except Exception:  # noqa: BLE001
        return False


def tazelenmeli(hata, kok):
    """Bu hata bayat modülden mi olabilir? ImportError ve kaynağı proje dosyası."""
    if not isinstance(hata, ImportError):
        return False
    if _proje_icinde(getattr(hata, "path", None), kok):
        return True
    ad = (getattr(hata, "name", None) or "").split(".")[0]
    return bool(ad) and os.path.isdir(os.path.join(kok, ad))


def proje_modullerini_sil(moduller, kok):
    """sys.modules'tan dosyası proje klasöründe olan modülleri siler; silinen adları döndürür.
    '__main__' ve proje dışı (streamlit, pandas…) modüllere dokunmaz."""
    silinen = []
    for ad, m in list(moduller.items()):
        if ad == "__main__" or m is None:
            continue
        if _proje_icinde(getattr(m, "__file__", None), kok):
            moduller.pop(ad, None)
            silinen.append(ad)
    return silinen

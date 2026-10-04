# -*- coding: utf-8 -*-
"""Bayat modül koruması (Ekim 2026).

SORUN: Streamlit Cloud güncellemeyi alırken bazı modülleri yeniden yükleyip bazılarını
BELLEKTE eski hâliyle bırakabiliyor. Yeni bir sayfa dosyası, eski bellekteki modülde
olmayan bir adı içe aktarınca 'ImportError: cannot import name …' çıkıyordu (3 Ekim:
'urun_ad' from 'shared.ana_veri' — dosyada vardı, bellekte yoktu). Tek çare uygulamayı
yeniden başlatmaktı.

Aynısı eski fonksiyonun yeni parametreyle çağrılmasında da olur ('unexpected keyword
argument'). 3 Ekim: Müşteri Satışları güncellemeden sonra hata verdi, Reboot ile düzeldi;
muhtemel sebep yeni ekranın eski meta_hazirla'yı eslesme= ile çağırması — bu tür yakalanmıyordu.

ÇÖZÜM: Hata PROJE dosyasından gelen bir içe aktarma / eksik ad / çağrı imzası hatasıysa
proje modülleri bellekten silinir ve sayfa bir kez yeniden çalıştırılır (app.py). Aynı oturumda bir kez denenir;
hata sürerse normal hata kartı görünür (döngü yok).
"""
import os


def _proje_icinde(yol, kok):
    try:
        return bool(yol) and os.path.abspath(str(yol)).startswith(os.path.abspath(kok) + os.sep)
    except Exception:  # noqa: BLE001
        return False


# Çağrı imzası uyuşmazlığı: yeni dosya, bellekte eski kalan fonksiyonu yeni parametreyle çağırır
# (ör. meta_hazirla(..., eslesme=…) → "got an unexpected keyword argument 'eslesme'").
_IMZA_IPUCLARI = ("unexpected keyword argument", "positional argument")


def _son_cerceve_dosyasi(hata):
    tb = getattr(hata, "__traceback__", None)
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    return tb.tb_frame.f_code.co_filename if tb is not None else None


def tazelenmeli(hata, kok):
    """Bu hata bayat modülden mi olabilir?
      - ImportError, kaynağı proje dosyası/paketi ('cannot import name …');
      - AttributeError, eksik ad bir PROJE modülünde ('module … has no attribute …');
      - TypeError, çağrı imzası uyuşmuyor ve hata proje dosyasındaki çağrıda çıktı.
    Gerçek bir kod hatası da bu kalıba uyabilir; o durumda modüller bir kez tazelenir, hata
    sürer ve normal hata kartı görünür (aynı oturumda bir kez denenir, döngü yok)."""
    if isinstance(hata, ImportError):
        if _proje_icinde(getattr(hata, "path", None), kok):
            return True
        ad = (getattr(hata, "name", None) or "").split(".")[0]
        return bool(ad) and os.path.isdir(os.path.join(kok, ad))
    if isinstance(hata, AttributeError):
        return _proje_icinde(getattr(getattr(hata, "obj", None), "__file__", None), kok)
    if isinstance(hata, TypeError):
        return (any(i in str(hata) for i in _IMZA_IPUCLARI)
                and _proje_icinde(_son_cerceve_dosyasi(hata), kok))
    return False


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


# ── Hatasız bayat modül (Ekim 2026) ─────────────────────────────────
# Yukarıdaki koruma yalnız HATA çıkınca çalışıyordu. Güncellemeden sonra bellekte eski kalan bir
# modül hata vermeden ESKİ davranışı sürdürüyordu: PR #117 / #118 birleşti, kod doğruydu, canlıdaki
# stok kartı hâlâ eski mesajı gösteriyordu (Reboot gerekiyordu). Artık her çalıştırmada yüklü
# proje modüllerinin dosya zamanı kontrol edilir; biri değiştiyse BÜTÜN proje modülleri bellekten
# silinir (birbirinden içe aktardıkları eski nesneler de gitsin) ve bu çalıştırma yeni koddan yükler.
def degisen_moduller(moduller, kok, kayit):
    """Yüklü proje modüllerinden dosyası, ilk görüldüğü andan sonra değişenler.
    kayit: {modül adı: dosya zamanı} — süreç boyunca yaşamalı (proje modülü silinse de)."""
    degisen = []
    for ad, m in list(moduller.items()):
        if ad == "__main__" or m is None:
            continue
        f = getattr(m, "__file__", None)
        if not _proje_icinde(f, kok):
            continue
        try:
            mt = os.path.getmtime(f)
        except OSError:
            continue
        eski = kayit.setdefault(ad, mt)
        if mt != eski:
            degisen.append(ad)
    return degisen


def yuklenenleri_kaydet(moduller, kok, kayit):
    """Çalıştırmanın SONUNDA: bu çalıştırmada yüklenen modüllerin dosya zamanını kaydeder.
    Kayıt yalnız başta alınsaydı, bir modül yüklendikten sonra ve bir sonraki çalıştırmadan önce
    gelen güncelleme 'ilk görüş' sayılıp kaçardı (yerel denemede yakalandı)."""
    degisen_moduller(moduller, kok, kayit)


def bayatlari_tazele(moduller, kok, kayit):
    """Değişen dosya varsa proje modüllerini siler ve kaydı sıfırlar; silinen adları döndürür."""
    if not degisen_moduller(moduller, kok, kayit):
        return []
    kayit.clear()
    return proje_modullerini_sil(moduller, kok)

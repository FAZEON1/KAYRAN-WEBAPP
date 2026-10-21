# -*- coding: utf-8 -*-
"""
otonom/mikro_esitle.py — Mikro eşitlemesi, uygulama kapalıyken de (Ekim 2026)

Kullanıcı: "Her şey Mikro'dan, tam otomatik." Uygulama eşitlemeyi kendi içinde 5 dakikada bir yapıyor
(app.py:_mikro_esitle_dene), ama yalnız biri uygulamayı açıkken: kimse girmezse banka, satış, stok güncel
kalmıyordu (21.10: YKB USD düzeltmesi ancak biri uygulamayı açınca yazıldı). Bu betik aynı işleri GitHub
Actions'tan saatte bir çalıştırır (.github/workflows/mikro-esitle.yml). Hesap uygulamanın kendi
modüllerinden gelir; ekranla ayrışmaz. Her iş yalnız kullanıcı onayıyla açılmışsa çalışır (otomatik()
kapalıyken hiçbir şey yapmaz) ve yalnız aktarıcı yeni veri getirdiyse yazar.

Supabase erişimi: iş akışı .streamlit/secrets.toml yazar, uygulamanın get_client() fonksiyonu onu okur.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ISLER = (
    ("Aktarıcı kodu", "satis.mikro_esitle", "aktarici_yayinla"),
    ("Satış / iade", "satis.mikro_esitle", "otomatik"),
    ("Banka / çek / cari", "kayranacc.mikro_muhasebe", "otomatik"),
    ("Gider tablosu", "kayranacc.mikro_gider", "otomatik"),
    ("Depo stoğu", "kayranpm.mikro_stok", "otomatik"),
)


def calistir(isler=ISLER):
    """Her işi sırayla çalıştırır; biri çökerse diğerleri sürer. Döner: [(ad, sonuç metni)]."""
    import importlib
    out = []
    for ad, modul, fonk in isler:
        try:
            sonuc = getattr(importlib.import_module(modul), fonk)()
            out.append((ad, "yeni veri yok / kapalı" if sonuc is None else f"tamam: {sonuc}"))
        except Exception as e:  # noqa: BLE001
            out.append((ad, f"HATA {type(e).__name__}: {str(e)[:200]}"))
    return out


if __name__ == "__main__":
    for ad, metin in calistir():
        print(f"{ad}: {metin}")

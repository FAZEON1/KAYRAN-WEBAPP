# -*- coding: utf-8 -*-
"""
otonom/mikro_esitle.py — Mikro eşitlemesi, uygulama kapalıyken de (Ekim 2026)

Kullanıcı: "Her şey Mikro'dan, tam otomatik." Uygulama eşitlemeyi kendi içinde 5 dakikada bir yapıyor
(app.py:_mikro_esitle_dene), ama yalnız biri uygulamayı açıkken: kimse girmezse banka, satış, stok güncel
kalmıyordu (21.10: YKB USD düzeltmesi ancak biri uygulamayı açınca yazıldı). Bu betik aynı işleri GitHub
Actions'tan çalıştırır (.github/workflows/mikro-esitle.yml). Hesap uygulamanın kendi modüllerinden gelir;
ekranla ayrışmaz. Her iş yalnız kullanıcı onayıyla açılmışsa çalışır (otomatik() kapalıyken hiçbir şey
yapmaz) ve yalnız aktarıcı yeni veri getirdiyse yazar.

Ne zaman çalışır: aktarıcı yeni veri getirdiği turun sonunda Supabase fonksiyonu mikro-tetik üzerinden
(GitHub'ın zamanlanmış işleri saatlerce gecikiyor); aktarıcı durursa Supabase zamanlayıcısı tetikler.
Her turdan sonra sağlık denetimi (shared/mikro_saglik.py): günlüğe yazar, sorun varsa Telegram'a bildirir.

Supabase erişimi: iş akışı .streamlit/secrets.toml yazar, uygulamanın get_client() fonksiyonu onu okur.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ISLER = (
    ("Aktarıcı kodu", "satis.mikro_esitle", "aktarici_yayinla"),
    ("Satış / iade", "satis.mikro_esitle", "otomatik"),
    ("Banka / çek / cari", "kayranacc.mikro_muhasebe", "otomatik"),
    ("Haftalık ödeme listesi", "kayranacc.mikro_odeme_oto", "otomatik"),        # çekler eşitlendikten SONRA
    ("Gider tablosu", "kayranacc.mikro_gider", "otomatik"),
    ("Depo stoğu", "kayranpm.mikro_stok", "otomatik"),
    ("Toplam Aktifler stok değeri", "kayranacc.mikro_stok_degeri", "otomatik"),   # depo stoğundan SONRA
    ("Toplam Aktifler defter kalemleri", "kayranacc.mikro_aktif", "otomatik"),
    ("Toplam Aktifler sonucu", "kayranacc.toplam_aktif", "otomatik"),            # bütün kalemlerden SONRA
    ("Ürün kartları / fiyat listeleri", "kayranpm.mikro_urun", "otomatik"),
    ("İthalat dosyaları / masraflar", "ithalat.mikro_ithalat", "otomatik"),
)


class _Toplayici(logging.Handler):
    """İşlerin otomatik() içinde yuttuğu (shared.kayit.sessiz) uyarıları toplar: 21.10'da satış eşitlemesi
    "yeni veri yok" diyerek iki saat yazmadı, sebep yalnız günlükteki bir uyarı satırındaydı."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.kayitlar = []

    def emit(self, record):
        try:
            self.kayitlar.append(record.getMessage())
        except Exception:  # noqa: BLE001
            pass


def calistir(isler=ISLER):
    """Her işi sırayla çalıştırır; biri çökerse diğerleri sürer. Döner: [(ad, sonuç metni)].
    Metin: 'tamam: …' (yazdı), 'yeni veri yok / kapalı', 'UYARI …' (yazmadı, uyarı verdi), 'HATA …'."""
    import importlib
    out = []
    kok = logging.getLogger("kayran")
    for ad, modul, fonk in isler:
        t = _Toplayici()
        kok.addHandler(t)
        try:
            sonuc = getattr(importlib.import_module(modul), fonk)()
            if sonuc is not None:
                out.append((ad, f"tamam: {sonuc}"))
            elif t.kayitlar:
                out.append((ad, "UYARI " + " | ".join(t.kayitlar)[:300]))
            else:
                out.append((ad, "yeni veri yok / kapalı"))
        except Exception as e:  # noqa: BLE001
            out.append((ad, f"HATA {type(e).__name__}: {str(e)[:200]}"))
        finally:
            kok.removeHandler(t)
    return out


KILITLI = [("Eşitleme", "atlandı: başka bir eşitleme turu çalışıyor (kilit)")]


def tur(kaynak="github", isler=ISLER, gunluk_her_zaman=True):
    """Bir eşitleme turu + sağlık denetimi (günlük, Telegram). Döner: [(ad, metin)].
    Tur kilitlidir (shared/mikro_kilit): GitHub işi ile uygulamanın arka plan turu aynı anda çalışırsa ikincisi
    atlanır — aynı anda iki tur çek listesini iki katına çıkarabilir, satırı iki kez ekleyebilirdi (21.10 denetimi).
    gunluk_her_zaman=False (uygulamanın 5 dakikalık arka plan turu): günlüğe yalnız bir iş yazdıysa / uyardıysa /
    hata verdiyse yazılır (her 5 dakikada boş satır olmasın)."""
    from shared.mikro_kilit import tur_kilidi
    from shared.mikro_saglik import denetle_ve_bildir, is_durumu
    with tur_kilidi(kaynak) as alindi:
        if not alindi:
            return list(KILITLI)
        sonuc = calistir(isler)
    durumlar = [{"ad": ad, "durum": is_durumu(m), "metin": m} for ad, m in sonuc]
    if gunluk_her_zaman or any(d["durum"] != "yok" for d in durumlar):
        try:
            denetle_ve_bildir(durumlar, kaynak=kaynak)
        except Exception as e:  # noqa: BLE001
            print(f"Sağlık denetimi yapılamadı: {type(e).__name__}: {e}")
    return sonuc


if __name__ == "__main__":
    _kaynak = os.environ.get("ESITLE_KAYNAK") or "github"
    for ad, metin in tur(_kaynak):
        print(f"{ad}: {metin}")

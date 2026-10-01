# -*- coding: utf-8 -*-
"""Depo — saf hesaplar (Ekim 2026). Veritabanına gitmez, test edilir.

  sevk_sonucu     Toplu sevk sonuçları → başarılı sayısı + listede KALACAK kalemler
  fis_anahtari    Fiş No kutusunun anahtarı — her düşümden sonra yeni kutu
  bekleyen_ozet   (faturalanan, sevk edilen, bekleyen, oran)
  toplam_satiri   Ortak tablonun alt bilgiye sabitlediği "Σ Toplam" satırı
  tarih_tr        ISO → GG.AA.YYYY (kayranpm.urun_hesap ile aynı)
"""
from kayranpm.urun_hesap import tarih_tr  # noqa: F401  (tek tanım)


def sevk_sonucu(sepet, sonuclar):
    """sonuclar: sepetle aynı sırada [(ok, mesaj)]. Başarısız kalemler hata
    metniyle listede KALIR (eskiden liste koşulsuz boşaltılıyordu)."""
    ok = ok_adet = 0
    kalan, hatalar = [], []
    for kalem, (basarili, mesaj) in zip(sepet, sonuclar):
        if basarili:
            ok += 1
            ok_adet += int(kalem.get("adet") or 0)
        else:
            k = dict(kalem)
            k["hata"] = str(mesaj or "")
            kalan.append(k)
            hatalar.append((kalem.get("sku"), k["hata"]))
    return {"ok": ok, "ok_adet": ok_adet, "kalan": kalan, "hatalar": hatalar}


def fis_anahtari(kayit_id, hareketler):
    """Kutu hem key hem otomatik value alınca Streamlit value'yu ikinci kez
    uygulamıyordu: iki düşüm aynı fiş numarasını aldı (tarayıcıda görüldü).
    Anahtar hareket sayısına bağlı → her düşümden sonra yeni öneriyle yeni kutu."""
    return f"mt_d_fis_{kayit_id}_{len(hareketler or [])}"


def bekleyen_ozet(kayit):
    fa = int(kayit.get("fatura_adet") or 0)
    se = int(kayit.get("sevk_edilen") or 0)
    bek = max(0, fa - se)
    oran = (min(se, fa) / fa) if fa else 0.0
    return fa, se, bek, oran


def toplam_satiri(kolonlar, toplamlar, ozet=None):
    """İlk hücresi "Σ" ile başlayan satırı ortak tablo alt bilgiye sabitler, sıralamaya
    katmaz. "🧮 TOPLAM" sıradan satır sayılıyor, azalan sıralamada başa geçiyordu."""
    r = {k: "" for k in kolonlar}
    r[kolonlar[0]] = "Σ Toplam"
    r.update(ozet or {})
    r.update(toplamlar)
    return r

# -*- coding: utf-8 -*-
"""Depo — saf hesaplar (Ekim 2026). Veritabanına gitmez, test edilir.

  sevk_sonucu     Toplu sevk sonuçları → başarılı sayısı + listede KALACAK kalemler
  fis_anahtari    Fiş No kutusunun anahtarı — her düşümden sonra yeni kutu
  bekleyen_ozet   (faturalanan, sevk edilen, bekleyen, oran)
  toplam_satiri   Ortak tablonun alt bilgiye sabitlediği "Σ Toplam" satırı
  tarih_tr        ISO → GG.AA.YYYY (kayranpm.urun_hesap ile aynı)
  barkoddan_sku   Okutulan EAN → ürün kartının SKU'su (arama SKU / ad üzerinden çalışır)
"""
from kayranpm.urun_hesap import tarih_tr as _tarih_tr

tarih_tr = _tarih_tr   # tek tanım kayranpm.urun_hesap'ta; buradan da alınır (depo ekranları)


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


def barkoddan_sku(ara, barkod_map):
    """Arama metni bir ürün kartının barkoduysa (kameradan / el okuyucusundan EAN) o kartın SKU'su;
    değilse arama olduğu gibi. barkod_map: {sku: barkod} (ithalat.database.get_barkod_map)."""
    a = str(ara or "").strip()
    if not a:
        return ara
    for sku, bk in (barkod_map or {}).items():
        if bk and str(bk).strip() == a:
            return sku
    return ara


TUM_DEPOLAR = "Tüm depolar"


def tum_depo_stok(urunler, dagilim):
    """Talep #43 (Serkan, 22.10.2026): "Depo seçmeden tüm stokların olduğu ürün listesi gelsin; ürüne tıklayınca
    yanında tüm depoların stoklarını göstersin." urunler: [{sku, urun_adi, depo_kirilim}]; dagilim:
    kayranpm.database.depo_dagilimi (kanonik depo adı, sıfırlar atılır). Aynı SKU'nun yazım farkıyla iki kartı
    varsa (BÜYÜK + tek boşluk) tek satır olur — get_depo_stok ile aynı kural. Döner: [{sku, urun_adi, adet,
    depolar: [(depo, adet)] adede göre azalan}] (stoklu depo toplamı > 0 olanlar)."""
    birlesik, adlar = {}, {}
    for u in urunler or []:
        sku = " ".join(str(u.get("sku") or "").strip().upper().split())
        if not sku:
            continue
        if not adlar.get(sku):
            adlar[sku] = u.get("urun_adi") or ""
        d = birlesik.setdefault(sku, {})
        for depo, adet in dagilim(u.get("depo_kirilim"))[0]:
            d[depo] = d.get(depo, 0) + int(adet or 0)
    out = []
    for sku, d in birlesik.items():
        depolar = sorted(((k, a) for k, a in d.items() if a > 0), key=lambda x: (-x[1], x[0]))
        toplam = sum(a for _, a in depolar)
        if toplam > 0:
            out.append({"sku": sku, "urun_adi": adlar.get(sku, ""), "adet": toplam, "depolar": depolar})
    return sorted(out, key=lambda x: -x["adet"])

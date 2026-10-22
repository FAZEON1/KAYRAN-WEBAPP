# -*- coding: utf-8 -*-
"""Toplam Aktifler — hesap ve otomatik kayıt (Ekim 2026). Ekran: Yönetim panosu (yonetim.py) + ayrıntı
(kayranacc/toplam_aktif_ekran.py).

Kullanıcı (22.10.2026): "Toplam aktiflerden artık upload edilecek dosya olmadığı için muhasebe modülünden toplam
aktifleri kaldır." Bütün kalemler Mikro'dan ve uygulamanın kendi tablolarından geldiği için hesap artık bir sayfanın
açılmasını beklemez: her Mikro eşitleme turunda (otonom/mikro_esitle.py, defter kalemlerinden SONRA) hesaplanır ve
toplam değiştiyse ya da gün döndüyse "toplam_aktif_snapshot" kaydına yazılır. Yönetim panosu, patron paneli ve
Para haritası bu kaydı okur (değişmedi).

Formül eski Muhasebe › Toplam Aktifler sayfasının (kayranacc/main.py _sayfa_toplam_aktifler, silindi) birebir
aynısıdır; 22.10.2026'da canlı veriyle eski sayfanın son kaydıyla karşılaştırıldı: her kalem ve toplam (1.142.753,22 $)
kuruşu kuruşuna aynı.

  toplam = stok × çarpan + ithalat ödenen + banka (USD eşd.) + cari alacak + manuel ekleme
           − cari borç − çekler − manuel çıkarma
           + Mikro defter (+) − Mikro defter (−) − satış maliyeti

Eksik kaynak (stok, ithalat ya da cari kaydı yoksa) yazılmaz: panoda son tam hesap kalır (eski sayfanın kuralı).
Mikro'dan da gelen manuel kalem toplama girmez (kayranacc.mikro_aktif.manuel_cakisan).
"""
KAYIT_ANAHTAR = "toplam_aktif_snapshot"
KURUS = 0.005


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def stok_degeri(stok_kaydi):
    """aktif_excel 'stok' kaydı ([usd, {pazaryeri: usd}] ya da sayı) → depo stoğunun USD değeri (çarpansız)."""
    if isinstance(stok_kaydi, (list, tuple)) and stok_kaydi:
        return _f(stok_kaydi[0])
    return _f(stok_kaydi)


def cari_usd(cari, kur, eur_usd):
    """cari kaydı {"borc": {usd, tl, eur}, "alacak": {...}} → (borç $, alacak $). Eski üçlü biçim: yalnız borç."""
    if isinstance(cari, dict) and "borc" in cari:
        b, a = cari.get("borc") or {}, cari.get("alacak") or {}
    elif isinstance(cari, (list, tuple)) and len(cari) == 3:
        b, a = {"usd": cari[0], "tl": cari[1], "eur": cari[2]}, {}
    else:
        return 0.0, 0.0

    def _usd(d):
        tl, eur = _f(d.get("tl")), _f(d.get("eur"))
        return _f(d.get("usd")) + (tl / kur if kur > 0 else 0.0) + (eur * eur_usd if eur > 0 else 0.0)
    return _usd(b), _usd(a)


def banka_usd(bankalar, kur):
    """TL ve USD hesapların USD eşdeğeri (eski sayfa gibi: EUR hesap sayılmaz)."""
    tl = sum(_f(b.get("bakiye")) for b in bankalar or [] if b.get("para_birimi") == "TL")
    usd = sum(_f(b.get("bakiye")) for b in bankalar or [] if b.get("para_birimi") == "USD")
    return usd + (tl / kur if kur > 0 else 0.0)


def hesapla(g):
    """g: {stok, ithalat, cari, bankalar, cek (tl, usd), manuel [..], defter (mikro_defter kaydı ya da None),
    defter_acik, kur, eur_usd}. Döner: {toplam, kalemler…, eksik [ad], cakisan {id: kalem}}."""
    from kayranacc.mikro_aktif import manuel_cakisan, stok_carpani, usd_ozeti
    kur, eur = _f(g.get("kur")), _f(g.get("eur_usd"), 1.0)
    carpan = stok_carpani(bool(g.get("defter_acik")))
    stok = stok_degeri(g.get("stok")) * carpan
    ithalat = _f(g.get("ithalat"))
    banka = banka_usd(g.get("bankalar"), kur)
    borc, alacak = cari_usd(g.get("cari"), kur, eur)
    cek_tl, cek_usd = (g.get("cek") or (0.0, 0.0))[:2]
    cek = (_f(cek_tl) / kur if kur > 0 else 0.0) + _f(cek_usd)
    defter = g.get("defter") if g.get("defter_acik") else None
    ma = usd_ozeti(defter, kur, stok) if defter else {"arti": 0.0, "eksi": 0.0, "satis_maliyeti_usd": 0.0}
    cakisan = manuel_cakisan(g.get("manuel"), defter) if defter else {}
    ekle = cikar = 0.0
    for i, k in enumerate(g.get("manuel") or []):
        if k.get("id", i) in cakisan:
            continue
        t = _f(k.get("tutar"))
        t = t if str(k.get("para_birimi") or "USD").upper() == "USD" else (t / kur if kur > 0 else 0.0)
        if k.get("tip") == "ekle":
            ekle += t
        else:
            cikar += t
    toplam = (stok + ithalat + banka + alacak + ekle - borc - cek - cikar
              + ma["arti"] - ma["eksi"] - ma["satis_maliyeti_usd"])
    eksik = [ad for ad, v in (("Stok değeri", g.get("stok")), ("İthalat ödenen", g.get("ithalat")),
                              ("Cari", g.get("cari"))) if not v]
    return {"toplam": round(toplam, 2), "kur": kur, "stok": round(stok, 2), "ithalat": round(ithalat, 2),
            "banka": round(banka, 2), "alacak": round(alacak, 2), "borc": round(borc, 2), "cek": round(cek, 2),
            "manuel_ekle": round(ekle, 2), "manuel_cikar": round(cikar, 2), "havuz": 0.0,
            "defter_arti": round(ma["arti"], 2), "defter_eksi": round(ma["eksi"], 2),
            "satis_maliyeti": round(ma["satis_maliyeti_usd"], 2), "stok_carpan": carpan,
            "eksik": eksik, "cakisan": cakisan}


def kayit(sonuc, tarih):
    """Yönetim panosunun okuduğu kayıt (eski sayfanın yazdığı alanların aynısı + tarih)."""
    out = {k: v for k, v in sonuc.items() if k not in ("eksik", "cakisan")}
    out["tarih"] = str(tarih)
    return out


def yazilmali_mi(sonuc, eski, tarih):
    """Eksik kaynak varsa hayır; toplam ya da tarih değiştiyse evet."""
    if sonuc["eksik"]:
        return False
    eski = eski or {}
    return round(_f(eski.get("toplam")), 2) != sonuc["toplam"] or str(eski.get("tarih")) != str(tarih)


# ── Veritabanı ─────────────────────────────────────────────────────
def veri_oku():
    from kayranacc import database as db
    from kayranacc.mikro_aktif import acik_mi as defter_acik_mi, kayitli as defter_kayitli
    from shared.kur import eur_usd
    defter_acik = defter_acik_mi()
    return {"stok": db.aktif_excel_oku("ortak", "stok"), "ithalat": db.aktif_excel_oku("ortak", "ithalat"),
            "cari": db.aktif_excel_oku("ortak", "cari"), "bankalar": db.get_bankalar() or [],
            "cek": tuple((db.get_cek_toplamlari() or (0.0, 0.0))[:2]),
            "manuel": db.aktif_manuel_listele("ortak") or [],
            "defter": defter_kayitli() if defter_acik else None, "defter_acik": defter_acik,
            "kur": _f(db.get_kur()), "eur_usd": eur_usd()}


def guncelle(zorla=False):
    """Hesaplar; gerekiyorsa yazar. Döner: (sonuç, yazıldı mı). zorla: toplam aynı olsa da yazar (manuel kalem
    değişince kayıt anında)."""
    from kayranacc.database import get_ayar, set_ayar
    from shared.utils import tr_today
    g = veri_oku()
    if _f(g["kur"]) <= 0:
        raise RuntimeError("USD/TL kuru okunamadı")
    sonuc = hesapla(g)
    bugun = tr_today()
    if not (zorla and not sonuc["eksik"]) and not yazilmali_mi(sonuc, get_ayar(KAYIT_ANAHTAR, {}), bugun):
        return sonuc, False
    return sonuc, bool(set_ayar(KAYIT_ANAHTAR, kayit(sonuc, bugun)))


def otomatik():
    """Eşitleme turu (otonom/mikro_esitle.ISLER). Yazdıysa metin, yoksa None. Hata fırlatmaz."""
    try:
        sonuc, yazildi = guncelle()
        if sonuc["eksik"]:
            from shared.kayit import sessiz
            sessiz("kayranacc.toplam_aktif.otomatik", RuntimeError("eksik kaynak: " + ", ".join(sonuc["eksik"])))
            return None
        from shared.tasarim import tr_sayi
        return f"toplam aktifler ${tr_sayi(sonuc['toplam'], 0)}" if yazildi else None
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.toplam_aktif.otomatik", e)
        return None

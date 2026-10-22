# -*- coding: utf-8 -*-
"""Muhasebe liste sayfaları ORTAK LİSTE MASASINDA (shared/masa.py) — Ekim 2026, tüm program yeni tasarım.

Bu modül yalnız masaların TANIMINI (…_verisi) ve yürütücülerini (…_yurutucu) verir; ekranlar kendi
dosyalarında (odeme_ekran, gecmis_ekran, gelen_ekran, banka_ekran, cek_ekran). Tanımlar saf (Streamlit'e
gitmez); yürütücüler bugünkü veritabanı fonksiyonlarını AYNI argümanlarla çağırır
(kayranacc/database.py — iş kuralları değişmedi). Pencere açan işlemler ("ac") sayfanın verdiği açıcıyı
çağırır (B.detay_ac) ve sayfa masadan sonra bugünkü pencereyi açar.

  Ertelenen ödemeler  ertelenen_verisi · ertelenen_yurutucu   (ödeme işlemleri odeme_masasi'ndan)
  Bu hafta ödenenler  odenenler_verisi · odenenler_yurutucu   (geri al)
  Geçmiş haftalar     haftalar_verisi · haftalar_yurutucu     (ödemeleri göster · aktif yap · sil)
  Çek arşivi          cek_arsivi_verisi · cek_arsivi_yurutucu (sil)
  Gelenler geçmişi    gelenler_verisi · gelenler_yurutucu     (düzenle · geri al)
  Firma çekleri       firma_cekleri_verisi                     (salt okunur)
  Banka bakiyeleri    banka_verisi · banka_yurutucu            (satıra tıkla → hesap penceresi)

Rakamlar eski ekranlarla aynı fonksiyonlardan (cek_tutarlari, get_hafta_ozet, banka_ozet_kalemleri …);
özet bandında 1.000 ve üstü kuruşsuz (shared.tasarim.kart_degeri_kisa), satırda tam tutar.
Geri almak için her sayfanın kendi bayrağı (…_MASASI_YENI = False): eski ekran aynen duruyor.
"""
import re
from datetime import date

from . import odeme_hesap as H

SEMBOL = {"TL": "₺", "TRY": "₺", "USD": "$", "EUR": "€"}
_AC = {"ok": True, "yenileme": False, "sessiz": True}        # pencere açıldı: sayfa aynı çalıştırmada devam


# ── Biçim ───────────────────────────────────────────────────────────
def _tr(v, ondalik=2):
    from shared.tasarim import tr_sayi
    return tr_sayi(v, ondalik)


def _kisa(metin):
    """Büyük özet rakamı: 1.000 ve üstünde kuruşsuz (kartlarla aynı kural)."""
    from shared.tasarim import kart_degeri_kisa
    return kart_degeri_kisa(metin)[0]


def _tam(metin):
    """Kısaltılan özet rakamının tam hâli (ipucu)."""
    from shared.tasarim import kart_degeri_kisa
    return kart_degeri_kisa(metin)[1] or ""


def _tl(v):
    return f"₺{_tr(H._f(v), 2)}"


def _usd(v):
    return f"${_tr(H._f(v), 2)}"


def _para(v, pb):
    """Gelenler ekranındaki biçim: '₺1.234,56' (sembol başta, kendi para biriminde)."""
    return f"{SEMBOL.get(pb or 'TL', '')}{_tr(H._f(v), 2)}"


def _bakiye(v, pb):
    """Banka ekranındaki biçim: eksi işaret sembolden önce ('-₺1.234,56')."""
    f = H._f(v)
    return f"{'-' if f < 0 else ''}{SEMBOL.get(pb, '')}{_tr(abs(f), 2)}"


def _tutar(o):
    p = [x for x in (_tl(o.get("tutar_tl")) if H._f(o.get("tutar_tl")) else "",
                     _usd(o.get("tutar_usd")) if H._f(o.get("tutar_usd")) else "") if x]
    return " + ".join(p) or "—"


def gun_ay_yil(v):
    """'2026-09-30' → '30.09.2026' (gecmis_ekran ile aynı)."""
    t = str(v or "")[:10]
    return f"{t[8:10]}.{t[5:7]}.{t[:4]}" if len(t) == 10 and t[4] == "-" else (t or "—")


def _temiz_mesaj(m):
    """Veritabanı mesajının başındaki simge (onay işareti vb.) bildirimde gösterilmez."""
    return re.sub(r"^[^\w(\"']+", "", str(m or "")).strip() or "Tamam"


def _ozet_karti(k, et, deger, renk="", al="", suz=None, nokta=True):
    d = {"k": k, "et": et, "dg": _kisa(deger), "renk": renk, "al": al, "ipucu": _tam(deger)}
    if suz:
        d["suz"] = suz
    if not nokta:
        d["nokta"] = False
    return d


def yalniz_okuma(veri, mikro):
    """Mikro kaynaklı listede elle işlem yok (kullanıcı, 22.10.2026: "datalar Mikro'dan gelecekse bu gibi her şeyi
    kaldır"): mikro True ise yalnız okuma işlemleri kalır (ör. "Ödemeleri göster"). Satır seçimi de kalkar."""
    if mikro:
        veri = dict(veri, islemler=[i for i in veri.get("islemler") or [] if i.get("okuma")])
    return veri


def _ilk(temiz):
    return temiz["ids"][0], temiz["satirlar"][0]


# ════════════════════════════════════════════════════════════════════
# ERTELENEN ÖDEMELER — ödeme işlemleri Bu hafta masasıyla aynı (kayranacc/odeme_masasi)
# ════════════════════════════════════════════════════════════════════
def ertelenen_verisi(liste, bankalar, kategoriler, kur, bugun, salt=False, mikro_idler=None):
    """Satırlar odeme_masasi.masa_verisi'nden (aynı alanlar, aynı işlemler: öde / kısmi öde / ötele /
    düzenle / sil / geri al); üstüne erteleme bilgisi. Sıra eski ekranla aynı: önce bekleyenler, vadeye göre.
    mikro_idler: Mikro'dan gelen satırlar — Bu hafta gibi yalnız ötele (mikro_odeme_oto.mikro_idleri_tum)."""
    from . import odeme_masasi as OM
    v = OM.masa_verisi(liste or [], bankalar or [], kategoriler or {}, kur, bugun, salt=salt, mikro_idler=mikro_idler)
    satir = {s["id"]: s for s in v["satirlar"]}
    satirlar = []
    for o in sorted(liste or [], key=lambda x: (H.odendi_mi(x), str(x.get("vade") or ""))):
        s = dict(satir[o.get("id")])
        ilk, simdi = H._tarih(o.get("orijinal_vade")), H._tarih(o.get("vade"))
        kez = int(o.get("ertelendi_sayisi") or 1)
        kayma = (simdi - ilk).days if ilk and simdi else None
        s.update({
            "kez": kez, "kez_m": f"{kez}× ertelendi", "kez_m__s": kez,
            "simdi_m": f"{simdi:%d.%m.%Y}" if simdi else "—", "simdi_m__s": simdi.isoformat() if simdi else "9999",
            "ilk_m": f"ilk {ilk:%d.%m.%Y}" if ilk else "", "kayma": kayma,
            "firma_alt": " · ".join(x for x in (f"ilk vade {ilk:%d.%m.%Y}" if ilk else "",
                                                 f"{kayma} gün kaydı" if kayma is not None else "", s["kat_ad"]) if x),
            "_detay": [["İlk vade", f"{ilk:%d.%m.%Y}" if ilk else "—"],
                       ["Şimdiki vade", H.gun_basligi(o.get("vade"), bugun)],
                       ["Kayma", f"{kayma} gün" if kayma is not None else "—"],
                       ["Ertelenme", f"{kez} kez"]] + [d for d in s["_detay"] if d[0] != "Vade"],
        })
        satirlar.append(s)
    bek = [o for o in liste or [] if not H.odendi_mi(o)]
    btl = sum(H._f(o.get("tutar_tl")) for o in bek)
    busd = sum(H._f(o.get("tutar_usd")) for o in bek)
    en_cok = max((int(o.get("ertelendi_sayisi") or 1) for o in liste), default=0) if liste else 0
    ozet = [
        {"k": "ert", "et": "Ertelenmiş", "dg": f"{len(liste or [])} ödeme", "renk": "amber", "suz": "tum",
         "al": f"{len(bek)} hâlâ bekliyor"},
        _ozet_karti("bek", "Bekleyen tutar", _tl(btl), al=f"+ {_usd(busd)}" if busd else "", suz="bekleyen"),
        {"k": "en_cok", "et": "En çok ertelenen", "dg": f"{en_cok} kez", "renk": ""},
    ]
    bekler = [["durum", "ne", "odendi"]]
    return dict(v, **{
        "ozet": ozet,
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []},
                       {"k": "bekleyen", "ad": "Bekleyen", "f": bekler},
                       {"k": "gecikmis", "ad": "Gecikmiş", "f": [["durum", "eq", "gecikmis"]]},
                       {"k": "odendi", "ad": "Ödendi", "f": [["durum", "eq", "odendi"]]}],
        "sutunlar": [
            {"alan": "simdi_m", "ad": "Vade", "tip": "metin", "alt": "vade_alt", "alt_renk": "vade_renk", "gen": "104px",
             "dar": "alt"},
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "firma_alt"},
            {"alan": "kez_m", "ad": "Erteleme", "tip": "etiket", "gen": "112px", "genis": True},
            {"alan": "tl_m", "ad": "TL", "sag": True, "gen": "124px", "dar": "sag"},
            {"alan": "usd_m", "ad": "USD", "sag": True, "gen": "104px", "genis": True},
            {"alan": "durum", "ad": "Durum", "tip": "durum", "gen": "116px"},
        ],
        "grup": None,
        "satirlar": satirlar,
        "bos": {"liste": "Ertelenmiş ödeme yok.", "suzgec": "Bu süzgece uyan ertelenmiş ödeme yok."},
        "baslik_ipucu": "Ertelenen ödemeler",
    })


def ertelenen_yurutucu(liste, bankalar, kategoriler, kur, bugun, salt=False, mikro_idler=None):
    """Bu hafta masasının yürütücüsü (istek_coz + islem_uygula) bu listeyle — aynı veritabanı çağrıları."""
    from . import odeme_masasi as OM
    return OM.yurutucu(liste or [], bankalar or [], kategoriler or {}, kur, bugun, salt=salt, mikro_idler=mikro_idler)


# ════════════════════════════════════════════════════════════════════
# ÖDENENLER & GEÇMİŞ › Bu hafta ödenenler
# ════════════════════════════════════════════════════════════════════
def odenenler_verisi(odemeler, bankalar, bugun, salt=False):
    """Bu haftanın ödenmiş ödemeleri, ödeme gününe göre gruplu (yeni → eski) — eski ekranla aynı."""
    od = [o for o in odemeler or [] if o.get("durum") == "odendi"]
    bmap = {b.get("id"): b.get("hesap_adi") for b in bankalar or []}
    satirlar = []
    for o in sorted(od, key=lambda o: str(o.get("odendi_tarih") or o.get("vade") or ""), reverse=True):
        gun = str(o.get("odendi_tarih") or o.get("vade") or "")[:10]
        kat = H.KATEGORI_AD.get(o.get("kategori") or "diger", "Diğer")
        tl, usd = H._f(o.get("tutar_tl")), H._f(o.get("tutar_usd"))
        firma = str(o.get("firma") or "").strip() or "—"
        banka = bmap.get(o.get("banka_id")) or ""
        satirlar.append({
            "id": o.get("id"), "firma": firma, "ack": str(o.get("aciklama") or "").strip()[:60], "kat_ad": kat,
            "banka": banka or "banka seçilmemiş", "gun": H.gun_basligi(gun, bugun) if gun else "Tarihsiz",
            "vade_m": gun_ay_yil(o.get("vade")), "vade_m__s": str(o.get("vade") or "")[:10],
            "tl": tl, "usd": usd, "tl_m": _tl(tl) if tl else "", "usd_m": _usd(usd) if usd else "",
            "tl_m__s": tl, "usd_m__s": usd,
            "_durum": {"ad": "Ödendi", "renk": "yesil"}, "_baslik": firma, "_alt": str(o.get("aciklama") or "").strip(),
            "_buyuk": _tutar(o),
            "_detay": [["Açıklama", o.get("aciklama") or "—"],
                       ["Kategori", H.KATEGORI_AD.get(o.get("kategori") or "diger") or "—"],
                       ["Vade", gun_ay_yil(o.get("vade"))], ["Ödendi", gun_ay_yil(o.get("odendi_tarih"))],
                       ["Banka", banka or "—"]],
        })
    ttl = sum(H._f(o.get("tutar_tl")) for o in od)
    tusd = sum(H._f(o.get("tutar_usd")) for o in od)
    return {
        "ozet": [_ozet_karti("tl", "Ödenen TL", _tl(ttl), "yesil"),
                 _ozet_karti("usd", "Ödenen USD", _usd(tusd), "cyan"),
                 {"k": "adet", "et": "Ödeme", "dg": _tr(len(od), 0), "renk": "",
                  "al": f"{len(odemeler or [])} ödemeden"}],
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}],
        "secimler": [{"alan": "kat_ad", "ad": "Tüm kategoriler",
                      "secenekler": [{"k": k, "ad": k} for k in sorted({s["kat_ad"] for s in satirlar})]},
                     {"alan": "banka", "ad": "Tüm bankalar",
                      "secenekler": [{"k": k, "ad": k} for k in sorted({s["banka"] for s in satirlar})]}],
        "anahtarlar": [],
        "ara": {"alanlar": ["firma", "ack", "kat_ad", "banka", "tl_m", "usd_m"], "ipucu": "Firma, açıklama, banka, tutar"},
        "sutunlar": [
            {"alan": "vade_m", "ad": "Vade", "tip": "metin", "gen": "104px", "dar": "alt"},
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "ack"},
            {"alan": "kat_ad", "ad": "Kategori", "tip": "etiket", "gen": "110px", "genis": True},
            {"alan": "banka", "ad": "Banka", "tip": "metin", "gen": "150px", "genis": True},
            {"alan": "tl_m", "ad": "TL", "sag": True, "gen": "124px", "dar": "sag"},
            {"alan": "usd_m", "ad": "USD", "sag": True, "gen": "104px", "genis": True},
        ],
        "grup": {"alan": "gun", "birim": "ödeme", "toplamlar": [{"alan": "tl", "on": "₺"}, {"alan": "usd", "on": "$"}]},
        "satirlar": satirlar,
        "islemler": [{"k": "geri_al", "ad": "Geri al", "dugme": "Geri al (bekliyor yap)",
                      "ipucu": "Geri alınca ödeme yeniden 'bekliyor' olur; ödendiği bankanın bakiyesine tutar iade edilir."}],
        "bos": {"liste": "Bu hafta henüz ödenen yok.", "suzgec": "Bu süzgece uyan ödeme yok."},
        "baslik_ipucu": "Bu hafta ödenenler", "salt": bool(salt),
    }


def odenenler_yurutucu():
    """Geri al: eski penceredeki çağrının aynısı — odeme_durum_guncelle(id, 'bekliyor', kur=get_kur())."""
    def yurut(temiz):
        from . import database as D
        i, s = _ilk(temiz)
        if temiz["islem"] != "geri_al":
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        D.odeme_durum_guncelle(i, "bekliyor", kur=D.get_kur())
        return {"ok": True, "mesaj": f"{s.get('_baslik')} ödemesi geri alındı"}
    return yurut


# ════════════════════════════════════════════════════════════════════
# ÖDENENLER & GEÇMİŞ › Geçmiş haftalar
# ════════════════════════════════════════════════════════════════════
def haftalar_verisi(haftalar, ozetler, aktif_id, salt=False):
    """haftalar: get_tum_haftalar() (yeni → eski) · ozetler: {hafta_id: get_hafta_ozet(id)}."""
    satirlar = []
    for h in haftalar or []:
        oz = (ozetler or {}).get(h.get("id")) or {"toplam": 0, "odendi": 0, "tl_toplam": 0, "usd_toplam": 0}
        oran = (oz["odendi"] / oz["toplam"]) if oz["toplam"] else 0
        aktif = h.get("id") == aktif_id
        ad = str(h.get("hafta_adi") or "").strip() or "—"
        yuk = str(h.get("yuklendi_tarih") or "—")
        satirlar.append({
            "id": h.get("id"), "ad": ad, "yuklendi": f"yüklendi {yuk}", "aktif": aktif,
            "odendi_m": f"{oz['odendi']}/{oz['toplam']} ödendi", "odendi_m__s": oran,
            "oran_m": f"%{_tr(oran * 100, 0)}", "toplam": oz["toplam"],
            "tl": H._f(oz["tl_toplam"]), "usd": H._f(oz["usd_toplam"]),
            "tl_m": _tl(oz["tl_toplam"]), "usd_m": _usd(oz["usd_toplam"]),
            "tl_m__s": H._f(oz["tl_toplam"]), "usd_m__s": H._f(oz["usd_toplam"]),
            "_durum": {"ad": "Aktif", "renk": "mor"} if aktif else {},
            "_baslik": ad, "_alt": f"yüklendi {yuk}",
            "_buyuk": _tl(oz["tl_toplam"]), "_buyuk_alt": f"+ {_usd(oz['usd_toplam'])}",
            "_detay": [["Ödeme", f"{oz['toplam']} ödeme"], ["Ödendi", f"{oz['odendi']}/{oz['toplam']}"],
                       ["Yüklendi", yuk], ["Durum", "Aktif hafta" if aktif else "Geçmiş hafta"]],
        })
    return {
        "ozet": [],
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}],
        "ara": {"alanlar": ["ad", "yuklendi", "tl_m", "usd_m"], "ipucu": "Hafta adı ya da tutar"},
        "sutunlar": [
            {"alan": "ad", "ad": "Hafta", "tip": "ana", "alt": "yuklendi"},
            {"alan": "odendi_m", "ad": "Ödendi", "tip": "metin", "alt": "oran_m", "gen": "120px", "dar": "alt"},
            {"alan": "tl_m", "ad": "TL", "sag": True, "gen": "140px", "dar": "sag"},
            {"alan": "usd_m", "ad": "USD", "sag": True, "gen": "120px", "genis": True},
            {"alan": "aktif", "ad": "Durum", "tip": "durum", "gen": "96px"},
        ],
        "satirlar": satirlar,
        "islemler": [
            {"k": "ac", "ad": "Ödemeleri göster", "dugme": "Ödemeleri göster", "okuma": True, "birincil": True},
            {"k": "aktif_yap", "ad": "Bu haftayı aktif yap", "dugme": "Bu haftayı aktif yap",
             "f": [["aktif", "eq", False]]},
            {"k": "sil", "ad": "Haftayı sil", "dugme": "Haftayı sil", "tehlike": True,
             "ipucu": "Hafta, içindeki bütün ödemelerle birlikte kalıcı olarak silinir. Ödendi işaretlenmiş "
                      "ödemelerin banka hareketleri geri alınmaz.",
             "alanlar": [{"ad": "onay", "et": "Evet, '{baslik}' haftasını bütün ödemeleriyle sil", "tip": "onay",
                          "zorunlu": True}]},
        ],
        "bos": {"liste": "Henüz hafta yok.", "suzgec": "Aramaya uyan hafta yok."},
        "baslik_ipucu": "Geçmiş haftalar", "salt": bool(salt),
    }


def haftalar_yurutucu(ac):
    """ac(hafta_id): sayfanın pencere açıcısı (B.detay_ac('gech', id)) — bugünkü hafta penceresi açılır."""
    def yurut(temiz):
        from . import database as D
        i, s = _ilk(temiz)
        if temiz["islem"] == "ac":
            ac(i)
            return dict(_AC)
        if temiz["islem"] == "aktif_yap":
            D.hafta_aktif_yap(i)
            return {"ok": True, "mesaj": f"'{s.get('_baslik')}' aktif yapıldı"}
        if temiz["islem"] == "sil":
            D.hafta_sil(i)
            return {"ok": True, "mesaj": "Hafta silindi"}
        return {"ok": False, "mesaj": "Bilinmeyen işlem."}
    return yurut


# ════════════════════════════════════════════════════════════════════
# ÖDENENLER & GEÇMİŞ › Çek arşivi
# ════════════════════════════════════════════════════════════════════
def _cek_renk(c, ct):
    from .database import cek_durum_norm
    return "yesil" if ct["odendi"] else ("cyan" if "ciro" in cek_durum_norm(c.get("durum") or "Bekliyor") else "amber")


def cek_arsivi_verisi(cekler, pb, salt=False):
    """Çek arşivi (TL ya da USD). Tutarlar cek_tutarlari'ndan (Firma çekleriyle aynı kural)."""
    from .database import cek_tutarlari
    sym = SEMBOL.get(pb, "")
    satirlar = []
    for c in sorted(cekler or [], key=lambda c: str(c.get("vade") or ""), reverse=True):
        ct = cek_tutarlari(c)
        durum = c.get("durum") or "Bekliyor"
        firma = str(c.get("ch_ismi") or "").strip() or "—"
        ref = str(c.get("ref_no") or "")
        satirlar.append({
            "id": c.get("id"), "firma": firma, "cek_no": str(c.get("cek_no") or "—"), "ref_no": ref,
            "banka": str(c.get("banka") or ""), "durum_ad": durum,
            "alt": " · ".join(x for x in (str(c.get("banka") or ""), f"ref {ref}" if ref else "") if x),
            "vade_m": gun_ay_yil(c.get("vade")), "vade_m__s": str(c.get("vade") or "")[:10],
            "no_m": f"no {c.get('cek_no') or '—'}",
            "meblag": ct["meblag"], "kalan": ct["kalan"], "odendi": ct["odendi"],
            "meblag_m": f"{sym}{_tr(ct['meblag'], 2)}", "meblag_m__s": ct["meblag"],
            "kalan_m": f"{sym}{_tr(ct['kalan'], 2)}" if ct["kalan"] else "kapandı", "kalan_m__s": ct["kalan"],
            "_durum": {"ad": durum, "renk": _cek_renk(c, ct)},
            "_baslik": firma, "_alt": f"vade {gun_ay_yil(c.get('vade'))}",
            "_buyuk": f"{sym}{_tr(ct['meblag'], 2)}",
            "_detay": [["Çek no", c.get("cek_no") or "—"], ["Ref no", c.get("ref_no") or "—"],
                       ["Banka", c.get("banka") or "—"], ["Vade", gun_ay_yil(c.get("vade"))], ["Durum", durum],
                       ["Ödenen", f"{sym}{_tr(ct['odenen'], 2)}"], ["Kalan", f"{sym}{_tr(ct['kalan'], 2)}"]],
        })
    t = [(s["meblag"], s["kalan"], s["odendi"]) for s in satirlar]
    return {
        "ozet": [{"k": "adet", "et": "Çek", "dg": _tr(len(t), 0), "renk": "", "suz": "tum",
                  "al": f"{sum(1 for x in t if x[2])} ödendi"},
                 _ozet_karti("meblag", "Toplam meblağ", f"{sym}{_tr(sum(x[0] for x in t), 2)}", "cyan"),
                 _ozet_karti("kalan", "Kalan", f"{sym}{_tr(sum(x[1] for x in t), 2)}", "amber", suz="acik")],
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []},
                       {"k": "acik", "ad": "Kalanı olan", "f": [["kalan", "gt", 0]]},
                       {"k": "odendi", "ad": "Ödendi", "f": [["odendi", "eq", True]]}],
        "secimler": [{"alan": "durum_ad", "ad": "Tüm durumlar",
                      "secenekler": [{"k": k, "ad": k} for k in sorted({s["durum_ad"] for s in satirlar})]}],
        "ara": {"alanlar": ["firma", "cek_no", "ref_no", "banka", "meblag_m"], "ipucu": "Firma, çek no, ref no, banka…"},
        "sutunlar": [
            {"alan": "vade_m", "ad": "Vade", "tip": "metin", "alt": "no_m", "gen": "112px", "dar": "alt"},
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "alt"},
            {"alan": "durum_ad", "ad": "Durum", "tip": "durum", "gen": "130px"},
            {"alan": "meblag_m", "ad": "Meblağ", "sag": True, "gen": "136px", "dar": "sag"},
            {"alan": "kalan_m", "ad": "Kalan", "sag": True, "gen": "136px", "genis": True},
        ],
        "satirlar": satirlar,
        "islemler": [{"k": "sil", "ad": "Çeki sil", "dugme": "Çeki sil", "tehlike": True,
                      "alanlar": [{"ad": "onay", "et": "Evet, bu çeki sil", "tip": "onay", "zorunlu": True}]}],
        "bos": {"liste": f"Kayıtlı {pb} çeki yok.", "suzgec": "Bu süzgece uyan çek yok."},
        "baslik_ipucu": f"{pb} çek arşivi", "salt": bool(salt),
    }


def cek_arsivi_yurutucu():
    def yurut(temiz):
        from . import database as D
        i, _s = _ilk(temiz)
        if temiz["islem"] != "sil":
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        D.cek_sil(i)
        return {"ok": True, "mesaj": "Çek silindi"}
    return yurut


# ════════════════════════════════════════════════════════════════════
# GELENLER GEÇMİŞİ (tahsilatlar)
# ════════════════════════════════════════════════════════════════════
def _gun(iso):
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{d.day} {H.AY[d.month]}, {H.GUN_KISA[d.weekday()]}"
    except ValueError:
        return "Tarihsiz"


def _ay(iso):
    ay = str(iso or "")[:7]
    try:
        return f"{H.AY[int(ay[5:7])]} {ay[:4]}"
    except (ValueError, IndexError):
        return "Tarihsiz"


def kimden_ne_kadar(kayit):
    """'Kimden ne kadar' özeti (döviz ayrı ayrı), büyükten küçüğe — gelen_ekran ile aynı sıra kuralı."""
    oz = {}
    for t in kayit or []:
        k = (t.get("kaynak") or "—").strip() or "—"
        pb = t.get("para_birimi") or "TL"
        oz.setdefault(k, {}).setdefault(pb, 0.0)
        oz[k][pb] += H._f(t.get("tutar"))
    return sorted(oz.items(), key=lambda kv: -(kv[1].get("TL", 0) + kv[1].get("USD", 0) * 40 + kv[1].get("EUR", 0) * 44))


def gelenler_verisi(kayit, bankalar, salt=False):
    """Para girişleri, aya göre gruplu (yeni → eski); her giriş kendi para birimiyle."""
    satirlar = []
    for t in sorted(kayit or [], key=lambda t: (str(t.get("tarih") or ""), t.get("id") or 0), reverse=True):
        pb = t.get("para_birimi") or "TL"
        tutar = H._f(t.get("tutar"))
        kaynak = (t.get("kaynak") or "").strip()
        tarih = str(t.get("tarih") or "")[:10]
        satirlar.append({
            "id": t.get("id"), "kaynak": kaynak or "—", "kaynak_k": kaynak, "kaynak_ham": t.get("kaynak") or "",
            "ack": (t.get("aciklama") or "").strip(), "banka": t.get("hesap_adi") or "—", "banka_id": t.get("banka_id"),
            "pb": pb, "tutar": tutar, "tutar_ham": str(t.get("tutar") if t.get("tutar") is not None else ""),
            "tutar_m": _para(tutar, pb), "tutar_m__s": tutar,
            "tl": tutar if pb == "TL" else 0.0, "usd": tutar if pb == "USD" else 0.0, "eur": tutar if pb == "EUR" else 0.0,
            "tarih": tarih, "gun_m": _gun(t.get("tarih")), "gun_m__s": tarih, "ay": _ay(t.get("tarih")),
            "_baslik": kaynak or "—", "_alt": t.get("hesap_adi") or "", "_buyuk": _para(tutar, pb),
            "_detay": [["Tarih", tarih], ["Banka", t.get("hesap_adi") or "—"], ["Döviz", pb],
                       ["Açıklama", t.get("aciklama") or "—"]],
        })
    top = {pb: sum(s["tutar"] for s in satirlar if s["pb"] == pb) for pb in ("TL", "USD", "EUR")}
    ozet = [_ozet_karti("tl", "Gelen TL", _para(top["TL"], "TL"), "yesil"),
            _ozet_karti("usd", "Gelen USD", _para(top["USD"], "USD"), "cyan")]
    if top["EUR"]:
        ozet.append(_ozet_karti("eur", "Gelen EUR", _para(top["EUR"], "EUR"), "cyan"))
    ozet.append({"k": "adet", "et": "Giriş", "dg": _tr(len(satirlar), 0), "renk": "",
                 "al": f"{len({(t.get('kaynak') or '').strip() for t in kayit or []})} kaynak"})
    islemler = []
    if bankalar:
        islemler.append({
            "k": "duzenle", "ad": "Düzenle", "dugme": "Değişiklikleri kaydet",
            "ipucu": "Girişi silmeden düzeltir. Banka ya da tutar değişirse banka bakiyeleri farkla düzeltilir.",
            "alanlar": [{"ad": "banka", "et": "Banka", "tip": "secim", "zorunlu": True, "tam": True,
                         "varsayilan_alan": "banka_id", "bos": "Banka seç…",
                         "secenekler": [{"k": b.get("id"), "ad": f"{b.get('hesap_adi') or '—'} ({b.get('para_birimi') or 'TL'})"}
                                        for b in bankalar]},
                        {"ad": "tutar", "et": "Tutar", "tip": "sayi", "zorunlu": True, "varsayilan_alan": "tutar"},
                        {"ad": "tarih", "et": "Tarih", "tip": "tarih", "varsayilan_alan": "tarih"},
                        {"ad": "kaynak", "et": "Kimden / Kaynak", "tip": "metin", "varsayilan_alan": "kaynak_ham"},
                        {"ad": "aciklama", "et": "Açıklama", "tip": "metin", "varsayilan_alan": "ack"}]})
    islemler.append({"k": "geri_al", "ad": "Geri al", "dugme": "Girişi geri al", "tehlike": True,
                     "ipucu": "Kayıt silinir ve tutar banka bakiyesinden düşülür (yanlış girilmiş tahsilat için).",
                     "alanlar": [{"ad": "onay", "et": "Evet, bu girişi geri al", "tip": "onay", "zorunlu": True}]})
    return {
        "ozet": ozet,
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}],
        "secimler": [{"alan": "kaynak_k", "ad": "Tüm kaynaklar",
                      "secenekler": [{"k": k, "ad": k} for k in sorted({s["kaynak_k"] for s in satirlar if s["kaynak_k"]})]},
                     {"alan": "banka", "ad": "Tüm bankalar",
                      "secenekler": [{"k": k, "ad": k} for k in sorted({s["banka"] for s in satirlar})]},
                     {"alan": "pb", "ad": "Tüm dövizler",
                      "secenekler": [{"k": k, "ad": k} for k in ("TL", "USD", "EUR")]}],
        "ara": {"alanlar": ["kaynak", "ack", "banka", "tutar_ham", "tutar_m"], "ipucu": "Kimden, açıklama, banka, tutar…"},
        "sutunlar": [
            {"alan": "gun_m", "ad": "Tarih", "tip": "metin", "gen": "116px", "dar": "alt"},
            {"alan": "kaynak", "ad": "Kimden", "tip": "ana", "alt": "ack"},
            {"alan": "banka", "ad": "Banka", "tip": "metin", "gen": "170px", "genis": True},
            {"alan": "tutar_m", "ad": "Tutar", "sag": True, "alt": "pb", "gen": "140px", "dar": "sag"},
        ],
        "grup": {"alan": "ay", "birim": "giriş",
                 "toplamlar": [{"alan": "tl", "on": "₺"}, {"alan": "usd", "on": "$"}, {"alan": "eur", "on": "€"}]},
        "satirlar": satirlar,
        "islemler": islemler,
        "bos": {"liste": "Henüz para girişi yok.", "suzgec": "Filtreye uyan giriş yok."},
        "baslik_ipucu": "Para girişleri", "salt": bool(salt),
    }


def gelenler_yurutucu(bankalar=None):
    """Düzenle: tahsilat_guncelle(id, banka, tutar, kaynak, açıklama, tarih) · Geri al: tahsilat_geri_al(id)
    — eski penceredeki çağrıların aynısı (bakiye düzeltmesi veritabanı fonksiyonunda)."""
    def yurut(temiz):
        from . import database as D
        i, s = _ilk(temiz)
        d = temiz["degerler"]
        if temiz["islem"] == "duzenle":
            tarih = d.get("tarih")
            if tarih is None:
                try:
                    tarih = date.fromisoformat(str(s.get("tarih") or "")[:10])
                except ValueError:
                    tarih = date.today()
            bid, tutar = d["banka"], d["tutar"]
            ok, msg = D.tahsilat_guncelle(i, bid, tutar, str(d.get("kaynak") or "").strip(),
                                          str(d.get("aciklama") or "").strip(), tarih)
            if ok:
                fark = D.tahsilat_bakiye_farki(s.get("banka_id"), s.get("tutar"), bid, tutar)
                if fark:
                    ad = {b.get("id"): (b.get("hesap_adi") or "—", b.get("para_birimi") or "TL") for b in bankalar or []}
                    msg += " · " + " · ".join(
                        f"{ad.get(k, (k, 'TL'))[0]} {'+' if v > 0 else '−'}{_para(abs(v), ad.get(k, (k, 'TL'))[1])}"
                        for k, v in fark.items())
            return {"ok": bool(ok), "mesaj": _temiz_mesaj(msg)}
        if temiz["islem"] == "geri_al":
            ok, msg = D.tahsilat_geri_al(i)
            return {"ok": bool(ok), "mesaj": _temiz_mesaj(msg)}
        return {"ok": False, "mesaj": "Bilinmeyen işlem."}
    return yurut


# ════════════════════════════════════════════════════════════════════
# FİRMA ÇEKLERİ (salt okunur)
# ════════════════════════════════════════════════════════════════════
def _vade_durumu(v, bugun):
    """main.vade_durumu ile aynı kural: 'gecmis' | 'bugun' | 'yarin' | 'normal'."""
    d = H._tarih(v)
    if d is None:
        return "normal"
    from datetime import timedelta
    return "gecmis" if d < bugun else "bugun" if d == bugun else "yarin" if d == bugun + timedelta(days=1) else "normal"


def _tarih_m(s):
    """main.fmt_tarih gibi: 'YYYY-MM-DD…' → 'GG.AA.YYYY'; boşsa ''."""
    if not s:
        return ""
    d = H._tarih(s)
    return f"{d:%d.%m.%Y}" if d else str(s)


def _cek_rozet(pozisyon, ham):
    """main.cek_tablo._durum_rozet ile aynı karar (simgesiz)."""
    if pozisyon == "odendi":
        return {"ad": "Ödendi", "renk": "yesil"}
    if "bekliyor" in pozisyon:
        return {"ad": "Bekliyor", "renk": "amber"}
    if "gecmis" in pozisyon:
        return {"ad": "Gecikmiş", "renk": "kirmizi"}
    return {"ad": ham or "—", "renk": "soluk"}


def firma_cekleri_verisi(cekler, pb, bugun):
    """Firma çekleri (TL ya da USD) — eski tablonun sütunları, özet kartları ve satır renk kuralı
    (ödendi yeşil · vadesi geçmiş kalanlı kırmızı · bugün vadeli amber). Tutar biçimi tablo_html'deki gibi."""
    from shared.tasarim import _tr_para
    from .database import cek_durum_norm, cek_tutarlari
    sym = "$" if pb == "USD" else "₺"
    satirlar = []
    top_m = top_o = top_k = 0.0
    odendi_n = bekleyen_n = 0
    for c in cekler or []:
        t = cek_tutarlari(c)
        top_m += t["meblag"]
        top_o += t["odenen"]
        top_k += t["kalan"]
        odendi_n += 1 if t["odendi"] else 0
        bekleyen_n += 0 if t["odendi"] else 1
        vd = _vade_durumu(c.get("vade"), bugun)
        poz = cek_durum_norm(c.get("durum", "Bekliyor"))
        meb = c.get("meblagh", 0) or None
        kalan = t["kalan"] or 0
        gecikti = kalan > 0 and vd == "gecmis"
        bugun_mu = kalan > 0 and vd == "bugun"
        ref = str(c.get("ref_no") or c.get("ref", "") or "")
        firma = str(c.get("ch_ismi", "") or "").strip() or "—"
        satirlar.append({
            "id": c.get("id"), "ref": ref or "—", "firma": firma, "banka": c.get("banka", "") or "—",
            "cek_no": str(c.get("cek_no", "") or ""), "durum_ham": str(c.get("durum", "Bekliyor") or ""),
            "vade_m": _tarih_m(c.get("vade")) or "—", "vade_m__s": str(c.get("vade") or "")[:10] or "9999",
            "vade_alt": "gecikti" if gecikti else "bugün" if bugun_mu else "",
            "vade_renk": "kirmizi" if gecikti else "amber" if bugun_mu else "",
            "vd": vd, "odendi": bool(t["odendi"]), "kalan": kalan, "gecikmis": gecikti,
            "meblag_m": _tr_para(meb, sym) if meb else "", "meblag_m__s": H._f(meb),
            "odenen_m": _tr_para(t["odenen"], sym) if t["odenen"] else "", "odenen_m__s": t["odenen"],
            "kalan_m": _tr_para(kalan, sym) if kalan else "", "kalan_m__s": kalan,
            "_durum": _cek_rozet(poz, c.get("durum", "Bekliyor")),
            "_soluk": False,
            "_baslik": firma, "_alt": f"Ref {ref or '—'} · çek no {c.get('cek_no', '') or '—'}",
            "_buyuk": _tr_para(kalan, sym) if kalan else (_tr_para(meb, sym) if meb else "—"),
            "_buyuk_alt": "kalan" if kalan else "",
            "_detay": [["Ref no", ref or "—"], ["Çek no", c.get("cek_no", "") or "—"],
                       ["Tarih", _tarih_m(c.get("tarih")) or "—"], ["Vade", _tarih_m(c.get("vade")) or "—"],
                       ["Meblağ", _tr_para(meb, sym) if meb else "—"],
                       ["Ödenen", _tr_para(t["odenen"], sym) if t["odenen"] else "—"],
                       ["Kalan", _tr_para(kalan, sym) if kalan else "—"],
                       ["Son pozisyon", c.get("durum", "Bekliyor") or "—"], ["C/H kodu", c.get("ch_kodu", "") or "—"],
                       ["C/H ismi", c.get("ch_ismi", "") or "—"], ["Banka", c.get("banka", "") or "—"],
                       ["Şube", c.get("sube", "") or "—"], ["Hesap no", c.get("hesap_no", "") or "—"]],
        })
    n = len(cekler or [])
    return {
        "ozet": [_ozet_karti("meblag", "Toplam meblağ", f"{sym}{_tr(top_m, 2)}", "cyan", f"{n} çek (tümü)", suz="tum"),
                 _ozet_karti("odenen", "Toplam ödenen", f"{sym}{_tr(top_o, 2)}", "yesil", f"{odendi_n} adet ödendi",
                             suz="odendi"),
                 _ozet_karti("kalan", "Toplam kalan", f"{sym}{_tr(top_k, 2)}", "amber", f"{bekleyen_n} bekleyen/ciro",
                             suz="bekleyen")],
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []},
                       {"k": "bekleyen", "ad": "Bekleyen/ciro", "f": [["odendi", "eq", False]]},
                       {"k": "gecikmis", "ad": "Gecikmiş", "f": [["gecikmis", "eq", True]]},
                       {"k": "odendi", "ad": "Ödendi", "f": [["odendi", "eq", True]]}],
        "secimler": [{"alan": "banka", "ad": "Tüm bankalar",
                      "secenekler": [{"k": k, "ad": k} for k in sorted({s["banka"] for s in satirlar})]}],
        "ara": {"alanlar": ["ref", "firma", "banka", "cek_no", "durum_ham", "meblag_m"],
                "ipucu": "Ref no, firma, banka, çek no…"},
        "sutunlar": [
            {"alan": "vade_m", "ad": "Vade", "tip": "metin", "alt": "vade_alt", "alt_renk": "vade_renk", "gen": "104px",
             "dar": "alt"},
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "banka"},
            {"alan": "ref", "ad": "Ref no", "tip": "metin", "gen": "96px", "genis": True},
            {"alan": "cek_no", "ad": "Çek no", "tip": "metin", "gen": "96px", "genis": True},
            {"alan": "meblag_m", "ad": "Meblağ", "sag": True, "gen": "130px"},
            {"alan": "odenen_m", "ad": "Ödenen", "sag": True, "gen": "130px", "genis": True},
            {"alan": "kalan_m", "ad": "Kalan", "sag": True, "gen": "130px", "dar": "sag"},
            {"alan": "durum_ham", "ad": "Durum", "tip": "durum", "gen": "112px"},
        ],
        "satirlar": satirlar,
        "islemler": [],
        "bos": {"liste": f"{pb} çeki bulunamadı.", "suzgec": "Bu süzgece uyan çek yok."},
        "baslik_ipucu": f"{pb} çekleri",
    }


def salt_okunur_yurutucu():
    def yurut(_temiz):
        return {"ok": False, "mesaj": "Bu liste salt okunur."}
    return yurut


# ════════════════════════════════════════════════════════════════════
# BANKA BAKİYELERİ
# ════════════════════════════════════════════════════════════════════
def banka_verisi(bankalar, ozet_kalemleri, tahsilatlar=None, salt=False):
    """Hesap listesi (para birimine göre gruplu, bakiyesi büyükten küçüğe — eski kart sırası).
    ozet_kalemleri: banka_ekran.banka_ozet_kalemleri (eski toplam şeridinin kalemleri, aynı formül).
    Satıra tıklayınca bugünkü hesap penceresi açılır (son girişler · düzenle · onaylı sil)."""
    son = {}
    for t in tahsilatlar or []:                      # get_tahsilatlar: yeni → eski; hesabın ilk gördüğü en son giriş
        son.setdefault(t.get("banka_id"), t)
    pb_ad = {"TL": "TL hesapları", "USD": "USD hesapları", "EUR": "EUR hesapları"}
    sirali = sorted(bankalar or [], key=lambda b: ({"TL": 0, "USD": 1, "EUR": 2}.get(b.get("para_birimi"), 3),
                                                   -float(b.get("bakiye") or 0)))
    satirlar = []
    for b in sirali:
        pb = b.get("para_birimi") or ""
        bak = H._f(b.get("bakiye"))
        t = son.get(b.get("id"))
        ad = str(b.get("hesap_adi") or "").strip() or "—"
        son_m = gun_ay_yil(t.get("tarih")) if t else "—"
        son_alt = (f"+{_para(t.get('tutar'), t.get('para_birimi') or pb)} · {str(t.get('kaynak') or '').strip()}"
                   .rstrip(" ·")) if t else "tahsilat yok"
        satirlar.append({
            "id": b.get("id"), "ad": ad, "pb": pb, "pb_grup": pb_ad.get(pb, pb or "Diğer"),
            "bakiye": bak, "bakiye_m": _bakiye(bak, pb), "bakiye_m__s": bak,
            "b_tl": bak if pb == "TL" else 0.0, "b_usd": bak if pb == "USD" else 0.0, "b_eur": bak if pb == "EUR" else 0.0,
            "son_m": son_m, "son_m__s": str((t or {}).get("tarih") or "")[:10], "son_alt": son_alt,
            "_baslik": ad, "_alt": pb, "_buyuk": _bakiye(bak, pb),
        })
    ozet = []                                        # renk yalnız anlam taşıyan kartta (hafta sonu: yeşil/kırmızı)
    for i, k in enumerate(ozet_kalemleri or []):
        hs = k["etiket"] == "Hafta sonu tahmini"
        ozet.append(_ozet_karti(f"o{i}", k["etiket"], k["deger"], k["renk"] if hs else "", k.get("alt") or "",
                                nokta=not hs))
    return {
        "ozet": ozet,
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}],
        "secimler": [{"alan": "pb", "ad": "Tüm para birimleri",
                      "secenekler": [{"k": k, "ad": k} for k in ("TL", "USD", "EUR") if any(s["pb"] == k for s in satirlar)]}],
        "ara": {"alanlar": ["ad", "pb", "bakiye_m"], "ipucu": "Hesap adı ya da tutar"},
        "sutunlar": [
            {"alan": "ad", "ad": "Hesap", "tip": "ana", "alt": "pb"},
            {"alan": "son_m", "ad": "Son giriş", "tip": "metin", "alt": "son_alt", "gen": "minmax(150px,220px)",
             "dar": "alt"},
            {"alan": "bakiye_m", "ad": "Bakiye", "sag": True, "gen": "170px", "dar": "sag"},
        ],
        "grup": {"alan": "pb_grup", "birim": "hesap",
                 "toplamlar": [{"alan": "b_tl", "on": "₺"}, {"alan": "b_usd", "on": "$"}, {"alan": "b_eur", "on": "€"}]},
        "satirlar": satirlar,
        "islemler": [{"k": "ac", "ad": "Hesabı aç", "okuma": True}],
        "tik": "ac",
        "bos": {"liste": "Henüz banka hesabı eklenmemiş.", "suzgec": "Bu süzgece uyan hesap yok."},
        "baslik_ipucu": "Banka hesapları", "salt": bool(salt),
    }


def banka_yurutucu(ac):
    """ac(banka_id): B.detay_ac('bnk', id) — sayfa masadan sonra banka_detay_kontrol ile pencereyi açar."""
    def yurut(temiz):
        if temiz["islem"] != "ac":
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        ac(temiz["ids"][0])
        return dict(_AC)
    return yurut

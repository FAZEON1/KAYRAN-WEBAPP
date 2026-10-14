# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Kampanya Takip — LİSTE MASASI (Ekim 2026, ortak masa: shared/masa.py).

Eski kart listesi ortak masada: özet bandı (aynı dört kart), görünüm (Güncel / Kapanmayı bekleyen /
Kapalı / Tümü), müşteri · kategori · yıl seçimi, arama, sıralama. Satıra tıklayınca BUGÜNKÜ "Kampanya
detayı" penceresi açılır (B.detay_ac("kmp", id) → kampanya._detay_dialog; ürünler, bilgiler, kapanış
aynen orada). Rakamlar kampanya_hesap.kampanya_ozet'ten (tek formül); süzgeç kuralları
kampanya_hesap.filtrele ile aynı anahtarlar (firma_kanonik, kategori_anahtar, başlangıç yılı).

Geri almak için: kayranpm/kampanya.py → KAMPANYA_MASASI_YENI = False.
"""
from shared.tasarim import sayi, tr_sayi

from . import kampanya_hesap as H
from .masa_ortak import ac_islemi, kisa, usd

_GORUNUMLER = [{"k": "guncel", "ad": "Güncel", "f": [["durum", "ne", "kapali"]]},
               {"k": "bekliyor", "ad": "Kapanmayı bekleyen", "f": [["durum", "eq", "bekliyor"]]},
               {"k": "kapali", "ad": "Kapalı", "f": [["durum", "eq", "kapali"]]},
               {"k": "tumu", "ad": "Tümü", "f": []}]


def _kusd(v):
    """Eski kartların kısa doları (shared.tasarim.sayi: $123K, $1,17M)."""
    return "—" if v is None else sayi(v, "$")


def ozet_kartlari(kamps, oz, bugun):
    """Eski üst özet (kampanya.render kpi_serit) — aynı hesap, aynı metinler."""
    say = {d: sum(1 for o in oz.values() if o["durum"] == d) for d in H.DURUM_SIRA}
    yil = str(bugun.year)
    bu_yil = [oz[k["id"]] for k in kamps if str(k.get("baslangic_tarihi") or "")[:4] == yil]
    _d = sum(o["destek"] for o in bu_yil)
    _fd = sum(o["firma_destek"] for o in bu_yil)
    _ed = sum(o["ek_destek"] for o in bu_yil)
    _net = sum(o["net"] for o in bu_yil if o["adet"] > 0)
    _ciro = sum(o["ciro"] for o in bu_yil if o["adet"] > 0)
    return [
        {"k": "suruyor", "et": "Sürüyor", "dg": tr_sayi(say["suruyor"]), "renk": "yesil",
         "al": f"{say['yaklasan']} yaklaşan"},
        {"k": "bekliyor", "et": "Kapanmayı bekliyor", "dg": tr_sayi(say["bekliyor"]), "suz": "bekliyor",
         "renk": "amber" if say["bekliyor"] else "silik",
         "al": "satış adedi girilmeli" if say["bekliyor"] else "bekleyen yok"},
        {"k": "destek", "et": f"{yil} destek", "dg": kisa(_kusd(_d)), "renk": "mor", "nokta": False,
         "al": f"firma {_kusd(_fd)} · ek {_kusd(_ed)}", "ipucu": f"${tr_sayi(_d, 2)}"},
        {"k": "net", "et": f"{yil} net kâr", "dg": kisa(_kusd(_net)), "renk": "yesil" if _net >= 0 else "kirmizi",
         "nokta": False, "ipucu": f"${tr_sayi(_net, 2)}",
         "al": (f"net marj %{tr_sayi(_net / _ciro * 100, 1)} · spiff sonrası" if _ciro > 0 else "spiff sonrası")},
    ]


def _firma_anahtari(firma):
    """kampanya_hesap.filtrele ile aynı: 'DİĞER' = firması belli olmayan (eski KANAL dahil)."""
    from shared.utils import firma_kanonik, DIGER_KODU
    fk = firma_kanonik(firma)
    return "DİĞER" if fk == DIGER_KODU else fk


def masa_verisi(kamps, ku_map, pacal, bugun, kategoriler=(), firma_ad=str, kat_ad=str, aralik=None, kalan=None):
    """Masanın tanımı. firma_ad / kat_ad / aralik / kalan: kampanya.py'nin görünüm yardımcıları
    (_firma_ad, kategori_ad, _aralik, _kalan_metni) — ekrandaki metin eskisiyle aynı."""
    from shared.ana_veri import kategori_anahtar
    aralik = aralik or (lambda k: "")
    kalan = kalan or (lambda o: "")
    oz = {k["id"]: H.kampanya_ozet(k, ku_map.get(k["id"], []), pacal, bugun) for k in kamps}
    sira = {d: i for i, d in enumerate(H.DURUM_SIRA)}
    satirlar = []
    for k in H.filtrele(kamps, bugun):                     # eski liste sırası: durum, sonra bitiş
        o = oz[k["id"]]
        ad_d, renk, aciklama = H.DURUMLAR[o["durum"]]
        firma_m, kat_m, tur = firma_ad(k.get("firma")), kat_ad(k.get("kategori")), (k.get("kampanya_turu") or "").strip()
        meta = " · ".join(x for x in (firma_m, kat_m, tur) if x)
        adet_var = o["adet"] > 0
        bos_net = "adet girilmedi" if o["durum"] in ("bekliyor", "kapali") else "satış bekleniyor"
        satirlar.append({
            "id": k["id"], "ad": str(k.get("kampanya_adi") or "—"), "meta": meta,
            "ara_ek": f"{k.get('kampanya_adi', '')} {k.get('firma', '')} {k.get('kategori', '')} "
                      f"{k.get('kampanya_turu', '')} {k.get('notlar', '')} {firma_m} {kat_m}",
            "firma_s": _firma_anahtari(k.get("firma")), "kat_s": kategori_anahtar(k.get("kategori")),
            "yil": str(k.get("baslangic_tarihi") or "")[:4],
            "aralik": aralik(k), "aralik__s": str(k.get("bitis_tarihi") or "")[:10], "kalan": kalan(o),
            "adet_m": f"{tr_sayi(o['adet'])} adet", "adet_m__s": o["adet"], "urun_m": f"{o['urun']} ürün",
            "destek_m": usd(o["destek"]) if adet_var else "", "destek_m__s": o["destek"] if adet_var else None,
            "net_m": usd(o["net"]) if adet_var else bos_net, "net_m__s": o["net"] if adet_var else None,
            "marj_m": (f"marj %{tr_sayi(o['marj'], 1)}" if o["marj"] is not None else "") if adet_var else "",
            "net_renk": ("yesil" if o["net"] >= 0 else "kirmizi") if adet_var else "",
            "durum": o["durum"], "durum__s": sira[o["durum"]],
            "_durum": {"ad": ad_d, "renk": renk},
            "_soluk": o["durum"] == "kapali",
        })
    firmalar_var = {s["firma_s"] for s in satirlar}
    firma_sec = []
    for f in H.firma_secenekleri([k.get("firma") for k in kamps]):
        kod = "DİĞER" if f == "DİĞER" else f
        if kod in firmalar_var:
            firma_sec.append({"k": kod, "ad": "DİĞER" if kod == "DİĞER" else firma_ad(f)})
    katlar_var = {s["kat_s"] for s in satirlar}
    kat_sec, gor = [], set()
    for x in kategoriler or ():
        a = kategori_anahtar(x)
        if a in katlar_var and a not in gor:
            gor.add(a)
            kat_sec.append({"k": a, "ad": kat_ad(x)})
    yillar = sorted({s["yil"] for s in satirlar if s["yil"].isdigit()}, reverse=True)
    return {
        "ozet": ozet_kartlari(kamps, oz, bugun),
        "gorunumler": _GORUNUMLER,
        "secimler": [{"alan": "firma_s", "ad": "Tüm müşteriler", "secenekler": firma_sec},
                     {"alan": "kat_s", "ad": "Tüm kategoriler", "secenekler": kat_sec},
                     {"alan": "yil", "ad": "Tüm yıllar", "secenekler": [{"k": y, "ad": y} for y in yillar]}],
        "ara": {"alanlar": ["ara_ek"], "ipucu": "Kampanya, firma, kategori…"},
        "sutunlar": [
            {"alan": "ad", "ad": "Kampanya", "tip": "ana", "alt": "meta"},
            {"alan": "aralik", "ad": "Tarih", "alt": "kalan", "gen": "160px", "dar": "alt"},
            {"alan": "adet_m", "ad": "Satış", "sag": True, "alt": "urun_m", "gen": "100px", "genis": True},
            {"alan": "destek_m", "ad": "Destek", "sag": True, "gen": "116px", "genis": True},
            {"alan": "net_m", "ad": "Net kâr", "sag": True, "alt": "marj_m", "alt_renk": "net_renk", "gen": "132px",
             "dar": "sag"},
            {"alan": "durum", "ad": "Durum", "tip": "durum", "gen": "160px"},
        ],
        "satirlar": satirlar,
        "islemler": [ac_islemi("Kampanya detayı")],
        "tik": "ac",
        "bos": {"liste": "Henüz kampanya yok.",
                "suzgec": "Bu görünümde kampanya yok. Filtreleri gevşet, aramayı temizle ya da başka bir görünüm seç."},
        "baslik_ipucu": "Kampanyalar",
        "say": {d: sum(1 for o in oz.values() if o["durum"] == d) for d in H.DURUM_SIRA},
    }


def yurutucu():
    """Satıra tıklama → bugünkü detay penceresi (B.detay_ac("kmp", id)); sayfa aynı çalıştırmada devam eder
    ve render'ın sonundaki B.detay_istendi("kmp") pencereyi açar."""
    def yurut(temiz):
        if temiz["islem"] == "ac":
            from shared import bilesen as B
            B.detay_ac("kmp", temiz["ids"][0])
            return {"ok": True, "yenileme": False, "sessiz": True}
        return {"ok": False, "mesaj": "Bilinmeyen işlem."}
    return yurut

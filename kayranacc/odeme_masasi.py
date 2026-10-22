# -*- coding: utf-8 -*-
"""Muhasebe › Bu hafta — ÖDEME MASASI (Ekim 2026, hibrit yol B; kullanıcı onayı A).

Prototip: https://claude.ai/artifact/QeMhUiHWNK1sYnAtsRjkzW
Liste, yan detay paneli ve toplu işlem ORTAK LİSTE MASASINDA (shared/masa.py); bu modül yalnız masanın
tanımını (masa_verisi), ödemeye özgü kontrolü (istek_coz) ve yürütmeyi (islem_uygula) verir. İstek burada doğrulanır (istek_coz) ve bugünkü
veritabanı fonksiyonlarıyla yürütülür (islem_uygula) — bakiye düşme/iade, kısmi ödeme, kalıcı erteleme
kaydı, düzenleme ve silme kuralları DEĞİŞMEDİ (kayranacc/database.py).

Rakamlar: özet bandı kayranacc.odeme_hesap.ozet'ten (Genel Bakış ile aynı formül); büyük rakamda kuruş
yok (shared.tasarim.kart_degeri_kisa), satırda tam tutar.

Geri almak için: kayranacc/odeme_ekran.py → ODEME_MASASI_YENI = False (eski ekran aynen duruyor).
"""
from datetime import date, timedelta

from . import odeme_hesap as H

BANKASIZ = "_bankasiz"
TURLER = ("ode", "kismi", "otele", "duzenle", "sil", "geri_al")
_TEK = ("kismi", "duzenle", "sil")                 # tek ödemeyle yapılır
OTELE_EN_COK_GUN = 366


# ── Biçim ───────────────────────────────────────────────────────────
def _tl(v, ondalik=2):
    from shared.tasarim import tr_sayi
    return f"₺{tr_sayi(v, ondalik)}"


def _usd(v, ondalik=2):
    from shared.tasarim import tr_sayi
    return f"${tr_sayi(v, ondalik)}"


def _kisa(metin):
    """Büyük özet rakamı: 1.000 ve üstünde kuruşsuz (kartlarla aynı kural)."""
    from shared.tasarim import kart_degeri_kisa
    return kart_degeri_kisa(metin)[0]


def _bakiye(v, para):
    """Banka bakiyesi kendi para biriminde: ₺ · $ · € (eski ekran EUR hesabını ₺ ile yazıyordu)."""
    from shared.tasarim import tr_sayi
    isaret = {"TL": "₺", "TRY": "₺", "USD": "$", "EUR": "€"}.get(str(para or "").upper())
    return f"{isaret}{tr_sayi(v, 2)}" if isaret else f"{tr_sayi(v, 2)} {para or ''}".strip()


def _iki(tl, usd, kisa=False):
    p = [(_kisa(_tl(tl)) if kisa else _tl(tl)) if tl else "", (_kisa(_usd(usd)) if kisa else _usd(usd)) if usd else ""]
    return " + ".join(x for x in p if x)


# ── Ekrana giden veri (saf) ─────────────────────────────────────────
# Mikro'dan gelen satırda yapılabilecek tek işlem (durum, tutar ve satırın kendisi Mikro'dan gelir)
MIKRO_ISLEM = ("otele",)


def masa_verisi(odemeler, bankalar, kategoriler, kur, bugun, salt=False, bildirim=None, mikro_idler=None):
    """Bileşenin çizdiği her şey. Sıra odeme_hesap.gunlere_bol ile (vade, gün içinde önce bekleyen,
    sonra kategori önceliği) — eski ekranla aynı.
    mikro_idler: Mikro'dan gelen satırlar (kayranacc.mikro_odeme_oto.mikro_idleri). Bu satırlarda Öde, Düzenle,
    Sil, Geri al yok — ödendi bilgisi Mikro'dan gelir (kullanıcı, 22.10.2026); yalnız Ötele kalır. Elle eklenen
    satırlarda her işlem eskisi gibi."""
    mikro_idler = set(mikro_idler or ())
    from shared.tasarim import tr_sayi
    kur = H._f(kur)
    oz = H.ozet(odemeler, bankalar, kur, bugun)
    hs = oz["hafta_sonu_tl"]
    oran = (oz["odendi_adet"] / oz["adet"]) if oz["adet"] else 0.0
    ozet = [
        {"k": "bugun", "et": "Bugün vadeli", "dg": f"{len(oz['bugun'])} ödeme", "suz": "bugun",
         "renk": "amber" if oz["bugun"] else "silik", "al": _iki(oz["bugun_tl"], oz["bugun_usd"], True) or "bugün ödeme yok"},
        {"k": "gecikmis", "et": "Gecikmiş", "dg": f"{len(oz['gecikmis'])} ödeme", "suz": "gecikmis",
         "renk": "kirmizi" if oz["gecikmis"] else "silik",
         "al": _iki(oz["gecikmis_tl"], oz["gecikmis_usd"], True) or "gecikme yok"},
        {"k": "kalan", "et": "Bu hafta kalan", "dg": _kisa(_tl(oz["bekleyen_tl"])), "suz": "bekleyen", "renk": "",
         "al": (f"+ {_usd(oz['bekleyen_usd'])} · " if oz["bekleyen_usd"] else "")
               + f"{oz['odendi_adet']}/{oz['adet']} ödendi", "oran": round(oran, 4)},
        {"k": "hafta_sonu", "et": "Hafta sonu tahmini" if hs >= 0 else "Nakit açığı", "dg": _kisa(_tl(abs(hs))),
         "suz": None, "renk": "yesil" if hs >= 0 else "kirmizi", "al": "TL bankalar − bekleyenler", "nokta": False,
         "ipucu": f"TL banka bakiyesi − bekleyen TL − bekleyen USD × kur ({tr_sayi(kur, 4)})"},
    ]
    banka_ad = {b.get("id"): str(b.get("hesap_adi") or "") for b in bankalar or []}
    oncelik = {k: v.get("oncelik", 99) for k, v in (kategoriler or {}).items()}
    renk = {"gecikmis": "kirmizi", "bugun": "amber", "odendi": "yesil", "tarihsiz": "silik"}
    durum_ad = {"gecikmis": "Gecikmiş", "bugun": "Bugün", "yarin": "Yarın", "ileri": "Bekliyor", "odendi": "Ödendi",
                "tarihsiz": "Vadesiz"}
    satirlar = []
    for _gun, liste in H.gunlere_bol(odemeler or [], oncelik):
        for o in liste:
            v = H._tarih(o.get("vade"))
            tl, usd = H._f(o.get("tutar_tl")), H._f(o.get("tutar_usd"))
            kat = o.get("kategori") or "diger"
            d = H.vade_durumu(o, bugun)
            fark = (v - bugun).days if v else None
            ban = banka_ad.get(o.get("banka_id"), "") if H.odendi_mi(o) else ""
            od_t = str(o.get("odendi_tarih") or "")[:10]
            firma = str(o.get("firma") or "").strip() or "—"
            kat_ad = (kategoriler or {}).get(kat, {}).get("label") or H.KATEGORI_AD.get(kat, kat)
            satirlar.append({
                "id": o.get("id"), "firma": firma, "ack": str(o.get("aciklama") or "").strip(), "kat": kat,
                "kat_ad": kat_ad, "vade": v.isoformat() if v else "", "vade_kisa": f"{v:%d.%m}" if v else "—",
                "vade_kisa__s": (v.isoformat() if v else "9999"),
                "vade_alt": (ban or "ödendi") if d == "odendi" else ("vadesiz" if fark is None else f"{-fark} gün gecikti"
                            if fark < 0 else "bugün" if fark == 0 else "yarın" if fark == 1 else f"{fark} gün kaldı"),
                "vade_renk": renk.get(d, "silik") if d in ("gecikmis", "bugun") else "silik",
                "gun": H.gun_basligi(o.get("vade"), bugun), "durum": d, "fark": fark,
                "tl": tl, "usd": usd, "tl_m": _tl(tl) if tl else "", "usd_m": _usd(usd) if usd else "",
                "tl_m__s": tl, "usd_m__s": usd, "tl_try": tl + usd * kur, "banka_ad": ban, "odendi_tarih": od_t,
                "_durum": {"ad": durum_ad.get(d, ""), "renk": renk.get(d, "soluk"),
                           "ek": f"{-fark} gün" if d == "gecikmis" and fark is not None else ""},
                "_baslik": firma, "_alt": str(o.get("aciklama") or "").strip(),
                "_buyuk": _tl(tl) if tl else _usd(usd), "_buyuk_alt": f"+ {_usd(usd)}" if tl and usd else "",
                "_detay": [["Vade", H.gun_basligi(o.get("vade"), bugun)], ["Kategori", kat_ad]]
                          + ([["TL karşılığı", f"{_tl(tl + usd * kur)} (kur {tr_sayi(kur, 4)})"]] if usd else []),
                "_not": (f"Ödendi{' · ' + '.'.join(reversed(od_t.split('-'))) if od_t else ''}"
                         + (f" · {ban} hesabından düşüldü" if ban else " · bakiyeden düşülmedi")) if d == "odendi" else "",
                "_soluk": d == "odendi",
                "mikro": o.get("id") in mikro_idler,
            })
            if satirlar[-1]["mikro"]:
                satirlar[-1]["_not"] = ((satirlar[-1]["_not"] + " · ") if satirlar[-1]["_not"] else "") + \
                    "Mikro'dan geliyor: fatura Mikro'da kapanınca kendiliğinden ödendi olur."
    kat_sec = [{"k": k, "ad": v.get("label", k)}
               for k, v in sorted((kategoriler or {}).items(), key=lambda kv: kv[1].get("oncelik", 99))]
    banka_sec = [{"k": b.get("id"), "ad": f"{banka_ad.get(b.get('id'), '')} · "
                                           f"{_bakiye(H._f(b.get('bakiye')), b.get('para_birimi'))}"} for b in bankalar or []]
    banka_sec.append({"k": BANKASIZ, "ad": "Bakiyeden düşme (yalnız ödendi işaretle)"})
    bekler = [["durum", "ne", "odendi"]]
    elle = [["mikro", "ne", True]]            # yalnız elle eklenen satırlar
    return {
        # ortak masa (shared/masa.py) tanımı
        "ozet": ozet,
        "gorunumler": [{"k": "bekleyen", "ad": "Bekleyen", "f": bekler},
                       {"k": "gecikmis", "ad": "Gecikmiş", "f": [["durum", "eq", "gecikmis"]]},
                       {"k": "bugun", "ad": "Bugün", "f": [["durum", "eq", "bugun"]]},
                       {"k": "odendi", "ad": "Ödendi", "f": [["durum", "eq", "odendi"]]},
                       {"k": "tum", "ad": "Tümü", "f": []}],
        "secimler": [{"alan": "kat", "ad": "Tüm kategoriler",
                      "secenekler": [k for k in kat_sec if any(s["kat"] == k["k"] for s in satirlar)]}],
        "anahtarlar": [{"k": "tl", "ad": "Yalnız TL", "f": [["tl", "gt", 0]]},
                       {"k": "usd", "ad": "Yalnız USD", "f": [["usd", "gt", 0]]}],
        "ara": {"alanlar": ["firma", "ack", "kat_ad", "tl_m", "usd_m"], "ipucu": "Firma, açıklama ya da tutar"},
        "sutunlar": [
            {"alan": "vade_kisa", "ad": "Vade", "tip": "metin", "alt": "vade_alt", "alt_renk": "vade_renk", "gen": "96px", "dar": "alt"},
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "ack"},
            {"alan": "kat_ad", "ad": "Kategori", "tip": "etiket", "gen": "110px", "genis": True},
            {"alan": "tl_m", "ad": "TL", "sag": True, "gen": "124px", "dar": "sag"},
            {"alan": "usd_m", "ad": "USD", "sag": True, "gen": "104px", "genis": True},
            {"alan": "durum", "ad": "Durum", "tip": "durum", "gen": "116px"},
        ],
        "grup": {"alan": "gun", "birim": "ödeme", "toplamlar": [{"alan": "tl", "on": "₺"}, {"alan": "usd", "on": "$"}]},
        "toplu_toplam": [{"alan": "tl", "on": "₺"}, {"alan": "usd", "on": "$"}],
        "satirlar": satirlar,
        "islemler": [
            {"k": "ode", "ad": "Öde", "dugme": "Öde", "f": bekler + elle, "birincil": True,
             "ipucu": "Tutarı küçültürseniz kısmi ödeme olur: ödenen kısım ayrı kayıt açılır, kalan aynı vadeyle listede kalır.",
             "toplu": {"ad": "Seçilenleri öde", "alanlar": ["banka"]},
             "alanlar": [{"ad": "banka", "et": "Hangi bankadan ödendi?", "tip": "secim", "zorunlu": True, "tam": True,
                          "bos": "Banka seç…", "secenekler": banka_sec},
                         {"ad": "tl", "et": "Ödenen TL", "tip": "sayi", "varsayilan_alan": "tl", "en_cok_alan": "tl",
                          "gizle_sifir": True},
                         {"ad": "usd", "et": "Ödenen USD", "tip": "sayi", "varsayilan_alan": "usd", "en_cok_alan": "usd",
                          "gizle_sifir": True}]},
            {"k": "otele", "ad": "Ötele", "dugme": "Ötele", "f": bekler,
             "ipucu": "Erteleme kaydı kalıcıdır (Ertelenen ödemeler'de görünür).",
             "hizli": [{"ad": f"+{g} gün", "degerler": {"gun": g}} for g in (1, 3, 7, 30)],
             "toplu": {"ad": "+7 gün ötele", "alanlar": [], "degerler": {"gun": 7}},
             "alanlar": [{"ad": "vade", "et": "Ya da tarih seç", "tip": "tarih", "varsayilan_alan": "vade"},
                         {"ad": "gun", "tip": "gizli", "sayi": True, "en_az": 1, "en_cok": OTELE_EN_COK_GUN}]},
            {"k": "duzenle", "ad": "Düzenle", "dugme": "Kaydet", "f": bekler + elle,
             "alanlar": [{"ad": "tl", "et": "Tutar TL", "tip": "sayi", "varsayilan_alan": "tl"},
                         {"ad": "usd", "et": "Tutar USD", "tip": "sayi", "varsayilan_alan": "usd"},
                         {"ad": "kategori", "et": "Kategori", "tip": "secim", "secenekler": kat_sec, "varsayilan_alan": "kat",
                          "tam": True, "zorunlu": True},
                         {"ad": "aciklama", "et": "Açıklama", "tip": "metin", "varsayilan_alan": "ack"}]},
            {"k": "sil", "ad": "Sil", "dugme": "Ödemeyi sil", "f": bekler + elle, "tehlike": True,
             "ipucu": "Kayıt kalıcı olarak silinir.",
             "alanlar": [{"ad": "onay", "et": "Evet, {baslik} ödemesini sil", "tip": "onay", "zorunlu": True}]},
            {"k": "geri_al", "ad": "Geri al", "dugme": "Geri al (bekliyor yap)", "f": [["durum", "eq", "odendi"]] + elle,
             "coklu": True},
        ],
        "bos": {"liste": "Bu hafta ödeme yok.",
                "suzgec": "Bu süzgece uyan ödeme yok. Ödenenleri görmek için 'Ödendi' ya da 'Tümü'."},
        "baslik_ipucu": "Ödemeler",
        # sayfanın kendi kullandıkları (bileşen okumaz)
        "bugun": bugun.isoformat(), "salt": bool(salt), "kur": kur, "kur_m": tr_sayi(kur, 4),
        "kategoriler": kat_sec,
        "bankalar": [{"id": b.get("id"), "ad": banka_ad.get(b.get("id"), ""), "para": b.get("para_birimi") or "",
                      "bakiye_m": _bakiye(H._f(b.get("bakiye")), b.get("para_birimi"))} for b in bankalar or []],
        "bildirim": bildirim,
    }


# ── İsteğin doğrulanması (saf) ──────────────────────────────────────
def _sayi(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def istek_coz(istek, odemeler, bankalar, kategoriler, salt=False, bugun=None, mikro_idler=None):
    """Bileşenden gelen isteği doğrular. Döner: (temiz istek, None) ya da (None, kullanıcıya hata metni).
    Tarayıcıdan gelen hiçbir değere güvenilmez: kimlik listede, banka hesaplarda, tutar kalan tutarda olmalı.
    Mikro'dan gelen satırda yalnız MIKRO_ISLEM yapılır (masa_verisi)."""
    if salt:
        return None, "Salt-okur oturum: işlem yapılamaz."
    istek = istek if isinstance(istek, dict) else {}
    tur = istek.get("tur")
    if tur not in TURLER:
        return None, "Bilinmeyen işlem."
    ham = istek.get("ids") if isinstance(istek.get("ids"), list) else []
    if not ham:
        return None, "Ödeme seçilmedi."
    sozluk = {o.get("id"): o for o in odemeler or []}
    ids = []
    for i in ham:
        if isinstance(i, bool) or not isinstance(i, (int, float)) or int(i) != i or int(i) not in sozluk:
            return None, "Ödeme bulunamadı; sayfayı yenileyip tekrar deneyin."
        if int(i) not in ids:
            ids.append(int(i))
    if tur not in MIKRO_ISLEM and any(i in set(mikro_idler or ()) for i in ids):
        return None, "Bu ödeme Mikro'dan geliyor: ödendi bilgisi Mikro'dan gelir, burada değiştirilmez."
    if tur in _TEK and len(ids) != 1:
        return None, "Bu işlem tek ödemeyle yapılır."
    secilen = [sozluk[i] for i in ids]
    t = {"tur": tur, "ids": ids}

    if tur in ("ode", "kismi"):
        if any(H.odendi_mi(o) for o in secilen):
            return None, "Seçilenlerden biri zaten ödenmiş."
        b = istek.get("banka")
        if b == BANKASIZ:
            t["banka"] = None
        elif not isinstance(b, bool) and isinstance(b, (int, float)) and any(x.get("id") == b for x in bankalar or []):
            t["banka"] = int(b)
        else:
            return None, "Hangi bankadan ödendiğini seçin (ya da 'Bakiyeden düşme')."
    if tur == "kismi":
        o = secilen[0]
        tl, usd = _sayi(istek.get("tl")), _sayi(istek.get("usd"))
        if tl is None or usd is None or tl < 0 or usd < 0 or (tl == 0 and usd == 0):
            return None, "Ödenen tutarı girin."
        mtl, musd = H._f(o.get("tutar_tl")), H._f(o.get("tutar_usd"))
        if tl > mtl + 1e-9 or usd > musd + 1e-9:
            return None, f"Ödenen tutar en çok {_iki(mtl, musd)} olabilir."
        t.update(tl=tl, usd=usd)
    if tur == "otele":
        vadeler = {}
        gun = istek.get("gun")
        if gun is not None:
            if isinstance(gun, bool) or not isinstance(gun, (int, float)) or int(gun) != gun or not 1 <= gun <= OTELE_EN_COK_GUN:
                return None, "Geçerli bir tarih ya da gün sayısı seçin."
            for o in secilen:
                vadeler[o["id"]] = (H._tarih(o.get("vade")) or bugun or date.today()) + timedelta(days=int(gun))
        else:
            v = H._tarih(istek.get("vade")) if isinstance(istek.get("vade"), str) and len(istek["vade"]) == 10 else None
            if v is None:
                return None, "Geçerli bir tarih seçin."
            if len(secilen) == 1 and H._tarih(secilen[0].get("vade")) == v:
                return None, "Yeni vade mevcut vadeyle aynı."
            vadeler = {o["id"]: v for o in secilen}
        t["vadeler"] = vadeler
    if tur == "duzenle":
        tl, usd = _sayi(istek.get("tl")), _sayi(istek.get("usd"))
        if tl is None or usd is None or tl < 0 or usd < 0 or (tl == 0 and usd == 0):
            return None, "En az bir tutar (TL ya da USD) 0'dan büyük olmalı; eksi tutar olmaz."
        kat = istek.get("kategori")
        if kat not in (kategoriler or {}):
            return None, "Kategori listede yok."
        t.update(tl=tl, usd=usd, kategori=kat, aciklama=str(istek.get("aciklama") or "").strip()[:500])
    if tur == "geri_al" and not all(H.odendi_mi(o) for o in secilen):
        return None, "Geri alınacak ödeme ödenmemiş görünüyor."
    return t, None


# ── Yürütme (veritabanı) ────────────────────────────────────────────
def _ad(odemeler, i):
    o = next((x for x in odemeler or [] if x.get("id") == i), {})
    return str(o.get("firma") or "Ödeme").strip()


def islem_uygula(t, odemeler, kur):
    """istek_coz'dan geçmiş isteği bugünkü veritabanı fonksiyonlarıyla yürütür.
    Döner: {"ok", "mesaj", "geri_al": [ödemesi geri alınabilecek kimlikler]}."""
    from . import database as D
    ids, tur = t["ids"], t["tur"]
    adlar = f"{_ad(odemeler, ids[0])}" if len(ids) == 1 else f"{len(ids)} ödeme"
    if tur == "ode":
        for i in ids:
            D.odeme_durum_guncelle(i, "odendi", t.get("banka"), kur)
        return {"ok": True, "mesaj": f"{adlar} ödendi", "geri_al": list(ids)}
    if tur == "kismi":
        ok, msg = D.odeme_kismi_ode(ids[0], t["tl"], t["usd"], t.get("banka"), kur)
        return {"ok": bool(ok), "mesaj": msg, "geri_al": []}
    if tur == "otele":
        sozluk = {o.get("id"): o for o in odemeler or []}
        hata = [i for i in ids if not D.odeme_vade_guncelle(i, t["vadeler"][i], ertele=True,
                                                             eski_vade=H._tarih(sozluk[i].get("vade")))]
        if hata:
            return {"ok": False, "geri_al": [],
                    "mesaj": f"{len(hata)} ödemenin vadesi güncellenemedi; vadesi DEĞİŞMEDİ. Ayrıntı Sistem Kayıtları'nda."}
        if len(ids) == 1:
            return {"ok": True, "mesaj": f"{adlar} {t['vadeler'][ids[0]]:%d.%m.%Y} tarihine ötelendi", "geri_al": []}
        return {"ok": True, "mesaj": f"{adlar} ötelendi", "geri_al": []}
    if tur == "duzenle":
        i = ids[0]
        o = next((x for x in odemeler or [] if x.get("id") == i), {})
        D.odeme_tutar_guncelle(i, tutar_tl=t["tl"], tutar_usd=t["usd"])
        if t["kategori"] != (o.get("kategori") or "diger"):
            D.odeme_kategori_guncelle(i, t["kategori"])
        if t["aciklama"] != str(o.get("aciklama") or "").strip():
            D.odeme_aciklama_guncelle(i, t["aciklama"])
        return {"ok": True, "mesaj": f"{adlar} güncellendi", "geri_al": []}
    if tur == "sil":
        D.odeme_sil(ids[0])
        return {"ok": True, "mesaj": f"{adlar} ödemesi silindi", "geri_al": []}
    for i in ids:                                     # geri_al
        D.odeme_durum_guncelle(i, "bekliyor", kur=kur)
    return {"ok": True, "mesaj": f"{adlar} yeniden bekliyor durumunda (bankadan düşüldüyse iade edildi)",
            "geri_al": []}


# ── Ortak masaya köprü ──────────────────────────────────────────────
def motor_istegi(temiz):
    """shared.masa.istek_al çıktısı → bu modülün istek biçimi (istek_coz anlamsal kontrolü yapar).
    Tek ödemede tutar küçültülmüşse kısmi ödemedir."""
    d, ids, islem = temiz["degerler"], temiz["ids"], temiz["islem"]
    if islem == "ode":
        banka = d.get("banka")
        if len(ids) == 1 and ("tl" in d or "usd" in d):
            o = temiz["satirlar"][0]
            tl = d.get("tl", H._f(o.get("tl"))) if H._f(o.get("tl")) else 0.0
            usd = d.get("usd", H._f(o.get("usd"))) if H._f(o.get("usd")) else 0.0
            if abs(tl - H._f(o.get("tl"))) > 0.004 or abs(usd - H._f(o.get("usd"))) > 0.004:
                return {"tur": "kismi", "ids": ids, "banka": banka, "tl": tl, "usd": usd}
        return {"tur": "ode", "ids": ids, "banka": banka}
    if islem == "otele":
        if "gun" in d:
            return {"tur": "otele", "ids": ids, "gun": int(d["gun"])}
        v = d.get("vade")
        return {"tur": "otele", "ids": ids, "vade": v.isoformat() if v else None}
    if islem == "duzenle":
        return {"tur": "duzenle", "ids": ids, "tl": d.get("tl", 0.0), "usd": d.get("usd", 0.0),
                "kategori": d.get("kategori"), "aciklama": d.get("aciklama", "")}
    return {"tur": islem, "ids": ids}


def yurutucu(odemeler, bankalar, kategoriler, kur, bugun, salt=False, mikro_idler=None):
    """shared.masa.calistir için: temiz istek → anlamsal kontrol → veritabanı → bildirim."""
    def yurut(temiz):
        t, hata = istek_coz(motor_istegi(temiz), odemeler, bankalar, kategoriler, salt=salt, bugun=bugun,
                            mikro_idler=mikro_idler)
        if hata:
            return {"ok": False, "mesaj": hata}
        s = islem_uygula(t, odemeler, kur)
        return {"ok": s["ok"], "mesaj": s["mesaj"],
                "geri": {"islem": "geri_al", "ids": s["geri_al"]} if s.get("geri_al") else None}
    return yurut

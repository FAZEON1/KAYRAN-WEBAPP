# -*- coding: utf-8 -*-
"""Muhasebe › Bu hafta — ÖDEME MASASI (Ekim 2026, hibrit yol B; kullanıcı onayı A).

Prototip: https://claude.ai/artifact/QeMhUiHWNK1sYnAtsRjkzW
Liste, yan detay paneli ve toplu işlem tek bir JS bileşeninde (Streamlit components v2; iframe yok,
derleme yok — shared/tablo.py ile aynı altyapı). Bileşen tarayıcıda anında tepki verir; YALNIZ İSTEK
gönderir: {"tur": "ode", "ids": [12], "banka": 3}. İstek burada doğrulanır (istek_coz) ve bugünkü
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
def masa_verisi(odemeler, bankalar, kategoriler, kur, bugun, salt=False, bildirim=None):
    """Bileşenin çizdiği her şey. Sıra odeme_hesap.gunlere_bol ile (vade, gün içinde önce bekleyen,
    sonra kategori önceliği) — eski ekranla aynı."""
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
         "suz": None, "renk": "yesil" if hs >= 0 else "kirmizi", "al": "TL bankalar − bekleyenler",
         "ipucu": f"TL banka bakiyesi − bekleyen TL − bekleyen USD × kur ({tr_sayi(kur, 4)})"},
    ]
    banka_ad = {b.get("id"): str(b.get("hesap_adi") or "") for b in bankalar or []}
    oncelik = {k: v.get("oncelik", 99) for k, v in (kategoriler or {}).items()}
    satirlar = []
    for _gun, liste in H.gunlere_bol(odemeler or [], oncelik):
        for o in liste:
            v = H._tarih(o.get("vade"))
            tl, usd = H._f(o.get("tutar_tl")), H._f(o.get("tutar_usd"))
            kat = o.get("kategori") or "diger"
            satirlar.append({
                "id": o.get("id"), "firma": str(o.get("firma") or "").strip() or "—",
                "ack": str(o.get("aciklama") or "").strip(), "kat": kat,
                "kat_ad": (kategoriler or {}).get(kat, {}).get("label") or H.KATEGORI_AD.get(kat, kat),
                "vade": v.isoformat() if v else "", "vade_kisa": f"{v:%d.%m}" if v else "—",
                "gun": H.gun_basligi(o.get("vade"), bugun), "durum": H.vade_durumu(o, bugun),
                "fark": (v - bugun).days if v else None,
                "tl": tl, "usd": usd, "tl_m": _tl(tl) if tl else "", "usd_m": _usd(usd) if usd else "",
                "tl_try": tl + usd * kur,
                "banka_ad": banka_ad.get(o.get("banka_id"), "") if H.odendi_mi(o) else "",
                "odendi_tarih": str(o.get("odendi_tarih") or "")[:10],
            })
    return {
        "bugun": bugun.isoformat(), "salt": bool(salt), "kur": kur, "kur_m": tr_sayi(kur, 4),
        "ozet": ozet, "odemeler": satirlar,
        "kategoriler": [{"k": k, "ad": v.get("label", k)}
                        for k, v in sorted((kategoriler or {}).items(), key=lambda kv: kv[1].get("oncelik", 99))],
        "bankalar": [{"id": b.get("id"), "ad": banka_ad.get(b.get("id"), ""), "para": b.get("para_birimi") or "",
                      "bakiye_m": _bakiye(H._f(b.get("bakiye")), b.get("para_birimi"))}
                     for b in bankalar or []],
        "bildirim": bildirim,
    }


# ── İsteğin doğrulanması (saf) ──────────────────────────────────────
def _sayi(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def istek_coz(istek, odemeler, bankalar, kategoriler, salt=False, bugun=None):
    """Bileşenden gelen isteği doğrular. Döner: (temiz istek, None) ya da (None, kullanıcıya hata metni).
    Tarayıcıdan gelen hiçbir değere güvenilmez: kimlik listede, banka hesaplarda, tutar kalan tutarda olmalı."""
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


# ── Bileşen ─────────────────────────────────────────────────────────
_CSS = r"""
.om{--om-panel:380px;color:var(--k-metin);font-size:13.5px;line-height:1.45;font-variant-numeric:tabular-nums}
.om *{box-sizing:border-box}
.om button,.om input,.om select{font:inherit;color:inherit}
.om button{cursor:pointer}
.om :focus-visible{outline:2px solid var(--k-mor);outline-offset:2px}
.om .govde{display:grid;grid-template-columns:minmax(0,1fr);gap:16px;align-items:start}
.om.detayli .govde{grid-template-columns:minmax(0,1fr) var(--om-panel)}
.om .ozet{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));background:var(--k-yuzey1);border:1px solid var(--k-kenar);
  border-radius:12px;margin-bottom:14px;overflow:hidden}
.om .ozet>*{all:unset;box-sizing:border-box;padding:13px 16px;border-right:1px solid var(--k-kenar);display:flex;flex-direction:column;gap:2px;min-width:0}
.om .ozet>*:last-child{border-right:0}
.om .ozet button{cursor:pointer}.om .ozet button:hover{background:var(--k-ortu2)}
.om .ozet button[aria-pressed="true"]{box-shadow:inset 0 -2px 0 var(--k-mor)}
.om .ozet .et{font-size:12px;color:var(--k-soluk);display:flex;align-items:center;gap:6px}
.om .ozet .dg{font-size:21px;font-weight:650;letter-spacing:-.4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.om .ozet .al{font-size:12px;color:var(--k-silik);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.om .nk{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block;flex-shrink:0}
.om .r-kirmizi{color:var(--k-kirmizi)}.om .r-amber{color:var(--k-amber)}.om .r-yesil{color:var(--k-yesil)}.om .r-silik{color:var(--k-silik)}
.om .ilr{height:4px;border-radius:2px;background:var(--k-kenar2);overflow:hidden;margin-top:6px}
.om .ilr i{display:block;height:100%;background:var(--k-yesil)}
.om .suz{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.om .cip{border:1px solid var(--k-kenar2);background:transparent;border-radius:999px;padding:4px 12px;font-size:12.5px;color:var(--k-soluk);
  display:inline-flex;gap:6px;align-items:center;white-space:nowrap}
.om .cip:hover{color:var(--k-metin)}
.om .cip[aria-pressed="true"]{background:var(--k-vurgu);border-color:color-mix(in srgb,var(--k-mor) 55%,transparent);color:var(--k-mor2);font-weight:600}
.om .cip .s{font-size:11px;opacity:.8}
.om .ayr{width:1px;height:20px;background:var(--k-kenar2);margin:0 2px}
.om select.cip{appearance:none;-webkit-appearance:none;padding-right:12px;background:transparent}
.om select.cip option{color:var(--k-metin);background:var(--k-yuzey1)}
.om .kutu{display:flex;align-items:center;gap:8px;border:1px solid var(--k-kenar2);background:var(--k-yuzey1);border-radius:8px;
  padding:5px 10px;margin-left:auto;min-width:220px;flex:0 1 300px}
.om .kutu input{border:0;background:transparent;outline:0;width:100%;font-size:13px}
.om .tablo{border:1px solid var(--k-kenar);border-radius:12px;background:var(--k-yuzey1);overflow:hidden}
.om .sat{display:grid;grid-template-columns:40px 96px minmax(150px,1fr) 104px 124px 104px 104px;align-items:center;
  border-bottom:1px solid var(--k-kenar);min-height:46px}
.om.detayli .sat{grid-template-columns:40px 92px minmax(130px,1fr) 118px 104px}
.om.detayli .c-k,.om.detayli .c-usd{display:none}
.om .sat>*{padding:0 10px;min-width:0}
.om .tutar{text-align:right}
.om .bsat{background:var(--k-yuzey2);min-height:36px;font-size:12px;color:var(--k-soluk);font-weight:500}
.om .bsat button{all:unset;cursor:pointer;display:inline-flex;gap:4px;align-items:center}
.om .bsat button:hover{color:var(--k-metin)}
.om .bsat .tutar button{justify-content:flex-end;width:100%}
.om .gun{display:flex;align-items:center;gap:10px;padding:12px 14px 6px;font-size:12.5px;color:var(--k-soluk);border-bottom:1px solid var(--k-kenar)}
.om .gun b{color:var(--k-metin);font-weight:600;font-size:13px}
.om .gun .num{margin-left:auto}
.om .satir{cursor:pointer}
.om .satir:hover{background:var(--k-ortu2)}
.om .satir.secili{background:var(--k-vurgu)}
.om .satir.odak{box-shadow:inset 3px 0 0 var(--k-mor)}
.om .satir.acik{background:var(--k-yuzey2)}
.om .satir.odendi{opacity:.55}
.om .satir.odendi .c-tl,.om .satir.odendi .c-usd{text-decoration:line-through;text-decoration-color:color-mix(in srgb,var(--k-metin) 35%,transparent)}
.om .firma{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.om .ack{color:var(--k-silik);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.om .vade{font-size:12.5px}.om .vade small{display:block;font-size:11.5px}
.om .etk{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:6px;background:var(--k-yuzey2);color:var(--k-soluk);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.om .drm{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:500;white-space:nowrap}
.om .onay{width:16px;height:16px;border-radius:4px;border:1.5px solid var(--k-kenar2);display:grid;place-items:center;background:transparent;padding:0}
.om .onay[aria-checked="true"],.om .onay[aria-checked="mixed"]{background:var(--k-dolgu);border-color:var(--k-dolgu)}
.om .onay[aria-checked="true"]::after{content:"";width:8px;height:4px;border-left:2px solid #fff;border-bottom:2px solid #fff;transform:rotate(-45deg) translate(1px,-1px)}
.om .onay[aria-checked="mixed"]::after{content:"";width:8px;height:2px;background:#fff}
.om .onay:disabled{opacity:.35;cursor:default}
.om .bos{padding:40px 20px;text-align:center;color:var(--k-soluk)}
.om .kisa{display:flex;gap:14px;flex-wrap:wrap;color:var(--k-silik);font-size:12px;margin-top:10px}
.om kbd{font-family:var(--k-mono,monospace);font-size:11px;border:1px solid var(--k-kenar2);border-radius:4px;padding:0 5px;color:var(--k-soluk)}
.om .panel{position:sticky;top:8px;border:1px solid var(--k-kenar);border-radius:12px;background:var(--k-yuzey1);
  max-height:calc(100vh - 24px);overflow:auto;display:flex;flex-direction:column}
.om .pbas{display:flex;align-items:flex-start;gap:10px;padding:16px 18px 12px;border-bottom:1px solid var(--k-kenar)}
.om .pbas h3{font-size:16px;margin:0;font-weight:650;line-height:1.3}
.om .pbas p{margin:2px 0 0;color:var(--k-soluk);font-size:12.5px}
.om .kapat{margin-left:auto;border:0;background:transparent;color:var(--k-silik);border-radius:6px;padding:2px 6px;font-size:18px;line-height:1}
.om .kapat:hover{color:var(--k-metin);background:var(--k-ortu2)}
.om .pgov{padding:14px 18px 18px;display:flex;flex-direction:column;gap:16px}
.om .buyuk{font-size:24px;font-weight:650;letter-spacing:-.5px}
.om .buyuk small{font-size:13px;color:var(--k-soluk);font-weight:500;margin-left:6px}
.om dl{display:grid;grid-template-columns:96px 1fr;gap:6px 12px;font-size:13px;margin:0}
.om dt{color:var(--k-silik)}.om dd{margin:0}
.om .sekmeler{display:flex;gap:2px;background:var(--k-yuzey2);border-radius:8px;padding:2px}
.om .sekmeler button{flex:1;border:0;background:transparent;border-radius:6px;padding:6px 8px;font-size:12.5px;color:var(--k-soluk);font-weight:500}
.om .sekmeler button[aria-pressed="true"]{background:var(--k-yuzey1);color:var(--k-metin);box-shadow:var(--k-golge)}
.om .form{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.om .form label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--k-soluk)}
.om .form .tam{grid-column:1/-1}
.om .form input,.om .form select{border:1px solid var(--k-kenar2);background:var(--k-yuzey0);border-radius:8px;padding:7px 10px;font-size:13px;width:100%}
.om .ipucu{font-size:12px;color:var(--k-silik);grid-column:1/-1}
.om .hata{font-size:12.5px;color:var(--k-kirmizi);grid-column:1/-1}
.om .eylem{display:flex;gap:8px;flex-wrap:wrap}
.om .dug{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid var(--k-kenar2);background:var(--k-yuzey1);
  border-radius:8px;padding:7px 12px;font-weight:500;font-size:13px;white-space:nowrap}
.om .dug:hover{background:var(--k-ortu2)}
.om .dug.bir{background:var(--k-dolgu);border-color:var(--k-dolgu);color:var(--k-dolgu-metin)}
.om .dug.bir:hover{filter:brightness(1.08)}
.om .dug.teh{color:var(--k-kirmizi)}
.om .dug:disabled{opacity:.5;cursor:default;filter:none}
.om .not{font-size:13px;color:var(--k-soluk);background:var(--k-ortu);border-radius:8px;padding:10px 12px}
.om .toplu{position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);display:flex;align-items:center;gap:8px;
  background:var(--k-yuzey3);border:1px solid var(--k-kenar2);border-radius:12px;padding:8px 8px 8px 14px;box-shadow:0 12px 40px rgba(0,0,0,.35);
  z-index:999990;max-width:calc(100% - 32px);flex-wrap:nowrap;white-space:nowrap}
.om .toplu select{border:1px solid var(--k-kenar2);background:var(--k-yuzey1);border-radius:8px;padding:6px 8px;font-size:13px;width:190px;min-width:0}
.om .bildirim{position:fixed;right:max(20px,env(safe-area-inset-right,0px));bottom:calc(84px + env(safe-area-inset-bottom,0px));background:var(--k-yuzey3);
  border:1px solid var(--k-kenar2);border-radius:10px;padding:10px 12px 10px 14px;display:flex;gap:12px;align-items:center;
  box-shadow:0 12px 40px rgba(0,0,0,.35);z-index:999991;font-size:13px;max-width:min(460px,calc(100% - 32px))}
.om .bildirim.kotu{border-color:color-mix(in srgb,var(--k-kirmizi) 50%,transparent)}
.om .bildirim button{border:0;background:transparent;color:var(--k-mor2);font-weight:600}
.om [hidden]{display:none !important}
@media (prefers-reduced-motion: reduce){.om *{transition:none !important}}
@media (max-width:900px){
  .om.detayli .govde{grid-template-columns:minmax(0,1fr)}
  .om .panel{position:fixed;inset:0;z-index:999980;border-radius:0;max-height:none;border:0}
  .om .ozet{grid-template-columns:repeat(2,minmax(0,1fr))}
  .om .ozet>*:nth-child(2){border-right:0}
  .om .ozet>*:nth-child(-n+2){border-bottom:1px solid var(--k-kenar)}
  .om .kutu{margin-left:0;flex:1 1 100%;min-width:0}
  .om .bsat,.om .kisa{display:none}
  .om .sat,.om.detayli .sat{grid-template-columns:36px minmax(0,1fr) auto;grid-template-areas:"o f t" "o v d";row-gap:2px;padding:9px 0}
  .om .c-o{grid-area:o}.om .c-f{grid-area:f}.om .c-v{grid-area:v}.om .c-tl{grid-area:t}.om .c-d{grid-area:d;text-align:right}
  .om .c-k,.om .c-usd{display:none}
  /* telefonda alttaki menünün (Ana sayfa · Modüller …) üstünde dursun */
  .om .toplu{bottom:calc(92px + env(safe-area-inset-bottom,0px));flex-wrap:wrap;white-space:normal;left:12px;right:12px;transform:none;max-width:none}
  .om .toplu select{flex:1 1 100%;width:auto}
  .om .bildirim{bottom:calc(92px + env(safe-area-inset-bottom,0px));left:12px;right:12px;max-width:none}
  .om.detayli .toplu{display:none}                      /* ayrıntı tam ekranken alttaki çubuk örtmesin */
  .om .gun{flex-wrap:wrap;row-gap:2px}
}
"""

_JS = r"""
export default function(component){
  const {data, setTriggerValue, parentElement} = component;
  const D = data || {};
  const S = parentElement.__om || (parentElement.__om = {gor:"bekleyen", kat:"", pb:"", q:"", sira:["vade",1], sec:new Set(),
                                                         acik:null, sekme:"ode", odak:0, sonBildirim:null, form:{}});
  let kok = parentElement.querySelector(".om");
  if (!kok){ kok = document.createElement("div"); kok.className = "om"; parentElement.appendChild(kok); }
  const O = D.odemeler || [];
  const varMi = new Set(O.map(o => o.id));
  for (const i of [...S.sec]) if (!varMi.has(i) || (O.find(o => o.id === i) || {}).durum === "odendi") S.sec.delete(i);
  if (S.acik !== null && !varMi.has(S.acik)) S.acik = null;
  const tr = (n, d=2) => Number(n||0).toLocaleString("tr-TR", {minimumFractionDigits:d, maximumFractionDigits:d});
  const tl = n => n ? "₺" + tr(n) : "", usd = n => n ? "$" + tr(n) : "";
  const iki = (a, b) => [tl(a), usd(b)].filter(Boolean).join(" + ") || "—";
  const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const kucuk = s => String(s||"").toLocaleLowerCase("tr-TR");
  const DUR = {gecikmis:["Gecikmiş","r-kirmizi"], bugun:["Bugün","r-amber"], yarin:["Yarın",""], ileri:["Bekliyor",""],
               odendi:["Ödendi","r-yesil"], tarihsiz:["Vadesiz","r-silik"]};
  const bekler = o => o.durum !== "odendi";
  const GOR = [["bekleyen","Bekleyen",bekler], ["gecikmis","Gecikmiş",o => o.durum==="gecikmis"],
               ["bugun","Bugün",o => o.durum==="bugun"], ["odendi","Ödendi",o => o.durum==="odendi"], ["tum","Tümü",() => true]];
  const gonder = (istek) => setTriggerValue("islem", {...istek, n: Date.now() + Math.random()});

  function suzulmus(){
    const g = (GOR.find(x => x[0] === S.gor) || GOR[0])[2], q = kucuk(S.q.trim());
    let r = O.filter(g).filter(o => !S.kat || o.kat === S.kat)
             .filter(o => S.pb === "tl" ? o.tl > 0 : S.pb === "usd" ? o.usd > 0 : true)
             .filter(o => !q || kucuk(`${o.firma} ${o.ack} ${o.kat_ad} ${o.tl_m} ${o.usd_m} ${o.tl} ${o.usd}`).includes(q));
    const [a, y] = S.sira;
    if (a !== "vade"){
      const v = o => a === "firma" ? kucuk(o.firma) : a === "tl" ? o.tl : o.usd;
      r = r.slice().sort((p, q2) => (v(p) > v(q2) ? 1 : v(p) < v(q2) ? -1 : 0) * y);
    } else if (y < 0) r = r.slice().reverse();
    return r;
  }

  function ozetHtml(){
    return `<div class="ozet">` + (D.ozet || []).map(k => {
      const ic = `<span class="et">${k.renk && k.renk !== "silik" && k.k !== "hafta_sonu" ? `<span class="nk r-${k.renk}"></span>` : ""}${e(k.et)}</span>
        <span class="dg ${k.k === "hafta_sonu" || (k.renk && k.renk !== "silik") ? "r-" + k.renk : ""}">${e(k.dg)}</span>
        <span class="al" title="${e(k.al)}">${e(k.al)}</span>${k.oran !== undefined ? `<span class="ilr"><i style="width:${Math.round(k.oran*100)}%"></i></span>` : ""}`;
      return k.suz ? `<button data-suz="${k.suz}" aria-pressed="${S.gor === k.suz}">${ic}</button>` : `<div title="${e(k.ipucu||"")}">${ic}</div>`;
    }).join("") + `</div>`;
  }

  function suzHtml(){
    const say = Object.fromEntries(GOR.map(([k,,f]) => [k, O.filter(f).length]));
    const katlar = (D.kategoriler || []).filter(k => O.some(o => o.kat === k.k));
    return `<div class="suz">` + GOR.map(([k, ad]) => `<button class="cip" data-gor="${k}" aria-pressed="${S.gor === k}">${ad} <span class="s">${say[k]}</span></button>`).join("")
      + `<span class="ayr"></span><select class="cip" data-kat aria-label="Kategori"><option value="">Tüm kategoriler</option>`
      + katlar.map(k => `<option value="${e(k.k)}" ${S.kat === k.k ? "selected" : ""}>${e(k.ad)}</option>`).join("") + `</select>`
      + `<button class="cip" data-pb="tl" aria-pressed="${S.pb === "tl"}">Yalnız TL</button><button class="cip" data-pb="usd" aria-pressed="${S.pb === "usd"}">Yalnız USD</button>`
      + `<label class="kutu"><input data-ara placeholder="Firma, açıklama ya da tutar  ( / )" value="${e(S.q)}" autocomplete="off" aria-label="Ödeme ara"></label></div>`;
  }

  function tabloHtml(r){
    const sec = r.filter(bekler);
    const hepsi = sec.length && sec.every(o => S.sec.has(o.id)), biraz = !hepsi && sec.some(o => S.sec.has(o.id));
    const ok = a => S.sira[0] === a ? (S.sira[1] > 0 ? " ↑" : " ↓") : "";
    let h = `<div class="tablo" role="grid" aria-label="Ödemeler"><div class="sat bsat" role="row">
      <div><button class="onay" data-hepsi role="checkbox" aria-checked="${hepsi ? "true" : biraz ? "mixed" : "false"}" aria-label="Görünen bekleyenlerin hepsini seç" ${D.salt || !sec.length ? "disabled" : ""}></button></div>
      <div><button data-sira="vade">Vade${ok("vade")}</button></div><div><button data-sira="firma">Firma${ok("firma")}</button></div>
      <div class="c-k">Kategori</div><div class="tutar"><button data-sira="tl">TL${ok("tl")}</button></div>
      <div class="tutar c-usd"><button data-sira="usd">USD${ok("usd")}</button></div><div>Durum</div></div>`;
    if (!r.length) h += `<div class="bos">${S.gor === "bekleyen" && !S.q && !S.kat && !S.pb ? "Bekleyen ödeme kalmadı. Ödenenleri görmek için 'Ödendi' ya da 'Tümü'." : "Bu süzgece uyan ödeme yok."}</div>`;
    let son = null;
    r.forEach((o, i) => {
      if (S.sira[0] === "vade" && o.vade !== son){
        son = o.vade;
        const g = r.filter(x => x.vade === o.vade);
        h += `<div class="gun"><b>${e(o.gun)}</b><span>${g.length} ödeme</span><span class="num">${iki(g.reduce((s,x)=>s+x.tl,0), g.reduce((s,x)=>s+x.usd,0))}</span></div>`;
      }
      const [dad, dsn] = DUR[o.durum] || ["", ""];
      const alt = o.durum === "odendi" ? (o.banka_ad ? e(o.banka_ad) : "ödendi") : o.fark === null ? "vadesiz"
                : o.fark < 0 ? `${-o.fark} gün gecikti` : o.fark === 0 ? "bugün" : o.fark === 1 ? "yarın" : `${o.fark} gün kaldı`;
      const altS = o.durum === "gecikmis" ? "r-kirmizi" : o.durum === "bugun" ? "r-amber" : "r-silik";
      h += `<div class="sat satir ${S.sec.has(o.id) ? "secili" : ""} ${S.acik === o.id ? "acik" : ""} ${i === S.odak ? "odak" : ""} ${o.durum === "odendi" ? "odendi" : ""}"
             role="row" data-id="${o.id}" data-i="${i}">
        <div class="c-o"><button class="onay" role="checkbox" aria-checked="${S.sec.has(o.id)}" data-sec="${o.id}" aria-label="Seç: ${e(o.firma)}" ${D.salt || o.durum === "odendi" ? "disabled" : ""}></button></div>
        <div class="c-v vade">${e(o.vade_kisa)}<small class="${altS}">${alt}</small></div>
        <div class="c-f"><div class="firma" title="${e(o.firma)}">${e(o.firma)}</div><div class="ack" title="${e(o.ack)}">${e(o.ack)}</div></div>
        <div class="c-k"><span class="etk">${e(o.kat_ad)}</span></div>
        <div class="c-tl tutar">${o.tl_m ? e(o.tl_m) : o.durum !== "odendi" && o.usd_m ? `<span class="r-silik">${e(o.usd_m)}</span>` : "<span class='r-silik'>—</span>"}</div>
        <div class="c-usd tutar">${o.usd_m ? e(o.usd_m) : "<span class='r-silik'>—</span>"}</div>
        <div class="c-d"><span class="drm ${dsn}"><span class="nk"></span>${dad}</span></div></div>`;
    });
    return h + `</div><div class="kisa"><span><kbd>j</kbd> <kbd>k</kbd> satır gez</span><span><kbd>x</kbd> seç</span><span><kbd>Enter</kbd> detay</span><span><kbd>Esc</kbd> kapat</span><span><kbd>/</kbd> ara</span></div>`;
  }

  function bankaSecenek(sec, para){
    const b = (D.bankalar || []).slice().sort((x, y) => (x.para !== para) - (y.para !== para));
    return `<option value="" ${sec === "" ? "selected" : ""} disabled>Banka seç…</option>` + b.map(x =>
      `<option value="${x.id}" ${String(sec) === String(x.id) ? "selected" : ""}>${e(x.ad)} · ${e(x.bakiye_m)}</option>`).join("")
      + `<option value="_bankasiz" ${sec === "_bankasiz" ? "selected" : ""}>Bakiyeden düşme (yalnız ödendi işaretle)</option>`;
  }

  function panelHtml(){
    const o = O.find(x => x.id === S.acik);
    if (!o) return "";
    const [dad, dsn] = DUR[o.durum] || ["", ""];
    const F = S.form[o.id] || (S.form[o.id] = {banka:"", tl:tr(o.tl).replace(/\./g, ""), usd:tr(o.usd).replace(/\./g, ""), vade:o.vade || D.bugun,
                                                dtl:tr(o.tl).replace(/\./g, ""), dusd:tr(o.usd).replace(/\./g, ""), kat:o.kat, ack:o.ack, sil:false, hata:""});
    let ic = "";
    if (D.salt) ic = `<div class="not">Salt-okur oturum: işlem yapılamaz.</div>`;
    else if (o.durum === "odendi") ic = `<div class="not">Ödendi${o.odendi_tarih ? " · " + e(o.odendi_tarih.split("-").reverse().join(".")) : ""}${o.banka_ad ? " · " + e(o.banka_ad) + " hesabından düşüldü" : " · bakiyeden düşülmedi"}</div>
        <div class="eylem"><button class="dug" data-geri="${o.id}">Geri al (bekliyor yap)</button></div>`;
    else {
      const sek = [["ode","Öde"],["otele","Ötele"],["duzenle","Düzenle"],["sil","Sil"]];
      ic = `<div class="sekmeler" role="group" aria-label="İşlem">${sek.map(([k,a]) => `<button data-sekme="${k}" aria-pressed="${S.sekme === k}">${a}</button>`).join("")}</div>`;
      if (S.sekme === "ode"){
        const para = o.usd && !o.tl ? "USD" : "TL";
        ic += `<div class="form">
          <label class="tam">Hangi bankadan ödendi?<select data-f="banka">${bankaSecenek(F.banka, para)}</select></label>
          ${o.tl ? `<label>Ödenen TL<input data-f="tl" inputmode="decimal" value="${e(F.tl)}"></label>` : ""}
          ${o.usd ? `<label>Ödenen USD<input data-f="usd" inputmode="decimal" value="${e(F.usd)}"></label>` : ""}
          <span class="ipucu">Tutarı küçültürseniz kısmi ödeme olur: ödenen kısım ayrı kayıt açılır, kalan aynı vadeyle listede kalır.</span>
          ${F.hata ? `<span class="hata" role="alert">${e(F.hata)}</span>` : ""}</div>
          <div class="eylem"><button class="dug bir" data-yap="ode" ${F.banka ? "" : "disabled"}>Öde</button></div>`;
      } else if (S.sekme === "otele"){
        ic += `<div class="eylem">${[1,3,7,30].map(g => `<button class="dug" data-gun="${g}">+${g} gün</button>`).join("")}</div>
          <div class="form"><label>Ya da tarih seç<input type="date" data-f="vade" value="${e(F.vade)}"></label>
          <label>&nbsp;<button class="dug bir" data-yap="otele" ${F.vade && F.vade !== o.vade ? "" : "disabled"}>Ötele</button></label>
          <span class="ipucu">Erteleme kaydı kalıcıdır (Ertelenen ödemeler'de görünür).</span>
          ${F.hata ? `<span class="hata" role="alert">${e(F.hata)}</span>` : ""}</div>`;
      } else if (S.sekme === "duzenle"){
        ic += `<div class="form"><label>Tutar TL<input data-f="dtl" inputmode="decimal" value="${e(F.dtl)}"></label>
          <label>Tutar USD<input data-f="dusd" inputmode="decimal" value="${e(F.dusd)}"></label>
          <label class="tam">Kategori<select data-f="kat">${(D.kategoriler || []).map(k => `<option value="${e(k.k)}" ${F.kat === k.k ? "selected" : ""}>${e(k.ad)}</option>`).join("")}</select></label>
          <label class="tam">Açıklama<input data-f="ack" value="${e(F.ack)}" maxlength="500"></label>
          ${F.hata ? `<span class="hata" role="alert">${e(F.hata)}</span>` : ""}</div>
          <div class="eylem"><button class="dug bir" data-yap="duzenle">Kaydet</button></div>`;
      } else {
        ic += `<div class="form"><label class="tam" style="flex-direction:row;align-items:center;gap:8px;color:var(--k-metin)">
          <input type="checkbox" data-f="sil" ${F.sil ? "checked" : ""} style="width:auto">Evet, ${e(o.firma)} ödemesini sil</label>
          <span class="ipucu">Kayıt kalıcı olarak silinir.</span></div>
          <div class="eylem"><button class="dug teh" data-yap="sil" ${F.sil ? "" : "disabled"}>Ödemeyi sil</button></div>`;
      }
    }
    return `<aside class="panel" aria-label="Ödeme ayrıntısı">
      <div class="pbas"><div><h3>${e(o.firma)}</h3><p>${e(o.ack)}</p></div><button class="kapat" data-kapat aria-label="Ayrıntıyı kapat">×</button></div>
      <div class="pgov">
        <div><div class="buyuk">${o.tl ? e(o.tl_m) : e(o.usd_m)}${o.tl && o.usd ? `<small>+ ${e(o.usd_m)}</small>` : ""}</div>
          <span class="drm ${dsn}"><span class="nk"></span>${dad}${o.durum === "gecikmis" ? ` · ${-o.fark} gün` : ""}</span></div>
        <dl><dt>Vade</dt><dd>${e(o.gun)}</dd><dt>Kategori</dt><dd><span class="etk">${e(o.kat_ad)}</span></dd>
          ${o.usd ? `<dt>TL karşılığı</dt><dd>${tl(o.tl_try)} <span class="r-silik">(kur ${e(D.kur_m)})</span></dd>` : ""}</dl>
        ${ic}</div></aside>`;
  }

  function topluHtml(){
    const s = O.filter(o => S.sec.has(o.id));
    if (!s.length || D.salt) return "";
    const b = S.form.__toplu || (S.form.__toplu = {banka:""});
    return `<div class="toplu" role="region" aria-label="Seçili ödemeler"><span><b>${s.length} ödeme seçili</b> · ${iki(s.reduce((a,o)=>a+o.tl,0), s.reduce((a,o)=>a+o.usd,0))}</span>
      <select data-tbanka aria-label="Hangi bankadan">${bankaSecenek(b.banka, "TL")}</select>
      <button class="dug bir" data-toplu="ode" ${b.banka ? "" : "disabled"}>Seçilenleri öde</button>
      <button class="dug" data-toplu="otele">+7 gün ötele</button>
      <button class="kapat" data-tkapat aria-label="Seçimi kaldır">×</button></div>`;
  }

  function bildirimHtml(){
    const b = D.bildirim;
    if (!b || S.sonBildirim === b.n) return "";
    return `<div class="bildirim ${b.ok ? "" : "kotu"}" role="status"><span>${e(b.mesaj)}</span>${b.geri_al && b.geri_al.length ? `<button data-gerial>Geri al</button>` : ""}</div>`;
  }

  const sayi = s => { const t = String(s ?? "").trim().replace(/\s/g, "").replace(/\./g, "").replace(",", "."); return t === "" ? 0 : Number(t); };

  function yap(tur, o){
    const F = S.form[o.id]; F.hata = "";
    if (tur === "ode"){
      const btl = o.tl ? sayi(F.tl) : 0, busd = o.usd ? sayi(F.usd) : 0;
      if (!(btl >= 0) || !(busd >= 0) || (btl === 0 && busd === 0)){ F.hata = "Ödenen tutarı girin."; return ciz(); }
      if (btl > o.tl + 1e-9 || busd > o.usd + 1e-9){ F.hata = `Ödenen tutar en çok ${iki(o.tl, o.usd)} olabilir.`; return ciz(); }
      const banka = F.banka === "_bankasiz" ? "_bankasiz" : Number(F.banka);
      const tam = Math.abs(btl - o.tl) < 0.005 && Math.abs(busd - o.usd) < 0.005;
      return gonder(tam ? {tur:"ode", ids:[o.id], banka} : {tur:"kismi", ids:[o.id], banka, tl:btl, usd:busd});
    }
    if (tur === "otele") return gonder({tur:"otele", ids:[o.id], vade:F.vade});
    if (tur === "duzenle"){
      const a = sayi(F.dtl), b = sayi(F.dusd);
      if (!(a >= 0) || !(b >= 0) || (a === 0 && b === 0)){ F.hata = "En az bir tutar (TL ya da USD) 0'dan büyük olmalı."; return ciz(); }
      return gonder({tur:"duzenle", ids:[o.id], tl:a, usd:b, kategori:F.kat, aciklama:F.ack});
    }
    if (tur === "sil") return gonder({tur:"sil", ids:[o.id]});
  }

  function ciz(){
    const r = suzulmus();
    S.gorunen = r;
    if (S.odak >= r.length) S.odak = Math.max(0, r.length - 1);
    kok.classList.toggle("detayli", S.acik !== null);
    const odakli = document.activeElement && kok.contains(document.activeElement) ? document.activeElement.getAttribute("data-f") || (document.activeElement.hasAttribute("data-ara") ? "ara" : null) : null;
    kok.innerHTML = ozetHtml() + suzHtml() + `<div class="govde"><div style="min-width:0">${tabloHtml(r)}</div>${panelHtml()}</div>` + topluHtml() + bildirimHtml();
    if (odakli === "ara"){ const a = kok.querySelector("[data-ara]"); a.focus(); a.setSelectionRange(a.value.length, a.value.length); }
    else if (odakli){ const a = kok.querySelector(`[data-f="${odakli}"]`); if (a){ a.focus(); if (a.setSelectionRange && a.type !== "date" && a.type !== "checkbox") a.setSelectionRange(a.value.length, a.value.length); } }
    if (D.bildirim && S.sonBildirim !== D.bildirim.n){
      const n = D.bildirim.n; clearTimeout(S.bz);
      S.bz = setTimeout(() => { S.sonBildirim = n; const b = kok.querySelector(".bildirim"); if (b) b.remove(); }, 7000);
    }
  }

  kok.onclick = (ev) => {
    const t = ev.target.closest("button, [data-id]");
    if (!t || !kok.contains(t)) return;
    const d = t.dataset;
    if (d.suz !== undefined){ S.gor = d.suz; S.odak = 0; return ciz(); }
    if (d.gor !== undefined){ S.gor = d.gor; S.odak = 0; return ciz(); }
    if (d.pb !== undefined){ S.pb = S.pb === d.pb ? "" : d.pb; return ciz(); }
    if (d.sira !== undefined){ S.sira = [d.sira, S.sira[0] === d.sira ? -S.sira[1] : 1]; return ciz(); }
    if (d.hepsi !== undefined){ const g = (S.gorunen || []).filter(bekler); const h = g.every(o => S.sec.has(o.id));
      g.forEach(o => h ? S.sec.delete(o.id) : S.sec.add(o.id)); return ciz(); }
    if (d.sec !== undefined){ ev.stopPropagation(); const i = Number(d.sec); S.sec.has(i) ? S.sec.delete(i) : S.sec.add(i); return ciz(); }
    if (d.kapat !== undefined){ S.acik = null; return ciz(); }
    if (d.sekme !== undefined){ S.sekme = d.sekme; return ciz(); }
    if (d.tkapat !== undefined){ S.sec.clear(); return ciz(); }
    if (d.gerial !== undefined){ S.sonBildirim = D.bildirim.n; return gonder({tur:"geri_al", ids:D.bildirim.geri_al}); }
    if (d.geri !== undefined) return gonder({tur:"geri_al", ids:[Number(d.geri)]});
    if (d.gun !== undefined) return gonder({tur:"otele", ids:[S.acik], gun:Number(d.gun)});
    if (d.yap !== undefined){ const o = O.find(x => x.id === S.acik); if (o) yap(d.yap, o); return; }
    if (d.toplu !== undefined){
      const ids = [...S.sec];
      if (d.toplu === "ode"){ const b = S.form.__toplu.banka; return gonder({tur:"ode", ids, banka: b === "_bankasiz" ? b : Number(b)}); }
      return gonder({tur:"otele", ids, gun:7});
    }
    if (d.id !== undefined){
      const i = Number(d.id); S.odak = Number(d.i);
      if (S.acik !== i){ S.acik = i; S.sekme = "ode"; } else S.acik = null;
      return ciz();
    }
  };
  kok.oninput = (ev) => {
    const t = ev.target, d = t.dataset;
    if (d.ara !== undefined){ S.q = t.value; S.odak = 0; return ciz(); }
    if (d.f !== undefined && S.acik !== null){
      const F = S.form[S.acik]; F[d.f] = t.type === "checkbox" ? t.checked : t.value; F.hata = "";
      if (["banka","vade","sil"].includes(d.f)) ciz();
    }
  };
  kok.onchange = (ev) => {
    const t = ev.target, d = t.dataset;
    if (d.kat !== undefined){ S.kat = t.value; S.odak = 0; return ciz(); }
    if (d.tbanka !== undefined){ S.form.__toplu.banka = t.value; return ciz(); }
    if (d.f === "kat" && S.acik !== null){ S.form[S.acik].kat = t.value; }
  };
  S.ciz = ciz;
  if (!parentElement.__omKlavye){
    parentElement.__omKlavye = true;
    document.addEventListener("keydown", (ev) => {
      const s = parentElement.__om;
      if (!parentElement.isConnected || !s || !s.ciz) return;
      const a = document.activeElement, yaz = a && (["INPUT","SELECT","TEXTAREA"].includes(a.tagName) || a.isContentEditable);
      if (ev.key === "Escape"){ if (yaz && kok.contains(a)) { a.blur(); return; } if (s.acik !== null){ s.acik = null; s.ciz(); } else if (s.sec.size){ s.sec.clear(); s.ciz(); } return; }
      if (yaz || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      if (document.querySelector('[role="dialog"]')) return;
      const r = s.gorunen || [];
      if (ev.key === "/"){ ev.preventDefault(); const k = parentElement.querySelector("[data-ara]"); if (k) k.focus(); }
      else if (ev.key === "j" || ev.key === "ArrowDown"){ if (!r.length) return; ev.preventDefault(); s.odak = Math.min(r.length - 1, s.odak + 1); s.ciz(); parentElement.querySelector(".satir.odak")?.scrollIntoView({block:"nearest"}); }
      else if (ev.key === "k" || ev.key === "ArrowUp"){ if (!r.length) return; ev.preventDefault(); s.odak = Math.max(0, s.odak - 1); s.ciz(); parentElement.querySelector(".satir.odak")?.scrollIntoView({block:"nearest"}); }
      else if (ev.key === "x" && r[s.odak] && r[s.odak].durum !== "odendi" && !D.salt){ const i = r[s.odak].id; s.sec.has(i) ? s.sec.delete(i) : s.sec.add(i); s.ciz(); }
      else if (ev.key === "Enter" && r[s.odak]){ s.acik = r[s.odak].id; s.sekme = "ode"; s.ciz(); }
    });
  }
  ciz();
}
"""

_BILESEN = None


def _bilesen():
    global _BILESEN
    if _BILESEN is None:
        import streamlit.components.v2 as _v2
        _BILESEN = _v2.component("kayran_odeme_masasi", css=_CSS, js=_JS)
    return _BILESEN


def ciz(veri, key="odeme_masasi"):
    """Bileşeni çizer; kullanıcı bir işlem yaptıysa YALNIZ o çalıştırmada isteği (dict) döner."""
    sonuc = _bilesen()(key=key, data=veri, height="content", on_islem_change=lambda: None)
    try:
        return getattr(sonuc, "islem")
    except Exception:  # noqa: BLE001
        return getattr(sonuc, "get", lambda *_: None)("islem")

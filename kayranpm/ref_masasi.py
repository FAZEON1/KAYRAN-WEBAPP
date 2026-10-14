# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Ref No Takibi — LİSTE MASALARI (Ekim 2026, ortak masa: shared/masa.py).

Ref No'lar : firma rayı (solda) ve Liste / Tablo seçimi eskisi gibi; liste ortak masada — özet bandı
             (seçili firmanın beklemede / paylaşıldı / USD toplamı), durum görünümleri, yıl seçimi, arama,
             döneme göre gruplu satırlar. Yan panelde tek tık: Paylaşıldı (seçilenlere toplu da) · Beklemeye al
             · İptal et → ref_ekran._durum_yaz (bugünkü N.ref_guncelle çağrısı, aynı argümanlar). Bilgileri
             düzenleme, kalemler ve silme bugünkü "Ref no detayı" penceresinde (Düzenle düğmesi).
             Kategori süzgeci sayfada (Python) kaldı: bir ref'in birden çok kategorisi olabilir, masanın
             seçimi tek değerli.
Alınan destekler: yıl seçimi sayfada; firma / tür seçimi, arama ve dönem grupları masada; yan panelde
             onaylı silme → N.alinan_destek_sil (eski pencereyle aynı).
Rakamlar ref_hesap'tan (USD karşılığı, toplam, dönem).

Geri almak için: kayranpm/ref_ekran.py → REF_MASASI_YENI = False.
"""
from shared.tasarim import sayi, tr_sayi

from . import ref_hesap as R
from .masa_ortak import kisa

_DURUM_ISLEM = {"paylas": "paylasildi", "bekle": "beklemede", "iptal": "iptal"}


def _usd(v):
    return "—" if v is None else sayi(v, "$")


def _tutar(r):
    d = R.doviz(r)
    return f"{R.SEMBOL.get(d, d + ' ')}{tr_sayi(R._f(r.get('tutar')), 2)}"


def _usd_alt(r, eur, tl):
    d = R.doviz(r)
    if d == "USD":
        return "USD"
    v = R.usd(r.get("tutar"), d, eur, tl)
    return f"≈ {sayi(v, '$')}" if v is not None else f"{d} · kur yok"


def _gun(s):
    s = str(s or "")[:10]
    return f"{s[8:10]}.{s[5:7]}.{s[:4]}" if len(s) == 10 and s[4] == "-" else s


def ref_ozet(kapsam, eur, tl):
    """Eski sağ panelin üç kartı (kpi_serit) — aynı toplamlar, aynı metinler."""
    bek = [r for r in kapsam if (r.get("durum") or "beklemede") == "beklemede"]
    pay = [r for r in kapsam if r.get("durum") == "paylasildi"]
    t_bek, t_pay = R.toplam(bek, eur, tl), R.toplam(pay, eur, tl)
    t_all = R.toplam([r for r in kapsam if r.get("durum") != "iptal"], eur, tl)
    ham = " · ".join(f"{R.SEMBOL.get(d, d)}{sayi(v)}" for d, v in sorted(t_all["ham"].items(), key=lambda x: -x[1]) if v)
    return [
        {"k": "beklemede", "et": "Beklemede", "dg": tr_sayi(len(bek)), "renk": "amber" if bek else "silik",
         "suz": "beklemede",
         "al": f"≈ {_usd(t_bek['usd'])} paylaşılmayı bekliyor" if bek else "paylaşılmamış ref yok"},
        {"k": "paylasildi", "et": "Paylaşıldı", "dg": tr_sayi(len(pay)), "renk": "yesil", "suz": "paylasildi",
         "al": f"≈ {_usd(t_pay['usd'])}"},
        {"k": "toplam", "et": "Toplam (USD karşılığı)", "dg": kisa(_usd(t_all["usd"])), "renk": "mor", "nokta": False,
         "al": ham or "—", "ipucu": "İptaller hariç. TL kayıtlı günlük kurla, EUR güncel kurla çevrildi."},
    ], t_all


def ref_verisi(kapsam, firma_goster, eur=None, tl=None, ozet_kaynak=None):
    """Ref No'lar masası. kapsam: seçili firmanın (ya da tümünün) ref'leri, kategori süzgecinden geçmiş.
    ozet_kaynak: özet bandının hesaplandığı ref'ler (eski ekranda süzgeçsiz firma kapsamı); yoksa kapsam.
    Sıra ve gruplar ref_hesap.grupla ile (en yeni dönem üstte, grup içinde ref no büyükten küçüğe)."""
    ozet, _t = ref_ozet(kapsam if ozet_kaynak is None else ozet_kaynak, eur, tl)
    satirlar = []
    for d, grup in R.grupla(kapsam):
        for r in grup:
            dk = r.get("durum") or "beklemede"
            parca = [x.strip() for x in str(r.get("aciklama") or "").split("·") if x.strip()]
            katlar = R.kategoriler(r)
            meta = [k.capitalize() for k in katlar[:3]] + [R.donem_metni(r)]
            if firma_goster:
                meta.append(r.get("_firma") or "")
            if len(parca) > 1:
                meta.append(f"{len(parca)} kalem")
            u = R.usd(r.get("tutar"), R.doviz(r), eur, tl)
            satirlar.append({
                "id": r.get("id"), "ref_no": str(r.get("ref_no") or "—"), "ack": " · ".join(parca) or "—",
                "meta": " · ".join(x for x in meta if x), "durum": dk, "durum_ad": R.DURUM_AD.get(dk, dk),
                "_durum": {"ad": R.DURUM_AD.get(dk, dk), "renk": R.DURUM_RENK.get(dk, "silik")},
                "ara_ek": f"{r.get('ref_no', '')} {r.get('aciklama', '')} {r.get('kategori', '')} "
                          f"{r.get('_firma', '')} {r.get('tutar', '')} {r.get('doviz', '')}",
                "yil": R.donem(r)[:4], "donem_ad": R.donem_adi(d),
                "tutar_m": _tutar(r), "tutar_m__s": u if u is not None else R._f(r.get("tutar")),
                "usd_alt": _usd_alt(r, eur, tl),
                "usd_top": (u or 0.0) if dk != "iptal" else 0.0,
                "_baslik": str(r.get("ref_no") or ""), "_alt": f"{r.get('_firma', '')} · {R.donem_metni(r)}",
                "_buyuk": _tutar(r), "_buyuk_alt": _usd_alt(r, eur, tl),
                "_detay": [x for x in (["Açıklama", " · ".join(parca)], ["Kategori", " · ".join(katlar)],
                                       ["Firma", r.get("_firma") or ""], ["Dönem", R.donem_metni(r)],
                                       ["Kayıt tarihi", _gun(r.get("tarih"))],
                                       ["Paylaşım", _gun(r.get("paylasim_tarihi"))]) if x[1]],
                "_soluk": dk == "iptal",
            })
    yillar = sorted({s["yil"] for s in satirlar if s["yil"]}, reverse=True)
    return {
        "ozet": ozet,
        "gorunumler": [{"k": "tumu", "ad": "Tümü", "f": []}]
                      + [{"k": d, "ad": R.DURUM_AD[d], "f": [["durum", "eq", d]]} for d in R.DURUMLAR],
        "secimler": [{"alan": "yil", "ad": "Tüm yıllar", "secenekler": [{"k": y, "ad": y} for y in yillar]}],
        "ara": {"alanlar": ["ara_ek"], "ipucu": "Ref no, açıklama, kategori, tutar…"},
        "sutunlar": [
            {"alan": "ref_no", "ad": "Ref no", "gen": "150px", "dar": "alt"},
            {"alan": "ack", "ad": "Açıklama", "tip": "ana", "alt": "meta"},
            {"alan": "tutar_m", "ad": "Tutar", "sag": True, "alt": "usd_alt", "gen": "140px", "dar": "sag"},
            {"alan": "durum_ad", "ad": "Durum", "tip": "durum", "gen": "116px", "genis": True},   # panelde de yazar
        ],
        "grup": {"alan": "donem_ad", "birim": "ref", "toplamlar": [{"alan": "usd_top", "on": "≈ $", "ondalik": 0}]},
        "satirlar": satirlar,
        "islemler": [
            {"k": "paylas", "ad": "Paylaşıldı", "dugme": "Paylaşıldı olarak işaretle", "birincil": True,
             "f": [["durum", "eq", "beklemede"]], "toplu": {"ad": "Paylaşıldı işaretle", "alanlar": []}},
            {"k": "bekle", "ad": "Beklemeye al", "f": [["durum", "ne", "beklemede"]], "coklu": True},
            {"k": "iptal", "ad": "İptal et", "f": [["durum", "ne", "iptal"]], "tehlike": True},
            {"k": "ac", "ad": "Düzenle", "dugme": "Düzenle · kalemler · sil", "okuma": True},
        ],
        "bos": {"liste": "Bu firmada henüz ref yok.", "suzgec": "Bu görünümde ref yok. Filtreyi ya da aramayı değiştir."},
        "baslik_ipucu": "Ref numaraları",
    }


def ref_yurutucu(kapsam, durum_yaz=None):
    """paylas / bekle / iptal → durum_yaz(ref, yeni) (varsayılan ref_ekran._durum_yaz: N.ref_guncelle).
    ac → bugünkü "Ref no detayı" penceresi (B.detay_ac("ref", id); render'ın sonunda açılır)."""
    sozluk = {r.get("id"): r for r in kapsam or []}

    def yurut(temiz):
        ids, islem = temiz["ids"], temiz["islem"]
        if islem == "ac":
            from shared import bilesen as B
            B.detay_ac("ref", ids[0])
            return {"ok": True, "yenileme": False, "sessiz": True}
        yeni = _DURUM_ISLEM.get(islem)
        if not yeni:
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        yaz = durum_yaz
        if yaz is None:
            from .ref_ekran import _durum_yaz as yaz
        hata = []
        for i in ids:
            if yaz(sozluk[i], yeni) is False:
                hata.append(i)
        ad = str(sozluk[ids[0]].get("ref_no") or "") if len(ids) == 1 else f"{len(ids)} ref"
        if hata:
            return {"ok": False, "mesaj": f"{len(hata)} ref güncellenemedi; durumu DEĞİŞMEDİ."}
        metin = {"paylasildi": "paylaşıldı olarak işaretlendi", "beklemede": "beklemeye alındı",
                 "iptal": "iptal edildi"}[yeni]
        return {"ok": True, "mesaj": f"{ad} {metin}",
                "geri": {"islem": "bekle", "ids": list(ids)} if yeni == "paylasildi" else None}
    return yurut


# ── Alınan destekler ────────────────────────────────────────────────
def alinan_verisi(kayitlar, yil, bugun, eur=None, tl=None, kat_ad=str):
    """Alınan destekler masası (seçili yılın kayıtları). Sıra eski ekranla aynı: dönem (yeni üstte),
    dönem içinde tutar büyükten küçüğe."""
    kayitlar = [dict(r, donem_=str(r.get("donem") or "")[:7]) for r in kayitlar or []]
    bu_ay = f"{bugun.year:04d}-{bugun.month:02d}"
    t = R.toplam(kayitlar, eur, tl)
    t_ay = R.toplam([r for r in kayitlar if r["donem_"] == bu_ay], eur, tl)
    ham = " · ".join(f"{R.SEMBOL.get(d, d)}{sayi(v)}" for d, v in sorted(t["ham"].items(), key=lambda x: -x[1]) if v)
    ozet = [
        {"k": "toplam", "et": f"{yil} toplam (USD karşılığı)", "dg": kisa(_usd(t["usd"])), "renk": "yesil",
         "nokta": False, "al": ham or "—"},
        {"k": "ay", "et": f"Bu ay · {R.donem_adi(bu_ay)}", "dg": kisa(_usd(t_ay["usd"])), "renk": "mor", "nokta": False,
         "al": f"{sum(1 for r in kayitlar if r['donem_'] == bu_ay)} kayıt"},
        {"k": "kayit", "et": "Kayıt", "dg": tr_sayi(len(kayitlar)), "renk": "cyan", "nokta": False,
         "al": f"{len({(r.get('firma') or '').strip() for r in kayitlar})} firma"},
    ]
    satirlar = []
    for d in sorted({r["donem_"] for r in kayitlar}, reverse=True):
        for r in sorted([x for x in kayitlar if x["donem_"] == d], key=lambda x: -R._f(x.get("tutar"))):
            u = R.usd(r.get("tutar"), R.doviz(r), eur, tl)
            tur, kat = (r.get("tur") or "").strip(), kat_ad(r.get("kategori") or "")
            fat = f"Fatura {r.get('fatura_no')}" if r.get("fatura_no") else ""
            satirlar.append({
                "id": r.get("id"), "firma": (r.get("firma") or "—").strip() or "—", "ack": r.get("aciklama") or "—",
                "tur": tur, "etk": " · ".join(x for x in (tur.capitalize(), kat) if x), "fat": fat,
                "ara_ek": f"{r.get('firma', '')} {r.get('aciklama', '')} {r.get('fatura_no', '')} "
                          f"{r.get('tutar', '')} {r.get('tur', '')} {r.get('kategori', '')}",
                "donem_ad": R.donem_adi(d), "tutar_m": _tutar(r),
                "tutar_m__s": u if u is not None else R._f(r.get("tutar")), "usd_alt": _usd_alt(r, eur, tl),
                "usd_top": u or 0.0,
                "_baslik": (r.get("firma") or "").strip(), "_alt": R.donem_adi(d),
                "_buyuk": _tutar(r), "_buyuk_alt": _usd_alt(r, eur, tl),
                "_detay": [x for x in (["Tür", r.get("tur")], ["Kategori", r.get("kategori")],
                                       ["Fatura no", r.get("fatura_no")], ["Açıklama", r.get("aciklama")]) if x[1]],
            })
    firmalar = sorted({s["firma"] for s in satirlar if s["firma"] != "—"})
    turler = sorted({s["tur"] for s in satirlar if s["tur"]})
    return {
        "ozet": ozet, "t": t,
        "secimler": [{"alan": "firma", "ad": "Tüm firmalar", "secenekler": [{"k": f, "ad": f} for f in firmalar]},
                     {"alan": "tur", "ad": "Tüm türler", "secenekler": [{"k": x, "ad": x.capitalize()} for x in turler]}],
        "ara": {"alanlar": ["ara_ek"], "ipucu": "Firma, açıklama, fatura no, tutar…"},
        "sutunlar": [
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "ack"},
            {"alan": "etk", "ad": "Tür · kategori", "alt": "fat", "gen": "200px", "dar": "alt"},
            {"alan": "tutar_m", "ad": "Tutar", "sag": True, "alt": "usd_alt", "gen": "140px", "dar": "sag"},
        ],
        "grup": {"alan": "donem_ad", "birim": "kayıt", "toplamlar": [{"alan": "usd_top", "on": "≈ $", "ondalik": 0}]},
        "satirlar": satirlar,
        "islemler": [{"k": "sil", "ad": "Sil", "dugme": "Kaydı sil", "tehlike": True,
                      "ipucu": "Kayıt düzeltmek için silip yeniden girin (değişiklik geçmişi bozulmasın).",
                      "alanlar": [{"ad": "onay", "et": "Evet, bu kaydı sil", "tip": "onay", "zorunlu": True}]}],
        "bos": {"liste": "Bu dönemde alınan destek yok.", "suzgec": "Filtreye uyan kayıt yok."},
        "baslik_ipucu": "Alınan destekler",
    }


def alinan_yurutucu():
    """Onaylı silme → N.alinan_destek_sil(id) (eski pencereyle aynı fonksiyon)."""
    def yurut(temiz):
        if temiz["islem"] != "sil":
            return {"ok": False, "mesaj": "Bilinmeyen işlem."}
        from . import ref_no as N
        if N.alinan_destek_sil(temiz["ids"][0]):
            return {"ok": True, "mesaj": "Kayıt silindi"}
        return {"ok": False, "mesaj": "Silinemedi — kayıt başkası tarafından silinmiş olabilir."}
    return yurut

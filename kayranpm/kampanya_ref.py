# -*- coding: utf-8 -*-
"""Kampanya kapanınca otomatik Ref No (Ekim 2026).

Kampanya Takip'te bir kampanya kapatılınca Ref No Takip'e kendiliğinden ref açılır:
  - Firma: kampanyanın firması → ref firması (ref_no.FIRMA_ESLESME: VATAN, HB, ITOPYA/EERA).
    Eşleşmeyen firmada (DİĞER) ref açılmaz; ekranda ve mailde "elle girilmeli" denir.
  - Tutar: kampanyanın toplam desteği = Σ (firma desteği + ek destek) × satılan adet, USD
    (kampanya_hesap.kampanya_ozet ile aynı hesap). Spiff varsa ayrıca TL ref (spiff_tl).
    Tutar 0 ise o ref açılmaz.
  - Açıklama "<kampanya adı> · Kampanya #<no>"; kategori kampanyanın kategorisi; dönem bitiş ayı;
    durum beklemede (onaylanınca Ref Takip'te "paylaşıldı" yapılır).
  - Aynı kampanya için ikinci kez açılmaz (yeniden açılıp kapatılsa da): açıklamadaki
    "Kampanya #<no>" işaretiyle bulunur.
Ref tutarları P&L'de destek gideri sayılır: aynı desteği ayrıca aylık toplu ref olarak elle girmek
onu iki kez saydırır. Kapatma önizlemesi aynı firma ve ayda elle girilmiş ref varsa uyarır.
Kapanınca kapatan kişiye ve İbrahim'e mail gider (shared.eposta).
"""
import re

ISARET = "Kampanya #{}"
YONETICI = "ibrahim"


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def isaret(kid):
    return ISARET.format(int(kid))


def _isaret_re(kid):
    return re.compile(r"Kampanya\s*#\s*" + str(int(kid)) + r"(?!\d)", re.IGNORECASE)


# ── Saf kurallar ────────────────────────────────────────────────────
def ref_firmasi_sec(kampanya_firma, firmalar):
    """Kampanyanın firması (VATAN, HB, ITOPYA, …) → ref firması kaydı ya da None."""
    from kayranpm.ref_no import _firma_rol
    rol = _firma_rol({"firma_adi": kampanya_firma, "firma_kodu": kampanya_firma})
    if not rol:
        return None
    adaylar = [f for f in (firmalar or []) if _firma_rol(f) == rol]
    return adaylar[0] if len(adaylar) == 1 else (min(adaylar, key=lambda f: int(f.get("id") or 0))
                                                if adaylar else None)


def ref_plani(kamp, urunler):
    """Açılacak ref'ler: [{tutar, doviz, aciklama, kategori, donem_ay, donem_yil, tur}]."""
    from kayranpm.kampanya_hesap import kampanya_ozet
    o = kampanya_ozet(kamp, urunler)
    ad = str(kamp.get("kampanya_adi") or "Kampanya").strip()
    kid = kamp.get("id")
    bit = str(kamp.get("bitis_tarihi") or kamp.get("baslangic_tarihi") or "")[:10]
    try:
        yil, ay = int(bit[:4]), int(bit[5:7])
    except ValueError:
        yil = ay = None
    ortak = {"kategori": str(kamp.get("kategori") or "").strip(), "donem_ay": ay, "donem_yil": yil}
    plan = []
    destek = round(_f(o.get("firma_destek")) + _f(o.get("ek_destek")), 2)
    if destek > 0:
        plan.append(dict(ortak, tur="destek", tutar=destek, doviz="USD",
                         aciklama=f"{ad} · {isaret(kid)}"))
    spiff_tl = round(_f(kamp.get("spiff_tl")), 2)
    if spiff_tl > 0:
        plan.append(dict(ortak, tur="spiff", tutar=spiff_tl, doviz="TL",
                         aciklama=f"{ad} SPIFF · {isaret(kid)}"))
    return plan


def mevcut_refler(refler, kid):
    """Bu kampanya için daha önce açılmış ref'ler (açıklamadaki işaretle)."""
    r = _isaret_re(kid)
    return [x for x in (refler or []) if r.search(str(x.get("aciklama") or ""))]


def _ref_donemleri(r):
    out = set()
    aylik = r.get("aylik")
    if isinstance(aylik, dict):
        out |= {str(k)[:7] for k in aylik}
    if not out and r.get("tarih"):
        out.add(str(r.get("tarih"))[:7])
    return out


def elle_benzerler(refler, plan_kalemi):
    """Aynı firma ve aynı dönemde ELLE girilmiş (kampanya işaretsiz), iptal olmayan ref'ler:
    aynı destek iki kez sayılmasın diye kapatmadan önce gösterilir."""
    if not plan_kalemi or not plan_kalemi.get("donem_yil"):
        return []
    donem = f"{plan_kalemi['donem_yil']}-{int(plan_kalemi['donem_ay']):02d}"
    return [r for r in (refler or [])
            if "kampanya #" not in str(r.get("aciklama") or "").lower()
            and str(r.get("durum") or "").lower() != "iptal"
            and str(r.get("doviz") or "USD").upper() == plan_kalemi["doviz"]
            and donem in _ref_donemleri(r)]


def onizleme(kamp, urunler, firmalar, refler_fn):
    """Kapatma ekranı için: {firma, plan, mevcut, benzer, sorun}. refler_fn(firma_id) → ref listesi."""
    plan = ref_plani(kamp, urunler)
    firma = ref_firmasi_sec(kamp.get("firma"), firmalar)
    if not firma:
        return {"firma": None, "plan": plan, "mevcut": [], "benzer": [],
                "sorun": f"'{kamp.get('firma') or '—'}' firması Ref No Takip'teki bir firmayla eşleşmiyor; "
                         "ref otomatik açılmaz, elle girilmeli."}
    refler = refler_fn(firma["id"]) or []
    benzer = []
    for p in plan:
        benzer += [r for r in elle_benzerler(refler, p) if r not in benzer]
    return {"firma": firma, "plan": plan, "mevcut": mevcut_refler(refler, kamp.get("id")),
            "benzer": benzer, "sorun": "" if plan else "Kampanyanın desteği 0 (satış adedi girilmemiş); ref açılmaz."}


# ── Kayıt ───────────────────────────────────────────────────────────
def kapaninca_ref_ac(kamp, urunler, firmalar, refler_fn, ref_ekle_fn, bugun):
    """Kampanya kapandı: plan kadar ref açar (zaten varsa açmaz). Döner
    {firma, acilan: [(ref_no, tutar, doviz)], mevcut: [ref_no], hatalar: [str], sorun: str}."""
    o = onizleme(kamp, urunler, firmalar, refler_fn)
    sonuc = {"firma": o["firma"], "acilan": [], "mevcut": [r.get("ref_no") for r in o["mevcut"]],
             "hatalar": [], "sorun": o["sorun"], "benzer": [r.get("ref_no") for r in o["benzer"]]}
    if not o["firma"] or sonuc["mevcut"]:
        return sonuc
    f = o["firma"]
    for p in o["plan"]:
        ok, ref_no = ref_ekle_fn(f["id"], f.get("firma_kodu", ""), p["aciklama"], "beklemede", bugun, None,
                                 p["tutar"], p["doviz"], p["kategori"], p["donem_ay"], p["donem_yil"])
        if ok:
            sonuc["acilan"].append((ref_no, p["tutar"], p["doviz"]))
        else:
            sonuc["hatalar"].append(f"{p['doviz']} ref açılamadı: {ref_no}")
    return sonuc


def _para(tutar, doviz):
    from shared.tasarim import tr_sayi
    return f"${tr_sayi(tutar, 2)}" if doviz == "USD" else f"{tr_sayi(tutar, 2)} {doviz}"


def ekran_mesaji(sonuc):
    """Kapatmadan sonra gösterilecek tek satır."""
    if sonuc.get("acilan"):
        return "Kampanya kapatıldı; ref açıldı: " + ", ".join(
            f"{r} ({_para(t, d)})" for r, t, d in sonuc["acilan"]) + "."
    if sonuc.get("mevcut"):
        return ("Kampanya kapatıldı; bu kampanyanın ref'i zaten var (" + ", ".join(sonuc["mevcut"])
                + "). Tutar değiştiyse Ref No Takip'te güncelle.")
    if sonuc.get("hatalar"):
        return "Kampanya kapatıldı ama ref açılamadı: " + "; ".join(sonuc["hatalar"])
    return f"Kampanya kapatıldı. {sonuc.get('sorun') or ''}".strip()


def mail_icerigi(kamp, sonuc, kapatan):
    """(konu, html) — kapatan kişiye ve İbrahim'e."""
    from shared import eposta as E
    ad = str(kamp.get("kampanya_adi") or "Kampanya")
    firma = (sonuc.get("firma") or {}).get("firma_adi") or kamp.get("firma") or "—"
    satir = "".join(f'<li><b>{E._e(r)}</b> · {E._e(_para(t, d))}</li>' for r, t, d in sonuc.get("acilan") or [])
    if satir:
        durum = f"<p>Ref No Takip'e işlendi (durum: beklemede):</p><ul>{satir}</ul>"
    elif sonuc.get("mevcut"):
        durum = (f"<p>Bu kampanyanın ref'i zaten vardı: <b>{E._e(', '.join(sonuc['mevcut']))}</b>. Yeni ref "
                 "açılmadı; tutar değiştiyse Ref No Takip'te güncelleyin.</p>")
    else:
        durum = (f"<p><b>Ref açılmadı.</b> {E._e(sonuc.get('sorun') or '')} "
                 f"{E._e('; '.join(sonuc.get('hatalar') or []))}</p>")
    uyari = (f"<p style=\"color:#b45309\">Aynı firma ve ayda elle girilmiş ref var: "
             f"{E._e(', '.join(sonuc['benzer']))}. Aynı destek orada da varsa P&amp;L'de iki kez sayılır; "
             "kontrol edin.</p>" if sonuc.get("benzer") and sonuc.get("acilan") else "")
    govde = (f"<p><b>{E._e(ad)}</b> kampanyası kapatıldı ({E._e(kapatan or '—')}).</p>"
             f"<p style=\"margin:2px 0\"><b>Firma:</b> {E._e(firma)} · <b>Kampanya no:</b> {E._e(kamp.get('id'))}</p>"
             f"{durum}{uyari}")
    konu = f"[KAYRAN Kampanya] {ad} kapatıldı" + (" · ref açıldı" if sonuc.get("acilan") else "")
    return konu, E.sablon("Kampanya kapatıldı", govde, "Ref No Takip'i aç", E.baglanti("kayranpm"))


def mail_alicilari(kapatan, adresler):
    """Kapatan kişi + İbrahim (aynı kişiyse bir kez); adresi olmayan atlanır."""
    kisiler = []
    for k in (str(kapatan or "").strip().lower(), YONETICI):
        if k and k not in kisiler:
            kisiler.append(k)
    return [adresler[k] for k in kisiler if adresler.get(k)]

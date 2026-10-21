# -*- coding: utf-8 -*-
"""Stok kartı penceresi — yeni tasarım (Ekim 2026, kullanıcı onaylı taslak).

Üstte kimlik (SKU, durum, ad, marka / kategori / barkod), yanında "Başka ürün aç"; altında özet bandı
(satılabilir stok, stok değeri, paçal, liste satış, satış hızı, yolda); sekmeler sayılarıyla. Özet:
stok nerede (bizim depolar + müşteriler tek çubukta), durum uyarıları, son hareketler, haftalık satış.
Satışlar: firma kartları + ortak liste masası (aya göre gruplu; satıra tıkla → bugünkü satış ayrıntısı).
Diğer sekmeler (Alımlar, Kampanya, İade, Analiz, Hareketler, Stok yaşı) eski pencereyle aynı gövdeler.

HESAP YOK: rakamların hepsi stok_karti.goster'in bugünkü hesaplarından gelir (veri sözlüğü). Buradaki saf
fonksiyonlar yalnız gösterim için düzenler (test: tests/test_stok_karti_yeni.py).
Geri almak için kayranpm/stok_karti.py → STOK_KARTI_YENI = False.
"""
import html as _h
from datetime import date, timedelta

from shared.tasarim import tr_sayi

SATILABILIR = ("MERKEZ", "HAPPY")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _e(s):
    return _h.escape(str(s if s is not None else ""))


def _usd(v, ondalik=2):
    f = _f(v)
    return ("-" if f < 0 else "") + "$" + tr_sayi(abs(f), ondalik)


def _gun(iso):
    s = str(iso or "")[:10]
    try:
        y, a, g = s.split("-")
        return f"{g}.{a}.{y}"
    except ValueError:
        return s or "—"


def _tarih(iso):
    try:
        return date.fromisoformat(str(iso or "")[:10])
    except ValueError:
        return None


def satilabilir_mi(depo):
    d = str(depo or "").upper().replace("İ", "I")
    return any(x in d for x in SATILABILIR)


# ── Saf düzenleyiciler (test edilir) ────────────────────────────────
def haftalik_seri(satislar, bugun, n=12):
    """Son n haftanın (pazartesi başlangıçlı, bu hafta dahil) satış adetleri: [(pazartesi, adet)]."""
    bu_pzt = bugun - timedelta(days=bugun.weekday())
    haftalar = [bu_pzt - timedelta(weeks=i) for i in range(n - 1, -1, -1)]
    adet = {h: 0.0 for h in haftalar}
    for s in satislar or []:
        t = _tarih(s.get("tarih"))
        if t is None:
            continue
        p = t - timedelta(days=t.weekday())
        if p in adet:
            adet[p] += _f(s.get("adet"))
    return [(h, adet[h]) for h in haftalar]


def son_hareketler(satislar, iadeler, alimlar, yolda_rows, firma_ad, bugun, n=5):
    """Satış, iade, alım (teslim alındı) ve yoldaki partiler tek zaman çizgisinde, en yeniden eskiye."""
    olay = []
    for s in satislar or []:
        t = _tarih(s.get("tarih"))
        if t:
            olay.append((t, "satis", f"Satış · {firma_ad(s.get('kanal')) or '—'} {tr_sayi(_f(s.get('adet')))} adet",
                         s.get("siparis_no") or ""))
    for r in iadeler or []:
        t = _tarih(r.get("tarih"))
        if t:
            olay.append((t, "iade", f"İade · {firma_ad(r.get('kanal')) or '—'} {tr_sayi(_f(r.get('iade_adet')))} adet",
                         "stoğa döndü"))
    for a in alimlar or []:
        t = _tarih(a.get("tarih"))
        if t:
            alt = " · ".join(x for x in (a.get("belge_no") or "", a.get("tedarikci") or "",
                                          f"{_usd(a.get('final_birim'))} final birim" if _f(a.get("final_birim")) else "") if x)
            olay.append((t, "alim", f"Alım · {tr_sayi(_f(a.get('adet')))} adet", alt))
    for y in yolda_rows or []:
        m = _f(y.get("yoldaki_miktar"))
        if m > 0:
            t = _tarih(y.get("tahmini_varis_tarihi"))
            olay.append((t or bugun, "yolda", f"Yolda · {tr_sayi(m)} adet",
                         " · ".join(x for x in (y.get("yoldaki_tedarikci") or "",
                                                f"varış {_gun(t.isoformat())}" if t else "varış belirsiz") if x)))
    olay.sort(key=lambda o: o[0], reverse=True)
    out = []
    for t, tur, baslik, alt in olay[:n]:
        gun = "bugün" if t == bugun else ("dün" if t == bugun - timedelta(days=1) else _gun(t.isoformat()))
        out.append({"tur": tur, "baslik": baslik, "alt": " · ".join(x for x in (gun, alt) if x)})
    return out


def durum_uyarilari(toplam_stok, yolda_adet, gunluk_hiz, uretim_suresi, pacal, liste, satis_var):
    """Analiz sekmesindeki kuralların özeti (aynı eşikler): sipariş zamanı, marj sağlığı, hareketsiz stok."""
    out = []
    if gunluk_hiz > 0:
        nokta = gunluk_hiz * uretim_suresi
        if toplam_stok + yolda_adet <= nokta:
            out.append({"tur": "uyari", "baslik": "Sipariş zamanı",
                        "alt": f"Stok + yolda {tr_sayi(toplam_stok + yolda_adet)}, yeniden sipariş noktası "
                               f"{tr_sayi(nokta)} ({tr_sayi(uretim_suresi)} gün tedarik)"})
    elif toplam_stok > 0 and not satis_var:
        out.append({"tur": "uyari", "baslik": "Hareketsiz stok", "alt": "Stok var ama satış geçmişi yok."})
    if pacal > 0 and liste > 0:
        marj = (liste - pacal) / liste * 100
        if liste <= pacal:
            out.append({"tur": "kotu", "baslik": "Zarar riski",
                        "alt": f"Liste satış {_usd(liste)} ≤ paçal maliyet {_usd(pacal)}"})
        elif marj < 10:
            out.append({"tur": "uyari", "baslik": "Düşük marj", "alt": f"Teorik marj %{tr_sayi(marj, 1)}"})
        else:
            out.append({"tur": "iyi", "baslik": "Marj sağlıklı", "alt": f"Teorik marj %{tr_sayi(marj, 1)}"})
    return out


def stok_yerleri(depo_satir, firma_stok_son, firma_ad):
    """Bizim depolar (satılabilir önce, adede göre) ve müşteriler (her firmanın son raporu)."""
    depolar = sorted(((str(d), _f(m), satilabilir_mi(d)) for d, m in dict(depo_satir or {}).items() if _f(m) > 0),
                     key=lambda x: (not x[2], -x[1]))
    son = {}
    for r in firma_stok_son or []:
        fa = firma_ad(r.get("firma", "")) or "—"
        ft = str(r.get("yukleme_tarihi") or "")[:10]
        if fa not in son or ft > son[fa][0]:
            son[fa] = (ft, _f(r.get("stok_miktari")), _f(r.get("haftalik_satis")))
        elif ft == son[fa][0]:            # aynı raporda iki kod (D-market iki ilan) → topla
            son[fa] = (ft, son[fa][1] + _f(r.get("stok_miktari")), son[fa][2] + _f(r.get("haftalik_satis")))
    musteriler = sorted(((fa, v[1], v[2], v[0]) for fa, v in son.items() if v[1] > 0), key=lambda x: -x[1])
    return {"depolar": depolar, "musteriler": musteriler}


def satis_masa_verisi(satislar, satir_kar, firma_ad, bugun):
    """Satışlar sekmesinin masa tanımı + firma kartları. Rakamlar satir_kar'dan (bugünkü sekmeyle aynı)."""
    ay_ad = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
             "Kasım", "Aralık"]
    s90 = (bugun - timedelta(days=90)).isoformat()
    bu_ay = bugun.isoformat()[:7]
    satirlar, firmalar = [], {}
    for i, s in enumerate(satislar or []):
        k = satir_kar(s) if satir_kar else {}
        adet, ciro, kar, marj = _f(k.get("adet")), _f(k.get("ciro")), _f(k.get("net_kar")), _f(k.get("marj"))
        tarih = str(s.get("tarih") or "")[:10]
        fa = firma_ad(s.get("kanal")) or (s.get("kanal") or "—")
        fo = firmalar.setdefault(fa, {"adet": 0.0, "ciro": 0.0, "kar": 0.0})
        fo["adet"] += adet; fo["ciro"] += ciro; fo["kar"] += kar
        ay = f"{ay_ad[int(tarih[5:7]) - 1]} {tarih[:4]}" if len(tarih) >= 7 and tarih[5:7].isdigit() else "Tarihsiz"
        satirlar.append({
            "id": i, "tarih": _gun(tarih)[:5] if tarih else "—", "tarih__s": tarih, "ay": ay, "ay_k": tarih[:7],
            "son90": tarih >= s90, "bu_ay": tarih[:7] == bu_ay,
            "firma": fa, "firma_tam": (s.get("kanal") or "") if (s.get("kanal") or "") != fa else "",
            "siparis": s.get("siparis_no") or "—", "adet": adet, "adet_m": tr_sayi(adet), "adet_m__s": adet,
            "birim": _usd(s.get("birim_satis")), "birim__s": _f(s.get("birim_satis")),
            "kar_m": _usd(kar), "kar_m__s": kar, "marj_m": f"%{tr_sayi(marj, 1)}", "ciro": ciro,
            "_marj_renk": "yesil" if marj >= 10 else ("amber" if marj >= 0 else "kirmizi"),
            "_baslik": fa, "_alt": f"{_gun(tarih)} · {s.get('siparis_no') or '—'}",
            "_buyuk": _usd(kar), "_buyuk_alt": f"net kâr · %{tr_sayi(marj, 1)}",
        })
    kartlar = [{"ad": fa, "adet": v["adet"], "ciro": v["ciro"],
                "marj": (v["kar"] / v["ciro"] * 100) if v["ciro"] else 0.0}
               for fa, v in sorted(firmalar.items(), key=lambda x: -x[1]["adet"])]
    veri = {
        "gorunumler": [{"k": "tumu", "ad": "Tümü", "f": []},
                       {"k": "ay", "ad": "Bu ay", "f": [["bu_ay", "eq", True]]},
                       {"k": "s90", "ad": "Son 90 gün", "f": [["son90", "eq", True]]}],
        "secimler": [{"alan": "firma", "ad": "Tüm firmalar",
                      "secenekler": [{"k": k["ad"], "ad": k["ad"]} for k in kartlar]}],
        "ara": {"alanlar": ["siparis", "firma", "firma_tam"], "ipucu": "Sipariş no, firma"},
        "sutunlar": [
            {"alan": "tarih", "ad": "Tarih", "gen": "80px", "dar": "alt"},
            {"alan": "firma", "ad": "Firma", "tip": "ana", "alt": "firma_tam"},
            {"alan": "siparis", "ad": "Sipariş", "gen": "150px", "genis": True},
            {"alan": "adet_m", "ad": "Adet", "sag": True, "gen": "70px"},
            {"alan": "birim", "ad": "Birim", "sag": True, "gen": "90px", "genis": True},
            {"alan": "kar_m", "ad": "Net kâr", "sag": True, "gen": "110px", "alt": "marj_m",
             "alt_renk": "_marj_renk", "dar": "sag"},
        ],
        "grup": {"alan": "ay", "birim": "satış",
                 "toplamlar": [{"alan": "adet", "son": " adet", "ondalik": 0}, {"alan": "ciro", "on": "$"}]},
        "satirlar": satirlar,
        "islemler": [{"k": "ac", "ad": "Ayrıntı", "dugme": "Satış ayrıntısı", "okuma": True}],
        "tik": "ac",
        "bos": {"liste": "Bu ürünün satış kaydı yok.", "suzgec": "Bu süzgece uyan satış yok."},
    }
    return veri, kartlar


# ── Görünüm ─────────────────────────────────────────────────────────
CSS = """<style>
.skn-bas{display:flex;flex-direction:column;gap:6px;padding:2px 0 4px}
.skn-ust{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.skn-sku{font:700 13px var(--k-mono);color:var(--k-mor2);background:color-mix(in srgb,var(--k-mor) 14%,transparent);
  padding:3px 8px;border-radius:6px;letter-spacing:.2px}
.skn-durum{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600}
.skn-durum i{width:7px;height:7px;border-radius:50%;background:currentColor}
.skn-ad{font-size:20px;font-weight:650;letter-spacing:-.2px;color:var(--k-metin);line-height:1.25}
.skn-meta{display:flex;gap:6px;flex-wrap:wrap}
.skn-cip{font-size:12px;color:var(--k-soluk);border:1px solid var(--k-kenar2);border-radius:999px;padding:2px 10px}
.skn-cip b{color:var(--k-metin);font-weight:600}
.skn-bant{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:var(--k-kenar);
  border:1px solid var(--k-kenar);border-radius:12px;overflow:hidden;margin:8px 0 4px}
.skn-h{background:var(--k-yuzey1);padding:11px 15px;min-width:0}
.skn-h .e{font-size:12px;color:var(--k-soluk)}
.skn-h .d{font-size:20px;font-weight:650;margin-top:1px;letter-spacing:-.3px;color:var(--k-metin);white-space:nowrap}
.skn-h .d small{font-size:12.5px;color:var(--k-soluk);font-weight:500}
.skn-h .a{font-size:11.5px;color:var(--k-silik);margin-top:1px}
.skn-ye{color:var(--k-yesil) !important}.skn-ki{color:var(--k-kirmizi) !important}.skn-am{color:var(--k-amber) !important}
.skn-cy{color:var(--k-cyan) !important}
.skn-kut{border:1px solid var(--k-kenar);border-radius:12px;background:var(--k-yuzey1);padding:12px 16px 14px;height:100%}
.skn-kut h4{margin:0 0 8px;font-size:13px;font-weight:600;color:var(--k-metin);display:flex;gap:8px;align-items:baseline}
.skn-kut h4 small{font-weight:500;color:var(--k-silik);font-size:12px}
.skn-cubuk{display:flex;height:10px;border-radius:5px;overflow:hidden;gap:2px;margin:4px 0 12px}
.skn-cubuk i{display:block;min-width:3px}
.skn-iki{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.skn-ab{font-size:11px;letter-spacing:.07em;color:var(--k-silik);margin:0 0 2px}
.skn-sat{display:grid;grid-template-columns:10px 1fr auto;gap:10px;align-items:center;padding:6px 0;
  border-top:1px solid var(--k-kenar)}
.skn-sat .n{width:9px;height:9px;border-radius:3px}
.skn-sat .t{font-size:13px;color:var(--k-metin);min-width:0}
.skn-sat .t small{display:block;color:var(--k-silik);font-size:11.5px}
.skn-sat .v{font:600 13px var(--k-mono);color:var(--k-metin)}
.skn-bos{color:var(--k-silik);font-size:12.5px;padding:6px 0}
.skn-not{font-size:12px;color:var(--k-amber);margin-top:6px}
.skn-uy{display:flex;gap:10px;padding:9px 12px;border-radius:10px;margin-top:8px;font-size:13px;
  background:color-mix(in srgb,var(--k-amber) 9%,transparent);border:1px solid color-mix(in srgb,var(--k-amber) 28%,transparent)}
.skn-uy.iyi{background:color-mix(in srgb,var(--k-yesil) 8%,transparent);border-color:color-mix(in srgb,var(--k-yesil) 25%,transparent)}
.skn-uy.kotu{background:color-mix(in srgb,var(--k-kirmizi) 9%,transparent);border-color:color-mix(in srgb,var(--k-kirmizi) 28%,transparent)}
.skn-uy b{display:block;color:var(--k-metin);font-weight:600}.skn-uy span{color:var(--k-soluk);font-size:12px}
.skn-uy .ik{font-family:"Material Symbols Rounded";font-size:18px;line-height:1.2;font-feature-settings:"liga"}
.skn-zc{position:relative;padding-left:18px}
.skn-zc:before{content:"";position:absolute;left:4px;top:8px;bottom:8px;width:1px;background:var(--k-kenar2)}
.skn-zo{position:relative;padding:4px 0}
.skn-zo:before{content:"";position:absolute;left:-18px;top:9px;width:9px;height:9px;border-radius:50%;
  background:var(--k-yuzey1);border:2px solid var(--c,var(--k-mor))}
.skn-zo b{font-weight:600;font-size:13px;color:var(--k-metin)}.skn-zo span{display:block;color:var(--k-silik);font-size:12px}
.skn-graf{display:flex;align-items:flex-end;gap:6px;height:80px}
.skn-graf i{flex:1;background:color-mix(in srgb,var(--k-mor) 62%,transparent);border-radius:4px 4px 0 0;min-height:2px}
.skn-graf i.son{background:var(--k-mor)}
.skn-eks{display:flex;justify-content:space-between;font-size:10.5px;color:var(--k-silik);margin-top:4px}
.skn-kanal{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:2px 0 10px}
.skn-kn{border:1px solid var(--k-kenar);border-radius:10px;padding:10px 12px;background:var(--k-yuzey1);min-width:0}
.skn-kn .e{font-size:12px;color:var(--k-soluk);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.skn-kn .d{font-weight:650;font-size:16px;color:var(--k-metin)}.skn-kn small{color:var(--k-silik);font-size:11.5px}
.skn-kn .p{height:4px;background:var(--k-yuzey3);border-radius:2px;margin-top:8px}
.skn-kn .p i{display:block;height:4px;border-radius:2px;background:var(--k-mor)}
/* sekmeler: alt çizgili, zeminsiz (Ürün yönetiminin genel sekme zemini pencerede ezilir), sayılar sönük */
html body section[role="dialog"] .stTabs [data-testid="stTab"]{background:transparent !important;border-radius:0 !important;
  padding:9px 12px !important;box-shadow:none !important}
html body section[role="dialog"] .stTabs [data-testid="stTab"] p{font-size:13.5px !important;color:var(--k-soluk) !important}
html body section[role="dialog"] .stTabs [data-testid="stTab"][aria-selected="true"] p{color:var(--k-metin) !important;
  font-weight:600 !important}
@media (max-width:760px){
  .skn-bant{grid-template-columns:repeat(2,minmax(0,1fr))}.skn-iki{grid-template-columns:1fr}
  .skn-kanal{grid-template-columns:1fr 1fr}.skn-ad{font-size:17px}
}
</style>"""

# Tonlar temanın renklerinden (sabit renk kodu yok — tests/test_tema): ana renk, sonra yüzeye karışarak koyulaşır
def _tonlar(ana, n):
    return [ana] + [f"color-mix(in srgb,{ana} {100 - 14 * i}%,var(--k-yuzey1))" for i in range(1, n)]


_RENK_DEPO = _tonlar("var(--k-yesil)", 4)
_RENK_GRI = _tonlar("var(--k-silik)", 4)
_RENK_MUS = _tonlar("var(--k-mor)", 6)
_TUR_RENK = {"satis": "var(--k-yesil)", "iade": "var(--k-amber)", "alim": "var(--k-mor)", "yolda": "var(--k-cyan)"}
_UY_IKON = {"uyari": ("warning", "skn-am"), "iyi": ("check", "skn-ye"), "kotu": ("error", "skn-ki")}


def _bas_html(sku, u, toplam_stok, marka, kategori, ilk, ek=()):
    if toplam_stok > 0:
        durum = f'<span class="skn-durum skn-ye"><i></i>Stokta · {tr_sayi(toplam_stok)} adet satılabilir</span>'
    else:
        durum = '<span class="skn-durum skn-ki"><i></i>Satılabilir stok yok</span>'
    cipler = [("Marka", marka), ("Kategori", kategori), ("Barkod", u.get("barkod")), ("İlk görülme", ilk)]
    cipler += list(ek or ())                 # Mikro'dan: garanti, GTİP, ağırlık, ölçü (kayranpm.mikro_urun)
    return (f'<div class="skn-bas"><div class="skn-ust"><span class="skn-sku">{_e(sku)}</span>{durum}</div>'
            f'<div class="skn-ad">{_e(u.get("urun_adi") or "—")}</div><div class="skn-meta">'
            + "".join(f'<span class="skn-cip">{_e(a)} <b>{_e(d)}</b></span>' for a, d in cipler if d)
            + "</div></div>")


def _bant_html(v, musteri_toplam):
    ts, hz = v["toplam_stok"], v["haftalik_gercek"]
    alt1 = [f"kanal dahil {tr_sayi(ts + musteri_toplam)}"]
    if v["g5f_toplam"] and v["g5f_toplam"] != ts:
        alt1.append(f"tüm depolar {tr_sayi(v['g5f_toplam'])}")
    liste, pacal = v["liste_fiyat"], v["pacal_final"]
    marj = ((liste - pacal) / liste * 100) if (liste > 0 and pacal > 0) else None
    marj_alt = (f'<span class="{"skn-ye" if marj >= 10 else ("skn-am" if marj > 0 else "skn-ki")}">'
                f'teorik marj %{tr_sayi(marj, 1)}</span>') if marj is not None else "güncel"
    if hz > 0 and ts > 0:
        hiz_alt = f"~{tr_sayi(ts / hz)} hafta yeter"
    else:
        hiz_alt = "son 90 günde satış yok" if v["satislar"] else "satış verisi yok"
    varis = sorted(str(r.get("tahmini_varis_tarihi") or "")[:10] for r in v["yolda_rows"]
                   if _f(r.get("yoldaki_miktar")) > 0 and r.get("tahmini_varis_tarihi"))
    hucre = [
        ("Satılabilir stok", tr_sayi(ts), " · ".join(alt1), ""),
        ("Stok değeri", _usd(v["stok_degeri"], 0), "paçal × satılabilir", ""),
        ("Paçal maliyet", _usd(pacal), (f"canlı paçal {_usd(v['canli']['pacal'])}" if v.get("canli") else
                                         (v.get("canli_aciklama") or "")), ""),
        ("Liste satış", _usd(liste), marj_alt, ""),
        ("Satış hızı", f"{tr_sayi(hz, 1 if 0 < hz < 10 else 0)} <small>/hafta</small>", hiz_alt, ""),
        ("Yolda", tr_sayi(v["yolda_adet"]), (f"varış {_gun(varis[0])}" if varis else "yolda mal yok"),
         "skn-cy" if v["yolda_adet"] > 0 else ""),
    ]
    return ('<div class="skn-bant">' + "".join(
        f'<div class="skn-h"><div class="e">{e}</div><div class="d {c}">{d}</div><div class="a">{a}</div></div>'
        for e, d, a, c in hucre) + "</div>")


def _yer_html(yer, kanal_toplam, sat_kontrol):
    dep, mus = yer["depolar"], yer["musteriler"]
    toplam = sum(x[1] for x in dep) + sum(x[1] for x in mus)
    i_s = i_g = 0
    parca, sat_d = [], []
    for ad, adet, sat in dep:
        if sat:
            renk = _RENK_DEPO[min(i_s, 3)]; i_s += 1
        else:
            renk = _RENK_GRI[min(i_g, 3)]; i_g += 1
        parca.append(f'<i style="flex:{adet:g};background:{renk}"></i>')
        sat_d.append(f'<div class="skn-sat"><i class="n" style="background:{renk}"></i><div class="t">{_e(ad.title())}'
                     f'<small>{"satılabilir" if sat else "fiziksel takip"}</small></div><div class="v">{tr_sayi(adet)}</div></div>')
    sat_m = []
    for j, (fa, adet, haftalik, ft) in enumerate(mus):
        renk = _RENK_MUS[min(j, len(_RENK_MUS) - 1)]
        parca.append(f'<i style="flex:{adet:g};background:{renk}"></i>')
        alt = " · ".join(x for x in ((f"haftada {tr_sayi(haftalik)} satıyor" if haftalik else ""), _gun(ft) if ft else "") if x)
        sat_m.append(f'<div class="skn-sat"><i class="n" style="background:{renk}"></i><div class="t">{_e(fa)}'
                     f'<small>{_e(alt)}</small></div><div class="v">{tr_sayi(adet)}</div></div>')
    not_ = ""
    if sat_kontrol and sat_kontrol.get("fark"):
        fk = sat_kontrol["fark"]
        not_ = (f'<div class="skn-not">Satılabilir kayıtlı {tr_sayi(sat_kontrol["kayitli"])}, kırılıma göre '
                f'{tr_sayi(sat_kontrol["hesap"])} (fark {"+" if fk > 0 else "−"}{tr_sayi(abs(fk))}) — G5F sayımını yeniden yükle</div>')
    return (f'<div class="skn-kut"><h4>Stok nerede <small>toplam {tr_sayi(toplam)} adet</small></h4>'
            + (f'<div class="skn-cubuk">{"".join(parca)}</div>' if parca else "")
            + '<div class="skn-iki"><div><div class="skn-ab">BİZİM DEPOLAR</div>'
            + ("".join(sat_d) or '<div class="skn-bos">Depolarda adet yok (G5F sayımı yüklenmemiş olabilir).</div>')
            + not_ + '</div><div><div class="skn-ab">MÜŞTERİLERDE</div>'
            + ("".join(sat_m) or '<div class="skn-bos">Müşterilerde stok kaydı yok.</div>')
            + "</div></div></div>")


def _durum_html(uyarilar):
    if not uyarilar:
        return ""
    ic = "".join(
        f'<div class="skn-uy {u["tur"] if u["tur"] != "uyari" else ""}"><span class="ik {_UY_IKON[u["tur"]][1]}">'
        f'{_UY_IKON[u["tur"]][0]}</span><div><b>{_e(u["baslik"])}</b><span>{_e(u["alt"])}</span></div></div>'
        for u in uyarilar)
    return f'<div class="skn-kut" style="margin-bottom:14px"><h4>Durum</h4>{ic}</div>'


def _hareket_html(olaylar):
    if not olaylar:
        ic = '<div class="skn-bos">Kayıtlı hareket yok.</div>'
    else:
        ic = '<div class="skn-zc">' + "".join(
            f'<div class="skn-zo" style="--c:{_TUR_RENK[o["tur"]]}"><b>{_e(o["baslik"])}</b><span>{_e(o["alt"])}</span></div>'
            for o in olaylar) + "</div>"
    return f'<div class="skn-kut"><h4>Son hareketler</h4>{ic}</div>'


def _grafik_html(seri):
    en = max((a for _, a in seri), default=0)
    if en <= 0:
        return ('<div class="skn-kut" style="margin-top:14px"><h4>Haftalık satış <small>son 12 hafta</small></h4>'
                '<div class="skn-bos">Son 12 haftada satış yok.</div></div>')
    cub = "".join(f'<i class="{"son" if i == len(seri) - 1 else ""}" style="height:{a / en * 100:.1f}%" '
                  f'title="{_gun(h.isoformat())} haftası: {tr_sayi(a)} adet"></i>' for i, (h, a) in enumerate(seri))
    orta = [seri[0][0], seri[len(seri) // 3][0], seri[2 * len(seri) // 3][0]]
    eks = "".join(f"<span>{_gun(h.isoformat())[:5]}</span>" for h in orta) + "<span>bu hafta</span>"
    top = sum(a for _, a in seri)
    return (f'<div class="skn-kut" style="margin-top:14px"><h4>Haftalık satış <small>son 12 hafta · '
            f'{tr_sayi(top)} adet</small></h4><div class="skn-graf">{cub}</div><div class="skn-eks">{eks}</div></div>')


def _kanal_html(kartlar):
    if not kartlar:
        return ""
    en = max(k["adet"] for k in kartlar) or 1
    return '<div class="skn-kanal">' + "".join(
        f'<div class="skn-kn"><div class="e">{_e(k["ad"])}</div><div class="d">{tr_sayi(k["adet"])} adet</div>'
        f'<small>{_usd(k["ciro"], 0)} ciro · %{tr_sayi(k["marj"], 1)}</small>'
        f'<div class="p"><i style="width:{k["adet"] / en * 100:.0f}%"></i></div></div>' for k in kartlar[:4]) + "</div>"


def _firma_ad_fn():
    try:
        from shared.utils import firma_gorunen_ad
        return lambda k: firma_gorunen_ad(k) if k else ""
    except Exception:  # noqa: BLE001
        return lambda k: str(k or "")


def ciz(sku, v, govdeler, satis_detay):
    """v: stok_karti.goster'in hesapladığı değerler · govdeler: eski pencerenin sekme gövdeleri ·
    satis_detay(satir): bugünkü satış ayrıntısı."""
    import streamlit as st
    from shared.ana_veri import kategori_ad, marka_ad
    from kayranpm.stok_karti import baska_sku_secici
    try:
        from shared.utils import tr_today
        bugun = tr_today()
    except Exception:  # noqa: BLE001
        bugun = date.today()
    fa = _firma_ad_fn()
    u = v["urun"]
    musteri_toplam = sum(sum(_f(x) for x in d.values()) for d in (v["kanal_stok"] or {}).values())

    st.markdown(CSS, unsafe_allow_html=True)
    c1, c2 = st.columns([2.2, 1], vertical_alignment="top")
    from .mikro_urun import kart_cipleri
    c1.markdown(_bas_html(sku, u, v["toplam_stok"], marka_ad(u.get("marka")), kategori_ad(u.get("kategori")),
                          _gun(v["ilk_gorulen"]) if v["ilk_gorulen"] else "", ek=kart_cipleri(sku)),
                unsafe_allow_html=True)
    with c2:
        baska_sku_secici(sku, "Başka ürün aç · SKU ya da model")
    st.markdown(_bant_html(v, musteri_toplam), unsafe_allow_html=True)

    sayi = lambda n: f" :gray[{n}]" if n else ""   # noqa: E731
    t = st.tabs(["Özet", "Alımlar" + sayi(len(v["alimlar"])), "Satışlar" + sayi(len(v["satislar"])),
                 "Kampanya" + sayi(len(v["kampanya_urun"])), "İade" + sayi(len(v["iadeler"])),
                 "Analiz", "Hareketler", "Stok yaşı"])
    with t[0]:
        sol, sag = st.columns([1.35, 1], gap="medium")
        sol.markdown(_yer_html(stok_yerleri(v["depo_satir"], v["firma_stok_son"], fa), musteri_toplam,
                               v.get("satilabilir_kontrol")), unsafe_allow_html=True)
        uy = durum_uyarilari(v["toplam_stok"], v["yolda_adet"], v["gunluk_hiz"], v["uretim_suresi"],
                             v["pacal_final"], v["liste_fiyat"], bool(v["satislar"]))
        sag.markdown(_durum_html(uy) + _hareket_html(
            son_hareketler(v["satislar"], v["iadeler"], v["alimlar"], v["yolda_rows"], fa, bugun)),
            unsafe_allow_html=True)
        st.markdown(_grafik_html(haftalik_seri(v["satislar"], bugun)), unsafe_allow_html=True)
    with t[1]:
        govdeler["alim"]()
    with t[2]:
        _satislar(sku, v, fa, bugun, satis_detay)
    with t[3]:
        govdeler["kamp"]()
    with t[4]:
        govdeler["iade"]()
    with t[5]:
        govdeler["analiz"]()
    with t[6]:
        govdeler["har"]()
    with t[7]:
        govdeler["yas"]()


def _satislar(sku, v, fa, bugun, satis_detay):
    import streamlit as st
    if not v["satislar"] or not v["satir_kar"]:
        st.info("Bu SKU için satış kaydı bulunamadı.")
        return
    from shared.masa import calistir
    from shared.utils import sku_anahtar
    veri, kartlar = satis_masa_verisi(v["satislar"], v["satir_kar"], fa, bugun)
    st.markdown(_kanal_html(kartlar), unsafe_allow_html=True)
    sec_key = f"_skn_satis_sec_{sku_anahtar(sku)}"

    def yurut(temiz):
        st.session_state[sec_key] = temiz["ids"][0]
        # aynı çalıştırmada devam: pencere (dialog) kapanmasın, ayrıntı masanın altında açılır
        return {"ok": True, "sessiz": True, "yenileme": False}

    calistir(veri, f"skn_satis_{sku_anahtar(sku)}", yurut)
    i = st.session_state.get(sec_key)
    if isinstance(i, int) and 0 <= i < len(v["satislar"]):
        satis_detay(v["satislar"][i])
        if st.button("Ayrıntıyı kapat", key=f"skn_satis_kapat_{sku_anahtar(sku)}", icon=":material/close:"):
            st.session_state.pop(sec_key, None)
            st.rerun(scope="fragment")

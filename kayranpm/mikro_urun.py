# -*- coding: utf-8 -*-
"""Mikro → ürün kartları, barkod ve müşteri bazlı satış fiyatları (Ekim 2026).

Kullanıcı: "Mikro'da yeni ürün açılınca programa da gelsin. Stok kartları Mikro'da bazı modellerde 'Fazeon X...'
diye başlıyor; Fazeon olmasın, kodun önünde sadece kod olsun." Aktarıcı (araclar/mikro_aktarici/mikro_kayran.py:
stok_kart, stok_barkod, satis_fiyat, fiyat_liste) Mikro'daki kartları her turda tam çeker; burada uygulamaya yazılır.

KURALLAR
  • SKU: shared.utils.sku_anahtar ('Fazeon X24F165S' → 'X24F165S'); mevcut kart kendi yazımıyla bulunur.
  • Mikro'da olup uygulamada olmayan kart açılır (ad, marka, kategori, barkod). Pasif Mikro kartı yeni açılmaz;
    uygulamadaki kart Mikro'da pasif olsa da silinmez.
  • Mevcut kartta yalnız BOŞ alan dolar (ad, kategori, marka, barkod). Dolu kategori / marka / ad DEĞİŞMEZ:
    P&L, İthalat masraf dağıtımı ve Ref kırılımı kayıtlı yazıma dayanır. Yazım shared.ana_veri ile: kategori
    uygulamada aynı anahtarlı bir yazım varsa o (kayit_degeri), yoksa Türkçe küçük harf; marka aynı şekilde.
  • Garanti, GTİP, ölçü / ağırlık uygulama tablosuna YAZILMAZ (kolon açmak yerine): stok kartında Mikro
    kopyasından okunur (kart_cipleri).
  • Fiyat listesi → urunler.satis_fiyat_listesi ({müşteri: $ fiyat}). Mikro liste adı cari adına bağlanır
    (shared.utils.cari_eslestir; tek cari uymazsa liste aktarılmaz). Uygulamadaki liste dolar ve KDV hariç
    olduğundan yalnız dolar (sfiyat_doviz 1), KDV hariç, bütün depolar / peşin (depo 0, ödeme planı 0) satırlar
    yazılır; diğerleri atlanır ve sayısı karşılaştırmada görünür. Başka müşterilerin elle girilmiş fiyatına
    dokunulmaz; eşleşen müşterinin fiyatı Mikro'daki olur.
İlk açılışta "şimdi ↔ Mikro" karşılaştırması ve onay (Ürün Yönetimi › Tüm Ürünler, kayranpm/mikro_urun_ekran.py),
sonra otomatik (app.py _mikro_esitle_dene, otonom/mikro_esitle.py). Durum sistem_ayarlari'nda (DURUM_ANAHTAR).
"""
import time
from collections import defaultdict

DURUM_ANAHTAR = "mikro_urun_durum"
TABLOLAR = ("mikro_stok_kart", "mikro_stok_barkod", "mikro_satis_fiyat", "mikro_fiyat_liste")
DOLAR = 1                      # Mikro döviz cinsi: 0 TL, 1 USD, 2 EUR
DOLAN_ALANLAR = ("urun_adi", "kategori", "marka", "barkod")
FIYAT_ESIK = 0.00005
# Liste adında müşteriyi değil listeyi anlatan sözcükler (normalize_tr hâlleri): "VATAN FİYAT LİSTESİ" → "VATAN"
_LISTE_SOZCUKLERI = {"FIYAT", "FIYATI", "FIYATLARI", "LISTE", "LISTESI", "SATIS", "SATIS."}


def _s(v):
    return " ".join(str(v or "").split())


def _i(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ── Saf ────────────────────────────────────────────────────────────
def mikro_kategori(k):
    """Mikro kartının kategori adı: ana grup adı, yoksa alt grup adı, yoksa kategori kodu."""
    return _s(k.get("anagrup_isim")) or _s(k.get("altgrup_isim")) or _s(k.get("sto_kategori_kodu"))


def kategori_yazimi(ad, mevcut_yazimlar):
    """Uygulamada aynı anahtarlı kategori varsa onun yazımı ('MONİTÖR' → 'monitör'), yoksa Türkçe küçük harf."""
    from shared.ana_veri import kayit_degeri
    from shared.utils import tr_kucuk
    return kayit_degeri(ad, mevcut_yazimlar, bicim=tr_kucuk) if _s(ad) else ""


def marka_yazimi(ad, mevcut_yazimlar):
    """Uygulamada aynı anahtarlı marka varsa onun yazımı ('Fazeon' → 'FAZEON'), yoksa shared.ana_veri.marka_ad."""
    from shared.ana_veri import marka_ad, marka_anahtar
    a = marka_anahtar(ad)
    if not a:
        return ""
    for m in mevcut_yazimlar or ():
        if marka_anahtar(m) == a:
            return _s(m)
    return marka_ad(ad)


def barkod_haritasi(barkodlar):
    """{sku_anahtar: barkod} — ana barkod (bar_master) önce, sonra en küçük kod (her turda aynı sonuç)."""
    from shared.utils import sku_anahtar
    aday = defaultdict(list)
    for b in barkodlar or ():
        sku, kod = sku_anahtar(b.get("bar_stokkodu")), _s(b.get("bar_kodu"))
        if sku and kod:
            aday[sku].append((0 if _i(b.get("bar_master")) else 1, kod))
    return {sku: sorted(v)[0][1] for sku, v in aday.items()}


def mikro_kartlari(kartlar):
    """{sku_anahtar: Mikro kartı}. Aynı anahtara iki Mikro kodu düşerse ('Fazeon X' ve 'X') etkin olan, sonra
    önek taşımayan kazanır."""
    from shared.utils import sku_anahtar
    out = {}
    for k in kartlar or ():
        sku = sku_anahtar(k.get("sto_kod"))
        if not sku:
            continue
        onceki = out.get(sku)
        if onceki is None or _kart_puani(k, sku) < _kart_puani(onceki, sku):
            out[sku] = k
    return out


def _kart_puani(k, sku):
    return (_i(k.get("sto_pasif")), 0 if _s(k.get("sto_kod")).upper() == sku else 1)


def fazeon_kodlari(kartlar, urunler):
    """[(Mikro kodu, SKU, uygulamada kartı var mı)] — 'Fazeon ' önekli Mikro kodları."""
    from shared.utils import sku_anahtar
    mevcut = {sku_anahtar(u.get("sku")) for u in urunler or ()}
    return sorted((_s(k.get("sto_kod")), sku_anahtar(k.get("sto_kod")), sku_anahtar(k.get("sto_kod")) in mevcut)
                  for k in kartlar or () if _s(k.get("sto_kod")).upper().startswith("FAZEON "))


def kart_plani(kartlar, barkodlar, urunler):
    """Kart yazım planı. Döner: {"yeni": [kart satırı], "doldur": [(sku, {alan: değer})], "pasif_atlanan": [sku]}.
    urunler: [{sku, urun_adi, kategori, marka, barkod}]. Dolu alana hiçbir koşulda yazılmaz."""
    from shared.utils import sku_anahtar
    mevcut = {}
    for u in urunler or ():
        a = sku_anahtar(u.get("sku"))
        if a and a not in mevcut:
            mevcut[a] = u
    kat_yazim = [_s(u.get("kategori")) for u in urunler or () if _s(u.get("kategori"))]
    mar_yazim = [_s(u.get("marka")) for u in urunler or () if _s(u.get("marka"))]
    bar = barkod_haritasi(barkodlar)
    yeni, doldur, pasif = [], [], []
    for sku, k in sorted(mikro_kartlari(kartlar).items()):
        deger = {"urun_adi": _s(k.get("sto_isim")),
                 "kategori": kategori_yazimi(mikro_kategori(k), kat_yazim),
                 "marka": marka_yazimi(k.get("sto_marka_kodu"), mar_yazim),
                 "barkod": bar.get(sku, "")}
        u = mevcut.get(sku)
        if u is None:
            if _i(k.get("sto_pasif")):
                pasif.append(sku)
                continue
            yeni.append(dict(sku=sku, mikro_kod=_s(k.get("sto_kod")), **deger))
            continue
        bos = {a: v for a, v in deger.items() if v and not _s(u.get(a))}
        if bos:
            doldur.append((_s(u.get("sku")), bos))
    return {"yeni": yeni, "doldur": doldur, "pasif_atlanan": pasif}


def liste_musterisi(liste_adi, cariler):
    """Mikro fiyat listesinin adı hangi cariye ait. Önce adın tamamı, sonra liste sözcükleri ('FİYAT LİSTESİ')
    atılmış hâli, sonra baştan kısalan sözcük grupları shared.utils.cari_eslestir ile (birebir ya da TEK carinin
    başı). Uymazsa None — yanlış müşteriye fiyat yazılmasın."""
    from shared.utils import cari_eslestir, normalize_tr
    kel = normalize_tr(liste_adi).split()
    if not kel:
        return None
    sade = [k for k in kel if k not in _LISTE_SOZCUKLERI]
    denenecek = [" ".join(kel)] + [" ".join(sade[:n]) for n in range(len(sade), 0, -1)]
    for aday in dict.fromkeys(d for d in denenecek if d):
        c = cari_eslestir(aday, cariler)
        if c:
            return c
    return None


def liste_eslesmesi(listeler, cariler):
    """[{sirano, ad, musteri, kdv_dahil}] — her Mikro listesinin müşterisi (eşleşmezse None)."""
    return [{"sirano": _i(l.get("sfl_sirano")), "ad": _s(l.get("sfl_aciklama")),
             "musteri": liste_musterisi(l.get("sfl_aciklama"), cariler), "kdv_dahil": bool(_i(l.get("sfl_kdvdahil")))}
            for l in sorted(listeler or (), key=lambda x: _i(x.get("sfl_sirano")))]


def _anahtar_bul(liste, musteri):
    """Ürünün fiyat listesinde aynı müşterinin mevcut anahtarı (yazımı korunur), yoksa müşteri adı."""
    from shared.utils import normalize_tr
    n = " ".join(normalize_tr(musteri).split())
    for k in (liste or {}):
        if " ".join(normalize_tr(k).split()) == n:
            return k
    return musteri


def fiyat_plani(fiyatlar, eslesme, urunler, yeni_skular=()):
    """Fiyat yazım planı. Döner: {"degisen": [(sku, müşteri anahtarı, eski, yeni)], "atlanan": {neden: adet}}.
    Bir ürün × liste için birden çok uygun satır varsa son değiştirilen (sfiyat_lastup_date) kazanır."""
    from shared.utils import sku_anahtar
    liste = {e["sirano"]: e for e in eslesme or ()}
    mevcut = {}
    for u in urunler or ():
        a = sku_anahtar(u.get("sku"))
        if a and a not in mevcut:
            mevcut[a] = u
    yeni = set(yeni_skular or ())
    atlanan = defaultdict(int)
    secilen = {}
    for r in fiyatlar or ():
        e = liste.get(_i(r.get("sfiyat_listesirano"), -1))
        if e is None:
            atlanan["liste tanımı yok"] += 1
            continue
        if not e.get("musteri"):
            atlanan["liste müşteriyle eşleşmedi"] += 1
            continue
        if e.get("kdv_dahil"):
            atlanan["KDV dahil liste"] += 1
            continue
        if _i(r.get("sfiyat_doviz")) != DOLAR:
            atlanan["dolar dışı fiyat"] += 1
            continue
        if _i(r.get("sfiyat_deposirano")) or _i(r.get("sfiyat_odemeplan")) or _i(r.get("sfiyat_birim_pntr")) > 1:
            atlanan["depoya / ödeme planına / birime özel"] += 1
            continue
        fiyat = round(_f(r.get("sfiyat_fiyati")), 4)
        if fiyat <= 0:
            atlanan["fiyat sıfır"] += 1
            continue
        sku = sku_anahtar(r.get("sfiyat_stokkod"))
        if sku not in mevcut and sku not in yeni:
            atlanan["uygulamada kartı yok"] += 1
            continue
        k = (sku, e["musteri"])
        t = str(r.get("sfiyat_lastup_date") or "")
        if k not in secilen or t >= secilen[k][0]:
            secilen[k] = (t, fiyat)
    degisen = []
    for (sku, musteri), (_, fiyat) in sorted(secilen.items()):
        u = mevcut.get(sku) or {"sku": sku}
        fl = u.get("satis_fiyat_listesi") if isinstance(u.get("satis_fiyat_listesi"), dict) else {}
        anahtar = _anahtar_bul(fl, musteri)
        eski = _f(fl.get(anahtar)) if anahtar in fl else None
        if eski is None or abs(eski - fiyat) > FIYAT_ESIK:
            degisen.append((_s(u.get("sku")) or sku, anahtar, eski, fiyat))
    return {"degisen": degisen, "atlanan": dict(sorted(atlanan.items()))}


def birlesik_liste(mevcut, degisenler):
    """Ürünün mevcut fiyat listesine yalnız değişen müşterileri yazar; diğer müşteriler aynen kalır."""
    out = dict(mevcut) if isinstance(mevcut, dict) else {}
    for anahtar, fiyat in degisenler:
        out[anahtar] = float(fiyat)
    return out


def _sayi(v, basamak=0):
    from shared.tasarim import tr_sayi
    return tr_sayi(v, basamak)


def kart_cipleri_hazirla(k):
    """Stok kartında gösterilecek Mikro alanları: [(etiket, değer)] — boş olan yazılmaz."""
    if not k:
        return []
    out = []
    if _i(k.get("sto_garanti_sure")) > 0:       # birimi Mikro'daki süre tipine bağlı; sayı olduğu gibi
        out.append(("Garanti", _sayi(_i(k.get("sto_garanti_sure")))))
    if _s(k.get("sto_gtipno")):
        out.append(("GTİP", _s(k.get("sto_gtipno"))))
    if _f(k.get("sto_birim1_agirlik")) > 0:
        out.append(("Ağırlık", _sayi(_f(k.get("sto_birim1_agirlik")), 2)))
    olcu = [_f(k.get(a)) for a in ("sto_birim1_en", "sto_birim1_boy", "sto_birim1_yukseklik")]
    if any(x > 0 for x in olcu):
        out.append(("Ölçü", " × ".join(_sayi(x, 1) for x in olcu)))
    if _i(k.get("sto_pasif")):
        out.append(("Mikro", "pasif"))
    return out


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranpm.database import get_client
    return get_client()


def veri_oku():
    """Sıralı ve kopyasız okuma (aynı anahtar iki kez gelirse OkumaTutarsiz: tur atlanır)."""
    from satis.mikro_esitle import kopyasiz
    cli = _cli()
    return {
        "kart": kopyasiz(cli.table("mikro_stok_kart").select("*").order("sto_kod").execute().data or [], "sto_kod"),
        "barkod": kopyasiz(cli.table("mikro_stok_barkod").select("bar_guid,bar_kodu,bar_stokkodu,bar_master")
                           .order("bar_guid").execute().data or [], "bar_guid"),
        "fiyat": kopyasiz(cli.table("mikro_satis_fiyat").select("*").order("sfiyat_guid").execute().data or [],
                          "sfiyat_guid"),
        "liste": kopyasiz(cli.table("mikro_fiyat_liste").select("*").order("sfl_sirano").execute().data or [],
                          "sfl_sirano"),
        "cari": [_s(c.get("cari_unvan1")) for c in
                 (cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1").order("cari_kod").execute().data or [])
                 if _s(c.get("cari_unvan1"))],
        "urunler": kopyasiz(cli.table("urunler").select("sku,urun_adi,kategori,marka,barkod,satis_fiyat_listesi")
                            .order("sku").execute().data or [], "sku"),
    }


def hesapla(v):
    kp = kart_plani(v["kart"], v["barkod"], v["urunler"])
    es = liste_eslesmesi(v["liste"], v["cari"])
    fp = fiyat_plani(v["fiyat"], es, v["urunler"], [y["sku"] for y in kp["yeni"]])
    return dict(kp, fiyat=fp["degisen"], fiyat_atlanan=fp["atlanan"], liste=es,
                fazeon=fazeon_kodlari(v["kart"], v["urunler"]), bos=not v["kart"], mikro_kart=len(v["kart"]))


def plan_hazirla():
    return hesapla(veri_oku())


def uygula(plan):
    """Planı yazar. Mikro kart verisi boşsa yazmaz. Yazmadan hemen önce kartlar yeniden okunur: arada açılmış
    kart üzerine yazılmaz, arada dolmuş alana yazılmaz. Döner: değişen kart sayısı ya da hata metni."""
    if plan.get("bos"):
        return 0
    if not (plan["yeni"] or plan["doldur"] or plan["fiyat"]):
        return 0
    from shared.utils import sku_anahtar
    from kayranpm.database import get_today, stok_yas_ilk_gorulen
    cli = _cli()
    simdi = {}
    for u in cli.table("urunler").select("sku,urun_adi,kategori,marka,barkod,satis_fiyat_listesi") \
            .order("sku").execute().data or []:
        simdi.setdefault(sku_anahtar(u.get("sku")), u)
    bugun = get_today()
    degisen = set()
    acilan = []
    for y in plan["yeni"]:
        if y["sku"] in simdi:
            continue
        satir = {"sku": y["sku"], "urun_adi": y["urun_adi"], "kategori": y["kategori"], "marka": y["marka"],
                 "barkod": y["barkod"] or None, "satis_fiyati": 0, "alis_fiyati": 0, "hedef_kar_marji": 0,
                 "ozellikler": "", "bizim_stok": 0, "trendyol_stok": 0,
                 "ilk_giris_tarihi": bugun, "guncelleme_tarihi": bugun}
        cli.table("urunler").insert(satir).execute()
        simdi[y["sku"]] = dict(satir, satis_fiyat_listesi={})
        acilan.append(y["sku"])
        degisen.add(y["sku"])
    if acilan:
        stok_yas_ilk_gorulen(cli, acilan, bugun)
    for sku, alanlar in plan["doldur"]:
        u = simdi.get(sku_anahtar(sku))
        if not u:
            continue
        yaz = {a: v for a, v in alanlar.items() if a in DOLAN_ALANLAR and v and not _s(u.get(a))}
        if yaz:
            cli.table("urunler").update(yaz).eq("sku", u["sku"]).execute()
            degisen.add(sku_anahtar(sku))
    grup = defaultdict(list)
    for sku, anahtar, _eski, fiyat in plan["fiyat"]:
        grup[sku_anahtar(sku)].append((anahtar, fiyat))
    for a, fiyatlar in grup.items():
        u = simdi.get(a)
        if not u:
            continue
        yeni_liste = birlesik_liste(u.get("satis_fiyat_listesi"), fiyatlar)
        if yeni_liste != (u.get("satis_fiyat_listesi") or {}):
            cli.table("urunler").update({"satis_fiyat_listesi": yeni_liste}).eq("sku", u["sku"]).execute()
            degisen.add(a)
    if degisen:
        from kayranpm.database import _cache_temizle
        _cache_temizle()
    return len(degisen)


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    return bool(durum().get("acik"))


def ac(kullanici):
    from kayranacc.database import set_ayar
    from shared.utils import tr_now
    d = durum()
    d.update(acik=True, acan=str(kullanici or ""), acilis=str(tr_now()))
    set_ayar(DURUM_ANAHTAR, d)


def son_aktarim():
    """Ürün tablolarının en yeni çekim zamanı (biri değişince tur çalışır). Kart tablosu hiç çekilmediyse ''."""
    r = _cli().table("mikro_senk_durum").select("tablo,son_cekim").in_("tablo", list(TABLOLAR)).execute().data or []
    zaman = {x.get("tablo"): str(x.get("son_cekim") or "") for x in r}
    if not zaman.get("mikro_stok_kart"):
        return ""
    return max(z for z in zaman.values() if z)


def otomatik():
    """Açıksa ve aktarıcı yeni ürün verisi getirdiyse farkları yazar. Hata fırlatmaz."""
    try:
        from kayranacc.database import set_ayar
        d = durum()
        if not d.get("acik"):
            return None
        son = son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        from satis.mikro_esitle import aktarim_suruyor
        if aktarim_suruyor():
            return None                   # aktarıcı yazıyor (tablolar tam çekimde silinip yazılır)
        sonuc = uygula(plan_hazirla())
        if isinstance(sonuc, str):
            from shared.kayit import sessiz
            sessiz("kayranpm.mikro_urun.otomatik", RuntimeError(sonuc))
            return None
        d["son_calisma"] = son
        set_ayar(DURUM_ANAHTAR, d)
        return sonuc
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_urun.otomatik", e)
        return None


_KART_ONBELLEK = {"t": 0.0, "v": {}}
_KART_SURE = 300


def kart_cipleri(sku):
    """Stok kartı için Mikro alanları (garanti, GTİP, ağırlık, ölçü). Okunamazsa []; kart yine açılır."""
    try:
        if time.time() - _KART_ONBELLEK["t"] > _KART_SURE:
            from satis.mikro_esitle import kopyasiz
            satir = kopyasiz(_cli().table("mikro_stok_kart").select(
                "sto_kod,sto_garanti_sure,sto_gtipno,sto_birim1_agirlik,sto_birim1_en,sto_birim1_boy,"
                "sto_birim1_yukseklik,sto_pasif").order("sto_kod").execute().data or [], "sto_kod")
            _KART_ONBELLEK.update(t=time.time(), v=mikro_kartlari(satir))
        from shared.utils import sku_anahtar
        return kart_cipleri_hazirla(_KART_ONBELLEK["v"].get(sku_anahtar(sku)))
    except Exception:  # noqa: BLE001
        return []

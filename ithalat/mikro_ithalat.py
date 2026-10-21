# -*- coding: utf-8 -*-
"""Geçmiş İthalatlar Mikro'dan (Ekim 2026).

Kullanıcı: "Mikro'dan geçmiş ithalatlar datalarını alıp programa entegre edeceksin." Karar (21.10.2026, kullanıcı):
uygulamadaki PI dosyaları kalır ve Mikro dosyasına bağlanır; masraflar, teslim tarihi / deposu, durum ve beyanname
no Mikro'dan gelir; Mikro'da açılıp uygulamada olmayan dosya eklenir; karşılaştırma onayı beklenmeden otomatik
("5'i de onaylamadan önerdiğin gibi devam et"). Her değişiklikten önce dosyanın eski satırı mikro_esitleme_arsiv'e
yazılır; değişiklikler rapora (Geçmiş İthalatlar › Mikro eşitlemesi) düşer.

Mikro'daki yapı (canlı veri, 21.10.2026):
  ITHALAT_DOSYALARI  ith_kodu (VANEX-012), satıcı cari kodu (320.50.002)          → mikro_ithalat_dosya
  STOK_HAREKETLERI   ürün girişi, sth_exim_kodu = dosya kodu (adet, $ tutar, depo)  → mikro_alim_satir
  CARI_HESAP_HAREKETLERI (cha_EXIMkodu = dosya kodu)                                → mikro_ithalat
      evrak 0 / cinsi 29 : ithalat faturası (mal bedeli; cha_belge_no = gümrük beyannamesi)
      evrak 95           : masraf dağıtımı, satır başına bir kalem (cha_aciklama): Navlun, Sigorta, Gümrük vergi
                           ve resimler, Gümrük Müşavirlik, Ardiye, Diğer Çeşitli Giderler — $ (cha_d_cins 1)
      evrak 33 / 35      : ödemeler ve bedelsiz mal bedeli (masraf DEĞİL; 95 zaten toplamı taşır)

Eşleşme: bir Mikro dosyası uygulamada birden çok PI dosyasına bölünmüş olabilir (MASTER-008 = PIFAZ251125-2,
-4-1, -5). Aynı tedarikçinin, ürünleri Mikro dosyasının içinde kalan dosyalarından, ürün ürün adet toplamı Mikro'yla
BİREBİR tutan kümeler aranır; birden çoksa ürün ürün FOB'u Mikro'ya en yakın olan, sonra teslim alınmış olan seçilir;
tek kesin küme yoksa bağlanmaz (raporda "eşleşmedi"). Bağ ithalat_dosyalari.mikro_kodu.

Yeni dosya: Mikro'daki dosya hiçbir kümeye uymuyorsa ve aynı tedarikçinin bağlanmamış, aynı ürünleri taşıyan, yolda /
antrepoda ya da eşleşme penceresinde bir dosyası yoksa eklenir; birden çok kümeye uyan (belirsiz) hiç eklenmez (yoksa çift kayıt olurdu: raporda "eşleşmedi"). Bedelsiz
(FOB 0) dosya eklenmez. Teslim tarihi yalnız teslime geçişte ya da boşsa yazılır.

Masraf: Mikro'nun 6 kaleminin toplamı esastır. Uygulamada o kalemde tutar varsa uygulamanın kendi dağılımı (alt
kalemler, ürün grubu atamaları) korunur, Mikro toplamına ölçeklenir; yoksa tutar varsayılan alt kaleme, PI'lara FOB
payıyla yazılır. Mikro dosyasında masraf yoksa (henüz işlenmemiş) uygulamanın masrafına dokunulmaz.
Ürün / FOB değişmez (canlıda birebir tutuyor; fark raporda görünür).
"""
from collections import defaultdict
from itertools import combinations

ESLESME_GERI_GUN = 540                 # PI tarihi Mikro girişinden en fazla bu kadar önce olabilir
ADAY_SINIRI = 16                       # küme aramasında en fazla aday dosya (Mikro tarihine en yakınlar)
DURUM_ANAHTAR = "mikro_ithalat_durum"
RAPOR_ANAHTAR = "mikro_ithalat_rapor"
TESLIM = "Teslim Alındı"

KATEGORILER = ("navlun", "sigorta", "gumruk", "musavirlik", "ardiye", "diger")
KATEGORI_AD = {"navlun": "Navlun", "sigorta": "Sigorta", "gumruk": "Gümrük vergi ve resimler",
               "musavirlik": "Gümrük müşavirlik", "ardiye": "Ardiye", "diger": "Diğer giderler"}
# uygulama masraf kalemi (ithalat.database.MASRAF_TANIM) → Mikro kalemi
SLUG_KATEGORI = {
    "navlun": "navlun", "mal_sigortasi": "sigorta", "sigorta": "sigorta",
    "gv": "gumruk", "igv": "gumruk", "otv": "gumruk", "kbf": "gumruk", "damga_vergisi": "gumruk", "gumruk": "gumruk",
    "gumruk_musavirligi": "musavirlik", "antrepo_beyannamesi": "musavirlik",
    "liman_ardiye": "ardiye", "antrepo_ardiye": "ardiye", "demuraj": "ardiye",
    "liman_depo_nakliye": "diger", "tahliye_depolama_tasima": "diger", "banka_komisyonu": "diger",
    "tse_tareks": "diger", "yolluk": "diger", "nakliye": "diger", "diger": "diger",
}
VARSAYILAN_SLUG = {"navlun": "navlun", "sigorta": "mal_sigortasi", "gumruk": "gv",
                   "musavirlik": "gumruk_musavirligi", "ardiye": "liman_ardiye", "diger": "diger"}
KURUS = 0.01


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _i(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _gun(v):
    s = str(v or "")[:10]
    return "" if s.startswith(("1899", "1900")) else s


def _sku(v):
    from shared.utils import sku_anahtar
    return sku_anahtar(v)


def _kucuk(s):
    from shared.utils import tr_kucuk
    return tr_kucuk(str(s or ""))


def kategori_bul(aciklama, satir_no=None):
    """Mikro masraf satırı → kalem. Önce açıklama ("Navlun", "Gümrük vergi ve resimler"…), olmazsa satır sırası."""
    a = _kucuk(aciklama)
    for anahtar, kat in (("navlun", "navlun"), ("sigorta", "sigorta"), ("müşavir", "musavirlik"),
                         ("musavir", "musavirlik"), ("gümrük", "gumruk"), ("gumruk", "gumruk"), ("vergi", "gumruk"),
                         ("ardiye", "ardiye"), ("demuraj", "ardiye")):
        if anahtar in a:
            return kat
    n = _i(satir_no, -1)
    return KATEGORILER[n] if 0 <= n < len(KATEGORILER) and not a else "diger"


def _usd(r, fatura_kur):
    tutar, cins, kur = _f(r.get("cha_meblag")), _i(r.get("cha_d_cins")), _f(r.get("cha_d_kur"))
    if cins == 1:
        return tutar
    if cins == 0:
        return tutar / fatura_kur if fatura_kur > 0 else 0.0
    return tutar * kur / fatura_kur if fatura_kur > 0 else 0.0     # € vb.: TL'ye, sonra $'a


def mikro_dosyalari(dosyalar, satirlar, cariler, unvanlar=None, depo_adlari=None):
    """Mikro kopyalarından dosya özeti. Döner: {kod: {kod, cari, tedarikci, isim, olusturma, fatura_tarihi,
    giris, depo, beyanname, kur, urunler {sku: {adet, tutar}}, masraf {kalem: $}, masraf_var}}."""
    unvanlar, depo_adlari = unvanlar or {}, depo_adlari or {}
    out = {}
    for d in dosyalar or []:
        kod = str(d.get("ith_kodu") or "").strip()
        if not kod:
            continue
        cari = str(d.get("ith_satici") or "").strip()
        out[kod] = {"kod": kod, "cari": cari, "tedarikci": " ".join(str(unvanlar.get(cari) or "").split()),
                    "isim": str(d.get("ith_ismi") or "").strip(), "olusturma": _gun(d.get("ith_create_date")),
                    "fatura_tarihi": "", "giris": "", "depo": "", "beyanname": "", "kur": 0.0,
                    "urunler": {}, "masraf": {k: 0.0 for k in KATEGORILER}, "masraf_var": False}
    depo_adet = defaultdict(lambda: defaultdict(float))
    for s in satirlar or []:
        kod = str(s.get("sth_exim_kodu") or "").strip()
        if kod not in out or _i(s.get("sth_normal_iade")) == 1:
            continue
        sku = _sku(s.get("sth_stok_kod"))
        if not sku:
            continue
        u = out[kod]["urunler"].setdefault(sku, {"adet": 0.0, "tutar": 0.0})
        u["adet"] += _f(s.get("sth_miktar"))
        u["tutar"] += _f(s.get("sth_tutar")) - _f(s.get("sth_iskonto"))
        g = _gun(s.get("sth_tarih"))
        if g and (not out[kod]["giris"] or g < out[kod]["giris"]):
            out[kod]["giris"] = g
        depo_adet[kod][_i(s.get("sth_giris_depo_no"))] += _f(s.get("sth_miktar"))
    for kod, dag in depo_adet.items():
        no = max(dag.items(), key=lambda x: x[1])[0]
        out[kod]["depo"] = str(depo_adlari.get(no) or "")
    faturalar = [c for c in cariler or [] if _i(c.get("cha_evrak_tip")) == 0 and _i(c.get("cha_cinsi")) == 29]
    for c in faturalar:
        kod = str(c.get("cha_eximkodu") or "").strip()
        if kod in out:
            m = out[kod]
            m["fatura_tarihi"] = m["fatura_tarihi"] or _gun(c.get("cha_tarihi"))
            m["beyanname"] = m["beyanname"] or str(c.get("cha_belge_no") or "").strip()
            m["kur"] = m["kur"] or _f(c.get("cha_d_kur"))
    for c in cariler or []:
        if _i(c.get("cha_evrak_tip")) != 95:
            continue
        kod = str(c.get("cha_eximkodu") or c.get("dosya_veya_cari") or "").strip()
        if kod not in out:
            continue
        m = out[kod]
        m["masraf"][kategori_bul(c.get("cha_aciklama"), c.get("cha_satir_no"))] += _usd(c, m["kur"])
        m["masraf_var"] = True
        if not str(c.get("cha_aciklama") or "").strip() and c.get("cha_satir_no") is None:
            m["kalem_eksik"] = True     # aktarıcı kalem adını henüz getirmedi: hangi masraf olduğu bilinmiyor
    return out


# ── eşleşme ─────────────────────────────────────────────────────────
def _ted_anahtar(ad):
    """Tedarikçinin ilk kelimesi: 'SHENZHEN MASTER TECHNOLOGY CO., LTD' → 'SHENZHEN', Mikro dosya adı 'VANEX'."""
    import re
    from shared.utils import tr_buyuk
    kel = re.findall(r"[0-9A-ZÇĞİÖŞÜ]+", tr_buyuk(str(ad or "")))
    return kel[0] if kel else ""


def tedarikci_uyar(m, dosya):
    a = _ted_anahtar(dosya.get("tedarikci"))
    return bool(a) and a in {_ted_anahtar(m.get("tedarikci")), _ted_anahtar(m.get("isim"))}


def _adetler(kalemler):
    out = defaultdict(float)
    for k in kalemler or []:
        s = _sku(k.get("sku"))
        if s:
            out[s] += _f(k.get("adet"))
    return dict(out)


def _fob_sku(kalemler):
    out = defaultdict(float)
    for k in kalemler or []:
        s = _sku(k.get("sku"))
        if s:
            out[s] += _f(k.get("adet")) * _f(k.get("birim_fob"))
    return dict(out)


def _esit(a, b):
    return set(a) == set(b) and all(abs(a[k] - b[k]) < 0.5 for k in a)


def _tarih(v):
    from datetime import date
    try:
        return date.fromisoformat(_gun(v))
    except ValueError:
        return None


def _kume_sec(hedef, tutar, adaylar):
    """hedef {sku: adet}, tutar {sku: $} (Mikro); adaylar [(dosya, adet, fob)]. Döner: ([id], None) ya da (None, sebep).
    Her boyutta adetleri birebir tutan BÜTÜN kümeler toplanır (canlı: MASTER-004 tek dosyaya, MASTER-005 üç dosyaya
    bağlanıyordu, oysa FOB'ları tersini söylüyor). Birden çoksa önce ürün ürün FOB'u Mikro'ya en yakın küme, sonra
    hepsi teslim alınmış küme; yine de birden çoksa belirsiz (yanlış PI'ya masraf yazılmasın)."""
    kumeler = []
    for n in range(1, len(adaylar) + 1):
        for kume in combinations(adaylar, n):
            top = defaultdict(float)
            for _d, ad, _fob in kume:
                for s, a in ad.items():
                    top[s] += a
            if _esit(dict(top), hedef):
                kumeler.append(kume)
                if len(kumeler) > 40:
                    return None, "çok sayıda dosya kümesi aynı adetleri tutuyor"
    if not kumeler:
        return None, "uygulamadaki dosyalarla adetler birebir tutmuyor"
    if len(kumeler) > 1:
        def fark(kume):
            top = defaultdict(float)
            for _d, _ad, fob in kume:
                for s, v in fob.items():
                    top[s] += v
            return sum(abs(top[s] - tutar.get(s, 0.0)) for s in hedef)
        en = min(fark(k) for k in kumeler)
        pay = max(1.0, 0.002 * sum(abs(v) for v in tutar.values()))   # kur / kuruş yuvarlaması
        kumeler = [k for k in kumeler if fark(k) <= en + pay]
    if len(kumeler) > 1:
        teslim = [k for k in kumeler if all(str(d.get("durum") or "") == TESLIM for d, _a, _f in k)]
        if teslim:
            kumeler = teslim
    if len(kumeler) > 1:
        return None, "birden çok dosya kümesi aynı adetleri ve FOB'u tutuyor"
    return [d["id"] for d, _a, _f in kumeler[0]], None


def _adaylar(m, hedef, dosyalar, kalemler_map, kullanilan):
    """Aynı tedarikçinin, bağlanmamış, ürünleri Mikro dosyasının içinde kalan ve tarihi pencerede olan dosyaları."""
    from datetime import timedelta
    ref_t = _tarih(m["giris"] or m["fatura_tarihi"] or m["olusturma"])
    out = []
    for d in dosyalar:
        if d["id"] in kullanilan or not tedarikci_uyar(m, d):
            continue
        ad = _adetler(kalemler_map.get(d["id"]))
        if not ad or not set(ad) <= set(hedef) or any(ad[s] > hedef[s] + 0.5 for s in ad):
            continue
        t = _tarih(d.get("tarih"))
        if ref_t and t and not (ref_t - timedelta(days=ESLESME_GERI_GUN) <= t <= ref_t + timedelta(days=7)):
            continue
        out.append((d, ad, _fob_sku(kalemler_map.get(d["id"]))))
    # Mikro tarihine en yakın dosyalar önce (ikizi çok tedarikçide doğru dosya sınırın dışında kalmasın)
    out.sort(key=lambda x: abs((_tarih(x[0].get("tarih")) - ref_t).days)
             if ref_t and _tarih(x[0].get("tarih")) else 10 ** 6)
    return out[:ADAY_SINIRI]


def eslestir(mikro, dosyalar, kalemler_map):
    """{kod: [dosya id]} + belirsiz {kod: sebep}. dosyalar: uygulamadaki ithalat dosyaları (mikro_kodu dahil);
    kalemler_map: {dosya id: [kalem]}. Önce kayıtlı bağ (mikro_kodu), sonra birebir adet kümesi (_kume_sec).
    Kayıtlı bağın adetleri Mikro'dan azsa (antrepodaki kardeş PI sonradan aynı dosyayla girdi) eksik kısım
    bağlanmamış dosyalarda aranır."""
    bagli = defaultdict(list)
    for d in dosyalar:
        k = str(d.get("mikro_kodu") or "").strip()
        if k:
            bagli[k].append(d["id"])
    kullanilan = {i for ids in bagli.values() for i in ids}
    eslesme, belirsiz = {k: list(v) for k, v in bagli.items() if k in mikro}, {}
    for kod, m in sorted(mikro.items(), key=lambda x: (x[1]["giris"] or x[1]["olusturma"] or "9", x[0])):
        if not m["urunler"]:
            continue
        hedef = {s: u["adet"] for s, u in m["urunler"].items()}
        tutar = {s: u["tutar"] for s, u in m["urunler"].items()}
        if kod in eslesme:
            var = defaultdict(float)
            for i in eslesme[kod]:
                for s, a in _adetler(kalemler_map.get(i)).items():
                    var[s] += a
            kalan = {s: a - var.get(s, 0.0) for s, a in hedef.items() if a - var.get(s, 0.0) > 0.5}
            if not kalan or any(var[s] > hedef.get(s, 0.0) + 0.5 for s in var):
                continue
            ek, _sebep = _kume_sec(kalan, {s: tutar[s] for s in kalan},
                                   _adaylar(m, kalan, dosyalar, kalemler_map, kullanilan))
            if ek:
                eslesme[kod] += ek
                kullanilan.update(ek)
            continue
        bulunan, sebep = _kume_sec(hedef, tutar, _adaylar(m, hedef, dosyalar, kalemler_map, kullanilan))
        if bulunan:
            eslesme[kod] = bulunan
            kullanilan.update(bulunan)
        else:
            belirsiz[kod] = sebep
    return eslesme, belirsiz


def cift_riski(m, dosyalar, kalemler_map, eslesme):
    """Mikro dosyası uygulamaya eklenirse çift kayıt olur mu: aynı tedarikçinin, hiçbir Mikro dosyasına bağlı olmayan,
    ürün paylaşan ve henüz teslim alınmamış (yolda / antrepo) ya da tarihi eşleşme penceresinde dosyası var mı.
    (Canlı kuru çalıştırma: 120 günlük pencereyle LCCGAME-014, uygulamada ikizi dururken yeni dosya oluyordu.)"""
    from datetime import timedelta
    bagli = {i for ids in eslesme.values() for i in ids}
    ref_t = _tarih(m["giris"] or m["fatura_tarihi"] or m["olusturma"])
    for d in dosyalar:
        if d["id"] in bagli or str(d.get("mikro_kodu") or "").strip() or not tedarikci_uyar(m, d):
            continue
        if not set(_adetler(kalemler_map.get(d["id"]))) & set(m["urunler"]):
            continue
        t = _tarih(d.get("tarih"))
        if str(d.get("durum") or "") != TESLIM or not ref_t or not t \
                or ref_t - timedelta(days=ESLESME_GERI_GUN) <= t <= ref_t + timedelta(days=7):
            return True
    return False


# ── masraf ──────────────────────────────────────────────────────────
def _yuvarla(d):
    return {k: round(v, 2) for k, v in d.items() if abs(round(v, 2)) >= KURUS}


def masraf_hedefi(m, grup, fob):
    """m: Mikro dosyası; grup: [{id, masraflar {slug: $}, dagilim {slug: {grup: $}}}]; fob: {id: net FOB}.
    Döner: {id: (yeni masraflar, yeni dagilim)} ya da None (Mikro'da masraf yok: dokunma)."""
    if not m.get("masraf_var") or m.get("kalem_eksik"):
        return None         # kalemi bilinmeyen tutar "diğer"e yazılsaydı uygulamanın kalem dağılımı silinirdi
    yeni = {g["id"]: dict(g["masraflar"]) for g in grup}
    dagilim = {g["id"]: {s: dict(v) for s, v in (g.get("dagilim") or {}).items()} for g in grup}
    top_fob = sum(max(_f(fob.get(g["id"])), 0.0) for g in grup)
    for kat in KATEGORILER:
        hedef = _f(m["masraf"].get(kat))
        mevcut = sum(v for g in grup for s, v in g["masraflar"].items() if SLUG_KATEGORI.get(s, "diger") == kat)
        if abs(mevcut) >= KURUS:
            oran = hedef / mevcut
            for g in grup:
                for s in list(yeni[g["id"]]):
                    if SLUG_KATEGORI.get(s, "diger") == kat:
                        yeni[g["id"]][s] = g["masraflar"][s] * oran
                        if s in dagilim[g["id"]]:
                            dagilim[g["id"]][s] = {k: v * oran for k, v in dagilim[g["id"]][s].items()}
        elif abs(hedef) >= KURUS:
            slug = VARSAYILAN_SLUG[kat]
            for i, g in enumerate(grup):
                pay = (max(_f(fob.get(g["id"])), 0.0) / top_fob) if top_fob > 0 else 1.0 / len(grup)
                yeni[g["id"]][slug] = yeni[g["id"]].get(slug, 0.0) + hedef * pay
    return {i: (_yuvarla(yeni[i]), {s: _yuvarla(v) for s, v in dagilim[i].items() if s in yeni[i]})
            for i in yeni}


def _ayni_masraf(a, b):
    a, b = _yuvarla(a or {}), _yuvarla(b or {})
    return set(a) == set(b) and all(abs(a[k] - b[k]) < 0.015 for k in a)


# ── plan ────────────────────────────────────────────────────────────
def plan_yap(mikro, dosyalar, kalemler_map, masraf_oku, fob_hesapla, depo_kanonik=lambda x: x, bugun=None):
    """masraf_oku(dosya) → {slug: $} (ithalat.database._masraf_dict); fob_hesapla(dosya, kalemler) → net FOB.
    Döner: {guncelle: [{id, dosya_no, yeni {alan: değer}, eski {alan: değer}, ozet}], ekle: [dosya],
            eslesmeyen: [...], belirsiz: {...}, eslesme: {kod: [id]}}."""
    eslesme, belirsiz = eslestir(mikro, dosyalar, kalemler_map)
    dmap = {d["id"]: d for d in dosyalar}
    guncelle = []
    for kod, ids in sorted(eslesme.items()):
        m = mikro[kod]
        grup = [{"id": i, "masraflar": masraf_oku(dmap[i]),
                 "dagilim": dmap[i].get("masraf_grup_dagilim") if isinstance(dmap[i].get("masraf_grup_dagilim"), dict)
                 else {}} for i in ids]
        fob = {i: fob_hesapla(dmap[i], kalemler_map.get(i) or []) for i in ids}
        hedef = masraf_hedefi(m, grup, fob)
        for g in grup:
            d = dmap[g["id"]]
            yeni = {}
            if str(d.get("mikro_kodu") or "") != kod:
                yeni["mikro_kodu"] = kod
            if m["beyanname"] and str(d.get("mikro_beyanname") or "") != m["beyanname"]:
                yeni["mikro_beyanname"] = m["beyanname"]
            if m["giris"]:
                if str(d.get("durum") or "") != TESLIM:
                    yeni["durum"] = TESLIM
                    if d.get("stok_islendi") is not True:
                        yeni["stok_islendi"] = True       # stok Mikro'dan gelir; uygulama ikinci kez eklemesin
                # Teslim tarihi yalnız teslime geçerken ya da boşsa: canlıda 69 eski dosyada Mikro'nun giriş tarihi
                # toplu kayıt günü (2025-10-22 gibi); yazılsaydı stok yaşı (FIFO) aylarca kayardı.
                if ("durum" in yeni or not _gun(d.get("teslim_tarihi"))) and _gun(d.get("teslim_tarihi")) != m["giris"]:
                    yeni["teslim_tarihi"] = m["giris"]
                depo = depo_kanonik(m["depo"]) if m["depo"] else ""
                if depo and not str(d.get("teslim_deposu") or "").strip():
                    yeni["teslim_deposu"] = depo
            masraf_once = sum(g["masraflar"].values())
            masraf_sonra = masraf_once
            if hedef is not None:
                ym, yd = hedef[g["id"]]
                if not _ayni_masraf(g["masraflar"], ym):
                    yeni["masraflar"] = ym
                    masraf_sonra = sum(ym.values())
                    if g["dagilim"] and yd != {s: _yuvarla(v) for s, v in g["dagilim"].items()}:
                        yeni["masraf_grup_dagilim"] = yd
            if yeni:
                f = fob[g["id"]]
                guncelle.append({
                    "id": g["id"], "dosya_no": d.get("dosya_no") or d.get("pi_no") or str(g["id"]), "kod": kod,
                    "yeni": yeni, "eski": {k: d.get(k) for k in yeni},
                    "ozet": {"fob": round(f, 2), "masraf_once": round(masraf_once, 2),
                             "masraf_sonra": round(masraf_sonra, 2),
                             "yuzde_once": round(masraf_once / f * 100, 2) if f > 0 else 0.0,
                             "yuzde_sonra": round(masraf_sonra / f * 100, 2) if f > 0 else 0.0,
                             "durum_once": d.get("durum") or "", "durum_sonra": yeni.get("durum", d.get("durum") or "")}})
    bagli = set(eslesme)
    ekle, eslesmeyen = [], []
    for kod, m in sorted(mikro.items()):
        if kod in bagli or not m["urunler"]:
            continue
        if sum(abs(u["tutar"]) for u in m["urunler"].values()) < KURUS:
            sebep = "bedelsiz mal (FOB 0): masraf maliyete dağıtılamaz, eklenmedi"
        elif kod in belirsiz and belirsiz[kod] != "uygulamadaki dosyalarla adetler birebir tutmuyor" \
                or cift_riski(m, dosyalar, kalemler_map, eslesme):
            sebep = belirsiz.get(kod) or "uygulamadaki dosyalarla adetler birebir tutmuyor"
        else:
            ekle.append(yeni_dosya(m, depo_kanonik))
            continue
        eslesmeyen.append({"kod": kod, "tedarikci": m["tedarikci"] or m["isim"], "giris": m["giris"],
                           "adet": round(sum(u["adet"] for u in m["urunler"].values())), "sebep": sebep})
    return {"guncelle": guncelle, "ekle": ekle, "eslesmeyen": eslesmeyen, "belirsiz": belirsiz, "eslesme": eslesme}


def yeni_dosya(m, depo_kanonik=lambda x: x):
    """Uygulamada olmayan Mikro dosyası → yeni ithalat dosyası + kalemler."""
    masraf = _yuvarla({VARSAYILAN_SLUG[k]: v for k, v in m["masraf"].items() if abs(v) >= KURUS})
    kalemler = [{"sku": s, "adet": round(u["adet"], 2),
                 "birim_fob": round(u["tutar"] / u["adet"], 4) if u["adet"] else 0.0} for s, u in sorted(m["urunler"].items())]
    teslim = bool(m["giris"])
    return {"dosya": {"dosya_no": m["kod"], "pi_no": "", "tarih": m["fatura_tarihi"] or m["giris"] or m["olusturma"],
                      "tedarikci": m["tedarikci"] or m["isim"], "doviz": "USD", "kur": m["kur"] or 1.0,
                      "masraflar": masraf, "notlar": f"Mikro'dan ({m['kod']})",
                      "durum": TESLIM if teslim else "Yolda", "teslim_tarihi": m["giris"] or None,
                      "teslim_deposu": depo_kanonik(m["depo"]) if m["depo"] else None,
                      "stok_islendi": True if teslim else None, "mikro_kodu": m["kod"],
                      "mikro_beyanname": m["beyanname"] or None},
            "kalemler": kalemler}


def plan_ozeti(plan):
    g = plan["guncelle"]
    return {"guncellenen": len(g), "masraf_degisen": sum(1 for x in g if "masraflar" in x["yeni"]),
            "durum_degisen": sum(1 for x in g if "durum" in x["yeni"]), "yeni": len(plan["ekle"]),
            "eslesmeyen": len(plan["eslesmeyen"]), "bagli_mikro": len(plan["eslesme"])}


# ── veritabanı ──────────────────────────────────────────────────────
def _cli():
    from satis.database import _get_client
    return _get_client()


def _sayfali(tablo, secim, anahtar):
    from satis.mikro_esitle import kopyasiz
    cli, out, bas = _cli(), [], 0
    while True:
        r = cli.table(tablo).select(secim).order(anahtar).range(bas, bas + 999).execute().data or []
        out += r
        if len(r) < 1000:
            break
        bas += 1000
    return kopyasiz(out, anahtar)


def veri_oku():
    """(mikro dosyaları özeti, uygulama ithalat dosyaları, {id: kalemler})."""
    cli = _cli()
    mdos = _sayfali("mikro_ithalat_dosya", "*", "ith_kodu")
    satir = [s for s in _sayfali("mikro_alim_satir", "sth_guid,sth_tarih,sth_stok_kod,sth_miktar,sth_tutar,sth_iskonto,"
                                 "sth_giris_depo_no,sth_exim_kodu,sth_normal_iade", "sth_guid")
             if str(s.get("sth_exim_kodu") or "").strip()]
    cari = _sayfali("mikro_ithalat", "*", "cha_guid")
    unvan = {}
    for tablo in ("mikro_cari_bakiye", "mikro_cari_kart"):
        try:
            for c in cli.table(tablo).select("cari_kod,cari_unvan1").execute().data or []:
                unvan.setdefault(str(c.get("cari_kod") or ""), c.get("cari_unvan1") or "")
        except Exception:  # noqa: BLE001
            pass
    depo = {_i(d.get("dep_no")): d.get("dep_adi") or "" for d in cli.table("mikro_depo_kart").select("*").execute().data or []}
    mikro = mikro_dosyalari(mdos, satir, cari, unvan, depo)
    from ithalat.database import ithalat_mi
    dosyalar = [d for d in _sayfali("ithalat_dosyalari", "*", "id") if ithalat_mi(d)]
    kal = defaultdict(list)
    for k in _sayfali("ithalat_kalemleri", "id,dosya_id,sku,adet,birim_fob,urun_grubu", "id"):
        kal[k.get("dosya_id")].append(k)
    return mikro, dosyalar, dict(kal)


def plan_hazirla():
    from ithalat.database import _masraf_dict, dosya_hesapla
    from kayranpm.database import depo_kanonik
    mikro, dosyalar, kal = veri_oku()
    return plan_yap(mikro, dosyalar, kal, _masraf_dict,
                    lambda d, k: dosya_hesapla(d, k)["net_mal_bedeli"], depo_kanonik)


def _arsivle(cli, satir, neden):
    import json
    cli.table("mikro_esitleme_arsiv").insert({"tablo": "ithalat_dosyalari", "satir": json.loads(json.dumps(satir, default=str)),
                                              "neden": neden}).execute()


def uygula(plan):
    """Planı yazar: güncellenecek her dosyanın eski satırı önce arşive. Yeni dosya + kalemleri ekler.
    Döner: {guncellenen, yeni, hata}."""
    from shared.ana_veri import get_urun_ad_haritasi
    cli = _cli()
    sonuc = {"guncellenen": 0, "yeni": 0, "hata": []}
    for g in plan["guncelle"]:
        try:
            eski = (cli.table("ithalat_dosyalari").select("*").eq("id", g["id"]).execute().data or [None])[0]
            if not eski:
                continue
            _arsivle(cli, eski, f"mikro_ithalat:{g['kod']}")
            cli.table("ithalat_dosyalari").update(g["yeni"]).eq("id", g["id"]).execute()
            sonuc["guncellenen"] += 1
        except Exception as e:  # noqa: BLE001
            sonuc["hata"].append(f"{g['dosya_no']}: {type(e).__name__}: {str(e)[:120]}")
    adlar = {}
    try:
        adlar = get_urun_ad_haritasi() or {}
    except Exception:  # noqa: BLE001
        pass
    for y in plan["ekle"]:
        try:
            var = cli.table("ithalat_dosyalari").select("id").eq("mikro_kodu", y["dosya"]["mikro_kodu"]).execute().data
            if var:
                continue                                    # ikinci kez eklenmesin
            r = cli.table("ithalat_dosyalari").insert({k: v for k, v in y["dosya"].items() if v is not None}).execute()
            yid = (r.data or [{}])[0].get("id")
            if yid is not None and y["kalemler"]:
                cli.table("ithalat_kalemleri").insert([dict(k, dosya_id=yid, urun_adi=adlar.get(k["sku"], ""))
                                                       for k in y["kalemler"]]).execute()
            sonuc["yeni"] += 1
        except Exception as e:  # noqa: BLE001
            sonuc["hata"].append(f"{y['dosya']['dosya_no']}: {type(e).__name__}: {str(e)[:120]}")
    _onbellek_temizle()
    return sonuc


def _onbellek_temizle():
    try:
        from ithalat import database as D
        for fn in ("get_dosyalar", "get_tum_kalemler", "get_sku_ithalat_partileri"):
            getattr(getattr(D, fn, None), "clear", lambda: None)()
    except Exception:  # noqa: BLE001
        pass


def rapor_yaz(plan, sonuc, pacal_once=None, pacal_sonra=None, zaman=None):
    """Son değişiklikleri sistem_ayarlari'na yazar (ekran: Geçmiş İthalatlar › Mikro eşitlemesi)."""
    from datetime import datetime, timezone
    from kayranacc.database import get_ayar, set_ayar
    pacal = []
    for sku in sorted(set(pacal_once or {}) | set(pacal_sonra or {})):
        a, b = _f((pacal_once or {}).get(sku)), _f((pacal_sonra or {}).get(sku))
        if abs(a - b) >= KURUS:
            pacal.append({"sku": sku, "once": round(a, 2), "sonra": round(b, 2)})
    kayit = {"zaman": (zaman or datetime.now(timezone.utc)).isoformat(), "ozet": plan_ozeti(plan), "sonuc": sonuc,
             "degisen": [dict(g["ozet"], dosya_no=g["dosya_no"], kod=g["kod"], alanlar=sorted(g["yeni"]))
                         for g in plan["guncelle"]],
             "yeni": [y["dosya"]["dosya_no"] for y in plan["ekle"]], "eslesmeyen": plan["eslesmeyen"],
             "pacal": sorted(pacal, key=lambda x: -abs(x["sonra"] - x["once"]))[:60]}
    eski = get_ayar(RAPOR_ANAHTAR, {}) or {}
    gecmis = ([kayit] + list(eski.get("gecmis") or []))[:20] if (plan["guncelle"] or plan["ekle"]) else list(eski.get("gecmis") or [])
    set_ayar(RAPOR_ANAHTAR, {"son": kayit, "gecmis": gecmis})


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    """Kullanıcı kararı: varsayılan AÇIK (onay beklemeden otomatik). Kapatmak için durum {"acik": false}."""
    return durum().get("acik", True) is not False


def son_aktarim():
    r = (_cli().table("mikro_senk_durum").select("tablo,son_cekim")
         .in_("tablo", ["mikro_ithalat", "mikro_alim_satir", "mikro_ithalat_dosya"]).execute().data or [])
    zaman = [str(x.get("son_cekim") or "") for x in r if x.get("son_cekim")]
    return max(zaman) if len(zaman) == 3 else ""


def otomatik():
    """Açıksa ve aktarıcı yeni veri getirdiyse eşitler. Döner: özet ya da None. Hata fırlatmaz."""
    try:
        if not acik_mi():
            return None
        d = durum()
        son = son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        from satis.mikro_esitle import aktarim_suruyor
        if aktarim_suruyor():
            return None
        plan = plan_hazirla()
        pacal_once = pacal_sonra = None
        sonuc = {"guncellenen": 0, "yeni": 0, "hata": []}
        if plan["guncelle"] or plan["ekle"]:
            from ithalat.database import get_sku_maliyet_ozet
            pacal_once = {k: v.get("pacal_final") for k, v in (get_sku_maliyet_ozet() or {}).items()}
            sonuc = uygula(plan)
            pacal_sonra = {k: v.get("pacal_final") for k, v in (get_sku_maliyet_ozet() or {}).items()}
        rapor_yaz(plan, sonuc, pacal_once, pacal_sonra)
        from kayranacc.database import set_ayar
        set_ayar(DURUM_ANAHTAR, dict(d, acik=d.get("acik", True), son_calisma=son))
        if sonuc["hata"]:
            from shared.kayit import sessiz
            sessiz("ithalat.mikro_ithalat.otomatik", RuntimeError("; ".join(sonuc["hata"])[:400]))
        oz = plan_ozeti(plan)
        return oz if (plan["guncelle"] or plan["ekle"]) else None
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("ithalat.mikro_ithalat.otomatik", e)
        return None

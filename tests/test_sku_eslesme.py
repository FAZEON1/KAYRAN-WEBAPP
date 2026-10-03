# -*- coding: utf-8 -*-
"""SKU eşleme (Ekim 2026) — rapor SKU'su ↔ stok kartı, tahmin yerine onay.

Sorun: Müşteri Satışları'nda pazaryeri kodlu satır (HBCV…) addaki model koduyla karta
bağlanıyordu. Ad 'F11PA650B' gibi eksik kod taşıyınca önek kuralı İKİ karta uyuyor
(F11PA650BWM beyaz, F11PA650BBM siyah) ve alfabetik ilkini (siyah) seçiyordu.
Kural: tek aday → bağla; birden çok aday → 'belirsiz', kullanıcı onaylar (sku_eslesme
tablosu). Kendisi kart SKU'su olan kod başka bir karta asla eşlenemez.
"""

KARTLAR = {
    "F11PA650BWM": {"marka": "FAZEON", "kategori": "Kasa", "urun_adi": "Fazeon F11 Kasa Beyaz"},
    "F11PA650BBM": {"marka": "FAZEON", "kategori": "Kasa", "urun_adi": "Fazeon F11 Kasa Siyah"},
    "X24F180":     {"marka": "FAZEON", "kategori": "Monitör", "urun_adi": "Fazeon X24F180 Monitör"},
    "AB12345":     {"marka": "Mio", "kategori": "Araç Kamerası", "urun_adi": "Mio A"},
    "AB12399":     {"marka": "NZXT", "kategori": "Kasa", "urun_adi": "NZXT B"},
}


def _r(sku, ad=""):
    return {"firma": "HEPSIBURADA", "sku": sku, "urun_adi": ad, "haftalik_satis": 1,
            "stok_miktari": 0, "yukleme_tarihi": "2026-09-28"}


def _mh(rows, eslesme=None):
    from shared.utils import sku_anahtar
    from kayranpm.musteri_hesap import meta_hazirla
    ek = {"eslesme": eslesme} if eslesme is not None else {}
    return meta_hazirla(rows, KARTLAR, sku_fn=sku_anahtar, **ek)


# ── Belirsizlikte bağlama yok ───────────────────────────────────────

def test_iki_varyanta_uyan_kod_karta_baglanmaz():
    """Eski kod: 'F11PA650B' → F11PA650BBM (siyah) — beyaz ürün yanlış karta gidiyordu."""
    m = _mh([_r("HBCV001", "Fazeon F11PA650B Kasa Beyaz")])["HBCV001"]
    assert m["kart_sku"] == ""
    assert m["kart_kaynak"] == "belirsiz"
    assert m["adaylar"] == ["F11PA650BBM", "F11PA650BWM"]


def test_belirsizde_ortak_marka_kategori_korunur():
    """Adayların hepsi aynı marka + kategoride → kırılım değişmez, yalnız kart bağlanmaz."""
    m = _mh([_r("HBCV001", "Fazeon F11PA650B Kasa Beyaz")])["HBCV001"]
    assert m["marka"] == "FAZEON" and m["kategori"] == "Kasa"


def test_adda_iki_farkli_tam_kod_varsa_belirsiz():
    m = _mh([_r("HBCV002", "Set F11PA650BWM + F11PA650BBM")])["HBCV002"]
    assert m["kart_sku"] == "" and m["kart_kaynak"] == "belirsiz"


def test_iki_kart_ayni_ada_sahipse_belirsiz():
    kartlar = dict(KARTLAR, K1={"urun_adi": "Ortak Ad"}, K2={"urun_adi": "ortak  ad"})
    from shared.utils import sku_anahtar
    from kayranpm.musteri_hesap import meta_hazirla
    m = meta_hazirla([_r("HB9", "ORTAK AD")], kartlar, sku_fn=sku_anahtar)["HB9"]
    assert m["kart_sku"] == "" and m["adaylar"] == ["K1", "K2"]


def test_tek_aday_otomatik_baglanir():
    m = _mh([_r("HBCV003", "Fazeon 23.8' X24F180 FHD")])["HBCV003"]
    assert m["kart_sku"] == "X24F180" and m["kart_kaynak"] == "kural"


def test_tam_kod_adda_ise_dogru_varyanta_baglanir():
    m = _mh([_r("HBCV004", "Fazeon F11PA650BWM Kasa")])["HBCV004"]
    assert m["kart_sku"] == "F11PA650BWM"


def test_birebir_sku_kaynak_sku():
    m = _mh([_r("Fazeon F11PA650BWM")])["Fazeon F11PA650BWM"]
    assert m["kart_sku"] == "F11PA650BWM" and m["kart_kaynak"] == "sku"


# ── Eşleme tablosu ──────────────────────────────────────────────────

def test_tablo_belirsizi_cozer():
    m = _mh([_r("hbcv001 ", "Fazeon F11PA650B Kasa Beyaz")], eslesme={"HBCV001": "F11PA650BWM"})["hbcv001"]
    assert m["kart_sku"] == "F11PA650BWM" and m["kart_kaynak"] == "tablo" and m["adaylar"] == []


def test_kart_skusu_tablodan_once_gelir():
    """Tabloda bayat bir kayıt kalsa bile kodun KENDİ kartı kazanır."""
    m = _mh([_r("F11PA650BWM")], eslesme={"F11PA650BWM": "F11PA650BBM"})["F11PA650BWM"]
    assert m["kart_sku"] == "F11PA650BWM"


def test_tablodaki_kart_silinmisse_yok_sayilir():
    m = _mh([_r("HBCV005", "Tanımsız")], eslesme={"HBCV005": "SILINMIS"})["HBCV005"]
    assert m["kart_sku"] == "" and m["kart_kaynak"] == ""


# ── Kayıt koruması ──────────────────────────────────────────────────

def _dogrula(dis, kart, mevcut=None):
    from shared.utils import sku_anahtar
    from kayranpm.musteri_hesap import eslesme_dogrula
    return eslesme_dogrula(dis, kart, KARTLAR, sku_fn=sku_anahtar, mevcut=mevcut)


def test_kart_skusu_baska_karta_eslenemez():
    ok, msg, _ = _dogrula("F11PA650BWM", "F11PA650BBM")
    assert not ok and "F11PA650BBM" in msg


def test_onekli_kart_skusu_da_baska_karta_eslenemez():
    ok, _, _ = _dogrula("Fazeon f11pa650bwm", "F11PA650BBM")
    assert not ok


def test_olmayan_karta_eslenemez():
    ok, msg, _ = _dogrula("HBCV001", "YOK123")
    assert not ok and "YOK123" in msg


def test_bos_dis_kod_reddedilir():
    ok, _, _ = _dogrula("  ", "F11PA650BWM")
    assert not ok


def test_baska_karta_esli_kod_once_kaldirilmali():
    ok, msg, _ = _dogrula("HBCV001", "F11PA650BWM", mevcut={"HBCV001": "F11PA650BBM"})
    assert not ok and "F11PA650BBM" in msg


def test_gecerli_eslesme_kanonik_doner():
    ok, _, kayit = _dogrula(" hbcv001", "f11pa650bwm")
    assert ok and kayit == {"dis_kod": "HBCV001", "kart_sku": "F11PA650BWM"}


def test_ayni_eslesme_tekrar_kaydedilebilir():
    ok, _, _ = _dogrula("HBCV001", "F11PA650BWM", mevcut={"HBCV001": "F11PA650BWM"})
    assert ok

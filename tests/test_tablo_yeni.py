# -*- coding: utf-8 -*-
"""Ortak tablo bileşeni (Ekim 2026) — tasarım yenileme, 1. adım.

Görünüm/etkileşim tarayıcıda; burada SAF veri hazırlığı ve bağlantılar sınanır.
"""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

SATIR = [
    {"Kanal": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI", "Adet": 54425,
     "Ciro": 3307348.71, "Net Kâr": 1029742.12, "Marj": 31.13},
    {"Kanal": "HARUN GÜNEYSU", "Adet": 8124, "Ciro": 191014.26, "Net Kâr": -23436.71, "Marj": -12.27},
    {"Kanal": "Σ Toplam", "Adet": 62549, "Ciro": 3498362.97, "Net Kâr": 1006305.41, "Marj": 28.76},
]


def _veri(**kw):
    from shared.tablo import tablo_veri
    return tablo_veri(SATIR, **kw)


# ── Biçim ───────────────────────────────────────────────────────────
def test_turkce_bicim():
    v = _veri()
    h = v["satirlar"][0]["h"]
    assert h[1] == "54.425"
    assert h[2] == "$3.307.348,71"
    assert h[4] == "%31,1"            # eskiden ızgarada "31.1%" yazıyordu


def test_ham_deger_siralama_icin():
    v = _veri()
    assert v["satirlar"][0]["s"][2] == 3307348.71
    assert v["satirlar"][1]["s"][0] == "HARUN GÜNEYSU"


def test_kolon_tipleri_ve_hiza():
    k = _veri()["kolonlar"]
    assert [c["tip"] for c in k] == [None, "adet", "para", "para", "oran"]
    assert k[0]["hiza"] == "sol" and k[2]["hiza"] == "sag"


def test_toplam_satiri_ayrilir():
    v = _veri()
    assert len(v["satirlar"]) == 2
    assert v["toplam"]["h"][0] == "Σ Toplam"


def test_eksi_oran_turkce():
    v = _veri()
    assert v["satirlar"][1]["h"][4] == "-%12,3"        # eskiden "%-12,3"


def test_kar_gizleme_maskesi_bozulmaz():
    from shared.tablo import tablo_veri
    v = tablo_veri([{"Kanal": "A", "Net Kâr": "•••", "Marj": "•••"}])
    assert v["satirlar"][0]["h"][1:] == ["•••", "•••"] and v["satirlar"][0]["rz"][2] == ""


def test_eksi_deger_isaretlenir():
    v = _veri()
    assert v["satirlar"][1]["neg"][3] is True and v["satirlar"][0]["neg"][3] is False


def test_marj_rozeti_esikleri():
    from shared.tablo import marj_sinifi
    assert marj_sinifi(31) == "iyi"
    assert marj_sinifi(20) == "orta"
    assert marj_sinifi(8) == "dusuk"
    assert marj_sinifi(-3) == "eksi"


def test_rozet_yalniz_marj_kolonunda():
    k = _veri()["kolonlar"]
    assert k[4]["rozet"] is True
    assert not any(c["rozet"] for c in k[:4])


def test_pay_cubugu_istege_bagli():
    v = _veri(pay="Ciro")
    assert v["pay"] == 2
    p = v["satirlar"][0]["pay"]
    assert 94 < p < 95                  # 3.307.348 / (3.307.348 + 191.014)
    assert _veri()["pay"] is None


def test_gizli_alanlar_kolon_olmaz_ve_tasinir():
    from shared.tablo import tablo_veri
    v = tablo_veri([{"Kanal": "Vatan Bilgisayar", "Ciro": 1, "_etiket": "A.Ş.", "_ipucu": "VATAN … ŞİRKETİ"}])
    assert [c["ad"] for c in v["kolonlar"]] == ["Kanal", "Ciro"]
    assert v["satirlar"][0]["etiket"] == "A.Ş." and v["satirlar"][0]["ipucu"] == "VATAN … ŞİRKETİ"


def test_satir_kimligi_ozgun_sirada():
    v = _veri()
    assert [r["i"] for r in v["satirlar"]] == [0, 1]


def test_arama_kendiliginden_uzun_tabloda():
    from shared.tablo import tablo_veri
    kisa = tablo_veri([{"Ad": str(i)} for i in range(5)])
    uzun = tablo_veri([{"Ad": str(i)} for i in range(20)])
    assert kisa["arama"] is False and uzun["arama"] is True


def test_adsiz_sayi_kolonu_saga_ve_turkce():
    """'Kapsama (hft)', 'Acil' gibi adından tipi çıkmayan sayı kolonları."""
    from shared.tablo import tablo_veri
    v = tablo_veri([{"Kategori": "Kasa", "Kapsama (hft)": 61.4, "Acil": 1200},
                    {"Kategori": "Fan", "Kapsama (hft)": None, "Acil": 0}])
    k = v["kolonlar"]
    assert k[1]["hiza"] == "sag" and k[2]["hiza"] == "sag" and k[0]["hiza"] == "sol"
    assert v["satirlar"][0]["h"][1:] == ["61,4", "1.200"]
    assert v["satirlar"][0]["s"][1] == 61.4


def test_karisik_kolon_metin_kalir():
    from shared.tablo import tablo_veri
    v = tablo_veri([{"Kod": 12}, {"Kod": "A-7"}])
    assert v["kolonlar"][0]["hiza"] == "sol"


def test_bos_ve_nan_hucre():
    from shared.tablo import tablo_veri
    v = tablo_veri([{"Ad": None, "Ciro": float("nan")}])
    assert v["satirlar"][0]["h"] == ["", ""]


# ── Ünvan kısaltma ──────────────────────────────────────────────────
def test_kisa_unvan():
    from shared.tablo import kisa_unvan
    vakalar = {
        "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI": ("Vatan Bilgisayar", "A.Ş."),
        "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ": ("EERA Elektronik", "A.Ş."),
        "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ": ("D-Market Elektronik", "A.Ş."),
        "MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ": ("Monday Bilişim", "A.Ş."),
        "HARUN GÜNEYSU": ("Harun Güneysu", ""),
        "ELMACIK BİLGİSAYAR BİLİŞİM VE REKLAMCILIK TİCARET VE SANAYİ LİMİTED ŞİRKETİ": ("Elmacık Bilgisayar", "Ltd. Şti."),
        "AVASYA TEKNOLOJİ SANAYİ VE DIŞ TİCARET LİMİTED ŞİRKETİ": ("Avasya Teknoloji", "Ltd. Şti."),
        "HURACAN PC BİLİŞİM TEKNOLOJİLERİ SANAYİ TİCARET LİMİTED ŞİRKETİ": ("Huracan PC", "Ltd. Şti."),
        "TEKNORYA BİLİŞİM HİZMETLERİ SANAYİ VE TİCARET ANONİM ŞİRKETİ": ("Teknorya Bilişim", "A.Ş."),
        "GÜNEŞ BİLGİSAYAR İLETİŞİM SİSTEMLERİ ANONİM ŞİRKETİ": ("Güneş Bilgisayar", "A.Ş."),
    }
    for tam, bek in vakalar.items():
        assert kisa_unvan(tam) == bek, tam


def test_kisa_unvan_doviz_carisini_korur():
    """Aynı firmanın TL / USD carisi ayrışmalı (shared.utils.firma_kisa_ad kuralı)."""
    from shared.tablo import kisa_unvan
    assert kisa_unvan("EERA BİLGİSAYAR SANAYİ VE TİCARET LİMİTED ŞİRKETİ USD") == ("EERA Bilgisayar · USD", "Ltd. Şti.")
    assert kisa_unvan("EERA BİLGİSAYAR SANAYİ VE TİCARET LİMİTED ŞİRKETİ") == ("EERA Bilgisayar", "Ltd. Şti.")


def test_kisa_unvan_zaten_kisa_ad_dokunulmaz():
    from shared.tablo import kisa_unvan
    assert kisa_unvan("Vatan") == ("Vatan", "")
    assert kisa_unvan("") == ("", "")


# ── Bağlantılar ─────────────────────────────────────────────────────
def test_eski_ortak_tablo_yeni_bilesene_gider():
    src = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    g = src[src.index("def tablo_sirali"):]
    g = g[:g.index("\ndef ") if "\ndef " in g else len(g)]
    assert "from shared.tablo import tablo" in g


def test_firma_kirilimi_yeni_bilesende():
    src = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    i = src.index('grup_basligi("Firma kırılımı"')
    blok = src[i:i + 2500]
    assert 'key="pnl_kanal_df"' in blok
    assert "on_select=" not in blok and "secilebilir=True" in blok
    assert "kisa_unvan(" in blok


# ── 2. adım: kalıcı / çoklu seçim, satır kimliği, satır para birimi ──
def test_satir_para_birimi():
    from shared.tablo import tablo_veri
    v = tablo_veri([{"Ref No": "R1", "Tutar": 1500.0, "_birim": "₺"},
                    {"Ref No": "R2", "Tutar": 200.0}])
    assert v["satirlar"][0]["h"][1].startswith("₺") and v["satirlar"][1]["h"][1].startswith("$")


def test_satir_kimligi_secim_icin():
    """Seçim sıraya değil kimliğe bağlı: süzgeç değişince seçili satır başka belgeye kaymaz."""
    from shared.tablo import tablo_veri
    v = tablo_veri([{"Belge": "A", "_id": 41}, {"Belge": "B", "_id": "x-7"}])
    assert [r["id"] for r in v["satirlar"]] == ["41", "x-7"]
    v2 = tablo_veri([{"Belge": "A"}, {"Belge": "B"}])
    assert [r["id"] for r in v2["satirlar"]] == ["0", "1"]


def test_secim_cozumu():
    from shared.tablo import secim_coz
    v = [{"_id": 41}, {"_id": 7}]
    assert secim_coz(["7"], v) == [1]                       # kimlik → güncel sıra
    assert secim_coz(["99"], v) == []                       # artık listede yok → düşer
    assert secim_coz("41", v) == [0] and secim_coz(None, v) == []


def test_bilesen_kalici_ve_coklu_secim():
    import inspect
    from shared import tablo as T
    p = inspect.signature(T.tablo).parameters
    assert "kalici" in p and "coklu" in p
    assert 'setStateValue("secililer"' in T._JS and 'setStateValue("secili"' in T._JS


def test_kalan_izgaralar_ortak_tabloda():
    from pathlib import Path
    K = Path(__file__).resolve().parent.parent
    # kayranpm/ref_no.py'deki on_select'li tablo (_render_tumu) 28.07.2026'dan beri çağrılmıyor
    # (ekran ref_ekran.py'ye taşındı) — ölü kod, taşınmadı.
    for d in ("ithalat/main.py", "kayranpm/stok_karti.py"):
        s = (K / d).read_text(encoding="utf-8")
        assert "on_select=" not in s, d
    assert "coklu=True" in (K / "ithalat/main.py").read_text(encoding="utf-8")
    assert (K / "kayranpm/stok_karti.py").read_text(encoding="utf-8").count("kalici=True") == 3


def test_kompakt_tablo_kart_gorunumune_gecmez():
    """Yan yana düzende dar sütun (~330 px) masaüstünde de kart yığınına dönüyordu
    (Müşteri Satışları'nda tarayıcıda görüldü). kompakt=True → tablo kalır."""
    import inspect
    from shared import tablo as T
    assert "kompakt" in inspect.signature(T.tablo).parameters
    assert "container-name:kt" in T._CSS and "@container kt (max-width:560px)" in T._CSS
    assert ".kt.kompakt{container-name:kt-kompakt" in T._CSS
    assert 'classList.toggle("kompakt", !!D.kompakt)' in T._JS
    i = T._CSS.index("@media (max-width:640px){")                 # telefonda yine kart listesi
    assert ".kt.kompakt thead{display:none}" in T._CSS[i:]

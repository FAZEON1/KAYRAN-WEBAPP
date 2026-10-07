# -*- coding: utf-8 -*-
"""Kampanya kapanınca otomatik Ref No (Ekim 2026).

Kampanya Takip'te kapatılan kampanya için Ref No Takip'e kendiliğinden ref açılır: tutar kampanyanın
toplam desteği (Σ (firma + ek destek) × satılan adet, USD; spiff varsa ayrı TL ref), aynı kampanyaya
ikinci kez açılmaz, eşleşmeyen firmada açılmaz; kapatan kişiye ve İbrahim'e mail gider.
"""
from datetime import date
from pathlib import Path

import pytest

from kayranpm import kampanya_ref as KR

KOK = Path(__file__).resolve().parent.parent
FIRMALAR = [
    {"id": 1, "firma_adi": "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI", "firma_kodu": "VTN"},
    {"id": 2, "firma_adi": "D-MARKET ELEKTRONİK HİZMETLER VE TİCARET ANONİM ŞİRKETİ", "firma_kodu": "HB"},
    {"id": 3, "firma_adi": "EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ", "firma_kodu": "EER"},
    {"id": 4, "firma_adi": "MONDAY BİLİŞİM SANAYİ VE TİCARET ANONİM ŞİRKETİ", "firma_kodu": "MND"},
]
KAMP = {"id": 107, "kampanya_adi": "AĞUSTOS EK DESTEK", "firma": "VATAN", "kategori": "monitör",
        "baslangic_tarihi": "2026-08-01", "bitis_tarihi": "2026-08-31", "spiff_tl": 0}
URUNLER = [
    {"sku": "A", "satis_fiyati": 120, "birim_firma_destek": 5, "birim_ek_destek": 1, "satilan_adet": 100},
    {"sku": "B", "satis_fiyati": 260, "birim_firma_destek": 12, "birim_ek_destek": 0, "satilan_adet": 13},
]
BUGUN = date(2026, 10, 6)


class _Kayit:
    def __init__(self):
        self.cagri = []

    def __call__(self, firma_id, kod, aciklama, durum, tarih, yil, tutar, doviz, kategori, ay, dyil):
        self.cagri.append(dict(firma_id=firma_id, kod=kod, aciklama=aciklama, durum=durum, tarih=tarih,
                               tutar=tutar, doviz=doviz, kategori=kategori, ay=ay, yil=dyil))
        return True, f"FZ{kod}RF2026{len(self.cagri):03d}"


@pytest.mark.parametrize("firma, kod", [("VATAN", "VTN"), ("HB", "HB"), ("ITOPYA", "EER"), ("DİĞER", None),
                                        ("VATAN BİLGİSAYAR SAN. VE TİC. A.Ş.", "VTN")])
def test_kampanya_firmasi_ref_firmasina_baglanir(firma, kod):
    f = KR.ref_firmasi_sec(firma, FIRMALAR)
    assert (f or {}).get("firma_kodu") == kod


def test_kapaninca_kampanya_destegiyle_ref_acilir():
    kayit = _Kayit()
    s = KR.kapaninca_ref_ac(KAMP, URUNLER, FIRMALAR, lambda fid: [], kayit, BUGUN)
    # 100 × (5 + 1) + 13 × 12 = 756 $ (Kampanya Takip'teki toplam destekle aynı)
    assert kayit.cagri == [dict(firma_id=1, kod="VTN", aciklama="AĞUSTOS EK DESTEK · Kampanya #107",
                                durum="beklemede", tarih=BUGUN, tutar=756.0, doviz="USD", kategori="monitör",
                                ay=8, yil=2026)]
    assert s["acilan"] == [("FZVTNRF2026001", 756.0, "USD")]
    assert "FZVTNRF2026001 ($756,00)" in KR.ekran_mesaji(s)


def test_spiff_ayri_tl_ref():
    kayit = _Kayit()
    KR.kapaninca_ref_ac(dict(KAMP, spiff_tl=3540), URUNLER, FIRMALAR, lambda fid: [], kayit, BUGUN)
    assert [(c["tutar"], c["doviz"]) for c in kayit.cagri] == [(756.0, "USD"), (3540.0, "TL")]
    assert kayit.cagri[1]["aciklama"] == "AĞUSTOS EK DESTEK SPIFF · Kampanya #107"


def test_ayni_kampanyaya_ikinci_ref_acilmaz():
    """Kampanya yeniden açılıp kapatılsa da ref bir kez açılır (işaret: 'Kampanya #<no>')."""
    kayit = _Kayit()
    var = [{"ref_no": "FZVTNRF2026052", "aciklama": "AĞUSTOS EK DESTEK · Kampanya #107", "durum": "beklemede"},
           {"ref_no": "FZVTNRF2026053", "aciklama": "BAŞKA · Kampanya #1070"}]
    s = KR.kapaninca_ref_ac(KAMP, URUNLER, FIRMALAR, lambda fid: var, kayit, BUGUN)
    assert kayit.cagri == [] and s["mevcut"] == ["FZVTNRF2026052"]
    assert "zaten var" in KR.ekran_mesaji(s)
    assert KR.mevcut_refler(var, 10) == []                       # #10 ≠ #107 / #1070


def test_eslesmeyen_firma_ve_destegi_sifir_kampanya_ref_acmaz():
    kayit = _Kayit()
    s = KR.kapaninca_ref_ac(dict(KAMP, firma="DİĞER"), URUNLER, FIRMALAR, lambda fid: [], kayit, BUGUN)
    assert kayit.cagri == [] and "elle girilmeli" in s["sorun"]
    s = KR.kapaninca_ref_ac(KAMP, [dict(u, satilan_adet=0) for u in URUNLER], FIRMALAR, lambda fid: [], kayit,
                            BUGUN)
    assert kayit.cagri == [] and "desteği 0" in s["sorun"]


def test_ayni_ay_elle_girilmis_ref_uyarilir():
    """Bugün aylık toplu ref giriliyor; aynı destek iki kez sayılmasın diye gösterilir."""
    refler = [
        {"ref_no": "FZVTNRF2026051", "aciklama": "AĞUSTOS AYI MONİTÖR SELLOUT", "durum": "paylasildi",
         "doviz": "USD", "aylik": {"2026-08": 11553}},
        {"ref_no": "FZVTNRF2026050", "aciklama": "AĞUSTOS SPIFF", "durum": "paylasildi", "doviz": "TL",
         "aylik": {"2026-08": 3540}},                                                 # başka döviz
        {"ref_no": "FZVTNRF2026049", "aciklama": "İPTAL", "durum": "iptal", "doviz": "USD", "tarih": "2026-08-10"},
        {"ref_no": "FZVTNRF2026046", "aciklama": "TEMMUZ", "durum": "paylasildi", "doviz": "USD",
         "tarih": "2026-07-17"},
    ]
    o = KR.onizleme(KAMP, URUNLER, FIRMALAR, lambda fid: refler)
    assert [r["ref_no"] for r in o["benzer"]] == ["FZVTNRF2026051"]


def test_mail_kapatana_ve_ibrahime():
    adres = {"ibrahim": "i@x.com", "derya": "d@x.com"}
    assert KR.mail_alicilari("Derya", adres) == ["d@x.com", "i@x.com"]
    assert KR.mail_alicilari("ibrahim", adres) == ["i@x.com"]
    assert KR.mail_alicilari("kemal", adres) == ["i@x.com"]          # adresi yoksa atlanır
    s = {"firma": FIRMALAR[0], "acilan": [("FZVTNRF2026052", 756.0, "USD")], "mevcut": [], "hatalar": [],
         "sorun": "", "benzer": ["FZVTNRF2026051"]}
    konu, html = KR.mail_icerigi(dict(KAMP, kampanya_adi="<b>X</b>"), s, "derya")
    assert "ref açıldı" in konu and "FZVTNRF2026052" in html and "$756,00" in html
    assert "<b>X</b>" not in html and "FZVTNRF2026051" in html     # ad kaçışlı; elle ref uyarısı


def test_iki_kapatma_dugmesi_de_ref_acar():
    s = (KOK / "kayranpm" / "kampanya.py").read_text(encoding="utf-8")
    assert s.count("_yenile(kid, _kapat_ve_ref_ac(kamp))") == 2
    for g in s.split("\ndef ")[1:]:
        if not g.startswith("_kapat_ve_ref_ac"):
            assert "kapat_kampanya(kid)" not in g, g.split("(")[0]


# ── Ekim 2026: Ref No Takip'teki BÜTÜN firmalar kampanyada seçilebilir ve ref'i bağlanır ──
TUM_FIRMALAR = FIRMALAR + [
    {"id": 7, "firma_adi": "BİOSİS BİLGİSAYAR İLETİŞİM OTOMASYON SANAYİ VE TİCARET ANONİM ŞİRKETİ",
     "firma_kodu": "BIO"},
    {"id": 8, "firma_adi": "RVOTEC TEKNOLOJİ SANAYİ TİCARET LİMİTED ŞİRKETİ", "firma_kodu": "RVT"},
]


def test_ref_firmasi_kampanya_yazimina_cevrilir():
    from kayranpm.ref_no import ref_firma_kodu
    assert [ref_firma_kodu(f) for f in TUM_FIRMALAR] == [
        "VATAN", "HB", "ITOPYA", "MONDAY",
        "BİOSİS BİLGİSAYAR İLETİŞİM OTOMASYON SANAYİ VE TİCARET ANONİM ŞİRKETİ",
        "RVOTEC TEKNOLOJİ SANAYİ TİCARET LİMİTED ŞİRKETİ"]


@pytest.mark.parametrize("firma, kod", [
    ("MONDAY", "MND"),
    ("BİOSİS BİLGİSAYAR İLETİŞİM OTOMASYON SANAYİ VE TİCARET ANONİM ŞİRKETİ", "BIO"),
    ("RVOTEC TEKNOLOJİ SANAYİ TİCARET LİMİTED ŞİRKETİ", "RVT"),
    ("AVASYA TEKNOLOJİ", None), ("DİĞER", None)])
def test_ana_olmayan_firmanin_kampanyasi_da_ref_firmasina_baglanir(firma, kod):
    assert (KR.ref_firmasi_sec(firma, TUM_FIRMALAR) or {}).get("firma_kodu") == kod


def test_biosis_kampanyasi_kapaninca_ref_acilir():
    kayit = _Kayit()
    kf = TUM_FIRMALAR[4]["firma_adi"]
    s = KR.kapaninca_ref_ac(dict(KAMP, firma=kf), URUNLER, TUM_FIRMALAR, lambda fid: [], kayit, BUGUN)
    assert [(c["firma_id"], c["kod"], c["tutar"]) for c in kayit.cagri] == [(7, "BIO", 756.0)]
    assert s["acilan"] and not s["sorun"]


def test_kampanya_firma_listesinde_ref_firmalari(monkeypatch):
    import kayranpm.database as D
    import kayranpm.ref_no as N
    from kayranpm import kampanya
    monkeypatch.setattr(D, "get_firma_listesi", lambda: ["ITOPYA", "HB", "VATAN", "MONDAY", "DIGER"])
    monkeypatch.setattr(N, "get_firmalar", lambda: TUM_FIRMALAR)
    sec = kampanya._firma_secenekleri()
    assert sec[:4] == ["ITOPYA", "HB", "VATAN", "MONDAY"] and sec[-1] == "DİĞER"
    assert TUM_FIRMALAR[4]["firma_adi"] in sec and TUM_FIRMALAR[5]["firma_adi"] in sec
    assert len(sec) == len(set(sec)) == 7                     # ana firmalar ikinci kez eklenmez

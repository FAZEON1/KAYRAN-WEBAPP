# -*- coding: utf-8 -*-
"""Teknik servis bildirimi (Ekim 2026, Berkay): ürün grubu tekrarları, merkezdeki ürünün satış düğmeleri,
depo adları, değişim / iade belgesi."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from teknikservis import ts_masasi as M  # noqa: E402
from teknikservis import ts_hesap as H  # noqa: E402
from teknikservis.stok import ts_depo_ad  # noqa: E402


def satis_disi_neden(k):
    """Eski kodda kural yoktu: her kayıt (satılmamışsa) satılabilir sayılıyordu."""
    f = getattr(H, "satis_disi_neden", None)
    return f(k) if f else ("satıldı" if k.get("mevcut_durum") == "satıldı" else "")


def _masa(satir, **kw):
    try:
        return M.depo_masa_verisi(satir, satir, DEPOLAR, BUGUN, lambda k: "Depoya transfer", **kw)
    except TypeError:                     # eski imza: grup_ad / depo_ad yok
        return M.depo_masa_verisi(satir, satir, DEPOLAR, BUGUN, lambda k: "Depoya transfer")

BUGUN = date(2026, 10, 15)
DEPOLAR = ["teknik servis", "iade", "outlet", "ikinci el", "hurda", "merkez"]


def _k(i, durum, **x):
    d = {"id": i, "servis_form_no": f"G5F{i:05d}", "arayuz": "teknik", "stok_kodu": f"SK{i}", "stok_adi": f"Ürün {i}",
         "seri_no": f"SN{i}", "firma_bilgisi": "SON KULLANICI", "mevcut_durum": durum,
         "mal_kabul_tarihi": "2026-10-01T10:00:00", "depo_tarihi": "2026-10-12T10:00:00", "fatura_mevcut": True}
    d.update(x)
    return d


# ── 1. Ürün grubu: 'Kasa' / 'kasa' tek seçenek ───────────────────────
@pytest.fixture()
def ts_db(monkeypatch):
    from teknikservis import database as D
    import shared.ana_veri as A
    kayit = [{"urun_grubu": g} for g in ("kasa", "Kasa", "monitör", "Monitör", "Ekran Kartı", "ekran kartı",
                                         "depolama", "Depolama", "cpu soğutucu", "", None)]
    monkeypatch.setattr(D, "get_kayitlar", lambda *a, **k: kayit)
    monkeypatch.setattr(A, "_kategori_kaynaklari", lambda: (["MONİTÖR", "Kasa"], []))
    monkeypatch.setattr(A, "_kural_kategoriler", lambda: ["Monitör", "Kasa", "Ekran Kartı"], raising=False)
    return D


def test_urun_grubu_secenekleri_tekil(ts_db):
    """Canlıda 14 yazım vardı: 'Kasa' 168 + 'kasa' 152, 'Monitör' 277 + 'monitör' 128 ... (15.10.2026)."""
    g = ts_db.ts_urun_gruplari()
    assert hasattr(ts_db, "ts_grup_haritasi"), f"tek yazım haritası yok; seçenekler: {g}"
    from shared.ana_veri import kategori_anahtar
    anahtarlar = [kategori_anahtar(x) for x in g]
    assert len(anahtarlar) == len(set(anahtarlar)), g
    assert "Kasa" in g and "kasa" not in g and "Monitör" in g and "monitör" not in g
    assert "Ekran Kartı" in g and "ekran kartı" not in g
    h = ts_db.ts_grup_haritasi()
    assert ts_db.ts_grup_ad("kasa", h) == "Kasa" and ts_db.ts_grup_ad("MONITÖR", h) == "Monitör"
    assert ts_db.ts_grup_ad("", h) == "" and ts_db.ts_grup_ad(None, h) == ""
    assert set(ts_db.ts_grup_ad(x, h) for x in g) == set(g)          # seçenek = görünen ad


def test_serbest_yeni_grup_kutusu_yok():
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert "Ürün grubu listede yoksa yaz (yeni grup)" not in s     # mal kabul
    assert "➕ Yeni grup…" not in s                                 # evraksız ürün kayıt


def test_depolar_grup_suzgeci_tek_secenek():
    satir = [_k(1, "satışa hazır", depo="outlet", urun_grubu="kasa"),
             _k(2, "satışa hazır", depo="outlet", urun_grubu="Kasa"),
             _k(3, "satışa hazır", depo="outlet", urun_grubu="monitör")]
    harita = {"kasa": "Kasa", "monitor": "Monitör"}
    v = _masa(satir, grup_ad=lambda g: harita.get(g.lower().replace("ö", "o"), g))
    sec = next(s for s in v["secimler"] if s["alan"] == "grup")["secenekler"]
    assert [x["k"] for x in sec] == ["Kasa", "Monitör"]
    assert {x["id"]: x["grup"] for x in v["satirlar"]} == {1: "Kasa", 2: "Kasa", 3: "Monitör"}


# ── 2. Merkez deposundaki ürün Depolar'dan satılmaz ───────────────────
def test_satis_disi_neden():
    assert satis_disi_neden(_k(1, "gönderildi", depo="merkez"))           # G5F00148: merkez + gönderildi
    assert satis_disi_neden(_k(2, "satışa hazır", depo="merkez"))
    assert satis_disi_neden(_k(3, "satıldı", depo="outlet")) == "satıldı"
    assert satis_disi_neden(_k(4, "gönderildi", depo="outlet"))
    assert satis_disi_neden(_k(5, "satışa hazır", depo="outlet")) == ""
    assert satis_disi_neden(_k(6, "iade alındı", depo="teknik servis")) == ""   # G5F00801: değişmedi


def test_merkezdeki_urun_toplu_satista_yok():
    satir = [_k(1, "gönderildi", depo="merkez"), _k(2, "satışa hazır", depo="outlet")]
    v = _masa(satir)
    assert {x["id"]: x["satilabilir"] for x in v["satirlar"]} == {1: False, 2: True}


def test_ayrintida_dugmeler_kapali_kurala_bagli():
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    d = s[s.index("def _depo_detay(k):"):s.index("        with st.container(border=True):", s.index("def _depo_detay(k):"))]
    assert "_kapali = satis_disi_neden(k)" in d
    assert d.count("if not _kapali:") == 2 and "if not satildi:" not in d       # Satışa Hazır + Satıldı
    assert "_dlg_toplu_satis([k for k in goster if not satis_disi_neden(k)])" in s
    assert '_satilabilir = [k for k in goster if not satis_disi_neden(k)]' in s


# ── 3. Depo adları Depo modülündeki gibi ─────────────────────────────
def test_depo_adlari_depo_modulu_ile_ayni():
    assert [ts_depo_ad(d) for d in DEPOLAR] == ["TEKNİK DEPO", "İADE DEPO", "OUTLET DEPO", "İKİNCİ EL DEPO",
                                                 "HURDA DEPO", "MERKEZ DEPO"]
    satir = [_k(1, "gönderildi", depo="merkez"), _k(2, "satışa hazır", depo="outlet")]
    v = _masa(satir, depo_ad=ts_depo_ad)
    assert {x["id"]: x["depo_ad"] for x in v["satirlar"]} == {1: "MERKEZ DEPO", 2: "OUTLET DEPO"}
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert 'placeholder="Bütün depolar", format_func=_stok.ts_depo_ad' in s


# ── 4. Değişim / İade Belgesi ─────────────────────────────────────────
def _iade_modulu():
    import importlib.util
    assert importlib.util.find_spec("teknikservis.iade_belge"), "değişim / iade belgesi üretilmiyordu"


def test_iade_belgesi_uygunluk_ve_onay_tarihi():
    _iade_modulu()
    from teknikservis.iade_belge import iade_belgesi_uygun, iade_onay_tarihi
    assert iade_belgesi_uygun({"mevcut_durum": "iade alındı"})
    assert iade_belgesi_uygun({"mevcut_durum": "gönderildi", "ariza_sonucu": "iade alındı"})
    assert not iade_belgesi_uygun({"mevcut_durum": "satışa hazır"})
    gecmis = [{"durum": "teknisyende", "tarih": "2026-10-10T09:00:00"},
              {"durum": "iade alındı", "tarih": "2026-10-12T11:00:00"},
              {"durum": "iade alındı", "tarih": "2026-10-13T11:00:00"}]
    assert iade_onay_tarihi({}, gecmis) == date(2026, 10, 12)               # ilk iade satırı
    assert iade_onay_tarihi({"depo_tarihi": "2026-10-09T08:00:00"}, []) == date(2026, 10, 9)


def test_iade_belgesi_metni():
    _iade_modulu()
    from teknikservis.iade_belge import belge_metni, GECERLILIK_GUN
    k = _k(801, "iade alındı", stok_kodu="X24F241S", stok_adi="FAZEON X24F241S 24\" 240Hz",
           seri_no="M2512M02539", musteri_adi="Zeki Öksüz", musteri_tel="0532 000 00 00", ariza="panel hasarlı")
    m = belge_metni(k, {"unvan": "G5F TEKNOLOJİ A.Ş.", "tel": "0212 000 00 00"}, date(2026, 10, 12), BUGUN)
    assert m["baslik"] == "DEĞİŞİM / İADE BELGESİ"
    assert dict(m["ust"]) == {"Referans No": "G5F00801", "Belge Tarihi": "15.10.2026",
                              "İade Onay Tarihi": "12.10.2026"}
    u = dict(m["urun"])
    assert u["İthalatçı Firma"] == "G5F TEKNOLOJİ A.Ş." and u["Seri No"] == "M2512M02539"
    assert u["Ürün Modeli"].startswith("X24F241S — FAZEON") and u["Tüketici Adı"] == "Zeki Öksüz"
    assert str(GECERLILIK_GUN) in m["gecerlilik"] and "(0212 000 00 00)" in m["dikkat"][0]
    assert m["imza"] == ["G5F TEKNOLOJİ A.Ş.", "Teknik Servis"]


def test_iade_belgesi_pdf_uretilir():
    pytest.importorskip("reportlab")
    _iade_modulu()
    from teknikservis.iade_belge import iade_belgesi_pdf
    b = iade_belgesi_pdf(_k(801, "iade alındı", musteri_adi="Zeki Öksüz"),
                         [{"durum": "iade alındı", "tarih": "2026-10-12T11:00:00"}],
                         sirket={"unvan": "G5F TEKNOLOJİ A.Ş."}, bugun=BUGUN)
    assert b[:4] == b"%PDF" and len(b) > 1500


def test_iade_belgesi_dugmesi_iki_ayrintida():
    s = (KOK / "teknikservis" / "main.py").read_text(encoding="utf-8")
    assert '_iade_belgesi_dugmesi(kayit, get_gecmis(kid), f"ts_iade_belge_{kid}")' in s     # teknik servis
    assert '_iade_belgesi_dugmesi(k, _gec, f"depo_iade_belge_{kid}")' in s                 # depolar

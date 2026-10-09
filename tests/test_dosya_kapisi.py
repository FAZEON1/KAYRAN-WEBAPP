# -*- coding: utf-8 -*-
"""Dosya kapısı (Ekim 2026): bütün Excel yüklemeleri tek pencerede (shared/dosya_kapisi).

Tanıma (shared/dosya_tani) her yükleme ekranının kendi okuyucusunun aradığı başlıklarla çalışır;
her türün örnek dosyası (tests/kapi_ornekleri.py) TEK ve KESİN olarak doğru türe gitmeli, tanınmayan
dosya hiçbir yere gönderilmemeli. Sayfalardaki eski yükleme kutuları kaldırıldı: yeni bir
st.file_uploader kapı dışında açılırsa bu test kızarır.
Kapının içindeki akışların gerçek Streamlit'te çalışması: tests/duman/test_dosya_kapisi.py.
"""
import ast
from pathlib import Path

import pytest

from kapi_ornekleri import ORNEKLER
from shared.dosya_tani import tani, KESIN

KOK = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("tur", sorted(ORNEKLER))
def test_her_tur_tek_ve_kesin_taninir(tur):
    ad, veri = ORNEKLER[tur]()
    r = tani(ad, veri)
    assert [(x["tur"], x["guven"]) for x in r] == [(tur, KESIN)], r


def test_tum_kapi_turlerinin_ornegi_var():
    from shared.dosya_kapisi import TURLER
    assert set(TURLER) == set(ORNEKLER)


def test_vatan_siparisi_g5f_sayilmaz():
    """VATAN sipariş Excel'inde müşterinin 'Depo' kodu sütunu var; fiyatlı dosya stok sayımı değildir."""
    ad, veri = ORNEKLER["siparis_vatan"]()
    assert "g5f_sayim" not in {x["tur"] for x in tani(ad, veri)}


def test_taninmayan_dosya_hicbir_yere_gitmez():
    import pandas as pd
    from io import BytesIO
    b = BytesIO()
    pd.DataFrame({"Ad": ["a"], "Soyad": ["b"], "Not": ["c"]}).to_excel(b, index=False)
    assert tani("liste.xlsx", b.getvalue()) == []
    r = tani("bozuk.xlsx", b"PK\x03\x04 bu bir excel degil")
    assert r[0]["tur"] is None and "açılamadı" in r[0]["gerekce"]


def test_iki_kesin_adayda_secim_kullaniciya_kalir():
    import pandas as pd
    from io import BytesIO
    b = BytesIO()
    pd.DataFrame({"FİRMA": ["X"], "DÖNEM": ["2026-09"], "TUTAR": [5], "REF NO": ["R1"]}).to_excel(b, index=False)
    assert {x["tur"] for x in tani("karma.xlsx", b.getvalue())} == {"ref_excel", "alinan_destek"}


# ── Tanıma, okuyucularla aynı fikirde ──────────────────────────────
def test_konumsal_ve_aktif_okuyucular_ornekleri_okur():
    from kayranacc.excel_islemler import excel_yukle_odeme_listesi, excel_yukle_cek_listesi
    from kayranacc.aktif_excel import parse_cari, parse_ithalat, parse_stok, parse_stok_excel
    hafta, odemeler, _ = excel_yukle_odeme_listesi(ORNEKLER["odeme_listesi"]()[1])
    assert hafta.startswith("41. Hafta") and len(odemeler) == 2
    tl, usd, _ = excel_yukle_cek_listesi(ORNEKLER["cek_listesi"]()[1])
    assert len(tl) == 1 and len(usd) == 1
    assert parse_ithalat(ORNEKLER["aktif_ithalat"]()[1])[0] == 70000
    c, _ = parse_cari(ORNEKLER["aktif_cari"]()[1])
    assert c["alacak"]["tl"] == 1250000 and c["borc"]["usd"] == 48000
    (usd_stok, pazar), _ = parse_stok(ORNEKLER["aktif_stok"]()[1], parse_stok_excel)
    assert usd_stok == 4300 and pazar == {"VATAN": 990}


# ── Kapı yapısı ────────────────────────────────────────────────────
def _py_dosyalar():
    for p in KOK.rglob("*.py"):
        r = p.relative_to(KOK).as_posix()
        if r.startswith(("tests/", ".venv", "venv/", "deploy/")) or "/." in r:
            continue
        yield r, p


def test_yukleme_kutusu_yalniz_kapida():
    """Programın Excel yüklemeleri tek yerde: kapı dışında st.file_uploader yok (barkod: kamera;
    şirket belgeleri: veri değil, PDF/görsel arşivi)."""
    bulunan = []
    for r, p in _py_dosyalar():
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Attribute) and n.attr == "file_uploader":
                bulunan.append(r)
    assert set(bulunan) <= {"shared/dosya_kapisi.py", "shared/barkod.py",
                            "shared/sirket_belge_ekran.py"}, bulunan


def _fonksiyon_dugumu(yol):
    mod, ad = yol.split(":")
    p = KOK / (mod.replace(".", "/") + ".py")
    t = ast.parse(p.read_text(encoding="utf-8"))
    return next((n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == ad), None)


def test_govdeler_modul_duzeyinde_ve_pencere_degil():
    """Pencere içinde pencere açılamaz (Streamlit): gövdeler @st.dialog OLMAYAN modül düzeyi fonksiyon."""
    from shared.dosya_kapisi import TURLER, SABLONLAR
    for tur, t in TURLER.items():
        f = _fonksiyon_dugumu(t["govde"])
        assert f is not None, (tur, t["govde"])
        assert [a.arg for a in f.args.args] == ["dosya", "kapi"], tur
        assert not any("dialog" in ast.dump(d) for d in f.decorator_list), tur
        assert "Name(id='kapi'" in ast.dump(f), tur          # kayıt sonucu kapıda (kapi.bitti ya da aktarır)
        mod = KOK / (t["govde"].split(":")[0].replace(".", "/") + ".py")
        kod = ast.get_source_segment(mod.read_text(encoding="utf-8"), f)
        # st.rerun() kapıyı kapatır ve sonuç / başarı mesajı kaybolur: kayıt sonu kapi.bitti(...)
        assert "st.rerun(" not in kod and "st.balloons(" not in kod, tur
    for _ad, _mod, yol in SABLONLAR:
        assert _fonksiyon_dugumu(yol) is not None, yol


def test_eski_yukleme_pencereleri_kalkti():
    eski = {"satis/main.py": ["def _dlg_xl_vatan", "def _dlg_toplu_iade", 'elif _ssayfa == "📥 İçe Aktar"'],
            "kayranacc/main.py": ['elif sayfa == "📂 Veri Yükleme"', "def _dlg_aktif_excel", "def _yukle_bloku"],
            "kayranpm/main.py": ["def _dlg_musteri_yukle", 'key="g5f_depo_dosya"'],
            "kayranpm/ref_ekran.py": ["def _ad_excel_dialog"], "kayranpm/ref_no.py": ["def _dlg_ref_ice_aktar"],
            "kayranpm/kampanya.py": ["def _excel_dialog"], "yonetim.py": ["def _gider_yukle_dialog"],
            "ithalat/main.py": ["def _dlg_takip_ata", '"📑 Excel ile Toplu"'],
            "depo/main.py": ['"📥 Günlük Excel Yükle (G5F_Stok)"'], "teknikservis/main.py": ['key="tmk_yukle"']}
    for d, isaretler in eski.items():
        src = (KOK / d).read_text(encoding="utf-8")
        for i in isaretler:
            assert i not in src, (d, i)


def test_yetki_kurallari():
    from shared.dosya_kapisi import izinli
    tam = {"satis": True, "kayranacc": True, "kayranpm": True, "yonetim": True, "kar": True,
           "toplam_aktifler": True}
    assert izinli("aktif_cari", tam) and not izinli("aktif_cari", dict(tam, toplam_aktifler=False))
    assert izinli("odeme_listesi", dict(tam, toplam_aktifler=False))
    assert izinli("gider_tablosu", tam) and not izinli("gider_tablosu", dict(tam, kar=False))
    # Muhasebe elemanı: yönetim/kâr yetkisi yok, yalnız 'gider_girisi' özel yetkisi var → gider tablosunu yükler
    assert izinli("gider_tablosu", {"kayranacc": True, "gider_girisi": True})
    assert not izinli("gider_tablosu", {"kayranacc": True, "yonetim": True})
    assert not izinli("siparis_vatan", dict(tam, satis=False)) and not izinli("ithalat_rapor", tam)


def test_uygulama_baglantilari():
    a = (KOK / "app.py").read_text(encoding="utf-8")
    assert "_dosya_dugmesi(ak, yet)" in a and "ana_sayfa_alani(" in a
    # Bir çalışmada tek pencere: kapı açıkken Talep Merkezi açılmaz
    assert a.index("_kapi_acik = _dk.ciz(") < a.index("    if not _kapi_acik:\n        try:\n            _talep_merkezi()")
    from shared.gezinme import palet_ogeleri
    o = palet_ogeleri({"satis": True}, set(), "x", lambda *a: True)
    assert any(x["id"] == "kapi" for x in o)
    assert not any(x["id"] == "kapi" for x in palet_ogeleri({}, set(), "x", lambda *a: True))


def test_kampanya_urun_hatasi_yutulmaz():
    from kayranpm.kampanya import urunleri_ekle
    satir = [{"sku": s, "urun_adi": s, "pacal": 1, "satis": 2, "fd": 0, "ed": 0} for s in ("A", "B", "C")]

    def ekle(kid, sku, *a):
        if sku == "B":
            raise RuntimeError("kolon yok")
    n, hatalar = urunleri_ekle(7, satir, ekle=ekle)
    assert n == 2 and hatalar == [{"SKU": "B", "Hata": "RuntimeError: kolon yok"}]


def test_xls_adli_xlsx_icerik_de_taninir():
    """Bazı programlar .xlsx içeriği .xls adıyla verir; okuyucular içeriğe bakar, tanıma da bakmalı
    (eskiden ada bakıp .xls okuyucusunu zorluyordu: "Excel olarak açılamadı")."""
    ad, veri = ORNEKLER["mikro_fatura"]()
    assert [(x["tur"], x["guven"]) for x in tani("FaturaDokum.xls", veri)] == [("mikro_fatura", KESIN)]


def test_gider_okuyucusu_xls_adli_xlsx_okur():
    import io
    from yonetim import gider_tablosu_parse
    f = io.BytesIO(ORNEKLER["gider_tablosu"]()[1])
    f.name = "gider_2026.xls"
    kat, detay = gider_tablosu_parse(f)
    assert len(detay) == 2 and sum(sum(v) for v in kat.values()) == 1500000

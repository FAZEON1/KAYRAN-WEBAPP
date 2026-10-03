# -*- coding: utf-8 -*-
"""Stok değiştiren yüklemeler — işaretleme ve hata düzeltmeleri (Ekim 2026, geri alma hazırlığı).

- Her stok hareketi, içinde yapıldığı yüklemenin koduyla işaretlenir (stok_defteri.yukleme);
  yükleme geçmişi kaydı da aynı kodu taşır. Sonraki adım (geri alma) bu kodla çalışır.
- İthalat Excel'i "güncelle" modunda mevcut durumu / teslim deposunu / tahmini varışı / fatura
  indirimini boşa yazıyordu.
- Excel "üzerine yaz" satış silmesi çöp kutusuna düşüyordu (oradan geri alınan satış stoğa
  yeniden işlenmiyordu).
- G5F sayımında defter tamponu elle açılıp kapatılıyordu; döngüde hata çıkarsa açık kalıyordu.
"""
from pathlib import Path

import shared.stok_defteri as SD
import shared.yukleme_gecmisi as Y

KOK = Path(__file__).resolve().parent.parent


def _yakala(monkeypatch):
    giden = []
    monkeypatch.setattr(SD, "_gonder", lambda satirlar: giden.extend(satirlar))
    return giden


def test_yukleme_baglamindaki_hareket_isaretlenir(monkeypatch):
    giden = _yakala(monkeypatch)
    SD.yaz("A", "MERKEZ DEPO", 5, 4, "cikis")
    with SD.yukleme("k1"):
        SD.yaz("A", "MERKEZ DEPO", 4, 3, "cikis")
        with SD.yukleme("k2"):
            SD.yaz("B", "MERKEZ DEPO", 1, 0, "cikis")
        SD.yaz("C", "MERKEZ DEPO", 1, 0, "cikis")
    SD.yaz("D", "MERKEZ DEPO", 1, 0, "cikis")
    assert [r.get("yukleme_kodu") for r in giden] == [None, "k1", "k2", "k1", None]


def test_toplu_tamponda_da_isaret_kalir(monkeypatch):
    giden = _yakala(monkeypatch)
    with SD.toplu(), SD.yukleme("k9"):
        SD.yaz_fark("A", {"MERKEZ DEPO": 3}, {"MERKEZ DEPO": 7}, "aktarim")
    assert giden and giden[0]["yukleme_kodu"] == "k9" and giden[0]["degisim"] == 4


def test_sutun_yoksa_isaretsiz_yazilir(monkeypatch):
    yazilan = []

    class _T:
        def insert(self, rows):
            self.rows = rows
            return self

        def execute(self):
            if any("yukleme_kodu" in r for r in self.rows):
                raise RuntimeError('column "yukleme_kodu" of relation "stok_hareketleri" does not exist')
            yazilan.extend(self.rows)

    import shared.auth as A
    monkeypatch.setattr(A, "_get_supabase", lambda: type("C", (), {"table": lambda s, t: _T()})())
    with SD.yukleme("k1"):
        SD.yaz("A", "MERKEZ DEPO", 1, 0, "cikis")
    assert len(yazilan) == 1 and "yukleme_kodu" not in yazilan[0]


def test_kayit_kodu_gecmise_ve_stoga_ayni(monkeypatch):
    giden = _yakala(monkeypatch)
    out = []
    monkeypatch.setattr(Y, "kaydet", lambda *a, **k: out.append(k) or 1)
    k = Y.Kayit("siparis_excel", "s.xlsx")
    with k.stok():
        SD.yaz("A", "MERKEZ DEPO", 2, 1, "cikis")
    k.kaydet(1)
    assert len(k.kod) == 32 and giden[0]["yukleme_kodu"] == k.kod and out[0]["kod"] == k.kod


def test_gecmis_kod_sutunu_yoksa_onsuz_yazilir(monkeypatch):
    yazilan = []

    class _T:
        def insert(self, satir):
            self.satir = satir
            return self

        def execute(self):
            if "kod" in self.satir:
                raise RuntimeError('column "kod" of relation "yuklemeler" does not exist')
            yazilan.append(self.satir)
            return type("R", (), {"data": [{"id": 5}]})()

    monkeypatch.setattr(Y, "_ham", lambda: type("C", (), {"table": lambda s, t: _T()})())
    assert Y.kaydet("g5f_sayim", 0, "g.xlsx", kod="abc") == 5
    assert "kod" not in yazilan[0]


def test_stok_degistiren_bes_yol_isaretli():
    yerler = {"satis/main.py": ('"siparis_excel"', '"mikro_fatura"', '"iade_excel"'),
              "kayranpm/main.py": ('"g5f_sayim"',), "teknikservis/main.py": ('"toplu_mal_kabul"',)}
    for dosya, turler in yerler.items():
        src = (KOK / dosya).read_text(encoding="utf-8")
        for t in turler:
            i = src.index(f"_YKayit({t}")
            assert ".stok()" in src[i:i + 900], (dosya, t)


def test_ithalat_guncelle_mevcut_durumu_korur():
    src = (KOK / "ithalat" / "main.py").read_text(encoding="utf-8")
    i = src.index("ok, msg = guncelle_dosya(")
    i = src.index("ok, msg = guncelle_dosya(", i + 1) if "mevcut_kayit[\"id\"]" not in src[i:i + 200] else i
    cagri = src[i:i + 1200]
    for alan in ("durum=", "teslim_deposu=", "tahmini_varis=", "fatura_indirim="):
        assert alan in cagri and "mevcut_kayit.get" in cagri.split(alan, 1)[1][:80], alan


def test_uzerine_yaz_silmesi_cop_kutusuna_dusmez():
    src = (KOK / "satis" / "database.py").read_text(encoding="utf-8")
    g = src[src.index("def sil_siparisler("):src.index("def ice_aktar_onizle(")]
    i = g.index('table("satislar").delete()')
    assert "with cop_kutusu_kapali():" in g[i - 120:i]


def test_g5f_defter_tamponu_with_ile():
    src = (KOK / "kayranpm" / "excel_islemler.py").read_text(encoding="utf-8")
    g = src[src.index("def excel_yukle_g5f_depolar("):src.index("def excel_yukle_haftalik_stok_satis(")]
    assert "with _sd.toplu():" in g and "__enter__" not in g and "__exit__" not in g

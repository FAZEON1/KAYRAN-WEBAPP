# -*- coding: utf-8 -*-
"""Fatura ile iade (Ekim 2026, kullanıcı kararı): iade faturası Yeni Mal Kabül penceresinde satış girişi
gibi kalem kalem girilir. Her modelin birim fiyatı ayrıdır; ürün listesi stok kartlarımızdan gelir,
yanında bu firmaya son satış fiyatı önerilir. Her adet için servis kaydı + stok + Satış › İade satırı."""
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


SATISLAR = [
    {"id": 1, "tarih": "2026-05-01", "kanal": "VATAN BİLGİSAYAR SAN. A.Ş.", "sku": "X24F165S", "birim_satis": 50},
    {"id": 2, "tarih": "2026-08-01", "kanal": "VATAN BİLGİSAYAR SAN. A.Ş.", "sku": "Fazeon X24F165S", "birim_satis": 52},
    {"id": 3, "tarih": "2026-09-01", "kanal": "İTOPYA", "sku": "X24F165S", "birim_satis": 55},
    {"id": 4, "tarih": "2026-09-05", "kanal": "VATAN", "sku": "X24F165S", "birim_satis": 0},     # bedelsiz sayılmaz
    {"id": 5, "tarih": "2026-07-01", "kanal": "İTOPYA", "sku": "K100", "birim_satis": 12.5},
]


def test_firma_koku_turkce_ve_unvan():
    from teknikservis.iade_fatura import firma_koku
    assert firma_koku("VATAN BİLGİSAYAR SAN. A.Ş.") == firma_koku("Vatan") == "VATAN"
    assert firma_koku("İtopya") == firma_koku("ITOPYA ELEKTRONİK") == "ITOPYA"
    assert firma_koku("") == ""


def test_son_fiyat_haritasi_firmaya_ozel_once():
    from teknikservis.iade_fatura import son_fiyat_haritasi
    from shared.utils import sku_anahtar
    h = son_fiyat_haritasi(SATISLAR, "Vatan")
    # VATAN'a son satış 52 (SKU yazımı farklı ama aynı ürün); 0'lı bedelsiz satış yok sayılır
    assert h[sku_anahtar("X24F165S")] == {"fiyat": 52.0, "tarih": "2026-08-01", "firma_mi": True}
    # VATAN'a hiç satılmamış ürün: başka firmaya son satış
    assert h[sku_anahtar("K100")] == {"fiyat": 12.5, "tarih": "2026-07-01", "firma_mi": False}
    assert son_fiyat_haritasi(SATISLAR, "")[sku_anahtar("X24F165S")]["fiyat"] == 55.0   # firma yoksa en son


def test_fiyat_onerisi_sirasi():
    from teknikservis.iade_fatura import son_fiyat_haritasi, fiyat_onerisi
    h = son_fiyat_haritasi(SATISLAR, "VATAN")
    assert fiyat_onerisi("X24F165S", "VATAN", h) == (52.0, "bu firmaya son satış 01.08.2026")
    assert fiyat_onerisi("K100", "VATAN", h) == (12.5, "son satış (başka firma) 01.07.2026")
    kart = {"satis_fiyati": 30, "satis_fiyat_listesi": {"VATAN BİLGİSAYAR": 28, "İTOPYA": 29}}
    assert fiyat_onerisi("YENI", "Vatan", h, kart) == (28.0, "ürün kartında bu firmanın fiyatı")
    assert fiyat_onerisi("YENI", "AYKON", h, kart) == (30.0, "ürün kartı satış fiyatı")
    assert fiyat_onerisi("YENI", "AYKON", h, {}) == (0.0, "fiyat önerisi yok")


def test_para_cevir():
    from teknikservis.iade_fatura import para_cevir
    assert para_cevir(52, "USD", None) == 52.0
    assert para_cevir(52, "TL", 42.5) == 2210.0
    assert para_cevir(52, "TL", None) == 0.0


def test_kalem_ekle_ayni_sku_ayni_fiyat_birlesir():
    from teknikservis.iade_fatura import kalem_ekle
    k = kalem_ekle([], "X24F165S", "Monitör", 2, 52)
    k = kalem_ekle(k, "Fazeon X24F165S", "Monitör", 1, 52)        # aynı ürün, aynı fiyat → adet artar
    k = kalem_ekle(k, "X24F165S", "Monitör", 1, 48)               # farklı fiyat → ayrı kalem
    k = kalem_ekle(k, "K100", "Klavye", 0, 10)                    # 0 adet eklenmez
    assert [(x["sku"], x["adet"], x["fiyat"]) for x in k] == [("X24F165S", 3, 52.0), ("X24F165S", 1, 48.0)]


def test_sepet_toplam():
    from teknikservis.iade_fatura import sepet_toplam
    k = [{"sku": "A", "adet": 3, "fiyat": 52}, {"sku": "B", "adet": 2, "fiyat": 12.25}]
    assert sepet_toplam(k) == {"adet": 5, "toplam": 180.5, "usd": 180.5}
    assert sepet_toplam(k, "TL", 40) == {"adet": 5, "toplam": 180.5, "usd": 4.5125}
    assert sepet_toplam(k, "TL", None)["usd"] is None
    assert sepet_toplam([]) == {"adet": 0, "toplam": 0, "usd": 0.0}


def test_fatura_daha_once():
    from teknikservis.iade_fatura import fatura_daha_once
    kayitlar = [{"fatura_no": "IAD2026001", "firma_bilgisi": "VATAN BİLGİSAYAR"},
                {"fatura_no": "iad2026001 ", "firma_bilgisi": "Vatan"},
                {"fatura_no": "IAD2026001", "firma_bilgisi": "İTOPYA"}]
    assert fatura_daha_once(kayitlar, "IAD2026001", "VATAN") == 2
    assert fatura_daha_once(kayitlar, "IAD2026002", "VATAN") == 0
    assert fatura_daha_once(kayitlar, "", "VATAN") == 0


def test_birim_kayitlari_her_adet_bir_kayit():
    from teknikservis.iade_fatura import birim_kayitlari, SERISIZ
    kalemler = [{"sku": "X24F165S", "ad": "Monitör", "adet": 3, "fiyat": 52},
                {"sku": "K100", "ad": "Klavye", "adet": 1, "fiyat": 12.5}]
    b = {"firma": "VATAN", "fatura_no": "IAD1", "irsaliye_no": "IRS9", "giris_depo": "MERKEZ DEPO",
         "para_birimi": "USD", "aciklama": ""}
    r = birim_kayitlari(kalemler, b, gruplar={"X24F165S": "Monitör"})
    assert len(r) == 4 and all(x["seri_no"] == SERISIZ and x["arayuz"] == "iade" for x in r)
    assert [x["iade_net"] for x in r] == [52.0, 52.0, 52.0, 12.5]
    assert r[0]["urun_grubu"] == "Monitör" and r[3]["urun_grubu"] == ""
    assert r[0]["ariza"] == "Fatura ile iade" and r[0]["fatura_mevcut"] and r[0]["giris_depo"] == "MERKEZ DEPO"
    assert r[0]["iade_kur"] is None and r[0]["iade_pb"] == "USD"
    r[0]["iade_id"] = 5
    assert "iade_id" not in r[1]                                    # birimler birbirinin kopyası değil
    t = birim_kayitlari(kalemler[:1], dict(b, para_birimi="TL"), kur=40)
    assert t[0]["iade_fiyat"] == 52.0 and t[0]["iade_net"] == 1.3 and t[0]["iade_kur"] == 40
    with pytest.raises(ValueError):
        birim_kayitlari(kalemler[:1], dict(b, para_birimi="TL"), kur=None)


def test_birim_kaydi_stok_ve_iade_satiri(monkeypatch):
    """Üretilen birim kaydı mevcut yazıcılarla çalışır: seçilen depoya +1, iade satırı birim fiyatla."""
    from teknikservis import stok as S, iade_fatura as IF
    import satis.database as D
    hareket, iade = [], []
    monkeypatch.setattr(S, "_uygula", lambda sku, ad, depo, d: (hareket.append((sku, depo, d)), (True, "ok"))[1])
    monkeypatch.setattr(D, "ekle_iade", lambda *a, **k: (iade.append((a, k)), (True, "ok", 41))[1])
    v = IF.birim_kayitlari([{"sku": "X24F165S", "ad": "Monitör", "adet": 1, "fiyat": 52}],
                           {"firma": "VATAN", "fatura_no": "IAD1", "giris_depo": "HAPPY LIFE"})[0]
    assert S.mal_kabul_girisi(v)[0] and S.iade_kaydi_yaz(v)[0]
    assert hareket == [("X24F165S", "HAPPY LIFE", 1)]
    (a, k), = iade
    assert a[1] == "VATAN" and a[2] == "X24F165S" and a[4] == 1
    assert k["iade_net"] == 52.0 and k["depo"] == "HAPPY LIFE" and k["stok_isle"] is False
    assert v["iade_id"] == 41


# ── Ekran ──────────────────────────────────────────────────────────────
def test_ekran_mal_kabul_yalniz_teknik_servis():
    # Kullanıcı (22.10.2026): "Mal kabulde iade seçeneğini tamamen kaldıralım" — iade Mikro'daki faturadan gelir
    m = _oku("teknikservis/main.py")
    d = m[m.index("def _mal_kabul_dialog("):m.index("# ── Liste (Teknik Servis / İade)")]
    assert '"↩️ İade"' not in d and "_fatura_iade_formu" not in m and 'arayuz = "teknik"' in d
    assert 'key="mk_iade_net"' not in m and 'key="mk_iade_pb"' not in m

# -*- coding: utf-8 -*-
"""Hızlandırma (Ekim 2026): program ABD'de, veritabanı Frankfurt'ta; her istek ~0,2-0,3 sn.

Ölçüm (son 24 saat, canlı API kayıtları): satış tablosu 1.624 istek / 550 sn bekleme; Yönetim özeti
dönem başına ayrı sorgular; ayarlar anahtar anahtar. Düzeltmeler:
  1. Satış / iade / kur: tablo bir kez okunur, tarih aralıkları bellekte süzülür.
  2. Satış önbelleği veri değişince tazelenir (veri_surumu satış grubu, SQL 22), 2 dk'da bir değil.
  3. Ayarlar tek istekte.
  4. Bağımsız okumalar aynı anda (shared/paralel).
  5. Sayfalı okumada fazla istek kırpıldı.
Rakam / hesap değişmez: süzme sonucu veritabanının gte/lte süzgeciyle aynı satırlardır.
"""
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


class _Sorgu:
    """Kaydeden sahte sorgu: hangi süzgeçlerle sorgu atıldığını tutar."""
    def __init__(self, kayit, tablo, satirlar):
        self.kayit, self.tablo, self.satirlar, self.suz = kayit, tablo, satirlar, []

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def gte(self, s, v):
        self.suz.append(("gte", s, v))
        return self

    def lte(self, s, v):
        self.suz.append(("lte", s, v))
        return self

    def eq(self, s, v):
        self.suz.append(("eq", s, v))
        return self

    def execute(self):
        self.kayit.append((self.tablo, tuple(self.suz)))

        class R:
            pass
        r = R()
        r.data = [dict(x) for x in self.satirlar]
        return r


class _Istemci:
    def __init__(self, tablolar):
        self.tablolar, self.kayit = tablolar, []

    def table(self, ad):
        return _Sorgu(self.kayit, ad, self.tablolar.get(ad, []))


SAT = [{"id": 3, "tarih": "2026-09-30", "kanal": "A", "sku": "X", "adet": 1},
       {"id": 2, "tarih": "2026-09-01", "kanal": "B", "sku": "Y", "adet": 2},
       {"id": 1, "tarih": "2026-08-31", "kanal": "A", "sku": "X", "adet": 3}]


# ── 1. Tarih aralıkları tek tam okumadan süzülür ─────────────────────
def test_satis_araligi_veritabanina_suzgecli_sorgu_atmaz(monkeypatch):
    import satis.database as D
    ist = _Istemci({"satislar": SAT})
    monkeypatch.setattr(D, "_get_client", lambda: ist)
    eylul = D.get_satislar_yalin("2026-09-01", "2026-09-30")
    assert [r["id"] for r in eylul] == [3, 2]                      # sınırlar dahil (gte / lte ile aynı)
    assert [r["id"] for r in D.get_satislar_yalin(None, "2026-08-31")] == [1]
    assert [r["id"] for r in D.get_satislar_yalin()] == [3, 2, 1]
    assert all(t == "satislar" and not suz for t, suz in ist.kayit), ist.kayit


def test_iade_araligi_tek_tam_okumadan(monkeypatch):
    import satis.database as D
    ist = _Istemci({"iadeler": SAT})
    monkeypatch.setattr(D, "_get_client", lambda: ist)
    assert [r["id"] for r in D.get_iadeler("2026-09-01", "2026-09-30")] == [3, 2]
    assert all(not suz for _t, suz in ist.kayit), ist.kayit


def test_kur_araligi_tek_tam_okumadan(monkeypatch):
    import kayranacc.database as K
    ist = _Istemci({"kur_gunluk": [{"tarih": "2026-09-01", "usd_try": 41.0},
                                   {"tarih": "2026-10-01", "usd_try": 41.5}]})
    monkeypatch.setattr(K, "get_client", lambda: ist)
    assert K.get_kur_araligi("2026-09-01", "2026-09-30") == {"2026-09-01": 41.0}
    assert all(not suz for _t, suz in ist.kayit), ist.kayit


def test_ayarlar_tek_istekte(monkeypatch):
    import kayranacc.database as K
    ist = _Istemci({"sistem_ayarlari": [{"anahtar": "a", "deger": '{"x": 1}'},
                                        {"anahtar": "b", "deger": "[1, 2]"}]})
    monkeypatch.setattr(K, "get_client", lambda: ist)
    assert K.get_ayar("a") == {"x": 1} and K.get_ayar("b") == [1, 2] and K.get_ayar("yok", 7) == 7
    assert all(not suz for _t, suz in ist.kayit), ist.kayit         # anahtar süzgeci yok: tümü bir kez


def test_tam_okuma_hatasi_bos_liste_doner_ve_onbellege_yazilmaz(monkeypatch):
    import satis.database as D

    def patla():
        raise RuntimeError("ağ")
    monkeypatch.setattr(D, "_tum_satislar_yalin", patla)
    assert D.get_satislar_yalin("2026-09-01", "2026-09-30") == []
    src = (KOK / "satis" / "database.py").read_text(encoding="utf-8")
    govde = src[src.index("def _tum_satislar_yalin("):src.index("def _satislar_yalin_aralik(")]
    assert "except" not in govde                                     # hata yukarı: boş sonuç önbelleğe girmez


def test_tam_satis_okumalari_ortak_kaynakta():
    """Tam tabloyu ayrıca indiren eski çağrılar ortak okumaya bağlandı."""
    for yol in ("kayranpm/stok_yasi.py", "kayranpm/stok_karti.py", "depo/main.py", "shared/veri_sagligi.py"):
        s = (KOK / yol).read_text(encoding="utf-8")
        assert "get_satislar()" not in s, yol
    db = (KOK / "satis" / "database.py").read_text(encoding="utf-8")
    kn = db[db.index("def _kanallar_satistan("):db.index("@st.cache_resource")]
    assert "_tum_satislar_yalin()" in kn and 'select("kanal")' not in kn


# ── 2. Satış önbelleği veri değişince tazelenir ──────────────────────
@pytest.fixture
def surum(monkeypatch):
    import shared.veri_surumu as V
    durum = {"surum": None, "temizlik": 1000.0}
    temiz = []
    sayac = {"v": {"urunler": 1, "satislar": 5, "iadeler": 1}}
    monkeypatch.setattr(V, "_surec_durumu", lambda: durum)
    monkeypatch.setattr(V, "_surumler", lambda: sayac["v"])
    monkeypatch.setattr(V, "bagimlilari_temizle", lambda liste=None: temiz.append(liste) or 0)
    return V, durum, temiz, sayac


def test_satis_degisince_yalniz_satis_onbellegi_temizlenir(surum):
    V, durum, temiz, sayac = surum
    V.tazelik_kontrol(simdi=1001)
    assert temiz == []
    sayac["v"] = {"urunler": 1, "satislar": 6, "iadeler": 1}           # bir satış girildi
    assert V.tazelik_kontrol(simdi=1002) == "ayni"                      # ürün önbellekleri yerinde
    assert temiz == [V.SATIS_BAGIMLILAR]


def test_satis_sayaci_yoksa_eski_iki_dakika(surum):
    V, durum, temiz, sayac = surum
    sayac["v"] = {"urunler": 1}                                         # SQL 22 kurulmamış
    V.tazelik_kontrol(simdi=1001)
    V.tazelik_kontrol(simdi=1001 + V.SATIS_YEDEK_SN - 1)
    assert temiz == []
    V.tazelik_kontrol(simdi=1001 + V.SATIS_YEDEK_SN)
    assert temiz == [V.SATIS_BAGIMLILAR]


def test_satis_bagimlilari_gercek_ve_sql_ayni_tablolar():
    import importlib
    import shared.veri_surumu as V
    assert not [f"{m}.{a}" for m, a in V.SATIS_BAGIMLILAR if not hasattr(importlib.import_module(m), a)]
    sql = (KOK / "veritabani" / "22_satis_surumu.sql").read_text(encoding="utf-8")
    dizi = re.search(r"FOREACH t IN ARRAY ARRAY\[([^\]]+)\]", sql).group(1)
    assert tuple(re.findall(r"'(\w+)'", dizi)) == V.SATIS_TABLOLARI


# ── 4. Aynı anda okuma ───────────────────────────────────────────────
def test_paralel_sira_korunur_hata_yutulur():
    import time
    from shared.paralel import hepsi

    def yavas(x):
        time.sleep(0.05)
        return x * 2

    def patla():
        raise ValueError("x")
    t = time.time()
    assert hepsi([(yavas, 1), (yavas, 2), patla, (yavas, 3)]) == [2, 4, None, 6]
    assert time.time() - t < 0.15                                        # sırayla olsa ≥ 0,15 sn


def test_yonetim_once_ortak_okumalari_isitir():
    y = (KOK / "yonetim.py").read_text(encoding="utf-8")
    g = y[y.index("def _on_isit("):y.index("def _trend(")]
    assert g.index("hepsi([_tum_satislar_yalin") < g.index("basla(isler)")   # 12 iş aynı tabloyu 12 kez indirmesin
    assert "(_pnl_onbellekli, ky, kd, kb, kt, tuple(ka), kur)" in g          # _ozet'teki çağrıyla aynı anahtar
    assert "(_ay_ozeti, y, i, kur)" in g
    assert "_kiyas_bekle = _on_isit(" in y


# ── 5. Sayfalı okuma ─────────────────────────────────────────────────
def test_sayfalama_kucuk_tabloda_fazla_istek_atmaz():
    from shared.audit import wrap_client
    satir = [{"id": i} for i in range(1797)]
    istek = []

    class B:
        def __init__(self, aralik=None):
            self.aralik = aralik

        def select(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def range(self, a, b):
            return B((a, b))

        def execute(self, *a, **k):
            istek.append(self.aralik)
            a, b = self.aralik or (0, 999)

            class R:
                pass
            r = R()
            r.data = satir[a:b + 1]
            return r

    class C:
        def table(self, ad):
            return B()

    r = wrap_client(C(), "test").table("firma_stok").select("*").execute()
    assert len(r.data) == 1797
    assert len(istek) == 3, istek                                          # eskiden 1 + 8 = 9

# -*- coding: utf-8 -*-
"""Yönetim Panosu yenileme (Ekim 2026).

  1. Yedek ham bağlantıyla okuyordu (sayfalama sarmalayıcıda) → 1000 satırı aşan
     tablolar sessizce kesiliyordu.
  2. Yedek listesi eskimişti: iadeler, tahsilatlar, alinan_destekler, ref_no,
     e-Defter tabloları, stok_hareketleri, kullanici_yetkileri… hiç yedeklenmiyordu.
  3. Pano ile Ay Kapanış Raporu aynı ay için farklı net kâr verebiliyordu (rapor
     alınan desteği eklemiyordu, kur kuralı farklıydı) → tek hesap: pnl_topla.
  4. Okunamayan bileşen (iade, gider, destek, alınan destek) ya da girilmemiş gider
     ayı sessizce 0 sayılıyordu → eksikler listesi ekranda.
  5-10. Ay raporu tablolarında para sütununa metin, gider tablosunda metin sayılar
     + TOPLAM satırı, st.stop, kaybolan mesaj, ISO tarih, büyük harf, UTC tarih.
"""
import re
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


# ── Sahte veri kaynağı ──────────────────────────────────────────────
class _Kaynak:
    def __init__(self, **kw):
        self.d = {"satis": ({"ciro": 1000.0, "maliyet": 600.0}, {"VATAN": {"ciro": 1000.0}}, {}),
                  "iade": {"i_tutar": 100.0, "i_kar": 40.0},
                  "destek": [{"tutar": 50, "doviz": "USD", "tur": "Ref No", "donem": "2026-09-10"},
                             {"tutar": 3000, "doviz": "TL", "tur": "Ref No", "donem": "2026-09-12"}],
                  "gider": {"Sabit": [0.0] * 8 + [6000.0] + [0.0] * 3},
                  "alinan": 25.0, "kur": {"2026-09-12": 30.0, "2026-09-15": 30.0}, "yedek_kur": 40.0}
        self.d.update(kw)

    def _al(self, k):
        v = self.d[k]
        if isinstance(v, Exception):
            raise v
        return v

    def satis(self, bas, bit):
        return self._al("satis")

    def iade(self, bas, bit):
        return self._al("iade")

    def destekler(self, bas, bit):
        return self._al("destek")

    def gider_kat(self, yil):
        return self._al("gider")

    def alinan(self, bas, bit):
        return self._al("alinan")

    def kur_haritasi(self, bas, bit):
        return self._al("kur")

    def yedek_kur(self):
        return self._al("yedek_kur")


def _hesap():
    from yonetim_hesap import pnl_topla
    return pnl_topla


def test_pnl_formulu_alinan_destek_dahil():
    r = _hesap()(2026, "Eylül", "2026-09-01", "2026-09-30", _Kaynak(), bugun=date(2026, 10, 20))
    # ciro 1000-100=900 · cogs 600-(100-40)=540 · brüt 360
    assert r["ciro"] == 900 and r["cogs"] == 540 and r["brut"] == 360
    # destek 50 + 3000/30 = 150 · gider 6000/30 = 200 · alınan +25
    assert r["destek"] == 150 and r["gider"] == 200 and r["alinan"] == 25
    assert r["net_kar"] == 360 - 150 - 200 + 25
    assert r["eksikler"] == []


def test_pano_ve_rapor_ayni_hesabi_kullanir():
    y = _oku("yonetim.py")
    assert y.count("pnl_topla(") >= 2                                  # pano + ay raporu
    assert "net_kar = brut - toplam_destek - gider_usd" not in y
    assert 'r["net_kar"] = r["brut"] - r["destek"] - r["gider"]' not in y


def test_okunamayan_bilesen_eksiklerde():
    pt = _hesap()
    r = pt(2026, "Eylül", "2026-09-01", "2026-09-30", _Kaynak(iade=RuntimeError("x"), alinan=RuntimeError("y")),
           bugun=date(2026, 10, 20))
    metin = " ".join(r["eksikler"])
    assert "İade" in metin and "Alınan destek" in metin
    assert r["ciro"] == 1000                                           # iade düşülemedi, ama BİLİNİYOR


def test_girilmemis_gider_ayi_eksiklerde():
    pt = _hesap()
    # Q3: Temmuz ve Ağustos girilmemiş, Eylül var
    r = pt(2026, "Q3", "2026-07-01", "2026-09-30", _Kaynak(), bugun=date(2026, 10, 20))
    assert any("Temmuz" in e and "Ağustos" in e for e in r["eksikler"]), r["eksikler"]
    # henüz gelmemiş aylar (Kasım, Aralık) ve içinde bulunulan ay eksik sayılmaz
    r = pt(2026, "Tüm Yıl", "2026-01-01", "2026-12-31", _Kaynak(), bugun=date(2026, 10, 20))
    g = next(e for e in r["eksikler"] if "gider" in e.lower())
    assert "Ekim" not in g and "Kasım" not in g and "Ocak" in g
    r = pt(2026, "Eylül", "2026-09-01", "2026-09-30", _Kaynak(gider={}), bugun=date(2026, 10, 20))
    assert any("gider tablosu" in e.lower() for e in r["eksikler"])


def test_kur_yoksa_tl_kalem_atlanir_ve_bildirilir():
    pt = _hesap()
    r = pt(2026, "Eylül", "2026-09-01", "2026-09-30", _Kaynak(kur={}, yedek_kur=0), bugun=date(2026, 10, 20))
    assert r["destek"] == 50 and r["gider"] == 0
    assert any("kur" in e.lower() for e in r["eksikler"])


def test_ay_raporu_ocakta_onceki_yilin_araligi():
    from yonetim_hesap import onceki_ay
    assert onceki_ay(date(2026, 1, 15)) == (2025, 11)                 # (yıl, ay_idx) → Aralık
    assert onceki_ay(date(2026, 10, 2)) == (2026, 8)                  # Eylül


# ── Yedek ───────────────────────────────────────────────────────────
def _kodda_kullanilan_tablolar():
    adlar = set()
    for f in KOK.rglob("*.py"):
        if "tests" in f.parts or ".git" in f.parts:
            continue
        s = f.read_text(encoding="utf-8", errors="ignore")
        # tek ve çift tırnak (prim_gecmis tek tırnakla yazıldığı için gözden kaçıyordu)
        adlar |= set(re.findall(r'table\(\s*["\']([a-z_0-9]+)["\']\s*\)', s))
        adlar |= set(re.findall(r'^\w*TABLO\s*=\s*["\']([a-z_0-9]+)["\']', s, re.M))
    return adlar


def test_yedek_listesi_kodla_uyumlu():
    import yonetim as Y
    eksik = _kodda_kullanilan_tablolar() - set(Y.YEDEK_TABLOLAR) - set(Y.YEDEK_HARIC)
    assert not eksik, f"yedeğe girmeyen tablo: {sorted(eksik)} — YEDEK_TABLOLAR ya da YEDEK_HARIC'e ekle"
    for t in ("iadeler", "tahsilatlar", "alinan_destekler", "ref_no", "edefter_fisler",
              "stok_hareketleri", "kullanici_yetkileri", "happylife_stok"):
        assert t in Y.YEDEK_TABLOLAR, t
    assert "kullanici_sifreler" in Y.YEDEK_HARIC and "kullanici_sifreler" not in Y.YEDEK_TABLOLAR


def test_yedek_sayfali_okur():
    import yonetim as Y

    class _Q:
        def __init__(self, rows):
            self.rows, self.r = rows, None

        def select(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def range(self, a, b):
            self.r = (a, b)
            return self

        def execute(self):
            a, b = self.r if self.r else (0, 999)
            b = min(b, a + 999)                                        # Supabase: en fazla 1000
            return type("R", (), {"data": self.rows[a:b + 1]})()

    class _SB:
        def table(self, t):
            return _Q([{"id": i} for i in range(2500)])

    assert len(Y._tum_satirlar(_SB(), "satislar")) == 2500
    g = _oku("yonetim.py")
    g = g[g.index("def _yedek_olustur("):]
    g = g[:g.index("\ndef ", 1)]
    assert "_tum_satirlar(" in g


# ── Ekran ───────────────────────────────────────────────────────────
def test_ekranda_eksikler_ve_tek_toplam_aktif():
    y = _oku("yonetim.py")
    assert "_veri_durumu(" in y                                        # eksik bileşen satırı
    assert y.count("Stok değeri (×1.20)") == 1                         # toplam aktifler tek fonksiyonda


def test_ay_raporu_tablolari_sayi():
    y = _oku("yonetim.py")
    for eski in ('"Ciro": _usd(k["ciro"])', '"Net Kâr": _usd(k["net_kar"])', '"Net Kâr": _usd(u["net_kar"])'):
        assert eski not in y, eski
    assert '_row[_a] = f"{tr_sayi(_vv[_idx])}"' not in y               # gider tablosu metin
    assert '{"Kategori": "TOPLAM"}' not in y


def test_genel_temizlik():
    y = _oku("yonetim.py")
    assert "st.stop()" not in y and "uppercase" not in y
    for et in ("DESTEK KIRILIMI", "KANAL BAZINDA SATIŞ", "İŞLETME GİDERLERİ", "💎 TOPLAM AKTİFLER",
               '"ALINAN DESTEK"', "TOPLAM ({_donem})"):
        assert et not in y, et
    # İstanbul saati: dt.date.today() yalnız _bugun()'un yedeği olarak kalır
    g = y[y.index("def _bugun():"):]
    g = g[:g.index("\ndef ", 1)]
    assert y.count("dt.date.today()") == 1 and "dt.date.today()" in g
    assert 'st.success(f"✅ {len(_detayp)} kalem' not in y             # rerun'dan önce kaybolurdu
    assert "📅 {baslangic} → {bitis}" not in y                          # ISO aralık


def test_ay_raporu_panoyla_ayni_kaynagi_kullanir():
    """Rapor kaynağı kursuz kuruyordu: pano oturum kurunu kullanırken rapor TL desteği
    atlıyordu (tarayıcıda: pano ≠ rapor). İkisi de oturum kurlu kaynakla çağrılmalı."""
    y = _oku("yonetim.py")
    g = y[y.index("def _ay_kapanis():"):]
    g = g[:g.index("\ndef ", 1)]
    assert "_PnlKaynak(_okur)" in g and g.count("kaynak=_kyn") == 2
    assert "_PnlKaynak(_oturum_kur)" in y

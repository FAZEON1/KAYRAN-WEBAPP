# -*- coding: utf-8 -*-
"""Depo modülü kalan sayfalar yenileme (Ekim 2026).

Tarayıcıda ESKİ kodda gösterilenler (Streamlit 1.64, örnek veri):
  1. Depolar Arası Sevk: iki kalem de sevk edilemedi (hedef = kaynak), ekranda hata
     YOKTU ve sevk listesi boşaltılmıştı — kullanıcı sevk yapıldı sanıyordu.
  3. Bekleyen Sevk: iki ayrı düşüm aynı fiş numarasını aldı (KYR-2026-00001);
     kutu hem key hem otomatik value alıyordu, value ikinci kez uygulanmıyordu.
  4. "🧮 TOPLAM" satırı azalan sıralamada listenin BAŞINA geçiyordu (ortak tablo
     yalnız "Σ" ile başlayan satırı alt bilgiye sabitler).
Ayrıca: onaysız kayıt silme, Happy Life yüklemesi yarıda düşünce günün stoğunun
eksik kalması, rerun'dan önce kaybolan mesajlar, ISO tarihler, her yenilemede
üretilen PDF/Excel, ürün eklerken tüm önbelleğin boşaltılması, büyük harf.
"""
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
MAIN = "depo/main.py"


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _govde(src, bas):
    g = src[src.index(bas):]
    i = g.find("\ndef ", 1)
    return g if i < 0 else g[:i]


# ── 1. Sevk sonucu: başarısızlar listede kalır ─────────────────────
def test_sevk_sonucu():
    from depo.depo_hesap import sevk_sonucu
    sepet = [{"sku": "A", "adet": 2}, {"sku": "B", "adet": 1}, {"sku": "C", "adet": 4}]
    r = sevk_sonucu(sepet, [(True, "ok"), (False, "❌ Yetersiz stok"), (True, "ok")])
    assert r["ok"] == 2 and r["ok_adet"] == 6
    assert [k["sku"] for k in r["kalan"]] == ["B"] and r["kalan"][0]["hata"] == "❌ Yetersiz stok"
    assert r["hatalar"] == [("B", "❌ Yetersiz stok")]


def test_sevk_sonrasi_liste_kosulsuz_bosaltilmiyor():
    g = _govde(_oku(MAIN), "def _sayfa_sevk(")
    b = g[g.index('key="dpo_sevk_hepsi"'):]
    b = b[:b.index("st.rerun()")]
    assert "sevk_sonucu(" in b and 'st.session_state["dpo_sepet"] = _r["kalan"]' in b
    assert 'st.session_state["dpo_sepet"] = []' not in b
    assert "st.success(" not in b and "st.error(\"Bazı kalemler" not in b      # rerun'dan önce kaybolurdu
    assert "_mesaj = st.container()" in g and '"_dpo_sonuc"' in g


def test_listeye_eklemek_onbellegi_bosaltmaz():
    g = _govde(_oku(MAIN), "def _sayfa_sevk(")
    for anahtar in ('key="dpo_ekle"', 'key=f"dpo_sil_{_i}"', 'key="dpo_temizle"'):
        b = g[g.index(anahtar):]
        b = b[:b.index("st.rerun()")]
        assert "st.cache_data.clear()" not in b, anahtar


# ── 2-3. Bekleyen Sevk ──────────────────────────────────────────────
def test_bekleyen_silme_onayli_ve_anahtar_kayda_bagli():
    e = _oku("depo/bekleyen_ekran.py")
    assert "B.onayli_sil(" in e and 'key=f"mt_sil_{kid}"' in e
    assert 'delete().eq("id"' not in _oku(MAIN)


def test_fis_no_kutusu_her_duşumde_yeni():
    from depo.depo_hesap import fis_anahtari
    assert fis_anahtari(7, []) != fis_anahtari(7, [{"adet": 1}])
    assert fis_anahtari(7, []) != fis_anahtari(8, [])
    e = _oku("depo/bekleyen_ekran.py")
    assert 'key="mt_d_fis"' not in e and "fis_anahtari(" in e


def test_bekleyen_ozet():
    from depo.depo_hesap import bekleyen_ozet
    assert bekleyen_ozet({"fatura_adet": 100, "sevk_edilen": 10}) == (100, 10, 90, 0.1)
    assert bekleyen_ozet({"fatura_adet": 0, "sevk_edilen": 0}) == (0, 0, 0, 0.0)
    assert bekleyen_ozet({"fatura_adet": 5, "sevk_edilen": 7})[2] == 0      # eksiye düşmez


def test_bekleyen_liste_ve_sayfa_ici_detay():
    e = _oku("depo/bekleyen_ekran.py")
    assert 'ON_EK = "dpo_mt"' in e
    for s in ("B.tiklanir(", "B.secili(ON_EK)", "B.listeye_don(ON_EK)", "B.geri_yukle(", "B.koru("):
        assert s in e, s
    assert "data=partial(" in e                                             # PDF/Excel tıklanınca
    assert "sevk_fisi_pdf(_mt_sec, _hrk[_hsec])" not in _oku(MAIN)


# ── 4. Σ toplam satırı ──────────────────────────────────────────────
def test_toplam_satiri_sigma():
    from depo.depo_hesap import toplam_satiri
    r = toplam_satiri(["Tarih", "Firma", "Adet"], {"Adet": 12}, ozet={"Firma": "3 kayıt"})
    assert r == {"Tarih": "Σ Toplam", "Firma": "3 kayıt", "Adet": 12}
    for y in (MAIN, "depo/bekleyen_ekran.py"):
        assert "🧮 TOPLAM" not in _oku(y), y


# ── 5. Happy Life güvenli yükleme ───────────────────────────────────
class _Y:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, sb, t):
        self.sb, self.t, self.op, self.v, self.f = sb, t, "select", None, []

    def select(self, *a, **k):
        return self

    def eq(self, a, v):
        self.f.append((a, v))
        return self

    def delete(self):
        self.op = "delete"
        return self

    def insert(self, v):
        self.op, self.v = "insert", v
        return self

    def execute(self):
        rows = self.sb.db.setdefault(self.t, [])
        uy = [r for r in rows if all(r.get(a) == v for a, v in self.f)]
        if self.op == "select":
            return _Y([dict(r) for r in uy])
        if self.op == "delete":
            self.sb.db[self.t] = [r for r in rows if r not in uy]
            return _Y(uy)
        self.sb.ins += 1
        if self.sb.ins in self.sb.dus:
            raise RuntimeError("bağlantı koptu")
        rows.extend(dict(r) for r in self.v)
        return _Y(self.v)


class _SB:
    def __init__(self, db, dus=()):
        self.db, self.dus, self.ins = db, set(dus), 0

    def table(self, t):
        return _Q(self, t)


def test_happylife_yukleme_yarida_duserse_eski_gun_geri_gelir(monkeypatch):
    import depo.main as M
    eski = [{"sku": f"E{i}", "rapor_tarihi": "2026-09-30"} for i in range(3)]
    sb = _SB({"happylife_stok": [dict(r) for r in eski]}, dus={2})     # 2. parça düşer
    monkeypatch.setattr(M, "get_client", lambda: sb)
    ok, msg = M.hl_kaydet([{"sku": f"Y{i}"} for i in range(250)], "2026-09-30")
    assert not ok and "geri" in msg
    kalan = sorted(r["sku"] for r in sb.db["happylife_stok"] if r["rapor_tarihi"] == "2026-09-30")
    assert kalan == ["E0", "E1", "E2"]


def test_happylife_yukleme_basarili(monkeypatch):
    import depo.main as M
    sb = _SB({"happylife_stok": [{"sku": "E", "rapor_tarihi": "2026-09-30"}]})
    monkeypatch.setattr(M, "get_client", lambda: sb)
    ok, _ = M.hl_kaydet([{"sku": f"Y{i}"} for i in range(250)], "2026-09-30")
    assert ok and len(sb.db["happylife_stok"]) == 250


# ── Genel ───────────────────────────────────────────────────────────
def test_tarih_tr_ve_iso_yok():
    m = _oku(MAIN)
    assert '"Tarih": (g.get("tarih") or "")[:16]' not in m
    assert '"Tarih": str(s.get("tarih") or "")[:10]' not in m
    assert 'st.selectbox("Rapor tarihi", _tarihler, index=0, key="hl_sec_tarih")' not in m
    assert "tarih_tr(" in m and "tarih_tr(" in _oku("depo/bekleyen_ekran.py")


def test_mesajlar_rerundan_once_kaybolmaz():
    m = _oku(MAIN) + _oku("depo/bekleyen_ekran.py")
    assert 'st.success("✅ Takip kaydı oluşturuldu.")' not in m
    assert 'st.success("Kayıt silindi.")' not in m
    hl = _govde(_oku(MAIN), "def _sayfa_happylife(")
    assert "(st.success if ok else st.error)(msg)" not in hl


def test_buyuk_harf_ve_eski_metinler_yok():
    for y in (MAIN, "depo/bekleyen_ekran.py", "depo/depo_hesap.py"):
        assert "uppercase" not in _oku(y), y
    m = _oku(MAIN)
    assert "özet kartlar" not in m                                   # Depo Stok'ta kart yok
    assert 'if k["_yas"] is not None else "—"' not in m               # sayı sütununda metin


# ── Ortak tablo: boş sayı hücresi "nan" yazmasın (app.py) ───────────
def test_ortak_tablo_bos_sayi_nan_yazmaz():
    """Happy Life 'Fark' sütununda 6 hücre "nan" yazıyordu (tarayıcıda, eski kodda da).
    Sayı sütununda where(..., None) NaN'ı None'a çevirmiyor (pandas 2.3 ve 3.0'da
    denendi); önce object'e çevirmek gerekiyor."""
    import pandas as pd
    df = pd.DataFrame([{"Fark": 260}, {"Fark": None}])
    assert df.astype(object).where(pd.notna(df), None).to_dict("records")[1]["Fark"] is None
    a = _oku("app.py")
    assert 'df.astype(object).where(_pd.notna(df), None).to_dict("records")' in a
    assert 'return df.where(_pd.notna(df), None).to_dict("records")' not in a

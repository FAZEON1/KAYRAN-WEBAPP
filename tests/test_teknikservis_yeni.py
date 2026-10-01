# -*- coding: utf-8 -*-
"""Teknik Servis modülü yenileme (Ekim 2026).

  1. SLA N+1: bitmiş her kayıt için ts_gecmis'e ayrı sorgu atılıyordu (liste
     başına kayıt sayısı × 3-4). Artık tek toplu sorgu + sözlük.
  2. sil_kayit: önce geçmiş, sonra kayıt siliniyordu; kayıt silme düşerse kayıt
     geçmişsiz kalıyordu. Artık geçmiş geri yazılır.
  3. İşlem geçmişi tarihi GG-AA-YYYY → GG.AA.YYYY (her yerle aynı).
  4. Büyük harf etiketler (CSS uppercase, "İŞLEM ÖZETİ") kaldırıldı.
  5. Evraksız Kayıt'ta st.stop() yerine return.
  6. Teknik Servis / İade listesi: kayıt seçme kutusu yerine tıklanır satır,
     SLA kademesine göre gruplu; detay sayfa içinde açılır (iç pencereler
     çalışmaya devam etsin diye pencere değil).
  7. Excel raporları yalnız indirirken üretilir (data=callable).
  8. Excel'de boş "Satış Fiyatı" metin değil boş hücre; dolu ise sayı.
  9. Depolar: her kayıt için PDF + düğmeler çizilmiyor; tıklanır satır, depo
     bazında grup, detay sayfa içinde.
"""
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


# ── Sahte Supabase istemcisi: sorguları sayar, tablo verisi tutar ────────
class _Yanit:
    def __init__(self, data):
        self.data = data


class _Sorgu:
    def __init__(self, sb, tablo):
        self.sb, self.tablo = sb, tablo
        self.filtre, self.islem, self.veri, self.sira = [], "select", None, None

    def select(self, *_a, **_k):
        self.islem = "select"
        return self

    def eq(self, a, v):
        self.filtre.append((a, lambda x, v=v: x == v))
        return self

    def in_(self, a, vs):
        vs = list(vs)
        self.filtre.append((a, lambda x, vs=vs: x in vs))
        return self

    def order(self, a, desc=False):
        self.sira = (a, desc)
        return self

    def limit(self, *_a):
        return self

    def insert(self, veri):
        self.islem, self.veri = "insert", veri
        return self

    def delete(self):
        self.islem = "delete"
        return self

    def _uyan(self, r):
        return all(f(r.get(a)) for a, f in self.filtre)

    def execute(self):
        self.sb.cagri.append((self.tablo, self.islem))
        if (self.tablo, self.islem) in self.sb.hata:
            raise RuntimeError("sahte hata")
        rows = self.sb.tablolar.setdefault(self.tablo, [])
        if self.islem == "select":
            out = [dict(r) for r in rows if self._uyan(r)]
            if self.sira:
                out.sort(key=lambda r: str(r.get(self.sira[0]) or ""), reverse=self.sira[1])
            return _Yanit(out)
        if self.islem == "insert":
            yeni = self.veri if isinstance(self.veri, list) else [self.veri]
            rows.extend(dict(r) for r in yeni)
            return _Yanit(yeni)
        if self.islem == "delete":
            silinen = [r for r in rows if self._uyan(r)]
            self.sb.tablolar[self.tablo] = [r for r in rows if not self._uyan(r)]
            return _Yanit(silinen)
        raise AssertionError(self.islem)


class _SahteSB:
    def __init__(self, tablolar=None, hata=()):
        self.tablolar = tablolar or {}
        self.cagri = []
        self.hata = set(hata)

    def table(self, ad):
        return _Sorgu(self, ad)


@pytest.fixture
def db(monkeypatch):
    from teknikservis import database as D

    def kur(tablolar=None, hata=()):
        sb = _SahteSB(tablolar, hata)
        monkeypatch.setattr(D, "get_client", lambda: sb)
        monkeypatch.setattr(D, "_cache_temizle", lambda: None)
        return sb
    return kur


def _bitmis_kayitlar(n):
    kayit, gecmis = [], []
    for i in range(1, n + 1):
        kayit.append({"id": i, "mevcut_durum": "satışa hazır", "mal_kabul_tarihi": "2026-09-01"})
        gecmis += [{"kayit_id": i, "durum": "mal kabül", "tarih": "2026-09-01T09:00:00"},
                   {"kayit_id": i, "durum": "satışa hazır", "tarih": "2026-09-08T10:00:00"},
                   {"kayit_id": i, "durum": "satışa hazır", "tarih": "2026-09-20T10:00:00"}]
    return kayit, gecmis


# ── 1. SLA: tek toplu sorgu ─────────────────────────────────────────
def test_sla_haritasi_tek_sorgu_ve_ilk_gecis(db):
    from teknikservis import database as D
    kayit, gecmis = _bitmis_kayitlar(120)
    kayit.append({"id": 999, "mevcut_durum": "teknisyende", "mal_kabul_tarihi": "2026-09-01"})
    sb = db({"ts_gecmis": gecmis})
    harita = D.sla_bitis_haritasi(kayit)
    assert sum(1 for t, _ in sb.cagri if t == "ts_gecmis") == 1
    # 01.09 (Sal) → 08.09 (Sal) = 5 iş günü; SLA ilk geçişte donar (20.09 değil)
    assert all(D.sla_is_gunu(k, harita) == 5 for k in kayit[:120])
    assert sum(1 for t, _ in sb.cagri if t == "ts_gecmis") == 1        # harita varken sorgu yok


def test_sla_haritasi_parcali_sorgu(db):
    from teknikservis import database as D
    kayit, gecmis = _bitmis_kayitlar(400)
    sb = db({"ts_gecmis": gecmis})
    D.sla_bitis_haritasi(kayit)
    assert sum(1 for t, _ in sb.cagri if t == "ts_gecmis") == 3        # 150'lik parçalar


def test_ekranlarda_haritasiz_sla_cagrisi_yok():
    for y in ("teknikservis/main.py", "teknikservis/ts_ekran.py"):
        src = _oku(y)
        assert not re.search(r"sla_is_gunu\(\s*\w+\s*\)", src), y


# ── 2. Silme: kayıt silinemezse geçmiş geri yazılır ─────────────────
def test_sil_kayit_basarisizsa_gecmis_korunur(db):
    from teknikservis import database as D
    sb = db({"ts_kayitlar": [{"id": 7}],
             "ts_gecmis": [{"id": 1, "kayit_id": 7, "durum": "mal kabül"},
                           {"id": 2, "kayit_id": 7, "durum": "teknisyende"}]},
            hata={("ts_kayitlar", "delete")})
    ok, hata = D.sil_kayit(7)
    assert not ok and hata
    assert sorted(r["id"] for r in sb.tablolar["ts_gecmis"]) == [1, 2]


def test_sil_kayit_basarili(db):
    from teknikservis import database as D
    sb = db({"ts_kayitlar": [{"id": 7}, {"id": 8}],
             "ts_gecmis": [{"id": 1, "kayit_id": 7}, {"id": 3, "kayit_id": 8}]})
    assert D.sil_kayit(7) == (True, "")
    assert [r["id"] for r in sb.tablolar["ts_kayitlar"]] == [8]
    assert [r["id"] for r in sb.tablolar["ts_gecmis"]] == [3]


# ── 3. Tarih biçimi ─────────────────────────────────────────────────
def test_islem_gecmisi_tarihi_noktali():
    from teknikservis.main import _tarih_gun
    assert _tarih_gun("2026-09-30T14:05:00") == "30.09.2026"
    assert _tarih_gun("2026-09-30T14:05:00+03:00") == "30.09.2026"
    assert _tarih_gun("") == "—"


# ── 4-5. Büyük harf / st.stop ───────────────────────────────────────
def test_buyuk_harf_etiket_yok():
    for y in ("teknikservis/main.py", "teknikservis/ts_ekran.py"):
        src = _oku(y)
        assert "uppercase" not in src, y
        assert "İŞLEM ÖZETİ" not in src, y


def test_st_stop_yok():
    assert "st.stop()" not in _oku("teknikservis/main.py")


# ── 6. Liste: tıklanır satır, SLA grupları, sayfa içi detay ──────────
def test_sla_kademe():
    from teknikservis.ts_hesap import sla_kademe
    assert sla_kademe(0)[1] == sla_kademe(5)[1] == "yesil"
    assert sla_kademe(6)[1] == "amber"
    assert sla_kademe(15)[1] == "kirmizi2"
    assert sla_kademe(16)[1] == "kirmizi"
    assert sla_kademe(30, bitmis=True)[1] == "silik"
    assert sla_kademe(16)[2] < sla_kademe(0)[2]                       # en acil grup önce


def test_sla_gruplari_acil_once_ve_sira_korunur():
    from teknikservis.ts_hesap import sla_gruplari
    ks = [{"id": 1, "_g": 2}, {"id": 2, "_g": 20}, {"id": 3, "_g": 3}, {"id": 4, "_g": 8}]
    g = sla_gruplari(ks, lambda k: k["_g"])
    assert [b for b, _ in g] == ["16+ iş günü", "6–10 iş günü", "0–5 iş günü"]
    assert [k["id"] for k in g[-1][1]] == [1, 3]


def test_liste_tiklanir_satir_ve_secim_kutusu_yok():
    m, e = _oku("teknikservis/main.py"), _oku("teknikservis/ts_ekran.py")
    assert "Detay / işlem için kayıt seç" not in m
    assert "B.tiklanir(" in e and "Listeye dön" in e
    assert "_kontrol_paneli(" in m                                    # panel aynen kullanılıyor


# ── 7-8. Excel ──────────────────────────────────────────────────────
def _govde(src, bas):
    g = src[src.index(bas):]
    son = g.find("\ndef ", 1)
    return g if son < 0 else g[:son]


def test_excel_yalniz_indirirken_uretilir():
    m = _oku("teknikservis/main.py")
    for fn, yardimci in (("def _liste(", "_ts_rapor_bayt"), ("def _depolar(", "_depo_rapor_bayt")):
        govde = _govde(m, fn)
        assert "pd.ExcelWriter" not in govde and "to_excel" not in govde, fn
        assert f"data=partial({yardimci}," in govde, fn          # tıklanınca üretilir
        assert "excel_bayt(" in _govde(m, f"def {yardimci}("), yardimci


def test_excel_satis_fiyati_sayi():
    from teknikservis.ts_hesap import sayi_ya_da_bos, excel_bayt
    assert sayi_ya_da_bos("") is None and sayi_ya_da_bos(None) is None
    assert sayi_ya_da_bos("12.5") == 12.5 and sayi_ya_da_bos(3) == 3.0
    assert sayi_ya_da_bos("abc") is None
    import io
    import pandas as pd
    b = excel_bayt([{"Servis No": "G5F1", "Satış Fiyatı": None}, {"Servis No": "G5F2", "Satış Fiyatı": 9.5}],
                   "Depolar")
    df = pd.read_excel(io.BytesIO(b))
    assert pd.isna(df["Satış Fiyatı"][0]) and df["Satış Fiyatı"][1] == 9.5


def test_rapor_satirinda_satis_fiyati_metin_degil():
    m = _oku("teknikservis/main.py")
    assert '"Satış Fiyatı": k.get("satis_fiyati", "")' not in m


# ── 9. Depolar ──────────────────────────────────────────────────────
def test_depolar_satir_basina_pdf_ve_dugme_yok():
    m = _oku("teknikservis/main.py")
    assert 'st.expander("📋 Detay & İşlem Geçmişi")' not in m
    e = _oku("teknikservis/ts_ekran.py")
    govde = _govde(e, "def depo_listesi(")
    assert "servis_formu_pdf" not in govde and "download_button" not in govde
    assert "B.grup_basligi(" in govde


def test_depo_gruplari_sirasi():
    from teknikservis.ts_hesap import depo_gruplari
    ks = [{"id": 1, "depo": "hurda"}, {"id": 2, "depo": "outlet"}, {"id": 3, "depo": "outlet"},
          {"id": 4, "depo": "bilinmeyen"}]
    g = depo_gruplari(ks, ["outlet", "ikinci el", "hurda"])
    assert [d for d, _ in g] == ["outlet", "hurda", "bilinmeyen"]
    assert [k["id"] for k in g[0][1]] == [2, 3]


def test_dizin_sql():
    s = _oku("veritabani/08_ts_gecmis_index.sql")
    assert "IF NOT EXISTS" in s.upper() and "ts_gecmis" in s and "kayit_id" in s


# ── 10. Mesaj kabı sabit: mesaj kaybolunca açık menüler kapanmasın ────
def test_mesajlar_sabit_kapta():
    """İşlem sonrası mesajı (satıldı, transfer…) bir sonraki tıklamada kaybolunca
    sayfadaki öğelerin sırası kayıyor, açık menü kapanıyordu: silme onayı
    işaretlenince menü kapanıyor, ikinci kez açmak gerekiyordu (tarayıcıda görüldü)."""
    m = _oku("teknikservis/main.py")
    for fn, anahtar in (("def _depolar(", "_ts_depo_bilgi"), ("def _kontrol_paneli(", "_ts_bilgi")):
        g = _govde(m, fn)
        kap = g.index("_mesaj = st.container()")
        assert kap < g.index(f'st.session_state.pop("{anahtar}"'), fn
        assert "_mesaj.success(" in g and "\n        st.success(_depo_bilgi)" not in g, fn

# -*- coding: utf-8 -*-
"""Mal kabulde giriş deposu seçimi + iade kaydı (Ekim 2026, kullanıcı kararı A).

Müşteriden alınan iade doğrudan satılacaksa İADE DEPO yerine MERKEZ / HAPPY LIFE seçilir; ürün
satılabilir stoğa girer. İade türündeki kabul Satış › İade'ye manuel iade olarak da yazılır (P&L iadeyi
düşer, ay sonu Excel'i mükerrer saymaz). Aylık iade Excel'i görevi takvimden kalktı."""
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


# ── Saf: giriş deposu çözümü ───────────────────────────────────────────
@pytest.mark.parametrize("metin, arayuz, beklenen", [
    ("", "iade", "İADE DEPO"), ("", "teknik", "TEKNİK DEPO"), (None, "iade", "İADE DEPO"),
    ("MERKEZ DEPO", "iade", "MERKEZ DEPO"), ("merkez", "iade", "MERKEZ DEPO"), ("Merkez Depo", "teknik", "MERKEZ DEPO"),
    ("happy life", "iade", "HAPPY LIFE"), ("iade", "teknik", "İADE DEPO"), ("ASEL", "iade", None),      # ASEL DEPO kapatıldı (talep #46)
    ("teknik servis", "iade", "TEKNİK DEPO"),
    ("OUTLET DEPO", "iade", None),      # listede yok: mal kabulde seçilemez
    ("yok böyle depo", "iade", None),
    ("", "", None),
])
def test_giris_depo_coz(metin, arayuz, beklenen):
    from teknikservis.stok import giris_depo_coz
    assert giris_depo_coz(metin, arayuz) == beklenen


def test_giris_deposu_kayittan():
    from teknikservis.stok import giris_deposu
    assert giris_deposu({"arayuz": "iade"}) == "İADE DEPO"
    assert giris_deposu({"arayuz": "iade", "giris_depo": "MERKEZ DEPO"}) == "MERKEZ DEPO"
    assert giris_deposu({"arayuz": "teknik", "giris_depo": "HAPPY LIFE"}) == "HAPPY LIFE"
    assert giris_deposu({"arayuz": "iade", "giris_depo": "OUTLET DEPO"}) == "İADE DEPO"   # geçersiz → varsayılan
    assert giris_deposu({"arayuz": "", "giris_depo": ""}) is None


@pytest.mark.parametrize("metin, beklenen", [
    ("", 0.0), (None, 0.0), ("1234.56", 1234.56), ("1.234,56", 1234.56), ("1,5", 1.5), ("$ 99", 99.0),
    ("abc", None), ("12.3.4", None),
])
def test_tutar_coz(metin, beklenen):
    from teknikservis.stok import tutar_coz
    assert tutar_coz(metin) == beklenen


# ── Stok hareketi seçilen depoya ───────────────────────────────────────
def test_mal_kabul_girisi_secilen_depoya(monkeypatch):
    import teknikservis.stok as S
    hareket = []
    monkeypatch.setattr(S, "_uygula", lambda sku, ad, depo, delta: (hareket.append((sku, depo, delta)) or (True, "ok")))
    assert S.mal_kabul_girisi({"arayuz": "iade", "stok_kodu": "SKU1", "stok_adi": "A"})[0]
    assert S.mal_kabul_girisi({"arayuz": "iade", "stok_kodu": "SKU2", "giris_depo": "MERKEZ DEPO"})[0]
    assert S.mal_kabul_girisi({"arayuz": "teknik", "stok_kodu": "SKU3", "giris_depo": "HAPPY LIFE"})[0]
    assert hareket == [("SKU1", "İADE DEPO", 1), ("SKU2", "MERKEZ DEPO", 1), ("SKU3", "HAPPY LIFE", 1)]
    ok, msg = S.mal_kabul_girisi({"arayuz": "", "stok_kodu": "X"})
    assert not ok and "arayüz" in msg


def test_gonderildi_ve_transfer_giris_deposundan(monkeypatch):
    """Depoya transfer edilmemiş kayıt: çıkış / transfer kaynağı mal kabulde girdiği depo."""
    import teknikservis.stok as S
    hareket = []
    monkeypatch.setattr(S, "_uygula", lambda sku, ad, depo, delta: (hareket.append((depo, delta)) or (True, "")))
    k = {"arayuz": "iade", "stok_kodu": "S", "giris_depo": "MERKEZ DEPO"}
    assert S.gonderildi_cikisi(k)[0] and hareket[-1] == ("MERKEZ DEPO", -1)
    assert S.depoya_transfer(k, "outlet")[0]
    assert hareket[-2:] == [("MERKEZ DEPO", -1), ("OUTLET DEPO", 1)]
    assert S.depoya_transfer(dict(k, depo="iade"), "merkez")[0]              # transfer edilmişse o depo
    assert hareket[-2:] == [("İADE DEPO", -1), ("MERKEZ DEPO", 1)]


# ── İade kaydı: Satış › İade'ye manuel iade, stok BURADA işlenmez ─────────
def test_iade_kaydi_yaz_manuel_iade(monkeypatch):
    import teknikservis.stok as S
    import satis.database as D
    cagri = []

    def _ekle(tarih, kanal, sku, urun_adi, adet, **kw):
        cagri.append((tarih, kanal, sku, urun_adi, adet, kw))
        return True, "✅", 501
    monkeypatch.setattr(D, "ekle_iade", _ekle)
    k = {"arayuz": "iade", "stok_kodu": "SKU9", "stok_adi": "Ürün", "firma_bilgisi": "VATAN A.Ş.",
         "giris_depo": "MERKEZ DEPO", "iade_net": "123.4"}
    ok, msg = S.iade_kaydi_yaz(k, tarih="2026-10-12")
    assert ok and "SKU9" in msg and "123,40" in msg
    assert cagri == [("2026-10-12", "VATAN A.Ş.", "SKU9", "Ürün", 1,
                      {"iade_net": 123.4, "depo": "MERKEZ DEPO", "kaynak": "manuel", "stok_isle": False,
                       "kimlik": True})]
    assert k["iade_id"] == 501                                          # servis kaydı iade satırına bağlanır
    # teknik servis kaydı: iade değil, hiçbir şey yapmaz
    assert S.iade_kaydi_yaz({"arayuz": "teknik", "stok_kodu": "T"}) == (True, "") and len(cagri) == 1
    # tutar girilmedi: 0 ile yazılır, mesaj söyler
    ok, msg = S.iade_kaydi_yaz({"arayuz": "iade", "stok_kodu": "SKU0", "firma_bilgisi": "X"}, tarih="2026-10-12")
    assert ok and cagri[-1][5]["iade_net"] == 0.0 and "tutar girilmedi" in msg
    monkeypatch.setattr(D, "ekle_iade", lambda *a, **k: (False, "❌ Hata", None))
    assert not S.iade_kaydi_yaz(k)[0]


def test_ekle_iade_stok_isle_kapali_ve_yukleme_bildirimi(monkeypatch):
    """stok_isle=False: iadeler'e yazar, stoğa dokunmaz; aktif yükleme varsa eklenen satırı bildirir."""
    import satis.database as D

    class _Tbl:
        def __init__(self, kayit):
            self.kayit = kayit

        def insert(self, k):
            self.kayit.append(k)
            return self

        def execute(self):
            class _R:
                data = [dict(self.kayit[-1], id=77)]
            return _R()

    yazilan, stok = [], []

    class _Cli:
        def table(self, ad):
            assert ad == "iadeler"
            return _Tbl(yazilan)
    monkeypatch.setattr(D, "_get_client", lambda: _Cli())
    monkeypatch.setattr(D, "_stok_uygula_depolu", lambda m, yon: stok.append((m, yon)))
    monkeypatch.setattr(D, "_kart_sku", lambda s, h=None: s)
    monkeypatch.setattr(D, "_temizle", lambda: None)
    eklenen = []

    class _Yk:
        def eklenen(self, tablo, satirlar, beklenen=None):
            eklenen.append((tablo, [r["id"] for r in satirlar], beklenen))
    monkeypatch.setattr(D, "_aktif_yukleme", lambda: _Yk())
    ok, _ = D.ekle_iade("2026-10-12", "VATAN", "SKU1", "A", 1, iade_net=10, depo="MERKEZ DEPO",
                        kaynak="manuel", stok_isle=False)
    assert ok and yazilan[-1]["kaynak"] == "manuel" and yazilan[-1]["depo"] == "MERKEZ DEPO"
    assert stok == [] and eklenen == [("iadeler", [77], 1)]
    assert D.ekle_iade("2026-10-12", "V", "SKU1", "A", 1, stok_isle=False, kimlik=True)[2] == 77   # kimlik isteğe bağlı
    ok, _ = D.ekle_iade("2026-10-12", "VATAN", "SKU1", "A", 2, depo="HAPPY LIFE")   # varsayılan: stok işlenir
    assert ok and stok == [([("SKU1", 2, "HAPPY LIFE")], 1)]


def test_toplu_mal_kabul_geri_alma_iadeleri_kapsar():
    from shared.yukleme_gecmisi import GERI_ALINABILIR
    assert "iadeler" in GERI_ALINABILIR["toplu_mal_kabul"] and "ts_kayitlar" in GERI_ALINABILIR["toplu_mal_kabul"]


# ── Ekran ve takvim ───────────────────────────────────────────────────
def test_ekran_depo_secimi_ve_iade_kaydi():
    m = _oku("teknikservis/main.py")
    assert 'key="mk_giris_depo"' in m      # birim fiyat artık Fatura ile iade sekmesinde (test_fatura_ile_iade)
    assert '"giris_depo": giris_depo' in m and "_stok.iade_kaydi_yaz(data)" in m
    assert '"Giren Depo", "İade Birim Fiyat", "Para Birimi"' in m      # toplu Excel şablonu
    g = m[m.index("def kapi_mal_kabul("):]
    assert g.index("ekle_kayit(") < g.index("mal_kabul_girisi(") < g.index("iade_kaydi_yaz(")
    assert "giris_depo_coz(_depo_t, _tur)" in g and "tutar_coz(_net_t)" in g
    d = _oku("teknikservis/database.py")
    assert '"giris_depo", "iade_net"' in d                            # kolon yoksa onlarsız yazar
    sql = _oku("veritabani/27_mal_kabul_depo.sql")
    assert "giris_depo" in sql and "iade_net" in sql


def test_aylik_iade_gorevi_kalkti():
    from shared import yukleme_takvimi as Y
    assert "iade_aylik" not in {k["anahtar"] for k in Y.KAYNAKLAR} and "iade_aylik" not in Y._OKUYUCU
    s = _oku("satis/main.py")
    assert 'serit("iade_aylik")' not in s and 'kaydet("iade_aylik"' not in s
    assert re.search(r'"iade_excel": dict\(', _oku("shared/dosya_kapisi.py"))   # Excel yüklemesi isteğe bağlı kaldı


# ── İade faturası birim fiyatı: USD ya da TL (Ekim 2026) ────────────────
@pytest.mark.parametrize("fiyat, pb, kur, beklenen", [
    (100, "USD", None, 100.0), (100, "usd", 40, 100.0), (4250, "TL", 42.5, 100.0), (1000, "₺", 40, 25.0),
    (1000, "TL", 0, None), (1000, "TL", None, None), (0, "TL", 40, 0.0), ("abc", "USD", None, None),
])
def test_iade_usd(fiyat, pb, kur, beklenen):
    from teknikservis.stok import iade_usd
    assert iade_usd(fiyat, pb, kur) == beklenen


def test_iade_fiyat_metni():
    from teknikservis.stok import iade_fiyat_metni
    assert iade_fiyat_metni({}) == "—"
    assert iade_fiyat_metni({"iade_net": 23.5, "iade_pb": "USD", "iade_fiyat": 23.5}) == "$23,50"
    m = iade_fiyat_metni({"iade_net": 23.53, "iade_pb": "TL", "iade_fiyat": 1000, "iade_kur": 42.5})
    assert m == "₺1.000,00 (kur 42,50 → $23,53)"


def test_kur_bul_gun_ve_yedek(monkeypatch):
    import teknikservis.stok as S
    import kayranacc.database as K
    monkeypatch.setattr(K, "get_kur_araligi", lambda b, e: {"2026-10-08": 41.0, "2026-10-10": 42.0, "2026-10-11": 0})
    assert S.kur_bul("2026-10-12") == 42.0                              # en yakın geçerli gün
    monkeypatch.setattr(K, "get_kur_araligi", lambda b, e: {})
    import gunluk
    monkeypatch.setattr(gunluk, "get_doviz", lambda: {"USD": 43.0})
    assert S.kur_bul("2026-10-12") == 43.0                              # güncel kur yedek
    monkeypatch.setattr(gunluk, "get_doviz", lambda: {})
    assert S.kur_bul("2026-10-12") is None


def _fiyat_ortami(monkeypatch, bul=None):
    import teknikservis.stok as S
    import teknikservis.database as T
    import satis.database as D
    yazilan, guncel = [], []
    monkeypatch.setattr(T, "kayit_guncelle", lambda kid, al: (yazilan.append((kid, al)) or True))
    monkeypatch.setattr(D, "iade_tutar_guncelle", lambda iid, net: (guncel.append((iid, net)) or (True, "ok")))
    monkeypatch.setattr(D, "manuel_iade_bul", lambda *a: bul)
    monkeypatch.setattr(S, "kur_bul", lambda t=None: 40.0)
    return S, yazilan, guncel


def test_iade_fiyat_guncelle_bagli_satir(monkeypatch):
    S, yazilan, guncel = _fiyat_ortami(monkeypatch)
    k = {"id": 5, "iade_id": 99, "stok_kodu": "A", "firma_bilgisi": "V", "mal_kabul_tarihi": "2026-10-12T10:00"}
    ok, msg, al = S.iade_fiyat_guncelle(k, 2000, "TL")
    assert ok and al == {"iade_fiyat": 2000.0, "iade_pb": "TL", "iade_kur": 40.0, "iade_net": 50.0}
    assert yazilan == [(5, al)] and guncel == [(99, 50.0)] and "₺2.000,00" in msg
    ok, _, al = S.iade_fiyat_guncelle(k, 75, "USD")
    assert ok and al["iade_kur"] is None and guncel[-1] == (99, 75.0)


def test_iade_fiyat_guncelle_eski_kayit(monkeypatch):
    """Bağlantısız eski kayıt: eşleşen manuel iade bulunursa bağlanır; bulunamazsa yeni satır AÇILMAZ."""
    S, yazilan, guncel = _fiyat_ortami(monkeypatch, bul=7)
    k = {"id": 5, "stok_kodu": "A", "firma_bilgisi": "V", "mal_kabul_tarihi": "2026-10-12", "iade_net": 0}
    ok, _, al = S.iade_fiyat_guncelle(k, 10, "USD")
    assert ok and al["iade_id"] == 7 and guncel == [(7, 10.0)]
    S, yazilan, guncel = _fiyat_ortami(monkeypatch, bul=None)
    ok, msg, al = S.iade_fiyat_guncelle(k, 10, "USD")
    assert ok and "iade_id" not in al and guncel == [] and "bulunamadı" in msg


def test_iade_fiyat_guncelle_kur_yok(monkeypatch):
    S, yazilan, guncel = _fiyat_ortami(monkeypatch)
    monkeypatch.setattr(S, "kur_bul", lambda t=None: None)
    ok, msg, al = S.iade_fiyat_guncelle({"id": 1, "iade_id": 2}, 100, "TL")
    assert not ok and "kur" in msg and yazilan == [] and guncel == []


def test_iade_tutar_guncelle_yalniz_manuel(monkeypatch):
    import satis.database as D
    sorgu = []

    class _Q:
        def update(self, al):
            sorgu.append(("update", al))
            return self

        def eq(self, k, v):
            sorgu.append((k, v))
            return self

        def execute(self):
            class _R:
                data = [{"id": 3}]
            return _R()

    class _Cli:
        def table(self, ad):
            assert ad == "iadeler"
            return _Q()
    monkeypatch.setattr(D, "_get_client", lambda: _Cli())
    monkeypatch.setattr(D, "_temizle", lambda: None)
    assert D.iade_tutar_guncelle(3, 12.5)[0]
    assert sorgu == [("update", {"iade_net": 12.5, "iade_brut": 12.5}), ("id", 3), ("kaynak", "manuel")]


def test_ekran_fiyat_alanlari():
    m = _oku("teknikservis/main.py")
    assert 'kayit_guncelle_form(form_no, {"iade_id": data["iade_id"]})' in m
    assert "_stok.iade_fiyat_guncelle(kayit, _yf, _ypb)" in m          # fatura sonradan gelince
    assert '"İade Birim Fiyat": sayi_ya_da_bos(k.get("iade_fiyat"))' in m   # Excel raporu
    g = m[m.index("def kapi_mal_kabul("):]
    assert '_tv(_r, "Para Birimi", "Döviz")' in g and 'kayit_guncelle_form(_fnok' in g
    sql = _oku("veritabani/28_iade_fiyat.sql")
    assert all(c in sql for c in ("iade_fiyat", "iade_pb", "iade_kur", "iade_id"))


# ── Depolar: mal kabulde doğrudan depoya girenler (Ekim 2026) ──────────
def test_dogrudan_giris_ve_giris_sekli():
    from teknikservis.stok import dogrudan_giris_mi, giris_sekli, GIRIS_SEKILLERI
    assert dogrudan_giris_mi({"arayuz": "iade", "giris_depo": "MERKEZ DEPO"})
    assert dogrudan_giris_mi({"arayuz": "teknik", "giris_depo": "HAPPY LIFE"})
    assert not dogrudan_giris_mi({"arayuz": "iade", "giris_depo": "İADE DEPO"})     # varsayılan depo
    assert not dogrudan_giris_mi({"arayuz": "teknik", "giris_depo": "TEKNİK DEPO"})
    assert not dogrudan_giris_mi({"arayuz": "iade"}) and not dogrudan_giris_mi({})
    assert not dogrudan_giris_mi({"arayuz": "iade", "giris_depo": "OUTLET DEPO"})   # listede değil
    assert giris_sekli({"arayuz": "iade", "giris_depo": "MERKEZ DEPO", "depo": "outlet"}) == GIRIS_SEKILLERI[0]
    assert giris_sekli({"arayuz": "iade", "depo": "outlet"}) == GIRIS_SEKILLERI[1]


def test_depolar_kayitlari_ve_gruplar():
    from teknikservis.ts_hesap import depolar_kayitlari, depo_gruplari, konum
    kay = [{"id": 1, "depo": "outlet"},
           {"id": 2, "arayuz": "iade", "giris_depo": "MERKEZ DEPO"},             # doğrudan, transfersiz
           {"id": 3, "arayuz": "iade", "giris_depo": "HAPPY LIFE"},
           {"id": 4, "arayuz": "iade", "giris_depo": "İADE DEPO"},               # varsayılan: listede yok
           {"id": 5, "arayuz": "teknik"},                                         # işlemde: listede yok
           {"id": 6, "arayuz": "iade", "giris_depo": "MERKEZ DEPO", "depo": "outlet"}]
    d = depolar_kayitlari(kay)
    assert [k["id"] for k in d] == [1, 2, 3, 6]
    assert [konum(k) for k in d] == ["outlet", "merkez", "HAPPY LIFE", "outlet"]
    assert "depo" not in d[1] and "_konum" not in kay[1]                    # asıl kayıt değişmez
    gr = dict(depo_gruplari(d, ["merkez", "outlet"]))
    assert [k["id"] for k in gr["merkez"]] == [2] and [k["id"] for k in gr["HAPPY LIFE"]] == [3]


def test_satis_cikisi_dogrudan_giris_deposundan(monkeypatch):
    import teknikservis.stok as S
    hareket = []
    monkeypatch.setattr(S, "_uygula", lambda sku, ad, depo, delta: (hareket.append((depo, delta)) or (True, "")))
    S.satis_cikisi({"arayuz": "iade", "stok_kodu": "A", "giris_depo": "MERKEZ DEPO"})
    S.satis_cikisi({"arayuz": "iade", "stok_kodu": "A", "giris_depo": "MERKEZ DEPO", "depo": "outlet"})
    S.satis_cikisi({"arayuz": "iade", "stok_kodu": "A"})                     # eski davranış
    assert hareket == [("MERKEZ DEPO", -1), ("OUTLET DEPO", -1), ("OUTLET DEPO", -1)]


def test_depolar_ekrani_filtre_ve_excel():
    m = _oku("teknikservis/main.py")
    g = m[m.index("def _depolar("):m.index("def _depo_detay(")]
    assert "kayitlar = depolar_kayitlari(get_kayitlar())" in g
    assert '"key": "depo_giris_f"' in g and "_stok.giris_sekli(k) != giris_f" in g
    assert "if depo_f and _konum(k) not in depo_f" in g and '"depo_giris_f"' in g
    r = m[m.index("def _depo_rapor_bayt("):m.index("def _depolar(")]
    for s_ in ('"Giriş Şekli": _stok.giris_sekli(k)', '"Giriş Deposu"', '"İade Birim Fiyat"', '"İade Net ($)"'):
        assert s_ in r, s_

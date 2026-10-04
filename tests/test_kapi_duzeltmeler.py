# -*- coding: utf-8 -*-
"""Dosya kapısıyla birlikte düzeltilen yükleme hataları (Ekim 2026).

Yüklemeler tek pencereye (shared/dosya_kapisi) taşınırken akışlar satır satır okundu; bugün de
canlıda olan şu hatalar bulundu ve düzeltildi:
1. Haftalık müşteri dosyası: yazma tutmazsa o firmanın o haftaki eski verisi siliniyor, yenisi
   yazılmıyor ve geri alma kaydı da oluşmuyordu (veri kaybı).
2. G5F sayımı: yarıda koparsa bir kısım ürün güncellenmiş oluyor ama ekranda "Dosya okunamadı"
   yazıyor, yükleme kaydı oluşmadığı için geri alınamıyordu.
3. Toplam Aktifler: kayıttan sonra okuma önbelleği temizlenmiyor, kartlar 5 dakikaya kadar eski
   rakamı gösteriyordu.
4. Ödeme listesi: aynı adlı hafta ikinci kez yüklenince iki ayrı hafta açılıyordu (artık önce onay).
5. Çek dökümü: mevcut çekler onay sorulmadan siliniyordu (artık kayıttan önce gösterilip onaylanır).
"""
from io import BytesIO

import pandas as pd
import pytest

import shared.yukleme_gecmisi as Y


class _Q:
    def __init__(self, db, t):
        self.db, self.t, self.f, self.ins, self.sil, self.upd = db, t, {}, None, False, None

    def select(self, *a, **k):
        return self

    def eq(self, c, v):
        self.f[c] = v
        return self

    def delete(self):
        self.sil = True
        return self

    def update(self, d):
        self.upd = d
        return self

    def insert(self, rows):
        self.ins = rows if isinstance(rows, list) else [rows]
        return self

    def execute(self):
        rows = self.db.setdefault(self.t, [])
        uy = [r for r in rows if all(r.get(c) == v for c, v in self.f.items())]
        if self.ins is not None:
            hata = self.db.get("_insert_hatasi")
            if hata and hata(self.t, self.ins):
                raise RuntimeError("yazma reddedildi")
            out = []
            for r in self.ins:
                self.db["_id"] = self.db.get("_id", 100) + 1
                out.append(dict(r, id=r.get("id") or self.db["_id"]))
            rows.extend(out)
            return type("R", (), {"data": out})()
        if self.sil:
            self.db[self.t] = [r for r in rows if r not in uy]
            return type("R", (), {"data": uy})()
        if self.upd is not None:
            for r in uy:
                r.update(self.upd)
            return type("R", (), {"data": uy})()
        return type("R", (), {"data": [dict(r) for r in uy]})()


class _DB:
    def __init__(self, tablolar):
        self.v = {k: [dict(r) for r in v] for k, v in tablolar.items()}

    def table(self, t):
        return _Q(self.v, t)


@pytest.fixture
def yazilan(monkeypatch):
    out = []
    monkeypatch.setattr(Y, "kaydet", lambda tur, n, dosya="", anahtarlar=(), degisiklik=None, kod="",
                        geri_alinabilir=None: out.append({"tur": tur, "n": n, "degisiklik": degisiklik}) or 1)
    return out


def _xlsx(sayfalar):
    b = BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        for ad, df in sayfalar.items():
            df.to_excel(w, index=False, sheet_name=ad)
    b.seek(0)
    return b


def _haftalik_dosya():
    return _xlsx({
        "VATAN STOK": pd.DataFrame({"STOKKODU": ["A1", "B2"], "ADET": [5, 7]}),
        "VATAN SATIŞ": pd.DataFrame({"STOKKODU": ["A1"], "MIKTAR": [2], "TARİH": ["2026-09-27"]}),
    })


# ── 1. Haftalık müşteri dosyası: yazılamazsa eski hafta korunur ─────────
def test_haftalik_yazma_tutmazsa_eski_hafta_kaybolmaz(monkeypatch, yazilan):
    import kayranpm.excel_islemler as E
    eski = {"id": 5, "firma": "VATAN", "sku": "A1", "yukleme_tarihi": "2026-09-27", "stok_miktari": 3,
            "haftalik_satis": 1, "stok_magaza": 0, "satis_magaza": 0, "urun_adi": ""}
    db = _DB({"firma_stok": [eski]})
    # Yeni satırların hepsi reddedilir (şema farkı vb.); eski satır geri yazılabilir (kimliği var)
    db.v["_insert_hatasi"] = lambda t, rows: t == "firma_stok" and any("id" not in r for r in rows)
    monkeypatch.setattr(E, "get_client", lambda: db)

    def _red(*a, **k):
        raise RuntimeError("satır satır yazma da reddedildi")
    monkeypatch.setattr(E, "upsert_firma_stok", _red)
    ok, msg = E.excel_yukle_haftalik_stok_satis(_haftalik_dosya(), dosya_adi="h.xlsx")
    assert not ok
    kalan = [r for r in db.v["firma_stok"] if r.get("firma") == "VATAN"]
    assert [r["sku"] for r in kalan] == ["A1"] and kalan[0]["stok_miktari"] == 3   # eski veri yerinde
    assert "geri yazıldı" in msg


def test_haftalik_onizleme_hicbir_sey_yazmaz(monkeypatch):
    import kayranpm.excel_islemler as E
    db = _DB({"firma_stok": [{"id": 5, "firma": "VATAN", "sku": "A1", "yukleme_tarihi": "2026-09-27"}]})
    db.v["_insert_hatasi"] = lambda t, rows: True              # yazma denenirse patlasın
    monkeypatch.setattr(E, "get_client", lambda: db)
    ok, oz = E.excel_yukle_haftalik_stok_satis(_haftalik_dosya(), dosya_adi="h.xlsx", onizle=True)
    assert ok and oz["rapor_tarihi"] == "2026-09-27"
    assert oz["firmalar"]["VATAN"]["sku"] == 2 and oz["firmalar"]["VATAN"]["stok"] == 12
    assert oz["firmalar"]["VATAN"]["satis"] == 2 and oz["firmalar"]["VATAN"]["mevcut"] == 1
    assert len(db.v["firma_stok"]) == 1                          # silme yok


# ── 2. G5F sayımı: yarıda kalırsa doğru mesaj + geri alınabilir kayıt ───
def _g5f_dosya():
    return _xlsx({"Sayfa1": pd.DataFrame({"DEPO ADI": ["MERKEZ DEPO", "MERKEZ DEPO", "MERKEZ DEPO"],
                                          "STOK KODU": ["A1", "B2", "C3"], "STOK İSMİ": ["a", "b", "c"],
                                          "MİKTAR": [4, 5, 6]})})


def test_g5f_yarida_kalirsa_okunamadi_demez(monkeypatch):
    import kayranpm.excel_islemler as E
    db = _DB({"urunler": [{"sku": "A1"}, {"sku": "B2"}, {"sku": "C3"}]})
    monkeypatch.setattr(E, "get_client", lambda: db)
    yazilanlar = []

    def _upsert(sku, ad, satilabilir, dd):
        if len(yazilanlar) == 1:
            raise RuntimeError("bağlantı koptu")
        yazilanlar.append(sku)
    monkeypatch.setattr(E, "upsert_g5f_stok", _upsert)
    ok, msg = E.excel_yukle_g5f_depolar(_g5f_dosya())
    assert not ok
    assert "okunamadı" not in msg and "1 ürün güncellendi" in msg
    yazilanlar.clear()
    ozet = {}
    E.excel_yukle_g5f_depolar(_g5f_dosya(), ozet=ozet)
    assert ozet["guncellenen"] == 1          # çağıran yükleme kaydını yazar → geri alınabilir


def test_g5f_onizleme_hicbir_sey_yazmaz(monkeypatch):
    import kayranpm.excel_islemler as E
    db = _DB({"urunler": [{"sku": "A1", "depo_kirilim": {"MERKEZ DEPO": 2}}, {"sku": "Z9", "depo_kirilim": {"MERKEZ DEPO": 1}}]})
    monkeypatch.setattr(E, "get_client", lambda: db)
    monkeypatch.setattr(E, "upsert_g5f_stok", lambda *a, **k: pytest.fail("önizleme yazdı"))
    ok, oz = E.excel_yukle_g5f_depolar(_g5f_dosya(), onizle=True)
    assert ok and oz["urun"] == 3 and oz["eslesen"] == 1 and oz["yeni"] == 2
    assert oz["toplam_adet"] == 15 and oz["sifirlanacak"] == ["Z9"]


# ── 3. Toplam Aktifler: kayıttan sonra okuma önbelleği temizlenir ──────
def test_aktif_excel_kaydet_basarida_onbellegi_temizler(monkeypatch):
    import kayranacc.database as K
    db = _DB({"aktif_excel_verileri": []})
    monkeypatch.setattr(K, "get_client", lambda: db)
    temizlendi = []
    monkeypatch.setattr(K, "_cache_temizle", lambda: temizlendi.append(1))
    assert K.aktif_excel_kaydet("ibrahim", "ithalat", 123.0) is True
    assert temizlendi, "başarılı kayıttan sonra önbellek temizlenmedi (kartlar 5 dk eski kalıyordu)"


def test_aktif_kaydet_son_yukleyen_gercek_kullanici(monkeypatch):
    import kayranacc.database as K
    import kayranacc.aktif_excel as M
    cagri = []
    monkeypatch.setattr(K, "aktif_excel_kaydet", lambda k, tip, v: cagri.append((k, tip)) or True)
    assert M.aktif_kaydet("ithalat", 50.0, b"", "pamuk")
    assert M.aktif_kaydet("cari", {"borc": {}, "alacak": {}}, b"", "pamuk", {"isimler": ["A FİRMA"]})
    assert cagri == [("pamuk", "ithalat"), ("pamuk", "cari"), ("pamuk", "cari_isimler")]
    monkeypatch.setattr(K, "aktif_excel_kaydet", lambda k, tip, v: False)
    assert M.aktif_kaydet("ithalat", 50.0, b"", "pamuk") is False   # yazılamadıysa "yüklendi" denmez


# ── 4–5. Ödeme listesi ve çek dökümü: kayıttan önce gösterilenler ───────
def test_ayni_hafta_bulunur():
    from kayranacc.excel_islemler import ayni_hafta
    h = [{"id": 1, "hafta_adi": "41. Hafta 06-12 Ekim"}, {"id": 2, "hafta_adi": "42. Hafta"}]
    assert ayni_hafta("41. hafta  06-12 ekim", h)["id"] == 1
    assert ayni_hafta("43. Hafta", h) is None and ayni_hafta("", h) is None


def test_cek_degisim_ozeti():
    from kayranacc.excel_islemler import cek_degisim_ozeti
    oz = cek_degisim_ozeti([{"meblagh": 100}, {"meblagh": "50"}], [],
                           {"TL": [{"meblagh": 10}], "USD": [{"meblagh": 99}]})
    assert oz == {"TL": {"yeni": 2, "yeni_tutar": 150.0, "mevcut": 1, "mevcut_tutar": 10.0}}


# ── 6. Alınan destekler Excel'i: hiçbir dosya okunamıyordu ──────────────
def test_alinan_destek_kendi_sablonunu_okur(monkeypatch):
    """Başlıklar normalize_tr ile BÜYÜK harfe çevrilip KÜÇÜK harf aranıyordu ("firma" in "FIRMA"):
    programın kendi şablonu dahil her dosya "Zorunlu kolon(lar) yok" diye reddediliyordu."""
    import kayranpm.ref_no as R
    eklenen = []
    monkeypatch.setattr(R, "alinan_destek_ekle", lambda *a: eklenen.append(a) or (True, "ok"))
    df = pd.DataFrame([{"FİRMA": "FAZEON", "TÜR": "SELLOUT", "DÖNEM": "2026-09", "TUTAR": 1500.0, "DÖVİZ": "USD",
                        "KATEGORİ": "MONİTÖR", "FATURA NO": "F-1", "AÇIKLAMA": "Eylül"}])
    n, atlanan, hatalar = R.alinan_destek_excel_ice_aktar(df)
    assert (n, atlanan, hatalar) == (1, 0, [])
    firma, tur, donem, tutar, doviz, fatura, aciklama, kategori = eklenen[0]
    assert (firma, tur, tutar, doviz, fatura, aciklama, kategori) == (
        "FAZEON", "SELLOUT", 1500.0, "USD", "F-1", "Eylül", "MONİTÖR")

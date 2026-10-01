# -*- coding: utf-8 -*-
"""Ürün Yönetimi kalan sayfalar yenileme (Ekim 2026).

  1. Dashboard: Firma / Kategori filtreleri hiçbir şeyi değiştirmiyordu
     (süzülen liste hesaplanıp kullanılmıyordu).
  2. Maliyet Girişi: kaydetmeden arama / "yalnız eksikler" değişince yazılan
     maliyetler sessizce siliniyordu (Streamlit 1.64'te tarayıcıda gösterildi).
     Anahtar listeye bağlı + sıfırlanınca uyarı.
  3-5. Sipariş Önerisi: onay/red için gizli ID yazılıyordu; öneri yoksa sayfa
     duruyor, bekleyen onaylara ulaşılamıyordu; bekleyen öneri görünmüyordu.
  6. Veri Yükleme: bir tarihin tüm firma stok verisi onaysız siliniyordu.
  7. Müşteri Satışları: "Satış" sütunu adet ama ortak tablo para sanıyordu.
  8-13. st.stop, büyük harf etiketler, ISO tarihler, iki adımlı indirme,
     boş sütun satırı, rerun'dan önce kaybolan başarı mesajları.
  Tüm Ürünler: sayfa artık liste; satıra tıklayınca sayfa içi detay, düzenleme
  aynı ürün için (iki ayrı ürün seçici vardı).
"""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _govde(src, bas, son_isaret="\n        elif sayfa == "):
    g = src[src.index(bas):]
    i = g.find(son_isaret, 1)
    return g if i < 0 else g[:i]


MAIN = "kayranpm/main.py"
YENI = ("kayranpm/urunler_ekran.py", "kayranpm/siparis_ekran.py", "kayranpm/urun_hesap.py")


# ── 1. Dashboard filtreleri ─────────────────────────────────────────
def _veri():
    return [
        {"sku": "A", "kategori": "Monitör", "siparis_durum": "acil",
         "firma_detay": [{"firma": "İTOPYA", "stok": 3}, {"firma": "VATAN", "stok": 0}]},
        {"sku": "B", "kategori": "kasa", "siparis_durum": "yaklasıyor",
         "firma_detay": [{"firma": "VATAN", "stok": 5}]},
        {"sku": "C", "kategori": "monitör", "siparis_durum": "acil", "firma_detay": []},
    ]


def test_dashboard_filtrele():
    from kayranpm.urun_hesap import dashboard_filtrele
    v = _veri()
    assert [u["sku"] for u in dashboard_filtrele(v, "Tüm Firmalar", "Tüm Kategoriler")] == ["A", "B", "C"]
    assert [u["sku"] for u in dashboard_filtrele(v, "ITOPYA", "Tüm Kategoriler")] == ["A"]   # İ/I eşleşir
    assert [u["sku"] for u in dashboard_filtrele(v, "VATAN", "Tüm Kategoriler")] == ["B"]    # stok 0 sayılmaz
    assert [u["sku"] for u in dashboard_filtrele(v, "Tüm Firmalar", "monitör")] == ["A", "C"]


def test_dashboard_filtre_metriklere_uygulanir():
    m = _govde(_oku(MAIN), 'if sayfa == "📊  Dashboard":')
    assert "dashboard_filtrele(" in m and "gosterilecek" not in m
    assert 'acil_urunler = [u for u in _dveri' in m


# ── 2. Maliyet Girişi düzenleyici anahtarı ──────────────────────────
def test_editor_anahtari_listeye_bagli():
    from kayranpm.urun_hesap import editor_anahtari
    a = editor_anahtari("mal", ["X1", "X2"])
    assert a == editor_anahtari("mal", ["X1", "X2"]) and a.startswith("mal_")
    assert a != editor_anahtari("mal", ["X2", "X1"]) != editor_anahtari("mal", ["X1"])


def test_maliyet_editoru_sabit_anahtarla_cizilmiyor():
    m = _govde(_oku(MAIN), 'elif sayfa == "💵  Maliyet Girişi":')
    assert 'key="mal_editor"' not in m and "editor_anahtari(" in m
    assert "kaydedilmemiş" in m                                        # sıfırlanınca uyarı
    assert 'st.success("✅ {} ürünün maliyeti' not in m               # rerun'dan önce kaybolurdu


# ── 3-5. Sipariş Önerisi ────────────────────────────────────────────
def test_siparis_satir_ici_onay_ve_gecmis_her_zaman():
    s = _oku("kayranpm/siparis_ekran.py")
    assert "Onaylanacak ID" not in s and "Reddedilecek ID" not in s
    assert "st.stop()" not in s
    r = s[s.index("def render("):]
    r = r[:r.find("\ndef ", 1)] if r.find("\ndef ", 1) > 0 else r
    assert re.search(r"\n    _gecmis\(", r), "geçmiş koşulsuz çizilmeli"
    assert 'elif sayfa == "📦  Sipariş Önerisi":' in _oku(MAIN) and "siparis_ekran" in _oku(MAIN)


def test_bekleyen_haritasi_ve_durum_adi():
    from kayranpm.urun_hesap import bekleyen_haritasi, siparis_durum_adi
    h = bekleyen_haritasi([{"sku": "A", "durum": "bekliyor", "oneri_miktari": 40},
                           {"sku": "A", "durum": "bekliyor", "oneri_miktari": 10},
                           {"sku": "B", "durum": "onaylandi", "oneri_miktari": 5}])
    assert h == {"A": 50}
    assert siparis_durum_adi("onaylandi") == "Onaylandı" and siparis_durum_adi("reddedildi") == "Reddedildi"


# ── 6. Veri Yükleme: onaylı silme ───────────────────────────────────
def test_tarih_silme_onayli_ve_onbellek():
    m = _govde(_oku(MAIN), 'elif sayfa == "📂  Veri Yükleme":', "\n    _sayfa_parcasi()")
    assert 'table("firma_stok").delete()' not in m
    assert "B.onayli_sil(" in m and "sil_firma_stok_tarihi(" in m
    assert 'key=f"vy_tarih_{_sil_r[\'_ham\']}"' in m      # onay bir sonraki tarihe taşınmaz
    d = _oku("kayranpm/database.py")
    g = d[d.index("def sil_firma_stok_tarihi("):]
    g = g[:g.index("\ndef ", 1)]
    assert ".delete()" in g and "cache_data.clear()" in g


def test_tarih_sayaclari():
    from kayranpm.urun_hesap import yukleme_ozeti
    o = yukleme_ozeti([{"yukleme_tarihi": "2026-09-01", "firma": "VATAN"},
                       {"yukleme_tarihi": "2026-09-01", "firma": "HB"},
                       {"yukleme_tarihi": "2026-09-08", "firma": "VATAN"}],
                      [{"guncelleme_tarihi": "2026-09-08"}, {"guncelleme_tarihi": None}])
    assert [r["Tarih"] for r in o] == ["08.09.2026", "01.09.2026"]
    assert o[1]["Firma Kayıt Sayısı"] == 2 and o[1]["Firmalar"] == "HB, VATAN"
    assert o[0]["Yüklenen Ürün"] == 1 and o[0]["_ham"] == "2026-09-08"


# ── 7. Müşteri Satışları adet sütunu ────────────────────────────────
def test_musteri_satis_adet_sutunu():
    from shared.tasarim import _tablo_kolon_tipi
    assert _tablo_kolon_tipi("Satış") == "para"          # tuzak: tek başına "Satış" para sayılır
    assert _tablo_kolon_tipi("Satış adedi") == "adet"
    m = _govde(_oku(MAIN), 'elif sayfa == "📈  Müşteri Satışları":')
    assert '"Satış": int(r.get("haftalik_satis"' not in m and '"Satış adedi":' in m
    assert "_mhs_excel(_ozet, _df)," not in m             # Excel her yenilemede üretilmez


# ── 8-13. Genel ─────────────────────────────────────────────────────
def test_st_stop_ve_buyuk_harf_yok():
    for y in (MAIN,) + YENI:
        s = _oku(y)
        assert "st.stop()" not in s, y
        assert "uppercase" not in s, y
        for et in ("PAÇAL FOB", "FİYAT ANALİZİ", "STOK DAĞILIMI", "🚨 ACİL SİPARİŞ", "EXCEL RAPORU",
                   "PDF RAPORU", '"🔴 ACİL"', "G5F DEPO KIRILIMI"):
            assert et not in s, (y, et)


def test_tarih_tr():
    from kayranpm.urun_hesap import tarih_tr
    assert tarih_tr("2026-10-01") == "01.10.2026"
    assert tarih_tr("2026-10-01T14:05:09+03:00") == "01.10.2026"
    assert tarih_tr("2026-10-01T14:05:09", saat=True) == "01.10.2026 14:05"
    assert tarih_tr(None) == "" and tarih_tr("bozuk") == "bozuk"


def test_iso_tarih_gosterilmiyor():
    m = _oku(MAIN)
    assert '"Başlangıç": str(k.get("baslangic_tarihi", "") or "")[:10]' not in m
    assert '"Tarih": sp["olusturma_tarihi"]' not in m
    assert '"Tarih": str(r.get("yukleme_tarihi", ""))[:10]' not in m


def test_tek_adimli_indirme():
    for y in (MAIN, "kayranpm/urunler_ekran.py"):
        s = _oku(y)
        for et in ("Excel Oluştur", "PDF Oluştur", "Excel Raporu Oluştur", "PDF Raporu Oluştur"):
            assert et not in s, (y, et)
    assert "sablon_bytes = create_sample_excel_bytes()" not in _oku(MAIN)


def test_bos_sutun_satiri_ve_cift_ayrac_yok():
    m = _oku(MAIN)
    assert "c1, c2, c3, c4, c5 = st.columns(5)" not in m
    assert 'st.markdown("---")\n            st.markdown("---")' not in m


def test_toplu_dialog_oner_pencereyi_kapatmaz():
    m = _govde(_oku(MAIN), 'elif sayfa == "📂  Veri Yükleme":', "\n    _sayfa_parcasi()")
    for anahtar in ('key="satis_oner"', 'key="kat_oto"', 'key="kat_std_btn"'):
        g = m[m.index(anahtar):]
        g = g[:g.index("st.rerun(") + 40]
        assert 'st.rerun(scope="fragment")' in g, anahtar


# ── Tüm Ürünler ─────────────────────────────────────────────────────
def test_urun_satiri_hesap():
    from kayranpm.urun_hesap import urun_satiri
    r = urun_satiri({"sku": "A", "urun_adi": "Kasa", "satis_fiyati": 120, "final_cost_price": 100,
                     "fob_price": 80, "ithalat_dosya_sayisi": 2, "toplam_stok": 7,
                     "firma_stoklari": {"VATAN": 4}})
    assert r["Net Kar ($)"] == 20 and round(r["Net Marj (%)"], 2) == 16.67
    assert r["Maliyet %"] == 25 and r["VATAN"] == 4 and r["Toplam"] == 7
    r2 = urun_satiri({"sku": "B", "satis_fiyati": 50, "final_cost_price": 40, "ithalat_dosya_sayisi": 0})
    assert r2["Final Cost ($)"] is None and r2["Net Kar ($)"] is None     # ithalat yoksa paçal yok


def test_urun_filtrele_sirala():
    from kayranpm.urun_hesap import urun_filtrele_sirala
    rows = [{"SKU": "A", "Ürün Adı": "Monitör 27", "Kategori": "Monitör", "Marka": "X", "Net Kar ($)": 5.0},
            {"SKU": "B", "Ürün Adı": "Kasa", "Kategori": "kasa", "Marka": "Y", "Net Kar ($)": -3.0},
            {"SKU": "C", "Ürün Adı": "Fan", "Kategori": "kasa", "Marka": "Y", "Net Kar ($)": None}]
    assert [r["SKU"] for r in urun_filtrele_sirala(rows, ara="monit")] == ["A"]
    assert [r["SKU"] for r in urun_filtrele_sirala(rows, kategori="kasa")] == ["B", "C"]
    assert [r["SKU"] for r in urun_filtrele_sirala(rows, sadece_zarar=True)] == ["B"]
    assert [r["SKU"] for r in urun_filtrele_sirala(rows, sira="Net Kar ($)", azalan=True)] == ["A", "B", "C"]
    assert [r["SKU"] for r in urun_filtrele_sirala(rows, sira="Net Kar ($)", azalan=False)] == ["B", "A", "C"]


def test_tum_urunler_liste_ve_tek_secici():
    m = _govde(_oku(MAIN), 'elif sayfa == "📋  Tüm Ürünler":')
    assert "_dlg_urunler_ozet" not in m and 'key="tu_sku"' not in m and 'key="urun_duzen_sec"' not in m
    assert 'B.secili("pm_urun")' in m and 'B.listeye_don("pm_urun")' in m
    e = _oku("kayranpm/urunler_ekran.py")
    assert "B.tiklanir(" in e and "B.filtre(" in e and "data=partial(" in e


def test_bilesen_sayfa_ici_detay():
    from shared import bilesen as B
    for ad in ("sec", "secili", "birak", "listeye_don", "koru", "geri_yukle"):
        assert callable(getattr(B, ad)), ad
    assert "Listeye dön" in _oku("shared/bilesen.py")


def test_detaydan_donuste_filtreler_geri_yuklenir():
    """'st.session_state[k] = st.session_state[k]' hilesi 1.64'te değeri tutuyor ama
    yeniden çizilen kutu BOŞ görünüyordu (tarayıcıda görüldü; Teknik Servis'te de).
    koru() gölge anahtara kopyalar, geri_yukle() kutular oluşmadan önce geri yazar."""
    b = _oku("shared/bilesen.py")
    g = b[b.index("def koru("):]
    assert 'st.session_state[f"_koru_{k}"]' in g and "st.session_state[k] = st.session_state[k]" not in g
    pm = _oku(MAIN)
    i = pm.index("B.geri_yukle(_UFK")
    assert i < pm.index("_urun_liste(urun_data)")
    ts = _oku("teknikservis/main.py")
    for fn, kutu in (("def _liste(", 'barkod_okuyucu(f"ts_ara_{arayuz}"'), ("def _depolar(", 'key="depo_ara"')):
        g = ts[ts.index(fn):]
        assert g.index("E.geri_yukle(_filtre_keys)") < g.index(kutu), fn


def test_kanal_kart_adlari_bozulmaz():
    """Metrik etiketleri cümle düzenine iner; kanal kodu verilirse 'HB' → 'Hb' olurdu."""
    from shared.tasarim import kpi_etiketi
    from kayranpm.urun_hesap import KANAL_AD, KANALLAR
    assert kpi_etiketi("HB") == "Hb"                                  # tuzak
    for k in KANALLAR:
        assert kpi_etiketi(KANAL_AD[k]) == KANAL_AD[k]
    assert 'KANAL_AD.get(firma, firma)' in _oku(MAIN)

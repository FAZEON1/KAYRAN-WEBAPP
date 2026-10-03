# -*- coding: utf-8 -*-
"""Satış modülü yenileme — 1. paket (Ekim 2026): hatalar + Satışlar + Satış Girişi.

Bulunan hatalar:
  1. Tutarlar İngilizce biçimdeydi ($1,035,231.62) — program geri kalanı TR
  2. Toplamlar 4 haneli ("$230,365.7346")
  3. Metinde iki '$' yan yana gelince ekran araya kalanı LaTeX sanıyordu
     (Kâr/P&L notu "bekleniyorgenel toplamkar" diye bozuk görünüyordu)
  4. Kategori kırılımında MONİTÖR ve MONITÖR iki ayrı satır
  5. İade özetinde "İade tutarı" sütunu boş (metin '$7.29' sayıya çevrilemiyordu)
  6. Tarih seçicinin ‹ › düğmeleri boş kutu; Kâr/P&L'de seçici başlığın üstünde
  7. Kâr/P&L'de 7 sütunlu iki tablo yarım genişlikte yan yana, Kâr sütunu taşıyordu
  + Satışlar: "Kalemi sil" / "Siparişi sil" ONAYSIZ siliyordu
"""
from pathlib import Path

from satis import satis_hesap as H

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _kar(s):   # satis.database.satir_kar ile aynı formül (test için yerel)
    adet = int(s.get("adet") or 0)
    ciro = adet * float(s.get("birim_satis") or 0)
    mal = adet * float(s.get("birim_maliyet") or 0)
    des = adet * (float(s.get("birim_firma_destek") or 0) + float(s.get("birim_ek_destek") or 0))
    nk = ciro - des - mal
    return {"adet": adet, "ciro": ciro, "maliyet": mal, "destek": des, "net_kar": nk,
            "marj": (nk / (ciro - des) * 100) if ciro - des > 0 else 0}


S = [{"id": 1, "tarih": "2026-10-01", "siparis_no": "A1", "kanal": "VATAN", "sku": "X24F165S",
      "urun_adi": "FAZEON X24F165S MONITÖR", "adet": 2, "birim_satis": 100, "birim_maliyet": 70},
     {"id": 2, "tarih": "2026-10-01", "siparis_no": "A1", "kanal": "VATAN", "sku": "F14PLUS",
      "urun_adi": "FAZEON F14 KASA", "adet": 1, "birim_satis": 50, "birim_maliyet": 0},
     {"id": 3, "tarih": "2026-09-30", "siparis_no": "B7", "kanal": "EERA", "sku": "AIO240",
      "urun_adi": "FROST 240", "adet": 3, "birim_satis": 60, "birim_maliyet": 40},
     {"id": 4, "tarih": "2026-09-30", "siparis_no": "", "kanal": "EERA", "sku": "KB60",
      "urun_adi": "KB60", "adet": 1, "birim_satis": 40, "birim_maliyet": 20}]


def test_siparise_gore_gruplama():
    g = H.siparis_grupla(S, _kar)
    assert [o["siparis_no"] for o in g] == ["A1", "B7", ""]          # en yeni üstte; no'suz kalem tek sipariş
    a1 = g[0]
    assert a1["kalem"] == 2 and a1["adet"] == 3 and a1["ciro"] == 250
    assert a1["net_kar"] == (200 - 140) + (50 - 0) and a1["maliyetsiz"] == 1
    assert round(H.toplam(g)["ciro"], 2) == 250 + 180 + 40


def test_arama_i_ve_I_ayni_ve_firma_filtresi():
    g = H.siparis_grupla(S, _kar)
    assert [o["siparis_no"] for o in H.ara(g, "monitör")] == ["A1"]    # ürün adı noktasız I'lı
    assert [o["siparis_no"] for o in H.ara(g, "b7")] == ["B7"]
    assert [o["siparis_no"] for o in H.ara(g, "", "EERA")] == ["B7", ""]


def test_gun_adi_ve_gun_gruplari():
    from datetime import date
    b = date(2026, 10, 1)
    assert H.gun_adi("2026-10-01", b) == "Bugün" and H.gun_adi("2026-09-30", b) == "Dün"
    assert H.gun_adi("2026-09-28", b) == "28 Eylül, Pazartesi"
    assert [d for d, _ in H.gunlere_bol(H.siparis_grupla(S, _kar))] == ["2026-10-01", "2026-09-30"]


# ── Hatalar ──────────────────────────────────────────────────────────
def test_1_2_usd_tr_bicim_toplam_iki_hane():
    import tests.test_tablo_bicim as T   # _usd'yi satis/main.py'den çıkaran yardımcı
    assert T._usd(1035231.62) == "$1.035.231,62" and T._usd(230365.7346) == "$230.365,73"


def test_3_markdown_metinde_dolar_kacirilir():
    src = _oku("satis/main.py")
    assert "def _usd_md(" in src
    for parca in ("GENEL destek: **{_usd_md(_genel_dst)}**", "toplam kâr **{_usd_md(",
                  "{_usd_md(_ciro)} • Firma:"):   # etiket Kanal → Firma (Eki 2026)
        assert parca in src, parca
    assert "GENEL destek: **{_usd(" not in src


def test_4_alinan_destek_kategorisi_satisla_ayni_bicim():
    src = _oku("satis/main.py")
    assert "_ad_marka, _ad_kat = _tb_anahtar(_ad_marka), _tb_anahtar(_ad_kat)" in src


def test_5_iade_tablolari_ham_sayi():
    src = _oku("satis/main.py")
    assert '"İade tutarı": round(v["tutar"], 2)' in src
    assert '"İade tutarı": round(float(r.get("iade_net") or 0), 2)' in src
    assert '"İade tutar": _usd(' not in src


def test_6_tarih_oklari_ve_pnl_sirasi():
    t = _oku("shared/tarih.py")
    assert "on_click=_kaydir_tik" in t and "padding:0 !important" in t
    assert "button[data-testid]" in t            # ipucu kabının içindeki düğme hedeflenir
    src = _oku("satis/main.py")
    i_bas = src.index('_ph1.markdown(_sb("🧾 Satış", "Kâr / P&L"')
    i_tar = src.index('_pbas, _pbit = hizli_tarih_araligi("p_pnl"')
    assert i_bas < i_tar


def test_7_kirilim_tek_tablo_secicili():
    src = _oku("satis/main.py")
    assert 'st.segmented_control("Kırılım", ["Kategori", "Marka"]' in src
    assert "(_c1, _marka_map, _ad_marka" not in src


def test_satis_silme_onayli_ve_yeni_ekran():
    m = _oku("satis/main.py")
    assert "from .satislar_ekran import render_satislar" in m
    assert 'key="l_sil_btn"' not in m and 'key="l_sil_sip_btn"' not in m   # eski onaysız düğmeler
    e = _oku("satis/satislar_ekran.py")
    assert "B.onayli_sil(" in e and 'disabled=not onay' in e
    assert "get_siparis_kalemleri(" in e          # detay düzenlemesi taze kayda bakar


def test_satis_girisi_dogrudan_pencereler():
    m = _oku("satis/main.py")
    for d in ("def _dlg_xl_vatan", "def _dlg_xl_eera", "def _dlg_xl_diger", "def _sg_acilis("):
        assert d in m, d
    assert "_satis_excel_dialog" not in m and 'key="tgl_sat_vatan"' not in m


# ── 2. paket: Kâr/P&L · İade · İçe Aktar ────────────────────────────
def test_pnl_excel_raporu_ertelenmis_ve_kirilimli():
    """Rapor yalnız tıklanınca, AYRI iş parçacığında üretilir; orada
    st.session_state okunamaz. Kırılım sayfaları kapsam sözlüğünden gelir
    (yoksa rapor 'Marka'/'Kategori' sayfasız iniyordu)."""
    import ast
    src = _oku("satis/main.py")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_pnl_xlsx")
    assert "session_state" not in ast.get_source_segment(src, fn)
    assert "_xl_kirilim[_kol] = list(_tablo)" in src
    assert "data=_pnl_xlsx" in src and 'on_click="ignore"' in src


def test_pnl_yerlesim():
    src = _oku("satis/main.py")
    assert "_SHp.aylik_seyir(satislar, satir_kar)" in src            # aylık seyir grafiği
    assert "_mlz = _SHp.maliyetsiz_say(satislar)" in src and "if _mlz:" in src
    assert 'st.button("Maliyeti 0 olan satışları paçaldan düzelt' not in src   # koşulsuz düğme kalktı
    assert "%{y:,.0f}" not in src                                     # grafik ipucu TR


def test_aylik_seyir_ve_maliyetsiz():
    a = H.aylik_seyir(S, _kar)
    assert [x[0] for x in a] == ["2026-09", "2026-10"]
    assert a[1][1] == 250 and a[1][2] == (200 - 140) + 50
    assert H.maliyetsiz_say(S) == 1


def test_iade_silme_id_yazdirmiyor_onayli():
    """Eski pencere 'Silinecek iade ID' istiyordu ama tabloda ID yoktu."""
    src = _oku("satis/main.py")
    assert "st.number_input(\"Silinecek iade ID\"" not in src
    assert "def _iade_kayit_listesi(" in src and 'B.onayli_sil("Evet, bu iade kaydını sil"' in src


def test_iade_dort_kart_ve_ice_aktar_adimlari():
    src = _oku("satis/main.py")
    assert '("İade oranı", f"%{tr_sayi(_ior, 1)}", trenk("amber"))' not in src     # 9'lu eski kartlar
    assert "def _adim_gostergesi(" in src and "_adim_gostergesi(2)" in src

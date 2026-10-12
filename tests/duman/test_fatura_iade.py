# -*- coding: utf-8 -*-
"""Sayfa testi · Yeni Mal Kabül › İade › Fatura ile (çok kalem): ürün stok kartlarından seçilir, yanında
bu firmaya son satış fiyatı çıkar ve fiyat alanına dolar; kalemler eklenir, kaydedince her adet için
servis kaydı + Satış › İade satırı açılır. Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def test_fatura_ile_iade_kalem_kalem_kaydedilir():
    import os
    from datetime import date, timedelta
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["urunler"] = [
        {"sku": "X24F165S", "urun_adi": "FAZEON 24 MONITOR", "satis_fiyati": 60, "bizim_stok": 5,
         "depo_kirilim": {"MERKEZ DEPO": 5}},
        {"sku": "K100", "urun_adi": "KLAVYE", "satis_fiyati": 15, "bizim_stok": 3, "depo_kirilim": {"MERKEZ DEPO": 3}},
    ]
    dun = str(date.today() - timedelta(days=1))
    sahte_db.TABLOLAR["satislar"] = [
        {"id": 1, "tarih": dun, "kanal": "VATAN BİLGİSAYAR", "sku": "X24F165S", "adet": 1, "birim_satis": 52},
        {"id": 2, "tarih": dun, "kanal": "İTOPYA", "sku": "X24F165S", "adet": 1, "birim_satis": 55},
    ]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    for k, v in {"giris_yapildi": True, "aktif_kullanici": sahte_db.KULLANICI, "aktif_uygulama": "teknikservis",
                 "ts_sayfa": "📥  Mal Kabül", "_mk_dialog_ac": True, "mk_arayuz": "↩️ İade",
                 "mk_iade_bicim": "Fatura ile (çok kalem)", "mk_fat_firma_yeni": "VATAN BİLGİSAYAR",
                 "mk_fat_no": "IAD2026001", "mk_fat_depo": "MERKEZ DEPO"}.items():
        at.session_state[k] = v

    def _calistir(eleman=None):
        at.session_state["_mk_dialog_ac"] = True
        (eleman.run() if eleman is not None else at.run())
        assert not _sorunlar(at), _sorunlar(at)

    try:
        _calistir()
        sec = at.selectbox(key="mk_fat_sku_0")
        assert sec.format_func("X24F165S") == "X24F165S — FAZEON 24 MONITOR · son fiyat $52,00"   # VATAN'a son satış
        assert sec.format_func("K100") == "K100 — KLAVYE"                                         # satış yok
        _calistir(sec.select("X24F165S"))
        assert at.number_input(key="mk_fat_fiyat_X24F165S_USD").value == 52.0
        _calistir(at.number_input(key="mk_fat_adet").set_value(2))
        _calistir(at.button(key="mk_fat_ekle").click())
        _calistir(at.selectbox(key="mk_fat_sku_1").select("K100"))
        assert at.number_input(key="mk_fat_fiyat_K100_USD").value == 15.0    # kartın satış fiyatı
        _calistir(at.number_input(key="mk_fat_fiyat_K100_USD").set_value(14.5))
        _calistir(at.button(key="mk_fat_ekle").click())
        assert [(k["sku"], k["adet"], k["fiyat"]) for k in at.session_state["mk_fat_kalemler"]] == [
            ("X24F165S", 2, 52.0), ("K100", 1, 14.5)]
        assert any("3 adet · toplam $118,50" in m.value for m in at.markdown)
        _calistir(at.button(key="mk_fat_kaydet").click())
        ts = sahte_db.TABLOLAR.get("ts_kayitlar", [])
        assert [(r["stok_kodu"], r["seri_no"], r["iade_net"]) for r in ts] == [
            ("X24F165S", "NO SERIAL NUMBER", 52.0), ("X24F165S", "NO SERIAL NUMBER", 52.0),
            ("K100", "NO SERIAL NUMBER", 14.5)]
        assert all(r["fatura_no"] == "IAD2026001" and r["giris_depo"] == "MERKEZ DEPO" for r in ts)
        iade = sahte_db.TABLOLAR.get("iadeler", [])
        assert [(r["sku"], r["iade_adet"], r["iade_net"], r["depo"], r["kanal"]) for r in iade] == [
            ("X24F165S", 1, 52.0, "MERKEZ DEPO", "VATAN BİLGİSAYAR")] * 2 + [
            ("K100", 1, 14.5, "MERKEZ DEPO", "VATAN BİLGİSAYAR")]
        assert any("IAD2026001 numaralı iade faturası, 3 adet" in m.value for m in at.success)
        assert "mk_fat_kalemler" not in at.session_state                    # sepet temizlendi
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)

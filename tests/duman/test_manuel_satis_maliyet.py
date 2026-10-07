# -*- coding: utf-8 -*-
"""Sayfa testi · Manuel satış penceresi: kartın yazımı kanonik anahtardan farklı ürüne ('Mio MiVue J30')
kalem eklenince paçal maliyet gelir (canlıda 0 yazılıyor, sipariş "1 maliyetsiz" görünüyordu).
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402

MIO = "Mio MiVue J30"


def test_manuel_satista_kart_yazimli_urunun_pacali_gelir():
    import os
    import sahte_db
    from streamlit.testing.v1 import AppTest
    os.environ["DUMAN_ONBELLEK_TEMIZLE"] = "1"
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    # Yurt içi alış maliyeti kartta: get_pacal_map onu kanonik anahtarla ('MIO MIVUE J30') tutar
    sahte_db.TABLOLAR["urunler"] = [{"sku": MIO, "urun_adi": "MIO MIVUE J30 ARAÇ KAMERASI", "alis_fiyati": 41.2,
                                     "bizim_stok": 10, "depo_kirilim": {"MERKEZ DEPO": 10}}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "satis"
    at.session_state["satis_sayfa"] = "🧾 Satış Girişi"
    at.session_state["_ms_dialog_ac"] = True
    try:
        at.run()
        assert not _sorunlar(at), _sorunlar(at)
        sec = at.selectbox(key="s_sku_sec")
        mio = [o for o in sec.options if o.startswith(MIO)]
        assert len(mio) == 1 and not [o for o in sec.options if o.startswith("MIO MIVUE J30")], sec.options
        assert any("Maliyet (paçal): $41,2" in c.value for c in at.caption)
        at.session_state["_ms_dialog_ac"] = True
        sec.select(mio[0])
        at.number_input(key="s_bsat").set_value(57.0)
        at.run()
        at.session_state["_ms_dialog_ac"] = True
        at.button(key="s_ekle").click().run()
        assert not _sorunlar(at), _sorunlar(at)
        kalem = at.session_state["satis_kalemler"]
        assert [(k["sku"], k["birim_maliyet"]) for k in kalem] == [(MIO, 41.2)]
    finally:
        os.environ.pop("DUMAN_ONBELLEK_TEMIZLE", None)

# -*- coding: utf-8 -*-
"""Sayfa testi, ÖRNEK VERİYLE: Sistem › Bilgi İşlem (Ekim 2026). Ölçüm, rapor ve hata kayıtlarıyla
bütün bölümler çizilmeli; sayfa açılışı da bt_olcum'a yazılmalı."""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("streamlit.testing.v1")

from test_sayfalar import BETIK, SURE  # noqa: E402


def _veri():
    s = datetime.now(timezone.utc)
    olc = []
    for g in range(14):
        for i, ms in enumerate((900, 1400, 2600, 4100)):
            olc.append({"id": len(olc) + 1, "zaman": (s - timedelta(days=g, hours=i)).isoformat(),
                        "modul": "satis", "sayfa": "satislar", "ms": ms + g * 40, "hata": i == 3})
    rapor = [
        {"id": 1, "zaman": s.isoformat(), "tur": "calisma", "baslik": "Gece kontrolü", "durum": "bilgi",
         "ozet": "Testler geçti; en yavaş sayfa satis/satislar (p50 2,6 sn)."},
        {"id": 2, "zaman": (s - timedelta(days=5)).isoformat(), "tur": "iyilestirme",
         "baslik": "Bilgi işlem: Satışlar sayfası önbellek", "durum": "otomatik_birlesti",
         "pr_url": "https://github.com/FAZEON1/KAYRAN-WEBAPP/pull/999", "olcut": "satis/satislar p50",
         "once": 3200, "sonra": 1900, "birim": "ms"},
        {"id": 3, "zaman": (s - timedelta(days=1)).isoformat(), "tur": "oneri", "durum": "oneri",
         "baslik": "Paçal okuması tek sorguya", "ozet": "Rakam değiştirebilir, onay gerekiyor."},
        {"id": 4, "zaman": (s - timedelta(days=1)).isoformat(), "tur": "ogrenme",
         "baslik": "Satışlar ölçümünü en az 5 iş günü sonra değerlendir", "ozet": "Hafta sonu ölçüm az."},
        {"id": 5, "zaman": (s - timedelta(days=2)).isoformat(), "tur": "gelisim", "durum": "bilgi",
         "baslik": "Haftalık karnem", "ozet": "3 iyileştirme, 2 birleşti; ortalama %-18."},
    ]
    hata = [{"id": 1, "zaman": s.isoformat(), "yer": "satis._stok_akilli_dus", "tur": "ValueError",
             "mesaj": "x", "kritik": False}]
    return {"bt_olcum": olc, "bt_rapor": rapor, "hata_kayitlari": hata}


def test_bilgi_islem_ornek_veriyle():
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    for t, rows in _veri().items():
        sahte_db.TABLOLAR[t] = rows
    n_once = len(sahte_db.TABLOLAR["bt_olcum"])
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "bilgi_islem"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["aktif_uygulama"] == "ekip"          # eski adres Ekip › Serkan'a yönlenir
    assert at.session_state["ekip_sayfa"] == "Serkan"
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Onayını bekleyen öneriler" in metin and "Paçal okuması tek sorguya" in metin
    assert "İyileştirmeler ve sonuçları" in metin and "En yavaş sayfalar" in metin
    assert "Serkan kendini geliştiriyor" in metin and "Son haftalık karnesi" in metin
    assert "1 öğrenme · 1 karne/geliştirme" in metin     # öğrendikleri tablosu st.html ile çizilir (AppTest okumaz)
    tablo = at.dataframe[0].value
    assert list(tablo["Durum"])[:1] == ["Otomatik birleşti"] and list(tablo["Fark"])[:1] == ["%-40,6"]
    import time
    time.sleep(0.5)                                     # ölçüm arka planda yazılır
    assert len(sahte_db.TABLOLAR["bt_olcum"]) > n_once
    assert sahte_db.TABLOLAR["bt_olcum"][-1]["modul"] == "ekip"

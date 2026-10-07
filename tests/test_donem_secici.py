# -*- coding: utf-8 -*-
"""Dönem seçici (Ekim 2026, "tek araç çubuğu" — kullanıcı seçimi A).

Eskiden 5 hap + "Diğer…" listesi + ‹ › + ayrı tarih yazısı iki satıra yayılıyordu. Artık tek düğme
[‹][Bu ay · 1–7 Eki ▾][›]: pencerede solda hazır dönemler, sağda takvim. Düğme yazısı dönemi ve
aralığı birlikte söyler; kaydırılmış ay adıyla görünür ("Eylül 2026").
"""
from datetime import date
from pathlib import Path

from shared import tarih as T

BUGUN = date(2026, 10, 7)
KOK = Path(__file__).resolve().parent.parent


def test_kisa_aralik():
    assert T.kisa_aralik(date(2026, 10, 1), BUGUN, BUGUN) == "1–7 Eki"
    assert T.kisa_aralik(date(2026, 9, 8), BUGUN, BUGUN) == "8 Eyl – 7 Eki"
    assert T.kisa_aralik(BUGUN, BUGUN, BUGUN) == "7 Eki"
    assert T.kisa_aralik(date(2025, 1, 1), date(2025, 12, 31), BUGUN) == "1 Oca – 31 Ara 2025"
    assert T.kisa_aralik(date(2025, 12, 1), date(2026, 1, 31), BUGUN) == "1 Ara 2025 – 31 Oca 2026"


def test_dugme_yazisi_donem_ve_aralik():
    b, e = T.donem_coz("Bu ay", 0, BUGUN)
    assert (b, e) == (date(2026, 10, 1), BUGUN)
    assert T.donem_etiketi("Bu ay", b, e, 0, BUGUN) == "Bu ay · 1–7 Eki"
    b, e = T.donem_coz("Son 30 gün", 0, BUGUN)
    assert T.donem_etiketi("Son 30 gün", b, e, 0, BUGUN) == "Son 30 gün · 8 Eyl – 7 Eki"


def test_oklar_ayi_adiyla_kaydirir():
    b, e = T.donem_coz("Bu ay", -1, BUGUN)
    assert (b, e) == (date(2026, 9, 1), date(2026, 9, 30))
    assert T.donem_etiketi("Bu ay", b, e, -1, BUGUN) == "Eylül 2026"
    b, e = T.donem_coz("Bu yıl", -1, BUGUN)
    assert T.donem_etiketi("Bu yıl", b, e, -1, BUGUN) == "2025"


def test_ozel_aralik_takvimden():
    assert T.donem_coz("Özel…", 0, BUGUN, ozel=(date(2026, 8, 3), date(2026, 8, 20))) == \
        (date(2026, 8, 3), date(2026, 8, 20))
    assert T.donem_coz("Özel…", 0, BUGUN, ozel=(date(2026, 8, 3),)) == (date(2026, 8, 3), date(2026, 8, 3))
    assert T.donem_coz("Özel…", 0, BUGUN) == (date(2026, 10, 1), BUGUN)       # takvim boşsa bu ay
    assert T.donem_etiketi("Özel…", date(2026, 8, 3), date(2026, 8, 20), 0, BUGUN) == "3–20 Ağu"


def test_min_tarih_altina_inmez():
    assert T.donem_coz("Bu yıl", 0, BUGUN, min_tarih=date(2026, 3, 1))[0] == date(2026, 3, 1)


def test_satislar_tek_arac_cubugu():
    s = (KOK / "satis/satislar_ekran.py").read_text(encoding="utf-8")
    i = s.index('st.container(key="k_cubuk_sat", horizontal=True')
    blok = s[i:s.index("siparisler = H.ara(", i)]
    for parca in ('hizli_tarih_araligi("l"', "st.text_input(", "st.segmented_control(", "B.filtre(st,"):
        assert parca in blok
    assert "st.columns([1.2, 3.0, 1.0]" not in s

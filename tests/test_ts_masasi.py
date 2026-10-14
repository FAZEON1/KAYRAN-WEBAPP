# -*- coding: utf-8 -*-
"""Teknik Servis listeleri ortak masada (Ekim 2026, tüm program yeni tasarım — teknikservis/ts_masasi.py).

Teknik Servis / İade listesi ve Depolar: süzgeç kuralları eski ekranla aynı (durum_uyar — 'sorunsuz' seçilince
sorunsuz GÖNDERİLMİŞLER de görünür), varsayılan sıra eskisiyle aynı (SLA kademesi en acil önce / depo sırası,
depo içinde son transfer), SLA rengi kademeden, satıra tıklayınca bugünkü sayfa içi ayrıntı (ts_ekran.sec),
'Toplu sat…' bugünkü Toplu Satış formunu seçilenlerle açar."""
import sys
from datetime import date
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from teknikservis import ts_masasi as M  # noqa: E402
from teknikservis.database import DURUMLAR  # noqa: E402
from shared import masa  # noqa: E402

BUGUN = date(2026, 10, 14)        # Salı
VATAN = "VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI"


def _k(i, durum, **x):
    d = {"id": i, "servis_form_no": f"G5F{i:05d}", "arayuz": "teknik", "stok_kodu": f"SK{i}", "stok_adi": f"Ürün {i}",
         "seri_no": f"SN{i}", "firma_bilgisi": VATAN, "musteri_adi": f"Müşteri {i}", "mevcut_durum": durum,
         "mal_kabul_tarihi": f"2026-09-{i:02d}T10:00:00", "fatura_mevcut": True}
    d.update(x)
    return d


KAYIT = [   # get_kayitlar sırası: id azalan (yeni → eski)
    _k(9, "teknisyende"),
    _k(8, "gönderildi", sonuc_durumu="sorunsuz"),
    _k(7, "mal kabül", fatura_mevcut=None, fatura_no=""),
    _k(6, "sorunsuz"),
    _k(5, "tamir edildi", firma_bilgisi="EERA ELEKTRONİK TİCARET VE BİLİŞİM HİZMETLERİ ANONİM ŞİRKETİ"),
    _k(4, "gönderildi", sonuc_durumu="ürün değişimi"),
]
GUN = {9: 3, 8: 12, 7: 18, 6: 4, 5: 12, 4: 30}


def test_durum_uyar_eski_kurallar():
    assert [k["id"] for k in KAYIT if M.durum_uyar(k, M.AKTIF)] == [9, 7, 5]
    assert [k["id"] for k in KAYIT if M.durum_uyar(k, "sorunsuz")] == [8, 6]      # gönderilmiş sorunsuz da
    assert [k["id"] for k in KAYIT if M.durum_uyar(k, "gönderildi")] == [8, 4]
    assert len([k for k in KAYIT if M.durum_uyar(k, M.TUMU)]) == 6
    assert M.fatura_var({"fatura_mevcut": None, "fatura_no": " F1 "}) and not M.fatura_var({"fatura_no": ""})
    assert M.ara_uyar(KAYIT[0], "sn9", M.TS_ARA_ALANLARI) and not M.ara_uyar(KAYIT[0], "SN8", M.TS_ARA_ALANLARI)


def test_kayit_masasi_sira_sla_ve_gorunumler():
    v = M.kayit_masa_verisi(KAYIT, GUN)
    r = {x["id"]: x for x in v["satirlar"]}
    # SLA kademesi en acil önce (16+ → 11–15 → 0–5 → Tamamlanan), kademe içinde gelen sıra (yeni → eski)
    assert [x["id"] for x in v["satirlar"]] == [7, 5, 9, 8, 6, 4]
    assert [x["sla_grup"] for x in v["satirlar"]] == ["16+ iş günü", "11–15 iş günü", "0–5 iş günü",
                                                      "Tamamlanan", "Tamamlanan", "Tamamlanan"]
    assert r[7]["_durum"] == {"ad": "18 iş günü", "renk": "kirmizi"} and r[5]["_durum"]["renk"] == "amber"
    assert r[9]["_durum"] == {"ad": "3 iş günü", "renk": "yesil"} and r[8]["_durum"] == {"ad": "tamamlandı", "renk": "silik"}
    assert r[7]["sla__s"] == 18 and r[7]["fatura_etk"] == "fatura yok" and r[9]["fatura_etk"] == ""
    assert r[8]["durum_m"] == "gönderildi · sorunsuz" and r[8]["sonuc_g"] == "sorunsuz" and r[6]["sonuc_g"] == ""
    assert r[9]["kabul_m"] == "09.09.2026" and r[9]["urun_alt"] == "SK9 · seri SN9 · Müşteri 9"
    assert r[9]["firma_m"] == "VATAN BILGISAYAR"
    gor = {g["k"]: g for g in v["gorunumler"]}
    assert v["gorunumler"][0]["ad"] == M.AKTIF                                   # varsayılan eskisi gibi
    uyan = lambda g: [x["id"] for x in v["satirlar"] if masa.kosul_uyar(x, gor[g]["f"])]   # noqa: E731
    assert uyan("aktif") == [7, 5, 9] and len(uyan("tum")) == 6
    i_sor = DURUMLAR.index("sorunsuz")
    assert sorted(uyan(f"d{i_sor}")) == [6, 8]
    assert f"d{DURUMLAR.index('hurda')}" not in gor                              # kaydı olmayan durum çip olmaz
    sec = {s["alan"]: [o["k"] for o in s["secenekler"]] for s in v["secimler"]}
    assert sec["sonuc_g"] == ["sorunsuz", "ürün değişimi"] and sec["fatura"] == ["Mevcut", "Yok"]
    assert len(sec["firma"]) == 2 and v["tik"] == "ac"


def test_kayit_tiki_kontrol_paneli_excel_secilenler():
    v = M.kayit_masa_verisi(KAYIT, GUN)
    acilan, durum = [], {}
    yurut = M.kayit_yurutucu("ts_teknik", "teknik", lambda on_ek, i: acilan.append((on_ek, i)), durum)
    t, h = masa.istek_al(v, {"islem": "ac", "ids": [5]})
    s = yurut(t)
    assert acilan == [("ts_teknik", 5)] and s["sessiz"] and s["onbellek"] is False
    t, h = masa.istek_al(v, {"islem": "excel", "ids": [5, 9]})
    assert h is None
    s = yurut(t)
    assert durum == {"_ts_excel_ids_teknik": [5, 9]} and s["ok"] and "2 kayıt" in s["mesaj"]
    t, h = masa.istek_al(v, {"islem": "ac", "ids": [5, 9]})
    assert t is None and "tek kayıt" in h
    t, h = masa.istek_al(dict(v, salt=True), {"islem": "ac", "ids": [5]})
    assert h is None                                                             # salt-okurda da açılır


# ── Depolar ─────────────────────────────────────────────────────────
DEPO = [
    _k(21, "satışa hazır", depo="outlet", depo_tarihi="2026-10-14T09:00:00", urun_grubu="monitör"),
    _k(22, "satıldı", depo="outlet", depo_tarihi="2026-10-12T09:00:00", satis_fiyati=120.5, satis_tarihi="2026-10-13",
       urun_grubu="monitör"),
    _k(23, "hurda", depo="hurda", depo_tarihi="2026-10-01T09:00:00", arayuz="iade"),
    _k(24, "satıldı", depo="ikinci el", depo_tarihi="", bedelsiz=True, arayuz="", fatura_mevcut=False),
    _k(25, "satışa hazır", depo="outlet", depo_tarihi="2026-10-14T09:00:00"),
]
TUM = DEPO + [_k(30, "teknisyende"), _k(31, "mal kabül")]
DEPOLAR = ["teknik servis", "iade", "outlet", "ikinci el", "hurda", "merkez"]
GIRIS = lambda k: "Depoya transfer"   # noqa: E731


def test_depo_ozeti_donemler():
    oz = {k["k"]: k["dg"] for k in M.depo_ozeti(TUM, BUGUN)}
    assert oz == {"bugun": "2 adet", "hafta": "3 adet", "ay": "4 adet", "aktif": "2 adet", "toplam": "4 adet"}


def test_depo_masasi_sira_grup_ve_satis():
    v = M.depo_masa_verisi(DEPO, TUM, DEPOLAR, BUGUN, GIRIS)
    r = {x["id"]: x for x in v["satirlar"]}
    # depo sırası (outlet → ikinci el → hurda), depo içinde son transfer üstte, eşitlikte büyük id
    assert [x["id"] for x in v["satirlar"]] == [25, 21, 22, 24, 23]
    assert [x["depo_ad"] for x in v["satirlar"]] == ["Outlet", "Outlet", "Outlet", "İkinci el", "Hurda"]
    assert r[22]["satis_m"] == "$120,50" and r[22]["satis_alt"] == "13.10.2026" and r[24]["satis_m"] == "bedelsiz"
    assert r[21]["satis_m"] == "" and r[21]["hazir"] == 1 and r[22]["hazir"] == 0
    assert r[22]["_durum"] == {"ad": "satıldı", "renk": "mor"} and r[23]["_durum"]["renk"] == "kirmizi"
    assert r[23]["kaynak"] == "İade" and r[24]["kaynak"] == "evraksız" and r[24]["fatura"] == "Yok"
    assert r[24]["transfer_m"] == "24.09.2026"                                  # transfer yok → mal kabul
    assert v["grup"]["toplamlar"] == [{"alan": "hazir", "ondalik": 0, "son": " satışa hazır"}]
    gor = {g["ad"]: g["f"] for g in v["gorunumler"]}
    assert [x["id"] for x in v["satirlar"] if masa.kosul_uyar(x, gor["Satıldı"])] == [22, 24]


def test_depo_toplu_satis_ve_ac(monkeypatch):
    v = M.depo_masa_verisi(DEPO, TUM, DEPOLAR, BUGUN, GIRIS)
    acilan, durum = [], {}
    yurut = M.depo_yurutucu(DEPO, lambda on_ek, i: acilan.append((on_ek, i)), durum)
    t, h = masa.istek_al(v, {"islem": "sat", "ids": [21, 22]})
    assert t is None and "uygun değil" in h                                     # satılmış ürün satılamaz
    t, h = masa.istek_al(v, {"islem": "sat", "ids": [21, 25, 23]})
    assert h is None
    s = yurut(t)
    assert s == {"ok": True, "mesaj": "", "yenileme": False, "sessiz": True}
    assert durum[M.TOPLU_AC] is True
    assert durum["ts_toplu_sec"] == [M.toplu_etiket({k["id"]: k for k in DEPO}[i]) for i in (21, 25, 23)]
    assert durum["ts_toplu_sec"][0] == "G5F00021 · SK21 · Ürün 21 · Seri SN21 · [outlet]"
    t, h = masa.istek_al(v, {"islem": "ac", "ids": [24]})
    yurut(t)
    assert acilan == [("ts_depo", 24)]
    t, h = masa.istek_al(dict(v, salt=True), {"islem": "sat", "ids": [21]})
    assert t is None and "Salt-okur" in h


def test_toplu_etiket_eski_expander_ile_ayni():
    """Eski expander'daki _ts_etiket ile aynı metin (multiselect seçenekleri değişmesin)."""
    src = (KOK / "teknikservis/ts_masasi.py").read_text(encoding="utf-8")
    assert "f'{(k.get(\"stok_adi\") or \"\")[:32]} · Seri {k.get(\"seri_no\",\"\")} '" in src


def test_ekran_bayraklari_ve_ayni_kod_yolu():
    m = (KOK / "teknikservis/main.py").read_text(encoding="utf-8")
    assert "TS_MASASI_YENI = True" in m and "DEPO_MASASI_YENI = True" in m
    assert "if TS_MASASI_YENI:\n        _liste_masa(" in m and "if DEPO_MASASI_YENI:\n        _depolar_masa(kayitlar)" in m
    # Toplu Satış: eski expander ve yeni pencere AYNI fonksiyonu çağırır
    assert "_toplu_satis_formu(_satilabilir, st.rerun)" in m and "_toplu_satis_formu(satilabilir, _rerun_app)" in m
    assert m.count("def _toplu_satis_formu(") == 1 and m.count('key="ts_toplu_btn"') == 1
    # eski liste yolu duruyor
    assert "E.kayit_listesi(_gruplar, _g_of, _bitmis_of, _fatura_var, on_ek)" in m
    assert 'E.depo_listesi(goster, DEPOLAR, "ts_depo")' in m
    # masadan sonra: seçilenlerin Excel'i ve toplu satış penceresi
    i = m.index("def _depolar_masa(")
    blok = m[i:m.index("\ndef ", i + 10)]
    assert "_TM.depo_yurutucu(goster, E.sec, st.session_state)" in blok and "_dlg_toplu_satis(" in blok
    assert "_ozet_kirilim(donemsel, aktif, donem)" in blok


@pytest.mark.parametrize("istek, parca", [
    ({"islem": "sil", "ids": [21]}, "Bilinmeyen"),
    ({"islem": "ac", "ids": [99]}, "bulunamadı"),
])
def test_depo_gecersiz_istek(istek, parca):
    t, h = masa.istek_al(M.depo_masa_verisi(DEPO, TUM, DEPOLAR, BUGUN, GIRIS), istek)
    assert t is None and parca in h

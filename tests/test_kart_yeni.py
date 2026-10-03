# -*- coding: utf-8 -*-
"""Sayı kartları — tek görünüm, renk yalnız anlam taşıdığında (Ekim 2026)."""
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _t():
    from shared import tasarim
    return tasarim


# ── Renk → anlam ────────────────────────────────────────────────────
def test_renk_anlama_coz():
    T = _t()
    assert T.kart_anlami("kirmizi") == "kotu"
    assert T.kart_anlami(T.RENK["kirmizi"]) == "kotu"           # trenk("kirmizi") hex'i
    assert T.kart_anlami("#EF4444") == "kotu"                   # eski sabit hex
    for r in ("mor", "yesil", "amber", "cyan", "mavi", T.RENK["yesil"], "#10B981", None, ""):
        assert T.kart_anlami(r) is None, r


def test_acik_tema_hexi_de_cozulur():
    T = _t()
    assert T.kart_anlami(T.TEMALAR["acik"]["kirmizi"]) == "kotu"


# ── Değişim rozeti ──────────────────────────────────────────────────
def test_degisim_rozeti():
    T = _t()
    assert T.degisim_rozeti(3, 5) == ("▼ %40,0", "kotu")
    assert T.degisim_rozeti(6, 5) == ("▲ %20,0", "iyi")
    assert T.degisim_rozeti(6, 5, artis_iyi=False) == ("▲ %20,0", "kotu")   # gider artışı
    assert T.degisim_rozeti(5, 5) == ("■ %0,0", None)
    assert T.degisim_rozeti(5, 0) is None and T.degisim_rozeti(5, None) is None


# ── Kart HTML'i ─────────────────────────────────────────────────────
def test_renk_degere_boyanmaz_serit_yok():
    T = _t()
    h = T.kart_hucresi({"etiket": "Stok değeri", "deger": "$1.200", "renk": "amber"})
    assert "border-left-color" not in h and "color:var(--k-amber)" not in h
    assert 'class="k-kart k-yeni"' in h


def test_kirmizi_kotu_anlami_tasir():
    T = _t()
    h = T.kart_hucresi({"etiket": "Gecikmiş", "deger": "4", "renk": "kirmizi"})
    assert "k-kotu" in h


def test_acik_anlam_onceligi():
    T = _t()
    h = T.kart_hucresi({"etiket": "Net kâr", "deger": "$5", "renk": "kirmizi", "anlam": "iyi"})
    assert "k-iyi" in h and "k-kotu" not in h


def test_vurgu_rozet_ve_spark():
    T = _t()
    h = T.kart_hucresi({"etiket": "Haftalık satış", "deger": "3", "vurgu": True,
                        "simdi": 3, "onceki": 5, "seri": [4, 6, 5, 3]})
    assert "k-vurgu" in h and "▼ %40,0" in h and "k-rozet k-kotu" in h and "<svg" in h


def test_etiket_cumle_duzeni_ve_kacis():
    T = _t()
    h = T.kart_hucresi({"etiket": "TOPLAM STOK", "deger": "<b>9</b>"})
    assert "Toplam stok" in h                     # kpi_etiketi: BÜYÜK HARF → cümle düzeni
    assert "<b>9</b>" in h                         # değer HTML olabilir (eski sözleşme), kaçışlanmaz


def test_spark_bos_seride_cizilmez():
    T = _t()
    assert T.spark_svg([]) == "" and T.spark_svg([5]) == ""
    assert T.spark_svg([1, 2, 3]).startswith("<svg")


# ── Bağlantılar ─────────────────────────────────────────────────────
def test_geri_alma_anahtari_tek_satir():
    src = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^KART_YENI = (True|False)\s", src, re.M)) == 1


def test_ortak_kartlar_yeni_hucreyi_kullanir():
    u = (KOK / "shared" / "utils.py").read_text(encoding="utf-8")
    g = u[u.index("def metrik_satiri"):]
    g = g[:g.index("\ndef ", 10)]
    assert "kart_hucresi(" in g
    t = (KOK / "shared" / "tasarim.py").read_text(encoding="utf-8")
    g = t[t.index("def kpi_serit"):]
    g = g[:g.index("\ndef ", 10)]
    assert "kart_hucresi(" in g


def test_yerel_kartlar_ortak_hucrede():
    for d in ("satis/main.py", "kayranpm/stok_karti.py"):
        src = (KOK / d).read_text(encoding="utf-8")
        g = src[src.index("def _kart("):]
        g = g[:g.index("\ndef ", 10)]
        assert "kart_hucresi(" in g, d
    # Eski çizim yalnız KART_YENI = False iken kalır; yeni yol büyük harf CSS'i kullanmaz
    from shared.tasarim import kart_hucresi
    assert "uppercase" not in kart_hucresi({"etiket": "Bizim stok", "deger": "1"})


def test_sus_kirmizisi_notr():
    """Kırmızı her yerde sorun değil: paçal maliyet, borç, harcama… her durumda
    kırmızı boyanıyordu. anlam='notr' yeni görünümde rengi kaldırır (eski yol aynı)."""
    T = _t()
    assert "k-kotu" not in T.kart_hucresi({"etiket": "Paçal", "deger": "$0", "renk": "kirmizi", "anlam": "notr"})
    for d, metin in (("kayranpm/stok_karti.py", '"Paçal Maliyet"'), ("kayranpm/ref_no.py", '"Toplam Harcama"'),
                     ("kayranacc/main.py", '"label": "Borç"'), ("kayranacc/cari_ekstre.py", '"📤 Açık Borç (TL)"'),
                     ("kayranacc/odeme_ekran.py", '"En çok ertelenen"')):
        src = (KOK / d).read_text(encoding="utf-8")
        i = src.index(metin)
        assert 'anlam="notr"' in src[i:i + 200] or '"anlam": "notr"' in src[i:i + 200], (d, metin)


# ── 3. adım: ana kartlar ────────────────────────────────────────────
def test_rozet_disaridan_verilebilir():
    """Patron panosunda marj farkı yüzde değil 'puan' — rozet hazır verilir."""
    T = _t()
    h = T.kart_hucresi({"etiket": "Marj", "deger": "%19,2", "rozet": ("▲ 1,4 puan", "iyi")})
    assert "▲ 1,4 puan" in h and "k-rozet k-iyi" in h


def test_genel_bakis_kpi_seri_tasir():
    from kayranpm.genel_hesap import kpi
    seri = [(f"H{i}", v) for i, v in enumerate([2, 3, 4, 5, 6, 7, 8, 9, 5, 3])]
    k = kpi([], seri, None)
    assert k["seri"] == [4, 5, 6, 7, 8, 9, 5, 3]          # son 8 hafta
    assert k["hafta_satis"] == 3 and k["onceki_satis"] == 5


def test_genel_bakis_ana_kart_haftalik_satis():
    src = (KOK / "kayranpm" / "genel_bakis.py").read_text(encoding="utf-8")
    g = src[src.index("def _kartlar"):]
    g = g[:g.index("\ndef ", 10)]
    i = g.index('"Haftalık satış"')
    assert i < g.index('"Toplam stok"')                         # ana kart solda
    blok = g[i:i + 400]
    assert '"vurgu": True' in blok and '"onceki"' in blok and '"seri"' in blok


def test_satis_girisi_onceki_ay_ayni_gun():
    from satis.satis_hesap import onceki_ay_araligi
    from datetime import date
    assert onceki_ay_araligi(date(2026, 10, 3)) == (date(2026, 9, 1), date(2026, 9, 3))
    assert onceki_ay_araligi(date(2026, 3, 31)) == (date(2026, 2, 1), date(2026, 2, 28))   # kısa ay
    assert onceki_ay_araligi(date(2026, 1, 15)) == (date(2025, 12, 1), date(2025, 12, 15))


def test_satis_girisi_ana_kart():
    src = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    g = src[src.index("def _sg_acilis"):]
    g = g[:g.index("\ndef ", 10)]
    i = g.index('"Bu ay ciro"')
    assert i < g.index('"etiket": "Bugün"')
    assert '"vurgu": True' in g[i:i + 500] and '"onceki"' in g[i:i + 500]
    assert "onceki_ay_araligi(" in g


def test_pnl_net_kar_ana_kart_anlamli():
    src = (KOK / "satis" / "main.py").read_text(encoding="utf-8")
    i = src.index("# ── Üst şerit: yalnız 4 ana gösterge ──")
    g = src[i:i + 1400]
    assert g.index('"NET KÂR"') < g.index('"NET CİRO"')
    assert '"vurgu": True' in g and '"anlam": _anlam' in g


def test_patron_ortak_kart():
    src = (KOK / "shared" / "patron.py").read_text(encoding="utf-8")
    g = src[src.index("def kart_html"):]
    g = g[:g.index("\ndef ", 10)]
    assert "kart_hucresi(" in g and "KART_YENI" in g


# ── Muhasebe › Genel bakış ──────────────────────────────────────────
def _ozet(**kw):
    from kayranacc.genel_kartlar import haftalik_ozet_kartlari
    v = dict(tl_toplam=100000, odendi_tl=40000, usd_toplam=2000, kur=40.0, odendi_cnt=3, toplam_cnt=5,
             bekleyen_tl=60000, hafta_sonu_tl=25000, fmt=lambda x: f"{x:,.0f}".replace(",", "."))
    v.update(kw)
    return haftalik_ozet_kartlari(**v)


def test_muhasebe_ana_kart_nakit():
    k = _ozet()
    assert k[0]["label"] == "Hafta sonu kalan" and k[0]["vurgu"] is True
    assert k[0]["value"] == "₺25.000" and k[0].get("anlam") is None


def test_muhasebe_nakit_acigi_kirmizi():
    k = _ozet(hafta_sonu_tl=-12000)
    assert k[0]["label"] == "Nakit açığı" and k[0]["value"] == "₺12.000" and k[0]["anlam"] == "kotu"


def test_muhasebe_ilerleme_cubugu_alt_satirda():
    k = {c["label"]: c for c in _ozet()}
    assert "3 / 5" in k["İlerleme"]["value"] and "%60" in k["İlerleme"]["alt"] and "width:60%" in k["İlerleme"]["alt"]


def test_muhasebe_genel_bakis_ortak_kart():
    src = (KOK / "kayranacc" / "main.py").read_text(encoding="utf-8")
    i = src.index('if sayfa == "📊 Dashboard":')
    g = src[i:i + 12000]
    assert "haftalik_ozet_kartlari(" in g and "KART_YENI" in g

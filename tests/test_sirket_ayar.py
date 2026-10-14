# -*- coding: utf-8 -*-
"""shared/sirket_ayar.py — kişiye bağlı roller ve şirket kimliği tek kaynakta.

Kural: veritabanı yokken / rol etiketi verilmemişken davranış BUGÜNKÜYLE AYNI
(ibrahim görür, başkası görmez); rol veritabanından gelince başka kullanıcıya geçer;
okuma hatasında varsayılan.
"""
import re
from datetime import date
from pathlib import Path

import pytest

import shared.sirket_ayar as SA
import shared.yetki as Y

KOK = Path(__file__).resolve().parent.parent


def _kayit(*ozel, aktif=True):
    return {"moduller": [], "ozel": sorted(ozel), "salt_okur": False, "aktif": aktif}


@pytest.fixture
def ortam(monkeypatch):
    """Veritabanı durumunu sahteler: tablo (dict|None|hata) ve sistem_ayarlari (dict|hata)."""
    durum = {"tablo": None, "ayar": {}}

    def _tablo():
        t = durum["tablo"]
        if isinstance(t, Exception):
            raise t
        return t

    def _get_ayar(anahtar, varsayilan=None):
        a = durum["ayar"]
        if isinstance(a, Exception):
            raise a
        return a.get(anahtar, varsayilan)

    import kayranacc.database as KD
    monkeypatch.setattr(Y, "yetki_tablosu", _tablo)
    monkeypatch.setattr(KD, "get_ayar", _get_ayar)
    SA.temizle()
    yield durum
    SA.temizle()


def _yenile():
    SA.temizle()


# ── 1) Varsayılan = bugünkü davranış (veritabanı yok) ────────────────────
def test_varsayilan_kar(ortam):
    from shared.kar_gizle import kar_gorunur_kullanici
    assert kar_gorunur_kullanici("ibrahim") is True
    assert kar_gorunur_kullanici("IBRAHIM ") is True
    for k in ("gokhan", "derya", "serkan", ""):
        assert kar_gorunur_kullanici(k) is False, k


def test_varsayilan_talep_onay(ortam):
    from shared.claude_talep import onaylayabilir_mi, pr_mailleri
    assert onaylayabilir_mi("ibrahim") is True
    assert onaylayabilir_mi("derya") is False
    assert onaylayabilir_mi("derya", lambda k, a: a == "claude_onay") is True    # özel yetki yolu aynı
    m = pr_mailleri({"id": 1, "konu": "X"}, "pr_hazir", "https://ornek/pr/1")
    assert [x[0] for x in m] == ["ibrahim"]


def test_varsayilan_yonetici_ve_eskalasyon(ortam):
    from shared.eposta import hatirlatma_mailleri, YONETICI
    assert YONETICI == "ibrahim" and SA.yonetici_kullanici() == "ibrahim"
    d = {"anahtar": "a", "ad": "A", "sorumlu": "serdar", "sorumlu_ad": "Serdar", "modul": "kayranpm",
         "sayfa": "S", "seviye": "gecikti", "kalan_gun": None, "gecikme_gun": 8,
         "eksik_adlar": ["Hafta 39"], "siklik": "haftalik", "sonraki_adi": "Hafta 40", "vade_metni": "05.10"}
    adr = {"serdar": "s@x.com", "ibrahim": "i@x.com", "derya": "d@x.com"}
    p = hatirlatma_mailleri([d], date(2026, 10, 1), adr)[0]
    assert p["cc"] == ["i@x.com"]
    assert hatirlatma_mailleri([d], date(2026, 10, 1), adr, yonetici="derya")[0]["cc"] == ["d@x.com"]


def test_varsayilan_marj_alicilari(ortam):
    import shared.marj_uyari as M
    assert M.MAIL_ALICILARI == ("ibrahim", "korkut", "serkan")
    assert M.mail_alicilari() == ["ibrahim", "korkut", "serkan"]


def test_varsayilan_yukleme_sorumlulari(ortam):
    import shared.yukleme_takvimi as YT
    beklenen = {"musteri_haftalik": "derya", "satis_dokumu": "", "aktif_stok": "serdar",
                "aktif_ithalat": "serdar", "aktif_cari": "serdar", "odeme_listesi": "serdar",
                "happylife": "samet", "gider_tablosu": "serdar", "g5f_sayim": "gokhan"}
    assert {k["anahtar"]: k["sorumlu"] for k in YT.KAYNAKLAR} == beklenen
    assert {a: YT.kaynak_ayari(a, {})["sorumlu"] for a in beklenen} == beklenen
    assert YT.sorumlu_adi("ibrahim") == "İbrahim"          # SORUMLU_AD'dan çıkarıldı, sonuç aynı


def test_varsayilan_finans_ve_yonetici_rolu(ortam):
    for rol in (SA.ROL_KAR, SA.ROL_YONETICI, SA.ROL_TALEP_ONAY):
        assert SA.rol_var_mi("ibrahim", rol) is True
        assert SA.rol_var_mi("korkut", rol) is False
        assert SA.rol_var_mi("", rol) is False


def test_varsayilan_kimlik(ortam):
    assert SA.talep_eposta() == "ibrahim.kayran@g5fteknoloji.com"
    assert SA.sirket_kisa_ad() == "KAYRAN" and SA.sirket_ad() == "KAYRAN ELEKTRONİK"


# ── 2) Tablo var ama rol etiketi yok (tohum kurulmamış) → bugünkü gibi ──────
def test_etiketsiz_tablo_bugunku_gibi(ortam):
    ortam["tablo"] = {"ibrahim": _kayit("patron_panel", "yonetim"), "gokhan": _kayit("kar"),
                      "derya": _kayit()}
    from shared.kar_gizle import kar_gorunur_kullanici
    from shared.claude_talep import onaylayabilir_mi
    assert kar_gorunur_kullanici("ibrahim") and kar_gorunur_kullanici("gokhan")   # 'kar' özel yetkisi korunur
    assert not kar_gorunur_kullanici("derya")
    assert onaylayabilir_mi("ibrahim") and not onaylayabilir_mi("gokhan")
    assert SA.yonetici_kullanici() == "ibrahim"
    assert SA.rol_var_mi("ibrahim", SA.ROL_KAR) and not SA.rol_var_mi("gokhan", SA.ROL_KAR)


# ── 3) Rol veritabanından gelince başka kullanıcıya geçer ──────────────────
def test_rol_dbden_baska_kullaniciya_gecer(ortam):
    ortam["tablo"] = {
        "ibrahim": _kayit(),
        "derya": _kayit(SA.ROL_KAR, SA.ROL_TALEP_ONAY, SA.ROL_YONETICI, SA.ROL_MARJ_UYARI,
                        SA.yukleme_rolu("aktif_stok")),
        "cem": _kayit(SA.ROL_MARJ_UYARI, aktif=False),                     # pasif sayılmaz
    }
    from shared.kar_gizle import kar_gorunur_kullanici
    from shared.claude_talep import onaylayabilir_mi, pr_mailleri
    import shared.marj_uyari as M
    import shared.yukleme_takvimi as YT
    assert kar_gorunur_kullanici("derya") and not kar_gorunur_kullanici("ibrahim")
    assert onaylayabilir_mi("derya") and not onaylayabilir_mi("ibrahim")
    assert [x[0] for x in pr_mailleri({"id": 1, "konu": "X"}, "pr_hazir", "u")] == ["derya"]
    assert SA.yonetici_kullanici() == "derya"
    assert M.mail_alicilari() == ["derya"]
    assert YT.kaynak_ayari("aktif_stok", {})["sorumlu"] == "derya"
    assert YT.kaynak_ayari("aktif_cari", {})["sorumlu"] == "serdar"           # etiket yok → varsayılan
    # Takvim ayarları ekranında kayıtlı sorumlu her zaman kazanır (bugünkü davranış)
    assert YT.kaynak_ayari("aktif_stok", {"aktif_stok": {"sorumlu": "samet"}})["sorumlu"] == "samet"


def test_yetki_tablosu_rol_etiketlerini_korur(monkeypatch):
    """yetki_tablosu ozel'i OZEL ile süzer — yeni etiketler süzgeçte kaybolmamalı."""
    class _Sorgu:
        def select(self, *_a, **_k):
            return self

        def execute(self):
            class R:
                data = [{"kullanici": "derya", "moduller": [], "aktif": True, "salt_okur": False,
                         "ozel": ["kar_gorur", "yukleme_sorumlusu:aktif_stok", "uydurma"]}]
            return R()

    class _Sb:
        def table(self, _t):
            return _Sorgu()

    monkeypatch.setattr(Y, "_supabase", lambda: _Sb())
    t = Y.yetki_tablosu()
    assert t["derya"]["ozel"] == ["kar_gorur", "yukleme_sorumlusu:aktif_stok"]


# ── 4) sistem_ayarlari yedeği ─────────────────────────────────────────────
def test_sistem_ayarlari_yedegi(ortam):
    ortam["tablo"] = {"ibrahim": _kayit()}                                   # etiket yok
    ortam["ayar"] = {"rol_kar_gorur": ["Korkut"], "sirket_yonetici_kullanici": "serkan",
                     "rol_yukleme_sorumlusu:happylife": "derya", "sirket_talep_eposta": "a@b.com",
                     "sirket_kisa_ad": "ACME"}
    _yenile()
    import shared.yukleme_takvimi as YT
    assert SA.rol_var_mi("korkut", SA.ROL_KAR) and not SA.rol_var_mi("ibrahim", SA.ROL_KAR)
    assert SA.yonetici_kullanici() == "serkan"
    assert YT.kaynak_ayari("happylife", {})["sorumlu"] == "derya"
    assert SA.talep_eposta() == "a@b.com" and SA.sirket_kisa_ad() == "ACME"
    assert SA.rol_var_mi("ibrahim", SA.ROL_TALEP_ONAY)                       # ayarı olmayan rol → varsayılan


def test_etiket_sistem_ayarini_ezer(ortam):
    ortam["tablo"] = {"cem": _kayit(SA.ROL_YONETICI)}
    ortam["ayar"] = {"sirket_yonetici_kullanici": "serkan"}
    _yenile()
    assert SA.yonetici_kullanici() == "cem"


# ── 5) Veritabanı hatası → varsayılan ─────────────────────────────────────
def test_db_hatasinda_varsayilan(ortam):
    ortam["tablo"] = RuntimeError("bağlantı yok")
    ortam["ayar"] = RuntimeError("bağlantı yok")
    _yenile()
    from shared.kar_gizle import kar_gorunur_kullanici
    from shared.claude_talep import onaylayabilir_mi
    import shared.marj_uyari as M
    import shared.yukleme_takvimi as YT
    assert kar_gorunur_kullanici("ibrahim") and not kar_gorunur_kullanici("gokhan")
    assert onaylayabilir_mi("ibrahim") and not onaylayabilir_mi("derya")
    assert SA.yonetici_kullanici() == "ibrahim"
    assert M.mail_alicilari() == ["ibrahim", "korkut", "serkan"]
    assert YT.kaynak_ayari("g5f_sayim", {})["sorumlu"] == "gokhan"
    assert SA.talep_eposta() == "ibrahim.kayran@g5fteknoloji.com"


def test_ayar_hatasi_kisa_sure_saklanir(ortam, monkeypatch):
    """Veritabanı yokken her kar_gorunur çağrısı yeni istek atmasın."""
    import kayranacc.database as KD
    sayac = {"n": 0}

    def _say(anahtar, varsayilan=None):
        sayac["n"] += 1
        raise RuntimeError("yok")

    monkeypatch.setattr(KD, "get_ayar", _say)
    _yenile()
    for _ in range(20):
        SA.rol_sahipleri(SA.ROL_KAR)
    assert sayac["n"] == 1


# ── 6) Seçenek listesi ve yedek listeler ──────────────────────────────────
def test_yetki_ekrani_secenekleri():
    for rol in SA.ROLLER:
        assert rol in Y.OZEL and Y.OZEL_ADI[rol]
    import shared.yukleme_takvimi as YT
    for k in YT.KAYNAKLAR:
        r = SA.yukleme_rolu(k["anahtar"])
        assert r in Y.OZEL and k["ad"] in Y.OZEL_ADI[r]
    assert len(Y.OZEL) == len(set(Y.OZEL))
    for eski in ("yonetim", "patron_panel", "kar", "claude_onay", "kullanici_yonetimi"):
        assert eski in Y.OZEL                                                # eskiler yerinde


def test_yukleme_varsayilanlari_kaynaklarla_ayni_anahtarlar():
    import shared.yukleme_takvimi as YT
    assert set(SA.VARSAYILAN_YUKLEME) == {k["anahtar"] for k in YT.KAYNAKLAR}


def test_app_yedek_listeleri_eskisiyle_ayni():
    """app.py'nin eski sabit kümeleri (origin/main, Ekim 2026) — taşıma birebir."""
    eski = {
        "kayranacc": {"ibrahim", "derman", "cem", "pamuk", "serkan", "yilmaz", "korkut", "caglar", "serdar"},
        "kayranpm": {"ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"},
        "hesap_makinesi": {"ibrahim"},
        "ithalat": {"ibrahim", "kemal", "serkan", "derya", "gokhan", "korkut", "caglar", "cem", "pamuk", "serdar"},
        "teknikservis": {"ibrahim", "berkay", "gokhan", "cem", "pamuk", "derya", "samet", "serkan", "korkut",
                         "serdar"},
        "satis": {"ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"},
        "depo_ek": {"samet", "berkay", "selcuk", "serdar"},
        "yonetim": {"ibrahim", "korkut", "serkan", "caglar", "cem"},
        "patron_panel": {"ibrahim"},
        "kullanici_yonetimi": {"ibrahim"},
    }
    for ad, kume in eski.items():
        assert SA.yedek_liste(ad) == kume, ad
    a = SA.yedek_liste("yonetim")
    a.add("x")
    assert "x" not in SA.yedek_liste("yonetim")                              # her çağrı yeni küme


# ── 7) Tohum SQL'i: idempotent ve varsayılanlarla aynı kişiler ─────────────
def test_tohum_sql_varsayilanlarla_ayni():
    s = (KOK / "veritabani" / "32_sirket_ayarlari.sql").read_text(encoding="utf-8")
    atamalar = set(re.findall(r"array_append\([^)]*\), '([\w:]+)'\).*?\n\s*WHERE kullanici = '(\w+)' "
                              r"AND NOT \('\1' = ANY", s))
    beklenen = {(r, k) for r, ks in SA.VARSAYILAN_ROLLER.items() for k in ks}
    beklenen |= {(SA.yukleme_rolu(a), k) for a, k in SA.VARSAYILAN_YUKLEME.items() if k}
    assert atamalar == beklenen
    calisan = [x for x in s.splitlines() if x.startswith("UPDATE kullanici_yetkileri")]   # yorum değil
    assert len(calisan) == len(beklenen)                                     # her UPDATE "yoksa" koşullu
    assert "ON CONFLICT (anahtar) DO NOTHING" in s
    for alan, anahtar in SA.KIMLIK_ANAHTARI.items():
        assert f"'{anahtar}'" in s and f'\'"{SA.VARSAYILAN_KIMLIK[alan]}"\'' in s


# ── 8) Kişi adı artık yalnız sirket_ayar.py varsayılanlarında ve tohum SQL'inde ──
_SAHIP_DOSYALAR = ("shared/kar_gizle.py", "shared/claude_talep.py", "shared/eposta.py",
                   "shared/marj_uyari.py", "shared/yukleme_takvimi.py", "shared/yetki.py")


@pytest.mark.parametrize("dosya", _SAHIP_DOSYALAR)
def test_ibrahim_kodda_gomulu_degil(dosya):
    s = (KOK / dosya).read_text(encoding="utf-8")
    assert not re.search(r"ibrahim|İbrahim", s, re.I), dosya


def test_app_yetki_bolgeleri_kisi_adi_icermez():
    s = (KOK / "app.py").read_text(encoding="utf-8")
    blok = re.search(r"# YETKİ TANIMLARI.*?\ndef salt_okur_mu", s, re.S).group(0)
    assert "ibrahim" not in blok
    assert not re.search(r'^TALEP_ALICI\s*=.*ibrahim', s, re.M)
    assert not re.search(r'lower\(\)\s*==\s*"ibrahim"', s)
    u = (KOK / "shared" / "utils.py").read_text(encoding="utf-8")
    assert 'kullanici == "ibrahim"' not in u

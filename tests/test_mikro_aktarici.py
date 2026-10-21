# -*- coding: utf-8 -*-
"""Mikro → KAYRAN aktarıcı (araclar/mikro_aktarici, Ekim 2026).

Kullanıcı kararı: sunucu 10.0.1.11'de çalışır, 15 dakikada bir artımlı, gecede bir tam aktarım, Python 3.11+.
Aktarıcı Mikro'ya hiçbir şey yazmaz: yalnız SqlVeriOkuV2 (SELECT) kullanır."""
import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

KLASOR = Path(__file__).resolve().parent.parent / "araclar" / "mikro_aktarici"


@pytest.fixture()
def mk(monkeypatch, tmp_path):
    if importlib.util.find_spec("requests") is None:   # CI'da requests kurulu olmayabilir: modül yalnız içe aktarılır
        sahte = types.ModuleType("requests")
        sahte.Session = object
        sahte.RequestException = Exception
        sahte.Response = object
        monkeypatch.setitem(sys.modules, "requests", sahte)
    spec = importlib.util.spec_from_file_location("mikro_kayran_test", KLASOR / "mikro_kayran.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "KILIT", str(tmp_path / "aktarim.kilit"), raising=False)
    return m


def test_mikroya_yalniz_okuma(mk):
    """Bütün sorgular SELECT; yazan bir Mikro uç noktası (Kaydet / Sil / Guncelle) çağrılmaz."""
    for ad, t in mk.SORGULAR.items():
        sql = " ".join(t["sql"].split()).upper()
        assert sql.startswith("SELECT "), ad
        assert not re.search(r"\b(UPDATE|DELETE|INSERT|MERGE|DROP|ALTER|EXEC|TRUNCATE)\b", sql), ad
    kod = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8")
    assert mk.MikroIstemci.SQL_ENDPOINT.endswith("/SqlVeriOkuV2")
    assert not re.search(r"(Kaydet|Sil|Guncelle|Duzelt)V\d", kod)


def test_zamanlama_kullanici_karari(mk):
    assert getattr(mk, "ARALIK_SN", 120) == 900                        # 15 dakika (eskiden 120 sn)
    gorev = (KLASOR / "gorev_kur.bat").read_text(encoding="ascii")
    assert "/SC MINUTE /MO 15" in gorev
    assert '/SC DAILY /ST 03:00' in gorev and 'zamanli.bat\\" tam"' in gorev
    z = (KLASOR / "zamanli.bat").read_text(encoding="ascii")
    assert "--tam --bir-kez" in z and "mikro_kayran.py --bir-kez" in z and "pause" not in z
    assert "localhost:8094" in (KLASOR / "ayarlar_ornek.bat").read_text(encoding="ascii")   # sunucuda çalışır


def test_python_surum_ve_saat_dilimi(mk):
    kod = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8")
    assert "if sys.version_info < (3, 11):" in kod
    # Windows'ta tzdata yoksa ZoneInfo çöker: sabit +03:00'e düşer
    assert mk.TZ.utcoffset(mk.datetime(2026, 7, 1)).total_seconds() == 3 * 3600
    assert mk.TZ.utcoffset(mk.datetime(2026, 1, 1)).total_seconds() == 3 * 3600


def test_kilit_ust_uste_binmez(mk):
    assert hasattr(mk, "kilit_al"), "kilit yok: 15 dakikalık tur ile gecelik tam aktarım üst üste biner"
    assert mk.kilit_al() is True
    assert mk.kilit_al() is False             # 15 dakikalık tur, gecelik tam aktarım sürerken atlanır
    mk.kilit_birak()
    assert mk.kilit_al() is True
    mk.kilit_birak()


def test_bos_ayar_ve_yer_tutucu(mk):
    assert hasattr(mk, "_bos_mu"), "yer tutucu (<...>) dolu sayılıyordu"
    assert mk._bos_mu("") and mk._bos_mu(None) and mk._bos_mu("<Mikro ApiKey>")
    assert not mk._bos_mu("abc123")
    a = dict(mk.AYARLAR, api_key="<Mikro ApiKey>", firma_kodu="G5F", kullanici="api", sifre="x")
    with pytest.raises(mk.MikroHata, match="api_key"):
        mk.MikroIstemci(a)


def test_gizli_ayar_depoda_yok():
    gi = (KLASOR.parent.parent / ".gitignore").read_text(encoding="utf-8")
    assert "araclar/mikro_aktarici/ayarlar.bat" in gi
    ornek = (KLASOR / "ayarlar_ornek.bat").read_text(encoding="ascii")
    for satir in re.findall(r'^set "(\w+)=(.*)"', ornek, re.M):
        ad, deger = satir
        if ad in ("MIKRO_API_KEY", "MIKRO_KULLANICI", "MIKRO_SIFRE", "SUPABASE_SERVICE_KEY", "MIKRO_FIRMA_KODU"):
            assert deger.startswith("<") and deger.endswith(">"), ad
    assert not (KLASOR / "ayarlar.bat").exists()


# ── Kendini güncelleme + keşif (Ekim 2026, kullanıcı: "sunucuya bir daha dosya taşımayayım";
#    "olabilecek tüm veriler Mikro'dan" → adım 0: Mikro'da hangi veri var) ──
class _Yanit:
    def __init__(self, veri):
        self._v = veri
        self.ok, self.status_code, self.text = True, 200, ""

    def json(self):
        return self._v


class _SahteSb:
    def __init__(self, surum=None, kesif_zaman=None):
        self.rest, self.yazilan = "x", []
        self._surum, self._kz = surum, kesif_zaman
        sb = self

        class _O:
            def get(self, url, params=None, timeout=None):
                if url.endswith("mikro_aktarici_surum"):
                    return _Yanit([sb._surum] if sb._surum else [])
                return _Yanit([{"zaman": sb._kz}] if sb._kz else [])
        self.oturum = _O()

    def _kontrol(self, r):
        return r

    def upsert(self, tablo, satirlar, anahtar):
        self.yazilan.append((tablo, satirlar))


def _surum(kod):
    import hashlib
    return {"kod": kod, "sha256": hashlib.sha256(kod.encode("utf-8")).hexdigest()}


def test_kendini_gunceller_ve_bozugu_reddeder(mk, tmp_path):
    yol = tmp_path / "mikro_kayran.py"
    yol.write_text("eski", encoding="utf-8")
    yeni = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8") + "\n# yeni\n"
    assert mk.kendini_guncelle(_SahteSb(_surum(yeni)), str(yol)) is True
    assert yol.read_text(encoding="utf-8") == yeni and (tmp_path / "mikro_kayran.py.yedek").exists()
    assert mk.kendini_guncelle(_SahteSb(_surum(yeni)), str(yol)) is False          # aynı sürüm: dokunmaz
    bozuk = yeni + "\ndef ( :\n"
    assert mk.kendini_guncelle(_SahteSb(_surum(bozuk)), str(yol)) is False         # derlenmiyor
    yazan = yeni + "\nX = 'StokKaydet" + "V2'\n"
    assert mk.kendini_guncelle(_SahteSb(_surum(yazan)), str(yol)) is False         # Mikro'ya yazan uç
    sahte_ozet = dict(_surum(yeni + "#2"), sha256="0" * 64)
    assert mk.kendini_guncelle(_SahteSb(sahte_ozet), str(yol)) is False            # özet tutmuyor
    assert yol.read_text(encoding="utf-8") == yeni
    assert mk.guncelleme_uygun_mu((KLASOR / "mikro_kayran.py").read_text(encoding="utf-8")) == ""


def test_kesif_yalniz_okur_ve_hatayi_ayri_yazar(mk):
    for ad, sql in mk.KESIF_SORGULARI.items():
        s = " ".join(sql.split()).upper()
        assert s.startswith("SELECT "), ad
        assert not re.search(r"\b(UPDATE|DELETE|INSERT|MERGE|DROP|ALTER|EXEC|TRUNCATE)\b", s), ad

    class _Ist:
        def sql_oku(self, sql):
            if "sys.tables" in sql:
                return [{"tablo": "STOKLAR", "satir": 519}, {"tablo": "BOS", "satir": 0}]
            if "KASALAR" in sql:
                raise mk.MikroHata("Invalid object name 'KASALAR'")
            if "INFORMATION_SCHEMA" in sql:
                assert "'STOKLAR'" in sql and "'BOS'" not in sql          # yalnız dolu tablolar
                return [{"tablo": "STOKLAR", "kolon": "sto_kod", "tip": "nvarchar", "sira": 1}]
            return [{"a": 1}]
    sb = _SahteSb()
    sonuc = mk.kesif_yap(_Ist(), sb)
    assert sonuc["kasalar"] and not sonuc["depolar"] and not sonuc["kolonlar"]
    yazilan = {s[0]["anahtar"]: s[0] for t, s in sb.yazilan}
    assert yazilan["kasalar"]["hata"] and yazilan["kasalar"]["veri"] is None
    assert yazilan["kolonlar"]["veri"][0]["kolon"] == "sto_kod"
    assert mk.kesif_gerekli_mi(_SahteSb(kesif_zaman="2000-01-01T00:00:00+03:00")) is True
    assert mk.kesif_gerekli_mi(_SahteSb(kesif_zaman="2999-01-01T00:00:00+03:00")) is False


def test_muhasebe_fis_turu_ayri_cekilir(mk):
    """Yıl sonu kapanış fişi Aralık'ta gider hesaplarını sıfırlıyor: fiş türü ayrı çekilir (Ekim 2026).
    Eski muhasebe_ay sorgusu (gider tablosu bugün onu okuyor) değişmez."""
    eski = mk.SORGULAR["muhasebe_ay"]
    assert eski["anahtar"] == "yil,ay,hesap_kod" and "fis_tur" not in eski["sql"]
    assert " ".join(eski["sql"].split()) == " ".join("""SELECT YEAR(fis_tarih) AS yil, MONTH(fis_tarih) AS ay, fis_hesap_kod AS hesap_kod,
       SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc,
       SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak,
       COUNT(*) AS satir
FROM MUHASEBE_FISLERI WHERE fis_iptal=0 AND fis_tarih >= '20250101'
GROUP BY YEAR(fis_tarih), MONTH(fis_tarih), fis_hesap_kod""".split())
    ay_tur, tur = mk.SORGULAR["muhasebe_ay_tur"], mk.SORGULAR["muhasebe_tur"]
    assert ay_tur["tablo"] == "mikro_muhasebe_ay_tur" and ay_tur["anahtar"] == "yil,ay,hesap_kod,fis_tur"
    assert tur["tablo"] == "mikro_muhasebe_tur" and tur["anahtar"] == "yil,ay,fis_tur"
    for t in (ay_tur, tur):
        sql = " ".join(t["sql"].split())
        assert "fis_iptal=0" in sql and not t["artimli"]
        # anahtardaki her kolon SELECT'te ve GROUP BY'da (aynı anahtar iki kez upsert edilmesin)
        grup = sql.split("GROUP BY", 1)[1]
        assert "fis_tur" in grup and "COALESCE(CAST(fis_tur AS int), -1) AS fis_tur" in sql
    sema = (KLASOR.parent.parent / "veritabani" / "42_mikro_muhasebe_tur.sql").read_text(encoding="utf-8")
    assert "PRIMARY KEY (yil, ay, hesap_kod, fis_tur)" in sema and "PRIMARY KEY (yil, ay, fis_tur)" in sema


# ── İptal yansıması (Ekim 2026): artımlı sorgular "iptal=0 AND lastup > SON" ile çekiyor; Mikro'da sonradan
#    iptal edilen fatura / satış satırı / sipariş / ithalat hareketi kopyada 03:00 tam aktarımına kadar kalıyordu.
#    Artık her turda son çekimden beri iptal edilenlerin GUID'leri SELECT ile bulunup yalnız kopyadan silinir. ──
_GUID = "0f0e0d0c-0b0a-4908-8706-050403020100"


def _iptal_onekleri(sql):
    return set(re.findall(r"\b(?:\w+\.)?([a-z]+)_iptal=0", " ".join(sql.split())))


def test_iptal_sorgulari_artimli_sorgulardan_turer(mk):
    """WHERE'de iptal=0 süzgeci olan HER artımlı sorgu iptal yansımasında var (alan adı sorgunun kendi öneki)."""
    hedef_onek = {}
    for kaynak, t in mk.IPTAL_SORGULARI.items():
        s = " ".join(t["sql"].split())
        assert s.startswith("SELECT ") and "{SON}" in s and f"{t['alan']}=1" in s, kaynak
        assert not re.search(r"\b(UPDATE|DELETE|INSERT|MERGE|DROP|ALTER|EXEC|TRUNCATE)\b", s.upper()), kaynak
        assert f"FROM {kaynak} " in s, kaynak
        for ad, kolon in t["hedefler"]:
            tanim = mk.SORGULAR[ad]
            assert tanim["artimli"], ad
            assert kolon in tanim["sql"].lower(), (ad, kolon)          # silme kolonu kopyada var
            hedef_onek.setdefault(ad, set()).add(t["alan"].split("_")[0])
    for ad, tanim in mk.SORGULAR.items():
        if tanim["artimli"] and _iptal_onekleri(tanim["sql"]):
            assert hedef_onek.get(ad) == _iptal_onekleri(tanim["sql"]), ad
    # satış satırı iki yoldan düşer: satırın kendisi ya da bağlı faturası iptal
    assert ("satis_satir", "sth_guid") in mk.IPTAL_SORGULARI["STOK_HAREKETLERI"]["hedefler"]
    assert ("satis_satir", "sth_fat_uid") in mk.IPTAL_SORGULARI["CARI_HESAP_HAREKETLERI"]["hedefler"]


class _SenkSb:
    """senkronize_et için sahte Supabase: çağrıları kaydeder."""

    def __init__(self, durum):
        self._durum, self.upsertler, self.silinen, self.durumlar, self.eski = durum, [], [], [], []

    def durum_oku(self):
        return dict(self._durum)

    def upsert(self, tablo, satirlar, anahtar):
        self.upsertler.append(tablo)

    def eskileri_sil(self, tablo, once):
        self.eski.append(tablo)

    def guidleri_sil(self, tablo, kolon, guidler):
        self.silinen.append((tablo, kolon, list(guidler)))
        return len(guidler)

    def durum_yaz(self, tablo, **alanlar):
        self.durumlar.append((tablo, alanlar))


class _SenkIst:
    def __init__(self, iptal):
        self.iptal, self.sqller = iptal, []

    def sql_oku(self, sql):
        self.sqller.append(sql)
        for kaynak, guidler in self.iptal.items():
            if f"FROM {kaynak} WHERE" in " ".join(sql.split()) and "_iptal=1" in sql:
                return [{k: g} for k, g in guidler]
        return []


def test_iptal_edilen_kopyadan_silinir_ve_bildirilir(mk):
    son = "2026-10-21T10:00:00+03:00"
    durum = {t["tablo"]: son for t in mk.SORGULAR.values() if t["artimli"]}
    durum["mikro_siparis"] = "2026-10-21T09:00:00+03:00"
    ist = _SenkIst({"SIPARISLER": [("sip_Guid", _GUID.upper())],
                    "CARI_HESAP_HAREKETLERI": [("cha_Guid", _GUID), ("cha_Guid", "x'); bozuk")],
                    "STOK_HAREKETLERI": []})
    sb = _SenkSb(durum)
    yeni = mk.senkronize_et(ist, sb, tam=False)
    sil = {(t, k): g for t, k, g in sb.silinen}
    assert sil[("mikro_siparis", "sip_guid")] == [_GUID]                         # küçük harfe, uuid biçimi
    for tablo in ("mikro_fatura", "mikro_ithalat", "mikro_cari_hareket", "mikro_masraf"):
        assert sil[(tablo, "cha_guid")] == [_GUID], tablo                         # bozuk GUID gönderilmez
    assert sil[("mikro_satis_satir", "sth_fat_uid")] == [_GUID]                   # iptal faturanın satırları
    assert ("mikro_fatura_satir", "sth_guid") not in sil                          # iptal satır yok: istek yok
    assert not sb.eski                                                            # artımlı turda toplu silme yok
    # sorgunun SON'u, kaynağa bağlı tabloların en eskisi eksi güvenlik payı (09:00 - 2 dk)
    sip_sql = [s for s in ist.sqller if "FROM SIPARISLER WHERE sip_iptal=1" in " ".join(s.split())]
    assert len(sip_sql) == 1 and "20261021 08:58:00" in sip_sql[0]
    yazilan = {t: a["son_silinen"] for t, a in sb.durumlar if "son_silinen" in a}
    assert yazilan["mikro_siparis"] == 1 and yazilan["mikro_satis_satir"] == 1 and yazilan["mikro_alim_satir"] == 0
    assert yeni["mikro_fatura"] == 1 and mk.tetik_nedeni(yeni, False)            # silme de eşitlemeyi başlatır
    # aynı iptal sorgusu bir turda bir kez (tablo başına değil, Mikro tablosu başına)
    assert sum("_iptal=1" in s for s in ist.sqller) == 3


def test_tam_aktarimda_ve_ilk_cekimde_iptal_sorgusu_yok(mk):
    ist = _SenkIst({"SIPARISLER": [("sip_Guid", _GUID)]})
    sb = _SenkSb({})
    mk.senkronize_et(ist, sb, tam=True)
    assert not sb.silinen and not any("_iptal=1" in s for s in ist.sqller)
    mk.senkronize_et(ist, _SenkSb({}), tam=False)                                 # durum boş: ilk çekim
    assert not any("_iptal=1" in s for s in ist.sqller)


def test_iptal_okunamazsa_tur_bozulmaz(mk):
    class _Hatali(_SenkIst):
        def sql_oku(self, sql):
            if "_iptal=1" in sql:
                raise mk.MikroHata("zaman aşımı")
            return []
    durum = {t["tablo"]: "2026-10-21T10:00:00+03:00" for t in mk.SORGULAR.values() if t["artimli"]}
    sb = _SenkSb(durum)
    mk.senkronize_et(_Hatali({}), sb, tam=False)
    assert not sb.silinen
    assert any("iptal" in str(a.get("son_hata") or "") for t, a in sb.durumlar if t == "mikro_siparis")


class _SilOturum:
    def __init__(self):
        self.cagrilar = []

    def delete(self, url, params=None, headers=None, timeout=None):
        self.cagrilar.append((url, dict(params or {}), dict(headers or {})))
        kolon = [k for k in params if k != "select"][0]
        if kolon == "senk_zamani":
            return _Yanit(None)
        adet = params[kolon][len("in.("):-1].count(",") + 1
        return _Yanit([{kolon: "x"}] * adet)


def _sahte_supabase(mk):
    sb = object.__new__(mk.Supabase)
    sb.rest, sb.oturum = "https://x/rest/v1", _SilOturum()
    return sb


def test_guidleri_sil_parcali_ve_bos_listede_istek_yok(mk):
    sb = _sahte_supabase(mk)
    assert sb.guidleri_sil("mikro_fatura", "cha_guid", []) == 0
    assert not sb.oturum.cagrilar                                  # süzgeçsiz DELETE asla gönderilmez
    guidler = [f"00000000-0000-4000-8000-{i:012d}" for i in range(250)]
    assert sb.guidleri_sil("mikro_fatura", "cha_guid", guidler) == 250
    assert len(sb.oturum.cagrilar) == 3
    url, params, headers = sb.oturum.cagrilar[0]
    assert url == "https://x/rest/v1/mikro_fatura" and params["cha_guid"].startswith("in.(00000000-")
    assert "return=representation" in headers["Prefer"]
    sb.eskileri_sil("mikro_fatura", mk.datetime(2026, 10, 21, tzinfo=mk.TZ))     # ortak silme yardımcısı
    assert sb.oturum.cagrilar[-1][1] == {"senk_zamani": "lt.2026-10-21T00:00:00+03:00"}


# ── Sürüm (Ekim 2026): aktarıcı her turda çalışan kodunun özetini mikro_aktarici_surum'a yazar; kendini
#    güncellediği turda eski kodla çalıştığını ve yeninin bir sonraki turda devreye gireceğini bildirir. ──
class _SurumSb(_SahteSb):
    def __init__(self, surum=None):
        super().__init__(surum)
        self.yamalar = []
        sb, eski_get = self, self.oturum.get

        class _O:
            def get(self, url, params=None, timeout=None):
                return eski_get(url, params, timeout)

            def patch(self, url, params=None, data=None, headers=None, timeout=None):
                import json
                sb.yamalar.append((url, dict(params or {}), json.loads(data)))
                return _Yanit(None)
        self.oturum = _O()


def test_calisan_sha_bellekteki_kod(mk):
    import hashlib
    assert mk.CALISAN_SHA == hashlib.sha256((KLASOR / "mikro_kayran.py").read_bytes()).hexdigest()


def test_surum_bildir_guncelledigi_turda_eski_kodla_calistigini_yazar(mk, tmp_path):
    yol = tmp_path / "mikro_kayran.py"
    yol.write_bytes((KLASOR / "mikro_kayran.py").read_bytes())
    yeni = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8") + "\n# yeni\n"
    sb = _SurumSb(_surum(yeni))
    assert mk.surum_bildir(sb, str(yol)) is True
    url, params, veri = sb.yamalar[-1]
    assert url.endswith("/mikro_aktarici_surum") and params == {"id": "eq.1"}
    assert veri["calisan_sha256"] == mk.CALISAN_SHA and veri["calisan_zaman"]
    assert mk.CALISAN_SHA[:12] in veri["calisan_durum"] and _surum(yeni)["sha256"][:12] in veri["calisan_durum"]
    assert "eski kod" in veri["calisan_durum"] and "bir sonraki turda" in veri["calisan_durum"]
    # sonraki tur (yeni kod yüklendi): güncel
    sb2 = _SurumSb(_surum((KLASOR / "mikro_kayran.py").read_text(encoding="utf-8")))
    yol.write_bytes((KLASOR / "mikro_kayran.py").read_bytes())
    assert mk.surum_bildir(sb2, str(yol)) is False
    assert sb2.yamalar[-1][2]["calisan_durum"].startswith("güncel")
    # reddedilen sürüm: neden yazılır, eski kod sürer
    sb3 = _SurumSb(_surum(yeni + "\ndef ( :\n"))
    assert mk.surum_bildir(sb3, str(yol)) is False
    assert "reddedildi" in sb3.yamalar[-1][2]["calisan_durum"]


def test_surum_yazilamazsa_tur_bozulmaz(mk, tmp_path):
    class _Bozuk(_SurumSb):
        def _kontrol(self, r):
            if r._v is None:
                raise mk.MikroHata("Supabase HTTP 400: column calisan_durum does not exist")
            return r
    yol = tmp_path / "mikro_kayran.py"
    yol.write_text("eski", encoding="utf-8")
    assert mk.surum_bildir(_Bozuk(None), str(yol)) is False       # göç uygulanmamış: yalnız günlüğe


def test_tur_basinda_surum_bildirilir(mk):
    govde = (KLASOR / "mikro_kayran.py").read_text(encoding="utf-8").split("def main()", 1)[1]
    bir_kez = govde.split("if args.bir_kez:", 1)[1].split("finally:", 1)[0]
    assert bir_kez.index("surum_bildir(sb)") < bir_kez.index("senkronize_et(")
    assert "kendini_guncelle(sb)" not in bir_kez                  # surum_bildir içinde


def test_surum_gocu_kolonlari(mk):
    sema = (KLASOR.parent.parent / "veritabani" / "51_mikro_aktarici_surum.sql").read_text(encoding="utf-8")
    for kolon in ("calisan_sha256 text", "calisan_zaman timestamptz", "calisan_durum text"):
        assert f"ALTER TABLE public.mikro_aktarici_surum ADD COLUMN IF NOT EXISTS {kolon}" in sema
    assert "ALTER TABLE public.mikro_senk_durum ADD COLUMN IF NOT EXISTS son_silinen integer" in sema
    assert "GERİ ALMA" in sema and "NOTIFY pgrst" in sema

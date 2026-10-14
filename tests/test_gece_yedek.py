# -*- coding: utf-8 -*-
"""Gece yedeği gerçek yedek mi? (Ekim 2026)

Bulgu: otonom/gece_yedek.py her tabloyu tek select ile okuyordu; Supabase 1.000 satırda keser
(satislar 15.819 → yedekte 1.000). Tabloların yarısı listede yoktu, tam geri yükleme aracı yoktu.
Buradaki testler sahte bir Supabase istemcisiyle çalışır (ağ yok).
"""
import gzip
import importlib
import json
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from shared import yedek_tablolari as YT  # noqa: E402


# ── Sahte Supabase ──────────────────────────────────────────────────
class _Yanit:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class _Sorgu:
    def __init__(self, sb, tablo):
        self.sb, self.tablo = sb, tablo
        self.sira, self.r, self.sayim, self.yazma = [], None, False, False

    def select(self, *a, count=None, **k):
        self.sayim = count == "exact"
        return self

    def order(self, c, *a, **k):
        if c in self.sb.siralanamaz.get(self.tablo, ()):
            raise RuntimeError(f"could not identify an ordering operator for type json ({c})")
        self.sira.append(c)
        return self

    def range(self, a, b):
        self.r = (a, b)
        return self

    def upsert(self, satirlar, **k):
        self.sb.yazilan.append((self.tablo, list(satirlar)))
        self.yazma = True
        return self

    def execute(self):
        if self.tablo in self.sb.yok:
            raise RuntimeError("{'code': 'PGRST205', 'message': \"Could not find the table\"}")
        if self.yazma:
            return _Yanit([])
        satirlar = list(self.sb.veri.get(self.tablo, []))
        self.sb.sorgular.append((self.tablo, tuple(self.sira), self.r))
        for c in reversed(self.sira):
            satirlar.sort(key=lambda x: (x.get(c) is None, str(x.get(c))))
        a, b = self.r if self.r else (0, 10 ** 9)
        b = min(b, a + self.sb.tavan - 1)                 # Supabase: sorgu başına en fazla 1000
        parca = satirlar[a:b + 1]
        sayi = self.sb.sayim_yalan.get(self.tablo, len(satirlar)) if self.sayim else None
        return _Yanit(parca, sayi)


class SahteSB:
    def __init__(self, veri=None, tavan=1000, yok=(), sayim_yalan=None, siralanamaz=None):
        self.veri = veri or {}
        self.tavan, self.yok = tavan, set(yok)
        self.sayim_yalan = sayim_yalan or {}
        self.siralanamaz = siralanamaz or {}
        self.sorgular, self.yazilan = [], []

    def table(self, t):
        return _Sorgu(self, t)

    def rpc(self, ad, *a, **k):
        return types.SimpleNamespace(execute=lambda: _Yanit("ok"))


def _satis(n):
    return [{"id": i, "sku": f"SKU{i % 37}", "adet": 1, "tutar": float(i)} for i in range(n)]


# ── 1) 2.500 satırlık tablo eksiksiz okunur (eski kodda 1.000 → kırmızı) ──
def test_gece_yedegi_1000_satirda_kesilmez(tmp_path, monkeypatch):
    """otonom/gece_yedek.py main()'i, sahte `supabase` modülüyle uçtan uca çalıştırır ve
    üretilen Excel'deki satislar sayfasını sayar. Eski kod: 1.000 (kırmızı); yeni: 2.500."""
    sb = SahteSB({"satislar": _satis(2500), "urunler": [{"id": 1, "sku": "A"}]})
    sahte = types.ModuleType("supabase")
    sahte.create_client = lambda url, key: sb
    monkeypatch.setitem(sys.modules, "supabase", sahte)
    monkeypatch.setenv("SUPABASE_URL", "https://ornek.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "gizli-anahtar")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(KOK / "otonom"))
    sys.modules.pop("gece_yedek", None)
    gy = importlib.import_module("gece_yedek")
    gy.main()
    xlsx = sorted(tmp_path.glob("kayran_yedek_*.xlsx"))
    assert xlsx, "Excel yazılmadı"
    df = pd.read_excel(xlsx[0], sheet_name="satislar")
    assert len(df) == 2500, f"satislar yedekte {len(df)} satır (veritabanında 2500)"
    assert sorted(df["id"]) == list(range(2500))


def test_json_yedek_ve_manifest(tmp_path):
    from otonom import gece_yedek as gy
    sb = SahteSB({"satislar": _satis(2500),
                  "ithalat_dosyalari": [{"id": 7, "masraflar": {"navlun": 10}, "not": "a\x01b"}]})
    xlsx, jdizin, sonuc, hatali = gy.yedek_al(sb, tmp_path, ts="T")
    assert not hatali
    assert xlsx.name == "kayran_yedek_T.xlsx" and jdizin.name == "kayran_yedek_T_json"
    govde = json.loads(gzip.open(jdizin / "satislar.json.gz").read())
    assert len(govde["satirlar"]) == 2500 and govde["beklenen"] == 2500 and govde["sira"] == ["id"]
    ith = json.loads(gzip.open(jdizin / "ithalat_dosyalari.json.gz").read())["satirlar"][0]
    assert ith["masraflar"] == {"navlun": 10} and ith["not"] == "a\x01b"   # JSON'da bozulmadan
    m = json.loads((jdizin / "manifest.json").read_text(encoding="utf-8"))
    kayit = {t["tablo"]: t for t in m["tablolar"]}
    assert kayit["satislar"]["okunan"] == 2500 and kayit["satislar"]["durum"] == "tamam"
    assert set(m["haric"]) == set(YT.HARIC)
    for gizli in YT.HARIC:
        assert not (jdizin / f"{gizli}.json.gz").exists()
    # Excel'e yasak karakter IllegalCharacterError ile bütün dosyayı düşürmez; dict JSON metni olur
    x = pd.read_excel(xlsx, sheet_name="ithalat_dosyalari")
    assert json.loads(x.loc[0, "masraflar"]) == {"navlun": 10} and x.loc[0, "not"] == "ab"


# ── 2) Sayım tutmazsa yedek BAŞARISIZ ──────────────────────────────
def test_sayim_tutmazsa_basarisiz(tmp_path, monkeypatch, capsys):
    from otonom import gece_yedek as gy
    sb = SahteSB({"satislar": _satis(2500)}, sayim_yalan={"satislar": 3000})
    s = YT.tablo_oku(sb, "satislar")
    assert s["durum"] == "eksik" and "3000" in s["mesaj"] and "2500" in s["mesaj"]

    sahte = types.ModuleType("supabase")
    sahte.create_client = lambda url, key: sb
    monkeypatch.setitem(sys.modules, "supabase", sahte)
    monkeypatch.setenv("SUPABASE_URL", "https://ornek.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "gizli-anahtar")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as e:
        gy.main()
    assert e.value.code == 1
    cikti = capsys.readouterr().out
    assert "YEDEK BAŞARISIZ" in cikti and "satislar" in cikti
    assert "mv_gunluk_pnl tazelendi" in cikti                 # tazeleme yine yapılır
    assert "gizli-anahtar" not in cikti
    assert list(tmp_path.glob("kayran_yedek_*_json/manifest.json"))   # eldeki yine yazılır


def test_okunamayan_tablo_basarisiz_ama_ref_no_yoksa_uyari(monkeypatch):
    monkeypatch.setattr(YT, "CANLIDA_OLMAYABILIR", {"ref_no"})
    sb = SahteSB({"satislar": _satis(10)}, yok={"ref_no", "iadeler"})
    sonuc, hatali = YT.tumunu_oku(sb, ["satislar", "ref_no", "iadeler"])
    d = {s["tablo"]: s["durum"] for s in sonuc}
    assert d == {"satislar": "tamam", "ref_no": "yok", "iadeler": "hata"}
    assert [s["tablo"] for s in hatali] == ["iadeler"]


# ── 3) Sayfalama ayrıntıları ───────────────────────────────────────
def test_sunucu_tavani_500_olsa_da_tam_okur():
    sb = SahteSB({"satislar": _satis(2345)}, tavan=500)
    s = YT.tablo_oku(sb, "satislar")
    assert s["durum"] == "tamam" and s["okunan"] == 2345


def test_kararli_sira_pk_yoksa_tum_sutunlar_json_siralanamazsa_atlanir():
    satirlar = [{"firma": "B", "sku": f"S{i}", "ek": {"x": i}} for i in range(1500)]
    sb = SahteSB({"_temizlik_yedek_202610": satirlar}, siralanamaz={"_temizlik_yedek_202610": ("ek",)})
    s = YT.tablo_oku(sb, "_temizlik_yedek_202610")
    assert s["durum"] == "tamam" and s["okunan"] == 1500
    assert s["sira"] == ["firma", "sku"]                       # json sütunu çıkarıldı, kalan hepsi
    assert len({r["sku"] for r in s["satirlar"]}) == 1500       # tekrar / kayıp yok
    # id'li tablo id'ye göre, bilinen anahtarlı tablo anahtarına göre
    assert YT.sira_adaylari("satislar", {"id": 1, "a": 2})[0] == ["id"]
    assert YT.sira_adaylari("sistem_ayarlari", {"anahtar": "x", "deger": 1})[0] == ["anahtar"]


def test_okuma_sirasinda_eklenen_satir_baştan_okunur():
    sb = SahteSB({"satislar": _satis(1500)})
    asil = YT.tum_satirlar
    cagri = {"n": 0}

    def oku(sb_, t, **k):
        cagri["n"] += 1
        if cagri["n"] == 1:                                   # sayımdan sonra, okuma sırasında satır gelir
            sb.veri["satislar"].append({"id": 1500, "sku": "Y", "adet": 1, "tutar": 1.0})
        return asil(sb_, t, **k)

    s = YT.tablo_oku(sb, "satislar", oku=oku)
    assert s["durum"] == "tamam" and s["okunan"] == 1501 and cagri["n"] == 2


# ── 4) Tam geri yükleme ─────────────────────────────────────────────
def _yedek(tmp_path):
    from otonom import gece_yedek as gy
    sb = SahteSB({"satislar": _satis(2500), "personel": [{"kod": "P1", "ad": "A"}],
                  "izin_talepleri": [{"id": 1, "personel": "P1"}]})
    _, jdizin, _, hatali = gy.yedek_al(sb, tmp_path, ts="T")
    assert not hatali
    return jdizin


def test_kuru_calisma_yazmaz(tmp_path, capsys):
    from otonom import geri_yukle_tam as G
    j = _yedek(tmp_path)
    acilan = []
    fab = lambda url, key: acilan.append(url) or SahteSB()          # noqa: E731
    assert G.calistir(["--yedek", str(j)], istemci_fabrikasi=fab, ortam={"HEDEF_SUPABASE_KEY": "k"}) == 0
    assert G.calistir(["--yedek", str(j), "--hedef-url", "https://yeni.supabase.co"],
                      istemci_fabrikasi=fab, ortam={"HEDEF_SUPABASE_KEY": "k"}) == 0
    assert acilan == []
    o = capsys.readouterr().out
    assert "KURU ÇALIŞMA" in o and "satislar: 2500 satır, 5 parti" in o


def test_canli_url_korumasi(tmp_path, capsys):
    from otonom import geri_yukle_tam as G
    j = _yedek(tmp_path)
    canli = "https://qspwlqegoeudifxxrxcj.supabase.co"
    acilan = []

    def fab(url, key):
        acilan.append(url)
        return SahteSB()

    kod = G.calistir(["--yedek", str(j), "--hedef-url", canli, "--onayliyorum"],
                     istemci_fabrikasi=fab, ortam={"HEDEF_SUPABASE_KEY": "k"})
    assert kod == 2 and acilan == [] and "REDDEDİLDİ" in capsys.readouterr().out
    kod = G.calistir(["--yedek", str(j), "--hedef-url", canli, "--onayliyorum", "--canli-uzerine-yaz"],
                     istemci_fabrikasi=fab, ortam={"HEDEF_SUPABASE_KEY": "k"})
    assert kod == 0 and acilan == [canli]


def test_gercek_yazma_partiler_sira_ve_sir(tmp_path, capsys):
    from otonom import geri_yukle_tam as G
    j = _yedek(tmp_path)
    hedef = SahteSB()
    kod = G.calistir(["--yedek", str(j), "--hedef-url", "https://yeni.supabase.co", "--onayliyorum"],
                     istemci_fabrikasi=lambda u, k: hedef, ortam={"HEDEF_SUPABASE_KEY": "cok-gizli"})
    assert kod == 0
    partiler = [(t, len(p)) for t, p in hedef.yazilan]
    assert [n for t, n in partiler if t == "satislar"] == [500] * 5
    sira = [t for t, _ in partiler]
    assert sira.index("personel") < sira.index("izin_talepleri")    # önce bağımsızlar
    assert YT.YEDEK_TABLOLAR.index("personel") < YT.YEDEK_TABLOLAR.index("izin_talepleri")
    assert YT.YEDEK_TABLOLAR.index("ithalat_dosyalari") < YT.YEDEK_TABLOLAR.index("ithalat_kalemleri")
    assert YT.YEDEK_TABLOLAR.index("edefter_fisler") < YT.YEDEK_TABLOLAR.index("edefter_fis_satirlari")
    o = capsys.readouterr().out
    assert "cok-gizli" not in o and "setval" in o


def test_anahtar_yoksa_ve_bozuk_dosyada_yazmaz(tmp_path, capsys):
    from otonom import geri_yukle_tam as G
    j = _yedek(tmp_path)
    arg = ["--yedek", str(j), "--hedef-url", "https://yeni.supabase.co", "--onayliyorum"]
    assert G.calistir(arg, istemci_fabrikasi=lambda u, k: pytest.fail("açılmamalı"), ortam={}) == 2
    with gzip.open(j / "satislar.json.gz", "wb") as f:                  # dosya değiştirildi
        f.write(b'{"satirlar": []}')
    assert G.calistir(arg, istemci_fabrikasi=lambda u, k: pytest.fail("açılmamalı"),
                      ortam={"HEDEF_SUPABASE_KEY": "k"}) == 2
    assert "özeti tutmuyor" in capsys.readouterr().out


def test_eksik_yedekten_geri_yukleme_reddedilir(tmp_path):
    from otonom import gece_yedek as gy
    from otonom import geri_yukle_tam as G
    sb = SahteSB({"satislar": _satis(1200)}, sayim_yalan={"satislar": 1300})
    _, j, _, hatali = gy.yedek_al(sb, tmp_path, ts="T", tablolar=["satislar"])
    assert hatali
    with pytest.raises(G.GeriYuklemeHatasi, match="eksik"):
        G.yedegi_oku(j)


# ── 5) Tablo kapsamı ────────────────────────────────────────────────
# Canlı veritabanındaki tablolar (public, BASE TABLE), Ekim 2026.
CANLI_TABLOLAR = """
_kanal_birlestirme_yedek _temizlik_yedek_202610 aktif_excel_verileri aktif_manuel_kalemler
alinan_destekler asistan_rapor audit_log bankalar bayi_giris_denemeleri bayi_kullanicilar
bildirim_ayarlari bildirimler bt_olcum bt_rapor cekler cop_kutusu depo_manuel_takip depo_sevk_log
edefter_ayarlar edefter_donem_kilit edefter_fis_satirlari edefter_fisler edefter_hesap_plani
firma_stok giris_denemeleri gorevler gumruk_sorgulari gunluk_giris haftalar happylife_stok
hata_kayitlari hm_urun_karliligi iadeler ithalat_dosyalari ithalat_kalemleri izin_talepleri
kampanya_urunler kampanyalar kullanici_durum kullanici_sifreler kullanici_tercih kullanici_yetkileri
kur_gunluk odemeler personel pm_ayarlar prim_gecmis ref_butce ref_firmalar ref_kayitlari
satin_alma_gecmisi satislar siparis_onerileri sirket_belgeleri sistem_ayarlari sku_eslesme
soru_kayitlari stok_hareketleri stok_yas tahsilatlar talepler ts_gecmis ts_kayitlar urunler
veri_surumu virmanlar yoldaki_urunler yuklemeler
""".split()

SIRLAR = {"kullanici_sifreler", "bayi_kullanicilar", "bildirim_ayarlari", "giris_denemeleri",
          "bayi_giris_denemeleri", "aktif_excel_verileri", "kullanici_durum"}


def _kodda_kullanilan_tablolar():
    adlar = set()
    for f in KOK.rglob("*.py"):
        if {"tests", ".git", ".venv", "venv", ".claude"} & set(f.parts):
            continue
        s = f.read_text(encoding="utf-8", errors="ignore")
        adlar |= set(re.findall(r'\.table\(\s*["\']([A-Za-z_0-9]+)["\']\s*\)', s))
        adlar |= set(re.findall(r'^\s*_?\w*TABLO\w*\s*=\s*["\']([a-z_0-9]+)["\']\s*$', s, re.M))
        adlar |= set(re.findall(r'_hepsi\(\s*["\']([a-z_0-9]+)["\']', s))
    return adlar


def test_koddaki_her_tablo_yedekte_ya_da_haric():
    eksik = _kodda_kullanilan_tablolar() - set(YT.YEDEK_TABLOLAR) - YT.yedek_disi()
    assert not eksik, (f"yedeğe girmeyen tablo: {sorted(eksik)} — shared/yedek_tablolari.py "
                       "YEDEK_TABLOLAR ya da HARIC'e ekle")


def test_canli_her_tablo_yedekte_ya_da_haric():
    eksik = set(CANLI_TABLOLAR) - set(YT.YEDEK_TABLOLAR) - set(YT.HARIC)
    assert not eksik, sorted(eksik)
    for t in ("iadeler", "tahsilatlar", "edefter_ayarlar", "edefter_donem_kilit", "edefter_fis_satirlari",
              "edefter_fisler", "edefter_hesap_plani", "stok_hareketleri", "alinan_destekler",
              "depo_sevk_log", "depo_manuel_takip", "prim_gecmis", "happylife_stok", "audit_log",
              "satislar", "ts_gecmis", "firma_stok", "odemeler"):
        assert t in YT.YEDEK_TABLOLAR, t


def test_sirlar_haric_ve_listeler_tutarli():
    assert SIRLAR <= set(YT.HARIC)
    assert not set(YT.YEDEK_TABLOLAR) & YT.yedek_disi()
    assert len(YT.YEDEK_TABLOLAR) == len(set(YT.YEDEK_TABLOLAR))
    assert not any(t.startswith(("v_", "mv_")) for t in YT.YEDEK_TABLOLAR)


def test_eski_kod_yarim_listeydi():
    """Karşılaştırma: eski gece yedeği listesi canlı tabloların yarısını bile kapsamıyordu."""
    import subprocess
    try:
        eski = subprocess.run(["git", "show", "origin/main:otonom/gece_yedek.py"], cwd=KOK,
                              capture_output=True, text=True, check=True).stdout
    except Exception:
        pytest.skip("origin/main okunamadı")
    if "shared.yedek_tablolari" in eski or "YEDEK_TABLOLAR = [" not in eski:
        pytest.skip("main zaten yeni sürümde")
    blok = eski[eski.index("YEDEK_TABLOLAR = ["):]
    blok = blok[:blok.index("]")]
    eski_liste = set(re.findall(r'"([a-z_0-9]+)"', blok))
    assert len(eski_liste) == 29
    assert len(set(YT.YEDEK_TABLOLAR)) > 55


# ── 6) Uygulama içi yedek ve iş akışı aynı kaynağı kullanır ─────────
def test_yonetim_ayni_listeyi_kullanir():
    import yonetim as Y
    assert Y.YEDEK_TABLOLAR is YT.YEDEK_TABLOLAR
    assert set(Y.YEDEK_HARIC) == YT.yedek_disi()
    src = (KOK / "yonetim.py").read_text(encoding="utf-8")
    assert src.count("YEDEK_TABLOLAR = [") == 0                # kopya liste kalmadı
    g = (KOK / "otonom" / "gece_yedek.py").read_text(encoding="utf-8")
    assert "YEDEK_TABLOLAR = [" not in g and '"yedek_tablolari.py"' in g
    assert '.select("*").execute()' not in g


def test_betikler_streamlit_olmadan_calisir(tmp_path):
    """GitHub Actions görevinde yalnız supabase/pandas/openpyxl kurulu; `shared` paketi
    Streamlit'i yükler. Betikler shared/yedek_tablolari.py'yi dosyadan yüklemeli."""
    import subprocess
    kod = (
        "import sys, importlib.util\n"
        "sys.modules['streamlit'] = None\n"                       # import streamlit → ImportError
        "for ad in ('gece_yedek', 'geri_yukle_tam'):\n"
        f"    sp = importlib.util.spec_from_file_location(ad, r'{KOK}/otonom/' + ad + '.py')\n"
        "    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)\n"
        "    assert len(m.YEDEK_TABLOLAR) > 55\n"
        "print('tamam')\n")
    r = subprocess.run([sys.executable, "-c", kod], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0 and "tamam" in r.stdout, r.stderr[-800:]


def test_is_akisi_json_ciktisini_saklar():
    y = (KOK / ".github" / "workflows" / "gece-yedek.yml").read_text(encoding="utf-8")
    assert "*.xlsx" in y and "kayran_yedek_*_json/" in y
    assert "python otonom/gece_yedek.py" in y
    assert "secrets.SUPABASE_URL" in y and "secrets.SUPABASE_KEY" in y
    assert 'cron: "0 2 * * *"' in y

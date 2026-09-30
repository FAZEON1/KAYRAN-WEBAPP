# -*- coding: utf-8 -*-
"""
BÜTÜNLÜK TESTLERİ — dosya yüklemelerinin sessizce bir şey geri almadığını doğrular.

NEDEN VAR: Dosyalar GitHub'a elle yükleniyor. Bir düzeltme için yüklenen
dosya, aynı dosyaya daha önce yapılmış BAŞKA bir düzeltmeyi taşımıyorsa
onu sessizce siler ve kimse fark etmez. Bir günde beş kez yaşandı:

  · get_yurtici_kategoriler silindi → Maliyet Girişi ImportError verdi
  · Depo garanti listesi geri alındı → "Servis Depo" seçeneği kayboldu
  · Serdar'ın yetkileri silindi → "erişim yetkiniz yok"
  · kategori_kanonik testi, hiç uygulanmamış bir özelliği import ediyordu
  · Toplam Aktifler listesi iki yerde tekrarlanıyordu, biri güncellenmedi

Bu dosya her push'ta CI'da koşar ve bunların hepsini SANİYELER içinde
yakalar. Yeni bir düzeltme yaptığında buraya bir satır ekle: "bu
fonksiyon var olmalı", "bu kullanıcı bu listede olmalı" gibi.
"""
import ast
import os
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent

# Ölü kopyalar — bunlar CANLI değildir, taranmaz.
OLU_DESENLER = ("(", "/shared/shared", "/shared/kayran", "/shared/satis",
                "/shared/depo", "/shared/ithalat", "/shared/teknik",
                "/kayranpm/kayranpm", "/satis/satis", "_tek.py", "/.git",
                "/tests/", "/bekleyen/")
KOK_KOPYALAR = {"main.py", "kayranpm/app.py"}      # kökteki eski sürümler


def _canli_py_dosyalar():
    for k, _, fs in os.walk(KOK):
        for f in fs:
            p = os.path.join(k, f)
            rel = os.path.relpath(p, KOK).replace(os.sep, "/")
            if (f.endswith(".py") and not any(x in ("/" + rel) for x in OLU_DESENLER)
                    and rel not in KOK_KOPYALAR):
                yield rel, p


def _ust_duzey_isimler(dosya):
    """Bir modülün üst düzey fonksiyon / sınıf / değişken adları."""
    try:
        t = ast.parse(open(dosya, encoding="utf-8").read())
    except SyntaxError:
        return set()
    adlar = set()
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            adlar.add(n.name)
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    adlar.add(tg.id)
    return adlar


# ═══════════════════════════════════════════════════════════════════════
# 1) KIRIK İMPORT TARAMASI
#    "from X import Y" yazan her yer için Y gerçekten X'te tanımlı mı?
#    Sessiz fonksiyon kayıplarını yakalar.
# ═══════════════════════════════════════════════════════════════════════
_TARANAN_MODULLER = {}
for _mod in ("kayranpm", "kayranacc", "satis", "depo", "ithalat", "teknikservis", "shared"):
    for _d in ("database.py", "utils.py", "auth.py", "ui.py", "tasarim.py", "irsaliye.py",
               "stok.py", "arama.py", "audit.py", "dogrula.py", "kar_gizle.py",
               "sirket.py", "tarih.py", "telegram_gonder.py", "marj_uyari.py", "yetki.py", "stok_defteri.py", "hata_log.py", "oturum.py",
               "stok_karti.py", "ref_no.py", "bildirim.py", "belge.py", "excel_islemler.py"):
        _p = KOK / _mod / _d
        if _p.exists():
            _TARANAN_MODULLER[f"{_mod}.{_d[:-3]}"] = _ust_duzey_isimler(_p)


def _kirik_importlar():
    kirik = []
    for rel, p in _canli_py_dosyalar():
        try:
            t = ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError as e:
            kirik.append((rel, 0, "SÖZDİZİMİ HATASI", str(e)[:60]))
            continue
        paket = rel.split("/")[0] if "/" in rel else ""
        for n in ast.walk(t):
            if not isinstance(n, ast.ImportFrom) or not n.module:
                continue
            m = f"{paket}.{n.module}" if (n.level and paket) else n.module
            if m not in _TARANAN_MODULLER:
                continue
            for a in n.names:
                if a.name != "*" and a.name not in _TARANAN_MODULLER[m]:
                    kirik.append((rel, n.lineno, m, a.name))
    return kirik


# Bilinen ölü dosya — hiçbir yerden import edilmiyor, kırık importu zararsız.
_BILINEN_OLU = {("kayranpm/bildirim.py", "kayranpm.database", "get_connection")}


def test_kirik_import_yok():
    kirik = [(r, ln, m, ad) for r, ln, m, ad in _kirik_importlar()
             if (r, m, ad) not in _BILINEN_OLU]
    assert not kirik, (
        "KIRIK İMPORT — bir dosya artık var olmayan bir şeyi import ediyor. "
        "Muhtemelen eski bir sürüm yüklendi ve fonksiyon silindi:\n  "
        + "\n  ".join(f"{r}:{ln} → {m}.{ad}" for r, ln, m, ad in kirik))


# ═══════════════════════════════════════════════════════════════════════
# 2) KRİTİK FONKSİYONLAR — bugüne kadar en az bir kez KAYBOLMUŞ olanlar
#    Yeni bir düzeltme eklediğinde buraya da ekle.
# ═══════════════════════════════════════════════════════════════════════
KRITIK_FONKSIYONLAR = {
    "kayranpm.database": [
        "get_yurtici_kategoriler", "set_yurtici_kategoriler",   # 04.08'de silinmişti
        "get_satis_depolari", "depo_kanonik", "stok_hareket_coklu",
        "get_talepler", "get_talepler_kullanici", "acik_talep_sayisi", "ekle_talep",
    ],
    "kayranacc.database": [
        "get_kur",                                # hiç yoktu, ref_no sessizce None alıyordu
        "aktif_manuel_guncelle",                  # manuel kalem revizyonu
        "virman_yap",
    ],
    "satis.database": [
        "satis_anahtar", "_magaza_ayikla",        # mağazalı mükerrer anahtarı
        "kanal_kok", "kanal_bolunmeleri",         # kanal adı tekilleştirme
        "ice_aktar_satislar", "ekle_siparis",
    ],
    "teknikservis.database": [
        "kullanilmis_irsaliye_nolari", "irsaliye_no_ayir", "irsaliye_isle",
    ],
    "shared.telegram_gonder": ["gonder", "aktif_mi"],
    "shared.marj_uyari": ["marj_uyarisi", "sorunlu_kalemler"],
    "shared.yetki": ["yetki_tablosu", "moduller", "ozel_yetki", "ozel_sahipleri",
                     "salt_okur", "kullanici_kaydi", "kaydet"],
    "shared.stok_defteri": ["yaz", "yaz_fark", "toplu", "gecmis", "kaynak_bul"],
    "shared.hata_log": ["kaydet", "son_hatalar"],
    "shared.oturum": ["oturum_store", "oturum_kapat", "cikis_yap"],
    "shared.utils": ["sidebar_ust", "sidebar_baslik", "sidebar_kullanici"],
}


@pytest.mark.parametrize("modul,fonksiyonlar", KRITIK_FONKSIYONLAR.items())
def test_kritik_fonksiyonlar_duruyor(modul, fonksiyonlar):
    assert modul in _TARANAN_MODULLER, f"{modul} bulunamadı"
    eksik = [f for f in fonksiyonlar if f not in _TARANAN_MODULLER[modul]]
    assert not eksik, (
        f"{modul} içinden fonksiyon KAYBOLDU: {eksik}\n"
        "Bu fonksiyonlar daha önce yazılmıştı. Muhtemelen bu dosyanın eski "
        "bir sürümü yüklendi.")


# ═══════════════════════════════════════════════════════════════════════
# 3) YETKİ LİSTELERİ — kim hangi modüle girmeli
#    Yeni kullanıcı eklendiğinde buraya da ekle; kaybolursa test kırılır.
# ═══════════════════════════════════════════════════════════════════════
def _app_yetkileri():
    src = open(KOK / "app.py", encoding="utf-8").read()
    ns = {}
    for ad in ("KAYRANACC_KULLANICILAR", "KAYRANPM_KULLANICILAR",
               "HESAP_MAKINESI_KULLANICILAR", "ITHALAT_KULLANICILAR",
               "TEKNIKSERVIS_KULLANICILAR", "SATIS_KULLANICILAR",
               "DEPO_KULLANICILAR", "YONETIM_KULLANICILAR", "PATRON_PANEL_KULLANICILAR"):
        m = re.search(rf"^{ad}\s*=\s*(.*?)(?=\n[A-Z_]+\s*=|\n#|\nY0)", src, re.S | re.M)
        assert m, f"app.py içinde {ad} bulunamadı"
        exec(m.group(0).split("\n#")[0], ns)
    exec(re.search(r"^def _statik_yetkiler\(.*?^    \}", src, re.S | re.M).group(0), ns)
    return ns["_statik_yetkiler"]


# kullanıcı → sahip OLMASI gereken modüller
BEKLENEN_YETKILER = {
    "ibrahim": {"kayranacc", "kayranpm", "ithalat", "teknikservis", "satis", "depo",
                "hesap_makinesi"},
    "serdar":  {"kayranacc", "ithalat", "depo", "teknikservis"},   # 21.09'da iki kez kayboldu
    "samet":   {"teknikservis", "depo"},
    "selcuk":  {"depo"},
}
# kullanıcı → sahip OLMAMASI gereken modüller (yetki sızması kontrolü)
YASAK_YETKILER = {
    "serdar": {"kayranpm", "satis", "hesap_makinesi"},
    "selcuk": {"kayranacc", "kayranpm", "satis"},
}


@pytest.mark.parametrize("kullanici,moduller", BEKLENEN_YETKILER.items())
def test_kullanici_yetkileri_duruyor(kullanici, moduller):
    y = _app_yetkileri()(kullanici)
    eksik = [m for m in moduller if not y.get(m)]
    assert not eksik, (
        f"'{kullanici}' kullanıcısının yetkisi KAYBOLDU: {eksik}\n"
        "app.py'nin eski bir sürümü yüklenmiş olabilir.")


@pytest.mark.parametrize("kullanici,moduller", YASAK_YETKILER.items())
def test_kullanici_yetki_sizmasi_yok(kullanici, moduller):
    y = _app_yetkileri()(kullanici)
    sizan = [m for m in moduller if y.get(m)]
    assert not sizan, f"'{kullanici}' sahip olmaması gereken yetkiye sahip: {sizan}"


def test_toplam_aktifler_tek_kaynak():
    """Toplam Aktifler beyaz listesi TEK yerde tanımlı olmalı ve iki kontrol
    de oradan okumalı. Eskiden iki ayrı sabit liste vardı, biri güncellenmedi."""
    src = open(KOK / "kayranacc" / "main.py", encoding="utf-8").read()
    assert re.search(r"^TOPLAM_AKTIFLER_YETKILI\s*=\s*\{", src, re.M), \
        "TOPLAM_AKTIFLER_YETKILI modül düzeyinde tanımlı değil"
    assert "YETKILI_KULLANICILAR_TOPLAM_AKTIFLER = _toplam_aktifler_yetkilileri()" in src, \
        "sol menü tek kaynaktan okumuyor"
    assert "YETKILI_TOPLAM_AKTIFLER = _toplam_aktifler_yetkilileri()" in src, \
        "sayfa gövdesi tek kaynaktan okumuyor"
    # Elde yazılmış ikinci bir liste kalmamalı
    sabit = re.findall(r'YETKILI\w*TOPLAM\w*\s*=\s*\{"ibrahim"', src)
    assert not sabit, "Toplam Aktifler için elle yazılmış ikinci liste var"
    ns = {}
    exec(re.search(r"^TOPLAM_AKTIFLER_YETKILI\s*=\s*\{.*?\}", src, re.S | re.M).group(0), ns)
    assert "serdar" in ns["TOPLAM_AKTIFLER_YETKILI"]


# ═══════════════════════════════════════════════════════════════════════
# 4) DEPO GARANTİ LİSTESİ — stok sıfır olsa bile hepsi seçilebilir olmalı
# ═══════════════════════════════════════════════════════════════════════
def test_depo_garanti_listesi_eksiksiz():
    src = open(KOK / "kayranpm" / "database.py", encoding="utf-8").read()
    m = re.search(r"def get_satis_depolari\(.*?return adlar", src, re.S)
    assert m, "get_satis_depolari bulunamadı"
    govde = m.group(0)
    for depo in ("TEKNİK DEPO", "İADE DEPO", "İKİNCİ EL DEPO", "OUTLET DEPO", "HURDA DEPO"):
        assert depo in govde, (
            f"'{depo}' garanti listesinde YOK — stoğu sıfırlanınca seçeneklerden "
            "kaybolur (09.09'da Servis Depo'nun kaybolma sebebi).")


def test_depo_kanonik_servis_teknik_ayni():
    from kayranpm.database import depo_kanonik
    assert depo_kanonik("SERVIS DEPO") == depo_kanonik("TEKNİK DEPO") == "TEKNİK DEPO"


# ═══════════════════════════════════════════════════════════════════════
# 5) ÇALIŞMA ZAMANI KORUMALARI — Streamlit'e özgü tuzaklar
# ═══════════════════════════════════════════════════════════════════════
def test_dialog_icinde_duz_rerun_yok():
    """@st.dialog içinde st.rerun() değil _rerun_app() kullanılmalı.
    Fragment kapsamında kalan rerun dialog'u kapatmaz (mal kabul bug'ı)."""
    src = open(KOK / "teknikservis" / "main.py", encoding="utf-8").read()
    lines = src.split("\n")
    sorun = []
    for i, l in enumerate(lines):
        if "@st.dialog" not in l or l.strip().startswith("#"):
            continue
        j = i + 1
        while j < len(lines) and not re.match(r"\s*def\s+\w+", lines[j]):
            j += 1
        ind = len(lines[j]) - len(lines[j].lstrip())
        k = j + 1
        while k < len(lines):
            cur = lines[k]
            if cur.strip() and (len(cur) - len(cur.lstrip())) <= ind:
                break
            if re.search(r"(?<!_)\bst\.rerun\(\)", cur) and not cur.strip().startswith("#"):
                sorun.append(k + 1)
            k += 1
    assert not sorun, f"teknikservis/main.py dialog içinde düz st.rerun(): satır {sorun}"


def test_requirements_ust_sinirli():
    """Platform sürüm atlaması sessizce bozmasın diye üst sınır olmalı."""
    req = open(KOK / "requirements.txt", encoding="utf-8").read()
    for paket in ("streamlit", "supabase", "pandas"):
        satir = next((l for l in req.splitlines() if l.strip().startswith(paket)), "")
        assert satir and "<" in satir, f"requirements.txt: {paket} için üst sınır yok"


# ═══════════════════════════════════════════════════════════════════════
# 6) ÇERÇEVE (D1) — tek standart, geri dönmesin
# ═══════════════════════════════════════════════════════════════════════
_MODULLER = ["satis", "ithalat", "kayranpm", "teknikservis", "kayranacc", "depo"]


@pytest.mark.parametrize("modul", _MODULLER)
def test_modul_kendi_cikis_dugmesini_yazmiyor(modul):
    """Modüllerdeki elle yazılmış 'Çıkış Yap' düğmeleri oturum anahtarını
    YAKMIYORDU — kullanıcı yenileyince 7 gün boyunca geri içerideydi.
    Çıkış yalnız shared.oturum.cikis_yap() üzerinden yapılmalı."""
    src = open(KOK / modul / "main.py", encoding="utf-8").read()
    assert not re.search(r'st\.button\(\s*["\'][^"\']*Çıkış Yap', src), (
        f"{modul}/main.py kendi Çıkış düğmesini çiziyor — shared.utils.sidebar_ust kullanılmalı")
    assert "sidebar_ust(" in src, f"{modul}/main.py ortak sidebar üst bileşenini kullanmıyor"


def test_cikis_yap_anahtari_yakar_ve_urlyi_temizler():
    src = open(KOK / "shared" / "oturum.py", encoding="utf-8").read()
    govde = src[src.index("def cikis_yap"):]
    assert "oturum_kapat()" in govde and "query_params.clear()" in govde


@pytest.mark.parametrize("modul", ["kayranacc", "kayranpm"])
def test_elle_yazilmis_buyuk_baslik_kalmadi(modul):
    """Sayfa başlıkları tek standart (shared/tasarim.baslik). Muhasebe'de
    eskiden her sayfada başlık İKİ KEZ çıkıyordu."""
    src = open(KOK / modul / "main.py", encoding="utf-8").read()
    assert 'class="baslik"' not in src


def test_gorunmez_eleman_boslugu_kurali_var():
    """Sayfa başındaki ~200px boşluğu kapatan kural çekirdek CSS'te durmalı."""
    src = open(KOK / "shared" / "tasarim.py", encoding="utf-8").read()
    assert '[data-testid="stElementContainer"][height="0px"]' in src
    assert 'style:only-child' in src


def test_oturum_hata_yutmuyor():
    """shared/oturum.py'de 'except ...: pass' olmamalı. Anahtar yakma hatası
    sessizce geçerse çıkış yapan kullanıcı yenileyince içeride kalır."""
    import re
    src = open(KOK / "shared" / "oturum.py", encoding="utf-8").read()
    assert not re.search(r"except[^\n]*:\s*\n\s*pass\b", src)
    assert "kritik=True" in src

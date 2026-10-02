# -*- coding: utf-8 -*-
"""Dönemsel Excel yüklemeleri için hatırlatma / geri sayım (Ekim 2026).

Sorun: haftalık müşteri satışları, aylık iadeler, toplam aktifler gibi dosyalar
atlanınca veri sessizce eskiyordu. Çözüm: shared/yukleme_takvimi.py her kaynağın
"en son hangi dönem yüklendi" bilgisini veriden (ya da yükleme kaydından) okur,
dönem bazında durum çıkarır: güncel (geri sayım) · yaklaşıyor · gecikti.
Herkes görür (ana sayfa Bugün paneli + Veri güncelliği kartları).
"""
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _yt():
    from shared import yukleme_takvimi as Y
    return Y


# ── Dönem ve son gün ────────────────────────────────────────────────
def test_donem_bas():
    Y = _yt()
    assert Y.donem_bas("haftalik", date(2026, 10, 1)) == date(2026, 9, 28)      # Çarşamba → Pazartesi
    assert Y.donem_bas("aylik", date(2026, 10, 17)) == date(2026, 10, 1)
    assert Y.donem_bas("ceyreklik", date(2026, 8, 17)) == date(2026, 7, 1)
    assert Y.onceki("aylik", date(2026, 1, 1)) == date(2025, 12, 1)
    assert Y.sonraki("ceyreklik", date(2026, 10, 1)) == date(2027, 1, 1)


def test_son_gun_geri_ve_ileri():
    Y = _yt()
    # geri: Eylül verisi Ekim'in 5'ine kadar · Hafta 39 verisi sonraki Pazartesi
    assert Y.vade("aylik", date(2026, 9, 1), 5, "geri") == date(2026, 10, 5)
    assert Y.vade("haftalik", date(2026, 9, 21), 0, "geri") == date(2026, 9, 28)
    assert Y.vade("ceyreklik", date(2026, 7, 1), 15, "geri") == date(2026, 10, 15)
    # ileri: bu haftanın ödeme listesi bu haftanın Pazartesi'sine kadar
    assert Y.vade("haftalik", date(2026, 9, 28), 0, "ileri") == date(2026, 9, 28)


def test_donem_adi():
    Y = _yt()
    assert Y.donem_adi("aylik", date(2026, 9, 1)) == "Eylül 2026"
    assert Y.donem_adi("haftalik", date(2026, 9, 21)) == "Hafta 39 (21.09–27.09)"
    assert Y.donem_adi("ceyreklik", date(2026, 7, 1)) == "2026 Ç3"


def _k(**kw):
    k = {"siklik": "aylik", "son_gun": 5, "yon": "geri", "tarih_turu": "veri"}
    k.update(kw)
    return k


def test_durum_guncel_geri_sayim():
    Y = _yt()
    # 1 Ekim: Ağustos'un son günü (5 Eylül) geçti; Eylül'ün son günü 5 Ekim
    d = Y.durum(_k(), date(2026, 8, 20), date(2026, 10, 1))
    assert d["seviye"] == "guncel" and d["kalan_gun"] == 4 and d["sonraki_donem"] == date(2026, 9, 1)
    d = Y.durum(_k(), date(2026, 9, 30), date(2026, 10, 1))            # Eylül de var → sıradaki Ekim
    assert d["seviye"] == "guncel" and d["sonraki_vade"] == date(2026, 11, 5) and d["kalan_gun"] == 35
    d = Y.durum(_k(), date(2026, 8, 20), date(2026, 10, 3))            # Eylül 2 gün sonra
    assert d["seviye"] == "yaklasiyor" and d["kalan_gun"] == 2 and d["sonraki_donem"] == date(2026, 9, 1)


def test_durum_gecikti():
    Y = _yt()
    d = Y.durum(_k(), date(2026, 8, 20), date(2026, 10, 9))            # Eylül 5 Ekim'de gerekiyordu
    assert d["seviye"] == "gecikti" and d["gecikme_gun"] == 4
    assert d["eksik"] == [date(2026, 9, 1)]
    d = Y.durum(_k(), date(2026, 6, 20), date(2026, 10, 9))            # Temmuz, Ağustos, Eylül eksik
    assert d["eksik"] == [date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)]
    assert d["gecikme_gun"] == (date(2026, 10, 9) - date(2026, 8, 5)).days   # en eski eksiğin son günü


def test_son_gunde_gecikmez():
    Y = _yt()
    d = Y.durum(_k(), date(2026, 8, 20), date(2026, 10, 5))            # bugün son gün
    assert d["seviye"] == "yaklasiyor" and d["kalan_gun"] == 0


def test_atlanan_donem_eksik_sayilmaz():
    Y = _yt()
    d = Y.durum(_k(), date(2026, 8, 20), date(2026, 10, 9), atlanan=[date(2026, 9, 1)])
    assert d["seviye"] != "gecikti" and d["sonraki_donem"] == date(2026, 10, 1)


def test_yukleme_tarihi_onceki_donemi_kapsar():
    Y = _yt()
    # 3 Ekim'de yüklenen aylık anlık görüntü (toplam aktifler) Eylül sonunu kapsar
    assert Y.kapsanan("aylik", date(2026, 10, 3), "yukleme", "geri") == date(2026, 9, 1)
    assert Y.kapsanan("aylik", date(2026, 10, 3), "veri", "geri") == date(2026, 10, 1)
    assert Y.kapsanan("haftalik", date(2026, 9, 30), "yukleme", "ileri") == date(2026, 9, 28)
    d = Y.durum(_k(tarih_turu="yukleme"), date(2026, 10, 3), date(2026, 10, 9))
    assert d["seviye"] == "guncel"


def test_hic_yuklenmemis():
    Y = _yt()
    d = Y.durum(_k(), None, date(2026, 10, 9))
    assert d["seviye"] == "gecikti" and d["eksik"] == [date(2026, 9, 1)] and d["hic"] is True


def test_haftalik_ileri_odeme_listesi():
    Y = _yt()
    k = _k(siklik="haftalik", son_gun=0, yon="ileri", tarih_turu="yukleme")
    d = Y.durum(k, date(2026, 9, 22), date(2026, 9, 30))               # bu hafta (28.09) yüklenmedi
    assert d["seviye"] == "gecikti" and d["eksik"] == [date(2026, 9, 28)] and d["gecikme_gun"] == 2
    d = Y.durum(k, date(2026, 9, 28), date(2026, 9, 30))
    assert d["seviye"] == "guncel" and d["sonraki_vade"] == date(2026, 10, 5)


# ── Kaynaklar ───────────────────────────────────────────────────────
def test_kaynaklar_tanimli_ve_tutarli():
    Y = _yt()
    anahtarlar = [k["anahtar"] for k in Y.KAYNAKLAR]
    assert len(anahtarlar) == len(set(anahtarlar)) >= 10
    for k in Y.KAYNAKLAR:
        assert k["siklik"] in Y.SIKLIKLAR and k["yon"] in ("geri", "ileri")
        assert k["tarih_turu"] in ("veri", "yukleme") and k["modul"] and k["sayfa"]
    for a in ("musteri_haftalik", "iade_aylik", "satis_dokumu", "aktif_stok", "aktif_ithalat",
              "aktif_cari", "odeme_listesi", "happylife", "gider_tablosu", "g5f_sayim"):
        assert a in anahtarlar, a


def test_ayar_ezer_varsayilani():
    Y = _yt()
    k = Y.kaynak_ayari("happylife", {"happylife": {"siklik": "aylik", "son_gun": 3}})
    assert k["siklik"] == "aylik" and k["son_gun"] == 3 and k["ad"]
    k2 = Y.kaynak_ayari("happylife", {"happylife": {"siklik": "uydurma"}})
    assert k2["siklik"] in Y.SIKLIKLAR                                 # bozuk ayar yok sayılır


def test_gider_son_ay():
    Y = _yt()
    kat = {"Sabit": [10, 10, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0], "Değişken": [0, 5, 0, 7, 0, 0, 0, 0, 0, 0, 0, 0]}
    assert Y.gider_son_ay(2026, kat) == date(2026, 4, 1)
    assert Y.gider_son_ay(2026, {"Sabit": [0] * 12}) is None


# ── Görünürlük: herkes ──────────────────────────────────────────────
def test_bugun_maddeleri():
    from shared.bugun import maddeler_yukleme
    durumlar = [
        {"anahtar": "iade_aylik", "ad": "İade Excel'i", "modul": "satis", "sayfa": "Satış › İade",
         "seviye": "gecikti", "gecikme_gun": 4, "eksik_adlar": ["Eylül 2026"], "kalan_gun": None},
        {"anahtar": "happylife", "ad": "Happy Life stok", "modul": "depo", "sayfa": "Depo › Happy Life",
         "seviye": "yaklasiyor", "kalan_gun": 0, "sonraki_adi": "Hafta 40 (28.09–04.10)"},
        {"anahtar": "g5f_sayim", "ad": "G5F sayım", "modul": "kayranpm", "sayfa": "x",
         "seviye": "guncel", "kalan_gun": 40},
    ]
    m = maddeler_yukleme(durumlar)
    assert [x["oncelik"] for x in m] == ["kritik", "uyari"]
    assert "4 gün" in m[0]["detay"] and "Eylül 2026" in m[0]["detay"] and m[0]["hedef"] == "satis"
    assert "bugün" in m[1]["baslik"].lower() or "bugün" in m[1]["detay"].lower()


def test_herkes_gorur():
    b = _oku("shared/bugun.py")
    g = b[b.index("def topla("):]
    i = g.index("maddeler_yukleme(")
    # yetki koşullarının içinde değil: satırın girintisi try bloğu seviyesinde (8)
    satir = g[:i].rsplit("\n", 1)[1]
    assert len(satir) - len(satir.lstrip()) == 8, "hatırlatmalar yetkiye göre süzülmemeli"
    assert "_veri_guncelligi(" in _oku("app.py")


def test_kayit_kancalari():
    s = _oku("satis/main.py")
    assert 'kaydet("satis_dokumu"' in s and 'kaydet("iade_aylik"' in s
    assert 'kaydet("odeme_listesi"' in _oku("kayranacc/main.py")
    assert 'kaydet("g5f_sayim"' in _oku("kayranpm/main.py")


def test_yukleme_ekranlarinda_serit():
    assert 'serit(f"aktif_{anahtar}")' in _oku("kayranacc/main.py")   # üç aktif dosyası ortak blokta
    for y, a in (("kayranpm/main.py", "musteri_haftalik"), ("satis/main.py", "iade_aylik"),
                 ("satis/main.py", "satis_dokumu"),
                 ("kayranacc/main.py", "odeme_listesi"), ("depo/main.py", "happylife"),
                 ("yonetim.py", "gider_tablosu"), ("kayranpm/main.py", "g5f_sayim")):
        assert f'serit("{a}")' in _oku(y), (y, a)


def test_atlanan_donem_aramayi_kesmez():
    """Haziran yüklü, Eylül 'veri yok' işaretli → Temmuz ve Ağustos yine eksik görünmeli."""
    Y = _yt()
    d = Y.durum(_k(), date(2026, 6, 20), date(2026, 10, 9), atlanan=[date(2026, 9, 1)])
    assert d["seviye"] == "gecikti" and d["eksik"] == [date(2026, 7, 1), date(2026, 8, 1)]


def test_telegram_blogu():
    import telegram_brifing as T
    assert T.yukleme_blogu_kur([{"seviye": "guncel", "ad": "x"}]) is None      # hepsi güncelse sessiz
    b = T.yukleme_blogu_kur([
        {"seviye": "gecikti", "ad": "İade Excel'i", "eksik_adlar": ["Eylül 2026"], "gecikme_gun": 4},
        {"seviye": "yaklasiyor", "ad": "Happy Life", "sonraki_adi": "Hafta 40", "kalan_gun": 0}])
    assert "İade Excel&#x27;i" in b and "4 gün gecikti" in b and "bugün son gün" in b
    assert "yukleme_blogu_kur(durumlar(" in _oku("telegram_brifing.py")


def test_gecmisi_olmayan_kaynak_ilk_gun_alarm_vermez(monkeypatch):
    """Satış dökümü / ödeme listesi / G5F yalnız yükleme anında kaydedilir; geçmişleri
    yok. İlk gün 'hiç yüklenmedi · N gün gecikti' yanlış alarmı olmamalı."""
    Y = _yt()
    monkeypatch.setattr(Y, "_ayar", lambda a, v: v)                 # boş ayar / kayıt
    monkeypatch.setattr(Y, "_takip_baslangici", lambda a, b: b)
    for a in ("musteri_haftalik", "iade_aylik", "aktif_stok", "aktif_ithalat", "aktif_cari",
              "happylife", "gider_tablosu"):
        monkeypatch.setitem(Y._OKUYUCU, a, lambda b: None)
    dl = {d["anahtar"]: d for d in Y.durumlar(date(2026, 10, 9))}
    # satis_dokumu Ekim 2026'dan beri varsayılan olarak takip dışı (zaman zaman yapılıyor)
    for a in ("odeme_listesi", "g5f_sayim"):
        assert dl[a]["seviye"] != "gecikti" and dl[a]["baslangic"], a
    assert dl["iade_aylik"]["seviye"] == "gecikti"                  # veriden okunan kaynak alarm verir


def test_takip_baslangici_siradakini_bekler():
    """Kurulum 2 Ekim: Ağustos (son günü 5 Eylül) var sayılır; Eylül dökümü 5 Ekim'de
    beklenir — 'Ekim 2026 · 5 Kasım' diye bir ay ileri atlamaz (tarayıcıda görüldü)."""
    Y = _yt()
    k = _k(tarih_turu="yukleme")
    bas = Y.zorunlu_donem(k, date(2026, 10, 2))
    assert bas == date(2026, 8, 1)
    d = Y.durum(k, None, date(2026, 10, 2), son_donem=bas)
    assert d["sonraki_donem"] == date(2026, 9, 1) and d["kalan_gun"] == 3
    d = Y.durum(k, None, date(2026, 10, 8), son_donem=bas)            # Eylül yüklenmedi → gecikti
    assert d["seviye"] == "gecikti" and d["eksik"] == [date(2026, 9, 1)]


def test_ayni_sayfanin_gecikenleri_tek_madde():
    from shared.bugun import maddeler_yukleme
    ds = [{"anahtar": f"aktif_{t}", "ad": f"Toplam aktifler · {t}", "modul": "kayranacc",
           "sayfa": "Muhasebe › Toplam Aktifler", "seviye": "gecikti", "gecikme_gun": g,
           "eksik_adlar": ["Ağustos 2026"]} for t, g in (("stok", 27), ("cari", 3))]
    m = maddeler_yukleme(ds)
    assert len(m) == 1 and m[0]["sayi"] == 2 and "2 dosya" in m[0]["baslik"]
    assert "stok, cari" in m[0]["detay"] and "27 gün" in m[0]["detay"]


# ── Sorumlular (Ekim 2026) ──────────────────────────────────────────
ATAMA = {"musteri_haftalik": "derya", "iade_aylik": "gokhan", "aktif_stok": "serdar",
         "aktif_ithalat": "serdar", "aktif_cari": "serdar", "odeme_listesi": "serdar",
         "happylife": "samet", "gider_tablosu": "serdar", "g5f_sayim": "gokhan"}


def test_varsayilan_sorumlular_ve_takvim():
    Y = _yt()
    k = {x["anahtar"]: x for x in Y.KAYNAKLAR}
    for a, kim in ATAMA.items():
        assert k[a]["sorumlu"] == kim, a
    for a in ("aktif_stok", "aktif_ithalat", "aktif_cari"):
        assert (k[a]["siklik"], k[a]["son_gun"]) == ("haftalik", 0), a        # her Pazartesi
    assert (k["happylife"]["siklik"], k["happylife"]["son_gun"]) == ("aylik", 5)
    assert k["satis_dokumu"]["aktif"] is False and not k["satis_dokumu"].get("sorumlu")   # takip dışı
    assert Y.AYAR_ANAHTAR == "yukleme_takvimi_ayar_v2"                  # eski kayıtlı ayar ezmesin


def test_ayar_sorumlu_ve_takip_ezer():
    Y = _yt()
    k = Y.kaynak_ayari("happylife", {"happylife": {"sorumlu": "derya"}})
    assert k["sorumlu"] == "derya" and k["siklik"] == "aylik"
    assert Y.kaynak_ayari("satis_dokumu", {})["aktif"] is False
    assert Y.kaynak_ayari("satis_dokumu", {"satis_dokumu": {"aktif": True}})["aktif"] is True


def test_sorumlu_adi():
    Y = _yt()
    assert Y.sorumlu_adi("gokhan") == "Gökhan" and Y.sorumlu_adi("derya") == "Derya"
    assert Y.sorumlu_adi("ali") == "Ali" and Y.sorumlu_adi("") == ""


def test_takip_disi_kaynak_durumlarda_yok(monkeypatch):
    Y = _yt()
    monkeypatch.setattr(Y, "_ayar", lambda a, v: v)
    monkeypatch.setattr(Y, "_takip_baslangici", lambda a, b: b)
    for a in list(Y._OKUYUCU):
        monkeypatch.setitem(Y._OKUYUCU, a, lambda b: None)
    dl = {d["anahtar"]: d for d in Y.durumlar(date(2026, 10, 9))}
    assert "satis_dokumu" not in dl
    assert dl["iade_aylik"]["sorumlu"] == "gokhan" and dl["iade_aylik"]["sorumlu_ad"] == "Gökhan"


def test_uyarilarda_isim():
    from shared.bugun import maddeler_yukleme
    Y = _yt()
    d = {"anahtar": "iade_aylik", "ad": "İade Excel'i", "modul": "satis", "sayfa": "Satış › İade",
         "seviye": "gecikti", "gecikme_gun": 4, "eksik_adlar": ["Eylül 2026"], "sorumlu_ad": "Gökhan"}
    assert "Gökhan" in maddeler_yukleme([d])[0]["baslik"]
    y = dict(d, seviye="yaklasiyor", kalan_gun=1, sonraki_adi="Ekim 2026")
    assert "Gökhan" in maddeler_yukleme([y])[0]["baslik"]
    grup = [dict(d, anahtar=f"aktif_{t}", ad=f"Toplam aktifler · {t}", sayfa="Muhasebe › Toplam Aktifler",
                 sorumlu_ad="Serdar") for t in ("stok", "cari")]
    assert "Serdar" in maddeler_yukleme(grup)[0]["baslik"]
    kart = Y.kart_html(dict(d, siklik="aylik", kalan_gun=0, son_adi="Ağustos 2026", sonraki_adi="Eylül 2026",
                            vade_metni="05.10 Pzt", eksik=[]))
    assert "Gökhan" in kart
    import telegram_brifing as T
    assert "Gökhan" in T.yukleme_blogu_kur([d])


def test_ayar_penceresinde_sorumlu_ve_sorumlu_isaretleyebilir():
    a = _oku("app.py")
    g = a[a.index("def _veri_guncelligi("):a.index("def anasayfa():")]
    assert '"Sorumlu"' in g
    assert 'd.get("sorumlu") == aktif_kullanici' in g                  # sorumlu "veri yok" diyebilir


def test_uzun_gecikme_ozetlenir():
    Y = _yt()
    adlar = [f"Hafta {i} (01.01–07.01)" for i in range(35, 40)]
    assert Y.eksik_ozeti(adlar, "haftalik") == "5 hafta: Hafta 35 – Hafta 39"
    assert Y.eksik_ozeti(adlar[:2], "haftalik") == "Hafta 35 (01.01–07.01), Hafta 36 (01.01–07.01)"
    assert Y.eksik_ozeti(["Temmuz 2026", "Ağustos 2026", "Eylül 2026"], "aylik") == "3 ay: Temmuz 2026 – Eylül 2026"

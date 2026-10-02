# -*- coding: utf-8 -*-
"""KAYRAN — Dönemsel Excel yüklemeleri: hatırlatma ve geri sayım (Ekim 2026).

SORUN: Haftalık müşteri satışları, aylık iadeler, toplam aktifler gibi dosyalar
bazen atlanıyor; ekranlar eski veriyi güncelmiş gibi göstermeye devam ediyordu.

ÇÖZÜM: Her dönemsel kaynak için "en son hangi DÖNEM yüklendi" bilgisi veriden
(ya da yükleme kaydından) okunur ve dönem bazında durum çıkarılır:
  🟢 güncel     → sıradaki son güne geri sayım
  🟡 yaklaşıyor → son 2 gün (bugün dahil)
  🔴 gecikti    → son günü geçmiş eksik dönem(ler)
Herkes görür: ana sayfa Bugün paneli + Veri güncelliği kartları + yükleme
ekranlarının üstündeki şerit + Telegram sabah brifingi.

Kavramlar
  siklik      haftalik · aylik · ceyreklik
  son_gun     haftalık: hafta günü (0=Pzt) · aylık/çeyreklik: ayın günü (1–28)
  yon         geri  = biten dönemin verisi, SONRAKİ dönemin son gününe kadar
                      (Eylül iadeleri → 5 Ekim'e kadar)
              ileri = dönemin planı, dönemin İÇİNDEKİ son güne kadar
                      (bu haftanın ödeme listesi → bu Pazartesi)
  tarih_turu  veri    = okunan tarih verinin ait olduğu dönemde (iade dönem tarihi)
              yukleme = okunan tarih yükleme anı; geri yönde önceki dönemi kapsar
                        (3 Ekim'de yüklenen toplam aktifler → Eylül sonu)

Saf fonksiyonlar test edilir (tests/test_yukleme_takvimi.py); veritabanı
okumaları her kaynak için ayrı try bloğundadır — biri çökerse diğerleri çalışır.
Ayarlar / kayıtlar / atlanan dönemler sistem_ayarlari'nda (şema değişikliği yok).
"""
from datetime import date, datetime, timedelta

SIKLIKLAR = {"haftalik": "Haftalık", "aylik": "Aylık", "ceyreklik": "Çeyreklik"}
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
         "Eylül", "Ekim", "Kasım", "Aralık"]
YAKLASIYOR_GUN = 2          # son 2 gün (bugün dahil) sarı
GERIYE_BAKIS = 6            # en fazla bu kadar eksik dönem listelenir

# v2 (Ekim 2026): sorumlular ve yeni takvim verildi; eski anahtarda kayıtlı ayar varsa
# yeni varsayılanları ezmesin diye ayrı anahtar.
AYAR_ANAHTAR = "yukleme_takvimi_ayar_v2"   # {anahtar: {siklik, son_gun, aktif, sorumlu}}
KAYIT_ANAHTAR = "yukleme_takvimi_kayit"    # {anahtar: {tarih, kim, adet}}
ATLA_ANAHTAR = "yukleme_takvimi_atla"      # {anahtar: [dönem iso, ...]}

# ── Kaynaklar (varsayılanlar; Veri güncelliği → Ayarlar'dan değiştirilir) ──
KAYNAKLAR = [
    dict(anahtar="musteri_haftalik", ad="Haftalık müşteri stok + satış", modul="kayranpm",
         sayfa="Ürün Yönetimi › Müşteri Satışları", siklik="haftalik", son_gun=0, yon="geri",
         tarih_turu="veri", sorumlu="derya"),
    dict(anahtar="iade_aylik", ad="İade Excel'i", modul="satis", sayfa="Satış › İade",
         siklik="aylik", son_gun=5, yon="geri", tarih_turu="veri", sorumlu="gokhan"),
    # Takip DIŞI: gerektiğinde zaman zaman yapılıyor — atama ve uyarı yok (ayarlardan açılabilir)
    dict(anahtar="satis_dokumu", ad="Satış fatura dökümü", modul="satis", sayfa="Satış › İçe Aktar",
         siklik="aylik", son_gun=5, yon="geri", tarih_turu="yukleme", sorumlu="", aktif=False),
    # Toplam aktiflerin üç dosyası birlikte, HER PAZARTESİ yükleniyor
    dict(anahtar="aktif_stok", ad="Toplam aktifler · stok değeri", modul="kayranacc",
         sayfa="Muhasebe › Toplam Aktifler", siklik="haftalik", son_gun=0, yon="geri", tarih_turu="yukleme",
         sorumlu="serdar"),
    dict(anahtar="aktif_ithalat", ad="Toplam aktifler · ithalat ödeme takip", modul="kayranacc",
         sayfa="Muhasebe › Toplam Aktifler", siklik="haftalik", son_gun=0, yon="geri", tarih_turu="yukleme",
         sorumlu="serdar"),
    dict(anahtar="aktif_cari", ad="Toplam aktifler · cari alacaklar", modul="kayranacc",
         sayfa="Muhasebe › Toplam Aktifler", siklik="haftalik", son_gun=0, yon="geri", tarih_turu="yukleme",
         sorumlu="serdar"),
    dict(anahtar="odeme_listesi", ad="Haftalık ödeme listesi", modul="kayranacc",
         sayfa="Muhasebe › Veri Yükleme", siklik="haftalik", son_gun=0, yon="ileri", tarih_turu="yukleme",
         sorumlu="serdar"),
    dict(anahtar="happylife", ad="Happy Life stok raporu", modul="depo", sayfa="Depo › Happy Life Kiralık Depo",
         siklik="aylik", son_gun=5, yon="geri", tarih_turu="veri", sorumlu="samet"),
    dict(anahtar="gider_tablosu", ad="Aylık gider tablosu", modul="yonetim", sayfa="Yönetim › Gider tablosu",
         siklik="aylik", son_gun=10, yon="geri", tarih_turu="veri", sorumlu="serdar"),
    dict(anahtar="g5f_sayim", ad="G5F stok sayımı", modul="kayranpm", sayfa="Ürün Yönetimi › Veri Yükleme",
         siklik="ceyreklik", son_gun=15, yon="geri", tarih_turu="yukleme", sorumlu="gokhan"),
]
_KAYNAK = {k["anahtar"]: k for k in KAYNAKLAR}


# ── Saf: dönem hesapları ────────────────────────────────────────────
def donem_bas(siklik, d):
    if siklik == "haftalik":
        return d - timedelta(days=d.weekday())
    if siklik == "aylik":
        return d.replace(day=1)
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def _ay_ekle(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def sonraki(siklik, p):
    if siklik == "haftalik":
        return p + timedelta(days=7)
    return _ay_ekle(p, 1 if siklik == "aylik" else 3)


def onceki(siklik, p):
    if siklik == "haftalik":
        return p - timedelta(days=7)
    return _ay_ekle(p, -1 if siklik == "aylik" else -3)


def vade(siklik, p, son_gun, yon="geri"):
    """p döneminin son günü."""
    taban = sonraki(siklik, p) if yon == "geri" else p
    if siklik == "haftalik":
        return taban + timedelta(days=int(son_gun) % 7)
    return taban + timedelta(days=max(1, min(28, int(son_gun))) - 1)


def donem_adi(siklik, p):
    if siklik == "haftalik":
        son = p + timedelta(days=6)
        return f"Hafta {p.isocalendar()[1]} ({p:%d.%m}–{son:%d.%m})"
    if siklik == "aylik":
        return f"{AYLAR[p.month - 1]} {p.year}"
    return f"{p.year} Ç{(p.month - 1) // 3 + 1}"


def kapsanan(siklik, tarih, tarih_turu="veri", yon="geri"):
    """Okunan tarihin karşıladığı dönemin başı."""
    p = donem_bas(siklik, tarih)
    return onceki(siklik, p) if (tarih_turu == "yukleme" and yon == "geri") else p


def _gun_metni(d):
    return f"{d:%d.%m} {GUN_KISA[d.weekday()]}"


def zorunlu_donem(k, gun):
    """gun itibarıyla son günü GEÇMİŞ en yeni dönem."""
    s, g, yon = k["siklik"], k["son_gun"], k.get("yon", "geri")
    p = donem_bas(s, gun)
    while vade(s, p, g, yon) >= gun:
        p = onceki(s, p)
    return p


def durum(k, son_tarih, bugun, atlanan=(), son_donem=None):
    """k: {siklik, son_gun, yon, tarih_turu}. son_tarih: en son okunan tarih (date|None).
    Döner: seviye (guncel|yaklasiyor|gecikti), eksik (dönem başları), gecikme_gun,
    sonraki_donem, sonraki_vade, kalan_gun, son_donem, hic."""
    s, g, yon = k["siklik"], k["son_gun"], k.get("yon", "geri")
    atl = {a if isinstance(a, date) else date.fromisoformat(str(a)[:10]) for a in (atlanan or ())}
    son_d = kapsanan(s, son_tarih, k.get("tarih_turu", "veri"), yon) if son_tarih else None
    if son_donem is not None and (son_d is None or son_donem > son_d):
        son_d = son_donem                  # takip başlangıcı: o güne kadar vadesi geçenler var sayılır

    def _var(p):
        return (son_d is not None and p <= son_d) or p in atl

    # zorunlu: son günü BUGÜNDEN ÖNCE geçmiş en yeni dönem (son gün geç sayılmaz)
    zor = zorunlu_donem(k, bugun)
    eksik = []
    p = zor
    for _ in range(GERIYE_BAKIS):
        if son_d is not None and p <= son_d:
            break                          # buradan geriye her şey yüklü
        if p not in atl:                   # "veri yok" işaretli dönem atlanır, arama sürer
            eksik.append(p)
        p = onceki(s, p)
    eksik.reverse()
    if son_d is None:
        # Hiç kayıt yok: sistem yeni başlıyor; geçmiş 6 dönemi "eksik" saymak
        # yanıltıcı olur → yalnız son zorunlu dönem istenir.
        eksik = eksik[-1:]
    nxt = sonraki(s, zor)
    while _var(nxt):
        nxt = sonraki(s, nxt)
    sv = vade(s, nxt, g, yon)
    out = {"son_donem": son_d, "hic": son_tarih is None and son_donem is None, "eksik": eksik,
           "sonraki_donem": nxt, "sonraki_vade": sv, "kalan_gun": (sv - bugun).days, "gecikme_gun": 0}
    if eksik:
        out["seviye"] = "gecikti"
        out["gecikme_gun"] = (bugun - vade(s, eksik[0], g, yon)).days
    else:
        out["seviye"] = "yaklasiyor" if out["kalan_gun"] <= YAKLASIYOR_GUN else "guncel"
    return out


# ── Saf: ayarlar ve özel okumalar ───────────────────────────────────
def kaynak_ayari(anahtar, ayarlar):
    """Varsayılan + kayıtlı ayar (bozuk değerler yok sayılır)."""
    k = dict(_KAYNAK[anahtar])
    a = (ayarlar or {}).get(anahtar) or {}
    if a.get("siklik") in SIKLIKLAR:
        k["siklik"] = a["siklik"]
    try:
        if a.get("son_gun") is not None:
            k["son_gun"] = int(a["son_gun"])
    except (TypeError, ValueError):
        pass
    k["aktif"] = (a["aktif"] is not False) if "aktif" in a else (_KAYNAK[anahtar].get("aktif", True) is not False)
    if "sorumlu" in a:
        k["sorumlu"] = str(a.get("sorumlu") or "").strip()
    k.setdefault("sorumlu", "")
    return k


# Kullanıcı adı → ekranda görünen ad (Türkçe harflerle). Listede yoksa baş harf büyür.
SORUMLU_AD = {"gokhan": "Gökhan", "cagla": "Çağla", "caglar": "Çağlar", "ibrahim": "İbrahim",
              "yilmaz": "Yılmaz"}


def sorumlu_adi(kim):
    kim = str(kim or "").strip()
    if not kim:
        return ""
    if kim.lower() in SORUMLU_AD:
        return SORUMLU_AD[kim.lower()]
    ilk = {"i": "İ", "ı": "I"}.get(kim[0], kim[0].upper())
    return ilk + kim[1:]


def gider_son_ay(yil, kat):
    """Gider tablosu {kategori: [12 ay]} → değeri olan en son ayın başı."""
    son = None
    for aylik in (kat or {}).values():
        for i, v in enumerate(list(aylik or [])[:12]):
            try:
                if float(v or 0) != 0 and (son is None or i > son):
                    son = i
            except (TypeError, ValueError):
                continue
    return date(int(yil), son + 1, 1) if son is not None else None


def _tarih(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


# ── Veritabanı okumaları (her biri kendi try'ında) ──────────────────
def _ayar(anahtar, varsayilan):
    from kayranacc.database import get_ayar
    v = get_ayar(anahtar, varsayilan)
    return v if isinstance(v, type(varsayilan)) else varsayilan


def _max_kolon(tablo, kolon, filtre=None):
    from kayranpm.database import get_client
    q = get_client().table(tablo).select(kolon)
    for a, v in (filtre or {}).items():
        q = q.eq(a, v)
    r = q.order(kolon, desc=True).limit(1).execute()
    rows = getattr(r, "data", None) or []
    return _tarih(rows[0].get(kolon)) if rows else None


def _oku_musteri_haftalik():
    return _max_kolon("firma_stok", "yukleme_tarihi")


def _oku_iade_aylik():
    return _max_kolon("iadeler", "tarih", {"kaynak": "excel"})


def _oku_aktif(tip):
    from kayranacc.database import aktif_excel_meta_oku
    return _tarih((aktif_excel_meta_oku(tip) or {}).get("yukleme_zamani"))


def _oku_happylife():
    return _max_kolon("happylife_stok", "rapor_tarihi")


def _oku_gider(bugun):
    for yil in (bugun.year, bugun.year - 1):
        g = _ayar(f"gider_tablosu_{yil}", {})
        d = gider_son_ay(yil, g.get("kat") if isinstance(g, dict) else None)
        if d:
            return d
    return None


_OKUYUCU = {
    "musteri_haftalik": lambda b: _oku_musteri_haftalik(),
    "iade_aylik": lambda b: _oku_iade_aylik(),
    "aktif_stok": lambda b: _oku_aktif("stok"),
    "aktif_ithalat": lambda b: _oku_aktif("ithalat"),
    "aktif_cari": lambda b: _oku_aktif("cari"),
    "happylife": lambda b: _oku_happylife(),
    "gider_tablosu": _oku_gider,
}


def _takip_baslangici(anahtar, bugun):
    """Kaynağın takibe alındığı gün (ilk görüldüğünde sistem_ayarlari'na yazılır)."""
    try:
        b = _ayar("yukleme_takvimi_baslangic", {})
        if anahtar not in b:
            from kayranacc.database import set_ayar
            b[anahtar] = bugun.isoformat()
            set_ayar("yukleme_takvimi_baslangic", b)
        return _tarih(b[anahtar]) or bugun
    except Exception:  # noqa: BLE001
        return bugun


def _bugun():
    try:
        from shared.utils import tr_today
        return tr_today()
    except Exception:  # noqa: BLE001
        return date.today()


def durumlar(bugun=None):
    """Tüm etkin kaynakların durumu (önbellek: tum_durumlar)."""
    from shared.hata_log import kaydet as _hata
    bugun = bugun or _bugun()
    try:
        ayarlar = _ayar(AYAR_ANAHTAR, {})
        kayitlar = _ayar(KAYIT_ANAHTAR, {})
        atla = _ayar(ATLA_ANAHTAR, {})
    except Exception as e:  # noqa: BLE001
        _hata("yukleme_takvimi.ayar", e)
        ayarlar, kayitlar, atla = {}, {}, {}
    out = []
    for kd in KAYNAKLAR:
        a = kd["anahtar"]
        k = kaynak_ayari(a, ayarlar)
        if not k["aktif"]:
            continue
        son = None
        if a in _OKUYUCU:
            try:
                son = _OKUYUCU[a](bugun)
            except Exception as e:  # noqa: BLE001
                _hata(f"yukleme_takvimi.{a}", e)
        kayit = kayitlar.get(a) or {}
        kt = _tarih(kayit.get("tarih"))
        if kt and k["tarih_turu"] == "yukleme" and (son is None or kt > son):
            son = kt                       # kanca kaydı (yükleme anı)
        baslangic, son_donem = False, None
        if son is None and a not in _OKUYUCU:
            # Yalnız yükleme anında kaydedilen kaynakların GEÇMİŞİ yok: ilk gün
            # "hiç yüklenmedi · 79 gün gecikti" yanlış alarmı olurdu. Takip kurulum
            # günü başlar: o gün son günü GEÇMİŞ dönemler var sayılır, SIRADAKİ beklenir.
            baslangic = True
            son_donem = zorunlu_donem(k, _takip_baslangici(a, bugun))
        d = durum(k, son, bugun, atla.get(a) or [], son_donem=son_donem)
        d["baslangic"] = baslangic
        d.update(anahtar=a, ad=k["ad"], modul=k["modul"], sayfa=k["sayfa"], siklik=k["siklik"],
                 sorumlu=k["sorumlu"], sorumlu_ad=sorumlu_adi(k["sorumlu"]),
                 son_gun=k["son_gun"], yon=k["yon"], son_tarih=son, kim=kayit.get("kim", ""),
                 eksik_adlar=[donem_adi(k["siklik"], p) for p in d["eksik"]],
                 sonraki_adi=donem_adi(k["siklik"], d["sonraki_donem"]),
                 son_adi=donem_adi(k["siklik"], d["son_donem"]) if d["son_donem"] else "",
                 vade_metni=_gun_metni(d["sonraki_vade"]))
        out.append(d)
    return out


try:
    import streamlit as _st

    @_st.cache_data(ttl=300, show_spinner=False)
    def tum_durumlar(bugun_iso):
        return durumlar(date.fromisoformat(bugun_iso))
except Exception:  # noqa: BLE001 — streamlit yoksa (betikler) önbelleksiz
    def tum_durumlar(bugun_iso):
        return durumlar(date.fromisoformat(bugun_iso))


def _temizle():
    try:
        tum_durumlar.clear()
    except Exception:  # noqa: BLE001
        pass


# ── Yazma: kayıt kancası, atla, ayar ────────────────────────────────
def kaydet(anahtar, kim="", adet=None):
    """Başarılı yüklemeden sonra çağır. Asla hata fırlatmaz (yüklemeyi bozmasın)."""
    try:
        from kayranacc.database import set_ayar
        k = _ayar(KAYIT_ANAHTAR, {})
        k[anahtar] = {"tarih": datetime.now().isoformat(timespec="seconds"), "kim": kim or "",
                      "adet": adet}
        set_ayar(KAYIT_ANAHTAR, k)
        _temizle()
    except Exception as e:  # noqa: BLE001
        try:
            from shared.hata_log import kaydet as _hata
            _hata(f"yukleme_takvimi.kaydet.{anahtar}", e)
        except Exception:  # noqa: BLE001
            pass


def atla(anahtar, donem):
    """'Bu dönem veri yok' — dönem eksik sayılmaz."""
    from kayranacc.database import set_ayar
    a = _ayar(ATLA_ANAHTAR, {})
    liste = set(a.get(anahtar) or [])
    liste.add(donem.isoformat() if isinstance(donem, date) else str(donem)[:10])
    a[anahtar] = sorted(liste)[-24:]
    ok = set_ayar(ATLA_ANAHTAR, a)
    _temizle()
    return ok


def ayar_kaydet(yeni):
    from kayranacc.database import set_ayar
    ok = set_ayar(AYAR_ANAHTAR, yeni)
    _temizle()
    return ok


# ── Ekran: yükleme sayfalarının üstündeki şerit ─────────────────────
SEVIYE_RENK = {"guncel": "yesil", "yaklasiyor": "amber", "gecikti": "kirmizi"}


_BIRIM = {"haftalik": "hafta", "aylik": "ay", "ceyreklik": "çeyrek"}


def eksik_ozeti(adlar, siklik=None):
    """En çok 2 dönem: tek tek. Daha fazlası aralık olarak: '5 hafta: Hafta 35 – Hafta 39'
    (uzun gecikmede dönemler tek tek listelenince kart ve uyarı kalabalıklaşıyordu)."""
    adlar = list(adlar or [])
    if len(adlar) <= 2:
        return ", ".join(adlar)
    kisa = [a.split(" (")[0] for a in (adlar[0], adlar[-1])]
    return f"{len(adlar)} {_BIRIM.get(siklik, 'dönem')}: {kisa[0]} – {kisa[1]}"


def ozet_metni(d):
    if d["seviye"] == "gecikti":
        return (("Henüz hiç yüklenmedi · " if d.get("hic") else "")
                + f"{eksik_ozeti(d['eksik_adlar'], d.get('siklik'))} eksik · {d['gecikme_gun']} gün gecikti")
    if d["kalan_gun"] == 0:
        return f"{d['sonraki_adi']} için son gün bugün"
    return f"{d['sonraki_adi']} · {d['vade_metni']} · {d['kalan_gun']} gün kaldı"


def serit(anahtar):
    """Yükleme ekranının üstüne tek satır durum. Hata olursa sessizce çizmez."""
    try:
        import streamlit as st
        d = next((x for x in tum_durumlar(_bugun().isoformat()) if x["anahtar"] == anahtar), None)
        if not d:
            return
        r = SEVIYE_RENK[d["seviye"]]
        son = ("takip yeni başladı" if d.get("baslangic")
               else (f'son: {d["son_adi"]}' if d["son_adi"] else "henüz kayıt yok"))
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;font-size:13px;'
            f'border-left:3px solid var(--k-{r});background:color-mix(in srgb,var(--k-{r}) 9%,transparent);'
            f'border-radius:8px;padding:7px 12px;margin:2px 0 10px">'
            f'<b style="color:var(--k-{r})">{"⏰" if d["seviye"] != "guncel" else "🗓"} {ozet_metni(d)}</b>'
            f'<span style="color:var(--k-soluk)">{SIKLIKLAR[d["siklik"]].lower()} · {son}'
            + (f' · sorumlu <b style="color:var(--k-metin)">{d["sorumlu_ad"]}</b>' if d.get("sorumlu_ad") else "")
            + '</span></div>',
            unsafe_allow_html=True)
    except Exception:  # noqa: BLE001
        pass


def kart_html(d):
    """Ana sayfa 'Veri güncelliği' kartı (tek kaynak)."""
    import html as _h
    r = SEVIYE_RENK[d["seviye"]]
    cip = {"guncel": "güncel", "yaklasiyor": "yaklaşıyor", "gecikti": "gecikti"}[d["seviye"]]
    if d["seviye"] == "gecikti":
        buyuk = f'{d["gecikme_gun"]} gün'
        alt = f'gecikti · {eksik_ozeti(d["eksik_adlar"], d.get("siklik"))} eksik'
    elif d["kalan_gun"] == 0:
        buyuk, alt = "bugün", f'son gün · {d["sonraki_adi"]}'
    else:
        buyuk, alt = f'{d["kalan_gun"]} gün', f'kaldı · {d["sonraki_adi"]} · {d["vade_metni"]}'
    son = ("takip yeni başladı · ilk yükleme bekleniyor" if d.get("baslangic")
           else (d["son_adi"] or "henüz kayıt yok"))
    kim = f' · son yükleyen {_h.escape(str(d["kim"]))}' if d.get("kim") else ""
    sor = (f'<div style="font-size:12px;color:var(--k-metin);margin-top:4px">👤 {_h.escape(d["sorumlu_ad"])}</div>'
           if d.get("sorumlu_ad") else "")
    return (f'<div style="border:1px solid var(--k-kenar2);border-left:3px solid var(--k-{r});border-radius:10px;'
            f'padding:10px 12px;margin-bottom:8px;background:var(--k-yuzey1);min-height:104px">'
            f'<div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">'
            f'<div style="font-size:13px;font-weight:600;line-height:1.3">{_h.escape(d["ad"])}</div>'
            f'<span style="font-size:11px;font-weight:700;color:var(--k-{r});white-space:nowrap">{cip}</span></div>'
            f'<div style="font-family:var(--k-mono);font-size:20px;font-weight:700;color:var(--k-{r});margin-top:4px">'
            f'{buyuk}</div>'
            f'<div style="font-size:12px;color:var(--k-soluk);line-height:1.35">{_h.escape(alt)}</div>'
            f'<div style="font-size:11.5px;color:var(--k-silik);margin-top:4px">{SIKLIKLAR[d["siklik"]]} · '
            f'son: {_h.escape(son)}{kim}</div>{sor}</div>')

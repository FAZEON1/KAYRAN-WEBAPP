# -*- coding: utf-8 -*-
"""KAYRAN — Şirket kimliği ve kişiye bağlı roller için TEK KAYNAK (Ekim 2026).

NEDEN: Kimin kâr gördüğü, Claude talebini kimin onayladığı, zararına satış
e-postasını kimlerin aldığı, yükleme sorumluları, talep e-postasının yedek
alıcısı gibi bilgiler kodun içinde kişi adıyla yazılıydı (kar_gizle, claude_talep,
eposta, marj_uyari, yukleme_takvimi, app.py). Kişi değişince kod değişmesi
gerekiyordu; ürün başka bir şirkette çalışamazdı.

ŞİMDİ: Hepsi buradan okunur. Okuma sırası (ilk bulunan kazanır):
  1. kullanici_yetkileri.ozel içindeki ROL ETİKETİ (Kullanıcı yönetimi ekranından
     verilir; yalnız AKTİF kullanıcılar sayılır). Etiketi taşıyan kimse yoksa →
  2. sistem_ayarlari anahtarı (AYAR_ANAHTARI; JSON liste ya da tek ad) →
  3. aşağıdaki VARSAYILAN değerler = bugünkü davranış.
Veritabanı yoksa / okunamazsa / tohum (veritabani/32_sirket_ayarlari.sql) kurulmamışsa
3. adıma düşülür: davranış eskisiyle birebir aynıdır.

ÖNBELLEK: Mevcut önbellekli okuyucuları kullanır (shared.yetki.yetki_tablosu 60 sn —
yetki kaydı temizler; kayranacc.database.get_ayar 5 dk). get_ayar okuma hatasını
önbelleğe almadığından sistem_ayarlari sonucu burada ayrıca 60 sn saklanır (_ayar).

Bu dosya modül düzeyinde hiçbir PROJE modülü içe aktarmaz (app.py, yetki.py,
yukleme_takvimi.py en başta içe aktarır; döngü ve yavaşlık olmasın).
"""
import time

# ── Şirket kimliği ───────────────────────────────────────────────────
VARSAYILAN_KIMLIK = {
    "ad": "KAYRAN ELEKTRONİK",
    "kisa_ad": "KAYRAN",
    "talep_eposta": "ibrahim.kayran@g5fteknoloji.com",   # hiçbir talep yöneticisinin adresi yoksa yedek alıcı
    "yonetici_kullanici": "ibrahim",                      # yükleme gecikmesi kopyası vb.
}
KIMLIK_ANAHTARI = {                                       # sistem_ayarlari anahtarları
    "ad": "sirket_ad",
    "kisa_ad": "sirket_kisa_ad",
    "talep_eposta": "sirket_talep_eposta",
    "yonetici_kullanici": "sirket_yonetici_kullanici",
}

# ── Roller (kullanici_yetkileri.ozel etiketleri) ─────────────────────
ROL_KAR = "kar_gorur"                 # kâr/marj her yerde + ana sayfa finans kartları
ROL_TALEP_ONAY = "talep_onaylar"      # talebi Claude'a gönderir; PR maillerinin varsayılan alıcısı
ROL_YONETICI = "yonetici"             # ana sayfa "Yönetici araçları", gecikme kopyası, ölçüm paneli
ROL_MARJ_UYARI = "marj_uyari_alir"    # zararına satış e-postası
YUKLEME_ONEK = "yukleme_sorumlusu:"   # + yukleme_takvimi kaynak anahtarı (ör. yukleme_sorumlusu:aktif_stok)

ROLLER = (ROL_KAR, ROL_TALEP_ONAY, ROL_YONETICI, ROL_MARJ_UYARI)
ROL_ADI = {
    ROL_KAR: "Rol: finans ve kâr rakamları",
    ROL_TALEP_ONAY: "Rol: talep onaycısı (Claude)",
    ROL_YONETICI: "Rol: yönetici (ana sayfa araçları)",
    ROL_MARJ_UYARI: "Rol: zararına satış e-postası",
}

# Bugünkü değerler — rol etiketi ve ayar yoksa bunlar geçerlidir.
VARSAYILAN_ROLLER = {
    ROL_KAR: ("ibrahim",),
    ROL_TALEP_ONAY: ("ibrahim",),
    ROL_YONETICI: ("ibrahim",),
    ROL_MARJ_UYARI: ("ibrahim", "korkut", "serkan"),
}

# Dönemsel yükleme sorumluları (shared/yukleme_takvimi.KAYNAKLAR anahtarları; "" = atanmamış)
VARSAYILAN_YUKLEME = {
    "musteri_haftalik": "derya",
    "satis_dokumu": "",
    "aktif_stok": "serdar",
    "aktif_ithalat": "serdar",
    "aktif_cari": "serdar",
    "odeme_listesi": "serdar",
    "happylife": "samet",
    "gider_tablosu": "serdar",
    "g5f_sayim": "gokhan",
}

# app.py'deki modül yetkisi YEDEK listeleri — yalnız kullanici_yetkileri tablosu
# okunamazsa kullanılır (fail-open güvenlik ağı; bkz. shared/yetki.py).
_YEDEK_LISTELER = {
    "kayranacc": ("ibrahim", "derman", "cem", "pamuk", "serkan", "yilmaz", "korkut", "caglar", "serdar"),
    "kayranpm": ("ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"),
    "hesap_makinesi": ("ibrahim",),
    "ithalat": ("ibrahim", "kemal", "serkan", "derya", "gokhan", "korkut", "caglar", "cem", "pamuk", "serdar"),
    "teknikservis": ("ibrahim", "berkay", "gokhan", "cem", "pamuk", "derya", "samet", "serkan", "korkut",
                     "serdar"),
    "satis": ("ibrahim", "gokhan", "derya", "serkan", "korkut", "caglar"),
    "depo_ek": ("samet", "berkay", "selcuk", "serdar"),          # depo = kayranpm + bunlar
    "yonetim": ("ibrahim", "korkut", "serkan", "caglar", "cem"),
    "patron_panel": ("ibrahim",),
    "kullanici_yonetimi": ("ibrahim",),
}


def yedek_liste(ad):
    """app.py yedek yetki listesi — her çağrıda YENİ küme (app.py salt-okurları ekliyor)."""
    return set(_YEDEK_LISTELER.get(ad, ()))


def _norm(k):
    return str(k or "").strip().lower()


def ayar_anahtari(rol):
    """Rolün sistem_ayarlari anahtarı. Yönetici, şirket kimliğindeki anahtarı paylaşır."""
    if rol == ROL_YONETICI:
        return KIMLIK_ANAHTARI["yonetici_kullanici"]
    return "rol_" + rol


def yukleme_rolu(kaynak):
    return YUKLEME_ONEK + str(kaynak or "")


# ── Okuyucular (hata yutulur: None = "bu kaynakta yok") ───────────────
def _yetki_db():
    try:
        from shared.yetki import yetki_tablosu
        return yetki_tablosu()
    except Exception:  # noqa: BLE001 — DB yok / okunamadı → bir sonraki kaynak
        return None


_AYAR_SN = 60          # sistem_ayarlari okuması süreç içinde bu kadar saklanır
_bellek = {}           # {anahtar: (zaman, değer)} — okuma HATASI da saklanır


def _ayar(anahtar):
    """sistem_ayarlari değeri ya da None. get_ayar hatayı önbelleğe almadığı için
    (veritabanı yokken her çağrı yeni istek olurdu; kar_gorunur sayfa başına çok çağrılır)
    sonuç burada kısa süre saklanır."""
    simdi = time.monotonic()
    b = _bellek.get(anahtar)
    if b and simdi - b[0] < _AYAR_SN:
        return b[1]
    try:
        from kayranacc.database import get_ayar
        v = get_ayar(anahtar, None)
    except Exception:  # noqa: BLE001
        v = None
    _bellek[anahtar] = (simdi, v)
    return v


def temizle():
    """Ayar kaydından sonra / testlerde: saklanan sistem_ayarlari okumalarını boşalt."""
    _bellek.clear()


def _kume(v):
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple, set)):
        return set()
    return {_norm(x) for x in v if _norm(x)}


# ── Roller ───────────────────────────────────────────────────────────
def _varsayilan_rol(rol):
    if rol.startswith(YUKLEME_ONEK):
        return _kume(VARSAYILAN_YUKLEME.get(rol[len(YUKLEME_ONEK):], ""))
    return set(VARSAYILAN_ROLLER.get(rol, ()))


def rol_sahipleri(rol):
    """Rolü taşıyan kullanıcılar (küme, küçük harf). Sıra: ozel etiketi → sistem_ayarlari → varsayılan."""
    db = _yetki_db()
    if db:
        try:
            s = {_norm(k) for k, v in db.items()
                 if v.get("aktif") is not False and rol in (v.get("ozel") or ())}
        except Exception:  # noqa: BLE001
            s = set()
        if s:
            return s
    s = _kume(_ayar(ayar_anahtari(rol)))
    if s:
        return s
    return _varsayilan_rol(rol)


def rol_var_mi(kullanici, rol):
    k = _norm(kullanici)
    return bool(k) and k in rol_sahipleri(rol)


def _ilk(kume, yedek=""):
    return sorted(kume)[0] if kume else yedek


def yonetici_kullanici():
    """Tek yönetici gereken yerler (gecikme kopyası). Birden çok sahip varsa alfabetik ilki."""
    return _ilk(rol_sahipleri(ROL_YONETICI), VARSAYILAN_KIMLIK["yonetici_kullanici"])


def talep_onaycisi():
    """Talepte onaylayan yazılı değilse PR maillerinin gideceği onaycı."""
    return _ilk(rol_sahipleri(ROL_TALEP_ONAY), _ilk(set(VARSAYILAN_ROLLER[ROL_TALEP_ONAY])))


def yukleme_sorumlusu(kaynak, varsayilan=None):
    """Dönemsel yükleme kaynağının sorumlusu ("" = atanmamış).
    varsayilan verilirse 3. adımda o kullanılır (KAYNAKLAR'daki değer)."""
    rol = yukleme_rolu(kaynak)
    db = _yetki_db()
    if db:
        try:
            s = {_norm(k) for k, v in db.items()
                 if v.get("aktif") is not False and rol in (v.get("ozel") or ())}
        except Exception:  # noqa: BLE001
            s = set()
        if s:
            return _ilk(s)
    a = _ayar(ayar_anahtari(rol))
    if isinstance(a, str) and a.strip():
        return _norm(a)
    s = _kume(a)
    if s:
        return _ilk(s)
    if varsayilan is not None:
        return str(varsayilan or "").strip()
    return VARSAYILAN_YUKLEME.get(kaynak, "")


# ── Şirket kimliği ───────────────────────────────────────────────────
def kimlik(alan):
    """ad · kisa_ad · talep_eposta · yonetici_kullanici. sistem_ayarlari → varsayılan."""
    if alan == "yonetici_kullanici":
        return yonetici_kullanici()
    v = _ayar(KIMLIK_ANAHTARI.get(alan, ""))
    if isinstance(v, str) and v.strip():
        return v.strip()
    return VARSAYILAN_KIMLIK.get(alan, "")


def sirket_ad():
    return kimlik("ad")


def sirket_kisa_ad():
    return kimlik("kisa_ad")


def talep_eposta():
    return kimlik("talep_eposta")

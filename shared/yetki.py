# -*- coding: utf-8 -*-
"""KAYRAN — Kullanıcı yetkileri (veritabanı destekli).

NEDEN: Yetkiler eskiden kodda sabit listelerdi (app.py'de 10 küme, ayrıca
kayranacc/main.py ve Talep Merkezi'nde ayrı listeler). Yeni kullanıcı
eklemek üç dosyayı değiştirmeyi gerektiriyordu ve bir dosyanın eski sürümü
yüklenince yetkiler sessizce kayboluyordu (Serdar iki kez kilitlendi).

ŞİMDİ: Yetkiler Supabase 'kullanici_yetkileri' tablosunda. Ekrandan
(👥 Kullanıcı Yönetimi) değiştirilir, kod yüklemeleri onlara dokunmaz.

═══ GÜVENLİK AĞI ═══════════════════════════════════════════════════════
Tablo yoksa, boşsa ya da okunamazsa `yetki_tablosu()` None döner ve
çağıran taraf koddaki SABİT listelere düşer. Yani bir veritabanı sorunu
hiç kimseyi kilitlemez; en kötü durumda sistem eskisi gibi çalışır.
"""
import streamlit as st

TABLO = "kullanici_yetkileri"

# Ana menüdeki modüller (app.py kullanici_yetkileri anahtarlarıyla birebir)
MODULLER = ["kayranacc", "kayranpm", "depo", "ithalat", "teknikservis", "satis",
            "hesap_makinesi"]
MODUL_ADI = {"kayranacc": "Muhasebe", "kayranpm": "Ürün Yön.", "depo": "Depo",
             "ithalat": "İthalat", "teknikservis": "Teknik Servis", "satis": "Satış",
             "hesap_makinesi": "Hesap Mak."}

# Modül dışı özel yetkiler
OZEL = ["yonetim", "patron_panel", "toplam_aktifler", "talep_yonetici",
        "kullanici_yonetimi", "claude_onay", "izin_yonetimi", "izin_onay", "gider_girisi"]
OZEL_ADI = {"yonetim": "Yönetim P&L", "patron_panel": "Patron Panosu",
            "toplam_aktifler": "Toplam Aktifler", "talep_yonetici": "Talep Yöneticisi",
            "kullanici_yonetimi": "Kullanıcı Yönetimi",
            "claude_onay": "Talebi Claude'a gönderme",
            "izin_yonetimi": "İzin yönetimi (personel, rapor)",
            "izin_onay": "İzin onayı",
            "gider_girisi": "Gider tablosu yükleme"}


def _norm(k):
    return str(k or "").strip().lower()


def _liste(v):
    if not v:
        return []
    if isinstance(v, str):                       # "{a,b}" ya da "a,b" gelirse
        v = v.strip("{}").split(",")
    return [_norm(x).strip('"') for x in v if _norm(x)]


def _supabase():
    from shared.auth import _get_supabase
    return _get_supabase()


@st.cache_data(ttl=60, show_spinner=False)
def yetki_tablosu():
    """{kullanici: {"moduller": set, "ozel": set, "salt_okur": bool, "aktif": bool}}

    None → tablo yok / boş / okunamadı → çağıran SABİT listelere düşmeli.
    """
    try:
        sb = _supabase()
        if not sb:
            return None
        rows = sb.table(TABLO).select("*").execute().data or []
    except Exception:
        return None
    if not rows:
        return None
    out = {}
    for r in rows:
        k = _norm(r.get("kullanici"))
        if not k:
            continue
        out[k] = {
            "moduller": sorted(set(_liste(r.get("moduller"))) & set(MODULLER)),
            "ozel": sorted(set(_liste(r.get("ozel"))) & set(OZEL)),
            "salt_okur": bool(r.get("salt_okur")),
            "aktif": r.get("aktif") is not False,        # NULL → aktif say
        }
    return out or None


def temizle():
    """Kayıt sonrası önbelleği boşalt — değişiklik anında geçerli olsun."""
    try:
        yetki_tablosu.clear()
    except Exception:
        pass


# ── Sorgular (hepsi DB yoksa `statik` değere düşer) ─────────────────────
def moduller(kullanici, statik):
    """{modul: bool}. statik: DB yoksa kullanılacak sonuç (dict)."""
    db = yetki_tablosu()
    if db is None:
        return dict(statik)
    kayit = db.get(_norm(kullanici))
    if not kayit or not kayit["aktif"]:
        return {m: False for m in MODULLER}
    if kayit["salt_okur"]:
        return {m: True for m in MODULLER}          # salt-okur her şeyi GÖRÜR
    return {m: (m in kayit["moduller"]) for m in MODULLER}


def ozel_yetki(kullanici, ad, statik_kume):
    """Kullanıcının özel yetkisi var mı? DB yoksa statik_kume'ye bakar."""
    db = yetki_tablosu()
    k = _norm(kullanici)
    if db is None:
        return k in {_norm(x) for x in (statik_kume or ())}
    kayit = db.get(k)
    return bool(kayit and kayit["aktif"] and ad in kayit["ozel"])


def ozel_sahipleri(ad, statik_kume):
    """Özel yetkiye sahip aktif kullanıcılar (küme)."""
    db = yetki_tablosu()
    if db is None:
        return {_norm(x) for x in (statik_kume or ())}
    return {k for k, v in db.items() if v["aktif"] and ad in v["ozel"]}


def salt_okur(kullanici, statik_kume):
    db = yetki_tablosu()
    k = _norm(kullanici)
    if db is None:
        return k in {_norm(x) for x in (statik_kume or ())}
    kayit = db.get(k)
    return bool(kayit and kayit["aktif"] and kayit["salt_okur"])


def aktif_kullanicilar(statik_kume):
    db = yetki_tablosu()
    if db is None:
        return {_norm(x) for x in (statik_kume or ())}
    return {k for k, v in db.items() if v["aktif"]}


def kullanici_kaydi(kullanici):
    """Giriş kontrolü için: (db_var_mi, kayit|None)."""
    db = yetki_tablosu()
    if db is None:
        return False, None
    return True, db.get(_norm(kullanici))


# ── Yazma (yalnız Kullanıcı Yönetimi ekranı kullanır) ─────────────────────
def kaydet(kullanici, moduller_, ozel_, salt_okur_, aktif_, guncelleyen=""):
    """Tek kullanıcıyı ekle/güncelle (upsert). Döner: (ok, mesaj)."""
    k = _norm(kullanici)
    if not k:
        return False, "Kullanıcı adı boş"
    try:
        import datetime as _dt
        sb = _supabase()
        if not sb:
            return False, "Veritabanı bağlantısı yok"
        sb.table(TABLO).upsert({
            "kullanici": k,
            "moduller": sorted(set(_liste(moduller_)) & set(MODULLER)),
            "ozel": sorted(set(_liste(ozel_)) & set(OZEL)),
            "salt_okur": bool(salt_okur_),
            "aktif": bool(aktif_),
            "guncelleyen": _norm(guncelleyen),
            "guncelleme": _dt.datetime.utcnow().isoformat(),
        }, on_conflict="kullanici").execute()
        temizle()
        return True, "Kaydedildi"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"


def tablo_var_mi():
    """Tablo oluşturulmuş mu? (boş olsa da True). Ekranda kurulum uyarısı için."""
    try:
        sb = _supabase()
        if not sb:
            return False
        sb.table(TABLO).select("kullanici").limit(1).execute()
        return True
    except Exception:
        return False


def kullanici_adi_gecerli_mi(ad):
    """a-z, 0-9, _ ; 2-20 karakter. Türkçe karakter giriş sorunlarını önler."""
    import re
    return bool(re.fullmatch(r"[a-z0-9_]{2,20}", _norm(ad)))


def sifre_gecerli_mi(sifre):
    """En az 8 karakter, en az bir harf ve bir rakam."""
    s = str(sifre or "")
    return len(s) >= 8 and any(c.isalpha() for c in s) and any(c.isdigit() for c in s)

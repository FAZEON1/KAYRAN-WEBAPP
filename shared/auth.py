"""
KAYRAN — Kimlik Doğrulama Katmanı

Algoritma : PBKDF2-HMAC-SHA256 (stdlib hashlib — ek bağımlılık yok)
Salt      : 16 byte kriptografik rastgele, her şifre için benzersiz
Iterasyon : 260_000  (NIST SP 800-132 / 2023 tavsiyesi)
Timing    : hmac.compare_digest — sabit zamanlı karşılaştırma
Format    : "pbkdf2:sha256:<iter>$<salt_hex>$<hash_hex>"

Secrets yapılandırması (.streamlit/secrets.toml):
  [kullanicilar]
  ibrahim = "pbkdf2:sha256:260000$3f8a1b...$c9d2e4..."
  derman  = "pbkdf2:sha256:260000$..."

Migration (tek seferlik):
  python migrate_passwords.py
"""
import hashlib
import hmac
import secrets as _secrets
import threading as _threading
from typing import Dict

# ─ Sabitler ───────────────────────────────────────────────────────────────────────────
_ALGO       = "sha256"
_ITERATIONS = 260_000          # NIST SP 800-132 (2023)
_SALT_BYTES = 16               # 128-bit rastgele salt
_PREFIX     = "pbkdf2:sha256"  # hash format ön eki


# ─ Temel Fonksiyonlar ──────────────────────────────────────────────────────────────────

def sifre_hash_uret(sifre_duz: str, iterasyon: int = _ITERATIONS) -> str:
    """
    Düz metin şifreyi PBKDF2-SHA256 hash' e dönüştürür.
    Her çağrıda benzersiz salt üretilir; aynı şifre farklı hash verir.
    Dönen format: "pbkdf2:sha256:<iter>$<salt_hex>$<hash_hex>"
    """
    salt = _secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        hash_name=_ALGO,
        password=sifre_duz.encode("utf-8"),
        salt=salt,
        iterations=iterasyon,
        dklen=32,    # 256-bit çıktı
    )
    return f"{_PREFIX}:{iterasyon}${salt.hex()}${dk.hex()}"


def sifre_dogrula(sifre_duz: str, hash_str: str) -> bool:
    """
    Düz metin şifreyi saklı hash ile karşılaştırır.
    hmac.compare_digest ile timing attack korumalı.
    True → şifre doğru  |  False → şifre yanlış veya format geçersiz
    """
    try:
        if not str(hash_str or "").startswith(_PREFIX + ":"):
            # Düz metin (ya da tanınmayan biçimde) saklı şifre KABUL EDİLMEZ.
            # Eskiden "geçiş dönemi" diye düz metinle karşılaştırılıyordu; canlıda
            # kullanici_sifreler'deki bütün kayıtlar pbkdf2 olduğu için yol kaldırıldı
            # (Ekim 2026). Secrets [kullanicilar] listesi için de aynı kural geçerli.
            return False

        # Format: "pbkdf2:sha256:<iter>$<salt_hex>$<hash_hex>"
        parts = hash_str.split(":", 3)  # ["pbkdf2","sha256","<iter>$<salt>$<hash>"]
        if len(parts) != 3:
            return False

        seg = parts[2].split("$")
        if len(seg) != 3:
            return False

        iterasyon  = int(seg[0])
        salt_bytes = bytes.fromhex(seg[1])
        beklenen   = bytes.fromhex(seg[2])

        hesaplanan = hashlib.pbkdf2_hmac(
            hash_name=_ALGO,
            password=sifre_duz.encode("utf-8"),
            salt=salt_bytes,
            iterations=iterasyon,
            dklen=32,
        )
        return hmac.compare_digest(hesaplanan, beklenen)
    except Exception:
        return False


def kullanici_dogrula(kullanici_adi: str, sifre_duz: str, kullanicilar: Dict) -> bool:
    """
    Secrets dict' inden kullanıcıyı doğrular.
    Yalnız pbkdf2 biçimli hash kabul edilir; düz metin kayıt reddedilir.

    Args:
        kullanici_adi : Giriş formundan gelen kullanıcı adı
        sifre_duz     : Giriş formundan gelen şifre
        kullanicilar  : st.secrets["kullanicilar"] dict' i
    """
    hash_str = kullanicilar.get(kullanici_adi, "")
    if not hash_str:
        # Sahte hash hesapla → kullanıcı adı varlığı timing' den anlaşılmasın
        sifre_dogrula(sifre_duz, sifre_hash_uret("__dummy__"))
        return False
    return sifre_dogrula(sifre_duz, hash_str)


# ─ Migration Yardımcısı ──────────────────────────────────────────────────────────────────

def sifre_uret_toplu(kullanici_sifre_dict: Dict[str, str]) -> str:
    """
    Düz metin şifre sözlüğünden hazır secrets.toml bloğu üretir.
    Çıktıyı Streamlit Cloud > App Settings > Secrets editor' e yapıştır.
    """
    lines_out = ["[kullanicilar]"]
    max_len = max(len(k) for k in kullanici_sifre_dict)
    for kullanici, sifre in sorted(kullanici_sifre_dict.items()):
        h = sifre_hash_uret(sifre)
        pad = " " * (max_len - len(kullanici))
        lines_out.append(f'{kullanici}{pad} = "{h}"')
    return "\n".join(lines_out)


def hash_guncelleme_gerekli_mi(hash_str: str, hedef: int = _ITERATIONS) -> bool:
    """Hash' in iterasyon sayısı güncelse False, güncellenmesi gerekiyorsa True döner."""
    if not hash_str.startswith(_PREFIX + ":"):
        return True  # Düz metin — kesinlikle güncellenmeli
    try:
        return int(hash_str.split(":")[2].split("$")[0]) < hedef
    except Exception:
        return True


# ─ Supabase Şifre Yönetimi ──────────────────────────────────────────────────────────────

def _get_supabase():
    """Supabase client'ı döner (süreç başına TEK bağlantı — cache_resource).
    İmport hatası olursa None döner."""
    try:
        import streamlit as st

        @st.cache_resource(show_spinner=False)
        def _client_olustur():
            from supabase import create_client
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"].get("key")
            return create_client(url, key)

        return _client_olustur()
    except Exception:
        return None


def supabase_sifre_oku(kullanici_adi: str):
    """
    Supabase kullanici_sifreler tablosundan hash'i okur.
    Tablo yoksa veya kayıt yoksa None döner.
    """
    try:
        sb = _get_supabase()
        if not sb:
            return None
        res = sb.table("kullanici_sifreler").select("sifre_hash").eq("kullanici_adi", kullanici_adi).limit(1).execute()
        if res.data:
            return res.data[0]["sifre_hash"]
        return None
    except Exception:
        return None


def supabase_sifre_kaydet(kullanici_adi: str, yeni_hash: str) -> bool:
    """
    Supabase kullanici_sifreler tablosuna hash yazar (upsert).
    Başarılıysa True, hata olursa False döner.
    """
    try:
        sb = _get_supabase()
        if not sb:
            return False
        import datetime as _dt
        sb.table("kullanici_sifreler").upsert({
            "kullanici_adi": kullanici_adi,
            "sifre_hash": yeni_hash,
            "guncelleme_tarihi": _dt.datetime.utcnow().isoformat(),
        }, on_conflict="kullanici_adi").execute()
    except Exception:
        return False
    # Denetim izi: kimin şifresi, kim tarafından değişti. Hash ASLA yazılmaz.
    _guvenlik_kaydi("sifre_degisti", hedef=kullanici_adi, tablo="kullanici_sifreler")
    return True


def _guvenlik_kaydi(islem, kullanici=None, hedef="", detay=None, tablo=""):
    """shared.audit.guvenlik_kaydi'ya ince köprü; denetim yazılamazsa akış bozulmaz."""
    try:
        from shared.audit import guvenlik_kaydi
        guvenlik_kaydi(islem, kullanici=kullanici, hedef=hedef, detay=detay, tablo=tablo)
    except Exception:
        pass


def kullanici_dogrula_v2(kullanici_adi: str, sifre_duz: str, kullanicilar: dict) -> bool:
    """
    Gelişmiş doğrulama: önce Supabase'e bakar, yoksa Secrets'a düşer.

    Öncelik sırası:
      1. Supabase kullanici_sifreler tablosu (kullanıcı kendi şifresini değiştirmişse)
      2. Secrets [kullanicilar] bölümü (varsayılan / fallback)

    Args:
        kullanici_adi : Giriş formundan gelen kullanıcı adı
        sifre_duz     : Giriş formundan gelen şifre
        kullanicilar  : st.secrets["kullanicilar"] dict'i
    """
    # Kullanıcı tanımlı mı? İki kaynak:
    #   · Secrets [kullanicilar]  (eski yöntem)
    #   · 'kullanici_yetkileri' tablosu (👥 Kullanıcı Yönetimi ekranından açılanlar)
    # Tabloda PASİF işaretli kullanıcı, Secrets'ta olsa bile GİREMEZ.
    try:
        from shared.yetki import kullanici_kaydi
        _db_var, _kayit = kullanici_kaydi(kullanici_adi)
    except Exception:
        _db_var, _kayit = False, None

    if _db_var and _kayit is not None and not _kayit.get("aktif", True):
        sifre_dogrula(sifre_duz, sifre_hash_uret("__dummy__"))  # timing koruması
        return False

    _secrets_te = kullanici_adi in kullanicilar
    if not _secrets_te and _kayit is None:
        sifre_dogrula(sifre_duz, sifre_hash_uret("__dummy__"))  # timing koruması
        return False

    # 1) Supabase'de şifre var mı? (şifresini değiştirmiş ya da ekrandan açılmış)
    supabase_hash = supabase_sifre_oku(kullanici_adi) or (
        supabase_sifre_oku(kullanici_adi.strip().lower())
        if kullanici_adi != kullanici_adi.strip().lower() else None)
    if supabase_hash:
        return sifre_dogrula(sifre_duz, supabase_hash)

    # 2) Secrets'taki hash ile doğrula (fallback)
    if _secrets_te:
        return sifre_dogrula(sifre_duz, kullanicilar[kullanici_adi])
    return False            # tabloda var ama şifresi hiç atanmamış


# ── Brute-force koruması (kalıcı, kullanıcı bazlı) ───────────────────
# giris_denemeleri tablosu: kullanici_adi(PK), basarisiz_sayi, son_deneme, kilit_bitis
# Veritabanı okunamaz/yazılamazsa sayaç bu süreçte BELLEKTE tutulur (aynı eşik ve
# cezalar, kullanıcı bazlı). Eskiden DB hatasında sınırsız deneme serbestti; şimdi
# DB yokken de sınır var, ama yalnız hatalı deneme yapan kullanıcı kilitlenir.
_BF_ESIK = 5                                  # bu sayıdan itibaren kilit devreye girer
_BF_CEZA_DK = {5: 1, 6: 2, 7: 5, 8: 10}       # hata sayısı → kilit (dk); üstü 15 dk
_BF_BELLEK_SINIR = 5000                       # bellekte en çok bu kadar kullanıcı adı

_BF_BELLEK = {}                               # k → {"sayi", "kilit", "son", "db_hata"}
_BF_BELLEK_KILIT = _threading.Lock()


def _bf_now():
    import datetime as _dt
    return _dt.datetime.utcnow()


def _bf_parse(ts):
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(str(ts).replace("Z", "").split("+")[0].split(".")[0])
    except Exception:
        return None


def _bf_anahtar(kullanici_adi):
    return (kullanici_adi or "").lower().strip()


def _bellek_basarisiz(k):
    """Süreç içi sayacı artırır. Dönen: (sayi, kilit_saniye)."""
    import datetime as _dt
    simdi = _bf_now()
    with _BF_BELLEK_KILIT:
        if k not in _BF_BELLEK and len(_BF_BELLEK) >= _BF_BELLEK_SINIR:
            # En eski kayıtları at (sınırsız büyümesin); kilidi süren kayıtlar korunur
            _sira = sorted(_BF_BELLEK.items(), key=lambda kv: kv[1]["son"])
            for _ad, _e in _sira[: max(1, len(_sira) // 10)]:
                if not (_e.get("kilit") and _e["kilit"] > simdi):
                    _BF_BELLEK.pop(_ad, None)
        e = _BF_BELLEK.setdefault(k, {"sayi": 0, "kilit": None, "son": simdi, "db_hata": False})
        e["sayi"] += 1
        e["son"] = simdi
        kilit_saniye = 0
        if e["sayi"] >= _BF_ESIK:
            dk = _BF_CEZA_DK.get(e["sayi"], 15)
            e["kilit"] = simdi + _dt.timedelta(minutes=dk)
            kilit_saniye = dk * 60
        return e["sayi"], kilit_saniye


def _bellek_kontrol(k):
    """Dönen: (izin_var, kalan_saniye, db_hata)."""
    with _BF_BELLEK_KILIT:
        e = _BF_BELLEK.get(k)
        if not e:
            return True, 0, False
        if e.get("kilit"):
            kalan = (e["kilit"] - _bf_now()).total_seconds()
            if kalan > 0:
                return False, int(kalan), bool(e.get("db_hata"))
        return True, 0, bool(e.get("db_hata"))


def _bellek_db_durumu(k, hata):
    with _BF_BELLEK_KILIT:
        if k in _BF_BELLEK:
            _BF_BELLEK[k]["db_hata"] = bool(hata)


def _bellek_sifirla(k):
    with _BF_BELLEK_KILIT:
        _BF_BELLEK.pop(k, None)


def _giris_kontrol_ic(k):
    b_izin, b_kalan, b_db_hata = _bellek_kontrol(k)
    try:
        sb = _get_supabase()
        if not sb:
            raise RuntimeError("veritabanı bağlantısı yok")
        res = sb.table("giris_denemeleri").select("kilit_bitis").eq("kullanici_adi", k).limit(1).execute()
    except Exception:
        return b_izin, b_kalan               # DB okunamadı → bellek sayacı karar verir
    if res.data:
        kb = res.data[0].get("kilit_bitis")
        kbt = _bf_parse(kb) if kb else None
        if kbt:
            kalan = (kbt - _bf_now()).total_seconds()
            if kalan > 0:
                return False, int(kalan)
    # DB okundu ve kilit yok. Son hatalı deneme DB'ye YAZILAMADIYSA bellek söz sahibi.
    if not b_izin and b_db_hata:
        return False, b_kalan
    return True, 0


def giris_kontrol(kullanici_adi: str):
    """Kilit durumunu kontrol eder. Dönen: (izin_var: bool, kalan_saniye: int).
    Veritabanı okunamazsa bu süreçteki bellek sayacına bakar (sınırsız deneme yok)."""
    try:
        k = _bf_anahtar(kullanici_adi)
        if not k:
            return True, 0
        izin, kalan = _giris_kontrol_ic(k)
        if not izin:
            _guvenlik_kaydi("giris_engellendi", kullanici=k[:64], hedef=k[:64],
                            detay={"kalan_sn": kalan}, tablo="giris_denemeleri")
        return izin, kalan
    except Exception:
        return True, 0


def giris_basarisiz(kullanici_adi: str):
    """Başarısız deneme sayacını artırır, eşikte kilitler.
    Dönen: (toplam_basarisiz, kilit_saniye). DB yazılamazsa bellek sayacının değeri."""
    try:
        k = _bf_anahtar(kullanici_adi)
        if not k:
            return 0, 0
        b_sayi, b_kilit = _bellek_basarisiz(k)
        try:
            sb = _get_supabase()
            if not sb:
                raise RuntimeError("veritabanı bağlantısı yok")
            res = sb.table("giris_denemeleri").select("basarisiz_sayi").eq("kullanici_adi", k).limit(1).execute()
            sayi = ((res.data[0].get("basarisiz_sayi") or 0) if res.data else 0) + 1
            kayit = {"kullanici_adi": k, "basarisiz_sayi": sayi, "son_deneme": _bf_now().isoformat()}
            kilit_saniye = 0
            if sayi >= _BF_ESIK:
                import datetime as _dt
                dk = _BF_CEZA_DK.get(sayi, 15)
                kilit_saniye = dk * 60
                kayit["kilit_bitis"] = (_bf_now() + _dt.timedelta(minutes=dk)).isoformat()
            sb.table("giris_denemeleri").upsert(kayit, on_conflict="kullanici_adi").execute()
            _bellek_db_durumu(k, hata=False)
        except Exception:
            _bellek_db_durumu(k, hata=True)
            sayi, kilit_saniye = b_sayi, b_kilit
        _guvenlik_kaydi("giris_hatali", kullanici=k[:64], hedef=k[:64],
                        detay={"deneme": sayi, "kilit_sn": kilit_saniye}, tablo="giris_denemeleri")
        return sayi, kilit_saniye
    except Exception:
        return 0, 0


def giris_basarili(kullanici_adi: str):
    """Başarılı giriş → sayacı ve kilidi sıfırlar (DB + bellek), denetim izine yazar."""
    try:
        k = _bf_anahtar(kullanici_adi)
        if not k:
            return
        _bellek_sifirla(k)
        _guvenlik_kaydi("giris", kullanici=k[:64], hedef=k[:64], tablo="giris_denemeleri")
        sb = _get_supabase()
        if not sb:
            return
        sb.table("giris_denemeleri").upsert({
            "kullanici_adi": k, "basarisiz_sayi": 0,
            "kilit_bitis": None, "son_deneme": _bf_now().isoformat(),
        }, on_conflict="kullanici_adi").execute()
    except Exception:
        pass

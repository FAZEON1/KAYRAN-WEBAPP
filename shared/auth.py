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
        if not hash_str.startswith(_PREFIX + ":"):
            # Geçiş dönemi: düz metin şifre (migrate edilmemiş)
            # Sabit zamanlı karşılaştırma yine de uygulanır
            return hmac.compare_digest(
                sifre_duz.encode("utf-8"),
                hash_str.encode("utf-8"),
            )

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
    Hash veya düz metin formatını otomatik algılar (geçiş dönemi uyumlu).

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
        return True
    except Exception:
        return False


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
    # Kullanıcı secrets'ta tanımlı mı? (yoksa hiç kabul etme)
    if kullanici_adi not in kullanicilar:
        sifre_dogrula(sifre_duz, sifre_hash_uret("__dummy__"))  # timing koruması
        return False

    # 1) Supabase'de özel şifre var mı?
    supabase_hash = supabase_sifre_oku(kullanici_adi)
    if supabase_hash:
        return sifre_dogrula(sifre_duz, supabase_hash)

    # 2) Secrets'taki hash ile doğrula (fallback)
    return sifre_dogrula(sifre_duz, kullanicilar[kullanici_adi])


# ── Brute-force koruması (kalıcı, kullanıcı bazlı) ───────────────────
# giris_denemeleri tablosu: kullanici_adi(PK), basarisiz_sayi, son_deneme, kilit_bitis
_BF_ESIK = 5                                  # bu sayıdan itibaren kilit devreye girer
_BF_CEZA_DK = {5: 1, 6: 2, 7: 5, 8: 10}       # hata sayısı → kilit (dk); üstü 15 dk


def _bf_now():
    import datetime as _dt
    return _dt.datetime.utcnow()


def _bf_parse(ts):
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(str(ts).replace("Z", "").split("+")[0].split(".")[0])
    except Exception:
        return None


def giris_kontrol(kullanici_adi: str):
    """Kilit durumunu kontrol eder. Dönen: (izin_var: bool, kalan_saniye: int).
    Hata olursa engellemez (kullanıcıyı yanlışlıkla kilitlememek için)."""
    try:
        k = (kullanici_adi or "").lower().strip()
        if not k:
            return True, 0
        sb = _get_supabase()
        if not sb:
            return True, 0
        res = sb.table("giris_denemeleri").select("kilit_bitis").eq("kullanici_adi", k).limit(1).execute()
        if res.data:
            kb = res.data[0].get("kilit_bitis")
            kbt = _bf_parse(kb) if kb else None
            if kbt:
                kalan = (kbt - _bf_now()).total_seconds()
                if kalan > 0:
                    return False, int(kalan)
        return True, 0
    except Exception:
        return True, 0


def giris_basarisiz(kullanici_adi: str):
    """Başarısız deneme sayacını artırır, eşikte kilitler.
    Dönen: (toplam_basarisiz, kilit_saniye)."""
    try:
        k = (kullanici_adi or "").lower().strip()
        if not k:
            return 0, 0
        sb = _get_supabase()
        if not sb:
            return 0, 0
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
        return sayi, kilit_saniye
    except Exception:
        return 0, 0


def giris_basarili(kullanici_adi: str):
    """Başarılı giriş → sayacı ve kilidi sıfırlar."""
    try:
        k = (kullanici_adi or "").lower().strip()
        if not k:
            return
        sb = _get_supabase()
        if not sb:
            return
        sb.table("giris_denemeleri").upsert({
            "kullanici_adi": k, "basarisiz_sayi": 0,
            "kilit_bitis": None, "son_deneme": _bf_now().isoformat(),
        }, on_conflict="kullanici_adi").execute()
    except Exception:
        pass

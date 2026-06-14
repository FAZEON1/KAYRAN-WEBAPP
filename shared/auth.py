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

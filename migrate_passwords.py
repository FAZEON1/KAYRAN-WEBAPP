#!/usr/bin/env python3
"""
KAYRAN — Şifre Migration Script'i (tek seferlik çalıştırılır)

Mevcut secrets.toml'daki düz metin şifreleri PBKDF2-SHA256 hash'lerine
çevirir ve hazır secrets.toml bloğunu terminale yazdırır.

KULLANIM:
  1) Bu dosyayı proje kökünde çalıştır:
       python migrate_passwords.py

  2) Terminaldeki çıktıyı kopyala.

  3) Streamlit Cloud → App Settings → Secrets → Edit bölümüne git.
     [kullanicilar] bölümündeki DÜZ METİN satırları SİL.
     Kopyaladığın HASH satırlarını yapıştır.

  4) Save butonuna bas. Uygulama otomatik yeniden başlar.

  5) Bu script'i ve README'yi repoda bırakabilirsin (şifre içermiyor).

ÖRNEK ÇIKTI:
  [kullanicilar]
  cem     = "pbkdf2:sha256:260000$4a2b1c...$8f9e0d..."
  derman  = "pbkdf2:sha256:260000$7f3c8a...$2e4b6c..."
  ibrahim = "pbkdf2:sha256:260000$1d5e9f...$0a3b7c..."

NOT:
  - Her çalıştırmada farklı hash üretilir (salt rastgele) — bu normaldir.
  - Yeni hash'ler önceki giriş oturumlarını geçersiz KILMAZ (şifre aynı).
  - Eski format (düz metin) hâlâ çalışır; migrate sonrası kaldırın.
"""
import sys
import os

# Proje kökünü Python path'ine ekle (shared.auth import için)
sys.path.insert(0, os.path.dirname(__file__))

try:
    from shared.auth import sifre_uret_toplu
except ImportError as e:
    print(f"HATA: shared/auth.py bulunamadı: {e}")
    print("Bu script'i proje kökünden çalıştırın: python migrate_passwords.py")
    sys.exit(1)

# ─── BURAYA MEVCUT ŞİFRELERİ GİRİN ──────────────────────────────────────────
# secrets.toml'daki [kullanicilar] bölümüne bakarak doldurun.
# Bu dosyayı doldurup çalıştırdıktan sonra bu dict'i temizleyin
# ya da .gitignore'a ekleyin (şifre içerdiği için).
MEVCUT_SIFRELER = {
    # "kullanici_adi": "mevcut_sifre",
    # Örnekler (kendi değerlerinizle değiştirin):
    # "ibrahim": "1905",
    # "derman":  "dermanpass",
    # "cem":     "cempass",
    # "pamuk":   "pamukpass",
    # "serkan":  "serkanpass",
    # "yilmaz":  "yilmazpass",
    # "korkut":  "korkutpass",
    # "gokhan":  "gokhanpass",
    # "derya":   "deryapass",
}
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not MEVCUT_SIFRELER:
        print("=" * 60)
        print("HATA: MEVCUT_SIFRELER dict'i boş!")
        print("migrate_passwords.py dosyasını açıp")
        print("MEVCUT_SIFRELER bölümüne kullanıcı adı/şifre çiftlerini")
        print("girin, ardından tekrar çalıştırın.")
        print("=" * 60)
        sys.exit(1)

    print()
    print("=" * 60)
    print("KAYRAN — Şifre Migration")
    print("=" * 60)
    print(f"  {len(MEVCUT_SIFRELER)} kullanıcı için hash üretiliyor...")
    print(f"  Algoritma : PBKDF2-HMAC-SHA256")
    print(f"  Iterasyon : 260,000")
    print()

    result = sifre_uret_toplu(MEVCUT_SIFRELER)

    print("─" * 60)
    print("KOPYALANACAK SECRETS.TOML BLOĞU:")
    print("─" * 60)
    print(result)
    print("─" * 60)
    print()
    print("ADIMLAR:")
    print("  1) Yukarıdaki çıktıyı kopyalayın")
    print("  2) Streamlit Cloud > App Settings > Secrets > Edit")
    print("  3) Mevcut [kullanicilar] bölümünü SİLİP yapıştırın")
    print("  4) Save — uygulama otomatik yeniden başlar")
    print()
    print("Tamamlandı. Bu script'ten şifreleri temizlemeyi unutmayın.")
    print("=" * 60)

if __name__ == "__main__":
    main()

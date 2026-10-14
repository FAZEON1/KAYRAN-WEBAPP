# KAYRAN Workspace

Elektronik ürün ithalatı ve dağıtımı yapan bir şirketin iç yönetim uygulaması: ürün ve stok,
satış ve kârlılık, ithalat maliyetleri, depo, teknik servis ve muhasebe tek ekranda.
Streamlit (Python 3.12) ile yazılmıştır; veriler Supabase (PostgreSQL) üzerinde tutulur.

Sürüm: **1.0.0** (tek kaynak `shared/surum.py`; ekranda ana sayfanın alt bilgisinde).
Sürüm notları: [CHANGELOG.md](CHANGELOG.md).

## Modüller

| Modül | Klasör | Ne işe yarar |
|---|---|---|
| Ana sayfa | `app.py` | Bugün paneli, kısayollar, arama, kişi menüsü |
| Yönetim | `yonetim.py`, `yonetim_*.py` | Özet, para haritası, kanal ve ürün kârlılığı, ay kapanışı |
| Muhasebe | `kayranacc/` | Ödemeler, banka bakiyeleri, nakit akış, çekler, cari ekstre, e-Defter hazırlığı |
| İthalat | `ithalat/` | İthalat dosyaları, masraf dağıtımı, model sorgu, gümrük danışmanı |
| Ürün yönetimi | `kayranpm/` | Ürün kartları, stok yaşı, müşteri satışları, kampanya, sipariş önerisi, yurt içi alış |
| Depo | `depo/` | Depo stoku, depolar arası sevk, bekleyen sevk, SKU hareketleri |
| Satış | `satis/` | Satış girişi, satış listesi, kâr / P&L, iade |
| Teknik servis | `teknikservis/` | Mal kabul, servis kayıtları, iade, irsaliye, arıza oranı |
| Hesap makinesi | `hesap_makinesi/` | Ürün kârlılığı, kırılma noktası ve prim hesapları |
| Ortak kod | `shared/` | Yetki, tasarım, menü (`shared/gezinme.py`), ana veri kuralları, e-posta, Telegram |

Her kullanıcı yalnız yetkisi olan modülleri görür; yetkiler uygulamanın içindeki
**Kullanıcı yönetimi** sayfasından verilir.

## Yerel çalıştırma

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # ya da tam sürümlerle: pip install -r requirements.lock
mkdir -p .streamlit && $EDITOR .streamlit/secrets.toml   # aşağıdaki örneğe göre
streamlit run app.py
```

`requirements.txt` izin verilen sürüm aralıklarıdır (canlı ortam bunu kurar);
`requirements.lock` bu aralıkların çözülmüş tam sürümleridir.

### Gizli ayarlar (`.streamlit/secrets.toml`)

Dosya repoya girmez. Yalnız ANAHTAR ADLARI aşağıdadır; değerleri sistem yöneticisinden alın.

```toml
[supabase]
url = "..."                 # Supabase proje adresi
key = "..."                 # uygulama anahtarı
service_role_key = "..."    # yalnız yönetim işleri için (isteğe bağlı)

[kullanicilar]              # kullanıcı adı = şifre özeti (pbkdf2:sha256:...)
# ad = "..."

[sirket]                    # belgelerde görünen künye (isteğe bağlı; uygulamadan da girilir)
# unvan, marka, adres, vd, vkn, mersis, tel, mail

[bildirim]                  # e-posta (isteğe bağlı)
# smtp_host, smtp_port, smtp_user, smtp_pass, alici_email, aktif

[telegram]                  # Telegram bildirimi (isteğe bağlı)
# bot_token, chat_id, aktif, marj_esik_yuzde
```

Şifre özetleri `araclar/migrate_passwords.py` ile üretilebilir; kullanıcı kendi şifresini
uygulamadaki **Şifremi değiştir** sayfasından değiştirir.

## Veritabanı kurulumu

Tablolar, görünümler ve fonksiyonlar `veritabani/` klasöründeki numaralı SQL dosyalarıdır;
sırayla kurulur. Ayrıntılar: [veritabani/BENIOKU.md](veritabani/BENIOKU.md).

## Testler

Birim testleri sahte Streamlit ile çalışır; `requirements.txt`'yi bu ortama **kurmayın**
(gerçek streamlit önbelleği testler arasında sonuç sızdırır):

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pytest pandas openpyxl plotly pyflakes
python -m pytest -q
```

Sayfa testi her modülün her sayfasını gerçek Streamlit ve boş sahte veritabanıyla açar;
ayrı bir ortamda çalıştırın:

```bash
pip install "streamlit<2" "pandas<3" plotly openpyxl reportlab xlrd pytest
cd tests && python -m pytest duman -q -W ignore
```

Statik denetim (CI'da yok, yerelde): `ruff check .` — ayarı `pyproject.toml`'da
(yalnız pyflakes kuralları; bugünkü uyarılar dosya bazında taban çizgisi olarak işaretli).

## Dağıtım

- **Streamlit Cloud:** `main` dalı otomatik yayına çıkar. Değişiklikler dal + pull request ile gelir;
  "Testler" iş akışı yeşil olmadan birleştirilmez. Akış: [CONTRIBUTING.md](CONTRIBUTING.md).
- **Kendi sunucunuz (VPS):** `deploy/kurulum.sh` Docker + Caddy ile kurar, `deploy/guncelle.sh`
  her 5 dakikada `main`'i denetleyip yeniden kurar.
- Zamanlanmış görevler (gece yedeği, ölçüm, Telegram özeti) `.github/workflows/` altındadır.

## Klasörler

| Klasör | İçerik |
|---|---|
| `tests/` | Birim testleri; `tests/duman` sayfa testi; `tests/tarayici` tarayıcı taraması |
| `veritabani/` | Veritabanı kurulum SQL dosyaları |
| `araclar/` | Tek seferlik yönetim betikleri (şifre özeti üretimi, geçmiş veri doldurma SQL'i) |
| `deploy/` | Sunucu kurulumu |
| `otonom/` | Zamanlanmış bilgi işlem görevi |
| `static/` | Logo, simgeler |

## Lisans

Kapalı kaynak; G5F Teknoloji'nin iç kullanımı içindir.

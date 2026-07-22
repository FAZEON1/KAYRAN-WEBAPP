# Bayi Portalı — Faz 1

Bayilerin **kendi cari durumlarını** (Özet) ve **teknik servis / iade kayıtlarını**
(Servis Takibi) görebildiği, ana KAYRAN uygulamasından **ayrı** çalışan Streamlit portalı.

## Mimari

| Katman | Dosya | Görev |
|---|---|---|
| Giriş | `bayi_app.py` | Login kapısı + menü (Özet / Servis Takibi / Şifre) + Yönetici modu |
| Kimlik | `bayi/kimlik.py` | Bayi girişi (PBKDF2 · `shared.auth`), brute-force kilidi, oturum |
| Veri | `bayi/veri.py` | Cari bakiye okuma, bayi kullanıcı CRUD, servis okuma |
| Özet | `bayi/ozet.py` | Cari borç/alacak/net (döviz bazlı) + servis özeti |
| Servis | `bayi/servis.py` | Salt-okunur servis listesi + SLA + durum geçmişi |
| Yönetim | `bayi/yonetim.py` | Personel (admin) bayi hesabı açar/yönetir |
| Şema | `sql/bayi_kullanicilar.sql` | `bayi_kullanicilar`, `bayi_giris_denemeleri` tabloları |

## Cari verisi nereden gelir?

Bakiye için **ayrı tablo yoktur**. Kaynak, "💰 Toplam Aktifler" sayfasına yüklenen
**Cari Alacaklar Excel**'idir. Yükleme anında satır detayı (kod, unvan, döviz, borç,
alacak, bakiye) `aktif_excel_verileri` tablosuna `dosya_tipi='cari_detay'` anahtarıyla
da yazılır (bkz. `kayranacc/main.py`). Portal bu satırları okur ve bayiyi **cari_kod**
(bakiye) + **cari_unvan** (servis) ile eşleştirir.

> Not: Bu Excel bir **anlık bakiye** listesidir; tarihli hareket (ekstre) içermez.
> Dated ekstre Faz 1 kapsamı dışındadır.

## Bayi ↔ Cari eşleşmesi

- **Bakiye**: `bayi_kullanicilar.cari_kod` ↔ `cari_detay.kod` (yoksa unvan ile)
- **Servis**: `bayi_kullanicilar.cari_unvan` ↔ `ts_kayitlar.firma_bilgisi` (tam, harf duyarsız)

## Kurulum (bir kez)

1. **Tabloları oluştur**: `sql/bayi_kullanicilar.sql`'i Supabase → SQL Editor'de çalıştır.
2. **Cari detayını doldur**: Ana uygulamada "Toplam Aktifler" → Cari Alacaklar Excel'ini
   **yeniden yükle** (böylece `cari_detay` bir kez yazılır). Bundan sonra her yükleme
   otomatik günceller.
3. **Portalı çalıştır / dağıt**:
   - Yerel: `streamlit run bayi_app.py`
   - Streamlit Cloud: aynı repo, **Main file path = `bayi_app.py`** olan ikinci bir uygulama
     oluştur; aynı `secrets.toml` (supabase + kullanicilar) kullanılır.
4. **Bayi hesabı aç**: Portalda "🔑 Yönetici girişi" → personel kullanıcı adı/şifre
   (`ADMIN_KULLANICILAR`: ibrahim, derman, cem) → "Yeni Bayi Hesabı".

## Güvenlik notları

- Bayi şifreleri PBKDF2-SHA256 (`shared.auth`) ile saklanır; düz metin tutulmaz.
- Brute-force: 5 hatadan sonra kademeli kilit (`bayi_giris_denemeleri`).
- Servis sorgusu `ilike` ile **tam** unvan eşleşmesi yapar (wildcard yok) → başka
  cariye veri sızmaz.
- Portal `service_role_key` ile sunucu tarafında çalışır; anahtar tarayıcıya gitmez.

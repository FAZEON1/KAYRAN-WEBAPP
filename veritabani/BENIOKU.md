# Veritabanı şeması ve kayıtlı değişiklikler

## Dosyalar

| Dosya | Ne |
|---|---|
| `00_temel_sema.sql` | Canlı şemanın 14.10.2026 hâli: 68 tablo, görünümler, fonksiyonlar, tetikleyiciler, RLS, yetkiler. Boş veritabanını sıfırdan kurar. Tekrar çalıştırılabilir. |
| `04_…28_*.sql` | Eskiden SQL Editor'e elle yapıştırılan dosyalar. 00'dan sonra çalışınca bir şey değiştirmez (yalnız başlangıç verisi ekleyenler ekler). |
| `29_…` ve sonrası | Yeni değişiklikler. Her biri bir kez, `uygula.py` ile uygulanır. |
| `31_butunluk_onerisi.sql` | Öneri. İlk satırında `-- UYGULA: HAYIR` var; `uygula.py` onu hiç çalıştırmaz. |
| `uygula.py` | Dosyaları numara sırasıyla uygular, `sema_gecmisi` tablosuna yazar. |

`uygula.py` her dosyayı `sema_gecmisi(dosya, sha256, uygulama_zamani, uygulayan)` tablosuna yazar.
Uygulanmış bir dosyayı atlar. İçeriği sonradan değişmişse uyarır ve yeniden uygulamaz.
Varsayılan kip **kuru**dur: yalnız listeler, hiçbir şey yazmaz. Her dosya kendi işleminde çalışır,
hata veren dosya geri alınır ve sonrakiler çalışmaz. Adres canlı Supabase'i (`supabase.co` /
`supabase.com`) gösteriyorsa `--canli` olmadan hiçbir kipte çalışmaz.

Gerekenler: `pip install "psycopg[binary]"` ve `DATABASE_URL` (Supabase → Project Settings →
Database → Connection string → URI). Şifre komut geçmişine düşmesin diye `read -s` ile girin:

```
read -s DATABASE_URL && export DATABASE_URL
```

## Yeni şirket kurulumu

1. Supabase'te yeni proje açın.
2. `python veritabani/uygula.py --canli` çalıştırın. Bu kuru çalışmadır ve 00 ile tüm numaralı
   dosyaları "uygulanacak" diye listeler.
3. `python veritabani/uygula.py --canli --uygula` çalıştırın.
4. Kullanıcıları ayarlayın: `04_` dosyası KAYRAN'ın kullanıcı yetkilerini başlangıç verisi olarak yazar.
   Yeni şirkette bunları Kullanıcı Yönetimi ekranından düzeltin. `25_` de `sistem_ayarlari`'na bir satır ekler.
5. Uygulamanın gizli ayarlarına (Streamlit Secrets) yeni projenin adresini ve service_role anahtarını yazın.

Yerelde denemek için Postgres 16 ya da üstü yeterlidir. 00, Supabase'e özgü rolleri (`anon`,
`authenticated`, `service_role`) ve `storage.buckets` tablosunu yoksa kendisi oluşturur:

```
createdb kayran_deneme
DATABASE_URL=postgresql://postgres@127.0.0.1/kayran_deneme python veritabani/uygula.py --uygula
```

`KAYRAN_TEST_PG=postgresql://…/postgres` tanımlıysa `tests/test_sema.py` aynı kurulumu boş bir
veritabanında kendisi dener.

## Canlıya değişiklik

**İlk kez (bir kez):** canlıda `sema_gecmisi` tablosu henüz yok. 00–28 zaten kurulu: 14.10.2026'da
canlı şema ile "00 + 04…28" karşılaştırıldı ve birebir aynı çıktı. Bu dosyaları çalıştırmadan kayda
geçirin:

```
python veritabani/uygula.py --canli                                  # kuru: listeyi görün
python veritabani/uygula.py --canli --uygula --isaretle --kadar 28   # yalnız kaydeder
```

Elle kurulmuş başka dosya varsa (ör. 29), `--kadar` değerini ona göre büyütün. Hangisinin kurulu
olduğundan emin değilseniz önce sorun, sonra işaretleyin.

**Her yeni değişiklikte:**

1. Bir sonraki numarayla `NN_kisa_ad.sql` yazın. Dosya tekrar çalıştırılabilir olsun
   (`IF NOT EXISTS`, `CREATE OR REPLACE`). Kod, dosya kurulmadan da çalışmalı.
2. PR birleştikten sonra kuru çalıştırın: `python veritabani/uygula.py --canli`. Listede yalnız
   beklediğiniz dosya "uygulanacak" görünmeli.
3. Gerekirse önce yedek alın (Supabase → Database → Backups), sonra uygulayın:
   `python veritabani/uygula.py --canli --uygula`.
4. `DEĞİŞMİŞ` uyarısı, uygulanmış bir dosyanın sonradan düzenlendiğini gösterir. O dosyayı eski
   hâline getirin ve değişikliği yeni numaralı bir dosyaya yazın.

Canlı şemayı SQL Editor'de elle değiştirmeyin; değiştirdiyseniz aynı değişikliği numaralı bir dosyaya
yazıp `--isaretle` ile kaydedin. Aksi hâlde 00 ile canlı birbirinden ayrılır.

## 00 ile canlı arasındaki bilinen küçük farklar

- Canlıda iki fazlalık UNIQUE kısıt var (`firma_stok_firma_sku_yukleme_tarihi_key`,
  `sistem_ayarlari_anahtar_key`). Aynı kolonlarda zaten başka bir kısıt olduğu için 00'a yazılmadı.
- `yukleme_satir_geri_al` fonksiyonunun canlıdaki gövdesinde, 14_ dosyasındaki iki açıklama satırı yok.
  Bu fark davranışı etkilemez.
- Canlı Postgres 17'dir. 17'de `GRANT ALL`, 16'da olmayan MAINTAIN yetkisini de kapsar.

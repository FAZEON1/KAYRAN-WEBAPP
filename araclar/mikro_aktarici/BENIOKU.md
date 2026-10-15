# Mikro → KAYRAN aktarıcı

Mikro Jump'taki stok, cari bakiye, sipariş, fatura, iade, ithalat ve masraf kayıtlarını okuyup
Supabase'deki `mikro_*` tablolarına yazar. **Mikro'ya hiçbir şey yazmaz.** Yalnız okuma işlemi
(`SqlVeriOkuV2`, yalnız SELECT) kullanır.

- **Yer:** şirket sunucusu 10.0.1.11. Mikro API orada `http://localhost:8094` adresinde çalışıyor.
- **Sıklık:** 15 dakikada bir değişenler, her gece 03:00'te her şey baştan. Mikro'da silinen ya da
  iptal edilen kayıtlar yalnız tam aktarımda temizlenir.
- **Kilit:** iki aktarım üst üste binmez. Aynı anda başlarsa ikincisi o turu atlar (`aktarim.kilit`).

## Kurulum (bir kez)

1. **Python 3.11 veya üstü** kurun (python.org).
   - Kurarken "Install for all users" ve "Add python.exe to PATH" kutularını işaretleyin.
   - Zamanlanmış görevler SYSTEM hesabıyla çalıştığı için Python herkese kurulmalı.
2. Yönetici komut isteminde gerekli paketleri kurun:
   `py -3 -m pip install requests tzdata`
3. Bu klasörü sunucuya kopyalayın, örneğin `C:\MikroKayran`.
4. Ayar dosyasını hazırlayın:
   - `ayarlar_ornek.bat` dosyasını aynı klasöre `ayarlar.bat` adıyla kopyalayın.
   - Not Defteri'yle açıp `< >` arasındaki değerleri doldurun.
   - `ayarlar.bat` kimseyle paylaşılmaz.
5. Bağlantıyı deneyin: `baslat.bat test`.
   - Bu adım yalnız okur ve her sorgudan ilk 3 kaydı ekrana yazar; Supabase'e bir şey yazmaz.
6. İlk aktarımı yapın: `baslat.bat tam`.
7. Zamanlamayı kurun: `gorev_kur.bat` dosyasına sağ tıklayıp "Yönetici olarak çalıştır" deyin.

## Kontrol

- **Günlük:** zamanlanmış çalıştırmaların çıktısı `aktarim.log` dosyasına eklenir.
- **Son durum:** her tablonun son aktarım zamanı ve son hatası Supabase'de `mikro_senk_durum` tablosunda.
- **Görevler:** Görev Zamanlayıcısı → "KAYRAN Mikro aktarim" ve "KAYRAN Mikro tam aktarim".

## Geri alma

`gorev_kaldir.bat` dosyasını yönetici olarak çalıştırın; iki görev silinir. Supabase'deki
`mikro_*` tablolarına dokunmaz.

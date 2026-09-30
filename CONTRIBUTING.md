# Değişiklik Nasıl Yapılır

Bu repo canlı bir sistemi besliyor. Bir dosya yüklemesi, aynı dosyaya daha
önce yapılmış başka bir düzeltmeyi **sessizce silebilir** — bir günde beş kez
yaşandı. Aşağıdaki akış bunu engeller.

## Kısa kural

**`main` dalına doğrudan dosya yükleme.** Önce dal, sonra pull request, CI
yeşilse merge.

## Adım adım (GitHub arayüzünden)

1. **Dal aç.** Repo sayfasında dal seçicisine tıkla, yeni bir ad yaz
   (örn. `serdar-toplam-aktifler`), *Create branch*.

2. **Dosyayı o dala yükle.** Üstte dalın seçili olduğundan emin ol, sonra
   *Add file → Upload files*. Commit mesajına ne değiştiğini yaz.

3. **Pull request aç.** Yükleme sonrası GitHub "Compare & pull request"
   düğmesi gösterir. Tıkla, kısa bir açıklama yaz, *Create pull request*.

4. **CI'yı bekle.** 30–60 saniye içinde "Testler" kontrolü çalışır.
   - ✅ Yeşil → *Merge pull request*. Streamlit otomatik deploy eder.
   - ❌ Kırmızı → *Details*'a tıkla. `test_butunluk.py` hangi fonksiyonun
     ya da yetkinin kaybolduğunu **adıyla** söyler. Eksik olanı ekleyip aynı
     dala tekrar yükle; CI kendiliğinden yeniden koşar.

5. **Merge sonrası dalı sil.** GitHub bunu öneriyor, kabul et.

## CI ne kontrol ediyor?

| Kontrol | Ne yakalar |
|---|---|
| Sözdizimi | Bozuk Python dosyası |
| 149 birim testi | Hesaplama / mantık hataları |
| Kırık import taraması | "X'ten Y'yi import et" ama Y artık yok |
| Kritik fonksiyon listesi | Daha önce en az bir kez kaybolmuş fonksiyonlar |
| Yetki listeleri | Kullanıcı yetkilerinin geri alınması |
| Depo garanti listesi | Depo seçeneklerinin kaybolması |
| Tek kaynak kontrolleri | Aynı listenin iki yerde tekrar yazılması |
| requirements üst sınırı | Platform sürüm atlaması |

## Yeni bir düzeltme yaptığında

`tests/test_butunluk.py` içindeki ilgili listeye bir satır ekle:

- Yeni fonksiyon → `KRITIK_FONKSIYONLAR`
- Yeni kullanıcı / yetki → `BEKLENEN_YETKILER`
- Yeni depo → `test_depo_garanti_listesi_eksiksiz`

Bir kez eklenen koruma bir daha kaybolmaz.

## Acil durumda

Bir şey bozulduysa ve hemen geri almak gerekiyorsa: GitHub → *Commits* →
ilgili commit'in sağındaki `<>` → *Browse files* → dosyayı indir → yeni
dalda yükle → PR. Ya da Actions'ta son yeşil çalışmayı bul, o commit'e dön.

## Dal koruması (bir kez ayarlanır)

Settings → Branches → *Add branch protection rule*:
- Branch name pattern: `main`
- ☑ Require a pull request before merging
- ☑ Require status checks to pass → **Testler / pytest** seç
- ☑ Do not allow bypassing the above settings

Bu ayar açıldıktan sonra `main`'e testleri geçmeyen hiçbir şey giremez.

# Değişiklik günlüğü

Bu dosya KAYRAN Workspace'in sürüm notlarıdır. Sürüm numarasının tek kaynağı `shared/surum.py`
(`SURUM`); ekranda ana sayfanın alt bilgisinde "Sürüm x.y.z" olarak görünür.

Numaralama anlamsal sürümdür (BÜYÜK.KÜÇÜK.YAMA): kayıtlı veriyi ya da iş akışını bozan değişiklik
BÜYÜK, yeni özellik KÜÇÜK, düzeltme YAMA artırır. Yeni sürümde `shared/surum.py`, `pyproject.toml`
ve bu dosyanın en üst başlığı birlikte güncellenir.

## [1.0.0] — 2026-10-14

İlk numaralı sürüm. Aşağıdaki maddeler son birleşen değişikliklerin (PR #166–#202) özetidir.

### Arayüz ve tasarım
- Yeni tasarım: masaüstünde sol menü; bütün liste sayfaları ortak tablo düzeninde (#191, #197).
- Ekrandaki emojiler ikonlara çevrildi (#202); hesap sayfalarında görünüm düzeltmeleri (#199).
- Görünüm cilası: boşluklar, sayfa başlıkları, kartlarda kuruş, ürün adları (#188).
- Giriş formları yeni düzende: Satış girişi, Yurt içi alış, Yeni ithalat (#200).
- Stok kartı penceresi yeni tasarımda; sekmeler ve pencere içi tablolar yeni düzende; stok kartı
  araması üst çubukta (#192, #193, #201).
- Telefon alt menüsü bildirim rozetine yer bırakır (#176).
- Hızlandırma: sıkıştırma, tablo verisinin sütun düzeninde gönderilmesi, süzmenin tarayıcıda
  yapılması (#196).

### Ürün yönetimi ve stok
- Canlı paçal maliyet: eldeki malın maliyeti paçalın yanında (#181).
- Müşteri satışları: kategori × müşteri stok tablosu, adet ve paçal değer (#185).
- Stok yaşı: müşterilerdeki stokta kategori süzgeci; Ayarlar bölümü kaldırıldı (#186, #195).
- Tüm ürünler'e müşteri süzgeci; tıklanmayan çip ve kaymayan sayfa düzeltmeleri (#194).

### Depo, mal kabul ve iade
- Mal kabulde giriş deposu seçimi; iade Satış › İade'ye yazılır (#177).
- Depolar: mal kabulde doğrudan depoya girenler listede; giriş şekli süzgeci ve Excel sütunları (#179).
- Mal kabul: fatura ile çok kalemli iade (#180); iade faturası birim fiyatı USD ya da TL (#178).

### Muhasebe ve yönetim
- Bu hafta: ödeme masası — liste, yan detay ve toplu işlem (#190).
- Ertelenen ödemeler: satıra tıklayınca ödeme penceresi (#183); hafta etiketiyle tek tıkla hafta
  değişimi (#182).
- Yönetim P&L şeridinde karta tıklayınca ilgili bölüm açılır (#175); gider tablosunda aylık kurla USD
  görünümü (#174); gider tablosu yüklemesi için ayrı yetki (#173).
- Zararına satış uyarısı e-postayla da gönderilir (#171).

### İnsan kaynakları
- Çalışan izinleri: talep, onay, bakiye, takvim ve bordro dökümü (#166).
- İzin formu ve yıllık izin kayıt belgesi antetli PDF olarak (#167).
- İzin onayı ayrı yetki; personel kartı ve bilgilendirme e-postası düzenlemeleri (#168–#170, #172).
- Kâr görme yetkisi Kullanıcı yönetiminden verilir (#176).

### Hesap makinesi
- Prim hesabı güncellendi; prim ödemelerine not penceresi (#187).

### Kalite ve test
- Tarayıcı taraması CI'da: her sayfa gerçek tarayıcıda bilgisayar ve telefon boyutunda açılır (#198).
- Sayfa testinde Muhasebe önbelleği testler arasında temizlenir (#184).

### Paketleme
- Sürüm numarası (`shared/surum.py`) ve ekranda sürüm gösterimi; bu değişiklik günlüğü.
- `README.md`, `pyproject.toml` (proje bilgisi ve ruff ayarı), `requirements.lock` (çözülmüş tam sürümler).
- Tek seferlik betikler kök dizinden `araclar/` klasörüne taşındı.
- Kullanıcıya dönük metinler sadeleşti: eski KAYRANTS&W adresi Depo ve Teknik servis modüllerine
  yönlendirir; e-Defter ekranlarında iç geliştirme dili yerine mali mühür açıklaması; veritabanı
  bağlantı hatası mesajı sade ve doğru.

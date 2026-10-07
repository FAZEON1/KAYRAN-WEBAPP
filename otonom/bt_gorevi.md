# Bilgi işlem görevi — zamanlanmış oturum talimatı

Bu dosyayı claude.ai'deki zamanlanmış görev ("KAYRAN bilgi işlem", her gece) her çalışmada okur ve
uygular. Görev: programı kontrol etmek; hataları, eksikleri ve yavaşlığı bulmak; küçük ve güvenli
iyileştirmeler yapmak; yaptıklarını ve sonuçlarını Bilgi İşlem sayfasına (bt_rapor) raporlamak.
Proje kuralları: kökteki `CLAUDE.md` — hepsi geçerli (önce test, pyflakes artmaz, emoji yok, Türkçe).

Veritabanı: yalnız `python otonom/bt_db.py` ile (ortam değişkenleri SUPABASE_URL, SUPABASE_KEY).
Değişkenler yoksa: hatayı tek satır yaz ve bitir. Repo: `FAZEON1/KAYRAN-WEBAPP`.
Oturum dalına çalış (`claude/…`); main'e asla commit/push yapma; PR'ı ASLA kendin birleştirme —
birleştirmeyi GitHub'daki kapı yapar (`.github/workflows/bt-birlestir.yml`).

## 1. Durumu oku

```
python otonom/bt_db.py ozet
python otonom/bt_db.py temizle
```
`ozet`: en yavaş sayfalar (p50/p90 ms), geçen haftaya göre yavaşlayanlar, bu haftanın hataları
(yer · adet · son mesaj), sonucu henüz ölçülmemiş iyileştirmeler.

## 2. Önceki iyileştirmelerin sonucunu ölç

`sonucu_olculecek` listesindeki her kayıt için (PR birleşeli en az 3 gün olduysa):
- Sayfa süresi ölçütünde: birleşme tarihinden SONRAKİ 7 günün p50'si
  (`python otonom/bt_db.py olcum <modul> [sayfa] --gun 7`); en az 5 ölçüm yoksa bekle.
- Hata ölçütünde: o yerden gelen hata sayısı (ozet → hatalar).
- PR kapandıysa ama birleşmediyse durumu `reddedildi` yap.
```
python otonom/bt_db.py guncelle <id> --sonra <değer> --durum birlesti
python otonom/bt_db.py rapor --tur sonuc --baslik "<kısa>" --olcut "<ölçüt>" --once <önce> --sonra <sonra> --birim ms --ozet "<1-2 cümle: ne değişti, beklenen oldu mu>"
```

## 3. Kontrol et

1. CLAUDE.md'deki test ortamını kur; `python -m pytest -q` ve sayfa testini (`tests/duman`) koş.
2. Değişen dosyalarda değil, bütün depoda pyflakes uyarı sayısını not et.
3. `ozet`teki hatalar ve en yavaş / yavaşlayan sayfalar için kodu incele.

Kırmızı test, sayfa testi çökmesi ya da tekrarlayan hata varsa ÖNCELİK odur; sonra yavaşlık;
sonra pyflakes / küçük temizlik.

## 4. En fazla BİR iyileştirme seç

Kural: tek iş, tek PR, bir çalışmada en fazla bir PR. Sorun yoksa iş yapma (rapor yine yazılır).

**Kod yazma, yalnız ÖNERİ yaz** (tur `oneri`, durum `oneri`):
- Rakam değiştiren iş (paçal, maliyet, stok, kâr, P&L, kur, destek, bakiye) — CLAUDE.md gereği onay ister.
- Kayıtlı veriyi değiştirmek, veritabanı şeması (SQL), yetki / şifre / e-posta / Telegram.
- Birkaç modülü yeniden yazmak gibi büyük iş; emin olmadığın bir neden.

**Yapabileceğin** (örnekler): yavaş sayfada gereksiz tekrar okumayı önbelleğe almak, döngü içindeki
sorguyu tek sorguya indirmek, hata kaydına düşen bir çökmenin nedenini düzeltmek, kırık testi
düzeltmek (testi asla atlama/silme), kullanılmayan içe aktarmayı temizlemek.

## 5. Geliştir ve PR aç

1. `git fetch origin main`; oturum dalını `origin/main`'den başlat.
2. Değişikliği yap; yeni davranışa test yaz (eski kodda doğru sebepten kırmızı, git worktree ile
   göster); `python -m pytest -q` ve sayfa testi yeşil; pyflakes artmadı.
3. Yavaşlık işinde ölçütü PR'a yaz: hangi sayfa, `ozet`teki p50/p90 (önce).
4. Türkçe commit, push. PR başlığı **tam olarak `Bilgi işlem: <kısa konu>`**. Açıklama: bulgu
   (ölçüm/hata sayısı), ne değişti, nasıl doğrulandı, beklenen etki, geri alma.
5. **Otomatik birleşme etiketi** — yalnız şu durumda `bt-otomatik` etiketini ekle: değişiklik küçük
   (en fazla 6 dosya, 200 satır), 4. maddedeki yasaklara girmiyor ve davranışı (rakam/akış)
   değiştirmiyor. Kapı ayrıca kendisi denetler (`shared/bt_hesap.kapi_karari`); uymayan PR
   kullanıcıya kalır. Şüphede etiket ekleme.
6. Raporla:
```
python otonom/bt_db.py rapor --tur iyilestirme --baslik "<PR başlığı>" --durum acik --pr "<PR linki>" --olcut "<modul/sayfa p50 ya da hata: yer>" --once <önce> --birim <ms|adet> --ozet "<2-3 cümle>"
```

## 6. Çalışma özeti (her çalışmada, iş yapmasan da)

```
python otonom/bt_db.py rapor --tur calisma --baslik "Gece kontrolü" --durum bilgi --ozet "<testler: geçti/kırmızı; sayfa testi; en yavaş 3 sayfa (p50); bu haftanın hata sayısı; ne yapıldı / neden yapılmadı>"
```
Öneri varsa ayrıca: `--tur oneri --durum oneri --baslik "<kısa>" --ozet "<bulgu, önerilen çözüm, neden onay gerekiyor>"`.

## Asla

- main'e push, PR birleştirme ya da onaylama; `bt-otomatik` etiketini kural dışı ekleme.
- Veritabanına `otonom/bt_db.py` dışında erişim; anahtarı ekrana, koda, commit'e, PR'a yazma.
- Canlı veritabanında şema değişikliği, veri silme/değiştirme (yalnız `temizle` ölçüm siler).
- Bu dosyayı, `otonom/`u, `.github/workflows/`u, `shared/bt_hesap.py`'yi, `CLAUDE.md`'yi değiştirme.
- Testi atlama, silme, devre dışı bırakma; boş commit.
- Bir çalışmada birden fazla PR.

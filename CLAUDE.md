# KAYRAN WEBAPP — Claude Code rehberi

Bu dosyayı Claude Code her oturumun başında okur. Proje sahibi: İbrahim (Türkçe konuşur).
Geçmiş ve ayrıntılı devir notu: https://claude.ai/artifact/4AY9LqUaKhijmryzneJKkE

## Proje

Streamlit tabanlı iç yönetim uygulaması (Python 3.12, Supabase). `main` dalı Streamlit Cloud'a
otomatik çıkar — **main canlıdır**. Modüller: `kayranpm` (Ürün Yönetimi), `satis`, `ithalat`,
`depo`, `teknikservis`, `kayranacc` (Muhasebe), `yonetim.py`; ortak kod `shared/`; testler `tests/`.

## İlk oturumda bir kez

Repoda 39 adet `__pycache__/*.pyc` takipli (eski zip yüklemelerinden). `.gitignore` artık bunları
dışlıyor ama takipli olanlar silinmeli — ilk PR:
`git rm -r --cached $(git ls-files | grep __pycache__) && git commit -m "pyc dosyalarını takipten çıkar"`.
Ayrıca `gh auth status` ile GitHub CLI girişini doğrula.

## Teslim akışı (zip yükleme YOK)

1. `main`'i çek: `git switch main && git pull`.
2. Yeni dal aç: `git switch -c claude/<kisa-konu>`. **main'e asla doğrudan commit/push yapma.**
3. Değişiklik + test (aşağıdaki kurallar). Commit mesajı Türkçe, ne ve neden.
4. `git push -u origin HEAD` ve `gh pr create` — açıklamada: ne değişti, nasıl doğrulandı,
   doğrulanamayanlar, geri alma (PR sayfasındaki Revert).
5. CI ("Testler / pytest") yeşil olunca kullanıcıya PR linkini ver; **birleştirmeyi kullanıcı yapar.**
6. Birleşmeden sonra canlıda "cannot import name …" görülürse: uygulama bayat modülü kendisi
   tazeler (`shared/modul_tazele.py`); sürerse Streamlit Cloud → ⋮ → Reboot app.

**İstisna — bilgi işlem elemanı (Ekim 2026, kullanıcı kararı).** Her gece çalışan zamanlanmış görev
(`otonom/bt_gorevi.md`) küçük düzeltmeleri `Bilgi işlem: …` başlıklı PR olarak açar; `bt-otomatik`
etiketli ve kurallara uyan PR'ları (en fazla 6 dosya / 200 satır; para, stok, kâr, yetki, veritabanı,
`otonom/`, iş akışlarına dokunmayan; testler yeşil) GitHub iş akışı `bt-birlestir.yml` birleştirir —
karar `shared/bt_hesap.kapi_karari`'da. Bunun dışındaki her PR'ı yine kullanıcı birleştirir; bu
istisna normal oturumlara birleştirme yetkisi vermez. Rapor: Sistem › Bilgi İşlem (`bt_rapor`).

**Tek iş, tek PR.** Bir istek parça parça PR'larla teslim edilmez; envanter, tüm düzeltmeler ve
testler bitince tek PR. İstisna: canlıda çalışmayan bir şey (kullanıcıya sorarak ayrı PR).

**Aynı anda birden çok oturum çalışır — çakışma kuralı.** Kullanıcı başka oturumlarda da iş yapar;
PR'lar aynı dosyalara dokunabilir ve biri birleşince diğeri "birleştirilemez" olur.
- İşe başlamadan açık PR'lara bak; aynı dosyalara dokunan varsa kullanıcıya baştan söyle.
- Push etmeden ve PR linkini vermeden hemen önce `git fetch origin main` ve main'i dala birleştir
  (merge; başkasının dalında rebase / force-push yok). Çakışmada iki tarafın amacını da koru,
  testleri (pytest + sayfa testi) yeniden çalıştır, sonra gönder.
- PR açıkken main değişirse her bildirimde / kontrolde PR'ın birleştirilebilir durumuna bak;
  çakışma varsa kullanıcı söylemeden çöz ve push et. "Birleştirmeye hazır" demeden önce CI'ın yeşil
  VE çakışmanın olmadığını doğrula.

## Çalışma düzeni

- **Envanter → plan → onay.** Yeni işte kod yazmadan önce bulgular (tablo) ve sıralı plan;
  karar gereken noktada tek soru, önerilen seçenek söylenir.
- **Rakam değiştiren değişiklik** (paçal, maliyet, stok, kâr) için önce kullanıcı onayı; gerekirse
  önce salt okunur "önceki ↔ şimdiki" karşılaştırma ekranı.
- **Kayıtlı veriyi toplu değiştirme** (İthalat masraf dağıtımı kategori adının birebir eşleşmesine
  dayanır; kapanmış ithalatların paçalı değişir). Okumada birleştir, kayıtta mevcut yazımı koru.
- **Önce test, kırmızı kanıtı.** Yeni testler eski kodda doğru sebepten kırmızı (yanlış sayı, KeyError
  değil), yeni kodda yeşil olmalı. Eski kodu denemek için `git worktree` kullan (stash değil).
- **Statik denetim:** her değişen dosyada `pyflakes` çıktısı main'dekiyle karşılaştırılır; uyarı artmaz.
- Yeni fonksiyon → `tests/test_butunluk.py` `KRITIK_FONKSIYONLAR`; yeni modül taranacaksa
  `_TARANAN_MODULLER` dosya listesine de ekle.
- **Üslup:** Türkçe, düz yazı; sayılar "1.234,56", yüzde "%31,1"; ekranda emoji yok
  (`tests/test_emoji_siniri.py` sayıyı denetler). Kullanıcı kısa yanıt verir ("devam", "A");
  belirsizse yorumunu yazıp ilerle.

## Test ortamı

CI ile aynı kur — `requirements.txt` KURMA (gerçek streamlit `@st.cache_data` testler arasında
sonuç sızdırır, `test_maliyet_kar.py` kızarır; conftest sahte streamlit kullanır):

```
python3 -m venv .venv && . .venv/bin/activate
pip install pytest pandas openpyxl plotly pyflakes
python -m pytest -q
```

**Sayfa testi** (`tests/duman`, CI'da ayrı iş "Sayfa testi"): her modülün her sayfası gerçek Streamlit'le,
boş sahte veritabanıyla açılır; çöken sayfa kırmızı. Ayrı bir ortamda çalıştır (gerçek streamlit yukarıdaki
testleri bozar): `pip install "streamlit<2" "pandas<3" plotly openpyxl reportlab xlrd pytest` →
`cd tests && python -m pytest duman -q -W ignore`. Yeni sayfa `shared/gezinme.MODULLER`'e eklenince teste
kendiliğinden girer.

Yerelde Supabase bilgisi yoksa ekran canlı veriyle açılmaz; davranış kanıtı main'deki kodu aynı
veriyle çalıştırıp sayıları yan yana koyarak verilir.

## Ana veri kuralları (tek kaynak — kendi kopyanı yazma)

| Konu | Kullan |
|---|---|
| SKU karşılaştırma | `shared.utils.sku_anahtar` (yazımda `excel_islemler.normalize_sku` de buna devreder) |
| Kategori / marka | `shared.ana_veri`: `kategori_anahtar`, `kategori_ad`, `get_kategori_havuzu`, `kayit_degeri`, `marka_anahtar`, `marka_ad` |
| Ürün adı | `shared.ana_veri.urun_ad(sku, yedek)` — kartın adı, yoksa satırın adı |
| Paçal maliyet | `satis.database.get_pacal_map` (yoldaki parti hariç, SKU yazımları birleşik, yurt içi alış yedek) |
| Firma | `shared.utils`: `firma_kanonik`, `firma_sirala`, `firma_gorunen_ad`, `cari_eslestir`. Liste VERİDEN; "KANAL" yok (eski KANAL → DİĞER). Ekranda cari adı (D-MARKET, EERA, MONDAY BİLİŞİM). |
| Depo kırılımı | `kayranpm.database.depo_dagilimi`, `satilabilir_kontrol` |
| Alımlar | ithalat + yurt içi + yerli üretim aynı tabloda (`ithalat_dosyalari.alim_turu`); ithalat listeleri `ithalat.database.ithalat_mi` ile süzer |
| Stok yaşı | `kayranpm.stok_yasi` (FIFO, depoya giriş tarihinden; satılabilir depolar + müşteri stoğu) |

## Tuzaklar

- Python'un `.upper()` / `.lower()` Türkçe değil: "monitör".upper() → noktasız "MONITÖR".
- Ekranda bir seçeneğin biçimini değiştirirken o değeri alan BÜTÜN fonksiyonları ara (P&L süzgeci
  bir kez sayfada düzeltilip `satis_pnl` içinde unutuldu → P&L boş döndü).
- Sözlükte aynı anahtar iki kez yazılırsa sonuncusu kazanır — pyflakes "dictionary key repeated".
- Supabase tek sorguda en fazla 1000 satır döndürür: tablo okurken `_hepsi(...)` (sayfalı) kullan.
- Müşteri raporundaki SKU pazaryeri kodu olabilir (HBCV…); model kodu adda — `meta_hazirla`.
- `__pycache__` takipten çıkana kadar `git add -A` kullanma; dosyaları adıyla ekle.
- Kart etiketleri cümle düzenine iner ("D-MARKET" → "D-market"); özel ad için `ozel_ad=True`.

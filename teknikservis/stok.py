# -*- coding: utf-8 -*-
"""Teknik Servis ↔ Stok entegrasyonu.

Teknik servis / iade hareketlerini ana stok sistemine (urunler.depo_kirilim)
işler. Tek giriş noktası: kayranpm.database.stok_hareket_coklu().

═══ TASARIM İLKELERİ ═══════════════════════════════════════════════════
1) STOK HATASI ASLA KAYDI BOZMAZ.
   Her fonksiyon kendi içinde hata yakalar ve (ok, mesaj) döner. Teknik
   servis kaydı her koşulda oluşur/güncellenir; stok işlenemezse yalnızca
   uyarı gösterilir. Bir Supabase hatası yüzünden mal kabul kaybolmaz.

2) 'bizim_stok' ETKİLENMEZ.
   kayranpm._SATILABILIR_DEPOLAR = {MERKEZ DEPO, HAPPY LIFE}. Aşağıdaki
   servis/iade/outlet/2.el/hurda depoları o kümede DEĞİL — dolayısıyla
   satılabilir stok, sipariş önerileri ve stok uyarıları şişmez.

3) SERİ NO TUTULMAZ.
   Stok katmanı SKU+adet bazlıdır. Hangi seri numarasının satıldığını
   stok tarafı bilemez; bu yüzden satış eşleştirmesi Depolar'daki
   TOPLU SATIŞ ekranından elle yapılır (orada kullanıcı birimi seçer).

4) BUGÜNDEN İTİBAREN.
   Geçmiş ts_kayitlar kayıtları için geriye dönük hareket ÜRETİLMEZ —
   mevcut depo_kirilim değerleriyle çift sayım olurdu.
"""
from shared.kayit import sessiz

# Teknik Servis depo adı → ana stok sistemindeki KANONİK depo adı.
# 'teknik servis' = 'TEKNİK DEPO': ithalat ve satış-iade modülleri zaten bu
# depoyu kullanıyor; ayrı bir "servis depo" açmak ikiz depo yaratırdı.
TS_DEPO_HARITA = {
    "teknik servis": "TEKNİK DEPO",
    "iade":          "İADE DEPO",
    "outlet":        "OUTLET DEPO",
    "ikinci el":     "İKİNCİ EL DEPO",
    "hurda":         "HURDA DEPO",
    "merkez":        "MERKEZ DEPO",
    "pazarlama":     "PAZARLAMA",
    "yedek parça":   "YEDEK PARÇA DEPO",
}

# Mal kabulde arayüze göre ürünün gireceği VARSAYILAN depo
ARAYUZ_DEPO = {"teknik": "TEKNİK DEPO", "iade": "İADE DEPO"}

# Mal kabulde seçilebilen giriş depoları (Ekim 2026, kullanıcı kararı): müşteriden alınan
# iade çoğu zaman doğrudan satılacağı için İADE DEPO yerine satılabilir depoya (MERKEZ / HAPPY
# LIFE) da girebilir. İlk sıradaki, "iade" türünün varsayılanıdır; "teknik" TEKNİK DEPO ile açılır.
MAL_KABUL_DEPOLAR = ["İADE DEPO", "MERKEZ DEPO", "HAPPY LIFE", "TEKNİK DEPO", "ASEL DEPO"]

# Teknik servis / 2.el satışının işareti. Ekim 2026'ya kadar satislar.kanal'a yazılıyordu
# (P&L'de ayrı kanal); artık kanal diğer satışlar gibi CARİ adı, bu işaret satış notunun
# başında durur (ts_satisi_mi). Cari seçilmezse kanal yine bu ad olur.
TS_SATIS_KANALI = "TEKNİK SERVİS / 2.EL"


def ts_satisi_mi(satir):
    """satislar satırı teknik servis / 2.el satışı mı (eski: kanal, yeni: not başı)."""
    s = satir or {}
    return (str(s.get("kanal") or "").strip() == TS_SATIS_KANALI
            or str(s.get("notlar") or "").startswith(TS_SATIS_KANALI))


def toplu_siparis_no(an=None):
    """Toplu satışın ortak sipariş no'su: 'TS261007-114050' (manuel satıştaki S… gibi)."""
    from datetime import datetime as _dt
    return (an or _dt.now()).strftime("TS%y%m%d-%H%M%S")


def ts_depo_ad(ts_depo):
    """Teknik servis depo adını ana stok sistemindeki karşılığına çevirir."""
    a = str(ts_depo or "").strip().lower()
    return TS_DEPO_HARITA.get(a, str(ts_depo or "").strip().upper())


def _sku_ad(kayit, degisim=False):
    """Kayıttan (sku, urun_adi) çıkarır. degisim=True ise değişim ürününü verir."""
    k = kayit or {}
    if degisim:
        return (str(k.get("degisim_stok_kodu") or "").strip(),
                str(k.get("degisim_stok_adi") or "").strip())
    return (str(k.get("stok_kodu") or "").strip(),
            str(k.get("stok_adi") or "").strip())


def _uygula(sku, ad, depo, delta):
    """Tek kalemlik stok hareketi. Döner: (ok, mesaj).
    Ürün kartı yoksa otomatik boş kart açar (kart_ac=True) — hiçbir hareket
    kaybolmasın diye. Açılan kartlar mesajda bildirilir."""
    sku = str(sku or "").strip()
    if not sku:
        return False, "stok kodu boş — stok işlenmedi"
    if not delta:
        return True, ""
    try:
        from kayranpm.database import stok_hareket_coklu
        _kart_vardi = _kart_var(sku)
        uygulanan, atlanan = stok_hareket_coklu(
            {sku: delta}, depo, kart_ac=True, kart_adlar={sku: ad or ""})
        if atlanan:
            return False, f"{sku}: stok kartı açılamadı, hareket işlenmedi"
        _y = "girdi" if delta > 0 else "çıktı"
        _msg = f"{sku} · {abs(int(delta))} adet {depo} deposuna {_y}"
        if not _kart_vardi:
            _msg += " · ⚠️ ürün kartı yoktu, otomatik açıldı"
        return True, _msg
    except Exception as e:
        return False, f"stok işlenemedi ({type(e).__name__}: {str(e)[:80]})"


def _kart_var(sku):
    """Ürün kartı zaten var mı — otomatik açılanları raporlayabilmek için."""
    try:
        from kayranpm.database import get_client
        r = get_client().table("urunler").select("sku").eq("sku", sku).limit(1).execute()
        if getattr(r, "data", None):
            return True
        r2 = (get_client().table("urunler").select("sku")
              .eq("sku", sku.upper()).limit(1).execute())
        return bool(getattr(r2, "data", None))
    except Exception:
        return True          # emin değilsek uyarı basma


def giris_depo_coz(metin, arayuz=""):
    """Mal kabulde yazılan / seçilen giriş deposunu kanonik ada çevirir ('merkez' → 'MERKEZ DEPO').
    Boşsa arayüzün varsayılanı; tanınmayan ya da listede olmayan depo için None (çağıran uyarır)."""
    m = str(metin or "").strip()
    if not m:
        return ARAYUZ_DEPO.get(str(arayuz or "").strip().lower())
    try:
        from kayranpm.database import depo_kanonik
        k = depo_kanonik(m)
    except Exception:  # noqa: BLE001
        k = ts_depo_ad(m)
    return k if k in MAL_KABUL_DEPOLAR else None


# İade faturasındaki birim fiyat (KDV hariç) iki para biriminde girilebilir (Ekim 2026, kullanıcı
# kararı): USD olduğu gibi; TL, iade tarihindeki kurla USD'ye çevrilir. Raporlar (Satış › İade, P&L)
# USD okur; asıl tutar ve kullanılan kur servis kaydında saklanır.
PARA_BIRIMLERI = ["USD", "TL"]


def iade_usd(fiyat, para_birimi, kur):
    """Birim fiyat → USD. USD olduğu gibi; TL kur ile bölünür (kur yoksa / 1'den küçükse None)."""
    try:
        f = float(fiyat or 0)
    except (TypeError, ValueError):
        return None
    if str(para_birimi or "USD").strip().upper() in ("TL", "TRY", "₺"):
        try:
            k = float(kur or 0)
        except (TypeError, ValueError):
            k = 0.0
        return round(f / k, 4) if k > 1 else None
    return round(f, 4)


def kur_bul(tarih=None):
    """O günün (yoksa önceki 10 günün en yakın) USD/TL kuru; hiç yoksa güncel kur; o da yoksa None."""
    from datetime import date as _date, timedelta as _td
    try:
        t = _date.fromisoformat(str(tarih or _date.today())[:10])
    except ValueError:
        t = _date.today()
    try:
        from kayranacc.database import get_kur_araligi
        kmap = get_kur_araligi((t - _td(days=10)).isoformat(), t.isoformat()) or {}
        gun = sorted(g for g, k in kmap.items() if k and float(k) > 1)
        if gun:
            return float(kmap[gun[-1]])
    except Exception as _e:  # noqa: BLE001
        sessiz("teknikservis.stok.kur_bul", _e)
    try:
        from gunluk import get_doviz
        k = float((get_doviz() or {}).get("USD") or 0)
        return k if k > 1 else None
    except Exception:  # noqa: BLE001
        return None


def iade_fiyat_metni(kayit):
    """Servis kaydındaki iade birim fiyatının ekran metni: '$23,53' ya da '₺1.000,00 (kur 42,50 → $23,53)'."""
    from shared.tasarim import tr_sayi
    k = kayit or {}
    usd = k.get("iade_net")
    if usd in (None, ""):
        return "—"
    pb = str(k.get("iade_pb") or "USD").upper()
    if pb == "TL" and k.get("iade_fiyat") not in (None, ""):
        return (f"₺{tr_sayi(float(k['iade_fiyat']), 2)} (kur {tr_sayi(float(k.get('iade_kur') or 0), 2)}"
                f" → ${tr_sayi(float(usd), 2)})")
    return f"${tr_sayi(float(usd), 2)}"


def tutar_coz(metin):
    """Excel hücresindeki tutar: '1.234,56' (TR), '1234.56' (Excel sayısı), '1,5' → float; boş → 0;
    sayı değilse None."""
    s = str(metin if metin is not None else "").strip().replace("$", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def giris_deposu(kayit):
    """Kaydın girdiği depo: mal kabulde seçilen giris_depo (kanonik), yoksa arayüzün varsayılanı."""
    k = kayit or {}
    return giris_depo_coz(k.get("giris_depo"), k.get("arayuz")) or ARAYUZ_DEPO.get(
        str(k.get("arayuz") or "").strip().lower())


def dogrudan_giris_mi(kayit):
    """Mal kabulde varsayılandan farklı bir depoya doğrudan girdi mi (ör. iade → MERKEZ DEPO)?
    Varsayılan depo (iade → İADE DEPO, teknik → TEKNİK DEPO) ya da seçim yoksa False."""
    k = kayit or {}
    secilen = giris_depo_coz(k.get("giris_depo"), k.get("arayuz")) if str(k.get("giris_depo") or "").strip() else None
    return bool(secilen) and secilen != ARAYUZ_DEPO.get(str(k.get("arayuz") or "").strip().lower())


GIRIS_SEKILLERI = ["Mal kabulde doğrudan depoya", "Depoya transfer"]


def giris_sekli(kayit):
    """Depolar listesindeki giriş şekli: doğrudan giriş öncelikli (sonradan transfer edilse de)."""
    return GIRIS_SEKILLERI[0] if dogrudan_giris_mi(kayit) else GIRIS_SEKILLERI[1]


# ── Olay bazlı girişler ──────────────────────────────────────────────
def mal_kabul_girisi(kayit):
    """Mal kabul: seçilen giriş deposuna, seçilmediyse teknik → TEKNİK DEPO, iade → İADE DEPO. (+1)"""
    depo = giris_deposu(kayit)
    if not depo:
        return False, "arayüz belirsiz — stok işlenmedi"
    sku, ad = _sku_ad(kayit)
    return _uygula(sku, ad, depo, +1)


def iade_kaydi_yaz(kayit, tarih=None):
    """İade türündeki mal kabul, Satış › İade'deki 'manuel iade' gibi iadeler tablosuna da yazılır:
    P&L iadeyi düşer (net tutar girildiyse), ay sonu iade Excel'i yüklenirse mükerrer sayılmaz
    (kaynak='manuel' → avans). Stok BURADA işlenmez; mal_kabul_girisi zaten işledi (stok_isle=False).
    Yazılan iade satırının kimliği kayit['iade_id']'ye konur (fiyat sonradan değişince o satır
    güncellenir). Teknik servis kaydı için hiçbir şey yapmaz. Döner: (ok, mesaj)."""
    k = kayit or {}
    if str(k.get("arayuz") or "").strip().lower() != "iade":
        return True, ""
    sku, ad = _sku_ad(k)
    if not sku:
        return False, "stok kodu boş — iade kaydı açılmadı"
    try:
        from satis.database import ekle_iade
        from datetime import date as _date
        try:
            net = float(k.get("iade_net") or 0)
        except (TypeError, ValueError):
            net = 0.0
        ok, msg, iade_id = ekle_iade(str(tarih or _date.today())[:10], str(k.get("firma_bilgisi") or "").strip(),
                                     sku, ad, 1, iade_net=net, depo=giris_deposu(k), kaynak="manuel",
                                     stok_isle=False, kimlik=True)
        if not ok:
            return False, f"iade kaydı açılamadı ({msg})"
        if iade_id is not None and isinstance(kayit, dict):
            kayit["iade_id"] = iade_id
        from shared.tasarim import tr_sayi
        return True, (f"{sku} iade kaydı açıldı" + (f" · net ${tr_sayi(net, 2)}" if net else " · tutar girilmedi"))
    except Exception as e:  # noqa: BLE001
        return False, f"iade kaydı açılamadı ({type(e).__name__}: {str(e)[:80]})"


def iade_fiyat_guncelle(kayit, fiyat, para_birimi, kur=None):
    """İade faturası sonradan gelince birim fiyat girilir / düzeltilir. Servis kaydı ve bağlı iade satırı
    (Satış › İade, P&L) birlikte güncellenir. TL ise kur verilmezse kaydın mal kabul gününün kuru
    kullanılır. Bağlı iade satırı yoksa (eski kayıt) aynı SKU · firma · gün · eski tutarlı manuel iade
    aranır; bulunamazsa YENİ satır açılmaz (eski kayıtlar ay sonu Excel'iyle de girmiş olabilir —
    çift sayılmasın), yalnız servis kaydı güncellenir ve mesaj söyler.
    Döner: (ok, mesaj, alanlar) — alanlar servis kaydına yazılanlar."""
    from teknikservis.database import kayit_guncelle
    from satis.database import iade_tutar_guncelle, manuel_iade_bul
    k = kayit or {}
    pb = "TL" if str(para_birimi or "").strip().upper() in ("TL", "TRY", "₺") else "USD"
    if pb == "TL" and not kur:
        kur = kur_bul(k.get("mal_kabul_tarihi"))
    usd = iade_usd(fiyat, pb, kur)
    if usd is None:
        return False, "TL fiyat için kur bulunamadı — fiyat kaydedilmedi", {}
    alanlar = {"iade_fiyat": float(fiyat or 0), "iade_pb": pb, "iade_kur": float(kur) if pb == "TL" else None,
               "iade_net": usd}
    iade_id = k.get("iade_id")
    if not iade_id:
        iade_id = manuel_iade_bul(_sku_ad(k)[0], str(k.get("firma_bilgisi") or "").strip(),
                                  str(k.get("mal_kabul_tarihi") or "")[:10], k.get("iade_net"))
        if iade_id:
            alanlar["iade_id"] = iade_id
    if not kayit_guncelle(k.get("id"), alanlar):
        return False, "servis kaydı güncellenemedi", {}
    if not iade_id:
        return True, "Fiyat servis kaydına yazıldı; Satış › İade'de bağlı iade satırı bulunamadı (eski kayıt).", alanlar
    ok, msg = iade_tutar_guncelle(iade_id, usd)
    return ok, (f"İade tutarı güncellendi: {iade_fiyat_metni(dict(k, **alanlar))}" if ok else msg), alanlar


def gonderildi_cikisi(kayit):
    """Ürün müşteriye geri gönderildi → bulunduğu depodan (−1): depoya transfer edildiyse o depo,
    yoksa mal kabulde girdiği depo."""
    depo = (ts_depo_ad(kayit.get("depo")) if (kayit or {}).get("depo") else giris_deposu(kayit))
    if not depo:
        return False, "çıkış deposu belirlenemedi — stok işlenmedi"
    sku, ad = _sku_ad(kayit)
    return _uygula(sku, ad, depo, -1)


def degisim_cikisi(kayit):
    """Ürün değişimi: müşteriye verilen YENİ ürün MERKEZ DEPO'dan düşer (−1).
    Arızalı ürün servis deposunda kalır; depoya transferde yeri değişir."""
    sku, ad = _sku_ad(kayit, degisim=True)
    if not sku:
        return False, "değişim ürününün stok kodu boş — stok işlenmedi"
    return _uygula(sku, ad, "MERKEZ DEPO", -1)


def degisim_cari(kayit):
    """Değişimde verilen ürünün satış carisi — teknik servisin elle yazdığı 'S.K. Değişim (G5F…)' biçimi."""
    return f"S.K. Değişim ({str((kayit or {}).get('servis_form_no') or '').strip()})"


def degisim_depodan_ver(kayit, bagli, personel, durum_guncelle_fn, bugun=None):
    """Ürün değişimi, değişim ürünü Depolar'daki bir kayıttan verildi (Ekim 2026, kullanıcı kararı): o kayıt
    bedelsiz 'satıldı' olur (cari 'S.K. Değişim (G5F…)'), KENDİ deposundan düşer ve satış kaydı açılır —
    teknik servisin elle yaptığının aynısı. Bu yolda MERKEZ DEPO'dan ayrıca düşülmez (eskiden değişim ürünü
    hangi depodan verilirse verilsin MERKEZ'den de düşülüyordu: iki kez çıkış).
    Döner: [(ok, mesaj), ...]."""
    from datetime import date as _date
    cari = degisim_cari(kayit)
    sfn = str((kayit or {}).get("servis_form_no") or "").strip()
    ok = durum_guncelle_fn(bagli.get("id"), "satıldı", personel, f"Ürün değişiminde verildi: {sfn}",
                           {"satis_firma": cari, "satis_fiyati": 0.0, "bedelsiz": True,
                            "satis_tarihi": str(bugun or _date.today())[:10]})
    if not ok:
        return [(False, f"{bagli.get('servis_form_no', '')} satıldı yapılamadı — stok işlenmedi")]
    return [satis_cikisi(bagli), satis_kaydi_yaz(bagli, 0, bedelsiz=True, cari=cari)]


def depoya_transfer(kayit, hedef_ts_depo):
    """İşlemi biten ürün servis/iade deposundan hedef depoya taşınır.
    İki hareket: kaynaktan −1, hedefe +1. Döner: (ok, mesaj)."""
    sku, ad = _sku_ad(kayit)
    kaynak = (ts_depo_ad(kayit.get("depo")) if (kayit or {}).get("depo") else giris_deposu(kayit))
    hedef = ts_depo_ad(hedef_ts_depo)
    if not hedef:
        return False, "hedef depo belirsiz — stok işlenmedi"
    if kaynak == hedef:
        return True, ""
    mesajlar = []
    if kaynak:
        ok1, m1 = _uygula(sku, ad, kaynak, -1)
        if not ok1:
            return False, m1
        mesajlar.append(m1)
    ok2, m2 = _uygula(sku, ad, hedef, +1)
    if not ok2:
        # Kaynaktan düşüp hedefe ekleyememek stoğu kaybeder — geri al
        if kaynak:
            _uygula(sku, ad, kaynak, +1)
        return False, m2 + " (kaynak hareketi geri alındı)"
    mesajlar.append(m2)
    return True, " · ".join(m for m in mesajlar if m)


def evraksiz_girisi(kayit, hedef_ts_depo):
    """Evraksız ürün doğrudan hedef depoya girer (+1) — servis deposuna uğramaz."""
    sku, ad = _sku_ad(kayit)
    return _uygula(sku, ad, ts_depo_ad(hedef_ts_depo), +1)


def satis_cikisi(kayit):
    """Satılan ürün bulunduğu depodan düşer (−1): transfer edildiyse o depo, mal kabulde doğrudan
    depoya girdiyse o depo, ikisi de yoksa OUTLET DEPO (eski davranış)."""
    sku, ad = _sku_ad(kayit)
    k = kayit or {}
    depo = (ts_depo_ad(k.get("depo")) if k.get("depo")
            else (giris_deposu(k) if dogrudan_giris_mi(k) else "OUTLET DEPO"))
    return _uygula(sku, ad, depo, -1)


def _pacal(sku):
    """Ürünün ithalat paçalı (yoksa ürün kartındaki yurt içi alış) — satis.get_pacal_map
    ile, SKU 'Fazeon …' yazılı olsa bile normalize eşleşir. Okunamazsa 0."""
    try:
        from satis.database import get_pacal_map
        from shared.utils import sku_anahtar
        return float((get_pacal_map() or {}).get(sku_anahtar(sku), 0) or 0)
    except Exception:
        return 0.0


def satis_kaydi_yaz(kayit, birim_satis, tarih=None, notlar="", bedelsiz=False, cari="", siparis_no=""):
    """satislar tablosuna kayıt açar — diğer satışlar gibi: firma (kanal) = CARİ adı,
    sipariş no = verilen (toplu satış) ya da servis form no. Teknik servis / 2.el olduğu
    notun başındaki TS_SATIS_KANALI işaretinden anlaşılır (ts_satisi_mi). Cari boşsa
    kanal eskisi gibi TS_SATIS_KANALI olur.
    Birim maliyet: ithalat PAÇALI (Ekim 2026). Eskiden 0 yazılıyordu ("orijinal alışta
    giderleşti, tekrar yazmak çift sayım" gerekçesiyle); oysa bu depolara gelen ürünler
    çoğunlukla iade/değişim ürünü — iade ilk satışın maliyetini geri alıyor, ürün
    maliyetiyle stoğa dönüyor. Maliyet yazılmazsa satış %100 marjlı görünüyordu.
    Bedelsiz verilen ürünün de maliyeti yazılır (zarar olarak görünür).
    Paçal bilinmiyorsa 0 yazılır ve mesajda söylenir. Döner: (ok, mesaj)."""
    try:
        from satis.database import ekle_satis
        from datetime import date as _date
        sku, ad = _sku_ad(kayit)
        if not sku:
            return False, "stok kodu boş — satış kaydı açılmadı"
        maliyet = _pacal(sku)
        kanal = str(cari or "").strip() or TS_SATIS_KANALI
        ekle_satis(
            tarih=str(tarih or _date.today())[:10],
            kanal=kanal,
            sku=sku, urun_adi=ad,
            adet=1,
            birim_satis=0.0 if bedelsiz else float(birim_satis or 0),
            birim_maliyet=maliyet,
            notlar=(f"{TS_SATIS_KANALI} · {kayit.get('servis_form_no','')} · "
                    f"{kayit.get('depo','')} · seri {kayit.get('seri_no','')}"
                    + (f" · {notlar}" if notlar else ""))[:400],
            siparis_no=(str(siparis_no or "").strip()
                        or str(kayit.get("servis_form_no") or "").strip()),
        )
        return True, (f"{sku} satış kaydı açıldı ({kanal})"
                      + ("" if maliyet > 0 else " · paçal maliyet bulunamadı, maliyet 0 yazıldı"))
    except Exception as e:
        return False, f"satış kaydı açılamadı ({type(e).__name__}: {str(e)[:80]})"

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
}

# Mal kabulde arayüze göre ürünün gireceği depo
ARAYUZ_DEPO = {"teknik": "TEKNİK DEPO", "iade": "İADE DEPO"}

# Toplu satışta satislar tablosuna yazılacak kanal adı.
# P&L kanal bazında kırıldığı için ikinci el / outlet cirosu burada
# normal satıştan AYRI bir satır olarak görünür.
TS_SATIS_KANALI = "TEKNİK SERVİS / 2.EL"


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


# ── Olay bazlı girişler ──────────────────────────────────────────────
def mal_kabul_girisi(kayit):
    """Mal kabul: teknik → TEKNİK DEPO, iade → İADE DEPO. (+1)"""
    depo = ARAYUZ_DEPO.get(str((kayit or {}).get("arayuz") or "").strip().lower())
    if not depo:
        return False, "arayüz belirsiz — stok işlenmedi"
    sku, ad = _sku_ad(kayit)
    return _uygula(sku, ad, depo, +1)


def gonderildi_cikisi(kayit):
    """Ürün müşteriye geri gönderildi → bulunduğu servis/iade deposundan (−1)."""
    depo = (ts_depo_ad(kayit.get("depo")) if (kayit or {}).get("depo")
            else ARAYUZ_DEPO.get(str((kayit or {}).get("arayuz") or "").strip().lower()))
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


def depoya_transfer(kayit, hedef_ts_depo):
    """İşlemi biten ürün servis/iade deposundan hedef depoya taşınır.
    İki hareket: kaynaktan −1, hedefe +1. Döner: (ok, mesaj)."""
    sku, ad = _sku_ad(kayit)
    kaynak = (ts_depo_ad(kayit.get("depo")) if (kayit or {}).get("depo")
              else ARAYUZ_DEPO.get(str((kayit or {}).get("arayuz") or "").strip().lower()))
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
    """Satılan ürün bulunduğu depodan düşer (−1)."""
    sku, ad = _sku_ad(kayit)
    depo = ts_depo_ad(kayit.get("depo")) if (kayit or {}).get("depo") else "OUTLET DEPO"
    return _uygula(sku, ad, depo, -1)


def satis_kaydi_yaz(kayit, birim_satis, tarih=None, notlar="", bedelsiz=False):
    """satislar tablosuna kayıt açar — P&L'de AYRI kanal olarak görünür.
    Maliyet 0 yazılır: ikinci el / outlet ürünün maliyeti orijinal alışta
    zaten giderleşmiştir, tekrar maliyet yazmak çift sayım olur.
    Döner: (ok, mesaj)."""
    try:
        from satis.database import ekle_satis
        from datetime import date as _date
        sku, ad = _sku_ad(kayit)
        if not sku:
            return False, "stok kodu boş — satış kaydı açılmadı"
        ekle_satis(
            tarih=str(tarih or _date.today())[:10],
            kanal=TS_SATIS_KANALI,
            sku=sku, urun_adi=ad,
            adet=1,
            birim_satis=0.0 if bedelsiz else float(birim_satis or 0),
            birim_maliyet=0.0,
            notlar=(f"{kayit.get('servis_form_no','')} · "
                    f"{kayit.get('depo','')} · seri {kayit.get('seri_no','')}"
                    + (f" · {notlar}" if notlar else ""))[:400],
        )
        return True, f"{sku} satış kaydı açıldı ({TS_SATIS_KANALI})"
    except Exception as e:
        return False, f"satış kaydı açılamadı ({type(e).__name__}: {str(e)[:80]})"

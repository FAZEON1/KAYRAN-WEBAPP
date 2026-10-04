# -*- coding: utf-8 -*-
"""Sayfa kayıt defteri — modüller, sayfalar, palet ve adres çubuğu TEK listeden (Ekim 2026).

Modül menüleri seçeneklerini buradan alır: secenekler("kayranpm"). Seçenek metni
(emoji + ad) modülün içindeki eşleşmeler için olduğu gibi korunur; ekranda
menu_etiketi ile ikona çevrilir. Yeni sayfa eklerken YALNIZ buraya ekle.

Saf fonksiyonlar (test edilir): secenekler, sayfa_kodu, secenek_kodundan,
palet_ogeleri, arama_ogeleri, hedef.
"""

# ── Sayfa menüsünün yeri ────────────────────────────────────────────
# True : modül şeridinin altında sekme satırı (Ekim 2026)
# False: eskisi gibi kenar çubuğunda. Geri almak için YALNIZ bu satırı değiştir.
MENU_UST = True

# kod · ad (cümle düzeni) · ikon (material) · anahtar (modül menüsünün session anahtarı)
# sayfalar: (seçenek metni, url kodu, ad, koşul)
MODULLER = [
    {"kod": "anasayfa", "ad": "Ana sayfa", "ikon": "home"},
    {"kod": "yonetim", "ad": "Yönetim", "ikon": "monitoring", "ozel": "yonetim", "anahtar": "yon_sayfa",
     "sayfalar": [
         ("Özet", "ozet", "Özet", None),
         ("Kanal ve ürün", "kanal_urun", "Kanal ve ürün", None),
         ("Destekler ve giderler", "destek_gider", "Destekler ve giderler", None),
         ("Ay kapanışı", "ay_kapanis", "Ay kapanışı", None),
         ("Sistem", "sistem", "Sistem", None),
     ]},
    {"kod": "kayranacc", "ad": "Muhasebe", "ikon": "account_balance_wallet", "anahtar": "acc_sayfa",
     "sayfalar": [
         ("📊 Dashboard", "genel_bakis", "Genel bakış", None),
         ("💳 Bu Hafta", "bu_hafta", "Bu hafta", None),
         ("🏦 Banka Bakiyeleri", "banka", "Banka bakiyeleri", None),
         ("💰 Toplam Aktifler", "toplam_aktifler", "Toplam aktifler", "toplam_aktifler"),
         ("💸 Nakit Akış", "nakit_akis", "Nakit akış", None),
         ("📋 Firma Çekleri", "cekler", "Firma çekleri", None),
         ("🕐 Ödenenler & Geçmiş", "odenenler", "Ödenenler ve geçmiş", None),
         ("💵 Gelenler Geçmişi", "gelenler", "Gelenler geçmişi", None),
         ("⏳ Ertelenen Ödemeler", "ertelenen", "Ertelenen ödemeler", None),
         ("🧾 Cari Ekstre", "cari_ekstre", "Cari ekstre", None),
         ("📂 Veri Yükleme", "veri_yukleme", "Veri yükleme", None),
         ("📄 Raporlar & Bildirim", "raporlar", "Raporlar ve bildirim", None),
         ("📚 e-Defter", "edefter", "e-Defter", None),
     ],
     # 13 sayfa tek sekme satırına sığmıyordu → iki katlı: grup + o grubun sayfaları
     "gruplar": [
         ("genel", "Genel bakış", ["genel_bakis"]),
         ("odemeler", "Ödemeler", ["bu_hafta", "cekler", "ertelenen", "odenenler"]),
         ("nakit", "Nakit", ["banka", "nakit_akis", "toplam_aktifler", "gelenler"]),
         ("cari", "Cari", ["cari_ekstre"]),
         ("veri", "Veri ve raporlar", ["veri_yukleme", "raporlar", "edefter"]),
     ]},
    {"kod": "ithalat", "ad": "İthalat", "ikon": "directions_boat", "anahtar": "ith_sayfa",
     "sayfalar": [
         ("📋  Geçmiş İthalatlar", "gecmis", "Geçmiş ithalatlar", None),
         ("➕  Yeni İthalat", "yeni", "Yeni ithalat", None),
         ("🔍  Model Sorgu", "model_sorgu", "Model sorgu", None),
         ("💸  Masraf Detayları", "masraf", "Masraf detayları", None),
     ]},
    {"kod": "kayranpm", "ad": "Ürün yönetimi", "ikon": "inventory_2", "anahtar": "pm_sayfa",
     "sayfalar": [
         ("📊  Dashboard", "genel_bakis", "Genel bakış", None),
         ("📋  Tüm Ürünler", "tum_urunler", "Tüm ürünler", None),
         ("Stok Yaşı", "stok_yasi", "Stok yaşı", None),
         ("📈  Müşteri Satışları", "musteri_satislari", "Müşteri satışları", None),
         ("🎯  Kampanya Takip", "kampanya", "Kampanya takip", None),
         ("📦  Sipariş Önerisi", "siparis_onerisi", "Sipariş önerisi", None),
         ("💵  Yurt İçi Alış", "maliyet", "Yurt içi alış", None),
         ("🔖  Ref No Takibi", "ref_no", "Ref No takibi", None),
         ("📂  Veri Yükleme", "veri_yukleme", "Veri yükleme", None),
     ],
     # 9 sayfa tek sekme satırına sığmıyor → iki katlı (Stok yaşı eklenince, Ekim 2026)
     "gruplar": [
         ("genel", "Genel bakış", ["genel_bakis"]),
         ("urunler", "Ürün ve stok", ["tum_urunler", "stok_yasi", "maliyet"]),
         ("musteri", "Müşteri ve kampanya", ["musteri_satislari", "kampanya", "ref_no"]),
         ("siparis", "Sipariş", ["siparis_onerisi"]),
         ("veri", "Veri yükleme", ["veri_yukleme"]),
     ]},
    {"kod": "depo", "ad": "Depo", "ikon": "warehouse", "anahtar": "depo_sayfa",
     "sayfalar": [
         ("🏬 Depo Stok", "stok", "Depo stok", None),
         ("🚚 Depolar Arası Sevk", "sevk", "Depolar arası sevk", None),
         ("📦 Bekleyen Sevk Takibi", "bekleyen", "Bekleyen sevk takibi", None),
         ("🔎 SKU Hareketleri", "sku_hareket", "SKU hareketleri", None),
         ("🏭 Happy Life Kiralık Depo", "happy_life", "Happy Life kiralık depo", None),
     ]},
    {"kod": "satis", "ad": "Satış", "ikon": "point_of_sale", "anahtar": "satis_sayfa",
     "sayfalar": [
         ("🧾 Satış Girişi", "giris", "Satış girişi", None),
         ("📋 Satışlar", "satislar", "Satışlar", None),
         ("📊 Kâr / P&L", "pnl", "Kâr / P&L", "kar"),
         ("📥 İçe Aktar", "ice_aktar", "İçe aktar", None),
         ("↩️ İade", "iade", "İade", None),
     ]},
    {"kod": "teknikservis", "ad": "Teknik servis", "ikon": "construction", "anahtar": "ts_sayfa",
     "sayfalar": [
         ("📥  Mal Kabül", "mal_kabul", "Mal kabul", None),
         ("📋  Evraksız Ürün Kayıt", "evraksiz", "Evraksız ürün kayıt", None),
         ("🔧  Teknik Servis", "servis", "Teknik servis", None),
         ("↩️  İade", "iade", "İade", None),
         ("🚚  İrsaliye", "irsaliye", "İrsaliye", None),
         ("📦  Depolar", "depolar", "Depolar", None),
         ("Arıza Oranı", "ariza_orani", "Arıza oranı", None),
     ]},
    {"kod": "hesap_makinesi", "ad": "Hesap makinesi", "ikon": "calculate"},
]

# Ana sayfanın kenar çubuğundaki hesap sayfaları (modül değil, tek sayfa)
SISTEM = [
    ("soru", "Soru sor", "forum", None),
    ("cop_kutusu", "Çöp kutusu", "delete", None),
    ("yukleme_gecmisi", "Yükleme geçmişi", "history", None),
    ("veri_sagligi", "Veri sağlığı", "health_and_safety", None),
    ("sifre_degistir", "Şifremi değiştir", "key", None),
    ("kullanici_yonetimi", "Kullanıcı yönetimi", "group", "kullanici_yonetimi"),
    ("sistem_kayitlari", "Sistem kayıtları", "receipt_long", "kullanici_yonetimi"),
    ("tasarim_rehberi", "Tasarım rehberi", "palette", "kullanici_yonetimi"),
]

# Fiil ile başlayan kısayollar → bir sayfaya gider
ISLEMLER = [
    ("Yeni satış girişi", "satis/giris", "add_shopping_cart"),
    ("Yeni ithalat", "ithalat/yeni", "add_box"),
    ("Depolar arası sevk", "depo/sevk", "local_shipping"),
    ("Satış dosyası içe aktar", "satis/ice_aktar", "upload_file"),
    ("Ürün verisi yükle", "kayranpm/veri_yukleme", "upload"),
    ("Muhasebe verisi yükle", "kayranacc/veri_yukleme", "upload"),
]

_MOD = {m["kod"]: m for m in MODULLER}
_HARF = str.maketrans("çğıöşüÇĞİIÖŞÜâÂîÎ", "cgiosuCGIIOSUaAiI")


def _sade(s):
    """Arama için: küçük harf, Türkçe harfsiz ('Tüm Ürünler' → 'tum urunler')."""
    return str(s or "").translate(_HARF).lower()


def secenekler(mod):
    """Modül menüsünün seçenek metinleri (sıralı, koşulsuz — modül kendi süzer)."""
    return [s[0] for s in _MOD.get(mod, {}).get("sayfalar", [])]


def sayfa_kodu(mod, secenek):
    for s in _MOD.get(mod, {}).get("sayfalar", []):
        if s[0] == secenek:
            return s[1]
    return None


def secenek_kodundan(mod, kod):
    for s in _MOD.get(mod, {}).get("sayfalar", []):
        if s[1] == kod:
            return s[0]
    return None


def _ikon(secenek):
    try:
        from shared.tasarim import menu_etiketi
        e = menu_etiketi(secenek)
        if e.startswith(":material/"):
            return e.split(":")[1].split("/")[1]
    except Exception:
        pass
    return "chevron_right"


def palet_ogeleri(yetkiler, ozel, kullanici, kosul):
    """Paletin sabit öğeleri: sayfalar + işlemler + hesap sayfaları.
    yetkiler: {modül: bool} · ozel: kullanıcının özel yetkileri (set) ·
    kosul(ad, kullanici) → bool (kar, toplam_aktifler…)."""
    out = []
    acik = set()
    for m in MODULLER:
        k = m["kod"]
        if k == "anasayfa":
            gor = True
        elif m.get("ozel"):
            gor = m["ozel"] in ozel
        else:
            gor = bool(yetkiler.get(k))
        if not gor:
            continue
        sayfalar = m.get("sayfalar") or []
        if not sayfalar:
            out.append({"tur": "sayfa", "id": k, "ad": m["ad"], "yol": "", "ikon": m["ikon"],
                        "ara": _sade(m["ad"])})
        for sec, kod, ad, ks in sayfalar:
            if ks and not kosul(ks, kullanici):
                continue
            acik.add(f"{k}/{kod}")
            out.append({"tur": "sayfa", "id": f"{k}/{kod}", "ad": ad, "yol": m["ad"],
                        "ikon": _ikon(sec), "ara": _sade(f"{ad} {m['ad']}")})
    for ad, hid, ikon in ISLEMLER:
        if hid in acik:
            out.append({"tur": "islem", "id": hid, "ad": ad, "yol": "", "ikon": ikon, "ara": _sade(ad)})
    for kod, ad, ikon, oz in SISTEM:
        if oz and oz not in ozel:
            continue
        out.append({"tur": "sayfa", "id": f"sistem/{kod}", "ad": ad, "yol": "Hesap", "ikon": ikon,
                    "ara": _sade(ad)})
    return out


def arama_ogeleri(sonuclar):
    """shared.arama.ara() sonuçları → palet öğeleri (her biri bir hedefe gider)."""
    from shared.tablo import kisa_unvan
    o = []
    for u in (sonuclar or {}).get("urunler", []):
        sku = str(u.get("sku") or "")
        o.append({"tur": "urun", "id": f"urun:{sku}", "ad": f"{sku} · {u.get('urun_adi') or ''}".strip(" ·"),
                  "yol": "stok kartı", "ikon": "inventory_2"})
    for c in (sonuclar or {}).get("cariler", []):
        ad, tur = kisa_unvan(c.get("firma_adi"))
        o.append({"tur": "cari", "id": "kayranacc/cari_ekstre", "ad": f"{ad} {tur}".strip(),
                  "yol": "Muhasebe · cari ekstre", "ikon": "storefront"})
    for s in (sonuclar or {}).get("satislar", []):
        o.append({"tur": "satis", "id": "satis/satislar",
                  "ad": f"Sipariş {s.get('siparis_no') or '—'} · {kisa_unvan(s.get('kanal'))[0]}".strip(" ·"),
                  "yol": f"Satış · {str(s.get('tarih') or '')[:10]}", "ikon": "receipt_long"})
    for d in (sonuclar or {}).get("ithalat", []):
        b = d.get("pi_no") or d.get("dosya_no") or d.get("ithalat_takip_no") or "—"
        o.append({"tur": "ithalat", "id": "ithalat/gecmis", "ad": f"{b} · {d.get('tedarikci') or ''}".strip(" ·"),
                  "yol": "İthalat", "ikon": "directions_boat"})
    for t in (sonuclar or {}).get("servis", []):
        o.append({"tur": "servis", "id": "teknikservis/servis",
                  "ad": f"Servis {t.get('servis_form_no') or '—'} · seri {t.get('seri_no') or '—'}",
                  "yol": "Teknik servis", "ikon": "construction"})
    return o


def hedef(oge_id):
    """'kayranpm/tum_urunler' → {modul, anahtar, secenek} · 'urun:SKU' → {stok_karti: SKU}."""
    s = str(oge_id or "")
    if s.startswith("urun:"):
        return {"stok_karti": s[5:]}
    if s.startswith("sistem/"):
        kod = s[7:]
        return {"modul": kod, "anahtar": None, "secenek": None} if any(x[0] == kod for x in SISTEM) else None
    mod, _, kod = s.partition("/")
    m = _MOD.get(mod)
    if not m:
        return None
    if not kod:
        return {"modul": mod, "anahtar": None, "secenek": None}
    sec = secenek_kodundan(mod, kod)
    return {"modul": mod, "anahtar": m.get("anahtar"), "secenek": sec} if sec else None


# ── Adres çubuğu (?s=modül&p=sayfa) ─────────────────────────────────
def adres_oku():
    """Oturum başında: ?p= varsa modül menüsünü o sayfaya ayarla (yenileyince
    aynı sayfada kalınır; sayfa linki paylaşılabilir)."""
    import streamlit as st
    try:
        mod, kod = st.query_params.get("s"), st.query_params.get("p")
        m = _MOD.get(mod or "")
        sec = secenek_kodundan(mod, kod) if (m and kod) else None
        if sec and m.get("anahtar"):
            st.session_state.setdefault(m["anahtar"], sec)
    except Exception:
        pass


def adres_yaz(aktif):
    """Her çalıştırmada: aktif modülün seçili sayfasını ?p= olarak yaz.
    Widget değeri betik başlamadan oturuma yazıldığı için burada güncel."""
    import streamlit as st
    try:
        m = _MOD.get(aktif or "")
        kod = sayfa_kodu(aktif, st.session_state.get(m["anahtar"])) if (m and m.get("anahtar")) else None
        if kod:
            if st.query_params.get("p") != kod:
                st.query_params["p"] = kod
        elif "p" in st.query_params:
            del st.query_params["p"]
    except Exception:
        pass


# ── Sayfa menüsü (üstte sekme / kenar çubuğunda liste) ──────────────
def sekme_adi(mod, secenek):
    """Sekme metni: kayıt defterindeki cümle düzenli ad; yoksa ikon/emoji atılmış metin."""
    for s in _MOD.get(mod, {}).get("sayfalar", []):
        if s[0] == secenek:
            return s[2]
    try:
        from shared.tasarim import menu_etiketi
        e = menu_etiketi(secenek)
        return e.split(": ", 1)[1] if e.startswith(":material/") else e
    except Exception:
        return str(secenek)


def _ctx():
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx
        return get_script_run_ctx()
    except Exception:
        return None


def serit_kur(kap):
    """app.py, modül şeridinin hemen altındaki boş kabı verir. Oturuma (çalışma
    bağlamına) yazılır; modül global değişkeni oturumlar arasında karışırdı."""
    c = _ctx()
    if c is not None:
        try:
            setattr(c, "_kayran_sayfa_seridi", kap)
        except Exception:
            pass


def _serit():
    c = _ctx()
    return getattr(c, "_kayran_sayfa_seridi", None) if c is not None else None


def grup_yapisi(mod, secenekler):
    """[(grup adı, [seçenek…])] — yalnız verilen (yetkiyle süzülmüş) seçenekler;
    boş kalan grup atlanır. Grup tanımı yoksa []."""
    m = _MOD.get(mod, {})
    kod_sec = {s[1]: s[0] for s in m.get("sayfalar", [])}
    izin = set(secenekler)
    out = []
    for _gk, ad, kodlar in m.get("gruplar") or []:
        ss = [kod_sec[k] for k in kodlar if kod_sec.get(k) in izin]
        if ss:
            out.append((ad, ss))
    return out


def grup_adi(mod, secenek):
    for ad, ss in grup_yapisi(mod, secenekler(mod)):
        if secenek in ss:
            return ad
    return None


def sayfa_menusu(etiket, secenekler, *, modul, key, format_func=None, **kw):
    """Modüllerin sayfa menüsü — st.radio ile aynı çağrı + modul=.
    MENU_UST açıksa şeridin altında yatay sekme; kapalıysa (ya da şerit
    kurulmamışsa) çağrıldığı yerde (kenar çubuğu) eskisi gibi liste.
    Modülün grubu tanımlıysa iki katlı: üstte grup, altta o grubun sayfaları."""
    import streamlit as st
    kap = _serit() if MENU_UST else None
    if kap is None:
        return st.radio(etiket, secenekler, key=key, format_func=format_func or str, **kw)
    yapi = grup_yapisi(modul, secenekler)
    if not yapi:
        return kap.radio(etiket, secenekler, key=key, horizontal=True, label_visibility="collapsed",
                         format_func=lambda s: sekme_adi(modul, s))
    return _iki_katli(kap, modul, key, secenekler, yapi)


def _iki_katli(kap, modul, key, secenekler, yapi):
    """Grup sekmeleri + seçili grubun sayfa düğmeleri.

    Seçili SAYFA st.session_state[key]'de DÜZ değer olarak tutulur (bileşen anahtarı
    değil): tek sayfalı grupta alt satır çizilmez ve Streamlit çizilmeyen bileşenin
    değerini silerdi. Palet ve adres çubuğu da aynı anahtara yazar. Grup her
    çalıştırmada sayfadan türetilir; böylece paletten başka gruba gidince üst sekme de
    doğru grubu gösterir."""
    import streamlit as st
    sayfa = st.session_state.get(key)
    if sayfa not in secenekler:
        sayfa = secenekler[0]
    st.session_state[key] = sayfa
    gruplar = [ad for ad, _ in yapi]
    grubu = dict(yapi)
    g_key, s_key = f"{key}__grup", f"{key}__alt"
    st.session_state[g_key] = next(ad for ad, ss in yapi if sayfa in ss)

    def _grup_degisti():
        st.session_state[key] = grubu[st.session_state[g_key]][0]       # grubun ilk sayfası

    def _sayfa_degisti():
        st.session_state[key] = st.session_state[s_key]

    kap.radio("Bölüm", gruplar, key=g_key, horizontal=True, label_visibility="collapsed",
              on_change=_grup_degisti)
    ss = grubu[st.session_state[g_key]]
    if len(ss) > 1:
        st.session_state[s_key] = sayfa
        with kap.container(key="sayfa_alt"):
            st.radio("Sayfa", ss, key=s_key, horizontal=True, label_visibility="collapsed",
                     format_func=lambda x: sekme_adi(modul, x), on_change=_sayfa_degisti)
    return sayfa

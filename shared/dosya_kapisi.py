# -*- coding: utf-8 -*-
"""Dosya kapısı (Ekim 2026): programın BÜTÜN Excel yüklemeleri tek pencerede.

Dosya bırakılır → shared.dosya_tani türünü bulur → aynı pencerede o türün yükleme akışı
(önizleme, kontroller, kaydet) çalışır. Akışların kendisi YENİ değildir: her modülün eski
yükleme ekranındaki gövde, modül düzeyinde bir fonksiyona taşındı (TURLER["govde"]) ve dosyayı
yükleme kutusundan değil kapıdan alır. Sayfalardaki eski yükleme alanları kaldırıldı.

Pencere kuralları (Streamlit):
- Pencere içinde pencere açılamaz → gövdeler @st.dialog DEĞİL, düz fonksiyondur.
- Bir çalışmada tek pencere açılabilir → kapı açıkken Talep Merkezi açılmaz (app.py) ve kapı
  açılırken başka pencerelerin bekleyen bayrakları silinir.
- Kayıttan sonra gövde kapi.bitti(...) çağırır: sonuç kapıda gösterilir, sayfa da tazelenir
  (st.rerun sonrası kaybolan st.success sorunu yok).
- Pencere X / Esc / dışarı tıklamayla KAPANMAZ (dismissible=False), her ekranda "Kapat" düğmesi
  vardır: X tam yenileme başlatır ve sürmekte olan kaydı yarıda keserdi (satışlar yazılır, stok
  düşülmez, geri alma kaydı oluşmaz). Pencere içindeki düğmeler yalnız pencereyi yeniler, kaydı kesmez.
"""
import copy
import hashlib
import uuid
from io import BytesIO

import streamlit as st

from shared.dosya_tani import tani, KESIN

_ACIK, _DOSYALAR, _AKTIF, _SONUC, _SURUM = ("_kapi_acik", "_kapi_dosyalar", "_kapi_aktif",
                                            "_kapi_sonuc", "_kapi_surum")
_ATLANAN = "_kapi_atlanan"
# Kapı açılırken kapanan diğer pencerelerin bayrakları (bir çalışmada tek pencere). Sayfaların
# pencere bayrakları "_<ad>_ac" kalıbındadır (shared.bilesen.detay_ac, _talep_ac, _mk_dialog_ac,
# _ms_dialog_ac, _mlyt_ac …): hepsi temizlenir — tek tek sayılınca Kâr / P&L'nin _mlyt_ac'ı unutulmuştu.
def _pencere_bayragi_mi(k):
    return isinstance(k, str) and k.startswith("_") and k.endswith("_ac")

# Bir dosyanın en büyük boyutu ve listedeki en çok dosya: dosyalar oturum belleğinde tutulur
EN_BUYUK_MB = 30
EN_COK_DOSYA = 20

MODUL_AD = {"satis": "Satış", "kayranacc": "Muhasebe", "kayranpm": "Ürün Yönetimi", "depo": "Depo",
            "ithalat": "İthalat", "teknikservis": "Teknik Servis", "yonetim": "Yönetim"}

# tur → ad, yetki modülü, kayıt sonrası rakamın göründüğü yer, gövde ("modül:fonksiyon")
TURLER = {
    "siparis_vatan": dict(ad="VATAN sipariş Excel'i", modul="satis", yer="Satış › Satışlar",
                          govde="satis.main:kapi_siparis_vatan"),
    "siparis_itopya": dict(ad="Sipariş Excel'i (EERA / İtopya şablonu, diğer firmalar)", modul="satis",
                           yer="Satış › Satışlar", govde="satis.main:kapi_siparis_itopya"),
    "mikro_fatura": dict(ad="Mikro satış fatura dökümü", modul="satis", yer="Satış › Satışlar",
                         govde="satis.main:kapi_mikro_fatura"),
    "iade_excel": dict(ad="İade Excel'i", modul="satis", yer="Satış › İade",
                       govde="satis.main:kapi_iade"),
    "ithalat_rapor": dict(ad="Satın alım raporu (ithalat)", modul="ithalat", yer="İthalat › Geçmiş ithalatlar",
                          govde="ithalat.main:kapi_ithalat_rapor"),
    "happylife": dict(ad="Happy Life stok raporu", modul="depo", yer="Depo › Happy Life kiralık depo",
                      govde="depo.main:kapi_happylife"),
    "toplu_mal_kabul": dict(ad="Toplu mal kabul", modul="teknikservis", yer="Teknik Servis › Teknik servis",
                            govde="teknikservis.main:kapi_mal_kabul"),
    "kampanya_sablon": dict(ad="Kampanya şablonu", modul="kayranpm", yer="Ürün Yönetimi › Kampanya takip",
                            govde="kayranpm.kampanya:kapi_kampanya"),
    "g5f_sayim": dict(ad="G5F depo stok sayımı", modul="kayranpm", yer="Ürün Yönetimi › Tüm ürünler",
                      govde="kayranpm.main:kapi_g5f"),
    "ref_excel": dict(ad="Ref listesi", modul="kayranpm", yer="Ürün Yönetimi › Ref No takibi",
                      govde="kayranpm.ref_no:kapi_ref"),
    "alinan_destek": dict(ad="Alınan destekler", modul="kayranpm", yer="Ürün Yönetimi › Ref No takibi",
                          govde="kayranpm.ref_ekran:kapi_alinan_destek"),
    "gider_tablosu": dict(ad="Aylık gider tablosu", modul="yonetim", yer="Yönetim › Destekler ve giderler",
                          govde="yonetim:kapi_gider"),
    "aktif_cari": dict(ad="Cari alacaklar listesi", modul="kayranacc", yer="Muhasebe › Toplam aktifler",
                       ozel="toplam_aktifler", govde="kayranacc.main:kapi_aktif_cari"),
    "aktif_ithalat": dict(ad="İthalat ödeme takip", modul="kayranacc", yer="Muhasebe › Toplam aktifler",
                          ozel="toplam_aktifler", govde="kayranacc.main:kapi_aktif_ithalat"),
    "aktif_stok": dict(ad="Stok değeri raporu", modul="kayranacc", yer="Muhasebe › Toplam aktifler",
                       ozel="toplam_aktifler", govde="kayranacc.main:kapi_aktif_stok"),
    "musteri_haftalik": dict(ad="Haftalık müşteri stok + satış", modul="kayranpm",
                             yer="Ürün Yönetimi › Müşteri satışları", govde="kayranpm.main:kapi_musteri_haftalik"),
    "odeme_listesi": dict(ad="Haftalık ödeme listesi", modul="kayranacc", yer="Muhasebe › Bu hafta",
                          govde="kayranacc.main:kapi_odeme_listesi"),
    "cek_listesi": dict(ad="Firma çek dökümü", modul="kayranacc", yer="Muhasebe › Firma çekleri",
                        govde="kayranacc.main:kapi_cek_listesi"),
}

# Boş şablonlar (eskiden yükleme kutularının yanındaydı): ad → "modül:fonksiyon" → (bytes, dosya adı)
SABLONLAR = [
    ("VATAN sipariş şablonu", "satis", "satis.main:sablon_siparis_vatan"),
    ("EERA / diğer firmalar sipariş şablonu", "satis", "satis.main:sablon_siparis_itopya"),
    ("Haftalık ödeme listesi örneği", "kayranacc", "kayranacc.main:sablon_odeme_listesi"),
    ("Satın alım raporu (ithalat) şablonu", "ithalat", "ithalat.main:sablon_ithalat"),
    ("Kampanya şablonu", "kayranpm", "kayranpm.kampanya:sablon_kampanya"),
    ("Alınan destekler şablonu", "kayranpm", "kayranpm.ref_ekran:sablon_alinan_destek"),
    ("Toplu mal kabul şablonu", "teknikservis", "teknikservis.main:sablon_mal_kabul"),
]


def _fonksiyon(yol):
    import importlib
    mod, ad = yol.split(":")
    return getattr(importlib.import_module(mod), ad)


def izinli(tur, yetkiler):
    """yetkiler: {modül: bool, "yonetim": bool, "kar": bool, "toplam_aktifler": bool} (app.py doldurur)."""
    t = TURLER.get(tur)
    if not t:
        return False
    if t["modul"] == "yonetim":
        return bool(yetkiler.get("yonetim") and yetkiler.get("kar"))
    if t.get("ozel") and not yetkiler.get(t["ozel"]):
        return False            # Toplam Aktifler'in kendi yetki listesi var
    return bool(yetkiler.get(t["modul"]))


def izinli_turler(yetkiler):
    return [t for t in TURLER if izinli(t, yetkiler)]


class KapiDosyasi(BytesIO):
    """Gövdelere verilen dosya: yükleme kutusunun dosyası gibi davranır (.name, .size, getvalue)."""

    def __init__(self, veri, ad):
        super().__init__(veri)
        self.name = ad
        self.size = len(veri)
        self.type = ""


class Kapi:
    """Gövdeye verilen bağlam: dosya, benzersiz widget anahtarı, bitiş."""

    def __init__(self, kayit):
        self.kayit = kayit
        self.id = kayit["id"]

    @property
    def ad(self):
        return self.kayit["ad"]

    def dosya(self):
        return KapiDosyasi(self.kayit["veri"], self.kayit["ad"])

    def anahtar(self, ad):
        """Dosyaya özgü widget anahtarı: ikinci dosyada ilk dosyanın girdileri kalmasın."""
        return f"{ad}__kp{self.id}"

    def onbellek(self, ad, fonk):
        """Dosyadan okunan sonucu bu dosya için bir kez hesapla. Pencere içindeki her tıklama
        gövdeyi yeniden çalıştırır; büyük Excel'in her tuşta baştan okunmaması için. Kopya döner
        (gövde sonucu değiştirse de saklanan bozulmaz)."""
        d = self.kayit.setdefault("_onbellek", {})
        if ad not in d:
            d[ad] = fonk()
        return copy.deepcopy(d[ad])

    def yenile(self):
        """Yalnız pencerenin içini yeniden çiz (ara adım: ör. takip no atandı, içe aktarma sürüyor)."""
        _yenile()

    def bitti(self, mesaj, tablo=None, uyari=False, ayrinti=""):
        """Kayıt tamam: sonucu kapıda göster, dosyayı listeden çıkar, sayfayı tazele."""
        ss = st.session_state
        ss[_SONUC] = {"mesaj": str(mesaj), "tablo": tablo or [], "uyari": bool(uyari),
                      "ayrinti": ayrinti, "dosya": self.ad, "tur": self.kayit.get("secim")}
        ss[_DOSYALAR] = [d for d in ss.get(_DOSYALAR, []) if d["id"] != self.id]
        ss.pop(_AKTIF, None)
        st.rerun()              # tam yenileme: sayfa yeni veriyle çizilir, kapı sonuçla açılır


# ── Açma / kapama ────────────────────────────────────────────────────────
def ac():
    """Kapıyı aç (düğmenin on_click'i). Bekleyen başka pencere bayrakları silinir."""
    ss = st.session_state
    ss[_ACIK] = True
    for b in [k for k in list(ss.keys()) if _pencere_bayragi_mi(k)]:
        ss.pop(b, None)


def acik():
    return bool(st.session_state.get(_ACIK))


def kapat():
    ss = st.session_state
    for k in (_ACIK, _DOSYALAR, _AKTIF, _SONUC, _ATLANAN):
        ss.pop(k, None)


def _yenile():
    """Yalnız pencerenin içini yenile; ilk açılış çalışmasında olamıyorsa tam yenile."""
    try:
        st.rerun(scope="fragment")
    except Exception:  # noqa: BLE001 — StreamlitAPIException: parça yenilemesi değil
        st.rerun()


def yetkiler_topla(kullanici, modul_yetkileri, ozel_yetki, tam=True):
    """Kapının yetki sözlüğü. modul_yetkileri: app.kullanici_yetkileri sonucu;
    ozel_yetki(kullanici, ad) → bool. tam=False: Toplam Aktifler listesi okunmaz (üst menü düğmesi
    her çalışmada çizilir; o liste yalnız pencere açıkken gerekir)."""
    y = dict(modul_yetkileri or {})
    y["yonetim"] = bool(ozel_yetki(kullanici, "yonetim"))
    try:
        from shared.kar_gizle import kar_gorunur
        y["kar"] = bool(kar_gorunur())
    except Exception:  # noqa: BLE001
        y["kar"] = False
    if not tam:
        return y
    try:
        from shared.yetki import ozel_sahipleri
        from kayranacc.main import TOPLAM_AKTIFLER_YETKILI
        y["toplam_aktifler"] = (kullanici or "").lower().strip() in ozel_sahipleri(
            "toplam_aktifler", TOPLAM_AKTIFLER_YETKILI)
    except Exception:  # noqa: BLE001
        y["toplam_aktifler"] = False
    return y


def gorunur(yetkiler):
    """Kapı düğmesi: kullanıcının yükleyebileceği en az bir dosya türü varsa."""
    return bool(izinli_turler(yetkiler))


def ciz(yetkiler):
    """app.py her tam çalışmada bir kez çağırır. Kapı açıksa pencereyi açar → True."""
    if not acik():
        return False
    _pencere(yetkiler)
    return True


def _pencere_kalibi():
    """X / Esc ile kapanmayan pencere (modül başındaki not: kaydı yarıda kesmesin); kapatma her
    ekrandaki "Kapat" düğmesiyle. Eski Streamlit dismissible'ı tanımıyorsa onsuz kurulur."""
    try:
        return st.dialog("Dosya kapısı", width="large", dismissible=False)
    except TypeError:
        return st.dialog("Dosya kapısı", width="large")


def _kapat_dugmesi(yer=None, anahtar="kapi_kapat_ust"):
    if (yer or st).button("Kapat", key=anahtar, icon=":material/close:", use_container_width=True):
        kapat()
        st.rerun()


@_pencere_kalibi()
def _pencere(yetkiler):
    try:
        _ic(yetkiler)
    except Exception as e:  # noqa: BLE001 — bir gövdenin hatası pencereyi değil yalnız o dosyayı düşürsün
        if type(e).__name__ in ("RerunException", "StopException"):
            raise
        try:
            from shared.hata_log import kaydet
            kaydet("dosya_kapisi", e)
        except Exception:  # noqa: BLE001
            pass
        st.error(f"Bu dosya işlenirken hata oluştu ({type(e).__name__}: {str(e)[:160]}). "
                 "Hiçbir şey yarım kaydedilmediyse dosyayı yeniden deneyebilirsin; hata kaydı tutuldu.")
        c1, c2 = st.columns(2)
        if c1.button("Dosyalara dön", key="kapi_hata_don", icon=":material/arrow_back:",
                     use_container_width=True):
            st.session_state.pop(_AKTIF, None)
            _yenile()
        _kapat_dugmesi(c2, "kapi_hata_kapat")


def _ic(yetkiler):
    ss = st.session_state
    ss.setdefault(_DOSYALAR, [])
    sonuc = ss.get(_SONUC)
    if sonuc:
        _sonuc_ciz(sonuc)
        return
    kayit = next((d for d in ss[_DOSYALAR] if d["id"] == ss.get(_AKTIF)), None)
    if kayit:
        _govde_ciz(kayit, yetkiler)
        return
    _liste_ciz(yetkiler)


def _sonuc_ciz(s):
    (st.warning if s.get("uyari") else st.success)(s["mesaj"])
    if s.get("ayrinti"):
        st.caption(s["ayrinti"])
    if s.get("tablo"):
        import pandas as pd
        st.dataframe(pd.DataFrame(s["tablo"]), hide_index=True, use_container_width=True)
    kalan = len(st.session_state.get(_DOSYALAR, []))
    c1, c2 = st.columns(2)
    if c1.button(f"Kalan dosyalar ({kalan})" if kalan else "Başka dosya yükle", key="kapi_devam",
                 icon=":material/upload_file:", use_container_width=True):
        st.session_state.pop(_SONUC, None)
        _yenile()
    if c2.button("Kapat", key="kapi_kapat", type="primary", use_container_width=True):
        kapat()
        st.rerun()


def _govde_ciz(kayit, yetkiler):
    tur = kayit.get("secim")
    t = TURLER.get(tur)
    c1, c2, c3 = st.columns([1, 4, 1], vertical_alignment="center")
    if c1.button("Dosyalar", key="kapi_geri", icon=":material/arrow_back:"):
        st.session_state.pop(_AKTIF, None)
        _yenile()
    c2.markdown(f"**{t['ad']}** · `{kayit['ad']}`" if t else f"`{kayit['ad']}`")
    _kapat_dugmesi(c3)
    if not t or not izinli(tur, yetkiler):
        st.error("Bu dosya türü için yetkin yok.")
        return
    # Elle seçilen tür, tanımanın bulduğu türlerden değilse: yanlış akışa giren dosya yanlış yere
    # yazılabilir (ör. sipariş Excel'i "stok değeri raporu" seçilince sütun sayıları stok değeri
    # sanılıyordu). Önce uyarı + bilinçli onay.
    taninan = [a["tur"] for a in kayit.get("adaylar") or [] if a.get("tur")]
    if tur not in taninan:
        st.warning(f"Bu dosya **{t['ad']}** türüne benzemiyor"
                   + (f" (tanıma: {', '.join(TURLER[x]['ad'] for x in taninan if x in TURLER)})." if taninan
                      else " (tanınmadı).")
                   + " Yanlış tür seçildiyse kayıt yanlış yere yazılır; dosyayı ve türü kontrol et.")
        if not st.checkbox("Dosyanın bu türde olduğundan eminim, devam et", key=f"kapi_tur_onay_{kayit['id']}"):
            return
    _k = Kapi(kayit)
    _fonksiyon(t["govde"])(_k.dosya(), _k)


_ETIKET = {KESIN: ("kesin", "yesil"), "olasi": ("büyük olasılıkla", "amber"), None: ("tanınmadı", "kirmizi")}


def _liste_ciz(yetkiler):
    ss = st.session_state
    st.caption("Programın kullandığı bütün Excel dosyaları buradan yüklenir. Dosya türü kendiliğinden "
               "tanınır; kayıt, aynı pencerede önizleme ve kontrollerden sonra yapılır.")
    ss.setdefault(_SURUM, 0)
    yeni = st.file_uploader("Excel dosyalarını bırakın ya da seçin", type=["xlsx", "xls"],
                            accept_multiple_files=True, key=f"kapi_yukle_{ss[_SURUM]}")
    if yeni:
        dosyalari_ekle(yeni, yetkiler)
        _yenile()
    for m in ss.pop(_ATLANAN, None) or []:
        st.warning(m)

    izin = izinli_turler(yetkiler)
    for d in list(ss[_DOSYALAR]):
        _dosya_satiri(d, izin, yetkiler)
    if not ss[_DOSYALAR]:
        _sablonlar(yetkiler)
    _kapat_dugmesi()


def dosyalari_ekle(dosyalar, yetkiler):
    """Yüklenen dosyaları tanıyıp kapı listesine ekler (kapı penceresi ve ana sayfadaki bırakma alanı)."""
    ss = st.session_state
    ss.setdefault(_DOSYALAR, [])
    ss[_SURUM] = ss.get(_SURUM, 0) + 1          # yükleme kutusu boşalsın; dosyalar listede
    atlanan = []
    for f in dosyalar:
        veri = f.getvalue()
        ozet = hashlib.sha1(veri).hexdigest()
        if any(d.get("ozet") == ozet for d in ss[_DOSYALAR]):
            # Aynı dosya iki kez eklenirse iki kez kaydedilebilirdi (kampanya, mal kabul mükerrer olurdu)
            atlanan.append(f"{f.name}: bu dosya listede zaten var, ikinci kez eklenmedi.")
            continue
        if len(veri) > EN_BUYUK_MB * 1024 * 1024:
            atlanan.append(f"{f.name}: dosya {EN_BUYUK_MB} MB'tan büyük, eklenmedi.")
            continue
        if len(ss[_DOSYALAR]) >= EN_COK_DOSYA:
            atlanan.append(f"{f.name}: listede en çok {EN_COK_DOSYA} dosya olabilir; önce bekleyenleri kaydet.")
            continue
        adaylar = [a for a in tani(f.name, veri) if a.get("tur")]
        ss[_DOSYALAR].append({"id": uuid.uuid4().hex[:8], "ad": f.name, "veri": veri, "ozet": ozet,
                              "adaylar": adaylar, "secim": adaylar[0]["tur"] if adaylar else None})
    if atlanan:
        ss[_ATLANAN] = atlanan
    if len(ss[_DOSYALAR]) == 1 and _tek_kesin(ss[_DOSYALAR][0], yetkiler):
        ss[_AKTIF] = ss[_DOSYALAR][0]["id"]     # tek ve kesin tanınan dosya: doğrudan aç


def ana_sayfa_alani(yetkiler):
    """Ana sayfa · Veri güncelliği bölümünün başındaki bırakma alanı: dosya bırakılınca kapı açılır."""
    if not gorunur(yetkiler):
        return
    ss = st.session_state
    ss.setdefault("_kapi_ana_surum", 0)
    with st.container(key="kapi_ana"):
        f = st.file_uploader("Excel dosyalarını buraya bırakın — türü kendiliğinden tanınır, doğru yükleme açılır",
                             type=["xlsx", "xls"], accept_multiple_files=True,
                             key=f"kapi_ana_{ss['_kapi_ana_surum']}")
    if f:
        ss["_kapi_ana_surum"] += 1
        dosyalari_ekle(f, yetkiler)
        ac()
        st.rerun()


def _tek_kesin(d, yetkiler):
    a = d.get("adaylar") or []
    kesin = [x for x in a if x["guven"] == KESIN]
    return len(kesin) == 1 and izinli(kesin[0]["tur"], yetkiler)


def _dosya_satiri(d, izin, yetkiler):
    from shared.tasarim import renk
    aday = {a["tur"]: a for a in d.get("adaylar") or []}
    secim = d.get("secim")
    a = aday.get(secim)
    etiket, rk = _ETIKET[a["guven"] if a else None]
    t = TURLER.get(secim)
    with st.container(border=True):
        c1, c2 = st.columns([5, 2], vertical_alignment="center")
        with c1:
            st.markdown(
                f'<div style="font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--k-soluk)">'
                f'{_kac(d["ad"])}</div><div style="font-size:15px;font-weight:600;margin:2px 0">'
                f'{_kac(t["ad"]) if t else "Tanınmadı"} <span style="font-size:11px;font-weight:600;padding:1px 7px;'
                f'border-radius:5px;border:1px solid {renk(rk)};color:{renk(rk)}">{etiket}</span></div>',
                unsafe_allow_html=True)
            if a:
                st.caption(f"Tanıyan: {a['gerekce']} · Kayıttan sonra: {t['yer']}")
            elif not aday:
                st.caption("Bilinen dosya türlerinin hiçbirine uymuyor; tahminle bir yere gönderilmez. "
                           "Türünü biliyorsan aşağıdan seç.")
            # Birden çok aday ya da tanınmadıysa tür seçimi
            if len(aday) != 1 or (a and a["guven"] != KESIN):
                secenek = [x for x in aday if x in izin] + [x for x in izin if x not in aday]
                if secenek:
                    yeni = st.selectbox("Dosya türü", secenek, index=secenek.index(secim) if secim in secenek else None,
                                        key=f"kapi_tur_{d['id']}", placeholder="Tür seç",
                                        format_func=lambda x: TURLER[x]["ad"] + (" (önerilen)" if x in aday else ""))
                    if yeni != secim:
                        d["secim"] = secim = yeni
        with c2:
            if secim and not izinli(secim, yetkiler):
                st.caption(f"Bu dosya {MODUL_AD.get(TURLER[secim]['modul'], '')} modülüne ait; yetkin yok.")
            elif st.button("Aç", key=f"kapi_ac_{d['id']}", type="primary", use_container_width=True,
                           disabled=not secim, icon=":material/arrow_forward:"):
                st.session_state[_AKTIF] = d["id"]
                _yenile()
            if st.button("Listeden çıkar", key=f"kapi_cik_{d['id']}", use_container_width=True):
                st.session_state[_DOSYALAR] = [x for x in st.session_state[_DOSYALAR] if x["id"] != d["id"]]
                _yenile()


def _sablonlar(yetkiler):
    liste = [s for s in SABLONLAR if yetkiler.get(s[1])]
    if not liste:
        return
    with st.expander("Boş şablonlar"):
        sec = st.selectbox("Şablon", [s[0] for s in liste], index=None, key="kapi_sablon_sec",
                           placeholder="İndirilecek şablonu seç")
        if sec:
            yol = next(s[2] for s in liste if s[0] == sec)
            try:
                veri, ad = _fonksiyon(yol)()
            except Exception as e:  # noqa: BLE001
                st.error(f"Şablon hazırlanamadı ({type(e).__name__}).")
                return
            st.download_button("İndir", veri, ad, key="kapi_sablon_indir", icon=":material/download:",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _kac(s):
    import html
    return html.escape(str(s))

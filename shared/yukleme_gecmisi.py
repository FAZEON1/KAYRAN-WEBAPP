# -*- coding: utf-8 -*-
"""Yükleme geçmişi ve geri alma (Ekim 2026).

Her Excel yüklemesi yuklemeler tablosuna bir satır yazar: tür, dosya, kim, ne zaman, kaç satır.
Geri alınabilir türlerde (GERI_ALINABILIR) ayrıca: eklenen satırların kimlikleri ve üzerine
yazılan / silinen eski satırların TAM hâli. Geri alma veritabanında TEK İŞLEMDE yapılır
(yukleme_geri_al, veritabani/12_yuklemeler.sql): eklenenler silinir, eskiler özgün
kimlikleriyle geri yazılır — ya hepsi ya hiçbiri.

KORUMA: Aynı veri dilimine (aynı firma + hafta, aynı rapor tarihi, aynı para birimi, aynı
firma bütçesi) sonradan başka bir yükleme yapıldıysa önceki geri alınamaz; önce sonraki geri
alınmalı (geri_alma_engeli). Kişi yalnız kendi yüklemesini, yönetici herkesinkini geri alır.

GÜVENCE: Geçmiş yazılamazsa (tablo kurulmamış vb.) yükleme YİNE tamamlanır; yalnız geçmişe
düşmez. Bu modüldeki yazma fonksiyonları hata fırlatmaz.
"""
import contextlib
import contextvars
from datetime import datetime, timezone

TABLO = "yuklemeler"

# tür → ekranda görünen ad
TURLER = {
    "musteri_haftalik": "Müşteri stok / satış (haftalık)",
    "happylife": "Happy Life stoğu",
    "cek_listesi": "Çek listesi",
    "havuz_butce": "Havuz bütçe",
    "g5f_sayim": "G5F depo sayımı",
    "siparis_excel": "Sipariş Excel'i (satış)",
    "mikro_fatura": "Mikro fatura dökümü (satış)",
    "iade_excel": "İade Excel'i",
    "ithalat_rapor": "İthalat satın alma raporu",
    "ref_excel": "Ref Excel'i",
    "alinan_destek": "Alınan destek Excel'i",
    "kampanya_sablon": "Kampanya şablonu",
    "toplu_mal_kabul": "Teknik servis toplu mal kabul",
    "gider_tablosu": "Gider tablosu",
    "odeme_listesi": "Ödeme listesi",
    "aktif_excel": "Aktif stok / ithalat / cari Excel'i",
}
# Geri alınabilir türler → satır düzeyinde dokundukları tablolar. Birleşimleri veritabanı
# fonksiyonundaki (yukleme_satir_geri_al) izin listesiyle AYNI olmalı (testte denetlenir).
GERI_ALINABILIR = {
    "musteri_haftalik": ("firma_stok",), "happylife": ("happylife_stok",),
    "cek_listesi": ("cekler",), "havuz_butce": ("ref_butce",),
    "siparis_excel": ("satislar",), "mikro_fatura": ("satislar",), "iade_excel": ("iadeler",),
    "g5f_sayim": (), "toplu_mal_kabul": ("ts_kayitlar",),
    "ithalat_rapor": ("ithalat_dosyalari", "ithalat_kalemleri"),
}
SATIR_TABLOLARI = sorted({t for ts in GERI_ALINABILIR.values() for t in ts})
# Stok da değiştiren türler: geri almada işaretli stok hareketleri (stok_defteri.yukleme)
# ürün + depo bazında toplanıp TERS uygulanır. Yalnız yükleme kodu taşıyan kayıtlarda.
STOKLU = {"siparis_excel", "mikro_fatura", "iade_excel", "g5f_sayim", "toplu_mal_kabul"}

_AKTIF = contextvars.ContextVar("aktif_yukleme_kaydi", default=None)


def aktif():
    """Şu an sürmekte olan yüklemenin Kayit'ı (Kayit.stok() bağlamı içindeyse), yoksa None.
    Derindeki yazma fonksiyonları (ice_aktar_satislar, ekle_dosya…) buna eklenen / silinen
    satırları bildirir; yükleme dışından çağrıldıklarında hiçbir şey yapmaz."""
    return _AKTIF.get()


def _ham():
    from shared.audit import _raw_client
    return _raw_client()


def _kullanici():
    try:
        import streamlit as st
        return str(st.session_state.get("aktif_kullanici", "") or "")
    except Exception:  # noqa: BLE001
        return ""


class Kayit:
    """Bir yüklemenin geçmiş kaydını biriktirir; sonunda kaydet() ile yazar.

        k = Kayit("musteri_haftalik", dosya_adi)
        k.anahtar("VATAN|2026-09-27")
        k.onceki("firma_stok", silinecek_satirlar)      # silmeden ÖNCE okunan tam satırlar
        k.eklenen("firma_stok", insert_cevabi.data)     # insert'in döndürdüğü satırlar (id'li)
        k.kaydet(satir_sayisi)

    Kimliği bilinmeyen bir yazma olduysa (ör. satır satır yedek yol) iptal() çağrılır:
    kayıt yine yazılır ama geri alınamaz."""

    def __init__(self, tur, dosya_adi=""):
        import uuid
        self.tur, self.dosya_adi = tur, str(dosya_adi or "")
        self.anahtarlar, self.degisiklik, self._iptal = [], {}, ""
        # Stok hareketlerini bu yüklemeyle işaretleyen kod (stok_defteri.yukleme(k.kod)).
        self.kod = uuid.uuid4().hex

    def anahtar(self, *parcalar):
        a = "|".join(str(p) for p in parcalar)
        if a not in self.anahtarlar:
            self.anahtarlar.append(a)

    def _t(self, tablo):
        return self.degisiklik.setdefault(tablo, {"eklenen": [], "onceki": []})

    def onceki(self, tablo, satirlar):
        self._t(tablo)["onceki"].extend(dict(r) for r in (satirlar or []))

    def eklenen(self, tablo, satirlar, beklenen=None):
        """satirlar: insert cevabı (data). beklenen: gönderilen satır sayısı — cevapta kimlik
        eksikse kayıt geri alınamaz olur (eksik silme yapmamak için)."""
        ids = [r.get("id") for r in (satirlar or []) if isinstance(r, dict) and r.get("id") is not None]
        if beklenen is not None and len(ids) != beklenen:
            self.iptal(f"{tablo}: {beklenen} satırdan {len(ids)} kimlik döndü")
        self._t(tablo)["eklenen"].extend(ids)

    def kontrol(self, tablo, kimlik, **alanlar):
        """Geri almadan önce denetlenecek 'yükleme anındaki' değerler: satır sonradan değiştiyse
        (ör. ithalat dosyasına masraf girildi, servis kaydı işlem gördü) geri alma ENGELLENİR —
        emek kaybolmasın. Özel alan '_gecmis_sayisi': ts_gecmis'te bu kayda ait satır sayısı."""
        self.degisiklik.setdefault("_kontrol", []).append(
            {"tablo": tablo, "id": kimlik, "alanlar": alanlar})

    def iptal(self, neden):
        self._iptal = self._iptal or str(neden)

    @property
    def geri_alinabilir(self):
        if self.tur not in GERI_ALINABILIR or self._iptal:
            return False
        return self.tur in STOKLU or any(t in self.degisiklik for t in GERI_ALINABILIR[self.tur])

    def kaydet(self, satir_sayisi):
        g = self.geri_alinabilir
        return kaydet(self.tur, satir_sayisi, self.dosya_adi, self.anahtarlar,
                      self.degisiklik if g else None, kod=self.kod, geri_alinabilir=g)

    @contextlib.contextmanager
    def stok(self):
        """Bu blok içinde: stok hareketleri bu yüklemenin koduyla işaretlenir ve derindeki yazma
        fonksiyonları eklenen / silinen satırları bu kayda bildirir (aktif()).
            with k.stok(): ice_aktar_satislar(...)"""
        tok = _AKTIF.set(self)
        try:
            try:
                from shared.stok_defteri import yukleme
                isaret = yukleme(self.kod)
            except Exception:  # noqa: BLE001
                isaret = contextlib.nullcontext()
            with isaret:
                yield self
        finally:
            _AKTIF.reset(tok)


def kaydet(tur, satir_sayisi, dosya_adi="", anahtarlar=(), degisiklik=None, kod="", geri_alinabilir=None):
    """Geçmişe bir yükleme yazar. degisiklik verilirse geri alınabilir (geri_alinabilir açıkça
    verilmezse). Döner: id ya da None. ASLA hata fırlatmaz — yükleme her koşulda tamamlanmış sayılır."""
    try:
        import json
        satir = {"tur": str(tur), "dosya_adi": str(dosya_adi or "")[:200], "kullanici": _kullanici(),
                 "satir_sayisi": int(satir_sayisi or 0), "anahtarlar": list(anahtarlar or []),
                 "geri_alinabilir": bool(degisiklik) if geri_alinabilir is None else bool(geri_alinabilir),
                 "degisiklik": json.loads(json.dumps(degisiklik or {}, default=str))}
        if kod:
            satir["kod"] = str(kod)[:40]
        try:
            r = _ham().table(TABLO).insert(satir).execute()
        except Exception as e1:                       # kod sütunu henüz yoksa onsuz yaz
            if "kod" not in satir or "kod" not in str(e1):
                raise
            satir.pop("kod")
            r = _ham().table(TABLO).insert(satir).execute()
        return ((r.data or [{}])[0]).get("id")
    except Exception as e:  # noqa: BLE001
        try:
            from shared.hata_log import kaydet as _hk
            _hk(f"yukleme_gecmisi.kaydet.{tur}", e)
        except Exception:  # noqa: BLE001
            pass
        return None


# ── Saf: geri alma kuralı ───────────────────────────────────────────
def _zaman(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def geri_alma_engeli(kayit, tum_kayitlar, kullanici="", yonetici=False):
    """Geri alınamıyorsa nedeni (metin), alınabiliyorsa "".
    tum_kayitlar: diğer yükleme kayıtları (aktif olanlar yeterli).

    Sonraki yükleme kuralı: aynı türde ortak dilimi (anahtar) olan, ya da HER türde ortak bir
    tablo-dilimi ('satislar:FAT-1', 'iadeler:2026-10-01' gibi ':' içeren anahtar) olan daha yeni
    ve aktif bir yükleme varsa önce o geri alınmalı (eski satırlar onun üzerine yazılmasın)."""
    durum = kayit.get("durum")
    if durum == "geri_alindi":
        return "Bu yükleme zaten geri alınmış."
    if durum not in ("aktif", "geri_aliniyor"):
        return "Bu yükleme geri alınamaz."
    if not kayit.get("geri_alinabilir"):
        return "Bu yükleme türü şimdilik geri alınamaz (yalnız geçmişte görünür)."
    if kayit.get("tur") in STOKLU and not kayit.get("kod"):
        return "Bu yükleme stok işaretlemesinden önce yapılmış; stok etkisi ayrılamadığı için geri alınamaz."
    if not yonetici and str(kayit.get("kullanici") or "") != str(kullanici or ""):
        return "Yalnız kendi yüklemeni geri alabilirsin (yönetici herkesinkini alır)."
    benim = set(kayit.get("anahtarlar") or [])
    t0 = _zaman(kayit.get("zaman"))

    def _cakisir(k):
        ortak = benim & set(k.get("anahtarlar") or [])
        return bool(ortak) and (k.get("tur") == kayit.get("tur") or any(":" in a for a in ortak))

    sonraki = [k for k in tum_kayitlar or []
               if k.get("id") != kayit.get("id") and k.get("durum") in ("aktif", "geri_aliniyor")
               and _zaman(k.get("zaman")) > t0 and _cakisir(k)]
    if sonraki:
        s = max(sonraki, key=lambda k: _zaman(k.get("zaman")))
        return (f"Aynı veriye sonradan başka bir yükleme yapılmış ({yerel_zaman(s.get('zaman'))}, "
                f"{TURLER.get(s.get('tur'), s.get('tur'))}, {s.get('dosya_adi') or 'dosya adı yok'}). "
                "Önce onu geri al.")
    return ""


def kontrol_farki(kayit, satirlar_getir):
    """Yükleme anındaki değerlerle ŞİMDİKİ değerleri karşılaştırır (Kayit.kontrol).
    satirlar_getir(tablo, kimlik, alanlar) → şimdiki {alan: değer} ya da None (satır yok).
    Döner: engel metni ya da ""."""
    for k in (kayit.get("degisiklik") or {}).get("_kontrol") or []:
        simdi = satirlar_getir(k.get("tablo"), k.get("id"), list((k.get("alanlar") or {}).keys()))
        if simdi is None:
            return f"{k.get('tablo')} #{k.get('id')} sonradan silinmiş; bu yükleme geri alınamaz."
        for alan, eski in (k.get("alanlar") or {}).items():
            if _esit_degil(simdi.get(alan), eski):
                return (f"{k.get('tablo')} #{k.get('id')} yüklemeden sonra değiştirilmiş ({alan}); "
                        "emek kaybolmasın diye geri alma engellendi.")
    return ""


def _duz(v):
    """Karşılaştırma için: sayılar float (veritabanı 1200, yükleme 1200.0 yazabilir), sözlük / liste
    içleri de; None ve "" aynı sayılır."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        return {str(k): _duz(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_duz(x) for x in v]
    if v is None:
        return ""
    try:
        return float(v) if isinstance(v, str) and v.strip() and v.strip().replace(".", "", 1).lstrip("-").isdigit() else v
    except ValueError:
        return v


def _esit_degil(a, b):
    import json
    try:
        return json.dumps(_duz(a), sort_keys=True, default=str) != json.dumps(_duz(b), sort_keys=True, default=str)
    except Exception:  # noqa: BLE001
        return a != b


def onizleme(kayit):
    """{tablo: (silinecek, geri_gelecek)} — geri almadan önce ekranda gösterilir."""
    return {t: (len(d.get("eklenen") or []), len(d.get("onceki") or []))
            for t, d in (kayit.get("degisiklik") or {}).items() if not t.startswith("_")}


def stok_net(hareketler, depo_kanonik=lambda d: d):
    """İşaretli hareketlerden ürün + depo bazında KALAN net etki: {(sku, depo): net}.
    hareketler: stok_hareketleri satırları (yüklemenin kendi kodu + 'kod:geri' ile yapılan kısmi
    ters çevirmeler). Net 0 olanlar atlanır — tekrar denemede yalnız kalan kısım uygulanır."""
    net = {}
    for h in hareketler or []:
        if h.get("basarili") is False:
            continue
        a = (str(h.get("sku") or ""), depo_kanonik(str(h.get("depo") or "")))
        try:
            net[a] = net.get(a, 0.0) + float(h.get("degisim") or 0)
        except (TypeError, ValueError):
            continue
    return {a: v for a, v in net.items() if abs(v) > 1e-9}


def yerel_zaman(v):
    z = _zaman(v)
    if z.year < 2000:
        return "?"
    try:
        from zoneinfo import ZoneInfo
        z = z.astimezone(ZoneInfo("Europe/Istanbul"))
    except Exception:  # noqa: BLE001
        pass
    return z.strftime("%d.%m.%Y %H:%M")


# ── Veritabanı: listele, geri al ────────────────────────────────────
def listele(kullanici=None, limit=300):
    q = _ham().table(TABLO).select("*")
    if kullanici is not None:
        q = q.eq("kullanici", kullanici)
    return q.order("zaman", desc=True).limit(limit).execute().data or []


def _stok_hareketleri(sb, kod):
    return sb.table("stok_hareketleri").select("sku, depo, degisim, basarili, yukleme_kodu") \
             .in_("yukleme_kodu", [kod, kod + ":geri"]).execute().data or []


def stok_etkisi(kod):
    """Geri alınınca uygulanacak stok değişimi: [(sku, depo, değişim)] (yüklemenin TERSİ)."""
    if not kod:
        return []
    from kayranpm.database import depo_kanonik
    net = stok_net(_stok_hareketleri(_ham(), kod), depo_kanonik)
    return sorted(((s, d, -v) for (s, d), v in net.items()), key=lambda x: (x[0], x[1]))


def _stok_ters_cevir(sb, kod):
    """İşaretli hareketlerin kalan net etkisini ters uygular (stok_hareket_coklu — tek stok kapısı;
    bizim_stok ve defter orada). Ters hareketler 'kod:geri' ile işaretlenir: yarıda kalırsa tekrar
    deneme yalnız kalanı uygular. Döner: (tamam_mi, atlanan_sku_listesi)."""
    from kayranpm.database import depo_kanonik, stok_hareket_coklu
    from shared.stok_defteri import yukleme
    net = stok_net(_stok_hareketleri(sb, kod), depo_kanonik)
    depolar = {}
    for (sku, depo), v in net.items():
        depolar.setdefault(depo, {})[sku] = -v
    atlanan = []
    with yukleme(kod + ":geri"):
        for depo, h in depolar.items():
            _u, atl = stok_hareket_coklu(h, depo, aciklama="Yükleme geri alma")
            atlanan.extend(atl or [])
    return not atlanan, atlanan


def _satir_getir(sb):
    def _g(tablo, kimlik, alanlar):
        ozel = [a for a in alanlar if a.startswith("_")]
        duz = [a for a in alanlar if not a.startswith("_")]
        r = sb.table(tablo).select(", ".join(["id"] + duz)).eq("id", kimlik).execute().data or []
        if not r:
            return None
        out = dict(r[0])
        if "_gecmis_sayisi" in ozel:
            out["_gecmis_sayisi"] = len(sb.table("ts_gecmis").select("id").eq("kayit_id", kimlik)
                                        .execute().data or [])
        return out
    return _g


def geri_al(kayit_id, kullanici, yonetici=False):
    """Geri alma: (1) kurallar, (2) kaydı 'geri_aliniyor' olarak sahiplen, (3) satırlar tek veritabanı
    işleminde (yukleme_satir_geri_al), (4) stoklu türlerde stok etkisini ters çevir, (5) 'geri_alindi'.
    4. adım yarıda kalırsa kayıt 'geri_aliniyor' kalır; tekrar denemek yalnız kalanı tamamlar.
    Döner: (ok, mesaj)."""
    sb = _ham()
    try:
        k = (sb.table(TABLO).select("*").eq("id", kayit_id).execute().data or [None])[0]
        if not k:
            return False, "Yükleme kaydı bulunamadı."
        diger = sb.table(TABLO).select("id, tur, zaman, durum, anahtarlar, dosya_adi") \
                  .in_("durum", ["aktif", "geri_aliniyor"]).execute().data or []
        engel = geri_alma_engeli(k, diger, kullanici, yonetici)
        if not engel and k.get("durum") == "aktif":
            engel = kontrol_farki(k, _satir_getir(sb))
        if engel:
            return False, engel
        if k.get("durum") == "aktif":
            al = sb.table(TABLO).update({"durum": "geri_aliniyor", "geri_alan": str(kullanici or "")}) \
                   .eq("id", kayit_id).eq("durum", "aktif").execute().data or []
            if not al:
                return False, "Bu yükleme şu an başka biri tarafından geri alınıyor."
    except Exception as e:  # noqa: BLE001
        return False, f"Geri alınamadı, hiçbir şey değişmedi: {type(e).__name__}: {str(e)[:160]}"

    # 3) Satırlar — tek işlem
    d = {}
    satirli = any(t in (k.get("degisiklik") or {}) for t in SATIR_TABLOLARI)
    if satirli and k.get("silinen") is None:
        try:
            d = sb.rpc("yukleme_satir_geri_al", {"p_id": int(kayit_id)}).execute().data or {}
        except Exception as e:  # noqa: BLE001
            try:   # satır adımı tek işlemdi, hiçbir şey değişmedi → sahiplenmeyi bırak
                sb.table(TABLO).update({"durum": "aktif", "geri_alan": None}).eq("id", kayit_id) \
                  .eq("durum", "geri_aliniyor").execute()
            except Exception:  # noqa: BLE001
                pass
            m = str(e)
            if "duplicate" in m.lower() or "23505" in m:
                return False, ("Geri alınamadı: eski satırlardan biri şu an başka bir kayıtla çakışıyor "
                               "(aynı kayıt sonradan yeniden girilmiş). Hiçbir şey değişmedi.")
            return False, f"Geri alınamadı, hiçbir şey değişmedi: {type(e).__name__}: {m[:160]}"

    # 4) Stok — tek stok kapısından, kalan net etki
    if k.get("tur") in STOKLU:
        try:
            tamam, atlanan = _stok_ters_cevir(sb, k.get("kod"))
        except Exception as e:  # noqa: BLE001
            tamam, atlanan = False, [f"{type(e).__name__}: {str(e)[:80]}"]
        if not tamam:
            try:
                from shared.hata_log import kaydet as _hk
                _hk("yukleme_gecmisi.geri_al.stok", RuntimeError(", ".join(map(str, atlanan[:10]))),
                    f"yükleme {kayit_id}", kritik=True)
            except Exception:  # noqa: BLE001
                pass
            return False, ("Satırlar geri alındı ama stok geri alma YARIM kaldı ("
                           + ", ".join(map(str, atlanan[:5])) + "). Kayıt 'yarım' işaretli; "
                           "'Tekrar dene' yalnız kalan stok hareketlerini uygular.")

    # 5) Bitir
    try:
        sb.table(TABLO).update({"durum": "geri_alindi", "geri_alan": str(kullanici or ""),
                                "geri_alma_zamani": datetime.now(timezone.utc).isoformat()}) \
          .eq("id", kayit_id).execute()
    except Exception as e:  # noqa: BLE001
        return False, f"Geri alındı ama kayıt durumu güncellenemedi: {type(e).__name__}"
    parcalar = []
    if satirli:
        parcalar.append(f"{d.get('silinen', 0)} satır silindi, {d.get('geri_yazilan', 0)} eski satır geri yazıldı")
    if k.get("tur") in STOKLU:
        parcalar.append("stok etkisi ters çevrildi")
    return True, "Yükleme geri alındı: " + "; ".join(parcalar) + "."


# ── Sayfa ───────────────────────────────────────────────────────────
def sayfa(aktif_kullanici, yonetici):
    import html as _h
    import streamlit as st
    from shared.tasarim import baslik as _sb
    from shared.yukleme_takvimi import sorumlu_adi

    st.markdown(_sb(":material/history: Yükleme geçmişi", "Excel yüklemeleri",
                    aciklama="kim · ne zaman · hangi dosya · geri alınabilenlerde tek tıkla geri al · "
                             + ("tüm kullanıcılar" if yonetici else "yalnız senin yüklemelerin")),
                unsafe_allow_html=True)
    mesaj = st.container()
    try:
        kayitlar = listele(kullanici=None if yonetici else aktif_kullanici)
    except Exception as e:  # noqa: BLE001
        st.warning("Yükleme geçmişi okunamadı. Supabase'de `veritabani/12_yuklemeler.sql` çalıştırılmış mı? "
                   f"({type(e).__name__})")
        return
    if not kayitlar:
        st.info("Henüz kayıtlı yükleme yok. Bundan sonraki Excel yüklemeleri burada görünecek.")
        return
    f1, f2 = st.columns(2)
    turler = sorted({k.get("tur") for k in kayitlar}, key=lambda t: TURLER.get(t, t))
    tf = f1.selectbox("Tür", ["Tümü"] + turler, key="yg_tur",
                      format_func=lambda t: t if t == "Tümü" else TURLER.get(t, t))
    kf = "Tümü"
    if yonetici:
        kf = f2.selectbox("Yükleyen", ["Tümü"] + sorted({str(k.get("kullanici") or "") for k in kayitlar}),
                          key="yg_kisi", format_func=lambda x: x if x == "Tümü" else (sorumlu_adi(x) or x or "?"))
    goster = [k for k in kayitlar if (tf == "Tümü" or k.get("tur") == tf)
              and (kf == "Tümü" or str(k.get("kullanici") or "") == kf)]
    st.caption(f"{len(goster)} yükleme")
    for k in goster[:150]:
        geri = k.get("durum") == "geri_alindi"
        with st.container(border=True):
            st.markdown(
                f'<div style="font-size:14px;font-weight:650">{_h.escape(TURLER.get(k.get("tur"), k.get("tur") or ""))}'
                + (' <span style="color:var(--k-silik);font-weight:500">· geri alındı</span>' if geri else "")
                + (' <span style="color:var(--k-kirmizi);font-weight:600">· geri alma yarım kaldı</span>'
                   if k.get("durum") == "geri_aliniyor" else "")
                + f'</div><div style="font-size:13px;color:var(--k-soluk)">{_h.escape(k.get("dosya_adi") or "dosya adı yok")}'
                f' · {int(k.get("satir_sayisi") or 0)} satır</div>'
                f'<div style="font-size:12px;color:var(--k-silik);margin-top:2px">'
                f'{_h.escape(sorumlu_adi(k.get("kullanici")) or k.get("kullanici") or "?")} · {yerel_zaman(k.get("zaman"))}'
                + (f' · {_h.escape(sorumlu_adi(k.get("geri_alan")) or k.get("geri_alan") or "?")} geri aldı '
                   f'({yerel_zaman(k.get("geri_alma_zamani"))})' if geri else "")
                + '</div>', unsafe_allow_html=True)
            if geri or not k.get("geri_alinabilir"):
                continue
            yarim = k.get("durum") == "geri_aliniyor"
            with st.expander("Geri almayı tamamla" if yarim else "Geri al", expanded=yarim):
                engel = geri_alma_engeli(k, kayitlar if yonetici else listele(), aktif_kullanici, yonetici)
                from shared.cop_kutusu import tablo_adi
                for t, (sil, gel) in onizleme(k).items():
                    st.caption(f"{tablo_adi(t)}: bu yüklemenin eklediği {sil} satır silinecek, "
                               f"üzerine yazdığı {gel} eski satır geri gelecek.")
                if k.get("tur") in STOKLU and k.get("kod"):
                    try:
                        etki = stok_etkisi(k.get("kod"))
                    except Exception:  # noqa: BLE001
                        etki = None
                    if etki is None:
                        st.caption("Stok etkisi okunamadı.")
                    elif not etki:
                        st.caption("Stok: değişecek bir şey yok.")
                    else:
                        from shared.tasarim import tr_sayi
                        st.caption(f"Stok: {len(etki)} ürün/depo satırı değişecek.")
                        st.dataframe([{"SKU": s_, "Depo": d_, "Değişim": tr_sayi(v_, 0)} for s_, d_, v_ in etki[:200]],
                                     hide_index=True, use_container_width=True, height=min(300, 40 + 35 * len(etki[:200])))
                if k.get("tur") == "g5f_sayim":
                    st.caption("Sayımın açtığı yeni boş ürün kartları ve stok yaşı tarihleri geri alınmaz.")
                if engel:
                    st.warning(engel)
                    continue
                if st.button("Tekrar dene" if yarim else "Bu yüklemeyi geri al", key=f"yg_geri_{k['id']}",
                             type="primary", icon=":material/undo:"):
                    ok, m = geri_al(k["id"], aktif_kullanici, yonetici)
                    (mesaj.success if ok else mesaj.error)(m)
                    if ok:
                        st.cache_data.clear()
                        st.toast(m)
                        st.rerun()

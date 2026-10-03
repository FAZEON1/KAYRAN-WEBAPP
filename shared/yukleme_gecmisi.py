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
# Geri alma bu aşamada yalnız stoğa dokunmayan, dilimi değiştiren yüklemelerde (Ekim 2026).
# Tablo listesi veritabanı fonksiyonundaki izin listesiyle AYNI olmalı (testte denetlenir).
GERI_ALINABILIR = {"musteri_haftalik": "firma_stok", "happylife": "happylife_stok",
                   "cek_listesi": "cekler", "havuz_butce": "ref_butce"}


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

    def iptal(self, neden):
        self._iptal = self._iptal or str(neden)

    @property
    def geri_alinabilir(self):
        return self.tur in GERI_ALINABILIR and not self._iptal and bool(self.degisiklik)

    def kaydet(self, satir_sayisi):
        return kaydet(self.tur, satir_sayisi, self.dosya_adi, self.anahtarlar,
                      self.degisiklik if self.geri_alinabilir else None, kod=self.kod)

    def stok(self):
        """Bu blok içindeki stok hareketleri bu yüklemeyle işaretlenir:
            with k.stok(): ice_aktar_satislar(...)"""
        try:
            from shared.stok_defteri import yukleme
            return yukleme(self.kod)
        except Exception:  # noqa: BLE001
            import contextlib
            return contextlib.nullcontext()


def kaydet(tur, satir_sayisi, dosya_adi="", anahtarlar=(), degisiklik=None, kod=""):
    """Geçmişe bir yükleme yazar. degisiklik verilirse geri alınabilir. Döner: id ya da None.
    ASLA hata fırlatmaz — yükleme her koşulda tamamlanmış sayılır."""
    try:
        import json
        satir = {"tur": str(tur), "dosya_adi": str(dosya_adi or "")[:200], "kullanici": _kullanici(),
                 "satir_sayisi": int(satir_sayisi or 0), "anahtarlar": list(anahtarlar or []),
                 "geri_alinabilir": bool(degisiklik),
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
    tum_kayitlar: yuklemeler satırları (aynı tür yeterli)."""
    if kayit.get("durum") != "aktif":
        return "Bu yükleme zaten geri alınmış."
    if not kayit.get("geri_alinabilir"):
        return "Bu yükleme türü şimdilik geri alınamaz (yalnız geçmişte görünür)."
    if not yonetici and str(kayit.get("kullanici") or "") != str(kullanici or ""):
        return "Yalnız kendi yüklemeni geri alabilirsin (yönetici herkesinkini alır)."
    benim = set(kayit.get("anahtarlar") or [])
    t0 = _zaman(kayit.get("zaman"))
    sonraki = [k for k in tum_kayitlar or []
               if k.get("id") != kayit.get("id") and k.get("tur") == kayit.get("tur")
               and k.get("durum") == "aktif" and _zaman(k.get("zaman")) > t0
               and benim & set(k.get("anahtarlar") or [])]
    if sonraki:
        s = max(sonraki, key=lambda k: _zaman(k.get("zaman")))
        return (f"Aynı veriye sonradan başka bir yükleme yapılmış ({yerel_zaman(s.get('zaman'))}, "
                f"{s.get('dosya_adi') or 'dosya adı yok'}). Önce onu geri al.")
    return ""


def onizleme(kayit):
    """{tablo: (silinecek, geri_gelecek)} — geri almadan önce ekranda gösterilir."""
    return {t: (len(d.get("eklenen") or []), len(d.get("onceki") or []))
            for t, d in (kayit.get("degisiklik") or {}).items()}


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


def geri_al(kayit_id, kullanici, yonetici=False):
    """Kuralı denetler, sonra veritabanında tek işlemde geri alır. Döner: (ok, mesaj)."""
    try:
        sb = _ham()
        k = (sb.table(TABLO).select("*").eq("id", kayit_id).execute().data or [None])[0]
        if not k:
            return False, "Yükleme kaydı bulunamadı."
        ayni = sb.table(TABLO).select("id, tur, zaman, durum, anahtarlar, dosya_adi") \
                 .eq("tur", k.get("tur")).eq("durum", "aktif").execute().data or []
        engel = geri_alma_engeli(k, ayni, kullanici, yonetici)
        if engel:
            return False, engel
        r = sb.rpc("yukleme_geri_al", {"p_id": int(kayit_id), "p_kullanici": str(kullanici or "")}).execute()
        d = r.data or {}
        return True, (f"Yükleme geri alındı: {d.get('silinen', 0)} satır silindi, "
                      f"{d.get('geri_yazilan', 0)} eski satır geri yazıldı.")
    except Exception as e:  # noqa: BLE001
        m = str(e)
        if "duplicate" in m.lower() or "23505" in m:
            return False, ("Geri alınamadı: eski satırlardan biri şu an başka bir kayıtla çakışıyor "
                           "(aynı ürün / tarih sonradan yeniden girilmiş). Hiçbir şey değişmedi.")
        return False, f"Geri alınamadı, hiçbir şey değişmedi: {type(e).__name__}: {m[:160]}"


# ── Sayfa ───────────────────────────────────────────────────────────
def sayfa(aktif_kullanici, yonetici):
    import html as _h
    import streamlit as st
    from shared.tasarim import baslik as _sb
    from shared.yukleme_takvimi import sorumlu_adi

    st.markdown(_sb("Yükleme geçmişi", "Excel yüklemeleri",
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
                + f'</div><div style="font-size:13px;color:var(--k-soluk)">{_h.escape(k.get("dosya_adi") or "dosya adı yok")}'
                f' · {int(k.get("satir_sayisi") or 0)} satır</div>'
                f'<div style="font-size:12px;color:var(--k-silik);margin-top:2px">'
                f'{_h.escape(sorumlu_adi(k.get("kullanici")) or k.get("kullanici") or "?")} · {yerel_zaman(k.get("zaman"))}'
                + (f' · {_h.escape(sorumlu_adi(k.get("geri_alan")) or k.get("geri_alan") or "?")} geri aldı '
                   f'({yerel_zaman(k.get("geri_alma_zamani"))})' if geri else "")
                + '</div>', unsafe_allow_html=True)
            if geri or not k.get("geri_alinabilir"):
                continue
            with st.expander("Geri al"):
                engel = geri_alma_engeli(k, kayitlar if yonetici else listele(), aktif_kullanici, yonetici)
                from shared.cop_kutusu import tablo_adi
                for t, (sil, gel) in onizleme(k).items():
                    st.caption(f"{tablo_adi(t)}: bu yüklemenin eklediği {sil} satır silinecek, "
                               f"üzerine yazdığı {gel} eski satır geri gelecek.")
                if engel:
                    st.warning(engel)
                    continue
                if st.button("Bu yüklemeyi geri al", key=f"yg_geri_{k['id']}", type="primary",
                             icon=":material/undo:"):
                    ok, m = geri_al(k["id"], aktif_kullanici, yonetici)
                    (mesaj.success if ok else mesaj.error)(m)
                    if ok:
                        st.cache_data.clear()
                        st.toast(m)
                        st.rerun()

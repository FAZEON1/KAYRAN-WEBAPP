# -*- coding: utf-8 -*-
"""KAYRAN — Çöp kutusu (Ekim 2026): silinen kayıtlar 30 gün saklanır, tek tıkla geri alınır.

NASIL: Merkezi sarmalayıcı (shared/audit.py) her silmede Supabase'in döndürdüğü
SİLİNEN SATIRLARI (silme varsayılan olarak returning=representation) sakla() ile
cop_kutusu tablosuna yazar. Modüllerin silme kodlarına dokunmak gerekmez; ileride
eklenecek silmeler de kendiliğinden kapsanır.

DIŞARIDA: birleştirme ve "sil-yeniden-yaz" işlemleri (Excel yeniden yüklemeleri,
yarım kaydın geri alınması, ayar/kilit yenileme) `with cop_kutusu_kapali():` ile —
yoksa kutu her yüklemede dolar, geri alınınca veri ikilenirdi. Şifre/oturum/log/geçici
tablolar da hiç yazılmaz (HARIC_TABLOLAR).

GÜVENCE: çöp kutusuna yazılamazsa (tablo kurulmamış vb.) silme YİNE çalışır, hata
kaydedilir. Geri alma satırı aynı kimlikle yazar; o kimlik doluysa ÜSTÜNE YAZMAZ.
Yetki: herkes kendi sildiğini, sistem yöneticisi herkesinkini görür ve geri alır.
"""
import contextlib
import contextvars
import json
import uuid
from datetime import datetime, timedelta, timezone

TABLO = "cop_kutusu"
SURE_GUN = 30
PARCA = 500                       # bir kayıtta en çok bu kadar satır
ISLEM_PENCERE_SN = 10             # aynı kişinin 10 sn içindeki silmeleri tek işlem
HARIC_TABLOLAR = {TABLO, "audit_log", "aktif_excel_verileri", "hata_kayitlari", "kullanici_durum",
                  "kullanici_sifreler", "giris_denemeleri"}

_KAPALI = contextvars.ContextVar("cop_kutusu_kapali", default=False)


@contextlib.contextmanager
def cop_kutusu_kapali():
    """Bu bloktaki silmeler çöp kutusuna yazılmaz (birleştirme / sil-yeniden-yaz)."""
    tok = _KAPALI.set(True)
    try:
        yield
    finally:
        _KAPALI.reset(tok)


def _ham():
    """Sarmalanmamış bağlantı: çöp kutusu yazımı denetim kaydına ve kendine düşmesin."""
    from shared.audit import _raw_client
    return _raw_client()


def _jsonla(rows):
    """Tarih / Decimal gibi değerler JSON'a sığsın (veri olduğu gibi geri yazılabilsin)."""
    return json.loads(json.dumps(rows, default=str))


def sakla(tablo, satirlar, modul=""):
    """Sarmalayıcı çağırır. ASLA hata fırlatmaz — silme her koşulda tamamlanır."""
    if not satirlar or tablo in HARIC_TABLOLAR or _KAPALI.get():
        return
    try:
        import shared.audit as _A
        silen = _A._aktif_kullanici()
        sb = _ham()
        grup = uuid.uuid4().hex
        zaman = datetime.now(timezone.utc).isoformat()
        rows = _jsonla(list(satirlar))
        for i in range(0, len(rows), PARCA):
            parca = rows[i:i + PARCA]
            sb.table(TABLO).insert({"grup": grup, "tablo": tablo, "modul": modul or "", "silen": silen or "",
                                    "zaman": zaman, "adet": len(parca), "satirlar": parca,
                                    "geri_alindi": False}).execute()
    except Exception as e:  # noqa: BLE001
        try:
            from shared.hata_log import kaydet
            kaydet(f"cop_kutusu.sakla.{tablo}", e)
        except Exception:  # noqa: BLE001
            pass


# ── Saf: gruplama, özet, süre ───────────────────────────────────────
def _zaman(v):
    try:
        z = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return z if z.tzinfo else z.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def islemlere_grupla(kayitlar, pencere_sn=ISLEM_PENCERE_SN):
    """Aynı kişinin art arda (pencere_sn içinde) silmeleri TEK işlem: ör. teknik servis
    kaydı + işlem geçmişi. Döner: en yeni işlem önce; işlem içinde parçalar silinme sırasıyla."""
    sirali = sorted(kayitlar, key=lambda k: (k.get("silen") or "", _zaman(k.get("zaman"))))
    islemler = []
    for k in sirali:
        son = islemler[-1] if islemler else None
        if (son and son["silen"] == (k.get("silen") or "")
                and (_zaman(k.get("zaman")) - _zaman(son["parcalar"][-1].get("zaman"))).total_seconds() <= pencere_sn):
            son["parcalar"].append(k)
        else:
            islemler.append({"silen": k.get("silen") or "", "parcalar": [k]})
    for i in islemler:
        i["zaman"] = i["parcalar"][-1].get("zaman")
        i["tablolar"] = list(dict.fromkeys(p["tablo"] for p in i["parcalar"]))
        i["adet"] = sum(int(p.get("adet") or 0) for p in i["parcalar"])
        i["modul"] = i["parcalar"][-1].get("modul") or ""
        i["id"] = "-".join(str(p.get("id")) for p in i["parcalar"])
    return sorted(islemler, key=lambda i: _zaman(i["zaman"]), reverse=True)


TABLO_AD = {"satislar": "Satış", "iadeler": "İade", "odemeler": "Ödeme", "haftalar": "Ödeme haftası",
            "bankalar": "Banka", "cekler": "Çek", "tahsilatlar": "Tahsilat", "virmanlar": "Virman",
            "aktif_manuel_kalemler": "Manuel aktif kalem", "ithalat_dosyalari": "İthalat dosyası",
            "ithalat_kalemleri": "İthalat kalemi", "urunler": "Ürün", "firma_stok": "Firma stok satırı",
            "kampanyalar": "Kampanya", "kampanya_urunler": "Kampanya ürünü", "ref_no": "Ref no",
            "ref_firmalar": "Ref firması", "ref_kayitlari": "Ref kaydı", "ref_butce": "Ref bütçesi",
            "ts_kayitlar": "Teknik servis kaydı", "ts_gecmis": "Teknik servis geçmişi",
            "depo_manuel_takip": "Bekleyen sevk takibi", "edefter_fisler": "e-Defter fişi",
            "edefter_fis_satirlari": "e-Defter fiş satırı", "prim_gecmis": "Prim ödemesi", "gorevler": "Görev",
            "happylife_stok": "Happy Life palet satırı"}

# Özet için tabloya göre en anlamlı alanlar (ilk dolu olanlar kullanılır)
_OZET_ALAN = ["servis_form_no", "siparis_no", "pi_no", "kampanya_adi", "firma", "firma_adi", "cari", "sku",
              "urun_adi", "stok_adi", "baslik", "donem", "aciklama", "banka_adi", "ad"]
_TUTAR_ALAN = ["tutar", "toplam_prim", "toplam", "fatura_adet"]


def tablo_adi(t):
    return TABLO_AD.get(t, t)


def ozet(tablo, satirlar):
    satirlar = satirlar or []
    if len(satirlar) != 1:
        return f"{len(satirlar)} satır"
    r = satirlar[0]
    parca = [str(r[a]) for a in _OZET_ALAN if r.get(a) not in (None, "")][:2]
    for a in _TUTAR_ALAN:
        if r.get(a) not in (None, "", 0):
            try:
                from shared.tasarim import tr_sayi
                parca.append(tr_sayi(float(r[a]), 2 if float(r[a]) % 1 else 0))
            except Exception:  # noqa: BLE001
                parca.append(str(r[a]))
            break
    return " · ".join(parca) or f"kayıt #{r.get('id', '?')}"


def yerel_zaman(zaman):
    """UTC saklanan zamanı İstanbul saatiyle 'GG.AA.YYYY SS:DD' (eskiden UTC görünüyordu)."""
    from zoneinfo import ZoneInfo
    z = _zaman(zaman)
    if z.year < 2000:
        return ""
    return z.astimezone(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")


def kalan_gun(zaman, simdi=None):
    simdi = simdi or datetime.now(timezone.utc)
    return max(0, SURE_GUN - (simdi - _zaman(zaman)).days)


# ── Veritabanı: listele, temizle, geri al ───────────────────────────
def temizle():
    """30 günden eski kayıtları kalıcı siler (sayfa açılınca)."""
    sinir = (datetime.now(timezone.utc) - timedelta(days=SURE_GUN)).isoformat()
    _ham().table(TABLO).delete().lt("zaman", sinir).execute()


def listele(silen=None):
    q = _ham().table(TABLO).select("*").eq("geri_alindi", False)
    if silen is not None:
        q = q.eq("silen", silen)
    return q.order("zaman", desc=True).limit(1000).execute().data or []


def geri_al(islem, geri_alan):
    """İşlemi TERS silinme sırasıyla geri yazar (önce ana kayıt, sonra bağlı satırlar).
    Aynı kimlikle kayıt varsa ÜSTÜNE YAZMAZ: o parça ve sonrası durur. Döner: (ok, mesaj)."""
    sb = _ham()
    yapilan = []
    for p in reversed(islem["parcalar"]):
        try:
            sb.table(p["tablo"]).insert(p["satirlar"]).execute()
        except Exception as e:  # noqa: BLE001
            m = str(e).lower()
            if "duplicate" in m or "unique" in m or "23505" in m:
                neden = (f"{tablo_adi(p['tablo'])}: aynı kimlikle bir kayıt zaten var (silindikten sonra yeniden "
                         f"oluşturulmuş olabilir) — üstüne yazılmadı")
            elif "foreign key" in m or "23503" in m:
                neden = f"{tablo_adi(p['tablo'])}: bağlı olduğu kayıt yok (önce onu geri al)"
            else:
                neden = f"{tablo_adi(p['tablo'])}: {type(e).__name__}: {str(e)[:120]}"
            ek = f" · {len(yapilan)} parça geri yazıldı" if yapilan else ""
            return False, neden + ek
        sb.table(TABLO).update({"geri_alindi": True, "geri_alan": geri_alan,
                                "geri_alma_zamani": datetime.now(timezone.utc).isoformat()}).eq("id", p["id"]).execute()
        p["geri_alindi"] = True
        yapilan.append(p)
    return True, f"{islem['adet']} satır geri alındı"


# ── Sayfa ───────────────────────────────────────────────────────────
def sayfa(aktif_kullanici, yonetici):
    import html as _h
    import streamlit as st
    from shared.tasarim import baslik as _sb
    from shared.yukleme_takvimi import sorumlu_adi

    st.markdown(_sb("🗑️ Çöp kutusu", "Silinen kayıtlar",
                    aciklama=f"{SURE_GUN} gün saklanır · tek tıkla geri alınır · "
                             + ("tüm kullanıcıların silmeleri" if yonetici else "yalnız senin sildiklerin")),
                unsafe_allow_html=True)
    mesaj = st.container()
    try:
        temizle()
        kayitlar = listele(silen=None if yonetici else aktif_kullanici)
    except Exception as e:  # noqa: BLE001
        st.warning("Çöp kutusu okunamadı. Supabase'de `veritabani/09_cop_kutusu.sql` çalıştırılmış mı? "
                   f"({type(e).__name__})")
        return
    islemler = islemlere_grupla(kayitlar)
    if not islemler:
        st.info("Çöp kutusu boş. Silinen kayıtlar burada 30 gün durur.")
        return

    f1, f2, f3 = st.columns(3)
    moduller = sorted({i["modul"] for i in islemler if i["modul"]})
    mf = f1.selectbox("Modül", ["Tümü"] + moduller, key="cop_modul")
    tablolar = sorted({t for i in islemler for t in i["tablolar"]}, key=tablo_adi)
    tf = f2.selectbox("Kayıt türü", ["Tümü"] + tablolar, key="cop_tablo",
                      format_func=lambda t: t if t == "Tümü" else tablo_adi(t))
    kf = "Tümü"
    if yonetici:
        kf = f3.selectbox("Silen", ["Tümü"] + sorted({i["silen"] for i in islemler}), key="cop_kisi",
                          format_func=lambda k: k if k == "Tümü" else sorumlu_adi(k))
    goster = [i for i in islemler if (mf == "Tümü" or i["modul"] == mf) and (tf == "Tümü" or tf in i["tablolar"])
              and (kf == "Tümü" or i["silen"] == kf)]
    st.caption(f"{len(goster)} silme işlemi · {sum(i['adet'] for i in goster)} satır")

    for i in goster[:100]:
        ana = i["parcalar"][-1]
        baslik = tablo_adi(ana["tablo"]) + ("" if len(i["parcalar"]) == 1 else
                                            " + " + ", ".join(f"{p['adet']} {tablo_adi(p['tablo']).lower()}"
                                                              for p in i["parcalar"][:-1]))
        kalan = kalan_gun(i["zaman"])
        with st.container(border=True):
            c1, c2 = st.columns([5, 1.2], vertical_alignment="center")
            c1.markdown(
                f'<div style="font-size:14px;font-weight:650">{_h.escape(baslik)}</div>'
                f'<div style="font-size:13px;color:var(--k-soluk)">{_h.escape(ozet(ana["tablo"], ana["satirlar"]))}</div>'
                f'<div style="font-size:12px;color:var(--k-silik);margin-top:2px">{_h.escape(i["modul"])} · '
                f'{_h.escape(sorumlu_adi(i["silen"]) or "?")} sildi · {yerel_zaman(i["zaman"])} · '
                f'<span style="color:var(--k-{"kirmizi" if kalan <= 3 else "silik"})">{kalan} gün sonra kalıcı '
                f'silinecek</span></div>', unsafe_allow_html=True)
            if c2.button("Geri al", key=f"cop_geri_{i['id']}", icon=":material/restore_from_trash:",
                         type="primary", use_container_width=True):
                ok, m = geri_al(i, aktif_kullanici)
                (mesaj.success if ok else mesaj.error)(("✅ " if ok else "Geri alınamadı — ") + m)
                if ok:
                    st.cache_data.clear()
                    st.toast("✅ " + m)
                    st.rerun()
            with st.expander("Silinen içeriği gör"):
                for p in i["parcalar"]:
                    st.caption(f"{tablo_adi(p['tablo'])} · {p['adet']} satır")
                    st.json(p["satirlar"][:20], expanded=False)
    if len(goster) > 100:
        st.caption(f"+{len(goster) - 100} işlem daha — filtreyle daralt.")

# -*- coding: utf-8 -*-
"""KAYRAN — Ana sayfa "Bugün" paneli.

NEDEN: Ana sayfa açılınca ilk ekranda motivasyon sözü, su hatırlatması ve
tanıtım metni vardı; "bugün neye bakmam lazım?" sorusunun cevabı yoktu.
Bu panel yalnız DİKKAT GEREKTİREN işleri, önem sırasına göre listeler:

  kritik  · vadesi GEÇMİŞ ödemeler · başarısız stok işlemleri
  uyarı   · BUGÜN vadeli ödemeler  · acil sipariş gereken ürünler
  bilgi   · YARIN vadeli ödemeler  · cevap bekleyen talepler
Rol bazlı (Ekim 2026, yalnız o modülün yetkilisine):
  teknik servis · 7 günden uzun mal kabulde / teknisyende bekleyen cihaz
  ithalat       · tahmini varışı geçmiş ve hâlâ gelmemiş dosya · 7 gün içinde gelecek dosya
  depo          · sevki tamamlanmamış elle takip kaydı
Madde hedefi "modul" ya da "modul/sayfa_kodu" (shared/gezinme) — Aç düğmesi doğrudan o sayfayı açar.

Her kaynak kendi try bloğunda: biri çökerse panel yine açılır, hata
Sistem Kayıtları'na düşer (sessizce yutulmaz).

Yapı: topla() veriyi getirir (Supabase), maddeler_*() saf fonksiyonlardır
(test edilir), html() çizer. Veri yoksa "her şey yolunda" gösterilir.
"""
import html as _h
from datetime import date, timedelta

from shared.tasarim import MONO

ONCELIK_SIRA = {"kritik": 0, "uyari": 1, "bilgi": 2}
ONCELIK_RENK = {"kritik": "var(--k-kirmizi)", "uyari": "var(--k-amber)", "bilgi": "var(--k-cyan)"}
# Rozet önceliği anlatır, zamanı değil (acil sipariş "bugün" değildir).
ONCELIK_ETIKET = {"kritik": "ACİL", "uyari": "ÖNEMLİ", "bilgi": "TAKİP"}


def _madde(oncelik, baslik, detay, sayi, hedef, anahtar):
    return {"oncelik": oncelik, "baslik": baslik, "detay": detay,
            "sayi": int(sayi), "hedef": hedef, "anahtar": anahtar}


def _isimler(liste, alan, n=3):
    adlar = [str(x.get(alan) or "").strip() for x in liste]
    adlar = [a for a in adlar if a]
    ek = f" +{len(adlar) - n}" if len(adlar) > n else ""
    return ", ".join(adlar[:n]) + ek


def _tl(v):
    try:
        return f"₺{float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "₺0"


def _vade(o):
    try:
        return date.fromisoformat(str(o.get("vade") or "")[:10])
    except ValueError:
        return None


# ── SAF FONKSİYONLAR (test edilir) ──────────────────────────────────
def maddeler_odeme(odemeler, bugun, kur=0.0):
    """Bekleyen ödemelerden vadesi geçmiş / bugün / yarın maddeleri."""
    bekleyen = [o for o in (odemeler or []) if o.get("durum") == "bekliyor"]
    gruplar = {"gecmis": [], "bugun": [], "yarin": []}
    for o in bekleyen:
        v = _vade(o)
        if v is None:
            continue
        if v < bugun:
            gruplar["gecmis"].append(o)
        elif v == bugun:
            gruplar["bugun"].append(o)
        elif v == bugun + timedelta(days=1):
            gruplar["yarin"].append(o)

    def _toplam(lst):
        return sum((o.get("tutar_tl") or 0) + (o.get("tutar_usd") or 0) * (kur or 0) for o in lst)

    m = []
    tanim = (("gecmis", "kritik", "Vadesi geçmiş ödeme"),
             ("bugun", "uyari", "Bugün vadeli ödeme"),
             ("yarin", "bilgi", "Yarın vadeli ödeme"))
    for anahtar, onc, baslik in tanim:
        lst = gruplar[anahtar]
        if lst:
            m.append(_madde(onc, baslik,
                            f"{_tl(_toplam(lst))} · {_isimler(lst, 'firma')}",
                            len(lst), "kayranacc", f"odeme_{anahtar}"))
    return m


def maddeler_acil_siparis(urunler):
    acil = [u for u in (urunler or []) if u.get("siparis_durum") == "acil"]
    if not acil:
        return []
    acil.sort(key=lambda u: (u.get("stok_bitis_gun") if isinstance(u.get("stok_bitis_gun"), (int, float)) else 9999))
    return [_madde("uyari", "Acil sipariş gereken ürün",
                   "En yakın: " + _isimler(acil, "sku"), len(acil), "kayranpm", "acil_siparis")]


def maddeler_stok_hatasi(hareketler, simdi_iso):
    """Son 7 günde başarısız stok işlemleri (stok_hareketleri, basarili=False)."""
    sinir = str(simdi_iso)[:10]
    try:
        sinir = (date.fromisoformat(sinir) - timedelta(days=7)).isoformat()
    except ValueError:
        pass
    son = [h for h in (hareketler or []) if str(h.get("zaman") or "")[:10] >= sinir]
    if not son:
        return []
    return [_madde("kritik", "Başarısız stok işlemi",
                   "Son 7 gün · SKU: " + _isimler(son, "sku"), len(son), "sistem_kayitlari", "stok_hata")]


def maddeler_talep(talepler):
    acik = [t for t in (talepler or []) if str(t.get("durum") or "") != "tamamlandi"]
    if not acik:
        return []
    return [_madde("bilgi", "Cevap bekleyen talep",
                   _isimler(acik, "konu"), len(acik), "talep", "talep")]


def _kim(d):
    """Uyarı başlığında sorumlunun adı (Ekim 2026: her yüklemenin bir sorumlusu var)."""
    return f" · 👤 {d['sorumlu_ad']}" if d.get("sorumlu_ad") else ""


def maddeler_yukleme(durumlar):
    """Dönemsel Excel yüklemeleri (shared/yukleme_takvimi). Geciken kırmızı,
    son 2 günü kalan sarı; güncel olanlar panele girmez (kartlarda görünür).
    Aynı sayfadaki birden çok geciken dosya TEK maddede birleşir (toplam
    aktiflerin üç dosyası üç ayrı madde olarak paneli kalabalıklaştırıyordu)."""
    m, yak = [], []
    gec = {}
    for d in durumlar or []:
        if d.get("seviye") == "gecikti":
            gec.setdefault(d["sayfa"], []).append(d)
        elif d.get("seviye") == "yaklasiyor":
            ne_zaman = "bugün son gün" if d.get("kalan_gun") == 0 else f"{d.get('kalan_gun')} gün kaldı"
            yak.append(_madde("uyari", f"{d['ad']} — {ne_zaman}{_kim(d)}",
                            f"{d.get('sonraki_adi', '')} · {d['sayfa']}",
                            max(0, int(d.get("kalan_gun") or 0)), d["modul"], f"yt_{d['anahtar']}"))
    for sayfa, ds in gec.items():
        en = max(int(x.get("gecikme_gun") or 0) for x in ds)
        from shared.yukleme_takvimi import eksik_ozeti
        en_cok = max(ds, key=lambda x: len(x.get("eksik_adlar") or []))
        eksik_m = eksik_ozeti(en_cok.get("eksik_adlar"), en_cok.get("siklik"))
        if len(ds) == 1:
            d = ds[0]
            m.append(_madde("kritik", f"{d['ad']} yüklenmedi{_kim(d)}",
                            f"{eksik_m} eksik · {en} gün gecikti · {sayfa}",
                            max(1, len(d.get("eksik_adlar") or [])), d["modul"], f"yt_{d['anahtar']}"))
        else:
            adlar = ", ".join(x["ad"].split(" · ")[-1] for x in ds)
            kimler = sorted({x.get("sorumlu_ad") for x in ds if x.get("sorumlu_ad")})
            m.append(_madde("kritik", f"{sayfa}: {len(ds)} dosya yüklenmedi"
                            + (f" · 👤 {', '.join(kimler)}" if kimler else ""),
                            f"{adlar} · {eksik_m} eksik · {en} gün gecikti",
                            len(ds), ds[0]["modul"], "yt_" + "_".join(x["anahtar"] for x in ds)))
    return m + yak


TS_BEKLEYEN = (("mal kabül", "Mal kabulde"), ("teknisyende", "Teknisyende"))
TS_ESIK_GUN = 7
ITHALAT_GELDI = "Teslim Alındı"


def _gun(v):
    try:
        return date.fromisoformat(str(v or "")[:10])
    except ValueError:
        return None


def maddeler_teknik_servis(kayitlar, bugun, esik=TS_ESIK_GUN):
    """Mal kabulde ya da teknisyende `esik` günden uzun bekleyen cihazlar (durum başına bir madde)."""
    m = []
    for durum, ad in TS_BEKLEYEN:
        uzun = []
        for k in kayitlar or []:
            if str(k.get("mevcut_durum") or "").strip().lower() != durum:
                continue
            g = _gun(k.get("mal_kabul_tarihi") or k.get("olusturma_tarihi"))
            if g and (bugun - g).days > esik:
                uzun.append(((bugun - g).days, k))
        if uzun:
            uzun.sort(key=lambda x: -x[0])
            m.append(_madde("uyari", f"{ad} {esik} günü geçen cihaz",
                            f"En eskisi {uzun[0][0]} gündür bekliyor · " + _isimler([k for _, k in uzun], "stok_adi"),
                            len(uzun), "teknikservis/servis", f"ts_{durum.split()[0]}"))
    return m


def maddeler_ithalat(dosyalar, bugun, gun=7):
    """Gelmemiş ithalat dosyaları: tahmini varışı geçmiş (uyarı) ve `gun` gün içinde gelecek (bilgi)."""
    yolda = [d for d in dosyalar or [] if str(d.get("durum") or "").strip() != ITHALAT_GELDI]
    gec, yakin = [], []
    for d in yolda:
        t = _gun(d.get("tahmini_varis"))
        if t is None:
            continue
        if t < bugun:
            gec.append(d)
        elif t <= bugun + timedelta(days=gun):
            yakin.append(d)
    m = []
    if gec:
        durumlar = sorted({str(d.get("durum") or "—") for d in gec})
        m.append(_madde("uyari", "Tahmini varışı geçmiş ithalat",
                        f"{', '.join(durumlar)} · " + _isimler(gec, "dosya_no"), len(gec),
                        "ithalat/gecmis", "ith_gecikmis"))
    if yakin:
        m.append(_madde("bilgi", f"{gun} gün içinde gelecek ithalat", _isimler(yakin, "dosya_no"), len(yakin),
                        "ithalat/gecmis", "ith_yakin"))
    return m


def maddeler_depo_sevk(takip):
    """Elle takipte faturalanmış ama tamamı sevk edilmemiş kayıtlar."""
    acik = []
    for t in takip or []:
        try:
            if float(t.get("sevk_edilen") or 0) < float(t.get("fatura_adet") or 0):
                acik.append(t)
        except (TypeError, ValueError):
            continue
    if not acik:
        return []
    return [_madde("bilgi", "Sevki tamamlanmamış kayıt", _isimler(acik, "firma"), len(acik),
                   "depo/bekleyen", "depo_sevk")]


def sirala(maddeler):
    return sorted(maddeler, key=lambda m: (ONCELIK_SIRA.get(m["oncelik"], 9), -m["sayi"]))


# ── VERİ TOPLAMA (Supabase) ─────────────────────────────────────────
def _basarisiz_stok_hareketleri():
    """Başarısız stok hareketleri — 60 sn önbellekli. Ana sayfa her açıldığında
    (her tıklamada) bu sorgu gidiyordu. streamlit burada içe aktarılır: test
    ortamında (streamlit yok) modülün kendisi yüklenebilsin."""
    import streamlit as st

    @st.cache_data(ttl=60, show_spinner=False)
    def _oku():
        from shared.stok_defteri import gecmis
        return gecmis(limit=200, yalniz_basarisiz=True)
    return _oku()


def _oku(tablo, kolonlar, suz=None):
    """Bugün paneli için hafif okuma (60 sn önbellek; en fazla 2.000 satır)."""
    import streamlit as st

    @st.cache_data(ttl=60, show_spinner=False)
    def _o(tablo, kolonlar, suz):
        from shared.auth import _get_supabase
        out = []
        for i in range(0, 2000, 1000):
            q = _get_supabase().table(tablo).select(kolonlar)
            if suz:
                q = q.in_(suz[0], list(suz[1]))
            r = q.range(i, i + 999).execute().data or []
            out += r
            if len(r) < 1000:
                break
        return out
    return _o(tablo, kolonlar, suz)


def topla(yetkiler, talep_yoneticisi=False, sistem_yoneticisi=False):
    """Kullanıcının yetkisi olan kaynaklardan maddeleri toplar."""
    from shared.hata_log import kaydet
    m = []
    bugun = date.today()
    try:
        from shared.utils import tr_today
        bugun = tr_today()
    except Exception as e:  # noqa: BLE001 — saat dilimi yoksa sunucu tarihi yeter
        kaydet("bugun.tarih", e)

    # Dönemsel yüklemeler: HERKES görür (yetkiye göre süzülmez — Ekim 2026 kararı)
    try:
        from shared.yukleme_takvimi import tum_durumlar
        m += maddeler_yukleme(tum_durumlar(bugun.isoformat()))
    except Exception as e:  # noqa: BLE001
        kaydet("bugun.yukleme_takvimi", e)

    if yetkiler.get("kayranacc"):
        try:
            from kayranacc.database import get_aktif_odemeler, get_kur
            odemeler, _ = get_aktif_odemeler()
            try:
                kur = float(get_kur() or 0)
            except Exception as e:  # noqa: BLE001
                kaydet("bugun.kur", e)
                kur = 0.0
            m += maddeler_odeme(odemeler, bugun, kur)
        except Exception as e:  # noqa: BLE001
            kaydet("bugun.odemeler", e)

    if yetkiler.get("kayranpm"):
        try:
            from kayranpm.analitik import dashboard_hesapla
            m += maddeler_acil_siparis(dashboard_hesapla())
        except Exception as e:  # noqa: BLE001
            kaydet("bugun.acil_siparis", e)

    if yetkiler.get("teknikservis"):
        try:
            m += maddeler_teknik_servis(_oku("ts_kayitlar", "id,mevcut_durum,mal_kabul_tarihi,olusturma_tarihi,stok_adi",
                                             ("mevcut_durum", tuple(d for d, _ in TS_BEKLEYEN))), bugun)
        except Exception as e:  # noqa: BLE001
            kaydet("bugun.teknik_servis", e)

    if yetkiler.get("ithalat"):
        try:
            m += maddeler_ithalat(_oku("ithalat_dosyalari", "id,dosya_no,durum,tahmini_varis"), bugun)
        except Exception as e:  # noqa: BLE001
            kaydet("bugun.ithalat", e)

    if yetkiler.get("depo"):
        try:
            m += maddeler_depo_sevk(_oku("depo_manuel_takip", "id,firma,fatura_adet,sevk_edilen"))
        except Exception as e:  # noqa: BLE001
            kaydet("bugun.depo", e)

    if sistem_yoneticisi:
        try:
            m += maddeler_stok_hatasi(_basarisiz_stok_hareketleri(), bugun.isoformat())
        except Exception as e:  # noqa: BLE001
            kaydet("bugun.stok_hata", e)

    if talep_yoneticisi:
        try:
            from kayranpm.database import get_talepler
            m += maddeler_talep(get_talepler())
        except Exception as e:  # noqa: BLE001
            kaydet("bugun.talepler", e)

    return sirala(m)


# ── ÇİZİM ───────────────────────────────────────────────────────────
def css():
    return f"""<style>
.bgn-satir{{display:flex;align-items:center;gap:12px;padding:10px 14px;
  background:var(--k-yuzey1);border:1px solid var(--k-kenar);border-left:3px solid var(--r);
  border-radius:10px;min-width:0}}
.bgn-sayi{{flex-shrink:0;min-width:34px;height:34px;border-radius:9px;display:flex;
  align-items:center;justify-content:center;font-family:{MONO};font-size:15px;font-weight:700;
  color:var(--r);background:color-mix(in srgb,var(--r) 14%,transparent)}}
.bgn-metin{{min-width:0;flex:1}}
.bgn-baslik{{color:var(--k-metin);font-size:13px;font-weight:600;display:flex;gap:8px;align-items:center}}
.bgn-rozet{{font-size:10px;font-weight:700;letter-spacing:.6px;color:var(--r)}}
.bgn-detay{{color:var(--k-soluk);font-size:12px;margin-top:2px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}}
.bgn-bos{{padding:14px 16px;border-radius:10px;border:1px solid color-mix(in srgb,var(--k-yesil) 30%,transparent);
  background:color-mix(in srgb,var(--k-yesil) 7%,transparent);color:var(--k-yesil2);font-size:13px}}
.st-key-bugun_panel [data-testid="stHorizontalBlock"]{{align-items:center;gap:8px}}
.st-key-bugun_panel .stButton button{{min-height:34px !important;height:34px !important;
  padding:0 12px !important;font-size:12px !important;background:transparent !important;
  border:1px solid var(--k-kenar2) !important;box-shadow:none !important;color:var(--k-soluk) !important;
  transform:none !important}}
.st-key-bugun_panel .stButton button:hover{{border-color:color-mix(in srgb,var(--k-mor) 45%,transparent) !important;
  color:var(--k-metin) !important}}
@media (max-width:640px){{
  .st-key-bugun_panel [data-testid="stHorizontalBlock"]{{flex-direction:row !important;flex-wrap:nowrap !important}}
  .st-key-bugun_panel [data-testid="stColumn"]:last-child{{flex:0 0 auto !important;width:auto !important;min-width:0 !important}}
  .st-key-bugun_panel [data-testid="stColumn"]:first-child{{flex:1 1 auto !important;min-width:0 !important}}
}}
</style>"""


def _kisi_ikonu(metin):
    """Başlıktaki sorumlu işareti (· 👤 Ad) → çizgi kişi ikonu (IKON_YENI)."""
    try:
        from shared.tasarim import IKON_YENI, ikon_html
        if IKON_YENI:
            return metin.replace("👤", ikon_html("person", 14))
    except Exception:  # noqa: BLE001
        pass
    return metin


def satir_html(m):
    r = ONCELIK_RENK.get(m["oncelik"], "var(--k-soluk)")
    return (f'<div class="bgn-satir" style="--r:{r}">'
            f'<div class="bgn-sayi">{m["sayi"]}</div>'
            f'<div class="bgn-metin"><div class="bgn-baslik">{_kisi_ikonu(_h.escape(m["baslik"]))}'
            f'<span class="bgn-rozet">{ONCELIK_ETIKET.get(m["oncelik"], "")}</span></div>'
            f'<div class="bgn-detay" title="{_h.escape(m["detay"], quote=True)}">{_h.escape(m["detay"])}</div>'
            f'</div></div>')


def bos_html():
    return ('<div class="bgn-bos">✓ Bugün dikkat gerektiren bir şey yok — '
            'vadesi gelen ödeme, acil sipariş ya da bekleyen talep bulunmuyor.</div>')

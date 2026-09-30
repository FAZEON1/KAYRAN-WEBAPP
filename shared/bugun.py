# -*- coding: utf-8 -*-
"""KAYRAN — Ana sayfa "Bugün" paneli.

NEDEN: Ana sayfa açılınca ilk ekranda motivasyon sözü, su hatırlatması ve
tanıtım metni vardı; "bugün neye bakmam lazım?" sorusunun cevabı yoktu.
Bu panel yalnız DİKKAT GEREKTİREN işleri, önem sırasına göre listeler:

  kritik  · vadesi GEÇMİŞ ödemeler · başarısız stok işlemleri
  uyarı   · BUGÜN vadeli ödemeler  · acil sipariş gereken ürünler
  bilgi   · YARIN vadeli ödemeler  · cevap bekleyen talepler

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


def sirala(maddeler):
    return sorted(maddeler, key=lambda m: (ONCELIK_SIRA.get(m["oncelik"], 9), -m["sayi"]))


# ── VERİ TOPLAMA (Supabase) ─────────────────────────────────────────
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

    if sistem_yoneticisi:
        try:
            from shared.stok_defteri import gecmis
            m += maddeler_stok_hatasi(gecmis(limit=200, yalniz_basarisiz=True), bugun.isoformat())
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
.st-key-bugun_panel .stButton button:hover{{border-color:rgba(129,140,248,.45) !important;
  color:var(--k-metin) !important}}
@media (max-width:640px){{
  .st-key-bugun_panel [data-testid="stHorizontalBlock"]{{flex-direction:row !important;flex-wrap:nowrap !important}}
  .st-key-bugun_panel [data-testid="stColumn"]:last-child{{flex:0 0 auto !important;width:auto !important;min-width:0 !important}}
  .st-key-bugun_panel [data-testid="stColumn"]:first-child{{flex:1 1 auto !important;min-width:0 !important}}
}}
</style>"""


def satir_html(m):
    r = ONCELIK_RENK.get(m["oncelik"], "var(--k-soluk)")
    return (f'<div class="bgn-satir" style="--r:{r}">'
            f'<div class="bgn-sayi">{m["sayi"]}</div>'
            f'<div class="bgn-metin"><div class="bgn-baslik">{_h.escape(m["baslik"])}'
            f'<span class="bgn-rozet">{ONCELIK_ETIKET.get(m["oncelik"], "")}</span></div>'
            f'<div class="bgn-detay" title="{_h.escape(m["detay"], quote=True)}">{_h.escape(m["detay"])}</div>'
            f'</div></div>')


def bos_html():
    return ('<div class="bgn-bos">✓ Bugün dikkat gerektiren bir şey yok — '
            'vadesi gelen ödeme, acil sipariş ya da bekleyen talep bulunmuyor.</div>')

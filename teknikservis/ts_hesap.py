# -*- coding: utf-8 -*-
"""Teknik Servis — saf hesaplar (Ekim 2026). Veritabanına gitmez, test edilir.

  ilk_gecis_haritasi  ts_gecmis satırlarından {kayit_id: {durum: ilk geçiş tarihi}}
  sla_kademe          iş günü → (grup adı, RENK anahtarı, sıra)
  sla_gruplari        kayıtları SLA kademesine göre (en acil önce) gruplar
  depo_gruplari       kayıtları depo sırasına göre gruplar
  sayi_ya_da_bos      Excel sayı sütunu: boş/metin → None, sayı → float
  excel_bayt          satır sözlükleri → .xlsx baytları
"""
from io import BytesIO


def ilk_gecis_haritasi(gecmis_rows):
    """Satırlar tarihe göre sıralı gelmese de her durum için EN ERKEN tarihi tutar."""
    h = {}
    for r in gecmis_rows or []:
        kid, durum, tarih = r.get("kayit_id"), str(r.get("durum") or ""), r.get("tarih")
        if kid is None or not tarih:
            continue
        d = h.setdefault(kid, {})
        if durum not in d or str(tarih) < str(d[durum]):
            d[durum] = tarih
    return h


_KADEMELER = [            # (alt sınır, grup adı, renk) — en acil önce
    (16, "16+ iş günü", "kirmizi"),
    (11, "11–15 iş günü", "kirmizi2"),
    (6, "6–10 iş günü", "amber"),
    (0, "0–5 iş günü", "yesil"),
]


def sla_kademe(is_gunu, bitmis=False):
    """Döner: (grup adı, RENK anahtarı, sıra). Sıra küçük = daha acil."""
    if bitmis:
        return "Tamamlanan", "silik", len(_KADEMELER)
    g = int(is_gunu or 0)
    for i, (alt, ad, renk) in enumerate(_KADEMELER):
        if g >= alt:
            return ad, renk, i
    return _KADEMELER[-1][1], _KADEMELER[-1][2], len(_KADEMELER) - 1


def sla_gruplari(kayitlar, gun_fn, bitmis_fn=lambda k: False):
    """[(grup adı, [kayıt…])] — gruplar en acilden başlar, grup içinde gelen sıra korunur."""
    gr = {}
    for k in kayitlar:
        ad, _r, sira = sla_kademe(gun_fn(k), bitmis_fn(k))
        gr.setdefault((sira, ad), []).append(k)
    return [(ad, ks) for (_s, ad), ks in sorted(gr.items(), key=lambda x: x[0][0])]


def depolar_kayitlari(kayitlar):
    """Depolar sayfasının kayıtları: depoya transfer edilenler + mal kabulde doğrudan depoya girip
    (ör. iade → MERKEZ DEPO) henüz transfer edilmeyenler. İkinciler kopyalanır ve bulundukları yer
    '_konum' alanına yazılır (teknik servis depo adı: 'merkez'; listede yoksa kanonik ad: 'HAPPY LIFE')
    — 'depo' alanı DOLDURULMAZ, kayıt transfer edilmemiş sayılmaya devam eder."""
    from .stok import TS_DEPO_HARITA, dogrudan_giris_mi, giris_deposu
    ters = {v: k for k, v in TS_DEPO_HARITA.items()}
    out = []
    for k in kayitlar or []:
        if (k.get("depo") or "").strip():
            out.append(k)
        elif dogrudan_giris_mi(k):
            g = giris_deposu(k)
            out.append(dict(k, _konum=ters.get(g, g)))
    return out


def konum(k):
    """Kaydın Depolar'daki yeri: transfer deposu, yoksa doğrudan giriş deposu."""
    return (k.get("depo") or k.get("_konum") or "").strip()


MERKEZ_DURUM = "merkeze aktarıldı"


def merkezde_mi(k):
    """Merkez deposuna aktarılmış (artık merkez ürünü; servis müdahale etmez)."""
    return (k.get("depo") or "").strip().lower() == "merkez" and (k.get("mevcut_durum") or "").strip() != "satıldı"


def gorunen_durum(k):
    """Depolar'da gösterilen durum: merkeze aktarılan ürün 'gönderildi' / 'satışa hazır' yerine
    'merkeze aktarıldı' (Ekim 2026, teknik servis isteği). Kayıtlı durum değişmez. Mikro'da iade faturası işlenip
    ürünü henüz gelmeyen kayıt 'mal kabul bekleniyor' (hasarlıysa ek açıklamayla)."""
    if bekleyen_mi(k):
        return bekleyen_etiket(k)
    return MERKEZ_DURUM if merkezde_mi(k) else (k.get("mevcut_durum") or "").strip()


# ── Mikro iade faturası → mal kabul bekleniyor (22.10.2026) ──────────
# Kullanıcı: "İlk durumda açıkça ayırt edebileceğim şekilde 'mal kabul bekleniyor' ibaresi olmalı … 1 ayı geçen
# mal kabul bekleniyor ürünleri olduğunda beni uyaran bildirim sistemi olmalı." Kaynak: teknikservis/mikro_iade.py.
FATURA_ISLENDI = "iade faturası işlendi"          # database.FATURA_ISLENDI ile aynı (döngüsel içe aktarma yok)
BEKLENIYOR = "mal kabul bekleniyor"
HASARLI_ETIKET = "mal kabul bekleniyor (teslim alınmayan hasarlı ürünler)"
UYARI_GUN = 30


def bekleyen_mi(k):
    return (k.get("mevcut_durum") or "").strip() == FATURA_ISLENDI


def bekleyen_etiket(k):
    return HASARLI_ETIKET if k.get("hasarli_teslim") else BEKLENIYOR


def bekleme_gunu(k, bugun):
    """İade faturasından bu yana takvim günü (fatura tarihi yoksa kayıt tarihi)."""
    from datetime import date
    s = str(k.get("iade_fatura_tarihi") or k.get("olusturma_tarihi") or "")[:10]
    try:
        return max(0, (bugun - date.fromisoformat(s)).days)
    except ValueError:
        return 0


def bekleyen_ozet(kayitlar, bugun):
    """İade arayüzünün üst bandı: {bekleyen, hasarli, gecikmis (UYARI_GUN günü geçen)}."""
    b = [k for k in kayitlar or [] if bekleyen_mi(k)]
    return {"bekleyen": len(b), "hasarli": sum(1 for k in b if k.get("hasarli_teslim")),
            "gecikmis": sum(1 for k in b if bekleme_gunu(k, bugun) > UYARI_GUN)}


def satis_disi_neden(k):
    """Depolar'da 'Satışa Hazır' / 'Satıldı' / toplu satışa KAPALI kayıt ise nedeni, değilse ''.
    Merkez deposuna aktarılan ürün ("gönderildi") artık MERKEZ DEPO stoğunda: normal satışla satılır. Burada
    'Satıldı' denirse MERKEZ DEPO'dan bir adet daha düşüyor ve ayrıca satış kaydı açılıyordu (Ekim 2026,
    teknik servis bildirimi)."""
    durum = (k.get("mevcut_durum") or "").strip()
    if durum == "satıldı":
        return "satıldı"
    if merkezde_mi(k):
        return "Merkez deposunda: normal satışla satılır"
    if durum == "gönderildi":
        return "Gönderildi"
    return ""


def depo_gruplari(kayitlar, depo_sirasi):
    """[(depo, [kayıt…])] — bilinen depolar verilen sırada, bilinmeyenler sonda."""
    gr = {}
    for k in kayitlar:
        gr.setdefault(konum(k) or "—", []).append(k)
    sira = {d: i for i, d in enumerate(depo_sirasi)}
    return sorted(gr.items(), key=lambda x: (sira.get(x[0], len(sira)), x[0]))


def sayi_ya_da_bos(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def excel_bayt(satirlar, sayfa_adi):
    import pandas as pd
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(satirlar).to_excel(w, index=False, sheet_name=str(sayfa_adi)[:28] or "Sayfa")
    return buf.getvalue()


def transfer_listesi(kayitlar, bas, bit, kaynak_fn, hedef_fn):
    """Mikro'ya transfer listesi (kullanıcı, 22.10.2026: "Kayran'daki teknik servis depo hareketleri gerçek stoğa
    işlenmesin; teknik servis depolarından aldığım Excel ile transferi Mikro'da yaparım"). Depoya transfer tarihi
    [bas, bit] aralığındaki kayıtlar, transfer sırasıyla. kaynak_fn / hedef_fn: kayıt → Mikro depo adı."""
    bas, bit = str(bas)[:10], str(bit)[:10]
    out = []
    for k in kayitlar or []:
        gun = str(k.get("depo_tarihi") or "").strip()[:10]
        if not (k.get("depo") or "").strip() or not gun or not (bas <= gun <= bit):
            continue
        out.append({"Transfer tarihi": f"{gun[8:10]}.{gun[5:7]}.{gun[0:4]}",
                    "Servis no": k.get("servis_form_no") or "", "Stok kodu": k.get("stok_kodu") or "",
                    "Stok adı": k.get("stok_adi") or "", "Seri no": k.get("seri_no") or "", "Adet": 1,
                    "Kaynak depo": kaynak_fn(k) or "", "Hedef depo": hedef_fn(k.get("depo")) or "",
                    "_sira": (gun, str(k.get("servis_form_no") or ""))})
    out.sort(key=lambda r: r["_sira"])
    for r in out:
        r.pop("_sira")
    return out

# -*- coding: utf-8 -*-
"""Teknik servis kayıtları ↔ depo stoğu (Ekim 2026) — SALT OKUNUR.

Teknik servis kaydı (ts_kayitlar) bir ürün birimidir. Kapanmamış kayıt (gönderildi / satıldı / iptal
dışındaki her durum) malın elimizde, bir depoda durduğunu söyler. Bulunduğu depo:
  · kayıtta depo yazılıysa o depo (teknikservis.stok.ts_depo_ad: 'ikinci el' → İKİNCİ EL DEPO),
  · yoksa girdiği depo (teknikservis.stok.giris_deposu: seçilen giriş deposu, yoksa iade → İADE DEPO,
    teknik → TEKNİK DEPO).
Bu sayfa her depo ve ürün için açık kayıt sayısını depo stoğuyla karşılaştırır. Fark ya kaydın durumu
güncellenmemiş (satıldı ama 'satışa hazır' duruyor) ya da stok yanlış demektir; hangisi olduğunu sayım
söyler. Satılabilir depolar (Merkez, Happy Life) karşılaştırılmaz: oradaki mal servis kaydından gelmez.
İade deposuna Excel iadeleri de girer; orada stoğun kayıttan fazla olması olağandır.
"""
from datetime import date

KAPALI_DURUMLAR = {"gönderildi", "satıldı", "iptal"}
# İşlemi sürmekte olan (bitmemiş) durumlar — uzun bekleyen listesi bunlardan
ISLEMDE_DURUMLAR = {"mal kabül", "teknisyende", "tamir edildi", "ürün değişimi", "iade alındı"}
BEKLEME_ESIK_GUN = 30
IADE_DEPO = "İADE DEPO"


def _tarih(v):
    s = str(v or "")[:10]
    try:
        return date.fromisoformat(s), s
    except ValueError:
        return None, ""


def acik_kayitlar(kayitlar, konum_bul):
    """Kapanmamış kayıtlar: [{id, form, sku, ad, durum, depo, tarih, personel}].
    konum_bul(kayit) → kanonik depo ya da None. tarih: depoya giriş (depo_tarihi; yoksa mal kabul)."""
    out = []
    for k in kayitlar or []:
        durum = str(k.get("mevcut_durum") or "").strip()
        if durum in KAPALI_DURUMLAR:
            continue
        _, t = _tarih(k.get("depo_tarihi") if str(k.get("depo") or "").strip() else None)
        if not t:
            _, t = _tarih(k.get("mal_kabul_tarihi"))
        _, kabul = _tarih(k.get("mal_kabul_tarihi"))
        out.append({"id": k.get("id"), "form": str(k.get("servis_form_no") or ""),
                    "sku": str(k.get("stok_kodu") or "").strip(), "ad": str(k.get("stok_adi") or "").strip(),
                    "durum": durum, "depo": konum_bul(k), "tarih": t, "kabul": kabul,
                    "personel": str(k.get("personel") or "").strip()})
    return out


def karsilastir(acik, stok, anahtar, satilabilir):
    """(depo, ürün) başına açık kayıt ↔ stok. stok: {(kanonik depo, anahtar(sku)): adet}.
    Yalnız kaydın ya da stoğun olduğu satılamayan depolar. Döner: [{depo, sku, ad, kayit, stok, fark}]
    (fark = stok − kayıt), önce farkı büyük olanlar."""
    say, adlar = {}, {}
    for k in acik:
        if not k["depo"] or k["depo"] in satilabilir or not k["sku"]:
            continue
        a = (k["depo"], anahtar(k["sku"]))
        say[a] = say.get(a, 0) + 1
        adlar.setdefault(a, (k["sku"], k["ad"]))
    depolar = {d for d, _ in say}
    out = []
    for a in set(say) | {a for a, v in stok.items() if a[0] in depolar and v}:
        kayit, st = say.get(a, 0), stok.get(a, 0)
        if kayit == st:
            continue
        sku, ad = adlar.get(a, (a[1], ""))
        out.append({"depo": a[0], "sku": sku, "ad": ad, "kayit": kayit, "stok": st, "fark": st - kayit})
    out.sort(key=lambda r: (-abs(r["fark"]), r["depo"], r["sku"]))
    return out


def depo_ozeti(acik, stok, satilabilir):
    """Depo başına {depo, kayit, stok, fark}; stok: {(depo, anahtar): adet}. Kaydı olan depolar."""
    kay = {}
    for k in acik:
        if k["depo"] and k["depo"] not in satilabilir and k["sku"]:
            kay[k["depo"]] = kay.get(k["depo"], 0) + 1
    out = []
    for d, n in kay.items():
        s = sum(v for (dd, _), v in stok.items() if dd == d)
        out.append({"depo": d, "kayit": n, "stok": s, "fark": s - n})
    return sorted(out, key=lambda o: (-abs(o["fark"]), o["depo"]))


def uzun_bekleyenler(acik, bugun, esik=BEKLEME_ESIK_GUN):
    """İşlemi süren (mal kabul / teknisyende / tamir edildi / değişim / iade alındı) ve mal kabulden bu
    yana esik günden uzun bekleyen kayıtlar, en eski önce."""
    out = []
    for k in acik:
        if k["durum"] not in ISLEMDE_DURUMLAR:
            continue
        d, _ = _tarih(k["kabul"])
        if d is None:
            continue
        gun = (bugun - d).days
        if gun > esik:
            out.append(dict(k, gun=gun))
    return sorted(out, key=lambda k: (-k["gun"], k["form"]))


def ts_partileri(acik, satilabilir):
    """Satılamayan stok raporunun yaş hesabı için giriş partileri: kayıt başına 1 adet, depoya giriş
    tarihiyle. İade deposu hariç (iade kaydı zaten Satış › İade'ye yazılır, oradan sayılır)."""
    return [{"depo": k["depo"], "sku": k["sku"], "tarih": k["tarih"], "adet": 1}
            for k in acik if k["depo"] and k["depo"] not in satilabilir and k["depo"] != IADE_DEPO
            and k["sku"] and k["tarih"]]


# ── Okuma ───────────────────────────────────────────────────────────
_SECIM = ("id, servis_form_no, arayuz, stok_kodu, stok_adi, mevcut_durum, depo, giris_depo, "
          "depo_tarihi, mal_kabul_tarihi, personel")


def konum(kayit):
    """Kaydın şu an bulunduğu depo (kanonik) ya da None."""
    from teknikservis.stok import giris_deposu, ts_depo_ad
    if str((kayit or {}).get("depo") or "").strip():
        from kayranpm.database import depo_kanonik
        return depo_kanonik(ts_depo_ad(kayit.get("depo")))
    return giris_deposu(kayit)


def acik_oku():
    from kayranpm.database import _hepsi
    return acik_kayitlar(_hepsi("ts_kayitlar", _SECIM) or [], konum)

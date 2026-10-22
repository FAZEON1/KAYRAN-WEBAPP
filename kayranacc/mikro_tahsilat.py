# -*- coding: utf-8 -*-
"""Tahsilat listesi — Mikro'daki müşteri alacaklarından (120), canlı (Ekim 2026). Ekran: kayranacc/tahsilat_ekran.py.

Kullanıcı (22.10.2026): "1 ve 3 yapalım" (öneri: ödeme listesinin tersi, vadesi gelen / geciken tahsilatlar).
Ödeme listesiyle aynı hesap (kayranacc.mikro_odeme.acik_kalemler, kalem_tipi=0): müşteriye kesilen fatura (borç)
kalemdir, tahsilat / iade / virman (alacak) en eski vadeden başlayarak düşülür (FIFO). Vade Mikro'dan: ödeme planı
(gün planın adından, "30 GÜN VADE"), taksit, vade tarihi; yoksa fatura günü.
Canlı (22.10.2026): 9.266 hareket, 923 açık kalem. En büyük iki alacak (VATAN 1.448.465 $, D-Market 533.292 $)
"30 GÜN SATIŞ ŞARTLI" planında: ödeme satışa bağlı, sabit vadesi yok — bu kalemler GECİKMİŞ sayılmaz, ayrı
"satışa bağlı" sütununda durur.
Pazartesi kaydı yok, veritabanına bir şey yazılmaz: liste her açılışta Mikro'dan hesaplanır (aktarıcı 15 dakikada
bir getirir). "Son 7 gün tahsil edilen" Mikro'daki tahsilat hareketlerinden (banka havalesi evrak 34, POS / kredi
kartı evrak 33; virman hariç).
"""
from collections import defaultdict
from datetime import timedelta

from . import mikro_odeme as O

ALACAK_ONEK = ("120",)
TAHSILAT_EVRAK = (34, 33)          # 34 banka gelen havale, 33 POS / kredi kartı (aynı türde virman da var: ayıklanır)
VIRMAN_SOZCUK = ("VİRMAN", "VIRMAN", "DEVİR", "DEVIR")
UFUK_HAFTA = 4                     # bu haftadan sonra kaç hafta ayrı sütun
SON_GUN = 7


def _s(v):
    return "" if v is None else str(v).strip()


def _buyuk(s):
    from shared.utils import tr_buyuk
    return tr_buyuk(_s(s))


# ── Saf ────────────────────────────────────────────────────────────
def plan_adlari(satirlar):
    """ODEME_PLANLARI satırları → {odp_no: ad}."""
    return {O._i(r.get("odp_no"), -1): _s(r.get("odp_adi")) for r in satirlar or [] if O._i(r.get("odp_no"), -1) > 0}


def satisa_bagli_mi(plan_adi):
    a = _buyuk(plan_adi).replace("İ", "I").replace("Ş", "S")
    return "SATIS SARTLI" in a


def ozet(kalemler, bugun, adlar=None):
    """Açık kalemler → müşteri × döviz satırları (büyükten küçüğe): {cari_kod, unvan, doviz, toplam, gecikmis,
    bu_hafta, sonraki: [UFUK_HAFTA hafta], ileri, satisa_bagli, en_eski_vade, gecikme_gun, kalem}.
    Satış şartlı plandaki kalem vadesine bakılmadan satisa_bagli'ya yazılır."""
    adlar = adlar or {}
    bas, son = O.hafta_araligi(bugun)
    out = {}
    for r in kalemler or []:
        k = (r["cari_kod"], r["doviz"])
        o = out.setdefault(k, {"cari_kod": r["cari_kod"], "unvan": r["unvan"], "doviz": r["doviz"], "toplam": 0.0,
                               "gecikmis": 0.0, "bu_hafta": 0.0, "sonraki": [0.0] * UFUK_HAFTA, "ileri": 0.0,
                               "satisa_bagli": 0.0, "en_eski_vade": None, "gecikme_gun": 0, "kalem": 0})
        a = float(r["acik"])
        o["toplam"] += a
        o["kalem"] += 1
        v = r.get("vade")
        if r.get("plan") and satisa_bagli_mi(adlar.get(r["plan"])):
            o["satisa_bagli"] += a
            continue
        if v is None or v < bas:
            o["gecikmis"] += a
            if v is not None and (o["en_eski_vade"] is None or v < o["en_eski_vade"]):
                o["en_eski_vade"] = v
                o["gecikme_gun"] = (bugun - v).days
        elif v <= son:
            o["bu_hafta"] += a
        else:
            hafta = (v - bas).days // 7 - 1
            if hafta < UFUK_HAFTA:
                o["sonraki"][hafta] += a
            else:
                o["ileri"] += a
    satir = [dict(o, toplam=round(o["toplam"], 2), gecikmis=round(o["gecikmis"], 2), bu_hafta=round(o["bu_hafta"], 2),
                  sonraki=[round(x, 2) for x in o["sonraki"]], ileri=round(o["ileri"], 2),
                  satisa_bagli=round(o["satisa_bagli"], 2)) for o in out.values() if o["toplam"] >= O.MIN_TUTAR]
    satir.sort(key=lambda r: (-r["toplam"], r["unvan"]))
    return satir


def son_tahsilatlar(hareketler, kartlar, bugun, gun=SON_GUN):
    """Son `gun` günde müşteri hesaplarına (120) düşen tahsilatlar: [{tarih, cari_kod, unvan, doviz, tutar, aciklama}]
    (yeni → eski). İade faturası (evrak 0) ve hesaplar arası virman tahsilat sayılmaz."""
    dov = {_s(k.get("cari_kod")): O._i(k.get("cari_doviz_cinsi")) for k in kartlar if _s(k.get("cari_kod"))}
    ad = {_s(k.get("cari_kod")): _s(k.get("cari_unvan1")) for k in kartlar}
    ilk = bugun - timedelta(days=gun)
    out = []
    for h in hareketler or []:
        kod = _s(h.get("cha_kod"))
        if (O._i(h.get("cha_tip"), -1) != 1 or O._i(h.get("cha_evrak_tip"), -1) not in TAHSILAT_EVRAK
                or kod not in dov or not kod.startswith(ALACAK_ONEK)):
            continue
        acik = _buyuk(h.get("cha_aciklama"))
        if any(w in acik for w in VIRMAN_SOZCUK):
            continue
        t = O._tarih(h.get("cha_tarihi"))
        if t is None or t < ilk or t > bugun:
            continue
        tutar = O.hareket_tutari(h, dov[kod])
        if tutar >= O.KURUS:
            out.append({"tarih": t, "cari_kod": kod, "unvan": ad.get(kod) or kod, "doviz": dov[kod],
                        "tutar": round(tutar, 2), "aciklama": _s(h.get("cha_aciklama"))})
    out.sort(key=lambda r: (r["tarih"], r["tutar"]), reverse=True)
    return out


def toplamlar(satirlar):
    """Döviz bazında sütun toplamları: {doviz: {toplam, gecikmis, bu_hafta, sonraki_toplam, satisa_bagli}}."""
    t = defaultdict(lambda: defaultdict(float))
    for r in satirlar or []:
        d = t[r["doviz"]]
        for a in ("toplam", "gecikmis", "bu_hafta", "ileri", "satisa_bagli"):
            d[a] += r[a]
        d["sonraki_toplam"] += sum(r["sonraki"])
    return {k: {a: round(v, 2) for a, v in d.items()} for k, d in t.items()}


# ── Veritabanı (yalnız okur) ───────────────────────────────────────
def veri_oku():
    from satis.mikro_esitle import sayfali_oku
    cli = O._cli()
    hareket = sayfali_oku(lambda: cli.table("mikro_cari_hareket").select(O._HAREKET_ALANLARI)
                          .eq("cha_cari_cins", O.CARI_CINS).like("cha_kod", f"{ALACAK_ONEK[0]}%")
                          .order("cha_guid"), "cha_guid")
    kart = sayfali_oku(lambda: cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1,cari_doviz_cinsi")
                       .order("cari_kod"), "cari_kod")
    pl = O._kesif("odeme_planlari")
    return {"hareket": hareket, "cari_kart": kart, "planlar": O.plan_gunleri(pl), "plan_adlari": plan_adlari(pl),
            "taksitler": O.taksit_haritasi(O._kesif("odeme_vadeleri"))}


def hesapla(veri, bugun):
    kal = O.acik_kalemler(veri["hareket"], veri["cari_kart"], veri.get("planlar"), veri.get("taksitler"),
                          onekler=ALACAK_ONEK, kalem_tipi=0)
    satir = ozet(kal, bugun, veri.get("plan_adlari"))
    return {"satirlar": satir, "toplam": toplamlar(satir),
            "son": son_tahsilatlar(veri["hareket"], veri["cari_kart"], bugun), "kalem": len(kal)}

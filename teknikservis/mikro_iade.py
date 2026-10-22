# -*- coding: utf-8 -*-
"""Mikro iade faturası → İade arayüzü (Ekim 2026). Ekran: Teknik Servis › İade (ts_masasi.kayit_masa_verisi).

Kullanıcı (22.10.2026): "Artık Serdar abi her iade faturası işlediğinde bu arayüze düşsün. Bir faturada 2 kalem
var: 1.de 5 adet, 2.de 1 adet; toplam 6 adet alt alta düşmesi sağlıklı olacaktır (her birine tek tek seri ve açıklama
gireceğim). Muhasebe faturayı işleyince yine G5F123 şeklinde otomatik belge no üretir; ilk aşama 'iade faturası
işlendi', ekranda 'mal kabul bekleniyor'. Serdar abinin girdiği açıklamayı aynı şekilde görmem lazım. Açıklamasız ya
da 'hasar' / 'teslim alınmayan hasarlı ürünler' yazanlar 'mal kabul bekleniyor (teslim alınmayan hasarlı ürünler)'.
Teknik servis iadesinde Serdar abi açıklamaya G5F123 yazar: kayıt eşleşip fatura bilgileri işlensin."

Kaynak: aktarıcının mikro_alim_satir tablosu (STOK_HAREKETLERI giriş satırları). İade faturası satırı = müşteri
carisinden (120) iade (sth_normal_iade 1) giriş. Kurallar:
  Başlangıç   BASLANGIC (kullanıcı: "sistemin ilk kaydından, bugünden") — öncesi alınmaz.
  Toplu iade  satırda TOPLU_SINIR'dan fazla adet (müşteri stok iadesi, ör. SND 3.120) alınmaz.
  Birim       her adet ayrı kayıt (anahtar: satır guid + sıra no); fiyat (tutar − iskonto) ÷ adet ÷ Mikro'nun satır
              dolar kuru (USD).
  G5F         açıklamada G5F no geçer ve o servis kaydı varsa YENİ kayıt açılmaz: fatura bilgisi o kayda yazılır,
              geçmişine "iade faturası işlendi" düşer (durumu değişmez; kayıt çoğu zaman depoya aktarılmıştır).
  Hasarlı     açıklama boş ya da 'HASAR' / 'TESLİM ALINMAYAN' geçiyor.
Kayran'dan Mikro'ya hiçbir şey yazılmaz; aynı birim ikinci kez açılmaz (ts_kayitlar.mikro_iade_anahtar).
"""
import re

DURUM_ANAHTAR = "mikro_iade_durum"
BASLANGIC = "2026-10-22"
TOPLU_SINIR = 20
MUSTERI = "120."
FATURA_ISLENDI = "iade faturası işlendi"
G5F_DESENI = re.compile(r"G5F\s*[-:]?\s*(\d+)")
SERI_DESENI = re.compile(r"SER[İI]\s*NO\s*[:.]?\s*([A-Z0-9][A-Z0-9\-/]{3,})")


def _f(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _i(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _s(v):
    return str(v or "").strip()


def _buyuk(s):
    from shared.utils import normalize_tr
    return normalize_tr(s)


def iade_satiri_mi(r, baslangic=BASLANGIC):
    """Müşteri iade faturası satırı mı (tarih başlangıçtan sonra, toplu stok iadesi değil)."""
    adet = _f(r.get("sth_miktar"))
    return (_i(r.get("sth_tip"), -1) == 0 and _i(r.get("sth_normal_iade")) == 1
            and _s(r.get("sth_cari_kodu")).startswith(MUSTERI)
            and _s(r.get("sth_tarih"))[:10] >= str(baslangic)
            and 0 < adet <= TOPLU_SINIR)


def g5f_no(aciklama):
    """Açıklamadaki servis form no → 'G5F00123' (yoksa None). Numara son 5 hane (database._sonraki_form_no)."""
    m = G5F_DESENI.search(_buyuk(aciklama))
    if not m:
        return None
    rakam = m.group(1)
    return f"G5F{int(rakam[-5:]):05d}"


def hasarli_mi(aciklama):
    """Açıklamasız iade ya da açıklamada 'hasar' / 'teslim alınmayan' (kullanıcı ile muhasebe kararı)."""
    a = _buyuk(aciklama)
    return not a.strip() or "HASAR" in a or "TESLIM ALINMAYAN" in a


def seri_onerisi(aciklama):
    """Açıklamadaki 'Seri No: X' (mal kabul formuna öneri; zorunlu alan yine elle onaylanır)."""
    m = SERI_DESENI.search(_buyuk(aciklama))
    return m.group(1) if m else ""


def birimler(satirlar, baslangic=BASLANGIC, kart_bul=None, unvan=None, depo_adi=None):
    """Mikro satırları → birim listesi (bir adet = bir satır), fatura tarihi + fatura no + kalem sırasıyla."""
    kart_bul = kart_bul or (lambda k: k)
    unvan, depo_adi = unvan or {}, depo_adi or {}
    out = []
    satir = sorted((r for r in satirlar or [] if iade_satiri_mi(r, baslangic)),
                   key=lambda r: (_s(r.get("sth_tarih")), _s(r.get("sth_evrakno_seri")),
                                  _i(r.get("sth_evrakno_sira")), _s(r.get("sth_guid"))))
    for r in satir:
        adet = int(_f(r.get("sth_miktar")))
        kur = _f(r.get("sth_alt_doviz_kuru")) or _f(r.get("sth_har_doviz_kuru"))
        tutar = _f(r.get("sth_tutar")) - _f(r.get("sth_iskonto"))
        birim_usd = round(tutar / adet / kur, 4) if adet and kur > 0 else 0.0
        ack = " ".join(_s(r.get("sth_aciklama")).split())
        seri, sira = _s(r.get("sth_evrakno_seri")), _i(r.get("sth_evrakno_sira"))
        cari = _s(r.get("sth_cari_kodu"))
        for n in range(1, adet + 1):
            out.append({
                "anahtar": f"{_s(r.get('sth_guid')).lower()}#{n}",
                "stok_kodu": kart_bul(_s(r.get("sth_stok_kod"))), "mikro_stok_kod": _s(r.get("sth_stok_kod")),
                "tarih": _s(r.get("sth_tarih"))[:10], "fatura_no": f"{seri}{sira}" if seri else str(sira),
                "cari_kodu": cari, "cari": unvan.get(cari) or cari, "aciklama": ack,
                "birim_usd": birim_usd, "kur": round(kur, 4),
                "depo": depo_adi.get(_i(r.get("sth_giris_depo_no")), ""),
                "g5f": g5f_no(ack), "hasarli": hasarli_mi(ack), "seri_onerisi": seri_onerisi(ack),
                "adet_sira": f"{n}/{adet}",
            })
    return out


def plan_yap(birim_listesi, kayitlar):
    """Döner: {yeni: [birim], eslesen: [(kayit, birim)]}. Daha önce işlenmiş birim (mikro_iade_anahtar) atlanır;
    G5F'li birim, o servis no'lu ve henüz faturası işlenmemiş kayda bağlanır (bir kayda bir birim)."""
    islenmis = {_s(k.get("mikro_iade_anahtar")) for k in kayitlar or [] if _s(k.get("mikro_iade_anahtar"))}
    form = {}
    for k in kayitlar or []:
        f = _s(k.get("servis_form_no")).upper()
        if f and not _s(k.get("mikro_iade_anahtar")):
            form.setdefault(f, k)
    yeni, eslesen, kullanilan = [], [], set()
    for b in birim_listesi:
        if b["anahtar"] in islenmis:
            continue
        k = form.get(b["g5f"] or "")
        if k is not None and k.get("id") not in kullanilan:
            kullanilan.add(k.get("id"))
            eslesen.append((k, b))
        else:
            yeni.append(b)
    return {"yeni": yeni, "eslesen": eslesen}


def _fatura_alanlari(b):
    return {"mikro_iade_anahtar": b["anahtar"], "iade_fatura_no": b["fatura_no"], "iade_fatura_tarihi": b["tarih"],
            "iade_aciklama": b["aciklama"], "iade_cari_kodu": b["cari_kodu"], "iade_fiyat": b["birim_usd"],
            "iade_pb": "USD", "iade_net": b["birim_usd"], "iade_kur": b["kur"]}


def yeni_kayit(b, form_no, stok_adi=""):
    """Birim → ts_kayitlar satırı (durum 'iade faturası işlendi'; mal kabul tarihi fiziksel kabulde yazılır)."""
    return dict(_fatura_alanlari(b), **{
        "servis_form_no": form_no, "arayuz": "iade", "mevcut_durum": FATURA_ISLENDI,
        "stok_kodu": b["stok_kodu"], "stok_adi": stok_adi, "firma_bilgisi": b["cari"],
        "giris_depo": b["depo"] or None, "hasarli_teslim": b["hasarli"], "fatura_mevcut": True,
        "ariza": b["aciklama"] or "teslim alınmayan hasarlı ürün (açıklama yok)"})


def gecmis_metni(b):
    return (f"Mikro iade faturası {b['fatura_no']} ({b['adet_sira']}) · {b['cari']}"
            + (f" · açıklama: {b['aciklama']}" if b["aciklama"] else " · açıklama yok"))


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from satis.database import _get_client
    return _get_client()


def veri_oku():
    from ithalat.mikro_ithalat import _sayfali
    from shared.utils import sku_anahtar
    cli = _cli()
    satir = [r for r in (cli.table("mikro_alim_satir").select("*").eq("sth_normal_iade", 1)
                         .gte("sth_tarih", BASLANGIC).like("sth_cari_kodu", MUSTERI + "%")
                         .limit(5000).execute().data or [])]
    kartlar = {}
    for u in _sayfali("urunler", "sku,urun_adi", "sku"):
        kartlar.setdefault(sku_anahtar(u.get("sku")), u)
    unvan = {}
    for c in cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1").like("cari_kod", MUSTERI + "%").execute().data or []:
        unvan[_s(c.get("cari_kod"))] = " ".join(_s(c.get("cari_unvan1")).split())
    from kayranpm.database import depo_kanonik
    depo = {_i(d.get("dep_no")): depo_kanonik(d.get("dep_adi") or "")
            for d in cli.table("mikro_depo_kart").select("dep_no,dep_adi").execute().data or []}
    bl = birimler(satir, BASLANGIC, lambda k: (kartlar.get(sku_anahtar(k)) or {}).get("sku") or k, unvan, depo)
    adlar = {sku_anahtar(k): (u.get("urun_adi") or "") for k, u in kartlar.items()}
    kayitlar = cli.table("ts_kayitlar").select("id,servis_form_no,mikro_iade_anahtar").execute().data or []
    return bl, kayitlar, adlar


def uygula(plan, adlar=None, personel="Mikro"):
    """Yeni kayıtları açar (G5F no sırayla), eşleşenlere fatura bilgisini yazar. Döner: {yeni, eslesen, hata}."""
    from shared.utils import sku_anahtar
    from . import database as D
    cli = _cli()
    adlar = adlar or {}
    simdi = D._simdi()
    sonuc = {"yeni": 0, "eslesen": 0, "hata": []}
    if plan["yeni"]:
        bas = int(D._sonraki_form_no()[3:])
        for i, b in enumerate(plan["yeni"]):
            try:
                if cli.table("ts_kayitlar").select("id").eq("mikro_iade_anahtar", b["anahtar"]).execute().data:
                    continue
                k = yeni_kayit(b, f"G5F{bas + i:05d}", adlar.get(sku_anahtar(b["stok_kodu"]), ""))
                r = cli.table("ts_kayitlar").insert(k).execute()
                kid = (r.data or [{}])[0].get("id")
                if kid is not None:
                    cli.table("ts_gecmis").insert({"kayit_id": kid, "durum": FATURA_ISLENDI, "personel": personel,
                                                   "aciklama": gecmis_metni(b), "tarih": simdi}).execute()
                sonuc["yeni"] += 1
            except Exception as e:  # noqa: BLE001
                sonuc["hata"].append(f"{b['fatura_no']}: {type(e).__name__}: {str(e)[:120]}")
    for k, b in plan["eslesen"]:
        try:
            cli.table("ts_kayitlar").update(_fatura_alanlari(b)).eq("id", k["id"]).execute()
            cli.table("ts_gecmis").insert({"kayit_id": k["id"], "durum": FATURA_ISLENDI, "personel": personel,
                                           "aciklama": gecmis_metni(b), "tarih": simdi}).execute()
            sonuc["eslesen"] += 1
        except Exception as e:  # noqa: BLE001
            sonuc["hata"].append(f"{k.get('servis_form_no')}: {type(e).__name__}: {str(e)[:120]}")
    try:
        D._cache_temizle()
    except Exception:  # noqa: BLE001
        pass
    return sonuc


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    """Varsayılan AÇIK; {"acik": false} kapatır."""
    return durum().get("acik", True) is not False


BILDIRIM_ALICILARI = ("ibrahim",)       # durum["bildirim_alicilari"] ile değiştirilebilir


def gecikme_mesaji(kayitlar, bugun):
    """30 günü geçen 'mal kabul bekleniyor' kayıtları için bildirim metni (yoksa None)."""
    from .ts_hesap import UYARI_GUN, bekleme_gunu, bekleyen_mi
    gec = [k for k in kayitlar or [] if bekleyen_mi(k) and bekleme_gunu(k, bugun) > UYARI_GUN]
    if not gec:
        return None
    ornek = ", ".join(_s(k.get("servis_form_no")) for k in gec[:5])
    return (f"Teknik Servis › İade: {len(gec)} ürün {UYARI_GUN} günden uzun süredir mal kabul bekliyor"
            f" ({ornek}{' …' if len(gec) > 5 else ''}).")


def gecikme_bildirimi(bugun=None):
    """Günde bir kez Kayran bildirimi (kullanıcı: "1 ayı geçen mal kabul bekleniyor ürünleri olduğunda beni uyaran
    bildirim"). Döner: gönderildiyse metin."""
    from datetime import date
    bugun = bugun or date.today()
    d = durum()
    if d.get("son_bildirim_gunu") == bugun.isoformat():
        return None
    rows = (_cli().table("ts_kayitlar").select("servis_form_no,mevcut_durum,iade_fatura_tarihi,olusturma_tarihi")
            .eq("mevcut_durum", FATURA_ISLENDI).execute().data or [])
    msg = gecikme_mesaji(rows, bugun)
    if not msg:
        return None
    from shared.izin import bildir
    bildir(d.get("bildirim_alicilari") or BILDIRIM_ALICILARI, msg, "kayran")
    from kayranacc.database import set_ayar
    d["son_bildirim_gunu"] = bugun.isoformat()
    set_ayar(DURUM_ANAHTAR, d)
    return msg


def otomatik():
    """Eşitleme turu (otonom/mikro_esitle.ISLER). Yazdıysa metin, yoksa None. Hata fırlatmaz."""
    try:
        if not acik_mi():
            return None
        bl, kayitlar, adlar = veri_oku()
        plan = plan_yap(bl, kayitlar)
        bildirim = gecikme_bildirimi()
        if not plan["yeni"] and not plan["eslesen"]:
            return "geciken mal kabul bildirimi gönderildi" if bildirim else None
        s = uygula(plan, adlar)
        from kayranacc.database import set_ayar
        d = durum()
        d.update(son_sonuc={k: (v if k != "hata" else v[:10]) for k, v in s.items()})
        set_ayar(DURUM_ANAHTAR, d)
        return f"iade faturası: {s['yeni']} yeni kayıt, {s['eslesen']} servis kaydına bağlandı"
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("teknikservis.mikro_iade.otomatik", e)
        return None

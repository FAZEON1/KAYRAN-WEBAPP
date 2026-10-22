# -*- coding: utf-8 -*-
"""Haftalık ödeme listesi Mikro'dan, her pazartesi kendiliğinden (Ekim 2026). Hesap: kayranacc/mikro_odeme.py.

Kullanıcı (22.10.2026): "Ödeme listesini de Mikro'dan çekelim" → "her pazartesi kendiliğinden açılsın". Excel
yüklemesi (Dosya kapısı › Haftalık ödeme listesi) bu açıkken kapıdan kalkar; kod yedekte durur.

Pazartesi (o hafta ilk eşitleme turunda; pazartesi tur olmadıysa ertesi günlerde) yeni hafta açılır ve aktif olur:
  - Mikro'daki açık cari borçlar (320, 336) — vadesi geçmiş olanlar dahil, 6 hafta ilerisine kadar.
    Mikro'da vade girilmemiş faturada firma vadesi kullanılır: elle hazırlanan geçmiş listelerden öğrenilir
    (Happy Life 30, UPS 15 gün …); "Firma vadeleri" penceresinden düzeltilen gün sonraki pazartesiden geçerli.
  - Ödenmemiş firma çekleri; muhtasar ve SGK (Mikro 360 / 361 bakiyesi); maaş (335; tahakkuk etmediyse geçen
    ayınki, "tahmini"); her ay aynı gelen faturalar (kira, aidat; kesilmediyse "tahmini").
  - Önceki haftada elle eklenmiş, ödenmemiş satırlar (KDV, GEKAP, DBS …) taşınır; Mikro'da karşılığı olanlar taşınmaz.
Hafta boyunca her eşitleme turunda (aktarıcı yeni cari verisi getirdiyse):
  - Mikro'da kapanan kalemin satırı "ödendi" olur (yalnız durum; banka bakiyesi Mikro'dan gelir, dokunulmaz).
  - Yeni gelen fatura / çek eklenir; tutarı değişen satır güncellenir — kullanıcı satırı düzelttiyse dokunulmaz.
  - Gerçek faturası gelen "tahmini" satır kaldırılır (yerine gerçek satır gelir).
  - Kullanıcının sildiği satır geri eklenmez; elle işaretlenen (ödendi) satıra dokunulmaz.
Satır ↔ Mikro kalemi eşlemesi sistem_ayarlari mikro_odeme_durum içinde tutulur (haftalar → anahtar → ödeme id).
O haftanın listesi Excel'le zaten yüklendiyse (aynı adlı hafta) o hafta açılmaz, Excel haftasına dokunulmaz.

Kapatmak: sistem_ayarlari mikro_odeme_durum = {"acik": false, …} (varsayılan AÇIK, kullanıcı kararı).
"""
from datetime import date, datetime, timedelta, timezone

from . import mikro_odeme as O

DURUM_ANAHTAR = "mikro_odeme_durum"
UFUK_GUN = 41               # pazartesiden 6 hafta (elle hazırlanan liste de ~5 hafta ilerisini taşıyordu)
TAZE_SAAT = 48              # Mikro cari verisi bundan eskiyse hafta açılmaz (eski veriyle liste olmasın)
SAKLA_HAFTA = 8             # durumda tutulan hafta eşlemesi
KURUS = 0.005
KAPANDI_NOTU = " · Mikro'da kapandı"


def _f(v):
    try:
        x = float(v)
        return x if x == x else 0.0
    except (TypeError, ValueError):
        return 0.0


def _s(v):
    return "" if v is None else str(v).strip()


# ── Saf ────────────────────────────────────────────────────────────
def pazartesi(bugun):
    return bugun - timedelta(days=bugun.weekday())


def liste_satirlari(veri, bas, bugun, gunler):
    """Haftanın Mikro satırları (her biri 'anahtar' taşır). veri: veri_oku(). Döner: (satırlar, uyarılar)."""
    son = bas + timedelta(days=UFUK_GUN)
    kalem = O.acik_kalemler(veri["hareket"], veri["cari_kart"], veri.get("planlar"), veri.get("taksitler"),
                            gunler=gunler)
    satir, uyari = O.oneri_satirlari(kalem, veri.get("cekler"), bas, son, gecikmis_dahil=True)
    faturalar = O.fatura_kalemleri(veri["hareket"], veri["cari_kart"])
    satir += O.tekrar_tahminleri(faturalar, bugun, son, gunler)
    satir += O.donem_borclari(veri.get("muhasebe"), bugun, son)
    satir += O.maas_satirlari(veri.get("muhasebe"), bugun, son)
    tekil, gorulen = [], set()
    for r in satir:
        if r["anahtar"] not in gorulen:
            gorulen.add(r["anahtar"])
            tekil.append(dict(r, sec=True, manuel=0))
    tekil.sort(key=lambda r: (r["vade"], r["kategori"] != O.CEK_KATEGORI, r["firma"]))
    return tekil, uyari


def _benzer_var(o, yeni, gun=3):
    """Firma adı farklı yazılmış ama aynı ödeme: aynı para birimi, tutar ±%1 ve vade ±3 gün (elle listedeki "KEYAP
    KASIM AYI AİDATI" ↔ Mikro carisi "S.S. İSTANBUL ANADOLU YAKASI KERESTE … KOOPERATİFİ", 12.180)."""
    usd, tl = _f(o.get("tutar_usd")), _f(o.get("tutar_tl"))
    pb, t = ("usd", usd) if usd >= KURUS else ("tl", tl)
    v = O._tarih(o.get("vade"))
    if t < KURUS or v is None:
        return False
    for r in yeni:
        rv = O._tarih(r.get("vade"))
        if rv and abs((rv - v).days) <= gun and abs(_f(r.get(pb)) - t) <= max(1.0, 0.01 * t):
            return True
    return False


def tasinacaklar(onceki, onceki_mikro_idler, yeni):
    """Önceki haftadan taşınan elle satırlar: ödenmemiş, Mikro'dan açılmamış, yeni listede aynı firma (aynı para
    birimi) yok. İlk Mikro haftasında önceki hafta Excel'le yüklenmiştir: Mikro'nun karşıladığı satırlar (UPS, SGK …)
    yeni listede olduğu için taşınmaz, karşılığı olmayanlar (KDV, GEKAP, DBS …) taşınır."""
    aday = [o for o in onceki or [] if o.get("durum") == "bekliyor" and o.get("id") not in onceki_mikro_idler]
    kalan = [o for o in O.karsilastir(yeni, aday)["yalniz_mevcut"] if not _benzer_var(o, yeni)]
    return [{"firma": o.get("firma"), "aciklama": o.get("aciklama"), "cari_banka": o.get("cari_banka"),
             "vade": o.get("vade"), "tl": o.get("tutar_tl"), "usd": o.get("tutar_usd"),
             "kategori": o.get("kategori") or "diger", "manuel": 1} for o in kalan]


def _yuvarla(v):
    v = _f(v)
    return round(v, 2) if v >= KURUS else None


def _iz(r):
    """Satırın en son yazılan hâli (kullanıcı düzeltmesini ayırt etmek için)."""
    return {"tl": _yuvarla(r.get("tl", r.get("tutar_tl"))), "usd": _yuvarla(r.get("usd", r.get("tutar_usd"))),
            "aciklama": _s(r.get("aciklama"))}


def _ayni_iz(a, b):
    return (abs(_f(a.get("tl")) - _f(b.get("tl"))) < 0.01 and abs(_f(a.get("usd")) - _f(b.get("usd"))) < 0.01
            and _s(a.get("aciklama")) == _s(b.get("aciklama")))


def guncelleme_plani(esleme, mevcut, yeni):
    """esleme: {anahtar: {"id", "tl", "usd", "aciklama"}} (haftaya en son yazılan); mevcut: {id: odemeler satırı};
    yeni: liste_satirlari. Döner: {"ekle": [satır], "kapandi": [(anahtar, id)], "sil": [(anahtar, id)],
    "guncelle": [(anahtar, id, {alan: değer}, yeni iz)]}."""
    yeni_h = {r["anahtar"]: r for r in yeni}
    plan = {"ekle": [r for k, r in yeni_h.items() if k not in esleme], "kapandi": [], "sil": [], "guncelle": []}
    for k, e in esleme.items():
        oid = e.get("id")
        row = mevcut.get(oid)
        if row is None or row.get("durum") != "bekliyor":
            continue                                    # kullanıcı sildi / ödendi işaretledi: dokunma
        duzeltilmis = not _ayni_iz(_iz(row), e)
        y = yeni_h.get(k)
        if y is None:
            plan["sil" if k.startswith("t|") else "kapandi"].append((k, oid))
            continue
        iz = _iz(y)
        if duzeltilmis or _ayni_iz(iz, e):
            continue
        plan["guncelle"].append((k, oid, {"tutar_tl": iz["tl"], "tutar_usd": iz["usd"], "aciklama": iz["aciklama"]},
                                 iz))
    return plan


def gecmis_satirlari(odemeler, mikro_hafta_idler):
    """Vade öğrenmesi için elle hazırlanmış haftaların satırları (Mikro'nun açtığı haftalar hariç)."""
    return [o for o in odemeler or [] if o.get("hafta_id") not in mikro_hafta_idler]


# ── Durum ──────────────────────────────────────────────────────────
def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    """Varsayılan AÇIK (kullanıcı kararı 22.10.2026); yalnız {"acik": false} kapatır."""
    return durum().get("acik", True) is not False


def _kaydet(d):
    from kayranacc.database import set_ayar
    haftalar = d.get("haftalar") or {}
    if len(haftalar) > SAKLA_HAFTA:
        for k in sorted(haftalar, key=lambda x: int(x))[:-SAKLA_HAFTA]:
            haftalar.pop(k, None)
    set_ayar(DURUM_ANAHTAR, d)


def mikro_haftasi(hafta_id, d=None):
    """Bu hafta Mikro'dan mı açıldı (eşleme kaydı var mı)."""
    return str(hafta_id) in ((d if d is not None else durum()).get("haftalar") or {})


def mikro_idleri(hafta_id, d=None):
    """Haftanın Mikro'dan gelen ödeme satırlarının kimlikleri (eşleme kaydı). Bu satırların ödendi / bekliyor
    durumu Mikro'dan gelir (fatura kapanınca ödendi olur); ekranda elle "Öde" seçeneği yoktur (kullanıcı,
    22.10.2026: "ödemeler Mikro'dan geleceği için ödeme yapıldı vs. seçenekleri olmasın")."""
    kayit = ((d if d is not None else durum()).get("haftalar") or {}).get(str(hafta_id)) or {}
    out = set()
    for e in (kayit.get("esleme") or {}).values():
        try:
            out.add(int(e.get("id")))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def mikro_idleri_tum(d=None):
    """Bütün haftaların Mikro'dan gelen ödeme satırları — Ertelenen ödemeler birden çok haftayı listeler
    (eskiden orada mikro_idler verilmiyordu: Mikro satırında Öde / Düzenle / Sil açıktı, 22.10.2026)."""
    d = d if d is not None else durum()
    out = set()
    for hid in (d.get("haftalar") or {}):
        out |= mikro_idleri(hid, d)
    return out


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranacc.database import get_client
    return get_client()


def _bugun():
    from shared.utils import tr_today
    return tr_today()


def son_aktarim():
    r = (_cli().table("mikro_senk_durum").select("son_cekim").eq("tablo", "mikro_cari_hareket").execute().data or [])
    return str((r[0] if r else {}).get("son_cekim") or "")


def _taze_mi(son, simdi=None):
    try:
        t = datetime.fromisoformat(str(son).replace("Z", "+00:00").replace(" ", "T"))
    except (TypeError, ValueError):
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return ((simdi or datetime.now(timezone.utc)) - t).total_seconds() < TAZE_SAAT * 3600


def veri_oku():
    """mikro_odeme.veri_oku + muhasebe bakiyeleri (335, 360, 361)."""
    from kayranacc.mikro_yil_sonu import oku as _ys_oku
    veri = O.veri_oku()
    # Yıl sonu kapanış / açılış ayıklanmış: Aralık SGK ve muhtasarı kapanış yapılınca sıfırlanmasın (Ocak'ta ödenir)
    veri["muhasebe"], _turlu = _ys_oku(_cli(), ("335", "360", "361"))
    return veri


def _hafta_odemeleri(hafta_id):
    from satis.mikro_esitle import sayfali_oku
    cli = _cli()
    return sayfali_oku(lambda: cli.table("odemeler").select("*").eq("hafta_id", int(hafta_id)).order("id"), "id")


def firma_gunleri(d, veri):
    """Öğrenilen firma vadeleri + elle düzeltmeler (elle olan kazanır). Öğrenme pazartesi bir kez yapılır."""
    from satis.mikro_esitle import sayfali_oku
    cli = _cli()
    gecmis = sayfali_oku(lambda: cli.table("odemeler").select("id,hafta_id,firma,vade,tutar_tl,tutar_usd")
                         .order("id"), "id")
    mikro_idler = {int(k) for k in (d.get("haftalar") or {})}
    gun = O.vade_gunleri_ogren(O.fatura_kalemleri(veri["hareket"], veri["cari_kart"]),
                               gecmis_satirlari(gecmis, mikro_idler))
    gun.update({k: int(v) for k, v in (d.get("vade_elle") or {}).items()})
    return gun


def hafta_ac(bugun=None, d=None):
    """Bu haftanın Mikro listesi henüz açılmadıysa açar. Döner: sonuç metni / None (gerek yok ya da yazılmadı)."""
    from kayranacc.database import get_aktif_hafta, get_client, hafta_olustur
    from kayranacc.excel_islemler import ayni_hafta
    bugun = bugun or _bugun()
    d = durum() if d is None else d
    bas = pazartesi(bugun)
    if d.get("son_pazartesi") == bas.isoformat():
        return None
    ad = O.hafta_adi(bas)
    haftalar = get_client().table("haftalar").select("id,hafta_adi,aktif").execute().data or []
    if ayni_hafta(ad, haftalar):
        d["son_pazartesi"] = bas.isoformat()
        _kaydet(d)
        return f"'{ad}' elle yüklenmiş; Mikro haftası açılmadı"
    if not _taze_mi(son_aktarim()):
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_odeme_oto.hafta_ac",
               RuntimeError(f"Mikro cari verisi {TAZE_SAAT} saatten eski; '{ad}' açılmadı (aktarıcı çalışıyor mu?)"))
        return None
    veri = veri_oku()
    gunler = firma_gunleri(d, veri)
    satir, uyari = liste_satirlari(veri, bas, bugun, gunler)
    satir = [r for r in satir if _yuvarla(r.get("tl")) or _yuvarla(r.get("usd"))]
    onceki_hafta = get_aktif_hafta()
    onceki, onceki_idler = [], set()
    if onceki_hafta:
        onceki = _hafta_odemeleri(onceki_hafta["id"])
        onceki_idler = {e.get("id") for e in
                        ((d.get("haftalar") or {}).get(str(onceki_hafta["id"])) or {}).get("esleme", {}).values()}
    tasinan = tasinacaklar(onceki, onceki_idler, satir)
    idler = []
    hafta_id = hafta_olustur(ad, satir + tasinan, idler)
    if hafta_id is None:
        return None
    esleme = {r["anahtar"]: dict(_iz(r), id=i) for r, i in zip(satir, idler[:len(satir)])}
    d.setdefault("haftalar", {})[str(hafta_id)] = {"pazartesi": bas.isoformat(), "gunler": gunler,
                                                   "esleme": esleme, "acilis": str(bugun)}
    d["son_pazartesi"] = bas.isoformat()
    d["son_calisma"] = son_aktarim()
    if uyari:
        d["son_uyarilar"] = uyari[:20]
    _kaydet(d)
    try:
        from shared.yukleme_takvimi import kaydet as _yt
        _yt("odeme_listesi", "Mikro", len(satir) + len(tasinan))
        from shared.yukleme_gecmisi import kaydet as _yg
        _yg("odeme_listesi", len(satir) + len(tasinan), "Mikro (otomatik)")
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_odeme_oto.hafta_ac.takvim", e, "debug")
    return f"'{ad}' açıldı: Mikro'dan {len(satir)}, önceki haftadan {len(tasinan)} satır"


def hafta_yenile(bugun=None, d=None):
    """Aktif hafta Mikro'dan açıldıysa Mikro'daki son duruma getirir. Döner: sonuç metni / None (değişiklik yok)."""
    from kayranacc.database import (get_aktif_hafta, odeme_ekle_bulk, odeme_mikro_guncelle, odeme_mikro_kapandi,
                                    odeme_sil)
    bugun = bugun or _bugun()
    d = durum() if d is None else d
    hafta = get_aktif_hafta()
    kayit = ((d.get("haftalar") or {}).get(str((hafta or {}).get("id"))) if hafta else None)
    if not kayit:
        return None
    bas = date.fromisoformat(kayit["pazartesi"])
    satir, _uyari = liste_satirlari(veri_oku(), bas, bugun, kayit.get("gunler") or {})
    satir = [r for r in satir if _yuvarla(r.get("tl")) or _yuvarla(r.get("usd"))]
    mevcut = {r.get("id"): r for r in _hafta_odemeleri(hafta["id"])}
    esleme = kayit.setdefault("esleme", {})
    plan = guncelleme_plani(esleme, mevcut, satir)
    if plan["ekle"]:
        idler = odeme_ekle_bulk(hafta["id"], plan["ekle"]) or []
        for r, i in zip(plan["ekle"], idler):
            esleme[r["anahtar"]] = dict(_iz(r), id=i)
    for _k, oid in plan["kapandi"]:
        odeme_mikro_kapandi(oid, bugun.isoformat(), KAPANDI_NOTU)
    for _k, oid in plan["sil"]:
        odeme_sil(oid)
    for k, oid, alanlar, iz in plan["guncelle"]:
        odeme_mikro_guncelle(oid, alanlar)
        esleme[k] = dict(iz, id=oid)
    _kaydet(d)
    n = {a: len(plan[a]) for a in ("ekle", "kapandi", "sil", "guncelle")}
    if not any(n.values()):
        return None
    return (f"yeni {n['ekle']}, Mikro'da kapanan {n['kapandi']}, tutarı değişen {n['guncelle']}, "
            f"gerçeği gelen tahmin {n['sil']}")


def otomatik():
    """Eşitleme turu: pazartesi haftayı açar; hafta içinde aktarıcı yeni cari verisi getirdiyse yeniler.
    Hata fırlatmaz."""
    try:
        if not acik_mi():
            return None
        from satis.mikro_esitle import aktarim_suruyor
        if aktarim_suruyor():
            return None
        d = durum()
        acilan = hafta_ac(d=d)
        if acilan:
            return acilan
        son = son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        sonuc = hafta_yenile(d=d)
        d["son_calisma"] = son
        _kaydet(d)
        return sonuc
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranacc.mikro_odeme_oto.otomatik", e)
        return None


def elle_yenile(kullanici=""):
    """Bu Hafta'daki "Mikro'dan yenile" düğmesi: tur kilidiyle (arka plan turuyla aynı anda iki kez eklenmesin).
    Döner: (tamam mı, mesaj)."""
    from shared.mikro_kilit import tur_kilidi
    with tur_kilidi(f"odeme-elle-{kullanici}") as alindi:
        if not alindi:
            return False, "Şu an bir Mikro eşitleme turu çalışıyor; bir dakika sonra yeniden dene."
        d = durum()
        sonuc = hafta_ac(d=d) or hafta_yenile(d=d)
    return True, sonuc or "Liste Mikro'yla aynı; değişiklik yok."


def firma_vadeleri_kaydet(degisen):
    """{cari_kod: gün | None} — None elle düzeltmeyi kaldırır (öğrenilen gün kullanılır). Sonraki pazartesiden geçerli."""
    d = durum()
    elle = d.setdefault("vade_elle", {})
    for k, v in (degisen or {}).items():
        if v is None:
            elle.pop(k, None)
        else:
            elle[k] = max(0, int(v))
    _kaydet(d)

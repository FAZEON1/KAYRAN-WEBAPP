# -*- coding: utf-8 -*-
"""Mikro → yurt içi alışlar (Ekim 2026). Ekran yok; Geçmiş kayıtlar paçalda ve stok kartının alımlarında görünür.

Kullanıcı (22.10.2026): "Mikro'ya giren yurt içi alımlar artık programa direkt yansısın. Unutma Mikro'daki
veriler baz alınsın, oradaki datalar hep doğrudur." (Yurt içi alış sayfası aynı gün kaldırıldı.)

Kaynak: aktarıcının mikro_alim_satir tablosu (STOK_HAREKETLERI giriş satırları, cari kodlu, 2025'ten beri).
Yurt içi alış = 320 (satıcılar) hesabından, 320.50 (yurt dışı tedarikçiler, ithalat) DIŞINDAKİ cariden normal
(iade olmayan), tutarlı giriş; ithalat dosyasına bağlı satır (sth_exim_kodu / sth_bagli_ithalat_kodu) sayılmaz.

  Belge      bir Mikro faturası (sth_fat_uid; boşsa evrak seri + sıra) = bir yurt içi alış kaydı
             (ithalat_dosyalari, alim_turu 'yurtici', mikro_kodu 'YI:<fatura>'). Durum Teslim Alındı, stok
             yazılmaz (stok_islendi: stok Mikro'dan gelir).
  Birim      (tutar − iskonto) ÷ adet ÷ Mikro'nun satırdaki dolar kuru (sth_alt_doviz_kuru) → USD; satır masrafı
             (sth_masraf) belgenin "diğer" masrafına.
  Değer farkı (sth_cins 9: fiyat farkı faturası, miktar 1 sembolik) adet eklemez: tutarı aynı ürünün o tarihe
             kadarki SON alımının kalemine eklenir (paçal adet-ağırlıklı olduğu için Mikro'nun maliyetiyle aynı
             etki). Önceki alımı yoksa ilk alımına.
  Elle girilmiş eski yurt içi kayıtlar (mikro_kodu boş, 2025 ve sonrası) Mikro'daki asıllarıyla değiştirilir;
  Mikro'da artık olmayan 'YI:' kaydı silinir. Silinen / değişen her satır önce mikro_esitleme_arsiv'e.
Yerli üretim (alim_turu 'yerli') dokunulmaz.
"""
from collections import defaultdict

DURUM_ANAHTAR = "mikro_yurtici_durum"
ONEK = "YI:"
SATICI = "320."
YURTDISI = "320.50"
DEGER_FARKI = 9
BOS_UID = "00000000-0000-0000-0000-000000000000"
BASLANGIC = "2025-01-01"
TESLIM = "Teslim Alındı"
KURUS = 0.005


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


def yurtici_satiri_mi(r):
    """Yurt içi satıcıdan normal alış satırı mı (ithalat ve iade değil, tutarlı)."""
    cari = _s(r.get("sth_cari_kodu"))
    return (cari.startswith(SATICI) and not cari.startswith(YURTDISI)
            and _i(r.get("sth_tip"), -1) == 0 and _i(r.get("sth_normal_iade")) == 0
            and not _s(r.get("sth_exim_kodu")) and not _s(r.get("sth_bagli_ithalat_kodu"))
            and _f(r.get("sth_tutar")) > 0 and _f(r.get("sth_miktar")) > 0
            and _s(r.get("sth_tarih"))[:10] >= BASLANGIC)


def _belge(r):
    uid = _s(r.get("sth_fat_uid")).lower()
    if uid and uid != BOS_UID:
        return uid
    return f"{_s(r.get('sth_evrakno_seri'))}-{_i(r.get('sth_evrakno_sira'))}-{_s(r.get('sth_tarih'))[:10]}"


def _usd(r, alan="sth_tutar"):
    kur = _f(r.get("sth_alt_doviz_kuru")) or _f(r.get("sth_har_doviz_kuru"))
    return _f(r.get(alan)) / kur if kur > 0 else 0.0


def mikro_alimlari(satirlar, kart_bul, unvan=None, depo_adi=None):
    """Mikro satırları → [{"dosya": {...}, "kalemler": [{sku, adet, birim_fob}]}] (belge tarihine göre).
    kart_bul(mikro stok kodu) → uygulamadaki kart SKU'su (yoksa Mikro kodu). unvan: {cari kodu: ad};
    depo_adi: {depo no: ad}."""
    unvan, depo_adi = unvan or {}, depo_adi or {}
    gercek, fark = [], []
    for r in satirlar or []:
        if not yurtici_satiri_mi(r):
            continue
        (fark if _i(r.get("sth_cins")) == DEGER_FARKI else gercek).append(r)
    belgeler = defaultdict(list)
    for r in gercek:
        belgeler[_belge(r)].append(r)
    alimlar = {}
    for b, rs in belgeler.items():
        rs = sorted(rs, key=lambda r: (_s(r.get("sth_tarih")), _s(r.get("sth_stok_kod"))))
        ilk = rs[0]
        kalem, masraf = {}, 0.0
        for r in rs:
            sku = kart_bul(_s(r.get("sth_stok_kod")))
            k = kalem.setdefault(sku, {"adet": 0.0, "tutar": 0.0})
            k["adet"] += _f(r.get("sth_miktar"))
            k["tutar"] += _usd(r) - _usd(r, "sth_iskonto")
            masraf += _usd(r, "sth_masraf")
        kur = _f(ilk.get("sth_alt_doviz_kuru")) or _f(ilk.get("sth_har_doviz_kuru")) or 1.0
        seri, sira = _s(ilk.get("sth_evrakno_seri")), _i(ilk.get("sth_evrakno_sira"))
        tarih = _s(ilk.get("sth_tarih"))[:10]
        cari = _s(ilk.get("sth_cari_kodu"))
        alimlar[b] = {"tarih": tarih, "kalem": kalem, "masraf": masraf, "kur": kur,
                      "doviz": "USD" if _i(ilk.get("sth_har_doviz_cinsi")) == 1 else "TL",
                      "no": f"{seri}-{sira}" if seri else f"MKR-{sira}", "cari": cari,
                      "depo": depo_adi.get(_i(ilk.get("sth_giris_depo_no")), "")}
    # Değer farkı: aynı ürünün o tarihe kadarki son alımına (yoksa ilk alımına)
    for r in sorted(fark, key=lambda r: _s(r.get("sth_tarih"))):
        sku, g = kart_bul(_s(r.get("sth_stok_kod"))), _s(r.get("sth_tarih"))[:10]
        aday = sorted((a["tarih"], b) for b, a in alimlar.items() if sku in a["kalem"])
        if not aday:
            continue
        once = [x for x in aday if x[0] <= g]
        hedef = (once[-1] if once else aday[0])[1]
        alimlar[hedef]["kalem"][sku]["tutar"] += _usd(r) - _usd(r, "sth_iskonto")
    out = []
    for b, a in sorted(alimlar.items(), key=lambda x: (x[1]["tarih"], x[0])):
        out.append({"dosya": {
            "dosya_no": a["no"], "pi_no": "", "tarih": a["tarih"], "tedarikci": unvan.get(a["cari"]) or a["cari"],
            "doviz": a["doviz"], "kur": round(a["kur"], 4),
            "masraflar": {"diger": round(a["masraf"], 4)} if a["masraf"] >= KURUS else {},
            "notlar": f"Mikro'dan ({a['no']})", "durum": TESLIM, "teslim_tarihi": a["tarih"],
            "teslim_deposu": a["depo"] or None, "stok_islendi": True, "alim_turu": "yurtici",
            "mikro_kodu": ONEK + b},
            "kalemler": [{"sku": s, "adet": round(k["adet"], 2),
                          "birim_fob": round(k["tutar"] / k["adet"], 4) if k["adet"] else 0.0}
                         for s, k in sorted(a["kalem"].items())]})
    return out


def _kalem_imzasi(kalemler):
    return sorted((_s(k.get("sku")), round(_f(k.get("adet")), 2), round(_f(k.get("birim_fob")), 4))
                  for k in kalemler or [])


def _masraf(d):
    m = d.get("masraflar") or {}
    if isinstance(m, str):
        import json
        try:
            m = json.loads(m)
        except ValueError:
            m = {}
    return {k: round(_f(v), 4) for k, v in m.items() if abs(_f(v)) >= KURUS}


DEGISEN_ALANLAR = ("dosya_no", "tarih", "tedarikci", "doviz", "teslim_tarihi", "teslim_deposu")


def plan_yap(mikro, dosyalar, kalemler_map):
    """mikro: mikro_alimlari() · dosyalar: uygulamadaki yurt içi alış kayıtları (alim_turu 'yurtici') ·
    kalemler_map: {dosya id: [kalem]}. Döner: {ekle: [...], guncelle: [{id, dosya, kalemler, kalem_degisti}],
    sil: [{id, dosya_no, neden}]}."""
    var = {_s(d.get("mikro_kodu")): d for d in dosyalar if _s(d.get("mikro_kodu")).startswith(ONEK)}
    ekle, guncelle = [], []
    for m in mikro:
        d = var.pop(m["dosya"]["mikro_kodu"], None)
        if d is None:
            ekle.append(m)
            continue
        yeni = {k: m["dosya"][k] for k in DEGISEN_ALANLAR if _s(d.get(k))[:10 if "tarih" in k else None]
                != _s(m["dosya"][k])}
        if abs(_f(d.get("kur")) - _f(m["dosya"]["kur"])) >= 0.0001:
            yeni["kur"] = m["dosya"]["kur"]
        if _masraf(d) != m["dosya"]["masraflar"]:
            yeni["masraflar"] = m["dosya"]["masraflar"]
        kalem_degisti = _kalem_imzasi(kalemler_map.get(d.get("id"))) != _kalem_imzasi(m["kalemler"])
        if yeni or kalem_degisti:
            guncelle.append({"id": d.get("id"), "dosya": yeni, "kalemler": m["kalemler"],
                             "kalem_degisti": kalem_degisti, "dosya_no": m["dosya"]["dosya_no"]})
    sil = [{"id": d.get("id"), "dosya_no": d.get("dosya_no"), "neden": "Mikro'da yok"} for d in var.values()]
    if mikro:
        # Elle girilmiş yurt içi kayıtlar: Mikro esas, asıllarıyla değiştirilir
        sil += [{"id": d.get("id"), "dosya_no": d.get("dosya_no"), "neden": "elle girilmiş; Mikro'daki asıl yazıldı"}
                for d in dosyalar if not _s(d.get("mikro_kodu"))
                and _s(d.get("alim_turu")) == "yurtici" and _s(d.get("tarih"))[:10] >= BASLANGIC]
    return {"ekle": ekle, "guncelle": guncelle, "sil": sil}


def plan_ozeti(plan):
    return {"yeni": len(plan["ekle"]), "guncellenen": len(plan["guncelle"]), "silinen": len(plan["sil"])}


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from satis.database import _get_client
    return _get_client()


def veri_oku():
    from ithalat.mikro_ithalat import _sayfali
    from shared.utils import sku_anahtar
    cli = _cli()
    satir = [r for r in _sayfali("mikro_alim_satir", "*", "sth_guid") if yurtici_satiri_mi(r)]
    kartlar = {}
    for u in _sayfali("urunler", "sku", "sku"):
        kartlar.setdefault(sku_anahtar(u.get("sku")), u.get("sku"))
    unvan = {}
    for c in cli.table("mikro_cari_kart").select("cari_kod,cari_unvan1").like("cari_kod", "320.%").execute().data or []:
        unvan[_s(c.get("cari_kod"))] = " ".join(_s(c.get("cari_unvan1")).split())
    from kayranpm.database import depo_kanonik
    depo = {_i(d.get("dep_no")): depo_kanonik(d.get("dep_adi") or "")
            for d in cli.table("mikro_depo_kart").select("dep_no,dep_adi").execute().data or []}
    mikro = mikro_alimlari(satir, lambda k: kartlar.get(sku_anahtar(k)) or k, unvan, depo)
    dosyalar = [d for d in _sayfali("ithalat_dosyalari", "*", "id") if _s(d.get("alim_turu")) == "yurtici"]
    ids = [d.get("id") for d in dosyalar]
    kal = defaultdict(list)
    for i in range(0, len(ids), 100):
        for k in (cli.table("ithalat_kalemleri").select("id,dosya_id,sku,adet,birim_fob")
                  .in_("dosya_id", ids[i:i + 100]).execute().data or []):
            kal[k.get("dosya_id")].append(k)
    return mikro, dosyalar, dict(kal)


def plan_hazirla():
    return plan_yap(*veri_oku())


def _arsivle(cli, dosya_id, neden):
    import json
    d = (cli.table("ithalat_dosyalari").select("*").eq("id", dosya_id).execute().data or [None])[0]
    if not d:
        return
    d["kalemler"] = cli.table("ithalat_kalemleri").select("*").eq("dosya_id", dosya_id).execute().data or []
    cli.table("mikro_esitleme_arsiv").insert({"tablo": "ithalat_dosyalari", "neden": neden,
                                              "satir": json.loads(json.dumps(d, default=str))}).execute()


def uygula(plan):
    """Döner: {yeni, guncellenen, silinen, hata}."""
    from shared.ana_veri import get_urun_ad_haritasi
    from shared.cop_kutusu import cop_kutusu_kapali
    cli = _cli()
    try:
        adlar = get_urun_ad_haritasi() or {}
    except Exception:  # noqa: BLE001
        adlar = {}
    sonuc = {"yeni": 0, "guncellenen": 0, "silinen": 0, "hata": []}

    def _kalem_yaz(did, kalemler):
        if kalemler:
            cli.table("ithalat_kalemleri").insert([dict(k, dosya_id=did, urun_adi=adlar.get(k["sku"], ""))
                                                   for k in kalemler]).execute()
    with cop_kutusu_kapali():            # arşiv mikro_esitleme_arsiv'de; çöp kutusu her turda dolmasın
        for s in plan["sil"]:
            try:
                _arsivle(cli, s["id"], f"mikro_yurtici: {s['neden']}")
                cli.table("ithalat_kalemleri").delete().eq("dosya_id", s["id"]).execute()
                cli.table("ithalat_dosyalari").delete().eq("id", s["id"]).execute()
                sonuc["silinen"] += 1
            except Exception as e:  # noqa: BLE001
                sonuc["hata"].append(f"{s['dosya_no']}: {type(e).__name__}: {str(e)[:120]}")
        for g in plan["guncelle"]:
            try:
                _arsivle(cli, g["id"], "mikro_yurtici: güncellendi")
                if g["dosya"]:
                    cli.table("ithalat_dosyalari").update(g["dosya"]).eq("id", g["id"]).execute()
                if g["kalem_degisti"]:
                    cli.table("ithalat_kalemleri").delete().eq("dosya_id", g["id"]).execute()
                    _kalem_yaz(g["id"], g["kalemler"])
                sonuc["guncellenen"] += 1
            except Exception as e:  # noqa: BLE001
                sonuc["hata"].append(f"{g['dosya_no']}: {type(e).__name__}: {str(e)[:120]}")
    for y in plan["ekle"]:
        try:
            if cli.table("ithalat_dosyalari").select("id").eq("mikro_kodu", y["dosya"]["mikro_kodu"]).execute().data:
                continue                                    # ikinci kez eklenmesin
            r = cli.table("ithalat_dosyalari").insert({k: v for k, v in y["dosya"].items() if v is not None}).execute()
            yid = (r.data or [{}])[0].get("id")
            if yid is not None:
                _kalem_yaz(yid, y["kalemler"])
            sonuc["yeni"] += 1
        except Exception as e:  # noqa: BLE001
            sonuc["hata"].append(f"{y['dosya']['dosya_no']}: {type(e).__name__}: {str(e)[:120]}")
    from ithalat.mikro_ithalat import _onbellek_temizle
    _onbellek_temizle()
    return sonuc


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    """Varsayılan AÇIK (kullanıcı: "Mikro'ya giren yurt içi alımlar direkt yansısın"); {"acik": false} kapatır."""
    return durum().get("acik", True) is not False


def son_aktarim():
    r = (_cli().table("mikro_senk_durum").select("son_cekim").eq("tablo", "mikro_alim_satir").execute().data or [])
    return str((r[0] if r else {}).get("son_cekim") or "")


def otomatik():
    """Eşitleme turu (otonom/mikro_esitle.ISLER). Yazdıysa metin, yoksa None. Hata fırlatmaz."""
    try:
        if not acik_mi():
            return None
        d = durum()
        son = son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        plan = plan_hazirla()
        oz = plan_ozeti(plan)
        sonuc = uygula(plan) if any(oz.values()) else {"hata": []}
        from kayranacc.database import set_ayar
        d = durum()
        d.update(son_calisma=son, son_ozet=oz, son_hata=sonuc.get("hata")[:10])
        set_ayar(DURUM_ANAHTAR, d)
        if any(oz.values()):
            return f"yurt içi alış: {oz['yeni']} yeni, {oz['guncellenen']} güncellendi, {oz['silinen']} silindi"
        return None
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_yurtici.otomatik", e)
        return None

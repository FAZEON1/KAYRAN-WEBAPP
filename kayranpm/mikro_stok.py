# -*- coding: utf-8 -*-
"""Mikro → depo stoğu (Ekim 2026, Mikro adım 2).

Kullanıcı: "Olabildiğince az dosya upload; her şey Mikro'dan, tam otomatik." G5F depo stok sayımı Excel'i
(Dosya kapısı → kayranpm.excel_islemler.excel_yukle_g5f_depolar) yerine aktarıcının mikro_stok_miktar
tablosu (Mikro'da her ürünün depo depo miktarı, 15 dakikada bir tam çekilir) aynı yoldan yazılır:
SKU ortak kurala göre (normalize_sku → shared.utils.sku_anahtar; "Fazeon X24F240P" = X24F240P), depo adı
depo_kanonik ile (SERVİS DEPO → TEKNİK DEPO, OUTLET → OUTLET DEPO …), yazım tek işlemde
(g5f_stok_aktar: ürünler + Mikro'da olmayanların sıfırlanması + stok defteri). "bizim stok" = Merkez +
Happy Life, sayımla aynı.

21.10.2026 karşılaştırması: depo toplamları Merkez 17.265 ↔ 17.270, Happy Life 14.225 ↔ 14.225; ürün
bazında yaklaşık 10 küçük adet farkı (ör. FAZE3 6.287 ↔ 6.284). Yazım yalnız fark varsa yapılır.
İlk açılışta "şimdi ↔ Mikro" karşılaştırması ve onay (Ürün Yönetimi › Tüm Ürünler), sonra otomatik.
Onaydan sonra uygulamadaki stok hareketleri (mal kabul, sevk) kayıt olarak kalır; miktar her turda Mikro'dan
yazılır. Durum sistem_ayarlari'nda (DURUM_ANAHTAR).
"""
from collections import defaultdict

DURUM_ANAHTAR = "mikro_stok_durum"
KAYNAK = "kayranpm/mikro_stok.py:uygula"


def _i(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _s(v):
    return str(v or "").strip()


# ── Saf ────────────────────────────────────────────────────────────
def kirilim_yap(satirlar, depo_adlari):
    """mikro_stok_miktar → ({sku_norm: {depo: miktar}}, {sku_norm: ad}). Sıfır miktar yazılmaz; hiç
    miktarı kalmayan ürün listede olmaz (sayımdaki gibi sıfırlanır)."""
    from kayranpm.database import depo_kanonik
    from kayranpm.excel_islemler import normalize_sku
    kir = defaultdict(lambda: defaultdict(int))
    adlar = {}
    for r in satirlar:
        sku = normalize_sku(r.get("sto_kod"))
        mik = _i(r.get("miktar"))
        if not sku or not mik:
            continue
        depo = depo_kanonik(_s(depo_adlari.get(_i(r.get("depo"), -1))) or f"DEPO {_i(r.get('depo'))}")
        kir[sku][depo] += mik
        adlar.setdefault(sku, _s(r.get("sto_isim")))
    out = {}
    for sku, dd in kir.items():
        dd = {d: m for d, m in dd.items() if m}
        if dd:
            out[sku] = dd
    return out, {k: v for k, v in adlar.items() if k in out}


def farklar(kirilim, urunler):
    """[(sku, eski kırılım, yeni kırılım)] — yalnız değişenler. urunler: [{sku, depo_kirilim}]."""
    from kayranpm.excel_islemler import normalize_sku
    mevcut = {}
    for u in urunler:
        g = _s(u.get("sku"))
        if g:
            dk = u.get("depo_kirilim") or {}
            mevcut[normalize_sku(g)] = (g, {d: _i(m) for d, m in dk.items() if _i(m)} if isinstance(dk, dict) else {})
    out = []
    for k in sorted(set(kirilim) | {k for k, (_, dk) in mevcut.items() if dk}):
        g, eski = mevcut.get(k, (k, {}))
        yeni = kirilim.get(k, {})
        if eski != yeni:
            out.append((g, eski, yeni))
    return out


def depo_ozeti(kirilimlar):
    """{depo: toplam} — kirilimlar: kırılım sözlükleri listesi."""
    t = defaultdict(int)
    for dd in kirilimlar:
        for d, m in (dd or {}).items():
            t[d] += _i(m)
    return dict(sorted(t.items()))


# ── Veritabanı ─────────────────────────────────────────────────────
def _cli():
    from kayranpm.database import get_client
    return get_client()


def plan_hazirla():
    cli = _cli()
    from satis.mikro_esitle import kopyasiz
    satir = kopyasiz(cli.table("mikro_stok_miktar").select("sto_kod,sto_isim,depo,miktar").order("sto_kod")
                     .order("depo").execute().data or [], ("sto_kod", "depo"))
    depo = {_i(d.get("dep_no")): _s(d.get("dep_adi")) for d in
            (cli.table("mikro_depo_kart").select("dep_no,dep_adi").execute().data or [])}
    urunler = cli.table("urunler").select("sku,depo_kirilim").execute().data or []
    kir, adlar = kirilim_yap(satir, depo)
    return {"kirilim": kir, "adlar": adlar, "fark": farklar(kir, urunler), "bos": not satir,
            "once": depo_ozeti(u.get("depo_kirilim") for u in urunler), "sonra": depo_ozeti(kir.values())}


def uygula(plan, kayit=None):
    """Fark varsa Mikro kırılımını sayım yoluyla yazar (tek işlem). Mikro verisi boşsa yazmaz (boş bir sayım
    bütün depo stoğunu sıfırlardı). kayit: shared.yukleme_gecmisi.Kayit (onay anında; geri alınabilsin).
    Döner: değişen ürün sayısı ya da hata metni."""
    if plan["bos"] or not plan["kirilim"] or not plan["fark"]:
        return 0
    from kayranpm.excel_islemler import _g5f_tek_islem, normalize_sku
    mevcut = {normalize_sku(_s(u.get("sku"))): _s(u.get("sku"))
              for u in (_cli().table("urunler").select("sku").execute().data or []) if _s(u.get("sku"))}
    if kayit is not None:
        with kayit.stok():
            sonuc = _g5f_tek_islem(plan["kirilim"], plan["adlar"], mevcut)
    else:
        sonuc = _g5f_tek_islem(plan["kirilim"], plan["adlar"], mevcut)
    if isinstance(sonuc, str):
        return sonuc
    if sonuc is None:
        return "Tek işlem fonksiyonu (g5f_stok_aktar) kurulu değil; yazılmadı."
    return len(plan["fark"])


def durum():
    try:
        from kayranacc.database import get_ayar
        return get_ayar(DURUM_ANAHTAR, {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def acik_mi():
    return bool(durum().get("acik"))


def ac(kullanici):
    from kayranacc.database import set_ayar
    from shared.utils import tr_now
    d = durum()
    d.update(acik=True, acan=str(kullanici or ""), acilis=str(tr_now()))
    set_ayar(DURUM_ANAHTAR, d)


def son_aktarim():
    r = (_cli().table("mikro_senk_durum").select("son_cekim").eq("tablo", "mikro_stok_miktar").execute().data
         or [])
    return str((r[0] if r else {}).get("son_cekim") or "")


def otomatik():
    """Açıksa ve aktarıcı yeni stok verisi getirdiyse farkları yazar. Hata fırlatmaz."""
    try:
        from kayranacc.database import set_ayar
        d = durum()
        if not d.get("acik"):
            return None
        son = son_aktarim()
        if not son or (d.get("son_calisma") and str(d.get("son_calisma")) >= son):
            return None
        from satis.mikro_esitle import aktarim_suruyor
        if aktarim_suruyor():
            return None                   # aktarıcı yazıyor (stok tablosu tam çekimde silinip yazılır)
        sonuc = uygula(plan_hazirla())
        if isinstance(sonuc, str):
            from shared.kayit import sessiz
            sessiz("kayranpm.mikro_stok.otomatik", RuntimeError(sonuc))
            return None
        d["son_calisma"] = son
        set_ayar(DURUM_ANAHTAR, d)
        return sonuc
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("kayranpm.mikro_stok.otomatik", e)
        return None

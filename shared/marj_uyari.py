# -*- coding: utf-8 -*-
"""KAYRAN — Zararına satış uyarısı (Telegram).

Yeni sipariş kaydedildiğinde kâr marjı eşiğin altında kalan kalemler için
TEK bir Telegram mesajı gönderir.

═══ TASARIM KARARLARI ══════════════════════════════════════════════════
1) SİPARİŞ BAŞINA TEK MESAJ.
   Kalem başına mesaj atılsaydı 40 kalemlik bir Excel yüklemesi 40 bildirim
   üretirdi ve kimse okumazdı. Tüm sorunlu kalemler tek mesajda listelenir.

2) KAYIT AKIŞINI ASLA BOZMAZ.
   Bütün fonksiyon try/except içindedir ve hiçbir şey fırlatmaz. Telegram
   çalışmazsa sipariş yine kaydedilir.

3) MALİYETİ 0 OLAN KALEM UYARI ÜRETMEZ — AMA AYRICA BİLDİRİLİR.
   Ürün kartı eksikse birim_maliyet 0 gelir ve marj %100 görünür. Bu
   "kârlı" değil, "maliyeti bilinmiyor" demektir. Zararına satış kadar
   önemli olduğu için mesajın altında ayrı bir satırda uyarılır.

4) EŞİK YAPILANDIRILABİLİR.
   Varsayılan: net kâr < 0 (zararına satış). Secrets'tan düşük marj
   eşiği de verilebilir:

       [telegram]
       marj_esik_yuzde = 5      # marjı %5'in altında olanlar da uyarı üretir
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _i(v):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def _esik_yuzde():
    """Uyarı eşiği (%). Varsayılan 0 → yalnız zararına satışlar."""
    try:
        import streamlit as st
        return float(st.secrets.get("telegram", {}).get("marj_esik_yuzde", 0) or 0)
    except Exception:
        return 0.0


def kalem_metrik(k):
    """Tek kalem için kâr metrikleri — satis.database.satir_kar ile aynı formül."""
    adet = _i(k.get("adet"))
    ciro = adet * _f(k.get("birim_satis"))
    maliyet = adet * _f(k.get("birim_maliyet"))
    destek = adet * (_f(k.get("birim_firma_destek")) + _f(k.get("birim_ek_destek")))
    net_satis = ciro - destek
    net_kar = net_satis - maliyet
    marj = (net_kar / net_satis * 100) if net_satis > 0 else 0.0
    return {"adet": adet, "ciro": ciro, "maliyet": maliyet,
            "net_satis": net_satis, "net_kar": net_kar, "marj": marj}


def sorunlu_kalemler(kalemler, esik=None):
    """Eşiğin altında kalan kalemleri ayırır.

    Döner: (zararli, maliyetsiz)
      zararli    — net kârı eşiğin altında olanlar
      maliyetsiz — birim_maliyet'i 0 olanlar (maliyet bilinmiyor)
    """
    esik = _esik_yuzde() if esik is None else float(esik)
    zararli, maliyetsiz = [], []
    for k in (kalemler or []):
        if _i(k.get("adet")) <= 0:
            continue
        m = kalem_metrik(k)
        if _f(k.get("birim_maliyet")) <= 0:
            maliyetsiz.append({**k, **m})
            continue                      # maliyet bilinmiyor → marj anlamsız
        if m["net_kar"] < 0 or (esik > 0 and m["marj"] < esik):
            zararli.append({**k, **m})
    return zararli, maliyetsiz


def mesaj_uret(zararli, maliyetsiz, kanal="", siparis_no="", tarih="",
               kullanici="", kaynak=""):
    """Telegram mesajını (HTML) üretir."""
    from shared.telegram_gonder import kacis as _k

    sat = ["🔴 <b>ZARARINA SATIŞ UYARISI</b>", ""]
    if kanal:
        sat.append(f"🏢 <b>Cari:</b> {_k(kanal)}")
    if siparis_no:
        sat.append(f"🧾 <b>Sipariş No:</b> {_k(siparis_no)}")
    if tarih:
        sat.append(f"📅 <b>Tarih:</b> {_k(str(tarih)[:10])}")
    if kullanici:
        sat.append(f"👤 <b>Giren:</b> {_k(kullanici)}")
    if kaynak:
        sat.append(f"⚙️ <b>Kaynak:</b> {_k(kaynak)}")

    if zararli:
        _top = sum(x["net_kar"] for x in zararli)
        sat += ["", f"<b>Eşiğin altındaki {len(zararli)} kalem:</b>"]
        for x in zararli[:12]:
            sat.append(
                f"• <code>{_k(x.get('sku'))}</code> × {x['adet']}  "
                f"alış {x['maliyet'] / max(x['adet'], 1):,.2f} → "
                f"satış {_f(x.get('birim_satis')):,.2f}  "
                f"<b>{x['net_kar']:+,.2f}$</b> (%{x['marj']:.1f})")
        if len(zararli) > 12:
            sat.append(f"  <i>… ve {len(zararli) - 12} kalem daha</i>")
        sat += ["", f"💸 <b>Toplam etki: {_top:+,.2f}$</b>"]

    if maliyetsiz:
        sat += ["", f"⚠️ <b>Maliyeti bilinmeyen {len(maliyetsiz)} kalem</b> "
                    f"(ürün kartı eksik — kâr olduğundan yüksek görünür):"]
        for x in maliyetsiz[:8]:
            sat.append(f"• <code>{_k(x.get('sku'))}</code> × {x['adet']}")
        if len(maliyetsiz) > 8:
            sat.append(f"  <i>… ve {len(maliyetsiz) - 8} kalem daha</i>")

    return "\n".join(sat)


def marj_uyarisi(kalemler, kanal="", siparis_no="", tarih="", kullanici="",
                 kaynak="", esik=None):
    """Sipariş kaydedildikten SONRA çağrılır. Döner: (gonderildi, aciklama).

    Hiçbir koşulda istisna fırlatmaz.
    """
    try:
        from shared.telegram_gonder import aktif_mi, gonder
        if not aktif_mi():
            return False, "Telegram kapalı/yapılandırılmamış"
        zararli, maliyetsiz = sorunlu_kalemler(kalemler, esik)
        if not zararli and not maliyetsiz:
            return False, "Uyarı gerektiren kalem yok"
        return gonder(mesaj_uret(zararli, maliyetsiz, kanal, siparis_no,
                                 tarih, kullanici, kaynak))
    except Exception as e:
        return False, f"uyarı gönderilemedi ({type(e).__name__})"

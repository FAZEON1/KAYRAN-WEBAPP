# -*- coding: utf-8 -*-
"""Muhasebe › Bu Hafta › "Mikro'dan öneri" penceresi (Ekim 2026). Hesap: kayranacc/mikro_odeme.py.

Neden Bu Hafta'da (Dosya kapısında değil): Dosya kapısı bir dosya seçilince açılır; burada dosya yok, öneri
Mikro verisinden hesaplanır. Haftalık liste Bu Hafta'da çalışıldığı için düğme oranın başlığında; kayıt
Excel yüklemesiyle aynı yoldan (database.hafta_olustur) ve aynı "aynı adlı hafta" uyarısıyla yapılır.

Akış: hafta seç (bu hafta / gelecek hafta) → öneri tablosu (satırı kaldır, tutar / vade / açıklama /
kategori düzelt) → "Haftaya kaydet": yeni hafta açılır, seçili satırlar ödeme olur, hafta aktif yapılır.
Düğmeye basılmadan hiçbir şey yazılmaz.
"""
from datetime import date

import pandas as pd
import streamlit as st

from shared.tasarim import tr_sayi
from shared.utils import tr_today

from . import mikro_odeme as O

_VERI = "_mo_veri"


def _veri(yenile=False):
    """Mikro verisi bu oturumda bir kez okunur (tabloyu düzenlerken her tıklamada yeniden okunmasın)."""
    if yenile or _VERI not in st.session_state:
        st.session_state[_VERI] = O.veri_oku()
        st.session_state["_mo_surum"] = st.session_state.get("_mo_surum", 0) + 1   # tablo yeni veriyle sıfırlansın
    return st.session_state[_VERI]


def _hafta_secenekleri(bugun):
    out = []
    for kay, ad in ((0, "Bu hafta"), (1, "Gelecek hafta")):
        bas, son = O.hafta_araligi(bugun, kay)
        out.append((f"{ad} ({bas:%d.%m} – {son:%d.%m})", bas, son))
    return out


def _aktif_haftada(satirlar, mevcut):
    """Satır no → aktif haftadaki karşılığı ('aynı' / 'tutar farklı')."""
    k = O.karsilastir(satirlar, mevcut)
    out = {}
    for ad, etiket in (("ayni", "var"), ("farkli", "tutar farklı")):
        for o, _m in k[ad]:
            out[id(o)] = etiket
    return out


def _tablo(satirlar, kat_ad, aktif):
    return pd.DataFrame([{
        "Seç": bool(r["sec"]), "Durum": r["durum"], "Vade": date.fromisoformat(r["vade"]), "Firma": r["firma"],
        "Açıklama": r["aciklama"], "TL": r["tl"], "USD": r["usd"], "Kategori": kat_ad.get(r["kategori"], r["kategori"]),
        "Kaynak": r["kaynak"], "Aktif haftada": aktif.get(id(r), ""),
    } for r in satirlar])


def _geri_cevir(df, kat_anahtar):
    out = []
    for r in df.to_dict("records"):
        v = r.get("Vade")
        out.append({"sec": bool(r.get("Seç")), "firma": r.get("Firma"), "aciklama": r.get("Açıklama"),
                    "cari_banka": "", "vade": v.isoformat() if hasattr(v, "isoformat") else v,
                    "tl": r.get("TL"), "usd": r.get("USD"),
                    "kategori": kat_anahtar.get(r.get("Kategori"), "diger")})
    return out


@st.dialog("Mikro'dan haftalık ödeme önerisi", width="large")
def oneri_penceresi(kategoriler):
    from .database import get_aktif_odemeler, get_tum_haftalar, hafta_olustur
    from .excel_islemler import ayni_hafta
    bugun = tr_today()
    secenek = _hafta_secenekleri(bugun)
    c1, c2, c3 = st.columns([2.6, 2.2, 1], vertical_alignment="bottom")
    # Hafta sonuna doğru (cuma ve sonrası) liste gelecek hafta için hazırlanır
    etiket = c1.segmented_control("Hafta", [s[0] for s in secenek], default=secenek[1 if bugun.weekday() >= 4 else 0][0],
                                  key="mo_hafta") or secenek[0][0]
    _, bas, son = next(s for s in secenek if s[0] == etiket)
    gecikmis = c2.toggle("Vadesi geçmiş açık borçları da göster", value=True, key="mo_gecikmis",
                         help="Vadesi bu haftadan önce olup Mikro'da hâlâ açık görünen faturalar ve çekler. "
                              "Bu hafta ödenmeyecekleri tablodan işaretini kaldırarak çıkar.")
    yenile = c3.button("Yenile", icon=":material/refresh:", key="mo_yenile", use_container_width=True,
                       help="Mikro verisini yeniden oku (aktarıcı 15 dakikada bir getirir).")
    try:
        with st.spinner("Mikro cari hareketleri okunuyor…"):
            veri = _veri(yenile)
        sonuc = O.oneri_hazirla(veri, bas, son, gecikmis)
    except Exception as e:  # noqa: BLE001
        st.error(f"Mikro verisi okunamadı: {type(e).__name__}: {str(e)[:160]}")
        return
    st.caption(f"Kaynak: Mikro'daki satıcı ve diğer borç hesapları (320, 336) — {sonuc['kalem_sayisi']} açık "
               "fatura, ödemeler en eski vadeden düşülerek; ve ödenmemiş firma çekleri. Müşteri hesapları (120, "
               "340) alınmaz. Vergi, SGK, maaş ve kira gibi cari dışı ödemeler Mikro carisinde olmadığı için "
               "listeye elle eklenir.")
    if sonuc["tahmini_vade"]:
        st.caption(f"{sonuc['tahmini_vade']} faturada Mikro ödeme planı var ama planın günü henüz gelmedi "
                   "(aktarıcının günlük keşfiyle gelir); bu faturaların vadesi fatura tarihi sayıldı, açıklamada "
                   "'vade tahmini' yazar.")
    for u in sonuc["uyarilar"]:
        st.warning(u)
    satirlar = sonuc["satirlar"]
    if not satirlar:
        st.info(f"{bas:%d.%m.%Y} – {son:%d.%m.%Y} arasında vadesi gelen açık borç ya da çek yok.")
        return
    mevcut, _hafta = get_aktif_odemeler()
    kat_ad = {k: v.get("label", k) for k, v in kategoriler.items()}
    kat_anahtar = {v: k for k, v in kat_ad.items()}
    df = st.data_editor(
        _tablo(satirlar, kat_ad, _aktif_haftada(satirlar, mevcut)), hide_index=True, use_container_width=True,
        num_rows="fixed", key=f"mo_tablo_{bas}_{int(gecikmis)}_{st.session_state.get('_mo_surum', 0)}", height=min(420, 38 + 35 * len(satirlar)),
        column_config={
            "Seç": st.column_config.CheckboxColumn("Seç", width="small"),
            "Vade": st.column_config.DateColumn("Vade", format="DD.MM.YYYY"),
            "TL": st.column_config.NumberColumn("TL", min_value=0.0, step=0.01, format="localized"),
            "USD": st.column_config.NumberColumn("USD", min_value=0.0, step=0.01, format="localized"),
            "Kategori": st.column_config.SelectboxColumn("Kategori", options=list(kat_ad.values()), required=True),
            "Aktif haftada": st.column_config.TextColumn("Aktif haftada",
                                                         help="Şu anki aktif haftanın listesinde aynı firma var mı"),
        },
        disabled=["Durum", "Kaynak", "Aktif haftada"])
    duzenli = _geri_cevir(df, kat_anahtar)
    odemeler, atlanan = O.odemeye_cevir(duzenli)
    oz = O.ozet(duzenli)
    st.markdown(f"**Seçili: {len(odemeler)} ödeme** · ₺{tr_sayi(oz['tl'], 2)} · ${tr_sayi(oz['usd'], 2)}"
                + (f" · {atlanan} satır tutarı ya da vadesi olmadığı için alınmayacak" if atlanan else ""))
    ad = st.text_input("Hafta adı", value=O.hafta_adi(bas), key=f"mo_ad_{bas}")
    onay = True
    _ayni = ayni_hafta(ad, get_tum_haftalar() or [])
    if _ayni:
        st.warning(f"**'{ad}'** adında bir hafta zaten var ({_ayni.get('yuklendi_tarih') or 'tarih yok'} yüklendi). "
                   "Aynı listeyi ikinci kez yüklersen ödemeler iki ayrı haftada görünür.")
        onay = st.checkbox("Bu farklı bir liste — yine de yeni hafta olarak yükle", key="mo_ayni_onay")
    salt = bool(st.session_state.get("salt_okur"))
    if st.button("Haftaya kaydet", type="primary", icon=":material/check_circle:", use_container_width=True,
                 disabled=salt or not odemeler or not onay or not ad.strip(), key="mo_kaydet",
                 help="Yeni hafta açılır, seçili satırlar ödeme olur ve hafta aktif yapılır."):
        if hafta_olustur(ad.strip(), odemeler) is None:
            st.error("Hafta oluşturulamadı (veritabanı kayıt döndürmedi); hiçbir şey değiştirilmedi.")
            return
        from shared.yukleme_takvimi import kaydet as _yt_kaydet
        _yt_kaydet("odeme_listesi", st.session_state.get("aktif_kullanici", ""), len(odemeler))
        from shared.yukleme_gecmisi import kaydet as _yg_kaydet
        _yg_kaydet("odeme_listesi", len(odemeler), "Mikro önerisi")
        st.session_state.pop(_VERI, None)
        from shared import bilesen as B
        B.yenile(f"{len(odemeler)} ödeme kaydedildi — '{ad.strip()}' aktif hafta yapıldı.")

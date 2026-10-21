# -*- coding: utf-8 -*-
"""Sistem › Mikro bağlantısı — aktarıcı ve eşitlemelerin sağlık paneli (Ekim 2026).

Tek ekranda: aktarıcı son ne zaman yazdı, hangi tablo okunamadı, eşitlemeler açık mı ve en son ne zaman
çalıştı, son eşitleme turları (kaynak: aktarıcı tetiği / yedek zamanlayıcı / uygulama) ve şu an açık sorunlar.
Sorunlar aynı kurallarla Telegram'a da gider (shared/mikro_saglik.py). "Şimdi eşitle" düğmesi turu bu
uygulama içinde hemen çalıştırır. Salt okunur; yalnız düğme eşitlemeyi çalıştırır (her iş kendi onay
kuralıyla: kapalı eşitleme yazmaz).
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from shared import mikro_saglik as S

# (ekrandaki ad, modül) — her modülde durum() / acik_mi() var
ESITLEMELER = (
    ("Satış / iade / sipariş", "satis.mikro_esitle"),
    ("Banka / çek / cari", "kayranacc.mikro_muhasebe"),
    ("Gider tablosu", "kayranacc.mikro_gider"),
    ("Depo stoğu", "kayranpm.mikro_stok"),
    ("Toplam Aktifler stok değeri", "kayranacc.mikro_stok_degeri"),
    ("Happy Life / stok yaşı", "kayranpm.mikro_depo"),
    ("Ürün kartı / fiyat listesi", "kayranpm.mikro_urun"),
    ("İthalat dosyaları / masraflar", "ithalat.mikro_ithalat"),
)
DURUM_AD = {"yazdi": "Yazdı", "yok": "Yeni veri yok", "uyari": "Uyarı", "hata": "Hata"}
KAYNAK_AD = {"github": "Yedek zamanlayıcı", "schedule": "Yedek zamanlayıcı", "workflow_dispatch": "Elle (GitHub)",
             "uygulama": "Uygulama"}


def kaynak_adi(k):
    k = str(k or "")
    if k.startswith("tetik:aktarici_durdu"):
        return "Denetim (aktarıcı durdu)"
    if k.startswith("tetik:"):
        return "Aktarıcı tetiği"
    return KAYNAK_AD.get(k, k or "—")


def tarih_metni(v):
    t = S.zaman(v)
    if t is None:
        return "—"
    yerel = t.astimezone(timezone.utc).timestamp() + 3 * 3600
    return datetime.fromtimestamp(yerel, timezone.utc).strftime("%d.%m.%Y %H:%M")


def esitleme_satirlari(simdi):
    import importlib
    out = []
    for ad, modul in ESITLEMELER:
        try:
            m = importlib.import_module(modul)
            d = m.durum() or {}
            acik = bool(d.get("acik"))
            son = d.get("son_calisma")
        except Exception:  # noqa: BLE001
            acik, son = False, None
        out.append({"Eşitleme": ad, "Durum": "Açık" if acik else "Kapalı (onay bekliyor)",
                    "Son çalışma": tarih_metni(son), "Ne zaman": S.sure_metni(S.dakika_once(son, simdi)) + " önce"
                    if son else "—"})
    return out


def tablo_satirlari(senk, simdi):
    return [{"Tablo": r.get("tablo"), "Son çekim": tarih_metni(r.get("son_cekim")),
             "Ne zaman": (S.sure_metni(S.dakika_once(r.get("guncelleme"), simdi)) + " önce") if r.get("guncelleme")
             else "—",
             "Son turda kayıt": r.get("son_kayit_sayisi") if r.get("son_kayit_sayisi") is not None else "—",
             "Hata": str(r.get("son_hata") or "")[:120]} for r in senk]


def tur_satirlari(gunluk):
    out = []
    for g in gunluk:
        isler = g.get("isler") or []
        yazan = [i["ad"] for i in isler if i.get("durum") == "yazdi"]
        sorunlu = [f"{i['ad']} ({DURUM_AD.get(i.get('durum'), '')})" for i in isler if i.get("durum") in ("uyari", "hata")]
        out.append({"Zaman": tarih_metni(g.get("zaman")), "Kaynak": kaynak_adi(g.get("kaynak")),
                    "Yazan": ", ".join(yazan) or "—", "Sorunlu": ", ".join(sorunlu) or "—",
                    "Açık sorun": len(g.get("sorunlar") or [])})
    return out


def sayfa():
    from shared.tasarim import baslik, kpi_serit
    st.markdown(baslik(":material/sync: Sistem", "Mikro bağlantısı",
                       aciklama="Aktarıcı, eşitlemeler ve uyarılar"), unsafe_allow_html=True)
    simdi = datetime.now(timezone.utc)
    try:
        senk = S.senk_oku()
    except Exception as e:  # noqa: BLE001
        st.error(f"Aktarıcı durumu okunamadı: {type(e).__name__}: {str(e)[:160]}")
        return
    gunluk = S.gunluk_oku(30)
    try:
        satis = S.satis_durumu()
    except Exception:  # noqa: BLE001
        satis = {}
    son_tur = (gunluk[0].get("isler") if gunluk else None)
    sorun = S.sorunlar(senk, son_tur, satis, simdi)
    son_yazim = max((S.zaman(r.get("guncelleme")) for r in senk if S.zaman(r.get("guncelleme"))), default=None)
    tetik = S.tetik_durumu()
    kritik = sum(1 for s in sorun if s["seviye"] == S.KRITIK)
    st.markdown(kpi_serit([
        {"etiket": "Aktarıcı son tur", "deger": (S.sure_metni(S.dakika_once(son_yazim, simdi)) + " önce")
         if son_yazim else "hiç", "renk": "kirmizi" if any(s["kod"].startswith("aktarici_d") for s in sorun) else "yesil"},
        {"etiket": "Son eşitleme turu", "deger": (S.sure_metni(S.dakika_once(gunluk[0].get("zaman"), simdi)) + " önce")
         if gunluk else "hiç", "renk": "mavi"},
        {"etiket": "Açık sorun", "deger": str(len(sorun)), "renk": "kirmizi" if kritik else ("amber" if sorun else "yesil")},
        {"etiket": "Son tetikleme", "deger": (S.sure_metni(S.dakika_once(tetik.get("zaman"), simdi)) + " önce")
         if tetik.get("zaman") else "hiç",
         "alt": "" if not tetik else ("GitHub işi başladı" if tetik.get("durum") == 204 else f"GitHub yanıtı {tetik.get('durum')}"),
         "renk": "mor"},
    ]), unsafe_allow_html=True)

    if sorun:
        for s in sorun:
            (st.error if s["seviye"] == S.KRITIK else st.warning)(s["metin"])
    else:
        st.success("Aktarım ve eşitleme normal.")
    try:
        from shared.telegram_gonder import aktif_mi
        tg = aktif_mi()
    except Exception:  # noqa: BLE001
        tg = False
    st.caption("Sorunlar Telegram'a da bildirilir (eşitleme turunun sonunda; aynı sorun sürerse "
               f"{S.TEKRAR_SAAT} saatte bir hatırlatma, düzelince bir kez \"düzeldi\")."
               + ("" if tg else " Bu uygulamada Telegram ayarı yok; bildirim GitHub işinden gider."))

    if st.button("Şimdi eşitle", icon=":material/sync:", key="msag_simdi"):
        with st.spinner("Eşitleme çalışıyor…"):
            import importlib.util
            from pathlib import Path
            yol = Path(__file__).resolve().parent.parent / "otonom" / "mikro_esitle.py"
            spec = importlib.util.spec_from_file_location("otonom_mikro_esitle_ekran", yol)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            sonuc = mod.tur("uygulama")
        st.dataframe(pd.DataFrame([{"İş": a, "Sonuç": m} for a, m in sonuc]), hide_index=True,
                     use_container_width=True)

    st.markdown("**Eşitlemeler**")
    st.dataframe(pd.DataFrame(esitleme_satirlari(simdi)), hide_index=True, use_container_width=True)
    st.markdown("**Son eşitleme turları**")
    if gunluk:
        st.dataframe(pd.DataFrame(tur_satirlari(gunluk)), hide_index=True, use_container_width=True)
    else:
        st.caption("Henüz kayıtlı tur yok.")
    with st.expander("Aktarıcı tabloları"):
        st.dataframe(pd.DataFrame(tablo_satirlari(senk, simdi)), hide_index=True, use_container_width=True)

# -*- coding: utf-8 -*-
"""Sistem › Bilgi İşlem (Ekim 2026) — bilgi işlem elemanı SERKAN'ın raporu (yönetici).

Eleman (zamanlanmış Claude görevi, otonom/bt_gorevi.md) programı kontrol eder, hata / eksik /
yavaşlık bulur, küçük düzeltmeleri PR olarak açar (kurala uyanlar GitHub'daki kapıdan otomatik
birleşir) ve her şeyi bt_rapor tablosuna yazar. Bu sayfa:
  · özet: son çalışma, açık iş, otomatik birleşen, bu haftanın hataları, sayfa hızı (bu / geçen hafta)
  · iyileştirmeler ve sonuçları (önce → sonra), onay bekleyen öneriler
  · günlük sayfa hızı ve hata grafiği, en yavaş sayfalar, çalışma günlüğü
  · Serkan'ın kendini geliştirmesi: öğrendikleri (her gece) ve haftalık karnesi; kendi talimatını
    değiştiren PR'ları yalnız kullanıcı onayıyla birleşir
"""
import html as _h
from datetime import datetime, timedelta, timezone

import streamlit as st

from shared import bilesen as B
from shared.bt_hesap import gunluk_seri, iyilestirme_satiri, karsilastir, sure_ozeti
from shared.tasarim import bos_durum, kpi_serit, mesaj, tr_sayi

AD = "Serkan"
DURUM_AD = {"acik": ("PR açık", "amber"), "otomatik_birlesti": ("Otomatik birleşti", "yesil"),
            "birlesti": ("Birleşti", "yesil"), "reddedildi": ("Reddedildi", "kirmizi"),
            "oneri": ("Onay bekliyor", "mavi"), "bilgi": ("Bilgi", "silik")}


def _tr_zaman(iso, gun_ay_saat=True):
    """'2026-10-07T10:08:00+00:00' → '07.10 13:08' (Türkiye saati)."""
    try:
        z = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if z.tzinfo is None:
            z = z.replace(tzinfo=timezone.utc)
        z = z.astimezone(timezone(timedelta(hours=3)))
        return z.strftime("%d.%m %H:%M" if gun_ay_saat else "%d.%m.%Y")
    except (TypeError, ValueError):
        return str(iso or "")[:16]


def _sn(ms):
    return "—" if ms is None else f"{tr_sayi(float(ms) / 1000, 2)} sn"


def _deger(v, birim):
    if v is None:
        return "—"
    return _sn(v) if birim == "ms" else f"{tr_sayi(v)} {birim}".strip()


@st.cache_data(ttl=300, show_spinner=False)
def _veri():
    from shared.bt_olcum import raporlar, son_olcumler
    from shared.hata_log import son_hatalar
    return son_olcumler(14), raporlar(300), son_hatalar(500)


def sayfa(kullanici, yonetici, baslik=True):
    """baslik=False: Sistem › Ofis'in sekmesi içinde (başlığı Ofis çizer)."""
    if not yonetici:
        st.error("Bu sayfaya erişim yetkiniz yok.")
        return
    if baslik:
        B.baslik_eylem("Sistem", f"Bilgi İşlem · {AD}",
                       aciklama=f"{AD} her gece programı kontrol eder: hataları, eksikleri ve yavaşlığı arar, küçük "
                                "düzeltmeleri kendisi yapar, büyükleri öneri olarak bırakır, yaptıklarından öğrenir.")
    olcum, rapor, hatalar = _veri()
    if not olcum and not rapor:
        st.markdown(bos_durum(f"{AD} henüz veri toplamadı",
                              "Sayfa süreleri bt_olcum tablosuna yazılır (veritabani/23_bilgi_islem.sql kurulu "
                              f"olmalı). {AD} ilk gece çalışınca rapor burada görünür.", "engineering"),
                    unsafe_allow_html=True)
        return

    simdi = datetime.now(timezone.utc)
    h1 = (simdi - timedelta(days=7)).isoformat()
    bu = [o for o in olcum if str(o.get("zaman")) >= h1]
    gecen = [o for o in olcum if str(o.get("zaman")) < h1]
    hata_bu = [h for h in hatalar if str(h.get("zaman")) >= h1]
    calisma = [r for r in rapor if r.get("tur") == "calisma"]
    iyi = [r for r in rapor if r.get("tur") in ("iyilestirme", "sonuc")]
    oneri = [r for r in rapor if r.get("tur") == "oneri" and r.get("durum") == "oneri"]
    ogren = [r for r in rapor if r.get("tur") == "ogrenme"]
    gelisim = [r for r in rapor if r.get("tur") == "gelisim"]
    gelisim_pr = [r for r in gelisim if r.get("durum") == "acik" and r.get("pr_url")]
    acik = [r for r in iyi if r.get("durum") == "acik"]
    oto = [r for r in iyi if r.get("durum") == "otomatik_birlesti"]

    def _p50(liste):
        s = sorted(float(o["ms"]) for o in liste if o.get("ms") is not None)
        return s[len(s) // 2] if s else None

    p_bu, p_gecen = _p50(bu), _p50(gecen)
    fark = f"geçen hafta {_sn(p_gecen)}" if p_gecen else "geçen hafta ölçüm yok"
    son = _tr_zaman(calisma[0].get("zaman")) if calisma else "henüz yok"
    st.markdown(kpi_serit([
        {"etiket": "Son kontrol", "deger": son, "renk": "mor",
         "alt": f"{tr_sayi(len(calisma))} çalışma"},
        {"etiket": "Sayfa açılışı (ortanca)", "deger": _sn(p_bu), "renk": "cyan", "alt": fark},
        {"etiket": "Bu hafta hata", "deger": tr_sayi(len(hata_bu)), "renk": "kirmizi" if hata_bu else "yesil",
         "alt": f"{len({h.get('yer') for h in hata_bu})} farklı yer"},
        {"etiket": "İyileştirme", "deger": tr_sayi(len(iyi)), "renk": "yesil",
         "alt": f"{len(oto)} otomatik birleşti · {len(acik)} açık"},
        {"etiket": "Onay bekleyen öneri", "deger": tr_sayi(len(oneri)), "renk": "amber" if oneri else "silik"},
    ]), unsafe_allow_html=True)

    for r in gelisim_pr[:3]:
        st.markdown(mesaj("uyari", f"{AD} kendi talimatını geliştirmek istiyor: {r.get('baslik') or ''}. "
                                   f"PR'ı inceleyip uygunsa birleştir: {r.get('pr_url')}"), unsafe_allow_html=True)
    if oneri:
        st.markdown(B.grup_basligi("Onayını bekleyen öneriler", f"{len(oneri)} öneri"), unsafe_allow_html=True)
        for r in oneri[:10]:
            # mesaj() metni kendisi kaçışlar: düz metin verilir
            st.markdown(mesaj("bilgi", f"{r.get('baslik') or ''}: {r.get('ozet') or ''} "
                                       "Yapılmasını istiyorsan bana yaz."), unsafe_allow_html=True)

    _grafik(gunluk_seri(olcum, hatalar))

    st.markdown(B.grup_basligi("İyileştirmeler ve sonuçları", f"{len(iyi)} kayıt"), unsafe_allow_html=True)
    if iyi:
        satir = []
        for r in iyi[:50]:
            s = iyilestirme_satiri(r)
            satir.append({"Tarih": _tr_zaman(r.get("zaman"), False), "İş": s["baslik"],
                          "Durum": DURUM_AD.get(s["durum"], (s["durum"] or "—",))[0],
                          "Ölçüt": s["olcut"] or "—", "Önce": _deger(s["once"], s["birim"]),
                          "Sonra": _deger(s["sonra"], s["birim"]),
                          "Fark": "—" if s["fark_yuzde"] is None else f"%{tr_sayi(s['fark_yuzde'], 1)}",
                          "PR": s["pr_url"] or None})
        st.dataframe(satir, hide_index=True, use_container_width=True,
                     column_config={"PR": st.column_config.LinkColumn("PR", display_text="Aç")})
        st.caption("Fark eksiyse iyileşme var (sayfa daha hızlı ya da hata daha az).")
    else:
        st.caption("Henüz iyileştirme yok.")

    st.markdown(B.grup_basligi("En yavaş sayfalar · bu hafta", f"{tr_sayi(len(bu))} açılış"),
                unsafe_allow_html=True)
    oz_bu, oz_gecen = sure_ozeti(bu), sure_ozeti(gecen)
    kars = {(r["modul"], r["sayfa"]): r for r in karsilastir(oz_gecen, oz_bu, en_az_adet=1)}
    yavas = sorted(oz_bu.items(), key=lambda kv: -kv[1]["p90"])[:12]
    if yavas:
        st.dataframe([{"Modül": k[0], "Sayfa": k[1] or "—", "Açılış": v["adet"], "Ortanca": _sn(v["p50"]),
                       "Yavaş (p90)": _sn(v["p90"]), "Hata": v["hata"],
                       "Geçen haftaya göre": ("—" if k not in kars else f"%{tr_sayi(kars[k]['fark_yuzde'], 1)}")}
                      for k, v in yavas], hide_index=True, use_container_width=True)
    else:
        st.caption("Bu hafta ölçüm yok.")

    st.markdown(B.grup_basligi(f"{AD} kendini geliştiriyor", f"{len(ogren)} öğrenme · {len(gelisim)} karne/geliştirme"),
                unsafe_allow_html=True)
    karne = next((r for r in gelisim if r.get("baslik") == "Haftalık karnem"), None)
    if karne:
        st.markdown(f"**Son haftalık karnesi ({_tr_zaman(karne.get('zaman'), False)}):** "
                    f"{_h.escape(karne.get('ozet') or '')}")
    if ogren:
        st.dataframe([{"Tarih": _tr_zaman(r.get("zaman"), False), "Öğrendiği": r.get("baslik") or "",
                       "Neden": r.get("ozet") or ""} for r in ogren[:15]],
                     hide_index=True, use_container_width=True)
    if not karne and not ogren:
        st.caption(f"{AD} her gecenin sonunda öğrendiklerini, pazar geceleri de haftalık karnesini buraya yazar.")

    if calisma:
        with st.expander(f"Çalışma günlüğü ({len(calisma)})", icon=":material/history:"):
            for r in calisma[:20]:
                st.markdown(f"**{_tr_zaman(r.get('zaman'))}** — "
                            f"{_h.escape(r.get('ozet') or r.get('baslik') or '')}")


def _grafik(seri):
    """Günlük sayfa açılışı ortancası (tek seri, tek eksen). Hatalar özet şeridinde ve tabloda."""
    seri = [s for s in seri if s.get("p50") is not None]
    if len(seri) < 2:
        return
    try:
        import plotly.graph_objects as go
        from shared import grafik as G
        gun = [s["gun"][8:10] + "." + s["gun"][5:7] for s in seri]
        fig = go.Figure(go.Scatter(x=gun, y=[s["p50"] / 1000 for s in seri], mode="lines+markers",
                                   line=dict(color=G.rol("ana"), width=2), marker=dict(size=8),
                                   fill="tozeroy", fillcolor=G.saydam(G.rol("ana"), 0.08),
                                   customdata=[s["adet"] for s in seri],
                                   hovertemplate="%{x}<br>%{y:.2f} sn · %{customdata} açılış<extra></extra>"))
        st.markdown(B.grup_basligi("Sayfa açılışı · son 14 gün", "günlük ortanca, saniye"), unsafe_allow_html=True)
        G.goster(fig, key="bt_grafik", yukseklik=240, aciklama=False,
                 xaxis=dict(type="category"),        # '07.10' sayı sanılmasın
                 yaxis=dict(title=None, rangemode="tozero", ticksuffix=" sn"))
    except Exception:  # noqa: BLE001
        pass

# -*- coding: utf-8 -*-
"""Bayi Portalı — Özet ekranı.

Bayinin güncel cari durumu (borç / alacak / net, döviz bazlı) + açık servis
kayıtlarının kısa özeti. Veri, "Toplam Aktifler"e yüklenen Cari Alacaklar
Excel'inin satır detayından gelir (bkz. bayi/veri.py).
"""
import pandas as pd
import streamlit as st

from bayi.veri import cari_bakiye, bayi_servis_kayitlari

# Döviz simgeleri ve formatı
_SIMGE = {"USD": "$", "TL": "₺", "EUR": "€", "TRY": "₺"}


def _fmt(doviz, tutar):
    sim = _SIMGE.get(doviz.upper(), "")
    if doviz.upper() in ("TL", "TRY"):
        return f"{sim}{tutar:,.0f}"
    return f"{sim}{tutar:,.2f}"


def _kart(baslik, deger, renk, alt=""):
    alt_html = f'<div style="font-size:12px;color:#94A3B8;margin-top:6px">{alt}</div>' if alt else ""
    st.markdown(
        f'<div style="background:#0F1730;border:1px solid #232B47;border-radius:12px;'
        f'padding:16px 18px;height:100%">'
        f'<div style="font-size:13px;color:#A5B4FC;font-weight:600">{baslik}</div>'
        f'<div style="font-size:26px;font-weight:800;color:{renk};'
        f'font-family:JetBrains Mono,monospace;letter-spacing:-1px;margin-top:6px">{deger}</div>'
        f'{alt_html}</div>',
        unsafe_allow_html=True,
    )


def render(bayi):
    """bayi: bayi_kullanicilar satırı (dict)."""
    unvan = bayi.get("cari_unvan") or ""
    kod = bayi.get("cari_kod") or ""

    st.markdown(
        f'<div style="font-size:22px;font-weight:800;color:#E2E8F0">👋 Hoş geldiniz'
        f'{", " + bayi.get("ad_soyad") if bayi.get("ad_soyad") else ""}</div>'
        f'<div style="font-size:14px;color:#94A3B8;margin-top:2px">{unvan}'
        f'{" · " + kod if kod else ""}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ─── Cari durum ───
    st.markdown('<div style="font-size:17px;font-weight:700;color:#E2E8F0;'
                'margin-bottom:10px">🧾 Cari Durumunuz</div>', unsafe_allow_html=True)

    veri = cari_bakiye(cari_kod=kod, cari_unvan=unvan)
    if not veri["bulundu"]:
        st.info("Cari kaydınız henüz güncellenmemiş. Muhasebe Cari Alacaklar listesi "
                "yüklendiğinde bakiyeniz burada görünecek.")
    else:
        for doviz, v in sorted(veri["doviz_bazli"].items()):
            net = v["net"]
            if net > 0:
                net_renk, net_etiket = "#F87171", "Borç bakiyeniz (ödemeniz gereken)"
                net_gosterim = _fmt(doviz, net)
            elif net < 0:
                net_renk, net_etiket = "#34D399", "Lehinize bakiye (alacağınız)"
                net_gosterim = _fmt(doviz, abs(net))
            else:
                net_renk, net_etiket = "#94A3B8", "Bakiye kapalı"
                net_gosterim = _fmt(doviz, 0)

            st.markdown(f'<div style="font-size:14px;color:#A5B4FC;font-weight:700;'
                        f'margin:6px 0">{doviz}</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                _kart("📤 Toplam Borç", _fmt(doviz, v["bayi_borc"]), "#F87171")
            with c2:
                _kart("📥 Toplam Alacak", _fmt(doviz, v["bayi_alacak"]), "#34D399")
            with c3:
                _kart(f"⚖️ Net", net_gosterim, net_renk, alt=net_etiket)

        with st.expander("🔎 Cari satır detayı"):
            df = pd.DataFrame([{
                "Kod": r.get("kod", ""),
                "Unvan": r.get("unvan", ""),
                "Döviz": r.get("doviz", ""),
                "Borç": round(float(r.get("borc") or 0), 2),
                "Alacak": round(float(r.get("alacak") or 0), 2),
                "Bakiye": round(float(r.get("bakiye") or 0), 2),
            } for r in veri["satirlar"]])
            st.dataframe(df, hide_index=True, use_container_width=True)
            st.caption("Bakiye şirket defteri işaretindedir: pozitif = borcunuz, "
                       "negatif = lehinize. Net kart bunu bayi perspektifine çevirir.")

    st.markdown("---")

    # ─── Servis özeti ───
    st.markdown('<div style="font-size:17px;font-weight:700;color:#E2E8F0;'
                'margin-bottom:10px">🔧 Servis Özeti</div>', unsafe_allow_html=True)
    try:
        from teknikservis.database import BITMIS_DURUMLAR
    except Exception:
        BITMIS_DURUMLAR = set()

    kayitlar = bayi_servis_kayitlari(unvan)
    toplam = len(kayitlar)
    acik = [k for k in kayitlar if (k.get("mevcut_durum") or "") not in BITMIS_DURUMLAR]
    c1, c2, c3 = st.columns(3)
    with c1:
        _kart("📋 Toplam Kayıt", str(toplam), "#818CF8")
    with c2:
        _kart("⏳ Açık / Süren", str(len(acik)), "#FBBF24")
    with c3:
        _kart("✅ Tamamlanan", str(toplam - len(acik)), "#34D399")

    if toplam:
        st.caption("Detay ve durum geçmişi için sol menüden **Servis Takibi** ekranına geçin.")
    else:
        st.info("Adınıza kayıtlı servis/iade kaydı bulunmuyor.")

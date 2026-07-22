# -*- coding: utf-8 -*-
"""Bayi Portalı — Servis Takibi ekranı (SALT-OKUNUR).

Bayi, yalnızca kendi cari unvanına ait teknik servis / iade kayıtlarını görür:
form no, arayüz, mevcut durum, SLA iş günü (renkli), mal kabul tarihi, seri no,
ürün ve durum geçmişi. Kayıt oluşturma/düzenleme YOK (Faz 1).
"""
import pandas as pd
import streamlit as st

from bayi.veri import bayi_servis_kayitlari, bayi_servis_gecmisi

# Teknik servis modülünün mantığını aynen yeniden kullan (tek doğruluk kaynağı)
try:
    from teknikservis.database import (
        sla_is_gunu, sla_renk, DURUM_RENK, BITMIS_DURUMLAR, ARAYUZ_ETIKET,
    )
except Exception:  # modül yüklenemezse güvenli varsayılanlar
    DURUM_RENK, BITMIS_DURUMLAR, ARAYUZ_ETIKET = {}, set(), {}

    def sla_is_gunu(k):
        return None

    def sla_renk(g, bitmis=False):
        return "#64748B", (f"{g} iş günü" if g is not None else "—")


def _tarih_kisa(v):
    return str(v or "")[:10] or "—"


def _durum_rozet(durum):
    renk = DURUM_RENK.get(durum, "#64748B")
    return (f'<span style="background:{renk}22;color:{renk};border:1px solid {renk}55;'
            f'padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600">{durum}</span>')


def _kayit_detay(kayit):
    """Bir kaydın genişletilebilir detayı + durum geçmişi."""
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Seri No:** {kayit.get('seri_no') or '—'}")
        st.markdown(f"**Ürün:** {kayit.get('stok_adi') or kayit.get('urun_grubu') or '—'}")
        st.markdown(f"**Arıza / Açıklama:** {kayit.get('ariza') or '—'}")
    with c2:
        st.markdown(f"**Mal Kabul:** {_tarih_kisa(kayit.get('mal_kabul_tarihi'))}")
        st.markdown(f"**Fatura No:** {kayit.get('fatura_no') or '—'}")
        st.markdown(f"**Firma Servis Form No:** {kayit.get('firma_servis_form_no') or '—'}")

    st.markdown("**📜 Durum Geçmişi**")
    gecmis = bayi_servis_gecmisi(kayit.get("id"))
    if not gecmis:
        st.caption("Henüz durum hareketi kaydı yok.")
        return
    for g in gecmis:
        durum = g.get("durum") or g.get("yeni_durum") or "—"
        tarih = _tarih_kisa(g.get("tarih"))
        aciklama = g.get("aciklama") or g.get("not") or ""
        st.markdown(
            f'<div style="display:flex;gap:10px;align-items:center;padding:4px 0">'
            f'<span style="color:#64748B;font-size:12px;font-family:JetBrains Mono,monospace;'
            f'min-width:92px">{tarih}</span>{_durum_rozet(durum)}'
            f'<span style="color:#94A3B8;font-size:13px">{aciklama}</span></div>',
            unsafe_allow_html=True,
        )


def render(bayi):
    """bayi: bayi_kullanicilar satırı (dict)."""
    unvan = bayi.get("cari_unvan") or ""
    st.markdown('<div style="font-size:22px;font-weight:800;color:#E2E8F0">'
                '🔧 Servis Takibi</div>'
                f'<div style="font-size:14px;color:#94A3B8;margin-top:2px">{unvan}</div>',
                unsafe_allow_html=True)
    st.caption("21 iş günü SLA hedefi · renkler süreyi gösterir · salt-okunur")
    st.markdown("---")

    kayitlar = bayi_servis_kayitlari(unvan)
    if not kayitlar:
        st.info("Adınıza kayıtlı servis/iade kaydı bulunmuyor.")
        return

    # ─── Filtreler ───
    c1, c2 = st.columns([1, 1])
    with c1:
        arayuz_sec = st.selectbox(
            "Arayüz", ["Tümü", "teknik", "iade"],
            format_func=lambda x: "Tümü" if x == "Tümü" else ARAYUZ_ETIKET.get(x, x),
            key="bayi_servis_arayuz")
    with c2:
        durum_gorunum = st.radio("Görünüm", ["Açık kayıtlar", "Tümü"],
                                 horizontal=True, key="bayi_servis_gorunum")

    filtreli = kayitlar
    if arayuz_sec != "Tümü":
        filtreli = [k for k in filtreli if (k.get("arayuz") or "") == arayuz_sec]
    if durum_gorunum == "Açık kayıtlar":
        filtreli = [k for k in filtreli if (k.get("mevcut_durum") or "") not in BITMIS_DURUMLAR]

    if not filtreli:
        st.info("Bu filtreye uyan kayıt yok.")
        return

    # ─── Özet tablo ───
    satirlar = []
    for k in filtreli:
        bitmis = (k.get("mevcut_durum") or "") in BITMIS_DURUMLAR
        g = sla_is_gunu(k)
        _, sla_etiket = sla_renk(g if g is not None else 0, bitmis=bitmis)
        satirlar.append({
            "Form No": k.get("servis_form_no") or "—",
            "Arayüz": ARAYUZ_ETIKET.get(k.get("arayuz"), k.get("arayuz") or "—"),
            "Durum": k.get("mevcut_durum") or "—",
            "SLA": sla_etiket,
            "Mal Kabul": _tarih_kisa(k.get("mal_kabul_tarihi")),
            "Seri No": k.get("seri_no") or "—",
            "Ürün": (k.get("stok_adi") or k.get("urun_grubu") or "—"),
        })
    st.dataframe(pd.DataFrame(satirlar), hide_index=True, use_container_width=True)
    st.caption(f"{len(filtreli)} kayıt gösteriliyor.")

    # ─── Kayıt detayı ───
    st.markdown('<div style="font-size:15px;font-weight:700;color:#E2E8F0;'
                'margin-top:14px">Kayıt detayı</div>', unsafe_allow_html=True)
    for k in filtreli:
        form_no = k.get("servis_form_no") or "—"
        durum = k.get("mevcut_durum") or "—"
        with st.expander(f"{form_no} · {durum} · {k.get('seri_no') or ''}"):
            _kayit_detay(k)

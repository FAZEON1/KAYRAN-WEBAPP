# -*- coding: utf-8 -*-
"""Ortak grafik dili (Ekim 2026) — bütün Plotly grafikleri bu düzenle çizilir.

Kullanım:
    from shared.grafik import goster, rol, isaretli
    fg = go.Figure()
    fg.add_bar(x=x, y=ciro, name="Ciro", marker_color=rol("ana"))
    goster(fg, key="pp_grafik", yukseklik=260, yaxis=dict(tickprefix="$"))

Renk kuralı (kartlar ve tablolarla aynı): renk yalnız anlam taşır.
  ana      → ana seri (ciro, satış)                    · mor
  ikincil  → ikinci seri (net kâr, kalan bakiye)        · nötr
  silik    → ortalama / eğilim (kesikli)
  iyi / kotu / dikkat → yalnız işaret: eksi gün kırmızı, ödenen yeşil, bekleyen amber
İstisna: kategori halkası — renkler kategoriyi ayırır.
Renkler aktif temadan (koyu / açık) alınır; grafik çizildiği an doğru temada olur.
"""
from shared.tasarim import renk as _renk

_ROL = {"ana": "mor", "ikincil": "soluk", "silik": "silik", "iyi": "yesil", "kotu": "kirmizi",
        "dikkat": "amber", "izgara": "kenar", "metin": "metin", "zemin": "yuzey2"}
YAZI = "Inter, sans-serif"


def rol(ad):
    """Renk rolü → aktif temanın hex rengi."""
    return _renk(_ROL.get(ad, ad))


def saydam(hex_renk, oran):
    """'#818CF8', 0.1 → 'rgba(129,140,248,0.1)' (dolgu için)."""
    h = str(hex_renk).lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{oran})"


def isaretli(degerler, ana="ana"):
    """Çubuk renkleri: eksi değer kırmızı (zarar günü/ayı), diğerleri verilen rol."""
    return [rol("kotu") if (v or 0) < 0 else rol(ana) for v in degerler]


def duzen(fig, yukseklik=280, aciklama=True, **ek):
    """Ortak düzeni uygular; ek= ile grafiğe özel ayar (eksen biçimi, bargap…) ezer.
    xaxis/yaxis sözlükleri ortak eksen ayarının ÜSTÜNE yazılır (birleştirilir)."""
    ex = dict(showgrid=False, zeroline=False, linecolor=rol("izgara"), tickfont=dict(size=11))
    ey = dict(gridcolor=rol("izgara"), zeroline=False, tickfont=dict(size=11))
    ex.update(ek.pop("xaxis", {}) or {})
    ey.update(ek.pop("yaxis", {}) or {})
    fig.update_layout(
        height=yukseklik, margin=dict(t=28 if aciklama else 8, b=4, l=4, r=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
        font=dict(family=YAZI, size=11, color=rol("ikincil")),
        showlegend=aciklama,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, xanchor="left",
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=rol("ikincil"))),
        hoverlabel=dict(bgcolor=rol("zemin"), bordercolor=rol("izgara"),
                        font=dict(family=YAZI, size=12, color=rol("metin"))),
        xaxis=ex, yaxis=ey)
    if ek:
        fig.update_layout(**ek)
    return fig


def halka(fig, orta_ust, orta_deger, orta_alt="", yukseklik=300):
    """Halka (pasta) grafiği: ince ayraç, alt açıklama, ortada cümle düzeninde etiket."""
    fig.update_traces(marker=dict(line=dict(color=rol("zemin"), width=2)), selector=dict(type="pie"))
    # Dilim yüzdesi Türkçe ("%39,4"); Plotly'nin kendi biçimi işareti sona koyuyor ("39,4%")
    from shared.tasarim import tr_sayi
    for tr in fig.data:
        if getattr(tr, "type", "") == "pie" and tr.values is not None:
            tp = float(sum(v or 0 for v in tr.values)) or 1.0
            tr.text = [f"%{tr_sayi((v or 0) / tp * 100, 1)}" for v in tr.values]
            tr.textinfo = "text"
    alt = f"<br><span style='font-size:11px'>{orta_alt}</span>" if orta_alt else ""
    fig.add_annotation(text=f"<span style='font-size:11px'>{orta_ust}</span><br><b>{orta_deger}</b>{alt}",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=20, family=YAZI, color=rol("metin")))
    duzen(fig, yukseklik=yukseklik, margin=dict(t=8, b=8, l=8, r=8),
          legend=dict(orientation="h", y=-0.04, yanchor="top", x=0.5, xanchor="center",
                      bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=rol("ikincil"))))
    return fig


def goster(fig, key=None, **duzen_kw):
    """Ortak düzen + st.plotly_chart (araç çubuğu kapalı, tam genişlik)."""
    import streamlit as st
    if duzen_kw or not getattr(fig.layout, "paper_bgcolor", None):
        duzen(fig, **duzen_kw)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "displaylogo": False},
                    key=key)

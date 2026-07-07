"""
KAYRAN — İthalat Modülü
  📋 Geçmiş İthalatlar : dosya başı toplam masraf + FOB üzerine binen % maliyet, kalem detayları
  ➕ Yeni İthalat      : manuel form + Excel toplu yükleme
  🔍 Model Sorgu       : SKU yaz → geçmiş tüm alımlar (firma/adet/fiyat/dosya % maliyeti/final maliyet)
"""
import io
from datetime import date

import streamlit as st
import pandas as pd
from collections import defaultdict
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici, gun_ay_yil

from .database import (
    get_dosyalar, get_kalemler, get_tum_kalemler, get_urun_katalog,
    ekle_dosya, guncelle_dosya, sil_dosya, dosya_hesapla, dosya_hesapla_coklu, dosya_coklu_mu, ORTAK_GRUP, parse_maliyet_coklu_sayfa, MASRAF_TANIM, MASRAF_ETIKET, masraf_dokumu, _masraf_dict, masraf_sifirla,
    set_dosya_takip_no, dagit_ortak_masraf, DURUM_SECENEKLER, VARSAYILAN_DURUM, IN_TRANSIT_DURUMLAR,
    get_tedarikciler, teslim_tarihleri_uygula, set_dosya_teslim, set_dosya_durum,
    set_dosya_sas, set_dosya_teslim_sekli,
    get_barkod_map, set_barkod, barkod_toplu_yukle, urun_bilgi_toplu_yukle, sil_dosya,
)


# Teslim deposu seçenekleri (açılır liste)
DEPO_SECENEKLER = ["(Seçilmedi)", "MERKEZ DEPO", "HAPPY LIFE", "TEKNİK DEPO", "ASEL DEPO"]
# Teslim Şekli (Incoterm) seçenekleri
INCOTERM_SECENEKLER = ["(Seçilmedi)", "FOB", "EXW", "CIF", "DAP", "DDP", "FCA", "CFR", "CPT", "CIP", "DPU"]


def _tam(x, max_ond=6):
    """Tutarı YUVARLAMADAN, gereksiz sondaki sıfırları atarak TR biçiminde gösterir.
    Mal bedeli ve masraf gibi tutarlar yukarı/aşağı yuvarlanmadan tam görünür.
    Örn: 1234 → '1.234', 1234.5 → '1.234,5', 1234.56 → '1.234,56', 1234.5678 → '1.234,5678'."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "0"
    neg = x < 0
    x = abs(x)
    s = f"{x:.{max_ond}f}".rstrip("0").rstrip(".")
    tam, _, ond = s.partition(".")
    parcali = ""
    while len(tam) > 3:
        parcali = "." + tam[-3:] + parcali
        tam = tam[:-3]
    tam = tam + parcali
    sonuc = tam + ("," + ond if ond else "")
    return ("-" + sonuc) if neg else sonuc


# ─────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────
def _sf(v, d=0.0):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return float(d)
        return float(v)
    except Exception:
        return float(d)


def _sd(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return str(v)[:10]


def _tr_upper(s):
    """Türkçe uyumlu büyük harf: i→İ, ı→I (Python'un .upper()'ı i→I yapar, yanlış)."""
    return str(s or "").replace("i", "İ").replace("ı", "I").upper()


def _baslik(ikon, ad, alt):
    from shared.ui import sayfa_baslik as _sb
    st.markdown(_sb(ikon, ad, alt), unsafe_allow_html=True)

def _metrik_satiri(cards):
    """Kompakt, renkli metric kartları satırı. cards = [{'label','value','renk','help'?}]."""
    cells = ""
    for c in cards:
        renk = c.get("renk", "#A5B4FC")
        ttl = f' title="{c["help"]}"' if c.get("help") else ""
        ipucu = ' <span style="color:#64748B;font-size:11px">ⓘ</span>' if c.get("help") else ""
        cells += (
            f'<div{ttl} style="flex:1;min-width:150px;'
            f'background:linear-gradient(180deg,rgba(255,255,255,0.030),rgba(255,255,255,0.012));'
            f'border:1px solid rgba(255,255,255,0.055);border-left:3px solid {renk};'
            f'border-radius:16px;padding:14px 18px">'
            f'<div style="color:#8B97A8;font-size:11px;font-weight:700;letter-spacing:.6px;'
            f'text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{c["label"]}{ipucu}</div>'
            f'<div style="color:#F1F5F9;font-size:19px;font-weight:800;margin-top:3px;'
            f'font-variant-numeric:tabular-nums;letter-spacing:-0.3px;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis">{c["value"]}</div>'
            f'</div>'
        )
    st.markdown(f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin:0px 0 12px">{cells}</div>',
                unsafe_allow_html=True)


def _alt_baslik(t):
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#A5B4FC;letter-spacing:1.2px;'
        f'text-transform:uppercase;margin:0px 0 12px;display:flex;align-items:center;gap:8px">'
        f'<span style="width:5px;height:14px;border-radius:3px;background:linear-gradient(180deg,#6366F1,#A78BFA);display:inline-block"></span>'
        f'{t}</div>',
        unsafe_allow_html=True,
    )


def _form_css():
    """İthalat sayfalarındaki Streamlit girdilerini modern KAYRAN temasına çeker."""
    st.markdown(
        """
        <style>
        /* ── Girdi kutuları (text / number / date) ── */
        .main [data-testid="stTextInput"] input,
        .main [data-testid="stNumberInput"] input,
        .main [data-testid="stDateInput"] input {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            border-radius: 11px !important;
            color: #E2E8F0 !important;
            font-size: 13px !important;
            padding: 11px 14px !important;
            transition: border-color .2s, box-shadow .2s !important;
        }
        .main [data-testid="stTextInput"] input:focus,
        .main [data-testid="stNumberInput"] input:focus,
        .main [data-testid="stDateInput"] input:focus {
            border-color: #8B5CF6 !important;
            box-shadow: 0 0 0 3px rgba(139,92,246,0.15) !important;
        }
        .main [data-testid="stTextInput"] input::placeholder { color: #475569 !important; }

        /* ── Etiketler ── */
        .main [data-testid="stWidgetLabel"] p {
            color: #94A3B8 !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            letter-spacing: .5px !important;
            text-transform: uppercase !important;
        }

        /* ── Selectbox (döviz) ── */
        .main [data-baseweb="select"] > div {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            border-radius: 11px !important;
            color: #E2E8F0 !important;
        }
        .main [data-baseweb="select"] > div:hover { border-color: rgba(139,92,246,0.4) !important; }

        /* ── Number input: adımlayıcıları gizle, temiz alan ── */
        .main [data-testid="stNumberInput"] button { display: none !important; }
        .main [data-testid="stNumberInput"] input { text-align: right !important; }

        /* ── Metric kartları (modern · sade) ── */
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015));
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 16px;
            padding: 16px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.22);
            transition: border-color .15s ease;
        }
        div[data-testid="stMetric"]:hover { border-color: rgba(139,92,246,0.32); }
        div[data-testid="stMetricLabel"],
        div[data-testid="stMetricLabel"] p,
        div[data-testid="stMetricLabel"] div {
            color: #94A3B8 !important; font-size: 11px !important; font-weight: 600 !important;
            letter-spacing: .5px !important; text-transform: uppercase !important;
        }
        div[data-testid="stMetricValue"] {
            color: #F1F5F9 !important; font-size: 22px !important; font-weight: 700 !important;
            font-variant-numeric: tabular-nums; line-height: 1.2 !important; margin-top: 3px;
            white-space: normal !important; word-break: break-word;
        }

        /* ── Özel ürün tablosu başlık hücreleri ── */
        .ith-th {
            background: linear-gradient(135deg,#1E293B,#0F172A);
            color: #CBD5E1; font-size: 10px; font-weight: 700; letter-spacing: .4px;
            text-transform: uppercase; padding: 8px 12px; border-radius: 8px;
            font-family: Inter, sans-serif; white-space: nowrap;
            overflow: hidden; text-overflow: ellipsis;
        }

        /* ── Kart kapsayıcılar (st.container border=True) ── */
        .main [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255,255,255,0.02) !important;
            border: 1px solid rgba(255,255,255,0.07) !important;
            border-radius: 16px !important;
        }

        /* ── Veri editörü / tablolar ── */
        .main [data-testid="stDataFrame"],
        .main [data-testid="stDataEditor"] {
            border-radius: 12px !important;
            overflow: hidden !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
        }

        /* ── Sekmeler ── */
        .main [data-baseweb="tab-list"] { gap: 6px !important; border-bottom: 1px solid rgba(255,255,255,0.06) !important; }
        .main [data-baseweb="tab"] {
            background: rgba(255,255,255,0.03) !important;
            border-radius: 10px 10px 0 0 !important;
            padding: 8px 16px !important;
            color: #94A3B8 !important;
        }
        .main [data-baseweb="tab"][aria-selected="true"] {
            background: rgba(99,102,241,0.15) !important;
            color: #C4B5FD !important;
        }

        /* ── Dosya yükleyici ── */
        .main [data-testid="stFileUploaderDropzone"] {
            background: rgba(255,255,255,0.03) !important;
            border: 1px dashed rgba(139,92,246,0.35) !important;
            border-radius: 12px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _tablo(df, para=None, yuzde=None, sol=None, kisalt=None):
    """DataFrame'i KAYRAN renkli HTML tablosunda çizer (salt-okunur)."""
    para = set(para or []); yuzde = set(yuzde or []); sol = set(sol or []); kisalt = kisalt or {}
    if df is None or len(df) == 0:
        st.info("Gösterilecek veri yok.")
        return
    kolonlar = list(df.columns)

    def _isnum(c):
        try:
            return pd.api.types.is_numeric_dtype(df[c])
        except Exception:
            return False

    def _sag(c):
        return (c in para or c in yuzde or _isnum(c)) and c not in sol

    def _fmt(c, v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "\u2014"
        try:
            if c in para:
                return _tam(v)
            if c in yuzde:
                return f"%{float(v):.2f}"
            if _isnum(c):
                fv = float(v)
                return _tam(fv)
        except Exception:
            pass
        s = str(v); mx = kisalt.get(c)
        return (s[:mx-1] + "\u2026") if (mx and len(s) > mx) else s

    rows_html = ""
    for _, row in df.iterrows():
        tds = ""
        for c in kolonlar:
            v = row[c]
            cls = "rk-num" if _sag(c) else "rk-txt"
            full = str(v); mx = kisalt.get(c)
            ttl = f' title="{full.replace(chr(34), "&quot;")}"' if (mx and len(full) > mx) else ""
            tds += f'<td class="{cls}"{ttl}>{_fmt(c, v)}</td>'
        rows_html += f"<tr>{tds}</tr>"
    ths = "".join(f'<th class="{"" if _sag(c) else "l"}">{c}</th>' for c in kolonlar)
    css = (
        "<style>"
        ".itw{overflow-x:auto;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,0.25);margin:4px 0}"
        ".itt{width:100%;border-collapse:collapse;font-family:Inter,sans-serif}"
        ".itt thead tr{background:linear-gradient(135deg,#1E293B,#0F172A)}"
        ".itt thead th{padding:8px 12px;color:#CBD5E1;font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap;text-align:right}"
        ".itt thead th.l{text-align:left}"
        ".itt tbody{background:#131C35}"
        ".itt td{padding:8px 12px;font-size:11px;max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".itt tbody tr{border-bottom:1px solid rgba(255,255,255,0.05)}"
        ".itt tbody tr:hover{background:rgba(99,102,241,0.06)}"
        ".rk-txt{text-align:left;color:#CBD5E1}"
        ".rk-num{text-align:right;color:#CBD5E1;font-family:'JetBrains Mono',monospace}"
        "</style>"
    )
    st.html(css + f'<div class="itw"><table class="itt"><thead><tr>{ths}</tr></thead><tbody>' + rows_html + "</tbody></table></div>")


def _excel_sablon_bytes():
    """Satın Alım Raporu formatında örnek şablon (sistemden çekilen yapıyla aynı başlıklar)."""
    kolonlar = ["İthalat Takip No", "Sipariş Tarihi", "Sipariş no", "Belge no", "Belge tarihi", "Sipariş cinsi",
                "Teslim tarihi", "Teslim türü", "Cari hesap kodu", "Cari hesap adı", "Stok kodu",
                "Stok ismi", "Depo", "Miktar", "Birim", "Birim Fiyat", "Toplam iskonto", "Net fiyat",
                "Döviz", "Tutar", "Tamamlanan miktar", "Kalan miktar", "Öd.Pl", "Onay durumu",
                "Açık/Kapalı", "Durum"]
    s1 = ["2025-1", "2025-01-15", "SAS-1", "PI-2025-001", "2025-01-15", "Dış Ticaret siparişi", "2025-04-20",
          "FOB", "320.50.001", "ABC DISPLAY CO., LTD", "X27F165QW",
          "27 inch Gaming Monitor", "Merkez depo", 100, "Adet", 85, 0, 85, "USD", 8500, 100, 0,
          "PEŞİN", "Onaylandı", "Açık", "Açık"]
    s2 = ["2025-1", "2025-01-15", "SAS-1", "PI-2025-001", "2025-01-15", "Dış Ticaret siparişi", "2025-04-20",
          "FOB", "320.50.001", "ABC DISPLAY CO., LTD", "CASE-MID-01",
          "Mid Tower Kasa", "Merkez depo", 50, "Adet", 40, 0, 40, "USD", 2000, 50, 0,
          "PEŞİN", "Onaylandı", "Açık", "Açık"]
    ornek = pd.DataFrame([s1, s2], columns=kolonlar)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        ornek.to_excel(w, index=False, sheet_name="Sheet")
    return buf.getvalue()


def _masraf_karti(d, h):
    doviz = d.get("doviz", "")
    _ind = h.get("indirim", 0.0)
    _net = h.get("net_mal_bedeli", h["mal_bedeli"])
    # İndirim varsa: Brüt → İndirim → Net olarak göster; yoksa tek "Mal Bedeli" kartı
    if _ind > 0:
        _mb_html = (
            '<div style="background:rgba(148,163,184,0.08);border:1px solid rgba(148,163,184,0.2);border-radius:12px;padding:12px 16px;flex:1;min-width:140px">'
            '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Brüt Mal Bedeli</div>'
            f'<div style="font-size:15px;font-weight:700;color:#CBD5E1;font-family:\'JetBrains Mono\',monospace">{_tam(h["mal_bedeli"])} {doviz}</div></div>'
            '<div style="background:rgba(251,146,60,0.10);border:1px solid rgba(251,146,60,0.25);border-radius:12px;padding:12px 16px;flex:1;min-width:130px">'
            '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Fatura Altı İndirim</div>'
            f'<div style="font-size:15px;font-weight:700;color:#FB923C;font-family:\'JetBrains Mono\',monospace">−{_tam(_ind)} {doviz}</div></div>'
            '<div style="background:rgba(52,211,153,0.10);border:1px solid rgba(52,211,153,0.28);border-radius:12px;padding:12px 16px;flex:1;min-width:140px">'
            '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Net Mal Bedeli (FOB)</div>'
            f'<div style="font-size:19px;font-weight:800;color:#34D399;font-family:\'JetBrains Mono\',monospace">{_tam(_net)} {doviz}</div></div>'
        )
    else:
        _mb_html = (
            '<div style="background:rgba(99,102,241,0.10);border:1px solid rgba(99,102,241,0.25);border-radius:12px;padding:12px 16px;flex:1;min-width:150px">'
            '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Mal Bedeli (FOB)</div>'
            f'<div style="font-size:19px;font-weight:700;color:#E2E8F0;font-family:\'JetBrains Mono\',monospace">{_tam(h["mal_bedeli"])} {doviz}</div></div>'
        )
    st.markdown(
        '<div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 12px">'
        + _mb_html +
        '<div style="background:rgba(251,146,60,0.10);border:1px solid rgba(251,146,60,0.25);border-radius:12px;padding:12px 16px;flex:1;min-width:140px">'
        '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Toplam Masraf</div>'
        f'<div style="font-size:19px;font-weight:700;color:#FB923C;font-family:\'JetBrains Mono\',monospace">{_tam(h["toplam_masraf"])} {doviz}</div></div>'
        '<div style="background:rgba(74,222,128,0.10);border:1px solid rgba(74,222,128,0.25);border-radius:12px;padding:12px 16px;flex:1;min-width:140px">'
        '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Binen % Maliyet</div>'
        f'<div style="font-size:19px;font-weight:700;color:#4ADE80;font-family:\'JetBrains Mono\',monospace">%{h["maliyet_yuzde"]:.2f}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# SAYFA 1 — Geçmiş İthalatlar
# ─────────────────────────────────────────────────────────────────────
def _gecmis_ithalatlar():
    _baslik("📋", "Geçmiş İthalatlar", "Dosya başı toplam masraf ve FOB üzerine binen % maliyet")
    dosyalar = get_dosyalar()

    # ── ⚠️ Deposu seçilmemiş 'Teslim Alındı' dosyaları — hızlı depo atama ──
    _depo_eksik = [d for d in (dosyalar or [])
                   if str(d.get("durum", "") or "").strip() == "Teslim Alındı"
                   and not str(d.get("teslim_deposu", "") or "").strip()]
    if _depo_eksik:
        @st.dialog(f"⚠️ Deposu seçilmemiş 'Teslim Alındı' dosyaları ({len(_depo_eksik)}) — depo ata", width="large")
        def _dlg_depo_ata():
            st.caption("Bu dosyalar **Teslim Alındı** ama teslim deposu boş. Aşağıdan seç, depoyu ata.")
            st.dataframe(pd.DataFrame([{
                "Belge No": d.get("dosya_no", ""), "Tarih": str(d.get("tarih", ""))[:10],
                "Tedarikçi": d.get("tedarikci", ""), "Teslim Tarihi": str(d.get("teslim_tarihi", "") or "")[:10],
            } for d in _depo_eksik]), hide_index=True, use_container_width=True,
                height=min(38 + 35 * len(_depo_eksik), 240))
            _de1, _de2, _de3 = st.columns([2, 1.4, 1])
            _de_sec = _de1.multiselect(
                "Dosya(lar)", _depo_eksik,
                format_func=lambda d: f"{d.get('dosya_no','')} · {d.get('tedarikci','')}",
                default=_depo_eksik, key="ith_depoeksik_sec")
            _de_depo = _de2.selectbox("Atanacak depo", DEPO_SECENEKLER, key="ith_depoeksik_depo")
            _de3.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
            _de_depo_val = "" if str(_de_depo).startswith("(") else _de_depo
            if _de3.button("📦 Depoyu Ata", type="primary", use_container_width=True,
                           key="ith_depoeksik_btn", disabled=(not _de_sec or not _de_depo_val)):
                _de_ok = 0
                for _d in _de_sec:
                    if set_dosya_teslim(_d["id"], teslim_deposu=_de_depo_val):
                        _de_ok += 1
                st.cache_data.clear()
                st.success(f"✅ {_de_ok} dosyaya '{_de_depo_val}' teslim deposu atandı.")
                st.rerun()
        if st.button(f"⚠️ Deposu seçilmemiş 'Teslim Alındı' dosyaları ({len(_depo_eksik)}) — depo ata", key="btn_ith_depoata", use_container_width=True):
            _dlg_depo_ata()
    if not dosyalar:
        st.info("Henüz ithalat kaydı yok. '➕ Yeni İthalat' sayfasından ekleyebilirsin.")
        return

    katalog = get_urun_katalog()
    # Performans: tüm kalemleri TEK sorguda çek, bellekte dosyaya göre grupla (N+1 sorgu önlenir)
    _kalem_by_dosya = {}
    for _k in get_tum_kalemler():
        _kalem_by_dosya.setdefault(_k.get("dosya_id"), []).append(_k)
    hesap_map = {}
    satirlar = []
    for d in dosyalar:
        kal = _kalem_by_dosya.get(d["id"], [])
        h = dosya_hesapla(d, kal)
        hesap_map[d["id"]] = (d, kal, h)
        satirlar.append({
            "Belge No": d.get("pi_no", "") or d.get("dosya_no", "") or "",
            "Takip No": d.get("ithalat_takip_no", "") or "",
            "SAS No": d.get("sas_no", "") or "",
            "Tarih": str(d.get("tarih", ""))[:10],
            "Teslim Tarihi": str(d.get("teslim_tarihi", "") or "")[:10],
            "Tedarikçi": d.get("tedarikci", ""),
            "Ülke": d.get("mense_ulke", ""),
            "Döviz": d.get("doviz", ""),
            "Mal Bedeli": h["net_mal_bedeli"],
            "Toplam Masraf": h["toplam_masraf"],
            "% Maliyet": h["maliyet_yuzde"],
            "Kalem": h["kalem_sayisi"],
            "Aşama": d.get("durum", "") or "—",
            "Teslim Şekli": d.get("teslim_sekli", "") or "—",
            "Teslim Deposu": ((d.get("teslim_deposu", "") or "").strip()
                              or ("⚠️ SEÇİLMEDİ" if str(d.get("durum", "") or "").strip() == "Teslim Alındı" else "—")),
            "Durum": "✅ Tamam" if h["toplam_masraf"] > 0 else "⏳ Bekliyor",
            "_skus": " ".join(str(k.get("sku", "") or "") for k in kal).lower(),
        })

    toplam_mal = sum(s["Mal Bedeli"] for s in satirlar)
    toplam_masraf = sum(s["Toplam Masraf"] for s in satirlar)
    ort_yuzde = (toplam_masraf / toplam_mal * 100) if toplam_mal > 0 else 0
    _metrik_satiri([
        {"label": "Dosya Sayısı", "value": f"{len(dosyalar):,}", "renk": "#818CF8"},
        {"label": "Toplam Mal Bedeli", "value": f"${_tam(toplam_mal)}", "renk": "#34D399"},
        {"label": "Toplam Masraf", "value": f"${_tam(toplam_masraf)}", "renk": "#FB923C"},
        {"label": "Ort. % Maliyet", "value": f"%{ort_yuzde:.2f}", "renk": "#A78BFA"},
    ])

    # ── 🧹 Mükerrer Belge Temizliği (Belge No + Tarih + Tutar birebir aynı) ──
    def _eklenme_anahtari(_d):
        """En yeni eklenen kaydı belirlemek için sıralama anahtarı (created_at varsa onu, yoksa id)."""
        for _c in ("created_at", "inserted_at", "olusturma_tarihi", "created"):
            if _d.get(_c):
                return (2, str(_d.get(_c)))
        _id = _d.get("id")
        try:
            return (1, float(_id))
        except Exception:
            return (0, str(_id))

    _dup_gruplari = {}
    for _d in dosyalar:
        _dd, _kk, _hh = hesap_map[_d["id"]]
        _bno = (str(_dd.get("pi_no", "") or "").strip() or str(_dd.get("dosya_no", "") or "").strip())
        if not _bno:
            continue
        _tar = str(_dd.get("tarih", "") or "")[:10]
        _tutar = round(_hh["mal_bedeli"], 2)
        _dup_gruplari.setdefault((_bno, _tar, _tutar), []).append(_d)
    _mukerrer = {k: v for k, v in _dup_gruplari.items() if len(v) >= 2}
    if _mukerrer:
        _toplam_silinecek = sum(len(v) - 1 for v in _mukerrer.values())
        @st.dialog(f"🧹 Mükerrer Belge Temizliği — {len(_mukerrer)} grup · {_toplam_silinecek} fazla kayıt", width="large")
        def _dlg_mukerrer():
            st.caption("**Belge No + Tarih + Mal Bedeli** birebir aynı olan kayıtlar mükerrer sayılır. "
                       "Her gruptan **en son eklenen** tutulur, diğerleri silinir. "
                       "Aşağıda hangisinin tutulacağını gör, onayla, sonra temizle.")
            _rows_dup, _silinecek_ids = [], []
            for (_bno, _tar, _tutar), _grp in sorted(_mukerrer.items(), key=lambda x: x[0][0]):
                _grp_sirali = sorted(_grp, key=_eklenme_anahtari, reverse=True)  # en yeni başta
                for _idx, _gd in enumerate(_grp_sirali):
                    _dd, _kk, _hh = hesap_map[_gd["id"]]
                    _kalan = (_idx == 0)
                    if not _kalan:
                        _silinecek_ids.append(_gd["id"])
                    _rows_dup.append({
                        "Belge No": _bno, "Tarih": gun_ay_yil(_tar) or "—",
                        "Mal Bedeli": f"${_tam(_hh['mal_bedeli'])}",
                        "Kalem": _hh["kalem_sayisi"],
                        "Masraf": f"${_tam(_hh['toplam_masraf'])}",
                        "Takip No": _dd.get("ithalat_takip_no", "") or "—",
                        "Aşama": _dd.get("durum", "") or "—",
                        "Kayıt": "✅ TUTULACAK" if _kalan else "🗑️ silinecek",
                    })
            st.dataframe(pd.DataFrame(_rows_dup), use_container_width=True,
                         height=min(440, 70 + len(_rows_dup) * 36), hide_index=True)
            _onay = st.checkbox(f"{_toplam_silinecek} fazla kaydı kalıcı olarak silmeyi onaylıyorum",
                                key="ith_dup_onay")
            if st.button(f"🧹 Mükerrerleri Temizle ({_toplam_silinecek} kayıt sil)",
                         type="primary", disabled=not _onay, use_container_width=True, key="ith_dup_temizle"):
                _n = 0
                with st.spinner("🧹 Temizleniyor..."):
                    for _iid in _silinecek_ids:
                        if sil_dosya(_iid):
                            _n += 1
                st.success(f"✅ {_n} mükerrer kayıt silindi.")
                st.rerun()
        if st.button(f"🧹 Mükerrer Belge Temizliği — {len(_mukerrer)} grup · {_toplam_silinecek} fazla kayıt", key="btn_ith_muker", use_container_width=True):
            _dlg_mukerrer()

    # 🔍 Filtreler (başlık bazlı) + arama
    _tedarikciler = sorted({s["Tedarikçi"] for s in satirlar if s["Tedarikçi"]})
    _fc1, _fc2, _fc3, _fc4 = st.columns(4)
    f_ted = _fc1.selectbox("Tedarikçi", ["Tümü"] + _tedarikciler, key="ith_f_ted")
    f_durum = _fc2.selectbox("Aşama / Durum", ["Tümü"] + DURUM_SECENEKLER, key="ith_f_durum")
    f_takip = _fc3.text_input("Takip No", key="ith_f_takip",
                              placeholder="takip no yaz...").strip().lower()
    f_sku = _fc4.text_input("SKU Ara", key="ith_f_sku",
                            placeholder="SKU yaz...").strip().lower()
    _ara = st.text_input("🔍 Ara — Belge No · Takip No · SAS No · Tedarikçi", key="ith_gecmis_ara",
                         placeholder="örn. PIFAZ, SAS-1, 2025-16, LCCGAME...").strip().lower()

    def _gecer(s):
        if _ara and _ara not in (str(s.get("Belge No", "")) + " " +
                                 str(s.get("Takip No", "")) + " " + str(s.get("SAS No", "")) + " " +
                                 str(s.get("Tedarikçi", ""))).lower():
            return False
        if f_ted != "Tümü" and s.get("Tedarikçi", "") != f_ted:
            return False
        if f_durum != "Tümü" and (s.get("Aşama", "") or "—") != f_durum:
            return False
        if f_takip and f_takip not in str(s.get("Takip No", "") or "").lower():
            return False
        if f_sku and f_sku not in s.get("_skus", ""):
            return False
        return True

    _pairs = [(d, s) for d, s in zip(dosyalar, satirlar) if _gecer(s)]
    dosyalar_goster = [d for d, s in _pairs]
    satirlar_goster = [s for d, s in _pairs]
    st.caption(f"{len(satirlar_goster)} / {len(dosyalar)} dosya gösteriliyor")

    if not satirlar_goster:
        st.info("Aramayla eşleşen dosya yok.")
        return

    # ── Sıralama + tıklanabilir tablo (satıra tıkla → detay) ──
    _sort = st.selectbox("Sırala", [
        "Sipariş Tarihi (yeni → eski)", "Sipariş Tarihi (eski → yeni)",
        "Teslim Tarihi (yeni → eski)", "Teslim Tarihi (eski → yeni)",
        "Mal Bedeli (çok → az)",
        "Toplam Masraf (çok → az)", "% Maliyet (çok → az)", "Tedarikçi (A → Z)", "Belge No (A → Z)",
    ], key="ith_sort")
    _sk = {
        "Sipariş Tarihi (yeni → eski)": (lambda p: p[1]["Tarih"], True),
        "Sipariş Tarihi (eski → yeni)": (lambda p: p[1]["Tarih"], False),
        "Teslim Tarihi (yeni → eski)":  (lambda p: p[1]["Teslim Tarihi"] or "", True),
        "Teslim Tarihi (eski → yeni)":  (lambda p: p[1]["Teslim Tarihi"] or "", False),
        "Mal Bedeli (çok → az)":   (lambda p: p[1]["Mal Bedeli"], True),
        "Toplam Masraf (çok → az)": (lambda p: p[1]["Toplam Masraf"], True),
        "% Maliyet (çok → az)":    (lambda p: p[1]["% Maliyet"], True),
        "Tedarikçi (A → Z)":       (lambda p: (p[1]["Tedarikçi"] or "").lower(), False),
        "Belge No (A → Z)":        (lambda p: (p[1]["Belge No"] or "").lower(), False),
    }[_sort]
    _pairs_sorted = sorted(_pairs, key=_sk[0], reverse=_sk[1])
    dosyalar_goster = [d for d, s in _pairs_sorted]
    satirlar_goster = [s for d, s in _pairs_sorted]

    _df_show = pd.DataFrame([{
        "Belge No": s["Belge No"], "Takip No": s["Takip No"] or "—",
        "SAS No": s["SAS No"] or "—",
        "Sipariş Tarihi": gun_ay_yil(s["Tarih"]), "Teslim Tarihi": gun_ay_yil(s["Teslim Tarihi"]) or "—",
        "Tedarikçi": s["Tedarikçi"], "Döviz": s["Döviz"] or "USD",
        "Mal Bedeli": f"${_tam(s['Mal Bedeli'])}", "Masraf": f"${_tam(s['Toplam Masraf'])}",
        "% Maliyet": f"%{s['% Maliyet']:.2f}", "Kalem": s["Kalem"],
        "Aşama": s["Aşama"],
        "Teslim Şekli": s.get("Teslim Şekli", "—"),
        "Teslim Deposu": s.get("Teslim Deposu", "—"),
        "Durum": s["Durum"],
    } for s in satirlar_goster])
    _evt = st.dataframe(
        _df_show, hide_index=True, height=420,
        on_select="rerun", selection_mode="multi-row", key="ith_gecmis_df",
    )
    st.caption("👆 **1 satır** seç → detay/masraf/düzenleme **penceresi** açılır.  ·  **2+ satır** seç (kutucuklarla) "
               "→ seçilenlere **ortak masraf** girip FOB payına göre dağıtabilirsin.  ·  Sütun başlığından sıralayabilirsin.")

    try:
        _sel = list(_evt.selection.rows)
    except Exception:
        _sel = []
    # Güvenlik: liste değiştiyse (silme/filtre/dağıtım sonrası) eski seçim indeksleri
    # mevcut listenin dışına taşabilir → IndexError'ı önlemek için geçerli aralığa filtrele.
    _sel = [i for i in _sel if isinstance(i, int) and 0 <= i < len(dosyalar_goster)]
    if not _sel:
        st.info("Yukarıdaki tablodan dosya seç. **1 satır** → detay & düzenleme · **2+ satır** → ortak masraf dağıt.")
        return

    # ── 2+ satır seçili → ORTAK MASRAF (FOB payına göre dağıt) ──
    if len(_sel) >= 2:
        _sec_dosyalar = [dosyalar_goster[i] for i in _sel]

        # ── Toplu aşama: seçilenleri 'Teslim Alındı' yap (teslim tarihine dokunmaz) ──
        _bekleyen_teslim = [d for d in _sec_dosyalar
                            if str(d.get("durum", "") or "").strip() != "Teslim Alındı"]
        st.caption(f"📦 Seçili {len(_sec_dosyalar)} belgeden **{len(_bekleyen_teslim)}** tanesi henüz "
                   "'Teslim Alındı' değil. Yalnızca aşama güncellenir; teslim tarihine dokunulmaz. "
                   "**Teslim deposu seçimi zorunludur** — deposuz hiçbir dosya 'Teslim Alındı' yapılamaz.")
        _tc1, _tc2 = st.columns([2, 1])
        _toplu_depo = _tc1.selectbox("Teslim deposu (seçili belgelerin hepsine) *", DEPO_SECENEKLER,
                                     key="ith_toplu_depo")
        _tc2.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        _toplu_depo_val = "" if str(_toplu_depo).startswith("(") else _toplu_depo
        if _tc2.button("📦 Teslim Alındı yap", use_container_width=True, key="ith_toplu_teslim",
                       disabled=(len(_bekleyen_teslim) == 0 or not _toplu_depo_val)):
            _ts_ok = 0
            _depo_sec = _toplu_depo_val
            for _d in _bekleyen_teslim:
                if set_dosya_durum(_d["id"], "Teslim Alındı"):
                    _ts_ok += 1
                    if _depo_sec:
                        set_dosya_teslim(_d["id"], teslim_deposu=_depo_sec)
            st.cache_data.clear()
            _msg = f"✅ {_ts_ok} belge 'Teslim Alındı' olarak işaretlendi."
            if _depo_sec:
                _msg += f" Teslim deposu: {_depo_sec}."
            st.success(_msg)
            st.rerun()

        # ── Toplu İthalat Takip No ata (seçili belgelerin hepsine) ──
        _mevcut_takipler = sorted({str(_d.get("ithalat_takip_no", "") or "").strip()
                                   for _d in _sec_dosyalar if str(_d.get("ithalat_takip_no", "") or "").strip()})
        _takip_durum = ("Mevcut: " + ", ".join(_mevcut_takipler)) if _mevcut_takipler else "Seçili belgelerde takip no yok."
        st.caption(f"🔗 Seçili {len(_sec_dosyalar)} belgeye ortak **İthalat Takip No** ata (hepsine birden yazılır). {_takip_durum}")
        _kc1, _kc2 = st.columns([2, 1])
        _onceki_takip = _mevcut_takipler[0] if len(_mevcut_takipler) == 1 else ""
        _toplu_takip = _kc1.text_input("İthalat Takip No (seçili belgelerin hepsine)",
                                       value=_onceki_takip, key="ith_toplu_takip",
                                       placeholder="örn. 2025-26")
        _kc2.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if _kc2.button("🔗 Takip No Ata", use_container_width=True, key="ith_toplu_takip_btn"):
            _tk_ok = 0
            for _d in _sec_dosyalar:
                if set_dosya_takip_no(_d["id"], _toplu_takip.strip()):
                    _tk_ok += 1
            st.cache_data.clear()
            if _toplu_takip.strip():
                st.success(f"✅ {_tk_ok} belgeye '{_toplu_takip.strip()}' takip no'su atandı.")
            else:
                st.success(f"✅ {_tk_ok} belgenin takip no'su temizlendi.")
            st.rerun()
        st.markdown("---")

        # Seçili belge id'lerinden imza — masraf kutularının anahtarını seçime bağlar
        # (farklı ithalat/takip seçilince kutular sıfırdan, 0 olarak gelir).
        _sec_sig = "_".join(str(x) for x in sorted(_sd["id"] for _sd in _sec_dosyalar))
        _sec_bilgi, _sec_toplam_fob = [], 0.0
        for _sd in _sec_dosyalar:
            # NET mal bedeli (fatura altı indirim düşülmüş) — tek dosya / liste görünümüyle tutarlı.
            # Aksi halde birden çok belge seçilince indirim devre dışı kalır.
            _hh = hesap_map.get(_sd["id"])
            if _hh:
                _mb = float(_hh[2].get("net_mal_bedeli", 0.0) or 0.0)
            else:
                _skal = _kalem_by_dosya.get(_sd["id"], [])
                _mb = sum(float(_k.get("adet", 0) or 0) * float(_k.get("birim_fob", 0) or 0) for _k in _skal)
            _sec_toplam_fob += _mb
            _sec_bilgi.append((_sd, _mb))
        _dv0 = (_sec_dosyalar[0].get("doviz", "USD") or "USD") if _sec_dosyalar else "USD"
        _dovizler_sec = {str(_sd.get("doviz", "USD") or "USD") for _sd in _sec_dosyalar}
        _takipler_sec = {str(_sd.get("ithalat_takip_no", "") or "").strip() for _sd in _sec_dosyalar if str(_sd.get("ithalat_takip_no", "") or "").strip()}

        _alt_baslik(f"🧾 Ortak Masraf — {len(_sec_dosyalar)} belge seçili (tek ithalat gibi)")
        # Birleşik mevcut masraf + birleşik % (o ithalatın tek oranı)
        _sec_mevcut_masraf = 0.0
        for _sd in _sec_dosyalar:
            _sec_mevcut_masraf += sum(float(_v or 0) for _v in _masraf_dict(_sd).values())
        _birlesik_yuzde = (_sec_mevcut_masraf / _sec_toplam_fob * 100) if _sec_toplam_fob > 0 else 0.0
        _metrik_satiri([
            {"label": "Birleşik Mal Bedeli (FOB)", "value": f"{_tam(_sec_toplam_fob)} {_dv0}", "renk": "#34D399"},
            {"label": "Birleşik Masraf", "value": f"{_tam(_sec_mevcut_masraf)} {_dv0}", "renk": "#FB923C"},
            {"label": "⭐ Birleşik % Maliyet", "value": f"%{_birlesik_yuzde:.2f}", "renk": "#FCD34D",
             "help": "Seçili tüm belgelerin TOPLAM masrafı / TOPLAM mal bedeli — o ithalatın tek ortalama oranı."},
            {"label": "Belge Sayısı", "value": f"{len(_sec_dosyalar)}", "renk": "#818CF8"},
        ])
        if _takipler_sec:
            st.caption("🔗 Takip No: " + ", ".join(sorted(_takipler_sec)))
        if len(_dovizler_sec) > 1:
            st.warning(f"⚠️ Seçili belgelerde farklı para birimleri var ({', '.join(sorted(_dovizler_sec))}). "
                       "Ortak masraf tek para biriminde girilmeli — dağıtım döviz farkı gözetmez.")
        _pay_html = "<div style='font-size:13px;color:#94A3B8;margin:0 0 8px;line-height:1.7'>"
        for _sd, _mb in _sec_bilgi:
            _pay = (_mb / _sec_toplam_fob * 100) if _sec_toplam_fob > 0 else (100.0 / max(len(_sec_bilgi), 1))
            _doc_masraf = sum(float(_v or 0) for _v in _masraf_dict(_sd).values())
            _doc_yuzde = (_doc_masraf / _mb * 100) if _mb > 0 else 0.0
            _bno = _sd.get("pi_no", "") or _sd.get("dosya_no", "") or "—"
            _pay_html += (f"• <b style='color:#E2E8F0'>{_bno}</b> — {_tam(_mb)} {_dv0} "
                          f"<span style='color:#A78BFA'>(FOB pay %{_pay:.1f})</span> "
                          f"<span style='color:#94A3B8'>· şu anki % {_doc_yuzde:.2f}</span><br>")
        _pay_html += "</div>"
        st.markdown(_pay_html, unsafe_allow_html=True)

        # Masraf dengesiz mi? (biri dolu/biri boş veya %'ler farklı) → tek tıkla FOB payına göre dağıt
        _doc_yuzdeler = []
        for _sd, _mb in _sec_bilgi:
            _dm = sum(float(_v or 0) for _v in _masraf_dict(_sd).values())
            _doc_yuzdeler.append((_dm / _mb * 100) if _mb > 0 else 0.0)
        _bos_belge_var = any(abs(_y) < 0.001 for _y in _doc_yuzdeler)
        _dengesiz = (max(_doc_yuzdeler) - min(_doc_yuzdeler) > 0.1) if _doc_yuzdeler else False
        if _sec_mevcut_masraf > 0 and (_bos_belge_var or _dengesiz):
            st.markdown(
                f'<div style="background:rgba(251,146,60,0.10);border:1px solid rgba(251,146,60,0.32);'
                f'border-radius:10px;padding:8px 16px;margin:0 0 8px;font-size:13px;color:#FDBA74">'
                f'⚠️ Masraf belgelere eşit dağılmamış — bazı belgeler boş/%0. '
                f'Aşağıdaki düğmeyle takibin <b>tüm masrafını</b> ({_tam(_sec_mevcut_masraf)} {_dv0}) '
                f'belgelere <b>FOB payına göre</b> dağıtabilirsin: hepsi <b>%{_birlesik_yuzde:.2f}</b> olur, '
                f'boş belgeler dolar ve hepsi <b>"Tamam"</b> görünür.</div>',
                unsafe_allow_html=True)
            if st.button("🔄 Takibin masrafını tüm belgelere FOB payına göre dağıt (boş belgeler dolsun)",
                         use_container_width=True, key="ith_takip_dagit"):
                _combined = {}
                for _sd in _sec_dosyalar:
                    for _slug, _v in _masraf_dict(_sd).items():
                        _combined[_slug] = _combined.get(_slug, 0.0) + float(_v or 0)
                with st.spinner("🔄 Dağıtılıyor..."):
                    _ok_t, _msg_t = dagit_ortak_masraf([s["id"] for s in _sec_dosyalar], _combined)
                if _ok_t:
                    for _slug, _ in MASRAF_TANIM:
                        st.session_state.pop(f"ith_ortak_mas_{_sec_sig}_{_slug}", None)
                    st.success(f"✅ Masraf {len(_sec_dosyalar)} belgeye dağıtıldı — hepsi %{_birlesik_yuzde:.2f}.")
                    st.rerun()
                else:
                    st.error(_msg_t)
            st.divider()

        # Seçili belgelerin MEVCUT masraf toplamı (slug bazında) — kutular bununla DOLU gelir
        _sec_mevcut_kalem = {}
        for _sd in _sec_dosyalar:
            for _slug, _v in _masraf_dict(_sd).items():
                _sec_mevcut_kalem[_slug] = _sec_mevcut_kalem.get(_slug, 0.0) + float(_v or 0)

        _kur_varsayilan = float(_sec_dosyalar[0].get("kur", 1) or 1) if _sec_dosyalar else 1.0
        _kurlar_sec = {round(float(_sd.get("kur", 1) or 1), 5) for _sd in _sec_dosyalar}

        st.markdown("**Ortak masraf — seçili belgelerin toplamı.** Dolu kutular mevcut masrafı gösterir; "
                    "boş kutuya **tıklayıp doğrudan yazabilirsin** (0,00 silmene gerek yok).")

        _ana_sol, _ana_sag = st.columns([2.05, 1])
        with _ana_sol:
            _ortak = {}
            for _slug, _label in MASRAF_TANIM:
                _lc, _ic = st.columns([1, 1.15])
                _lc.markdown(
                    f'<div style="padding-top:8px;font-size:13px;color:#CBD5E1;font-weight:600;'
                    f'text-align:right;padding-right:8px">{_label}</div>', unsafe_allow_html=True)
                _mevcut_v = float(_sec_mevcut_kalem.get(_slug, 0.0) or 0)
                _ok2 = f"ith_ortak_mas_{_sec_sig}_{_slug}"
                st.session_state.setdefault(_ok2, (_mevcut_v if _mevcut_v > 0 else None))
                _ortak[_slug] = _ic.number_input(
                    _label, min_value=0.0, value=None,
                    step=1.0, format="%.2f", placeholder="0,00",
                    label_visibility="collapsed", key=_ok2)
            _girilen = {k: v for k, v in _ortak.items() if v and v > 0}

        with _ana_sag:
            _ortak_kur = st.number_input("Kur (1 döviz = ? TL)", min_value=0.0,
                                         value=_kur_varsayilan, step=0.00001, format="%.5f",
                                         key=f"ith_ortak_kur_{_sec_sig}")
            _toplam_girilen = sum(_girilen.values())
            # Dağıtım sonrası birleşik % (girilen slug'lar üzerine yazılır, diğerleri korunur)
            _korunan = sum(float(_v or 0) for _sd in _sec_dosyalar
                           for _s2, _v in _masraf_dict(_sd).items() if _s2 not in _girilen)
            _proj_masraf = _korunan + _toplam_girilen
            _proj_yuzde = (_proj_masraf / _sec_toplam_fob * 100) if _sec_toplam_fob > 0 else 0.0
            st.markdown(
                '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(148,163,184,0.2);'
                'border-radius:12px;padding:12px 16px;margin-top:8px;line-height:1.5">'
                '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Birleşik Mal Bedeli</div>'
                f'<div style="font-size:15px;font-weight:700;color:#34D399;font-family:monospace;margin-bottom:8px">{_tam(_sec_toplam_fob)} {_dv0}</div>'
                '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Toplam Girilen Masraf</div>'
                f'<div style="font-size:15px;font-weight:700;color:#FB923C;font-family:monospace;margin-bottom:8px">{_tam(_toplam_girilen)} {_dv0}</div>'
                '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Dağıtım Sonrası % Maliyet</div>'
                f'<div style="font-size:19px;font-weight:800;color:#FCD34D;font-family:monospace">%{_proj_yuzde:.2f}</div>'
                '</div>', unsafe_allow_html=True)
            if len(_kurlar_sec) > 1:
                st.caption("⚠️ Seçili belgelerin kuru farklı; kaydedince hepsine yukarıdaki kur yazılır.")
        st.caption("ℹ️ **Kaydet**, girilen masrafları seçili belgelere FOB payına göre **kuruş-doğru** yazar ve **kuru** kaydeder. "
                   "Dolu bir kalemi **boşaltıp Kaydet** → o masraf seçili belgelerin **hepsinden silinir**. "
                   "**Tek bir belgenin masrafını birebir düzenlemek** için o belgeyi **tek başına seç**.")
        if st.button("💾 Kaydet (masraf FOB payına göre + kur)", type="primary",
                     use_container_width=True, key="ith_ortak_dagit_tablo"):
            _ids = [_sd["id"] for _sd in _sec_dosyalar]
            # SİLME SİNYALİ: daha önce değeri olan bir kalem boşaltıldıysa
            # (kutu None/0), o kalem seçili TÜM belgelerden silinir.
            _silinen = [_slug for _slug, _ in MASRAF_TANIM
                        if not _ortak.get(_slug)
                        and float(_sec_mevcut_kalem.get(_slug, 0) or 0) > 0]
            with st.spinner("💾 Kaydediliyor..."):
                _ok_d, _msg_d = dagit_ortak_masraf(_ids, _girilen, kur=_ortak_kur,
                                                   sil=_silinen)
            if _ok_d:
                # Kutuları DB'den tazele (kaydedilen yeni değerler dolu gelsin)
                for _slug, _ in MASRAF_TANIM:
                    st.session_state.pop(f"ith_ortak_mas_{_sec_sig}_{_slug}", None)
                st.session_state.pop(f"ith_ortak_kur_{_sec_sig}", None)
                st.success(_msg_d)
                st.rerun()
            else:
                st.error(_msg_d)
        return

    # ── Tek satır seçili → detay & düzenleme (AÇILIR PENCERE) ──
    @st.dialog("📋 İthalat Dosyası — Detay · Masraf · Düzenle", width="large")
    def _dlg_dosya_detay():
        did = dosyalar_goster[_sel[0]]["id"]
        d, kal, h = hesap_map[did]

        st.markdown(f'<div style="color:#94A3B8;font-size:13px;margin-bottom:8px">Belge No: <b style="color:#E2E8F0">{d.get("pi_no","") or d.get("dosya_no","") or "—"}</b> · Takip No: <b style="color:#E2E8F0">{d.get("ithalat_takip_no","") or "—"}</b> · {d.get("tedarikci","")}{(" · Aşama: <b style=" + chr(34) + "color:#38BDF8" + chr(34) + ">" + str(d.get("durum","")) + "</b>") if d.get("durum") else ""}{(" · Tahmini Varış: <b style=" + chr(34) + "color:#A78BFA" + chr(34) + ">" + gun_ay_yil(d.get("tahmini_varis")) + "</b>") if (str(d.get("durum","")).strip() in IN_TRANSIT_DURUMLAR and d.get("tahmini_varis")) else ""}</div>', unsafe_allow_html=True)
        _sip_t = gun_ay_yil(d.get("tarih")) or "—"
        _tes_t = gun_ay_yil(d.get("teslim_tarihi"))
        _tes_d = str(d.get("teslim_deposu", "") or "")
        st.markdown(
            f'<div style="color:#94A3B8;font-size:13px;margin-bottom:8px">'
            f'🗓️ Sipariş Tarihi: <b style="color:#E2E8F0">{_sip_t}</b>'
            + (f' · 📦 Teslim Tarihi: <b style="color:#34D399">{_tes_t}</b>' if _tes_t else ' · 📦 Teslim Tarihi: <b style="color:#64748B">—</b>')
            + (f' · 🏬 Teslim Deposu: <b style="color:#E2E8F0">{_tes_d}</b>' if _tes_d else '')
            + (f' · 🚢 Teslim Şekli: <b style="color:#E2E8F0">{str(d.get("teslim_sekli","") or "")}</b>' if d.get("teslim_sekli") else '')
            + '</div>', unsafe_allow_html=True)
        _dr_txt = "✅ Masraf girildi — maliyet hesaplandı" if h["toplam_masraf"] > 0 else "⏳ Masraf bekliyor — aşağıdan ✏️ Düzenle ile gir"
        _dr_renk = "#4ADE80" if h["toplam_masraf"] > 0 else "#FB923C"
        st.markdown(f'<div style="display:inline-block;background:rgba(255,255,255,0.04);border:1px solid {_dr_renk}55;border-radius:8px;padding:8px 12px;margin:0px 0 12px;color:{_dr_renk};font-size:13px;font-weight:700">{_dr_txt}</div>', unsafe_allow_html=True)

        # ── ÇOKLU ÜRÜN GRUBU: grup-bazlı maliyet kartları ──
        if dosya_coklu_mu(d, kal):
            _ck = dosya_hesapla_coklu(d, kal)
            _cur = str(d.get("doviz", "USD") or "USD")
            st.markdown(
                '<div style="color:#A78BFA;font-size:12px;font-weight:800;text-transform:uppercase;'
                'letter-spacing:0.8px;margin:6px 0 8px">🧩 Çoklu Ürün Grubu — Grup Bazlı Maliyet</div>',
                unsafe_allow_html=True)
            _gk = list(_ck["gruplar"].items())
            _cols = st.columns(min(len(_gk), 3)) if _gk else []
            for _i, (_gad, _gd) in enumerate(_gk):
                with _cols[_i % len(_cols)]:
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg,rgba(139,92,246,0.10),rgba(30,41,59,0.4));'
                        f'border:1px solid rgba(167,139,250,0.3);border-radius:14px;padding:12px 14px;margin-bottom:8px">'
                        f'<div style="font-size:14px;font-weight:800;color:#E9D5FF;margin-bottom:6px">{_gad}</div>'
                        f'<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px">Mal Bedeli (FOB)</div>'
                        f'<div style="font-size:14px;font-weight:700;color:#34D399;font-family:monospace;margin-bottom:5px">{_tam(_gd["fob"])} {_cur}</div>'
                        f'<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px">Ortak Pay · Özel</div>'
                        f'<div style="font-size:12px;font-weight:600;color:#CBD5E1;font-family:monospace;margin-bottom:5px">{_tam(_gd["ortak_pay"])} · {_tam(_gd["ozel_masraf"])}</div>'
                        f'<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px">Toplam Masraf</div>'
                        f'<div style="font-size:14px;font-weight:700;color:#FB923C;font-family:monospace;margin-bottom:5px">{_tam(_gd["toplam_masraf"])} {_cur}</div>'
                        f'<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px">Maliyet Yüzdesi</div>'
                        f'<div style="font-size:18px;font-weight:800;color:#FCD34D;font-family:monospace">%{_gd["yuzde"]:.2f}</div>'
                        f'<div style="font-size:10px;color:#64748B;margin-top:4px">{int(_gd["adet"])} adet · birim +maliyet ×{1+_gd["birim_ek_maliyet_orani"]:.4f}</div>'
                        f'</div>', unsafe_allow_html=True)
            st.caption("ℹ️ Ortak masraflar gruplara **FOB payına göre** dağıtıldı · özel masraflar "
                       "elle atandıkları gruba yazıldı. Atamaları **✏️ Düzenle** bölümünden değiştirebilirsin.")


        # ── Yanlış / boş açılan ithalatı sil (onaylı) ──
        _sok = f"ith_sil_onay_{did}"
        _scc1, _scc2 = st.columns([3, 1])
        with _scc2:
            if st.button("🗑️ Bu ithalatı sil", key=f"ith_sil_{did}", use_container_width=True):
                st.session_state[_sok] = True
        if st.session_state.get(_sok):
            _ad_g = d.get("dosya_no", "") or d.get("pi_no", "") or "—"
            st.warning(f"**{_ad_g}** ithalat dosyası ve tüm kalemleri kalıcı olarak silinecek. Emin misin?")
            _del1, _del2 = st.columns(2)
            if _del1.button("✅ Evet, sil", key=f"ith_sile_{did}", use_container_width=True, type="primary"):
                if sil_dosya(did):
                    st.session_state.pop(_sok, None)
                    st.cache_data.clear()
                    st.success("✅ İthalat silindi.")
                    st.rerun()
                else:
                    st.error("Silinemedi.")
            if _del2.button("Vazgeç", key=f"ith_silv_{did}", use_container_width=True):
                st.session_state.pop(_sok, None)
                st.rerun()

        # Bu belge bir takip no'ya aitse → o ithalatın (takibin) BİRLEŞİK % maliyetini üstte göster
        _bu_takip = str(d.get("ithalat_takip_no", "") or "").strip()
        if _bu_takip:
            _tk_dosyalar = [x for x in dosyalar if str(x.get("ithalat_takip_no", "") or "").strip() == _bu_takip]
            if len(_tk_dosyalar) >= 2:
                _tk_mal = sum(hesap_map[x["id"]][2]["net_mal_bedeli"] for x in _tk_dosyalar)
                _tk_mas = sum(hesap_map[x["id"]][2]["toplam_masraf"] for x in _tk_dosyalar)
                _tk_yuzde = (_tk_mas / _tk_mal * 100) if _tk_mal > 0 else 0.0
                st.markdown(
                    f'<div style="background:rgba(252,211,77,0.08);border:1px solid rgba(252,211,77,0.28);'
                    f'border-radius:10px;padding:8px 16px;margin:0 0 12px;font-size:13px;color:#FCD34D">'
                    f'🔗 Bu takip no\'ya (<b>{_bu_takip}</b>) ait <b>{len(_tk_dosyalar)}</b> belgenin '
                    f'<b>Birleşik % Maliyeti: %{_tk_yuzde:.2f}</b> '
                    f'<span style="color:#94A3B8">· toplam masraf {_tam(_tk_mas)} / toplam mal bedeli {_tam(_tk_mal)}</span></div>',
                    unsafe_allow_html=True)
        _masraf_karti(d, h)
        _dokum = masraf_dokumu(d)
        if _dokum:
            st.caption(
                "Masraf kalemleri → "
                + " · ".join(f"{ad}: {_tam(tutar)}" for ad, tutar in _dokum)
                + f" · Kur: {float(d.get('kur', 1) or 1):,.5f}"
            )
        else:
            st.caption(f"Masraf girilmemiş · Kur: {float(d.get('kur', 1) or 1):,.5f}")

        y = h["maliyet_yuzde"] / 100
        _ind_oran = (h.get("indirim", 0.0) / h["mal_bedeli"]) if h.get("mal_bedeli", 0) > 0 else 0.0
        krows = []
        for k in kal:
            adet = float(k.get("adet", 0) or 0)
            bf = float(k.get("birim_fob", 0) or 0) * (1 - _ind_oran)  # indirim sonrası NET birim FOB
            st_tutar = adet * bf
            krows.append({
                "SKU": k.get("sku", ""),
                "Ürün": (k.get("urun_adi", "") or katalog.get(k.get("sku", ""), "")),
                "Adet": adet,
                "Birim FOB": bf,
                "Satır Tutar": st_tutar,
                "Dağıtılan Masraf": st_tutar * y,
                "Final Birim Maliyet": bf * (1 + y),
                "% Maliyet": h["maliyet_yuzde"],
            })
        if _ind_oran > 0:
            st.caption(f"ℹ️ Fatura altı indirim (%{_ind_oran*100:.2f}) uygulandı — Birim FOB ve maliyetler **net** (indirimli) gösteriliyor.")
        _tablo(pd.DataFrame(krows),
               para=["Birim FOB", "Satır Tutar", "Dağıtılan Masraf", "Final Birim Maliyet"],
               yuzde=["% Maliyet"], sol=["SKU", "Ürün"], kisalt={"Ürün": 42})

        # ── Düzenle: masraf + ürün/adet/FOB (Aşama 2) — aynı pencere içinde açılır ──
        def _dosya_duzen_govde():
            # ── Bayat state koruması: bu dosya için düzenleme govdesi bu turda
            #    ilk kez çiziliyorsa, masraf/indirim widget anahtarlarını temizle
            #    ki number_input değerlerini DB'den (value=) taze alsın. Aksi halde
            #    önceki oturumdan kalan session_state, silinen değeri geri gösterir.
            _govde_guard = f"_ith_duzen_hazir_{did}"
            if not st.session_state.get(_govde_guard):
                for _sk in [k for k in list(st.session_state.keys())
                            if k == f"ith_edit_indirim_{did}"
                            or k.startswith(f"ith_edit_mas_{did}_")]:
                    st.session_state.pop(_sk, None)
                st.session_state[_govde_guard] = True
            # ── Masraf girişi CANLI (form DIŞI → yazdıkça sağdaki özet anında güncellenir) ──
            _alt_baslik("💸 Masraf Kalemleri · dosya para biriminde (canlı)")
            _md = _masraf_dict(d)
            _brut_mb = sum(float(k.get("adet", 0) or 0) * float(k.get("birim_fob", 0) or 0) for k in kal)
            _cur_dv = str(d.get("doviz", "USD") or "USD")
            _cs, _cr = st.columns([2.05, 1])
            with _cs:
                _ik = f"ith_edit_indirim_{did}"
                _iv0 = float(d.get("fatura_indirim", 0) or 0)
                # setdefault ön-yazma YOK (silinen değerin geri gelmesini önler)
                e_indirim = st.number_input(
                    "Fatura Altı İndirim (tutar)", min_value=0.0,
                    value=(_iv0 if _iv0 > 0 else None), step=1.0, format="%.2f",
                    key=_ik,
                    help="Net mal bedeli = Brüt − İndirim. SKU birim maliyetleri ve % maliyet bu indirime göre hesaplanır.")
                e_masraf = {}
                for _slug, _label in MASRAF_TANIM:
                    _lc, _ic = st.columns([1, 1.4])
                    _lc.markdown(
                        f'<div style="padding-top:8px;font-size:13px;color:#CBD5E1;font-weight:600;'
                        f'text-align:right;padding-right:8px">{_label}</div>', unsafe_allow_html=True)
                    _mv = float(_md.get(_slug, 0) or 0)
                    _mk = f"ith_edit_mas_{did}_{_slug}"
                    # NOT: session_state'e setdefault ile ÖN-YAZMA YAPILMAZ.
                    # Yapılırsa kullanıcı alanı silse bile eski değer session_state'te
                    # kalır ve number_input onu geri gösterir (kaydet→hâlâ eski değer bug'ı).
                    # value doğrudan verilir; kaydetme sonrası anahtar zaten temizleniyor.
                    e_masraf[_slug] = _ic.number_input(
                        _label, min_value=0.0,
                        value=(_mv if _mv > 0 else None),
                        step=1.0, format="%.2f", placeholder="0,00",
                        label_visibility="collapsed", key=_mk)
            with _cr:
                e_kur = st.number_input("Kur (1 döviz = ? TL)", min_value=0.0,
                                        value=float(d.get("kur", 1) or 1), step=0.00001, format="%.5f",
                                        key=f"ith_edit_kur_{did}")
                _ind_v = float(e_indirim or 0)
                _net_mb = max(_brut_mb - _ind_v, 0.0)
                _mas_v = sum(float(_v or 0) for _v in e_masraf.values())
                _yuzde_v = (_mas_v / _net_mb * 100) if _net_mb > 0 else 0.0
                _ind_row = (
                    '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Fatura İndirim</div>'
                    f'<div style="font-size:13px;font-weight:700;color:#FB923C;font-family:monospace;margin-bottom:8px">−{_tam(_ind_v)} {_cur_dv}</div>'
                ) if _ind_v > 0 else ""
                st.markdown(
                    '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(148,163,184,0.2);'
                    'border-radius:12px;padding:12px 16px;margin-top:8px;line-height:1.5">'
                    '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Net Mal Bedeli (FOB)</div>'
                    f'<div style="font-size:15px;font-weight:700;color:#34D399;font-family:monospace;margin-bottom:8px">{_tam(_net_mb)} {_cur_dv}</div>'
                    + _ind_row +
                    '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Toplam Girilen Masraf</div>'
                    f'<div style="font-size:15px;font-weight:700;color:#FB923C;font-family:monospace;margin-bottom:8px">{_tam(_mas_v)} {_cur_dv}</div>'
                    '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">% Maliyet</div>'
                    f'<div style="font-size:19px;font-weight:800;color:#FCD34D;font-family:monospace">%{_yuzde_v:.2f}</div>'
                    '</div>', unsafe_allow_html=True)
            st.caption("ℹ️ Masraf · kur · indirim **canlı**dır — yazdıkça sağdaki % maliyet güncellenir. "
                       "Ürün/adet/FOB · durum · teslim alanlarını aşağıdan düzenleyip **Kaydet**'e bas; hepsi birlikte kaydedilir.")
            st.caption("🧹 **Bir masrafı silmek için** kutunun içini tamamen boşalt (kutu boş/‘0,00’ görünür), sonra **Kaydet**'e bas — "
                       "artık geri gelmez. *(bu satırı görüyorsan güncel sürüm yüklüdür)*")
            _md_dolu = {s: v for s, v in _masraf_dict(d).items() if v}
            if _md_dolu:
                with st.expander("🧹 Masraf Kalemi Sıfırla (kesin silme — kutu boşaltmadan)", expanded=False):
                    st.caption("Kutu boşaltma çalışmazsa buradan sil: kalemi seç → düğmeye bas. "
                               "Doğrudan veritabanından silinir, geri gelmez.")
                    _ms_sec = st.multiselect(
                        "Sıfırlanacak masraf kalem(ler)i",
                        list(_md_dolu.keys()),
                        format_func=lambda s: f"{MASRAF_ETIKET.get(s, s)} — {_md_dolu[s]:,.2f}",
                        key=f"ith_ms_sifirla_{did}")
                    if st.button("🧹 Seçilenleri Sıfırla", type="primary", key=f"ith_ms_sifirla_btn_{did}",
                                 disabled=not _ms_sec):
                        _ok2, _msg2 = masraf_sifirla(did, _ms_sec)
                        if _ok2:
                            for _sk in [k for k in list(st.session_state.keys())
                                        if k.startswith(f"ith_edit_mas_{did}_")]:
                                st.session_state.pop(_sk, None)
                            st.success(_msg2)
                            st.rerun()
                        else:
                            st.error(_msg2)
            st.markdown("---")
            with st.form(f"ith_edit_{did}"):
                # ── ÇOKLU ÜRÜN GRUBU: masraf atama paneli (ortak/özel) ──
                # Kalemlerde tanımlı gruplara göre her masraf kalemini ortak mı
                # yoksa hangi gruba özel mi işaretle. Ortak → FOB payına dağıtılır.
                _mevcut_gruplar = sorted({(k.get("urun_grubu", "") or "").strip()
                                          for k in kal if (k.get("urun_grubu", "") or "").strip()})
                e_grup_atama = None
                if len(_mevcut_gruplar) >= 2:
                    _alt_baslik("🧩 Çoklu Grup — Masraf Atama (ortak / gruba özel)")
                    st.caption("Her masraf **ortak** (gruplara FOB payına göre bölünür) ya da **belirli bir gruba özel** "
                               "(vergi/TSE gibi) olabilir. Ürün grubu kalem tablosundan gelir.")
                    _atama_mevcut = d.get("grup_masraf_atama") if isinstance(d.get("grup_masraf_atama"), dict) else {}
                    _secenekler = [ORTAK_GRUP] + _mevcut_gruplar
                    _md_var = _masraf_dict(d)
                    e_grup_atama = {}
                    _ga_cols = st.columns(2)
                    _dolu_masraflar = [(s, l) for s, l in MASRAF_TANIM if float(_md_var.get(s, 0) or 0) > 0]
                    for _gi, (_slug, _label) in enumerate(_dolu_masraflar):
                        with _ga_cols[_gi % 2]:
                            _vars_secim = _atama_mevcut.get(_slug, ORTAK_GRUP)
                            if _vars_secim not in _secenekler:
                                _vars_secim = ORTAK_GRUP
                            _sec = st.selectbox(
                                f"{_label}  ({_tam(_md_var.get(_slug, 0))})",
                                _secenekler,
                                index=_secenekler.index(_vars_secim),
                                format_func=lambda x: "🌐 Ortak (FOB payına böl)" if x == ORTAK_GRUP else f"🎯 {x}",
                                key=f"ith_grup_atama_{did}_{_slug}")
                            e_grup_atama[_slug] = _sec
                    st.markdown("---")
                _alt_baslik("📄 Dosya Bilgileri")
                ec1, ec2, ec3 = st.columns(3)
                e_pi = ec1.text_input("PI No", value=str(d.get("pi_no", "") or ""))
                e_dno = ec1.text_input("Dosya No", value=str(d.get("dosya_no", "") or ""))
                e_sas = ec1.text_input("SAS No", value=str(d.get("sas_no", "") or ""))
                e_ted = ec2.text_input("Tedarikçi", value=str(d.get("tedarikci", "") or ""))
                _inc_cur = str(d.get("teslim_sekli", "") or "")
                _inc_opts = INCOTERM_SECENEKLER + ([_inc_cur] if _inc_cur and _inc_cur not in INCOTERM_SECENEKLER else [])
                e_teslim_sekli = ec2.selectbox("Teslim Şekli (Incoterm)", _inc_opts,
                    index=_inc_opts.index(_inc_cur) if _inc_cur in _inc_opts else 0,
                    key=f"ith_edit_inc_{did}")
                e_mense = ""
                _dv_list = ["USD", "EUR", "CNY", "TL"]
                _dv = str(d.get("doviz", "USD") or "USD")
                e_doviz = ec3.selectbox("Döviz", _dv_list, index=_dv_list.index(_dv) if _dv in _dv_list else 0)
                e_takip = ec3.text_input("İthalat Takip No", value=str(d.get("ithalat_takip_no", "") or ""),
                                         help="Masrafı giren kişinin kendi takibi için")
                try:
                    _td = date.fromisoformat(str(d.get("tarih", ""))[:10])
                except Exception:
                    _td = date.today()
                e_tarih = ec1.date_input("Sipariş Tarihi", value=_td)
                e_not = st.text_input("Notlar", value=str(d.get("notlar", "") or ""))

                # Aşama (durum) + tahmini varış
                _alt_baslik("🚚 Aşama / Durum · tahmini varış")
                _cur_durum = str(d.get("durum", "") or "").strip()
                _durum_idx = (DURUM_SECENEKLER.index(_cur_durum) if _cur_durum in DURUM_SECENEKLER
                              else DURUM_SECENEKLER.index(VARSAYILAN_DURUM))
                dcc1, dcc2 = st.columns([2.4, 1])
                with dcc1:
                    e_durum = st.radio("durum_e", DURUM_SECENEKLER, index=_durum_idx,
                                       horizontal=True, label_visibility="collapsed",
                                       key=f"ith_edit_durum_{did}")
                with dcc2:
                    if e_durum in IN_TRANSIT_DURUMLAR:
                        try:
                            _tv = date.fromisoformat(str(d.get("tahmini_varis", "") or "")[:10])
                        except Exception:
                            _tv = date.today()
                        e_tahmini_varis = st.date_input("Tahmini Varış", value=_tv, key=f"ith_edit_tv_{did}")
                    else:
                        e_tahmini_varis = None
                        st.markdown('<div class="ith-th" style="margin-bottom:4px">Tahmini Varış</div>', unsafe_allow_html=True)
                        st.caption("✅ Teslim alındı — tahmini varış gerekmez.")
                st.caption("📦 Üretimde/Yolda/Gümrükte/Antrepoda → Ürün Yönetimi'nde **yolda** görünür ve sipariş "
                           "önerisine girer. **Teslim Alındı** seçilince yolda sayılmaz.")

                _alt_baslik("📦 Teslim — ürün depoya girdiğinde doldur (stok yaşı bu tarihten sayılır)")
                tcc1, tcc2 = st.columns([1, 1.6])
                try:
                    _tt = date.fromisoformat(str(d.get("teslim_tarihi", "") or "")[:10])
                except Exception:
                    _tt = None
                e_teslim_tarihi = tcc1.date_input("Teslim Tarihi", value=_tt, key=f"ith_edit_tt_{did}",
                                                  format="YYYY-MM-DD")
                _td_cur = str(d.get("teslim_deposu", "") or "")
                _td_opts = DEPO_SECENEKLER + ([_td_cur] if _td_cur and _td_cur not in DEPO_SECENEKLER else [])
                _e_td_sec = tcc2.selectbox("Teslim Deposu", _td_opts,
                    index=_td_opts.index(_td_cur) if _td_cur in _td_opts else 0,
                    key=f"ith_edit_td_{did}")
                e_teslim_deposu = "" if str(_e_td_sec).startswith("(") else _e_td_sec

                _alt_baslik("📦 Ürün Kalemleri · satır ekle/sil/düzenle")
                st.caption("💡 **Çoklu ürün grubu** için: farklı ürünlere farklı **Ürün Grubu** yaz "
                           "(örn. SSD / RAM). 2+ grup olunca sistem grup-bazlı maliyet dağıtımına geçer. "
                           "Tek grup (ya da boş) bırakırsan normal tek-maliyet sistemi çalışır.")
                _kdf = pd.DataFrame([
                    {"SKU": k.get("sku", ""), "Ürün Grubu": (k.get("urun_grubu", "") or ""),
                     "Adet": float(k.get("adet", 0) or 0),
                     "Birim FOB": float(k.get("birim_fob", 0) or 0), "Sil": False}
                    for k in kal
                ])
                if _kdf.empty:
                    _kdf = pd.DataFrame([{"SKU": "", "Ürün Grubu": "", "Adet": 0.0, "Birim FOB": 0.0, "Sil": False}])
                _sku_secenek = sorted(set(katalog.keys()) | {str(k.get("sku", "")) for k in kal if k.get("sku")})
                _grup_mevcut = sorted({(k.get("urun_grubu", "") or "").strip() for k in kal if (k.get("urun_grubu", "") or "").strip()})
                e_kdf = st.data_editor(
                    _kdf, num_rows="dynamic", use_container_width=True, key=f"ith_edit_kal_{did}",
                    column_config={
                        "SKU": st.column_config.SelectboxColumn("SKU", options=_sku_secenek, required=False),
                        "Ürün Grubu": st.column_config.TextColumn(
                            "Ürün Grubu", help="Çoklu grup için doldur (örn. SSD, RAM). Tek grupsa boş bırak.",
                            default=""),
                        "Adet": st.column_config.NumberColumn("Adet", min_value=0, step=1, format="%d"),
                        "Birim FOB": st.column_config.NumberColumn("Birim FOB", min_value=0.0, step=0.01, format="%.2f"),
                        "Sil": st.column_config.CheckboxColumn(
                            "🗑 Sil", help="İşaretle → Kaydet'e basınca bu satır silinir", default=False),
                    },
                )
                st.caption("🗑 Bir satırı silmek için **Sil** kutusunu işaretle ve aşağıdan **Kaydet**'e bas. "
                           "(Alternatif: satırın solundaki kutucuğu seçip klavyeden **Delete**.)")

                _alt_baslik("🆕 Yeni Stok Kartı ile Satır Ekle · katalogda olmayan ürün")
                st.caption("Katalogda olmayan bir ürünü bu dosyaya eklemek için doldur — Kaydet'e basınca "
                           "hem dosyaya kalem olarak eklenir hem de **yeni stok kartı** (SKU + ürün adı + barkod) açılır. "
                           "Boş bırakılan satırlar yok sayılır.")
                _manuel_yeni = []
                _mver = st.session_state.setdefault(f"ith_edit_mver_{did}", 0)
                for _mi in range(2):
                    _mc1, _mc2, _mc3, _mc4, _mc5 = st.columns([1.2, 2, 1.2, 0.8, 1])
                    _msku = _mc1.text_input("Manuel SKU", key=f"ith_edit_msku_{did}_{_mi}_{_mver}",
                                            placeholder="örn. RMA-CE01", label_visibility=("visible" if _mi == 0 else "collapsed"))
                    _mad = _mc2.text_input("Ürün Adı", key=f"ith_edit_mad_{did}_{_mi}_{_mver}",
                                           placeholder="örn. Sertifikasyon Bedeli", label_visibility=("visible" if _mi == 0 else "collapsed"))
                    _mbk = _mc3.text_input("Barkod (ops.)", key=f"ith_edit_mbk_{did}_{_mi}_{_mver}",
                                           placeholder="barkod", label_visibility=("visible" if _mi == 0 else "collapsed"))
                    _madet = _mc4.number_input("Adet", min_value=0, value=0, step=1,
                                               key=f"ith_edit_madet_{did}_{_mi}_{_mver}", label_visibility=("visible" if _mi == 0 else "collapsed"))
                    _mfob = _mc5.number_input("Birim FOB", min_value=0.0, value=0.0, step=0.01, format="%.2f",
                                              key=f"ith_edit_mfob_{did}_{_mi}_{_mver}", label_visibility=("visible" if _mi == 0 else "collapsed"))
                    if _msku.strip() and _madet > 0:
                        _manuel_yeni.append({"sku": _msku.strip(), "urun_adi": _mad.strip(),
                                             "barkod": _mbk.strip(), "adet": float(_madet),
                                             "birim_fob": float(_mfob)})

                st.caption("💸 Masraf · kur · indirim **yukarıdaki canlı bölümde** girilir; aşağıdaki Kaydet hepsini birlikte kaydeder.")

                if st.form_submit_button("💾 Değişiklikleri Kaydet", type="primary", use_container_width=True):
                    if e_durum == "Teslim Alındı" and not (e_teslim_deposu or "").strip():
                        st.error("📦 'Teslim Alındı' için **Teslim Deposu seçimi zorunludur** — depo seçmeden kaydedilemez.")
                        st.stop()
                    _kal_ad = {str(k.get("sku", "")).strip(): (k.get("urun_adi") or "") for k in kal}
                    _yeni_kal = []
                    for _, _r in e_kdf.iterrows():
                        if _r.get("Sil"):
                            continue
                        _sku = str(_r.get("SKU", "") or "").strip()
                        if not _sku:
                            continue
                        _yeni_kal.append({"sku": _sku,
                                          "urun_adi": (katalog.get(_sku, "") or _kal_ad.get(_sku, "")),
                                          "urun_grubu": str(_r.get("Ürün Grubu", "") or "").strip(),
                                          "adet": float(_r.get("Adet", 0) or 0), "birim_fob": float(_r.get("Birim FOB", 0) or 0)})
                    for _m in _manuel_yeni:  # yeni stok kartlı satırlar
                        _yeni_kal.append({"sku": _m["sku"], "urun_adi": _m["urun_adi"],
                                          "urun_grubu": _m.get("urun_grubu", ""),
                                          "adet": _m["adet"], "birim_fob": _m["birim_fob"]})
                    with st.spinner("💾 Kaydediliyor..."):
                        ok, msg = guncelle_dosya(did, e_dno.strip(), e_pi.strip(), e_tarih, e_ted, e_mense,
                                                 e_doviz, e_kur, e_masraf, e_not, _yeni_kal,
                                                 ithalat_takip_no=e_takip.strip(),
                                                 grup_masraf_atama=e_grup_atama,
                                                 durum=e_durum,
                                                 tahmini_varis=(e_tahmini_varis if e_durum in IN_TRANSIT_DURUMLAR else ""),
                                                 fatura_indirim=e_indirim,
                                                 teslim_tarihi=(e_teslim_tarihi.isoformat() if e_teslim_tarihi else ""),
                                                 teslim_deposu=e_teslim_deposu,
                                                 teslim_sekli=("" if str(e_teslim_sekli).startswith("(") else e_teslim_sekli),
                                                 sas_no=e_sas.strip())
                    if ok:
                        st.session_state[f"ith_edit_mver_{did}"] = _mver + 1  # 🆕 manuel SKU alanlarını temizle
                        if _manuel_yeni:
                            try:
                                _n, _hata = urun_bilgi_toplu_yukle(
                                    [{"sku": m["sku"], "urun_adi": m["urun_adi"], "barkod": m["barkod"]}
                                     for m in _manuel_yeni])
                                if _n:
                                    st.toast(f"🆕 {_n} yeni stok kartı açıldı", icon="🆕")
                            except Exception:
                                pass
                        for _sk in [k for k in list(st.session_state.keys())
                                    if k in (f"ith_edit_indirim_{did}", f"ith_edit_kur_{did}")
                                    or k.startswith(f"ith_edit_mas_{did}_")
                                    or k.startswith(f"ith_edit_msku_{did}_")
                                    or k.startswith(f"ith_edit_mad_{did}_")
                                    or k.startswith(f"ith_edit_mbk_{did}_")
                                    or k.startswith(f"ith_edit_madet_{did}_")
                                    or k.startswith(f"ith_edit_mfob_{did}_")]:
                            st.session_state.pop(_sk, None)
                        st.toast("✅ Masraf ve değişiklikler kaydedildi", icon="✅")
                        st.rerun()
                    else:
                        st.error(msg)
        st.markdown("---")
        _duzen_key = f"ith_duzen_ac_{did}"
        if st.toggle("✏️ Düzenle — masraf kalemleri · ürün · adet · FOB", key=_duzen_key):
            _dosya_duzen_govde()
        else:
            # Düzenleme kapalı → guard'ı sıfırla ki tekrar açılışta DB'den taze dolsun
            st.session_state.pop(f"_ith_duzen_hazir_{did}", None)


    # ─────────────────────────────────────────────────────────────────────
    # SAYFA 2 — Yeni İthalat (Manuel + Excel)
    # ─────────────────────────────────────────────────────────────────────

    _dlg_dosya_detay()
def _yeni_ithalat():
    _baslik("➕", "Yeni İthalat", "Manuel form veya Excel ile dosya + kalem girişi")
    katalog = get_urun_katalog()
    sekme1, sekme2 = st.tabs(["📝 Manuel Giriş", "📑 Excel ile Toplu"])

    # ── Manuel ──
    with sekme1:
        with st.container(border=True):
            _fv = st.session_state.setdefault("m_form_ver", 0)
            _alt_baslik("📄 Dosya Bilgileri")
            c1, c2, c3 = st.columns(3)
            with c1:
                pi_no = st.text_input("PI No", key=f"m_pi_no_{_fv}", placeholder="PI-2025-001")
                dosya_no = st.text_input("Dosya / Sipariş No", key=f"m_dosya_no_{_fv}", placeholder="ITH-2025-001")
                sas_no = st.text_input("SAS No", key=f"m_sas_no_{_fv}", placeholder="SAS-1")
            with c2:
                _ted_gecmis = get_tedarikciler()
                _ted_opts = ["— tedarikçi seç —"] + _ted_gecmis + ["➕ Yeni tedarikçi (elle yaz)"]
                _ted_sec = st.selectbox("Tedarikçi (cari listesinden)", _ted_opts, key=f"m_ted_sec_{_fv}")
                if _ted_sec == "➕ Yeni tedarikçi (elle yaz)":
                    tedarikci = st.text_input("Yeni tedarikçi adı", key=f"m_ted_yeni_{_fv}",
                                              placeholder="Tam ticari unvanı yaz").strip()
                elif _ted_sec == "— tedarikçi seç —":
                    tedarikci = ""
                else:
                    tedarikci = _ted_sec
                teslim_sekli_m = st.selectbox("Teslim Şekli (Incoterm)", INCOTERM_SECENEKLER,
                                              index=INCOTERM_SECENEKLER.index("FOB"),
                                              key=f"m_teslim_sekli_{_fv}")
            with c3:
                tarih = st.date_input("Sipariş Tarihi", value=date.today(), key=f"m_tarih_{_fv}")
                doviz = st.selectbox("Döviz", ["USD", "EUR", "CNY", "TL"], key=f"m_doviz_{_fv}")
                # Kur burada girilmez — masraf aşamasında (Geçmiş İthalatlar → ✏️ Düzenle) girilir.
                kur = 1.0
            mense = ""

            # Aşama (durum) çubuğu + tahmini varış
            dc1, dc2 = st.columns([2.4, 1])
            with dc1:
                st.markdown('<div class="ith-th" style="margin-bottom:4px">Aşama / Durum</div>', unsafe_allow_html=True)
                durum = st.radio("durum", DURUM_SECENEKLER,
                                 index=DURUM_SECENEKLER.index(VARSAYILAN_DURUM),
                                 horizontal=True, label_visibility="collapsed", key=f"m_durum_{_fv}")
            with dc2:
                if durum in IN_TRANSIT_DURUMLAR:
                    tahmini_varis = st.date_input(
                        "Tahmini Varış", value=date.today(), key=f"m_tahmini_varis_{_fv}",
                        help="Yolda sayılan aşamalarda gecikme riski bu tarihe göre hesaplanır.")
                else:
                    tahmini_varis = None
                    st.markdown('<div class="ith-th" style="margin-bottom:4px">Tahmini Varış</div>', unsafe_allow_html=True)
                    st.caption("✅ Teslim aşaması — tahmini varış gerekmez.")
            if durum in IN_TRANSIT_DURUMLAR:
                st.caption(f"📦 **'{durum}'** → kalemler Ürün Yönetimi'nde *yolda* sayılır; teslim tarihi bu aşamada girilmez.")
                teslim_tarihi_m, teslim_deposu_m = "", ""
            else:

                _tcc1, _tcc2 = st.columns([1, 1.6])
                _tt_m = _tcc1.date_input("Teslim Tarihi", value=date.today(), key=f"m_teslim_tarihi_{_fv}",
                                         format="YYYY-MM-DD")
                _td_sec_m = _tcc2.selectbox("Teslim Deposu", DEPO_SECENEKLER, key=f"m_teslim_deposu_{_fv}")
                teslim_deposu_m = "" if str(_td_sec_m).startswith("(") else _td_sec_m
                teslim_tarihi_m = _tt_m.isoformat() if _tt_m else ""

        with st.container(border=True):
            _alt_baslik("📦 Ürün Kalemleri · katalogdan seç ya da manuel SKU / ürün adı / barkod gir")
            st.session_state.setdefault("m_satir_n", 5)
            n_satir = st.session_state.m_satir_n
            _barkod_map = get_barkod_map()

            # Aranabilir seçici: kutuya kod yazınca eşleşen SKU'lar listelenir, seçince ad otomatik gelir
            secenek_map = {sku: sku for sku in sorted(katalog.keys())}
            BOS = "— ürün seç (yazarak ara) —"
            secenek_labels = [BOS] + list(secenek_map.keys())

            if not katalog:
                st.info("Katalog boş — sorun değil, **Manuel SKU** + **Ürün Adı** + **Barkod** kutularına yazarak yeni kalem ekleyebilirsin.")

            _manuel_mod = st.toggle("✍️ Katalog dışı (yeni) ürün gireceğim — SKU · ad · barkod kolonlarını aç",
                                    key=f"m_manuel_mod_{_fv}",
                                    help="Kapalıyken sade görünüm: ürünü katalogdan seç, ad/barkod otomatik gelir.")
            if _manuel_mod:
                _oran = [1.8, 1.15, 1.6, 1.25, 0.75, 0.95, 0.5]
                _basliklar = ["Ürün (katalogdan)", "Manuel SKU", "Ürün Adı", "Barkod", "Adet", "Birim FOB", "🗑"]
            else:
                _oran = [3.2, 0.8, 1.0, 0.5]
                _basliklar = ["Ürün (katalogdan — yazarak ara)", "Adet", "Birim FOB", "🗑"]
            hcols = st.columns(_oran)
            for hc, ht in zip(hcols, _basliklar):
                hc.markdown(f'<div class="ith-th">{ht}</div>', unsafe_allow_html=True)

            def _kalem_doldur(i):
                _sv = st.session_state.get(f"m_urun_{i}_{_fv}")
                if _sv and _sv != BOS:
                    st.session_state[f"m_uad_{i}_{_fv}"] = katalog.get(_sv, "")
                    st.session_state[f"m_bk_{i}_{_fv}"] = _barkod_map.get(_sv, "")

            _kalemler = []
            for i in range(n_satir):
                rc = st.columns(_oran)
                _sel = rc[0].selectbox("urun", secenek_labels, key=f"m_urun_{i}_{_fv}",
                                       label_visibility="collapsed",
                                       on_change=_kalem_doldur, args=(i,))
                if _manuel_mod:
                    _msku = rc[1].text_input("msku", key=f"m_msku_{i}_{_fv}", label_visibility="collapsed",
                                             placeholder="SKU yaz").strip()
                    # Manuel SKU öncelikli; boşsa katalogdan seçilen kullanılır
                    _sku = _msku if _msku else (secenek_map[_sel] if (_sel and _sel != BOS) else "")
                    _uad = rc[2].text_input("uad", key=f"m_uad_{i}_{_fv}", label_visibility="collapsed",
                                            placeholder=(katalog.get(_sku, "") or "ürün adı")).strip()
                    _bk = rc[3].text_input("bk", key=f"m_bk_{i}_{_fv}", label_visibility="collapsed",
                                           placeholder=(_barkod_map.get(_sku, "") or "barkod")).strip()
                    _c_adet, _c_fob, _c_sil = rc[4], rc[5], rc[6]
                else:
                    # Sade mod: önceki oturumda manuel yazılmış değer varsa korunur (kaybolmaz)
                    _msku = str(st.session_state.get(f"m_msku_{i}_{_fv}", "") or "").strip()
                    _sku = _msku if _msku else (secenek_map[_sel] if (_sel and _sel != BOS) else "")
                    _uad = str(st.session_state.get(f"m_uad_{i}_{_fv}", "") or "").strip()
                    _bk = str(st.session_state.get(f"m_bk_{i}_{_fv}", "") or "").strip()
                    _c_adet, _c_fob, _c_sil = rc[1], rc[2], rc[3]
                _adet = _c_adet.number_input("adet", key=f"m_adet_{i}_{_fv}", label_visibility="collapsed",
                                             min_value=0, step=1, value=0)
                _fob = _c_fob.number_input("fob", key=f"m_fob_{i}_{_fv}", label_visibility="collapsed",
                                           min_value=0.0, step=0.01, value=0.0, format="%.2f")
                if _c_sil.button("🗑", key=f"m_sil_{i}_{_fv}", help="Bu satırı temizle"):
                    for _rk in (f"m_urun_{i}_{_fv}", f"m_msku_{i}_{_fv}", f"m_uad_{i}_{_fv}",
                                f"m_bk_{i}_{_fv}", f"m_adet_{i}_{_fv}", f"m_fob_{i}_{_fv}"):
                        st.session_state.pop(_rk, None)
                    st.rerun()
                if _sku:
                    _kalemler.append({"sku": _sku,
                                      "urun_adi": (_uad or katalog.get(_sku, "")),
                                      "barkod": (_bk or _barkod_map.get(_sku, "")),
                                      "adet": _adet, "birim_fob": _fob})

            ec1, _ec2 = st.columns([1.6, 5])
            if ec1.button("➕ Satır ekle", key=f"m_satir_ekle_{_fv}", use_container_width=True):
                st.session_state.m_satir_n = n_satir + 1
                st.rerun()
            _ec2.caption("🗑 satırı temizler · SKU'suz satırlar kaydedilmez.")
        _mal = sum(float(r.get("adet", 0) or 0) * float(r.get("birim_fob", 0) or 0) for r in _kalemler)

        # Fatura altı indirim (tutar) — net mal bedeli ve SKU maliyetleri buna göre düşer
        _ic1, _ic2 = st.columns([1, 2])
        with _ic1:
            m_indirim = st.number_input(
                "Fatura Altı İndirim (tutar)", min_value=0.0, value=0.0, step=1.0,
                format="%.2f", key=f"m_indirim_{_fv}",
                help="Faturanın altına yazılan toplam indirim (opsiyonel). "
                     "Net mal bedeli = Brüt − İndirim; SKU birim maliyetleri de bu orana göre düşer.")
        with _ic2:
            pass
        _net_mal = max(_mal - float(m_indirim or 0), 0.0)

        # Canlı özet — Brüt / İndirim / Net Mal Bedeli (masraf 2. aşamada girilir)
        _indirim_html = (
            '<div style="flex:1;min-width:120px;background:rgba(251,146,60,0.08);border:1px solid rgba(251,146,60,0.25);border-radius:12px;padding:12px 16px">'
            '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Fatura Altı İndirim</div>'
            f'<div style="font-size:15px;font-weight:700;color:#FB923C;font-family:monospace">−{_tam(float(m_indirim or 0))} <span style="font-size:11px;color:#64748B">{doviz}</span></div></div>'
        ) if float(m_indirim or 0) > 0 else ""
        st.markdown(
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 4px">'
            '<div style="flex:1;min-width:120px;background:rgba(148,163,184,0.08);border:1px solid rgba(148,163,184,0.2);border-radius:12px;padding:12px 16px">'
            '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Brüt Mal Bedeli</div>'
            f'<div style="font-size:15px;font-weight:700;color:#CBD5E1;font-family:monospace">{_tam(_mal)} <span style="font-size:11px;color:#64748B">{doviz}</span></div></div>'
            + _indirim_html +
            '<div style="flex:1;min-width:130px;background:rgba(52,211,153,0.10);border:1px solid rgba(52,211,153,0.28);border-radius:12px;padding:12px 16px">'
            '<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Net Mal Bedeli (FOB)</div>'
            f'<div style="font-size:15px;font-weight:800;color:#34D399;font-family:monospace">{_tam(_net_mal)} <span style="font-size:11px;color:#64748B">{doviz}</span></div></div>'
            '<div style="flex:2;min-width:200px;background:rgba(251,146,60,0.06);border:1px dashed rgba(251,146,60,0.28);border-radius:12px;padding:12px 16px;display:flex;align-items:center">'
            '<div style="font-size:11px;color:#FB923C;line-height:1.45">⏳ Masraf 2. aşamada (Geçmiş İthalatlar → ✏️ Düzenle). Maliyet & paçal masraf girilince oluşur.</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )

        if st.button("💾 Dosyayı Kaydet", type="primary", key=f"m_kaydet_{_fv}", use_container_width=True):
            if not dosya_no.strip():
                st.warning("Dosya / Sipariş No zorunlu.")
            elif not _kalemler:
                st.warning("En az bir ürün kalemi (SKU + adet) girin.")
            elif durum == "Teslim Alındı" and not (teslim_deposu_m or "").strip():
                st.error("📦 'Teslim Alındı' için **Teslim Deposu seçimi zorunludur** — depo seçmeden kaydedilemez.")
            else:
                for r in _kalemler:
                    if not (str(r.get("urun_adi") or "")).strip():
                        r["urun_adi"] = katalog.get((str(r.get("sku") or "")).strip(), "")
                _teslim_sekli_val = "" if str(teslim_sekli_m).startswith("(") else teslim_sekli_m
                ok, msg = ekle_dosya(dosya_no.strip(), tarih, tedarikci, mense, doviz, kur,
                                     {}, "", _kalemler, pi_no=pi_no.strip(),
                                     durum=durum,
                                     tahmini_varis=(tahmini_varis if durum in IN_TRANSIT_DURUMLAR else ""),
                                     fatura_indirim=m_indirim,
                                     teslim_tarihi=teslim_tarihi_m, teslim_deposu=teslim_deposu_m,
                                     teslim_sekli=_teslim_sekli_val, sas_no=sas_no.strip())
                (st.success if ok else st.error)(msg)
                if ok:
                    # Girilen barkodları urunler tablosuna yaz (SKU bazlı global)
                    for r in _kalemler:
                        _bk = (str(r.get("barkod") or "")).strip()
                        if _bk and r.get("sku"):
                            set_barkod(r["sku"], _bk)
                    # Formu SIFIRLA: sürüm sayacını artır → tüm alanlar/kalemler temizlenir
                    st.session_state["m_form_ver"] = _fv + 1
                    st.session_state.m_satir_n = 5
                    st.cache_data.clear()
                    st.rerun()

    # ── Excel ──
    with sekme2:
        # ═══════════════════════════════════════════════════════════════
        # AYRI PENCERE: Çoklu Ürün Grubu — MALİYET formatı (istisna dosyalar)
        # 2025-14 / 2026-12 gibi çok-gruplu sayfaları okur. Ortak masraf
        # FOB payına göre dağıtılır (grup atamasını sonra Düzenle'den yaparsın).
        # ═══════════════════════════════════════════════════════════════
        with st.expander("🧩 Çoklu Ürün Grubu Yükle — MALİYET formatı (istisna dosyalar)", expanded=False):
            st.caption("Bu pencere **yalnızca çoklu ürün gruplu** MALİYET dosyaların içindir "
                       "(2025-14 MITAC, 2026-12 AGI gibi). Normal tek-grup dosyaları **alttaki** "
                       "standart yükleyiciden gir. Bu pencere dosyanın masraflarını ve grup adlarını "
                       "okur; **SKU/adet/FOB kalemlerini ve masraf atamalarını (ortak/özel) sonra "
                       "Düzenle'den** eklersin. Ortak masraflar **FOB payına göre** dağıtılır.")
            _cg_up = st.file_uploader("MALİYET Excel'ini seç (çoklu-grup sayfası)",
                                      type=["xlsx", "xls"], key="ith_coklu_up")
            if _cg_up is not None:
                try:
                    import openpyxl as _oxl
                    _wb = _oxl.load_workbook(_cg_up, data_only=True)
                    _sayfalar = _wb.sheetnames
                    _sec_sayfa = st.selectbox("Hangi sayfa? (çoklu-grup olan)", _sayfalar,
                                              key="ith_coklu_sayfa")
                    _p = parse_maliyet_coklu_sayfa(_wb[_sec_sayfa])

                    st.markdown(f"**Okunan:** `{_p['tedarikci']}` · {_p['tasima']} · "
                                f"Mal Bedeli: {_tam(_p['mal_bedeli'])} · Kur: {_p['kur']:.4f}")
                    if _p["gruplar"]:
                        st.markdown("**Bulunan ürün grupları:** " +
                                    " · ".join(f"`{g}`" for g in _p["gruplar"]))
                    else:
                        st.warning("⚠️ Bu sayfada ürün grubu bulunamadı. Doğru sayfayı seçtiğinden emin ol.")
                    if _p["masraflar_usd"]:
                        st.markdown("**Okunan masraflar (USD'ye çevrildi):**")
                        _mdf = pd.DataFrame([{"Masraf": MASRAF_ETIKET.get(s, s),
                                              "Tutar (USD)": v}
                                             for s, v in _p["masraflar_usd"].items()])
                        _tablo(_mdf, para=["Tutar (USD)"], sol=["Masraf"])
                    if _p["uyari"]:
                        for _u in _p["uyari"]:
                            st.caption("⚠️ " + _u)

                    st.markdown("---")
                    _cg_dno = st.text_input("Dosya/Belge No *", key="ith_coklu_dno",
                                            placeholder="örn. 2026-12")
                    _cg_takip = st.text_input("İthalat Takip No", key="ith_coklu_takip",
                                              placeholder="opsiyonel")
                    _cg_doviz = st.selectbox("Döviz", ["USD", "EUR", "TL"], key="ith_coklu_doviz")

                    st.caption("💡 Kaydedince dosya **çoklu-grup** olarak oluşur (grup adları kalem "
                               "olarak eklenir; sonra Düzenle'den her gruba SKU/adet/FOB girip "
                               "masrafları ortak/özel atarsın).")
                    if st.button("💾 Çoklu-Grup Dosyası Oluştur", type="primary",
                                 use_container_width=True, key="ith_coklu_kaydet",
                                 disabled=not (_cg_dno.strip() and _p["gruplar"])):
                        # Her grup için 1 placeholder kalem (SKU sonradan düzenlenir).
                        # birim_fob = mal_bedeli / grup_sayisi geçici; kullanıcı Düzenle'de düzeltir.
                        _gsay = max(len(_p["gruplar"]), 1)
                        _kalemler = [{"sku": f"GRUP-{g}", "urun_adi": f"[{g}] — SKU'ları düzenle'den gir",
                                      "urun_grubu": g, "adet": 1,
                                      "birim_fob": round(_p["mal_bedeli"] / _gsay, 2)}
                                     for g in _p["gruplar"]]
                        # Tüm masraflar başta ORTAK; özel atamayı kullanıcı Düzenle'den yapar
                        _atama = {s: ORTAK_GRUP for s in _p["masraflar_usd"].keys()}
                        _okc, _msgc = ekle_dosya(
                            _cg_dno.strip(), None, _p["tedarikci"], "",
                            _cg_doviz, _p["kur"], _p["masraflar_usd"], "",
                            _kalemler, pi_no="", ithalat_takip_no=_cg_takip.strip())
                        if _okc:
                            # grup atamasını da yaz (hepsi ortak başlangıç)
                            try:
                                _yeni = get_dosyalar()
                                _bul = [d for d in _yeni if str(d.get("dosya_no","")) == _cg_dno.strip()]
                                if _bul:
                                    guncelle_dosya(
                                        _bul[0]["id"], _cg_dno.strip(), "", None,
                                        _p["tedarikci"], "", _cg_doviz, _p["kur"],
                                        _p["masraflar_usd"], "", _kalemler,
                                        ithalat_takip_no=_cg_takip.strip(),
                                        grup_masraf_atama=_atama)
                            except Exception:
                                pass
                            st.cache_data.clear()
                            st.success(f"✅ Çoklu-grup dosyası oluşturuldu: {_cg_dno.strip()} "
                                       f"({len(_p['gruplar'])} grup). Şimdi **Geçmiş İthalatlar**'dan "
                                       f"aç → Düzenle → her gruba SKU/adet/FOB gir, masrafları ortak/özel ata.")
                            st.rerun()
                        else:
                            st.error(_msgc)
                except Exception as _cge:
                    import traceback
                    st.error(f"❌ Dosya okunamadı: {type(_cge).__name__}: {str(_cge)[:200]}")
                    st.code(traceback.format_exc()[-1200:])
        st.markdown("---")
        st.markdown("**📄 Standart Satın Alım Raporu (tek grup — normal akış)**")
        st.download_button(
            "⬇️ Örnek şablonu indir", data=_excel_sablon_bytes(),
            file_name="ithalat_satin_alim_sablon.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="ith_sablon_dl",
        )
        up = st.file_uploader("Satın Alım Raporu Excel'ini yükle", type=["xlsx", "xls"], key="ith_excel_up")
        if up is not None:
            try:
                df = pd.read_excel(up)
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")
                return

            def _norm(h):
                h = str(h).strip().lower().replace("i̇", "i")
                for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c")):
                    h = h.replace(a, b)
                return h

            eslesme = {
                "ithalat takip no": "takip_no",
                "siparis tarihi": "tarih", "siparis no": "dosya_no", "belge no": "pi_no",
                "cari hesap adi": "tedarikci", "stok kodu": "sku", "stok ismi": "urun_adi",
                "miktar": "adet", "net fiyat": "net_fiyat", "birim fiyat": "birim_fiyat",
                "doviz": "doviz", "teslim tarihi": "teslim_tarihi",
                "teslim turu": "teslim_sekli", "teslim sekli": "teslim_sekli", "incoterm": "teslim_sekli",
                "urun grubu": "urun_grubu", "ürün grubu": "urun_grubu", "grup": "urun_grubu",
                "mal grubu": "urun_grubu", "kategori": "urun_grubu",
            }
            kol = {}
            for c in df.columns:
                alan = eslesme.get(_norm(c))
                if alan and alan not in kol:
                    kol[alan] = c

            eksik = [a for a in ("sku", "adet") if a not in kol]
            if "pi_no" not in kol and "dosya_no" not in kol:
                eksik.append("belge no / sipariş no")
            if "net_fiyat" not in kol and "birim_fiyat" not in kol:
                eksik.append("net fiyat / birim fiyat")
            if eksik:
                st.error("Şu sütunlar bulunamadı: " + ", ".join(eksik) +
                         ". Beklenen başlıklar: Belge no, Sipariş no, Cari hesap adı, Stok kodu, "
                         "Stok ismi, Miktar, Net fiyat (veya Birim Fiyat), Döviz.")
                return

            st.markdown("**Önizleme**")
            st.dataframe(df.head(30), use_container_width=True, height=240)

            # Gruplama anahtarı: BELGE NO (yoksa Sipariş no, yoksa Takip no).
            # Bir belge no = bir ithalat dosyası; her dosya kendi İthalat Takip No'su ile etiketlenir.
            # (Aynı takip no farklı belgelerde olabilir; her belge ayrı satır kalır.)
            _takip_col = kol.get("takip_no")
            _belge_col = kol.get("pi_no")
            _sip_col = kol.get("dosya_no")
            def _grup_key(r):
                b = str(r.get(_belge_col, "") or "").strip() if _belge_col else ""
                if b and b.lower() != "nan":
                    return b
                s = str(r.get(_sip_col, "") or "").strip() if _sip_col else ""
                if s and s.lower() != "nan":
                    return s
                return str(r.get(_takip_col, "") or "").strip() if _takip_col else ""
            df = df.copy()
            df["_grup"] = df.apply(_grup_key, axis=1)
            _dosyalar = get_dosyalar()
            # Mevcut dosya haritası: belge/dosya no VEYA takip no ile bul
            _dosya_map = {}
            for _d in _dosyalar:
                _tk = str(_d.get("ithalat_takip_no", "") or "").strip()
                _dn = str(_d.get("dosya_no", "") or "").strip()
                _pn = str(_d.get("pi_no", "") or "").strip()
                if _dn:
                    _dosya_map.setdefault(_dn, _d)
                if _pn:
                    _dosya_map.setdefault(_pn, _d)
                if _tk:
                    _dosya_map.setdefault(_tk, _d)
            gruplar = list(df.groupby("_grup"))
            _grup_ad = "belge" if _belge_col else "kayıt"
            st.caption(f"{len(gruplar)} {_grup_ad} (ithalat dosyası) bulundu — her belge ayrı dosya olur "
                       f"ve Excel'deki İthalat Takip No'su ile etiketlenir.")

            # 🔗 Mevcut dosyalara Excel'den Takip No ata/eşle (eski/boş kayıtlar için)
            if _takip_col:
                @st.dialog("🔗 Mevcut dosyalara Takip No ata (Excel'deki belge/sipariş eşleşmesiyle)", width="large")
                def _dlg_takip_ata():
                    st.caption("Excel'de aynı İthalat Takip No birden çok belge/sipariş içerir. "
                               "Bu araç, sistemdeki dosyalara — Belge No (PI) veya Sipariş No eşleşmesine göre — "
                               "Excel'deki takip no'yu atar. Mevcut içe aktarma akışını değiştirmez.")
                    _ust = st.checkbox("Dolu olan takip no'ları da güncelle (üzerine yaz)", key="ith_takip_ust")
                    # Excel'den eşleme haritaları
                    _belge_takip, _sip_takip = {}, {}
                    for _, _r in df.iterrows():
                        _t = str(_r.get(_takip_col, "") or "").strip()
                        if not _t or _t.lower() == "nan":
                            continue
                        if _belge_col:
                            _b = str(_r.get(_belge_col, "") or "").strip()
                            if _b and _b.lower() != "nan":
                                _belge_takip.setdefault(_b, _t)
                        if _sip_col:
                            _s = str(_r.get(_sip_col, "") or "").strip()
                            if _s and _s.lower() != "nan":
                                _sip_takip.setdefault(_s, _t)
                    # Aday dosyalar
                    _adaylar = []
                    for _d in _dosyalar:
                        _mevcut_t = str(_d.get("ithalat_takip_no", "") or "").strip()
                        if _mevcut_t and not _ust:
                            continue
                        _pi = str(_d.get("pi_no", "") or "").strip()
                        _dn = str(_d.get("dosya_no", "") or "").strip()
                        _yeni_t = (_belge_takip.get(_pi) or _belge_takip.get(_dn)
                                   or _sip_takip.get(_dn))
                        if _yeni_t and _yeni_t != _mevcut_t:
                            _adaylar.append((_d["id"], _dn or _pi, _mevcut_t or "—", _yeni_t))
                    st.caption(f"Eşleşen / atanacak dosya: {len(_adaylar)}")
                    if _adaylar:
                        st.dataframe(
                            pd.DataFrame([{"Dosya": a[1], "Eski Takip": a[2], "Atanacak Takip No": a[3]}
                                         for a in _adaylar]),
                            use_container_width=True, height=220, hide_index=True)
                        if st.button("🔗 Takip No'ları Ata", type="primary", key="ith_takip_ata"):
                            _n = 0
                            for _id, _, _, _t in _adaylar:
                                if set_dosya_takip_no(_id, _t):
                                    _n += 1
                            st.success(f"✅ {_n} dosyaya takip no atandı.")
                            st.rerun()
                    else:
                        st.info("Excel'de eşleşen (takip no atanacak) dosya bulunamadı.")
                if st.button("🔗 Mevcut dosyalara Takip No ata (Excel'deki belge/sipariş eşleşmesiyle)", key="btn_ith_takip", use_container_width=True):
                    _dlg_takip_ata()

            guncelle_mod = st.radio(
                "Sistemde zaten olan takip no'lar için:",
                ["Sadece yenileri ekle (mevcut atlanır · boş SAS/Incoterm/takip/teslim doldurulur)",
                 "Güncelle — Excel'i sisteme uygula (kalemleri yenile · masrafları KORU)"],
                key="ith_excel_mod",
            )
            _guncelle = guncelle_mod.startswith("Güncelle")
            if _guncelle:
                st.caption("⚠ Güncelle modu: mevcut takip no'ların ürün/adet/fiyatı Excel'e göre yenilenir. "
                           "Daha önce elle girdiğin **masraflar korunur** (silinmez).")
            else:
                st.caption("ℹ Sadece yenileri ekle: mevcut dosyaların ürün/adet/FOB'una **dokunulmaz**. "
                           "Yalnızca **boş** olan SAS No, Incoterm, takip no ve teslim tarihi Excel'den doldurulur. "
                           "→ Sadece eksik SAS No / Incoterm'i tamamlamak için aynı Excel'i bu modda tekrar yükle.")

            if st.button("📥 İçe Aktar", type="primary", key="ith_excel_import"):
                basari, guncellenen, atlanan, bedelsiz, hata, mesajlar = 0, 0, 0, 0, 0, []
                for dno, g in gruplar:
                    dno_s = str(dno).strip()
                    if not dno_s or dno_s.lower() == "nan":
                        continue
                    ilk = g.iloc[0]
                    kalemler = []
                    for _, r in g.iterrows():
                        sku = str(r.get(kol["sku"], "") or "").strip()
                        if not sku or sku.lower() == "nan":
                            continue
                        adet = _sf(r.get(kol["adet"]))
                        if adet <= 0:
                            continue
                        fob = _sf(r.get(kol["net_fiyat"])) if "net_fiyat" in kol else 0.0
                        if fob <= 0 and "birim_fiyat" in kol:
                            fob = _sf(r.get(kol["birim_fiyat"]))
                        # 0 fiyatlı (bedelsiz/yedek) satırı ATLAMA: adeti paçala dahil et,
                        # maliyet toplam tutara bölünerek düşer (ör. 707 adet, 700'ü fiyatlı).
                        if fob <= 0:
                            bedelsiz += 1
                        ad = str(r.get(kol["urun_adi"], "") or "").strip() if "urun_adi" in kol else ""
                        _ug = str(r.get(kol["urun_grubu"], "") or "").strip() if "urun_grubu" in kol else ""
                        kalemler.append({"sku": sku, "urun_adi": ad or katalog.get(sku, ""),
                                         "urun_grubu": _ug,
                                         "adet": adet, "birim_fob": fob})
                    if not kalemler:
                        atlanan += 1
                        mesajlar.append(f"{dno_s}: kalem yok, atlandı.")
                        continue
                    if sum(k["adet"] * k["birim_fob"] for k in kalemler) <= 0:
                        atlanan += 1
                        mesajlar.append(f"{dno_s}: tüm satırlar 0 fiyatlı (maliyet bazı yok), atlandı.")
                        continue
                    # Belge no(lar) — bir takip no altında birden çok belge olabilir
                    if "pi_no" in kol:
                        _belgeler = sorted({str(x).strip() for x in g[kol["pi_no"]].tolist()
                                            if str(x).strip() and str(x).strip().lower() != "nan"})
                    else:
                        _belgeler = []
                    belge_no = _belgeler[0] if _belgeler else dno_s
                    if "dosya_no" in kol:
                        _sips = sorted({str(x).strip() for x in g[kol["dosya_no"]].tolist()
                                        if str(x).strip() and str(x).strip().lower() != "nan"})
                    else:
                        _sips = []
                    # SAS No — Satın Alım Raporu'nda "Sipariş no" kolonu SAS numarasını taşır
                    sas_no_val = ", ".join(_sips) if _sips else ""
                    _not_parts = []
                    if len(_belgeler) > 1:
                        _not_parts.append("Belge(ler): " + ", ".join(_belgeler))
                    notlar = " · ".join(_not_parts)
                    # İthalat takip no (varsa) — dosya bununla dosyalanır; boşsa boş kalır
                    takip_no = str(ilk.get(kol["takip_no"], "") or "").strip() if "takip_no" in kol else ""
                    if takip_no.lower() == "nan":
                        takip_no = ""
                    tarih = _sd(ilk.get(kol["tarih"])) if "tarih" in kol else None
                    teslim = _sd(ilk.get(kol["teslim_tarihi"])) if "teslim_tarihi" in kol else None
                    ted = str(ilk.get(kol["tedarikci"], "") or "").strip() if "tedarikci" in kol else ""
                    dov = str(ilk.get(kol["doviz"], "USD") or "USD").strip() if "doviz" in kol else "USD"
                    # Teslim türü (Incoterm) — Excel'den; INCOTERM listesine uydur
                    teslim_sekli_val = ""
                    if "teslim_sekli" in kol:
                        _ts_raw = str(ilk.get(kol["teslim_sekli"], "") or "").strip()
                        if _ts_raw and _ts_raw.lower() != "nan":
                            _ts_up = _ts_raw.upper()
                            teslim_sekli_val = _ts_up if _ts_up in INCOTERM_SECENEKLER else _ts_raw

                    # Eşleştirme SADECE belge/dosya no ile (aynı takip no farklı belgelerde
                    # olabileceğinden takip no ile eşleştirme yapılmaz — birleşmeyi önler).
                    mevcut_kayit = _dosya_map.get(dno_s)
                    if mevcut_kayit:
                        if not _guncelle:
                            # "Sadece yenileri ekle": mevcut dosya atlanır AMA boş alanlar
                            # (takip no, teslim tarihi) Excel'den doldurulur — dolu olan ASLA değişmez.
                            _mt = str(mevcut_kayit.get("ithalat_takip_no", "") or "").strip()
                            _dolduruldu = []
                            if takip_no and not _mt:
                                set_dosya_takip_no(mevcut_kayit["id"], takip_no)
                                _dolduruldu.append(f"takip no {takip_no}")
                            _mtes = str(mevcut_kayit.get("teslim_tarihi", "") or "").strip()
                            if teslim and not _mtes:
                                set_dosya_teslim(mevcut_kayit["id"], teslim_tarihi=str(teslim)[:10])
                                _dolduruldu.append(f"teslim {str(teslim)[:10]}")
                            _msas = str(mevcut_kayit.get("sas_no", "") or "").strip()
                            if sas_no_val and not _msas:
                                set_dosya_sas(mevcut_kayit["id"], sas_no_val)
                                _dolduruldu.append(f"SAS {sas_no_val}")
                            _minc = str(mevcut_kayit.get("teslim_sekli", "") or "").strip()
                            if teslim_sekli_val and not _minc:
                                set_dosya_teslim_sekli(mevcut_kayit["id"], teslim_sekli_val)
                                _dolduruldu.append(f"Incoterm {teslim_sekli_val}")
                            if _dolduruldu:
                                guncellenen += 1
                                mesajlar.append(f"{dno_s}: zaten kayıtlı — boş alan dolduruldu ({', '.join(_dolduruldu)}).")
                            else:
                                atlanan += 1
                                mesajlar.append(f"{dno_s}: zaten kayıtlı, atlandı.")
                            continue
                        # GÜNCELLE — masrafları ve kuru koru, kalemleri yenile, teslim tarihini de yaz
                        eski_masraf = _masraf_dict(mevcut_kayit)
                        eski_kur = _sf(mevcut_kayit.get("kur"), 1) or 1
                        ok, msg = guncelle_dosya(
                            mevcut_kayit["id"], dno_s, belge_no, tarih, ted, "",
                            dov, eski_kur, eski_masraf, notlar, kalemler,
                            ithalat_takip_no=takip_no,
                            teslim_tarihi=(str(teslim)[:10] if teslim else ""),
                            teslim_sekli=(teslim_sekli_val or str(mevcut_kayit.get("teslim_sekli", "") or "")),
                            sas_no=(sas_no_val or str(mevcut_kayit.get("sas_no", "") or "")))
                        if ok:
                            guncellenen += 1
                        else:
                            hata += 1
                            mesajlar.append(f"{dno_s}: {msg}")
                    else:
                        ok, msg = ekle_dosya(dno_s, tarih, ted, "", dov, 1, {}, notlar, kalemler,
                                             pi_no=belge_no, ithalat_takip_no=takip_no,
                                             teslim_tarihi=(str(teslim)[:10] if teslim else ""),
                                             teslim_sekli=teslim_sekli_val, sas_no=sas_no_val)
                        if ok:
                            basari += 1
                        else:
                            hata += 1
                            mesajlar.append(f"{dno_s}: {msg}")
                if basari:
                    st.success(f"✅ {basari} yeni dosya içe aktarıldı (⏳ masraf bekliyor).")
                if guncellenen:
                    st.success(f"🔄 {guncellenen} mevcut dosya güncellendi (kalemler yenilendi, masraflar korundu).")
                if bedelsiz:
                    st.info(f"ℹ️ {bedelsiz} satır 0 fiyatlı (bedelsiz/yedek) — adetleri paçala dahil edildi, birim maliyet toplam tutara göre düştü.")
                if atlanan:
                    st.warning("Atlananlar:\n" + "\n".join(m for m in mesajlar if "atlandı" in m))
                if hata:
                    st.error("Hatalı dosyalar:\n" + "\n".join(m for m in mesajlar if "atlandı" not in m))
                if basari or guncellenen:
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────
# SAYFA 3 — Model Sorgu
# ─────────────────────────────────────────────────────────────────────
def _model_sorgu():
    _baslik("🔍", "Model Sorgu", "Bir SKU'nun geçmiş tüm alımları: firma · adet · fiyat · dosya % maliyeti · final maliyet")
    katalog = get_urun_katalog()
    tum_kalem = get_tum_kalemler()
    if not tum_kalem:
        st.info("Henüz ithalat kalemi yok.")
        return

    skular = sorted({k.get("sku", "") for k in tum_kalem if k.get("sku")})
    _sl, c_sec, _sr = st.columns([1.5, 2.2, 1.5])
    with c_sec:
        sku = st.selectbox("SKU", skular, label_visibility="collapsed", key="ith_ms_sku")

    dosyalar = {d["id"]: d for d in get_dosyalar()}
    kalem_by_dosya = defaultdict(list)
    for k in tum_kalem:
        kalem_by_dosya[k.get("dosya_id")].append(k)

    def _dosya_yuzde(did):
        return dosya_hesapla(dosyalar.get(did, {}), kalem_by_dosya.get(did, []))["maliyet_yuzde"]

    kayitlar = [k for k in tum_kalem if k.get("sku") == sku]
    satirlar = []
    for k in kayitlar:
        did = k.get("dosya_id")
        d = dosyalar.get(did, {})
        _h = dosya_hesapla(d, kalem_by_dosya.get(did, []))
        y = _h["maliyet_yuzde"]
        _ior = (_h.get("indirim", 0.0) / _h["mal_bedeli"]) if _h.get("mal_bedeli", 0) > 0 else 0.0
        bf = float(k.get("birim_fob", 0) or 0) * (1 - _ior)  # indirim sonrası NET birim FOB
        adet = float(k.get("adet", 0) or 0)
        satirlar.append({
            "Belge No": d.get("pi_no", "") or d.get("dosya_no", "") or "",
            "Tarih": str(d.get("tarih", ""))[:10],
            "Tedarikçi": d.get("tedarikci", ""),
            "Döviz": d.get("doviz", ""),
            "Adet": adet,
            "Birim FOB": bf,
            "% Maliyet": y,
            "Final Birim Maliyet": bf * (1 + y / 100),
        })
    df = pd.DataFrame(satirlar).sort_values("Tarih", ascending=False)
    if not df.empty:
        df["Tarih"] = df["Tarih"].apply(gun_ay_yil)

    ad = katalog.get(sku, "")
    st.markdown(
        f'<div style="color:#A5B4FC;font-size:15px;margin:0px 0 12px">📦 <b>{sku}</b>{(" — " + _tr_upper(ad)) if ad else ""}</div>',
        unsafe_allow_html=True,
    )

    toplam_adet = sum(s["Adet"] for s in satirlar)
    fobs = [s["Birim FOB"] for s in satirlar if s["Birim FOB"] > 0]
    # Adet ağırlıklı ortalama paçal (yerine konmuş) birim maliyet
    _pw = [(s["Adet"], s["Final Birim Maliyet"]) for s in satirlar if s["Adet"] > 0 and s["Birim FOB"] > 0]
    _pw_adet = sum(a for a, _ in _pw)
    pacal_ort = (sum(a * f for a, f in _pw) / _pw_adet) if _pw_adet > 0 else None
    # SON: en yeni TARİHLİ alımın FOB/maliyeti (aynı tarihte birden çok satır varsa adet-ağırlıklı)
    son_fob_v = son_mal_v = None
    son_tarih_v = ""
    if satirlar:
        _max_t = max((s["Tarih"] or "") for s in satirlar)
        _son_rows = [s for s in satirlar if (s["Tarih"] or "") == _max_t and s["Adet"] > 0 and s["Birim FOB"] > 0]
        _son_adet = sum(s["Adet"] for s in _son_rows)
        if _son_adet > 0:
            son_fob_v = sum(s["Adet"] * s["Birim FOB"] for s in _son_rows) / _son_adet
            son_mal_v = sum(s["Adet"] * s["Final Birim Maliyet"] for s in _son_rows) / _son_adet
            son_tarih_v = _max_t
    _dv = (satirlar[0]["Döviz"] if satirlar else "") or ""
    _ort_fob = f"${_tam(sum(fobs)/len(fobs))}" if fobs else "—"
    _pacal = f"${_tam(pacal_ort)}" if pacal_ort else "—"
    _son_fob = f"${_tam(son_fob_v)}" if son_fob_v else "—"
    _son_mal = f"${_tam(son_mal_v)}" if son_mal_v else "—"
    _son_help = (f"En yeni tarihli ({son_tarih_v}) ithalat dosyasındaki değer."
                 if son_tarih_v else "En yeni ithalat dosyasındaki değer.")
    _metrik_satiri([
        {"label": "Toplam Alım Adedi", "value": f"{toplam_adet:,.0f}", "renk": "#22D3EE"},
        {"label": "Sipariş Sayısı", "value": f"{len(satirlar):,}", "renk": "#818CF8"},
        {"label": "Ort. Birim FOB", "value": _ort_fob, "renk": "#60A5FA"},
        {"label": "Son FOB", "value": _son_fob, "renk": "#38BDF8", "help": _son_help},
        {"label": "⭐ Paçal Birim Maliyet", "value": _pacal, "renk": "#FCD34D",
         "help": "Ortalama FOB üzerine ithalat masraf yüzdesi bindirilmiş, adet ağırlıklı "
                 "ortalama yerine konmuş (paçal) birim maliyet. Masraf girilmemiş dosyalarda FOB'a eşittir."},
        {"label": "Son Birim Maliyet", "value": _son_mal, "renk": "#FCD34D", "help": _son_help},
    ])

    _tablo(df, para=["Birim FOB", "Final Birim Maliyet"], yuzde=["% Maliyet"],
           sol=["Belge No", "Tedarikçi", "Döviz"])


# ─────────────────────────────────────────────────────────────────────
# Çalıştırıcı
# ─────────────────────────────────────────────────────────────────────
def _masraf_detaylari():
    _baslik("💸", "Masraf Detayları", "Tüm ithalatlarda girilmiş her masraf kalemi — belge · masraf türü · tutar")
    dosyalar = get_dosyalar()
    if not dosyalar:
        st.info("Henüz ithalat kaydı yok.")
        return
    _kalem_by_dosya = {}
    for _k in get_tum_kalemler():
        _kalem_by_dosya.setdefault(_k.get("dosya_id"), []).append(_k)

    satirlar = []
    for d in dosyalar:
        _kal = _kalem_by_dosya.get(d["id"], [])
        _mb = sum(float(_k.get("adet", 0) or 0) * float(_k.get("birim_fob", 0) or 0) for _k in _kal)
        _bno = d.get("pi_no", "") or d.get("dosya_no", "") or "—"
        _tk = (d.get("ithalat_takip_no", "") or "").strip() or "—"
        _tar = str(d.get("tarih", "") or "")[:10]
        _ted = d.get("tedarikci", "") or ""
        _dov = d.get("doviz", "USD") or "USD"
        for _label, _tutar in masraf_dokumu(d):
            if _tutar:
                satirlar.append({
                    "Belge No": _bno, "Takip No": _tk, "Tarih": _tar,
                    "Tedarikçi": _ted, "Masraf Türü": _label,
                    "Tutar": float(_tutar), "Döviz": _dov,
                    "% (belge)": (float(_tutar) / _mb * 100) if _mb > 0 else 0.0,
                })
    if not satirlar:
        st.info("Henüz hiçbir ithalatta masraf girilmemiş. (Masraf, Geçmiş İthalatlar → belge düzenleme "
                "veya çoklu seçim → ortak masraf ile girilir.)")
        return

    # Filtreler + arama
    _turler = sorted({s["Masraf Türü"] for s in satirlar})
    _takipler = sorted({s["Takip No"] for s in satirlar if s["Takip No"] != "—"})
    fc1, fc2 = st.columns(2)
    f_tur = fc1.selectbox("Masraf Türü", ["Tümü"] + _turler, key="md_f_tur")
    f_tk = fc2.selectbox("Takip No", ["Tümü"] + _takipler, key="md_f_tk")
    _ara = st.text_input("🔍 Ara — Belge No · Takip No · Tedarikçi · Masraf Türü", key="md_ara").strip().lower()

    def _gecer(s):
        if f_tur != "Tümü" and s["Masraf Türü"] != f_tur:
            return False
        if f_tk != "Tümü" and s["Takip No"] != f_tk:
            return False
        if _ara and _ara not in (s["Belge No"] + " " + s["Takip No"] + " " +
                                 s["Tedarikçi"] + " " + s["Masraf Türü"]).lower():
            return False
        return True

    _flt = [s for s in satirlar if _gecer(s)]
    if not _flt:
        st.info("Filtre/aramayla eşleşen masraf kalemi yok.")
        return

    _toplam = sum(s["Tutar"] for s in _flt)
    _dovizler = {s["Döviz"] for s in _flt}
    _dov_lbl = list(_dovizler)[0] if len(_dovizler) == 1 else "karışık"
    _metrik_satiri([
        {"label": "Masraf Kalemi", "value": f"{len(_flt):,}", "renk": "#818CF8"},
        {"label": "Toplam Tutar", "value": f"{_tam(_toplam)} {_dov_lbl}", "renk": "#FB923C"},
        {"label": "Belge Sayısı", "value": f"{len({s['Belge No'] for s in _flt}):,}", "renk": "#34D399"},
        {"label": "Masraf Türü Sayısı", "value": f"{len({s['Masraf Türü'] for s in _flt}):,}", "renk": "#A78BFA"},
    ])

    # Masraf türüne göre toplam
    _tur_ozet = {}
    for s in _flt:
        _tur_ozet[s["Masraf Türü"]] = _tur_ozet.get(s["Masraf Türü"], 0.0) + s["Tutar"]
    @st.dialog("📊 Masraf Türüne Göre Toplam", width="large")
    def _dlg_masraf_top():
        st.dataframe(
            pd.DataFrame([{"Masraf Türü": k, "Toplam": _tam(v)}
                          for k, v in sorted(_tur_ozet.items(), key=lambda x: -x[1])]),
            hide_index=True, use_container_width=True)
    if st.button("📊 Masraf Türüne Göre Toplam", key="btn_ith_masraf", use_container_width=True):
        _dlg_masraf_top()

    # Ana liste
    _flt_sirali = sorted(_flt, key=lambda x: (x["Belge No"], x["Masraf Türü"]))
    _df = pd.DataFrame([{
        "Belge No": s["Belge No"], "Takip No": s["Takip No"], "Tarih": gun_ay_yil(s["Tarih"]),
        "Tedarikçi": s["Tedarikçi"], "Masraf Türü": s["Masraf Türü"],
        "Tutar": f"{s['Tutar']:,.2f}", "Döviz": s["Döviz"], "% (belge)": f"%{s['% (belge)']:.2f}",
    } for s in _flt_sirali])
    st.dataframe(_df, hide_index=True, use_container_width=True, height=520)
    st.caption(f"{len(_flt)} masraf kalemi · Toplam {_tam(_toplam)} {_dov_lbl}")

    # CSV indir
    _csv = pd.DataFrame([{
        "Belge No": s["Belge No"], "Takip No": s["Takip No"], "Tarih": gun_ay_yil(s["Tarih"]),
        "Tedarikçi": s["Tedarikçi"], "Masraf Türü": s["Masraf Türü"],
        "Tutar": round(s["Tutar"], 2), "Döviz": s["Döviz"],
    } for s in _flt_sirali]).to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ CSV indir", _csv, "ithalat_masraf_detaylari.csv",
                       mime="text/csv", use_container_width=True, key="md_csv")


def run():
    """İthalat modülü ana çalıştırıcı (portal tarafından çağrılır)."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown(
        "<style>"
        ".main .block-container{max-width:1200px !important;}"
        "[data-testid=\"stMetric\"]{background:linear-gradient(180deg,#152036,#0F172A);border:1px solid rgba(255,255,255,0.08);"
        "border-radius:12px;padding:12px 16px;}"
        "[data-testid=\"stMetricValue\"]{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:19px !important;}"
        "</style>",
        unsafe_allow_html=True,
    )
    _form_css()

    with st.sidebar:
        st.markdown(sidebar_stil(), unsafe_allow_html=True)
        st.markdown(sidebar_baslik("🚢", "İthalat", "İthalat Yönetimi"), unsafe_allow_html=True)
        if aktif_kullanici:
            st.markdown(sidebar_kullanici(aktif_kullanici), unsafe_allow_html=True)
            if st.button("Çıkış Yap", use_container_width=True, key="ith_cikis"):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.session_state.aktif_uygulama = "anasayfa"
                st.rerun()
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        sayfa = st.radio(
            "Sayfa",
            ["📋  Geçmiş İthalatlar", "➕  Yeni İthalat", "🔍  Model Sorgu", "💸  Masraf Detayları"],
            label_visibility="collapsed", key="ith_sayfa",
        )

    if sayfa == "📋  Geçmiş İthalatlar":
        _gecmis_ithalatlar()
    elif sayfa == "➕  Yeni İthalat":
        _yeni_ithalat()
    elif sayfa == "🔍  Model Sorgu":
        _model_sorgu()
    else:
        _masraf_detaylari()

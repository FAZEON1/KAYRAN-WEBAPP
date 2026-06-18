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

from .database import (
    get_dosyalar, get_kalemler, get_tum_kalemler, get_urun_katalog,
    ekle_dosya, sil_dosya, dosya_hesapla,
)


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


def _baslik(ikon, ad, alt):
    st.markdown(
        f'<div style="margin:2px 0 18px">'
        f'<div style="font-family:Inter,sans-serif;font-size:24px;font-weight:800;color:#FFFFFF;letter-spacing:-0.3px">{ikon} {ad}</div>'
        f'<div style="color:#94A3B8;font-size:13px;margin-top:4px">{alt}</div>'
        f'<div style="height:1px;background:linear-gradient(90deg,rgba(99,102,241,0.4),transparent);margin-top:12px"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _alt_baslik(t):
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#A5B4FC;letter-spacing:1.2px;'
        f'text-transform:uppercase;margin:2px 0 12px;display:flex;align-items:center;gap:8px">'
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

        /* ── Özel ürün tablosu başlık hücreleri ── */
        .ith-th {
            background: linear-gradient(135deg,#1E293B,#0F172A);
            color: #CBD5E1; font-size: 10px; font-weight: 700; letter-spacing: .4px;
            text-transform: uppercase; padding: 9px 12px; border-radius: 8px;
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
                return f"{float(v):,.2f}"
            if c in yuzde:
                return f"%{float(v):.1f}"
            if _isnum(c):
                fv = float(v)
                return f"{int(fv):,}" if fv == int(fv) else f"{fv:,.2f}"
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
        ".itt thead th{padding:10px 12px;color:#CBD5E1;font-size:10px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap;text-align:right}"
        ".itt thead th.l{text-align:left}"
        ".itt tbody{background:#131C35}"
        ".itt td{padding:8px 12px;font-size:11.5px;max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".itt tbody tr{border-bottom:1px solid rgba(255,255,255,0.05)}"
        ".itt tbody tr:hover{background:rgba(99,102,241,0.06)}"
        ".rk-txt{text-align:left;color:#CBD5E1}"
        ".rk-num{text-align:right;color:#CBD5E1;font-family:'JetBrains Mono',monospace}"
        "</style>"
    )
    st.html(css + f'<div class="itw"><table class="itt"><thead><tr>{ths}</tr></thead><tbody>' + rows_html + "</tbody></table></div>")


def _excel_sablon_bytes():
    """Örnek satırlı boş Excel şablonu üretir."""
    ornek = pd.DataFrame([
        {"dosya_no": "ITH-2025-001", "tarih": "2025-01-15", "tedarikci": "ABC Co.",
         "mense_ulke": "Cin", "doviz": "USD", "kur": 34.50,
         "navlun": 1200, "gumruk": 800, "sigorta": 150, "nakliye": 400, "diger": 100,
         "sku": "X27F165QW", "urun_adi": "27 inch Monitor", "adet": 100, "birim_fob": 85.00},
        {"dosya_no": "ITH-2025-001", "tarih": "2025-01-15", "tedarikci": "ABC Co.",
         "mense_ulke": "Cin", "doviz": "USD", "kur": 34.50,
         "navlun": 1200, "gumruk": 800, "sigorta": 150, "nakliye": 400, "diger": 100,
         "sku": "CASE-MID-01", "urun_adi": "Mid Tower Kasa", "adet": 50, "birim_fob": 40.00},
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        ornek.to_excel(w, index=False, sheet_name="ithalat")
    return buf.getvalue()


def _masraf_karti(d, h):
    doviz = d.get("doviz", "")
    st.markdown(
        '<div style="display:flex;gap:12px;flex-wrap:wrap;margin:6px 0 12px">'
        '<div style="background:rgba(99,102,241,0.10);border:1px solid rgba(99,102,241,0.25);border-radius:12px;padding:12px 18px;flex:1;min-width:150px">'
        '<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Mal Bedeli (FOB)</div>'
        f'<div style="font-size:18px;font-weight:700;color:#E2E8F0;font-family:\'JetBrains Mono\',monospace">{h["mal_bedeli"]:,.2f} {doviz}</div></div>'
        '<div style="background:rgba(251,146,60,0.10);border:1px solid rgba(251,146,60,0.25);border-radius:12px;padding:12px 18px;flex:1;min-width:150px">'
        '<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Toplam Masraf</div>'
        f'<div style="font-size:18px;font-weight:700;color:#FB923C;font-family:\'JetBrains Mono\',monospace">{h["toplam_masraf"]:,.2f} {doviz}</div></div>'
        '<div style="background:rgba(74,222,128,0.10);border:1px solid rgba(74,222,128,0.25);border-radius:12px;padding:12px 18px;flex:1;min-width:150px">'
        '<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Binen % Maliyet</div>'
        f'<div style="font-size:18px;font-weight:700;color:#4ADE80;font-family:\'JetBrains Mono\',monospace">%{h["maliyet_yuzde"]:.2f}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# SAYFA 1 — Geçmiş İthalatlar
# ─────────────────────────────────────────────────────────────────────
def _gecmis_ithalatlar():
    _baslik("📋", "Geçmiş İthalatlar", "Dosya başı toplam masraf ve FOB üzerine binen % maliyet")
    dosyalar = get_dosyalar()
    if not dosyalar:
        st.info("Henüz ithalat kaydı yok. '➕ Yeni İthalat' sayfasından ekleyebilirsin.")
        return

    katalog = get_urun_katalog()
    hesap_map = {}
    satirlar = []
    for d in dosyalar:
        kal = get_kalemler(d["id"])
        h = dosya_hesapla(d, kal)
        hesap_map[d["id"]] = (d, kal, h)
        satirlar.append({
            "Dosya No": d.get("dosya_no", ""),
            "Tarih": str(d.get("tarih", ""))[:10],
            "Tedarikçi": d.get("tedarikci", ""),
            "Ülke": d.get("mense_ulke", ""),
            "Döviz": d.get("doviz", ""),
            "Mal Bedeli": h["mal_bedeli"],
            "Toplam Masraf": h["toplam_masraf"],
            "% Maliyet": h["maliyet_yuzde"],
            "Kalem": h["kalem_sayisi"],
        })

    toplam_mal = sum(s["Mal Bedeli"] for s in satirlar)
    toplam_masraf = sum(s["Toplam Masraf"] for s in satirlar)
    ort_yuzde = (toplam_masraf / toplam_mal * 100) if toplam_mal > 0 else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dosya Sayısı", len(dosyalar))
    c2.metric("Toplam Mal Bedeli", f"{toplam_mal:,.0f}")
    c3.metric("Toplam Masraf", f"{toplam_masraf:,.0f}")
    c4.metric("Ort. % Maliyet", f"%{ort_yuzde:.1f}")

    _tablo(pd.DataFrame(satirlar),
           para=["Mal Bedeli", "Toplam Masraf"], yuzde=["% Maliyet"],
           sol=["Dosya No", "Tedarikçi", "Ülke", "Döviz"])

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    secenekler = {
        f'{d.get("dosya_no","")} — {str(d.get("tarih",""))[:10]} · {d.get("tedarikci","")}': d["id"]
        for d in dosyalar
    }
    sec = st.selectbox("Dosya detayını gör", list(secenekler.keys()), key="ith_dosya_sec")
    did = secenekler[sec]
    d, kal, h = hesap_map[did]

    _masraf_karti(d, h)
    st.caption(
        "Masraf kalemleri → "
        + " · ".join(
            f"{ad}: {float(d.get(k, 0) or 0):,.0f}"
            for ad, k in [("Navlun", "navlun"), ("Gümrük", "gumruk"), ("Sigorta", "sigorta"),
                          ("Nakliye", "nakliye"), ("Diğer", "diger")]
        )
        + f" · Kur: {float(d.get('kur', 1) or 1):,.2f}"
    )

    y = h["maliyet_yuzde"] / 100
    krows = []
    for k in kal:
        adet = float(k.get("adet", 0) or 0)
        bf = float(k.get("birim_fob", 0) or 0)
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
    _tablo(pd.DataFrame(krows),
           para=["Birim FOB", "Satır Tutar", "Dağıtılan Masraf", "Final Birim Maliyet"],
           yuzde=["% Maliyet"], sol=["SKU", "Ürün"], kisalt={"Ürün": 42})

    with st.expander("🗑️ Bu dosyayı sil"):
        st.warning("Bu işlem dosyayı ve tüm kalemlerini kalıcı olarak siler.")
        if st.button("Evet, sil", key="ith_sil_btn"):
            if sil_dosya(did):
                st.success("Dosya silindi.")
                st.rerun()
            else:
                st.error("Silinemedi.")


# ─────────────────────────────────────────────────────────────────────
# SAYFA 2 — Yeni İthalat (Manuel + Excel)
# ─────────────────────────────────────────────────────────────────────
def _yeni_ithalat():
    _baslik("➕", "Yeni İthalat", "Manuel form veya Excel ile dosya + kalem girişi")
    katalog = get_urun_katalog()
    sekme1, sekme2 = st.tabs(["📝 Manuel Giriş", "📑 Excel ile Toplu"])

    # ── Manuel ──
    with sekme1:
        with st.container(border=True):
            _alt_baslik("📄 Dosya Bilgileri")
            c1, c2, c3 = st.columns(3)
            with c1:
                dosya_no = st.text_input("Dosya / Sipariş No", key="m_dosya_no", placeholder="ITH-2025-001")
                doviz = st.selectbox("Döviz", ["USD", "EUR", "CNY", "TL"], key="m_doviz")
            with c2:
                tarih = st.date_input("Tarih", value=date.today(), key="m_tarih")
                kur = st.number_input("Kur (1 döviz = ? TL)", min_value=0.0, value=1.0, step=0.01, key="m_kur")
            with c3:
                tedarikci = st.text_input("Tedarikçi", key="m_ted")
                mense = st.text_input("Menşe Ülke", key="m_ulke")

        with st.container(border=True):
            _alt_baslik("💸 Masraf Kalemleri · dosya para birimi cinsinden")
            m1, m2, m3, m4, m5 = st.columns(5)
            navlun = m1.number_input("Navlun", min_value=0.0, value=0.0, step=1.0, key="m_navlun")
            gumruk = m2.number_input("Gümrük", min_value=0.0, value=0.0, step=1.0, key="m_gumruk")
            sigorta = m3.number_input("Sigorta", min_value=0.0, value=0.0, step=1.0, key="m_sigorta")
            nakliye = m4.number_input("Nakliye", min_value=0.0, value=0.0, step=1.0, key="m_nakliye")
            diger = m5.number_input("Diğer", min_value=0.0, value=0.0, step=1.0, key="m_diger")

        with st.container(border=True):
            _alt_baslik("📦 Ürün Kalemleri · SKU = Ürün Yönetimi'ndeki model no")
            st.session_state.setdefault("m_satir_n", 5)
            n_satir = st.session_state.m_satir_n

            hcols = st.columns([2, 3, 1.2, 1.5])
            for hc, ht in zip(hcols, ["SKU / Model No", "Ürün Adı (boşsa otomatik)", "Adet", "Birim FOB"]):
                hc.markdown(f'<div class="ith-th">{ht}</div>', unsafe_allow_html=True)

            _kalemler = []
            for i in range(n_satir):
                rc = st.columns([2, 3, 1.2, 1.5])
                _sku = rc[0].text_input("sku", key=f"m_sku_{i}", label_visibility="collapsed", placeholder="SKU")
                _ad = rc[1].text_input("ad", key=f"m_ad_{i}", label_visibility="collapsed", placeholder="otomatik gelir")
                _adet = rc[2].number_input("adet", key=f"m_adet_{i}", label_visibility="collapsed", min_value=0, step=1, value=0)
                _fob = rc[3].number_input("fob", key=f"m_fob_{i}", label_visibility="collapsed", min_value=0.0, step=0.01, value=0.0, format="%.2f")
                if str(_sku).strip():
                    _kalemler.append({"sku": str(_sku).strip(), "urun_adi": str(_ad).strip(),
                                      "adet": _adet, "birim_fob": _fob})

            ec1, _ec2 = st.columns([1.6, 5])
            if ec1.button("➕ Satır ekle", key="m_satir_ekle", use_container_width=True):
                st.session_state.m_satir_n = n_satir + 1
                st.rerun()
        _mal = sum(float(r.get("adet", 0) or 0) * float(r.get("birim_fob", 0) or 0) for r in _kalemler)
        _masraf = navlun + gumruk + sigorta + nakliye + diger
        _yuzde = (_masraf / _mal * 100) if _mal > 0 else 0

        # Canlı özet çipleri
        st.markdown(
            '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px">'
            '<div style="flex:1;min-width:140px;background:rgba(99,102,241,0.10);border:1px solid rgba(99,102,241,0.25);border-radius:12px;padding:11px 16px">'
            '<div style="font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Mal Bedeli (FOB)</div>'
            f'<div style="font-size:16px;font-weight:700;color:#E2E8F0;font-family:\'JetBrains Mono\',monospace">{_mal:,.2f} <span style="font-size:11px;color:#64748B">{doviz}</span></div></div>'
            '<div style="flex:1;min-width:140px;background:rgba(251,146,60,0.10);border:1px solid rgba(251,146,60,0.25);border-radius:12px;padding:11px 16px">'
            '<div style="font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Toplam Masraf</div>'
            f'<div style="font-size:16px;font-weight:700;color:#FB923C;font-family:\'JetBrains Mono\',monospace">{_masraf:,.2f} <span style="font-size:11px;color:#64748B">{doviz}</span></div></div>'
            '<div style="flex:1;min-width:140px;background:rgba(74,222,128,0.10);border:1px solid rgba(74,222,128,0.25);border-radius:12px;padding:11px 16px">'
            '<div style="font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Binen % Maliyet</div>'
            f'<div style="font-size:16px;font-weight:700;color:#4ADE80;font-family:\'JetBrains Mono\',monospace">%{_yuzde:.2f}</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )

        if st.button("💾 Dosyayı Kaydet", type="primary", key="m_kaydet", use_container_width=True):
            if not dosya_no.strip():
                st.warning("Dosya / Sipariş No zorunlu.")
            elif not _kalemler:
                st.warning("En az bir ürün kalemi (SKU + adet) girin.")
            else:
                for r in _kalemler:
                    if not (str(r.get("urun_adi") or "")).strip():
                        r["urun_adi"] = katalog.get((str(r.get("sku") or "")).strip(), "")
                ok, msg = ekle_dosya(dosya_no.strip(), tarih, tedarikci, mense, doviz, kur,
                                     navlun, gumruk, sigorta, nakliye, diger, "", _kalemler)
                (st.success if ok else st.error)(msg)
                if ok:
                    # Formu temizle
                    for i in range(st.session_state.get("m_satir_n", 5)):
                        for p in ("m_sku_", "m_ad_", "m_adet_", "m_fob_"):
                            st.session_state.pop(p + str(i), None)
                    for k in ("m_dosya_no", "m_ted", "m_ulke",
                              "m_navlun", "m_gumruk", "m_sigorta", "m_nakliye", "m_diger"):
                        st.session_state.pop(k, None)
                    st.session_state.m_satir_n = 5
                    st.rerun()

    # ── Excel ──
    with sekme2:
        st.markdown(
            "Şablonu indir, doldur ve yükle. Aynı **`dosya_no`** satırları tek ithalat dosyası olarak gruplanır; "
            "masraf alanları (navlun, gümrük, …) o dosyanın satırlarında aynı tekrar edilmeli (ya da yalnızca ilk satırda dolu)."
        )
        st.download_button(
            "⬇️ Excel şablonu indir", data=_excel_sablon_bytes(),
            file_name="ithalat_sablon.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="ith_sablon_dl",
        )
        up = st.file_uploader("Doldurulmuş Excel'i yükle", type=["xlsx", "xls"], key="ith_excel_up")
        if up is not None:
            try:
                df = pd.read_excel(up)
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")
                return
            df.columns = [str(c).strip().lower() for c in df.columns]
            gerekli = {"dosya_no", "sku", "adet", "birim_fob"}
            eksik = gerekli - set(df.columns)
            if eksik:
                st.error(f"Şu kolonlar eksik: {', '.join(sorted(eksik))}")
                return
            for col in ["tarih", "tedarikci", "mense_ulke", "doviz", "kur",
                        "navlun", "gumruk", "sigorta", "nakliye", "diger"]:
                if col not in df.columns:
                    df[col] = None
            ffill_cols = ["dosya_no", "tarih", "tedarikci", "mense_ulke", "doviz", "kur",
                          "navlun", "gumruk", "sigorta", "nakliye", "diger"]
            df[ffill_cols] = df[ffill_cols].ffill()

            st.markdown("**Önizleme**")
            st.dataframe(df, use_container_width=True, height=240)
            gruplar = list(df.groupby("dosya_no"))
            st.caption(f"{len(gruplar)} ithalat dosyası bulundu.")

            if st.button("📥 İçe Aktar", type="primary", key="ith_excel_import"):
                basari, hata, mesajlar = 0, 0, []
                for dno, g in gruplar:
                    ilk = g.iloc[0]
                    kalemler = []
                    for _, r in g.iterrows():
                        sku = str(r.get("sku", "") or "").strip()
                        if not sku or sku.lower() == "nan":
                            continue
                        ad = str(r.get("urun_adi", "") or "").strip()
                        kalemler.append({
                            "sku": sku,
                            "urun_adi": ad or katalog.get(sku, ""),
                            "adet": _sf(r.get("adet")),
                            "birim_fob": _sf(r.get("birim_fob")),
                        })
                    ok, msg = ekle_dosya(
                        str(dno).strip(), _sd(ilk.get("tarih")),
                        str(ilk.get("tedarikci", "") or ""), str(ilk.get("mense_ulke", "") or ""),
                        str(ilk.get("doviz", "USD") or "USD"), _sf(ilk.get("kur"), 1),
                        _sf(ilk.get("navlun")), _sf(ilk.get("gumruk")), _sf(ilk.get("sigorta")),
                        _sf(ilk.get("nakliye")), _sf(ilk.get("diger")), "", kalemler,
                    )
                    if ok:
                        basari += 1
                    else:
                        hata += 1
                        mesajlar.append(f"{dno}: {msg}")
                if basari:
                    st.success(f"✅ {basari} dosya içe aktarıldı.")
                if hata:
                    st.error("Hatalı dosyalar:\n" + "\n".join(mesajlar))
                if basari:
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
    _sl, c_ara, c_sec, _sr = st.columns([1.5, 1.1, 1.4, 1.5])
    with c_ara:
        ara = st.text_input("Ara", placeholder="SKU ara...", label_visibility="collapsed", key="ith_ms_ara")
    with c_sec:
        secenek = [s for s in skular if ara.upper() in s.upper()] if ara else skular
        if not secenek:
            st.warning("Eşleşen SKU yok.")
            return
        sku = st.selectbox("SKU", secenek, label_visibility="collapsed", key="ith_ms_sku")

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
        y = _dosya_yuzde(did)
        bf = float(k.get("birim_fob", 0) or 0)
        adet = float(k.get("adet", 0) or 0)
        satirlar.append({
            "Dosya No": d.get("dosya_no", ""),
            "Tarih": str(d.get("tarih", ""))[:10],
            "Tedarikçi": d.get("tedarikci", ""),
            "Döviz": d.get("doviz", ""),
            "Adet": adet,
            "Birim FOB": bf,
            "% Maliyet": y,
            "Final Birim Maliyet": bf * (1 + y / 100),
        })
    df = pd.DataFrame(satirlar).sort_values("Tarih", ascending=False)

    ad = katalog.get(sku, "")
    st.markdown(
        f'<div style="color:#A5B4FC;font-size:14px;margin:2px 0 12px">📦 <b>{sku}</b>{(" — " + ad) if ad else ""}</div>',
        unsafe_allow_html=True,
    )

    toplam_adet = sum(s["Adet"] for s in satirlar)
    fobs = [s["Birim FOB"] for s in satirlar if s["Birim FOB"] > 0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Alım Adedi", f"{toplam_adet:,.0f}")
    c2.metric("Sipariş Sayısı", f"{len(satirlar)}")
    c3.metric("Ort. Birim FOB", f"{(sum(fobs)/len(fobs)):,.2f}" if fobs else "—")
    c4.metric("Min – Maks FOB", f"{min(fobs):,.2f} – {max(fobs):,.2f}" if fobs else "—")

    _tablo(df, para=["Birim FOB", "Final Birim Maliyet"], yuzde=["% Maliyet"],
           sol=["Dosya No", "Tedarikçi", "Döviz"])


# ─────────────────────────────────────────────────────────────────────
# Çalıştırıcı
# ─────────────────────────────────────────────────────────────────────
def run():
    """İthalat modülü ana çalıştırıcı (portal tarafından çağrılır)."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown(
        "<style>"
        ".main .block-container{max-width:1200px !important;}"
        "[data-testid=\"stMetric\"]{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);"
        "border-radius:12px;padding:12px 16px;}"
        "[data-testid=\"stMetricValue\"]{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:20px !important;}"
        "</style>",
        unsafe_allow_html=True,
    )
    _form_css()

    with st.sidebar:
        st.markdown(
            '<div style="padding:6px 4px 8px;text-align:center">'
            '<div style="font-size:26px;margin-bottom:4px">🚢</div>'
            '<div style="font-size:9px;color:#64748B;letter-spacing:1.5px;text-transform:uppercase">İthalat Yönetimi</div>'
            '<div style="height:1px;background:linear-gradient(90deg,transparent,rgba(99,102,241,0.6),transparent);margin-top:14px"></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if aktif_kullanici:
            st.markdown(
                '<div style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);'
                'border-radius:10px;padding:10px 14px;margin-bottom:10px">'
                '<div style="color:#64748B;font-size:10px;font-weight:600;letter-spacing:0.5px;margin-bottom:2px">OTURUM AÇIK</div>'
                f'<div style="color:#A5B4FC;font-weight:700;font-size:13px">👤 {aktif_kullanici.capitalize()}</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Çıkış Yap", use_container_width=True, key="ith_cikis"):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.session_state.aktif_uygulama = "anasayfa"
                st.rerun()
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        sayfa = st.radio(
            "Sayfa",
            ["📋  Geçmiş İthalatlar", "➕  Yeni İthalat", "🔍  Model Sorgu"],
            label_visibility="collapsed", key="ith_sayfa",
        )

    if sayfa == "📋  Geçmiş İthalatlar":
        _gecmis_ithalatlar()
    elif sayfa == "➕  Yeni İthalat":
        _yeni_ithalat()
    else:
        _model_sorgu()

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
    ekle_dosya, guncelle_dosya, sil_dosya, dosya_hesapla, MASRAF_TANIM, masraf_dokumu, _masraf_dict,
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
    """Satın Alım Raporu formatında örnek şablon (sistemden çekilen yapıyla aynı başlıklar)."""
    kolonlar = ["Sipariş Tarihi", "Sipariş no", "Belge no", "Belge tarihi", "Sipariş cinsi",
                "Teslim tarihi", "Teslim türü", "Cari hesap kodu", "Cari hesap adı", "Stok kodu",
                "Stok ismi", "Depo", "Miktar", "Birim", "Birim Fiyat", "Toplam iskonto", "Net fiyat",
                "Döviz", "Tutar", "Tamamlanan miktar", "Kalan miktar", "Öd.Pl", "Onay durumu",
                "Açık/Kapalı", "Durum"]
    s1 = ["2025-01-15", "SAS-1", "PI-2025-001", "2025-01-15", "Dış Ticaret siparişi", "2025-04-20",
          "FOB", "320.50.001", "ABC DISPLAY CO., LTD", "X27F165QW",
          "27 inch Gaming Monitor", "Merkez depo", 100, "Adet", 85, 0, 85, "USD", 8500, 100, 0,
          "PEŞİN", "Onaylandı", "Açık", "Açık"]
    s2 = ["2025-01-15", "SAS-1", "PI-2025-001", "2025-01-15", "Dış Ticaret siparişi", "2025-04-20",
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
            "PI No": d.get("pi_no", "") or "",
            "Dosya No": d.get("dosya_no", ""),
            "Tarih": str(d.get("tarih", ""))[:10],
            "Tedarikçi": d.get("tedarikci", ""),
            "Ülke": d.get("mense_ulke", ""),
            "Döviz": d.get("doviz", ""),
            "Mal Bedeli": h["mal_bedeli"],
            "Toplam Masraf": h["toplam_masraf"],
            "% Maliyet": h["maliyet_yuzde"],
            "Kalem": h["kalem_sayisi"],
            "Durum": "✅ Tamam" if h["toplam_masraf"] > 0 else "⏳ Bekliyor",
        })

    toplam_mal = sum(s["Mal Bedeli"] for s in satirlar)
    toplam_masraf = sum(s["Toplam Masraf"] for s in satirlar)
    ort_yuzde = (toplam_masraf / toplam_mal * 100) if toplam_mal > 0 else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dosya Sayısı", len(dosyalar))
    c2.metric("Toplam Mal Bedeli", f"{toplam_mal:,.0f}")
    c3.metric("Toplam Masraf", f"{toplam_masraf:,.0f}")
    c4.metric("Ort. % Maliyet", f"%{ort_yuzde:.1f}")

    # 🔍 Arama / filtre (Dosya No · PI No · Tedarikçi)
    _ara = st.text_input("🔍 Ara — Dosya No · PI No · Tedarikçi", key="ith_gecmis_ara",
                         placeholder="örn. PIFAZ, SAS-44, LCCGAME...").strip().lower()

    def _esl_d(d):
        if not _ara:
            return True
        return _ara in (str(d.get("dosya_no", "")) + " " + str(d.get("pi_no", "")) + " " +
                        str(d.get("tedarikci", ""))).lower()

    dosyalar_goster = [d for d in dosyalar if _esl_d(d)]
    satirlar_goster = [s for s in satirlar
                       if (not _ara) or _ara in (str(s.get("Dosya No", "")) + " " +
                                                 str(s.get("PI No", "")) + " " +
                                                 str(s.get("Tedarikçi", ""))).lower()]
    st.caption(f"{len(dosyalar_goster)} / {len(dosyalar)} dosya gösteriliyor")

    if not satirlar_goster:
        st.info("Aramayla eşleşen dosya yok.")
        return

    _tablo(pd.DataFrame(satirlar_goster),
           para=["Mal Bedeli", "Toplam Masraf"], yuzde=["% Maliyet"],
           sol=["PI No", "Dosya No", "Tedarikçi", "Ülke", "Döviz", "Durum"])

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    secenekler = {
        f'{d.get("dosya_no","")} — {str(d.get("tarih",""))[:10]} · {d.get("tedarikci","")}': d["id"]
        for d in dosyalar_goster
    }
    sec = st.selectbox("Dosya detayını gör", list(secenekler.keys()), key="ith_dosya_sec")
    did = secenekler[sec]
    d, kal, h = hesap_map[did]

    st.markdown(f'<div style="color:#94A3B8;font-size:12px;margin-bottom:6px">PI No: <b style="color:#E2E8F0">{d.get("pi_no","") or "—"}</b> · Dosya: <b style="color:#E2E8F0">{d.get("dosya_no","")}</b> · {d.get("tedarikci","")}</div>', unsafe_allow_html=True)
    _dr_txt = "✅ Masraf girildi — maliyet hesaplandı" if h["toplam_masraf"] > 0 else "⏳ Masraf bekliyor — aşağıdan ✏️ Düzenle ile gir"
    _dr_renk = "#4ADE80" if h["toplam_masraf"] > 0 else "#FB923C"
    st.markdown(f'<div style="display:inline-block;background:rgba(255,255,255,0.04);border:1px solid {_dr_renk}55;border-radius:8px;padding:6px 12px;margin:2px 0 12px;color:{_dr_renk};font-size:12px;font-weight:700">{_dr_txt}</div>', unsafe_allow_html=True)
    _masraf_karti(d, h)
    _dokum = masraf_dokumu(d)
    if _dokum:
        st.caption(
            "Masraf kalemleri → "
            + " · ".join(f"{ad}: {tutar:,.0f}" for ad, tutar in _dokum)
            + f" · Kur: {float(d.get('kur', 1) or 1):,.2f}"
        )
    else:
        st.caption(f"Masraf girilmemiş · Kur: {float(d.get('kur', 1) or 1):,.2f}")

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

    # ── Düzenle: masraf + ürün/adet/FOB (Aşama 2) ──
    with st.expander("✏️ Düzenle — masraf kalemleri · ürün · adet · FOB"):
        with st.form(f"ith_edit_{did}"):
            _alt_baslik("📄 Dosya Bilgileri")
            ec1, ec2, ec3 = st.columns(3)
            e_pi = ec1.text_input("PI No", value=str(d.get("pi_no", "") or ""))
            e_dno = ec1.text_input("Dosya No", value=str(d.get("dosya_no", "") or ""))
            e_ted = ec2.text_input("Tedarikçi", value=str(d.get("tedarikci", "") or ""))
            e_mense = ec2.text_input("Menşe Ülke", value=str(d.get("mense_ulke", "") or ""))
            _dv_list = ["USD", "EUR", "CNY", "TL"]
            _dv = str(d.get("doviz", "USD") or "USD")
            e_doviz = ec3.selectbox("Döviz", _dv_list, index=_dv_list.index(_dv) if _dv in _dv_list else 0)
            e_kur = ec3.number_input("Kur", min_value=0.0, value=float(d.get("kur", 1) or 1), step=0.01)
            try:
                _td = date.fromisoformat(str(d.get("tarih", ""))[:10])
            except Exception:
                _td = date.today()
            e_tarih = ec1.date_input("Tarih", value=_td)
            e_not = st.text_input("Notlar", value=str(d.get("notlar", "") or ""))

            _alt_baslik("📦 Ürün Kalemleri · satır ekle/sil/düzenle")
            _kdf = pd.DataFrame([
                {"SKU": k.get("sku", ""), "Adet": float(k.get("adet", 0) or 0), "Birim FOB": float(k.get("birim_fob", 0) or 0)}
                for k in kal
            ])
            if _kdf.empty:
                _kdf = pd.DataFrame([{"SKU": "", "Adet": 0.0, "Birim FOB": 0.0}])
            _sku_secenek = sorted(set(katalog.keys()) | {str(k.get("sku", "")) for k in kal if k.get("sku")})
            e_kdf = st.data_editor(
                _kdf, num_rows="dynamic", use_container_width=True, key=f"ith_edit_kal_{did}",
                column_config={
                    "SKU": st.column_config.SelectboxColumn("SKU", options=_sku_secenek, required=False),
                    "Adet": st.column_config.NumberColumn("Adet", min_value=0, step=1, format="%d"),
                    "Birim FOB": st.column_config.NumberColumn("Birim FOB", min_value=0.0, step=0.01, format="%.2f"),
                },
            )

            _alt_baslik("💸 Masraf Kalemleri · dosya para biriminde")
            _md = _masraf_dict(d)
            e_masraf = {}
            for _b in range(0, len(MASRAF_TANIM), 4):
                _grup = MASRAF_TANIM[_b:_b + 4]
                _cols = st.columns(4)
                for _j, (_slug, _label) in enumerate(_grup):
                    e_masraf[_slug] = _cols[_j].number_input(
                        _label, min_value=0.0, value=float(_md.get(_slug, 0) or 0), step=1.0,
                        key=f"ith_edit_mas_{did}_{_slug}"
                    )

            if st.form_submit_button("💾 Değişiklikleri Kaydet", type="primary", use_container_width=True):
                _yeni_kal = []
                for _, _r in e_kdf.iterrows():
                    _sku = str(_r.get("SKU", "") or "").strip()
                    if not _sku:
                        continue
                    _yeni_kal.append({"sku": _sku, "urun_adi": katalog.get(_sku, ""),
                                      "adet": float(_r.get("Adet", 0) or 0), "birim_fob": float(_r.get("Birim FOB", 0) or 0)})
                ok, msg = guncelle_dosya(did, e_dno.strip(), e_pi.strip(), e_tarih, e_ted, e_mense,
                                         e_doviz, e_kur, e_masraf, e_not, _yeni_kal)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

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
                pi_no = st.text_input("PI No", key="m_pi_no", placeholder="PI-2025-001")
                dosya_no = st.text_input("Dosya / Sipariş No", key="m_dosya_no", placeholder="ITH-2025-001")
            with c2:
                tedarikci = st.text_input("Tedarikçi", key="m_ted")
                mense = st.text_input("Menşe Ülke", key="m_ulke")
            with c3:
                tarih = st.date_input("Tarih", value=date.today(), key="m_tarih")
                doviz = st.selectbox("Döviz", ["USD", "EUR", "CNY", "TL"], key="m_doviz")
                kur = st.number_input("Kur (1 döviz = ? TL)", min_value=0.0, value=1.0, step=0.01, key="m_kur")

        with st.container(border=True):
            _alt_baslik("📦 Ürün Kalemleri · katalogdan ürün seç")
            st.session_state.setdefault("m_satir_n", 5)
            n_satir = st.session_state.m_satir_n

            # Aranabilir seçici: kutuya kod yazınca eşleşen SKU'lar listelenir, seçince ad otomatik gelir
            secenek_map = {sku: sku for sku in sorted(katalog.keys())}
            BOS = "— ürün seç (yazarak ara) —"
            secenek_labels = [BOS] + list(secenek_map.keys())

            if not katalog:
                st.warning("Katalog boş görünüyor. Önce Ürün Yönetimi'nde ürün ekleyin; ithalat kalemleri mevcut SKU'lardan seçilir.")

            hcols = st.columns([4, 1.2, 1.5])
            for hc, ht in zip(hcols, ["Ürün  ·  SKU", "Adet", "Birim FOB"]):
                hc.markdown(f'<div class="ith-th">{ht}</div>', unsafe_allow_html=True)

            _kalemler = []
            for i in range(n_satir):
                rc = st.columns([4, 1.2, 1.5])
                _sel = rc[0].selectbox("urun", secenek_labels, key=f"m_urun_{i}",
                                       label_visibility="collapsed")
                _adet = rc[1].number_input("adet", key=f"m_adet_{i}", label_visibility="collapsed",
                                           min_value=0, step=1, value=0)
                _fob = rc[2].number_input("fob", key=f"m_fob_{i}", label_visibility="collapsed",
                                          min_value=0.0, step=0.01, value=0.0, format="%.2f")
                if _sel and _sel != BOS:
                    _sku = secenek_map[_sel]
                    _kalemler.append({"sku": _sku, "urun_adi": katalog.get(_sku, ""),
                                      "adet": _adet, "birim_fob": _fob})

            ec1, _ec2 = st.columns([1.6, 5])
            if ec1.button("➕ Satır ekle", key="m_satir_ekle", use_container_width=True):
                st.session_state.m_satir_n = n_satir + 1
                st.rerun()
        _mal = sum(float(r.get("adet", 0) or 0) * float(r.get("birim_fob", 0) or 0) for r in _kalemler)

        # Canlı özet — sadece Mal Bedeli (masraf 2. aşamada girilir)
        st.markdown(
            '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px">'
            '<div style="flex:1;min-width:140px;background:rgba(99,102,241,0.10);border:1px solid rgba(99,102,241,0.25);border-radius:12px;padding:11px 16px">'
            '<div style="font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">Mal Bedeli (FOB)</div>'
            f'<div style="font-size:16px;font-weight:700;color:#E2E8F0;font-family:monospace">{_mal:,.2f} <span style="font-size:11px;color:#64748B">{doviz}</span></div></div>'
            '<div style="flex:2;min-width:220px;background:rgba(251,146,60,0.08);border:1px dashed rgba(251,146,60,0.30);border-radius:12px;padding:11px 16px;display:flex;align-items:center">'
            '<div style="font-size:11px;color:#FB923C;line-height:1.5">⏳ Masraf kalemleri 2. aşamada girilecek (Geçmiş İthalatlar → ✏️ Düzenle). Maliyet & paçal, masraf girilince otomatik oluşur.</div></div>'
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
                                     {}, "", _kalemler, pi_no=pi_no.strip())
                (st.success if ok else st.error)(msg)
                if ok:
                    # Formu temizle
                    for i in range(st.session_state.get("m_satir_n", 5)):
                        for p in ("m_urun_", "m_adet_", "m_fob_"):
                            st.session_state.pop(p + str(i), None)
                    for k in ("m_pi_no", "m_dosya_no", "m_ted", "m_ulke"):
                        st.session_state.pop(k, None)
                    st.session_state.m_satir_n = 5
                    st.rerun()

    # ── Excel ──
    with sekme2:
        st.markdown(
            "Sisteminizden aldığınız **Satın Alım Raporu** Excel'ini (.xls/.xlsx) doğrudan yükleyin. "
            "Aynı **Belge no** satırları tek ithalat dosyası olur — **bir belgede birden çok sipariş olabilir** "
            "ve masraf bu dosyaya (Belge no) göre maliyetlenir. Eşleme: "
            "**Belge no → Dosya / PI**, **Cari hesap adı → Tedarikçi**, **Stok kodu/ismi → ürün**, "
            "**Miktar → adet**, **Net fiyat** (yoksa **Birim Fiyat**) **→ birim FOB**, **Döviz**. "
            "İçindeki **Sipariş no(lar)** dosya notuna eklenir. "
            "Masraf bu aşamada girilmez — dosya **⏳ masraf bekliyor** olarak düşer; masrafları sonra "
            "**Geçmiş İthalatlar → ✏️ Düzenle**'den girersiniz. (0 fiyatlı/bedelsiz satırlar atlanmaz; adetleri paçala dahil edilir, maliyet toplam tutara bölünür.)"
        )
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
                "siparis tarihi": "tarih", "siparis no": "dosya_no", "belge no": "pi_no",
                "cari hesap adi": "tedarikci", "stok kodu": "sku", "stok ismi": "urun_adi",
                "miktar": "adet", "net fiyat": "net_fiyat", "birim fiyat": "birim_fiyat",
                "doviz": "doviz",
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

            # Gruplama anahtarı: BELGE NO (yoksa Sipariş no). Bir belge = bir ithalat dosyası.
            _belge_col = kol.get("pi_no")
            _sip_col = kol.get("dosya_no")
            def _grup_key(r):
                b = str(r.get(_belge_col, "") or "").strip() if _belge_col else ""
                if b and b.lower() != "nan":
                    return b
                return str(r.get(_sip_col, "") or "").strip() if _sip_col else ""
            df = df.copy()
            df["_grup"] = df.apply(_grup_key, axis=1)
            mevcut_dosyalar = {str(d.get("dosya_no", "")).strip() for d in get_dosyalar()}
            gruplar = list(df.groupby("_grup"))
            st.caption(f"{len(gruplar)} belge (ithalat dosyası) bulundu.")

            if st.button("📥 İçe Aktar", type="primary", key="ith_excel_import"):
                basari, atlanan, bedelsiz, hata, mesajlar = 0, 0, 0, 0, []
                for dno, g in gruplar:
                    dno_s = str(dno).strip()
                    if not dno_s or dno_s.lower() == "nan":
                        continue
                    if dno_s in mevcut_dosyalar:
                        atlanan += 1
                        mesajlar.append(f"{dno_s}: zaten kayıtlı, atlandı.")
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
                        kalemler.append({"sku": sku, "urun_adi": ad or katalog.get(sku, ""),
                                         "adet": adet, "birim_fob": fob})
                    if not kalemler:
                        atlanan += 1
                        mesajlar.append(f"{dno_s}: kalem yok, atlandı.")
                        continue
                    if sum(k["adet"] * k["birim_fob"] for k in kalemler) <= 0:
                        atlanan += 1
                        mesajlar.append(f"{dno_s}: tüm satırlar 0 fiyatlı (maliyet bazı yok), atlandı.")
                        continue
                    belge_no = str(ilk.get(kol["pi_no"], "") or "").strip() if "pi_no" in kol else ""
                    if not belge_no or belge_no.lower() == "nan":
                        belge_no = dno_s
                    if "dosya_no" in kol:
                        _sips = sorted({str(x).strip() for x in g[kol["dosya_no"]].tolist()
                                        if str(x).strip() and str(x).strip().lower() != "nan"})
                    else:
                        _sips = []
                    notlar = ("Sipariş(ler): " + ", ".join(_sips)) if _sips else ""
                    tarih = _sd(ilk.get(kol["tarih"])) if "tarih" in kol else None
                    ted = str(ilk.get(kol["tedarikci"], "") or "").strip() if "tedarikci" in kol else ""
                    dov = str(ilk.get(kol["doviz"], "USD") or "USD").strip() if "doviz" in kol else "USD"
                    ok, msg = ekle_dosya(dno_s, tarih, ted, "", dov, 1, {}, notlar, kalemler, pi_no=belge_no)
                    if ok:
                        basari += 1
                    else:
                        hata += 1
                        mesajlar.append(f"{dno_s}: {msg}")
                if basari:
                    st.success(f"✅ {basari} dosya içe aktarıldı (⏳ masraf bekliyor).")
                if bedelsiz:
                    st.info(f"ℹ️ {bedelsiz} satır 0 fiyatlı (bedelsiz/yedek) — adetleri paçala dahil edildi, birim maliyet toplam tutara göre düştü.")
                if atlanan:
                    st.warning("Atlananlar:\n" + "\n".join(m for m in mesajlar if "atlandı" in m))
                if hata:
                    st.error("Hatalı dosyalar:\n" + "\n".join(m for m in mesajlar if "atlandı" not in m))
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
        secenek = [s for s in skular if s.upper().startswith(ara.upper())] if ara else skular
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

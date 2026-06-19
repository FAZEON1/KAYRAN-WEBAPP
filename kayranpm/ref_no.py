# -*- coding: utf-8 -*-
"""Firma bazlı Referans No (sellout / marketing destek) atama ve takip modülü.

Ref no formatı:  FZ<KOD>RF<YIL><SIRA:03d>   ör. FZVTNRF2025001
- KOD     : firmanın ref kısaltması (VATAN→VTN, HB→HB, İTOPYA→İT)
- YIL     : atama yılı (yıl değişse de SIRA sıfırlanmaz, sürekli artar)
- SIRA    : firma içinde sürekli artan sayaç (NUMARA)
"""
import re
import pandas as pd
import streamlit as st
from datetime import date, datetime

from .database import get_client, _rows, _cache_temizle

DURUMLAR = ["beklemede", "paylasildi", "iptal"]
DURUM_ETIKET = {
    "beklemede": "⏳ Beklemede (paylaşılmadı)",
    "paylasildi": "✅ Paylaşıldı",
    "iptal": "🚫 İptal",
}


def _yil():
    return datetime.now().year


def ref_uret(kod, yil, sira):
    return f"FZ{kod}RF{yil}{int(sira):03d}"


def _parse_ref(ref):
    """FZVTNRF2025001 → (kod='VTN', yil=2025, sira=1). Eşleşmezse (None, None, None)."""
    m = re.match(r"^FZ(.+?)RF(\d{4})(\d+)$", str(ref).strip())
    if not m:
        return None, None, None
    return m.group(1), int(m.group(2)), int(m.group(3))


# ── DB ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def get_firmalar():
    try:
        sb = get_client()
        return _rows(sb.table("ref_firmalar").select("*").order("firma_adi").execute())
    except Exception:
        return []


def firma_ekle(adi, kodu):
    try:
        sb = get_client()
        sb.table("ref_firmalar").insert(
            {"firma_adi": adi.strip(), "firma_kodu": kodu.strip().upper()}
        ).execute()
        _cache_temizle()
        return True, f"✅ '{adi}' firması eklendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


@st.cache_data(ttl=30, show_spinner=False)
def get_refler(firma_id):
    try:
        sb = get_client()
        return _rows(sb.table("ref_kayitlari").select("*")
                     .eq("firma_id", firma_id).order("sira_no").execute())
    except Exception:
        return []


def _sonraki_sira(firma_id):
    refler = get_refler(firma_id)
    return max((int(r.get("sira_no") or 0) for r in refler), default=0) + 1


def ref_ekle(firma_id, kod, aciklama, durum="beklemede", tarih=None, yil=None):
    try:
        sb = get_client()
        sira = _sonraki_sira(firma_id)
        yil = yil or _yil()
        ref_no = ref_uret(kod, yil, sira)
        sb.table("ref_kayitlari").insert({
            "firma_id": firma_id, "sira_no": sira, "ref_no": ref_no,
            "aciklama": aciklama or "", "durum": durum, "yil": yil,
            "tarih": str(tarih) if tarih else None,
            "paylasim_tarihi": str(tarih) if (durum == "paylasildi" and tarih) else None,
        }).execute()
        _cache_temizle()
        return True, f"✅ {ref_no} atandı."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def ref_guncelle(ref_id, ref_no, aciklama, durum, tarih, paylasim_tarihi=None):
    try:
        sb = get_client()
        sb.table("ref_kayitlari").update({
            "ref_no": ref_no, "aciklama": aciklama or "", "durum": durum,
            "tarih": str(tarih) if tarih else None,
            "paylasim_tarihi": str(paylasim_tarihi) if paylasim_tarihi else None,
        }).eq("id", ref_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def excel_ice_aktar(firma_id, df, varsayilan_durum="paylasildi"):
    """NUMARA / REF NUMARASI / AÇIKLAMA başlıklı df'i içe aktarır (mükerrer ref atlanır)."""
    try:
        sb = get_client()
        kol = {str(c).strip().lower(): c for c in df.columns}

        def _bul(*adlar):
            for a in adlar:
                for k, v in kol.items():
                    if a in k:
                        return v
            return None

        c_no = _bul("numara")
        c_ref = _bul("ref")
        c_ack = _bul("açıklama", "aciklama", "aklama", "klama")
        if not c_ref:
            return False, "REF NUMARASI sütunu bulunamadı.", 0
        mevcut = {str(r.get("ref_no", "")).strip() for r in get_refler(firma_id)}
        rows = []
        for _, r in df.iterrows():
            ref = str(r.get(c_ref, "") or "").strip()
            if not ref or ref.lower() == "nan" or ref in mevcut:
                continue
            kod, yil, sira = _parse_ref(ref)
            if c_no is not None:
                try:
                    sira = int(float(r.get(c_no)))
                except Exception:
                    pass
            ack = str(r.get(c_ack, "") or "").strip() if c_ack else ""
            if ack.lower() == "nan":
                ack = ""
            rows.append({
                "firma_id": firma_id, "sira_no": sira or 0, "ref_no": ref,
                "aciklama": ack, "durum": varsayilan_durum, "yil": yil,
            })
        if rows:
            sb.table("ref_kayitlari").insert(rows).execute()
        _cache_temizle()
        return True, f"✅ {len(rows)} ref içe aktarıldı.", len(rows)
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


# ── UI ──────────────────────────────────────────────────────────────
def render():
    st.markdown('<div class="baslik">🔖 Ref No Takibi</div>', unsafe_allow_html=True)
    st.markdown('<div class="alt-baslik">Firma bazlı sellout / marketing destek referans no atama ve takip</div>',
                unsafe_allow_html=True)

    firmalar = get_firmalar()

    with st.expander("🏢 Yeni Firma Ekle"):
        with st.form("ref_firma_ekle", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            yf_adi = fc1.text_input("Firma Adı", placeholder="örn. INCEHESAP")
            yf_kod = fc2.text_input("Ref Kodu (kısaltma)", placeholder="örn. INC",
                                    help="Ref no'da kullanılır: FZ<KOD>RF<yıl><sıra>")
            if st.form_submit_button("➕ Firma Ekle", type="primary"):
                if not yf_adi.strip() or not yf_kod.strip():
                    st.warning("Firma adı ve kodu zorunlu.")
                else:
                    ok, msg = firma_ekle(yf_adi, yf_kod)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()

    if not firmalar:
        st.info("Henüz firma yok. Yukarıdan 'Yeni Firma Ekle' ile başlayın (örn. VATAN / kod: VTN).")
        return

    fmap = {f"{f['firma_adi']}  ·  FZ{f['firma_kodu']}RF…": f for f in firmalar}
    sec_label = st.selectbox("Firma seç", list(fmap.keys()), key="ref_firma_sec")
    firma = fmap[sec_label]
    fid, fkod = firma["id"], firma["firma_kodu"]

    refler = get_refler(fid)
    _bekleyen = sum(1 for r in refler if r.get("durum") == "beklemede")
    _paylasilan = sum(1 for r in refler if r.get("durum") == "paylasildi")
    m1, m2, m3 = st.columns(3)
    m1.metric("Toplam Ref", len(refler))
    m2.metric("⏳ Beklemede", _bekleyen)
    m3.metric("✅ Paylaşılan", _paylasilan)

    # ── Yeni ref ata (otomatik no) ──
    _siradaki = _sonraki_sira(fid)
    _onizleme = ref_uret(fkod, _yil(), _siradaki)
    st.markdown(
        '<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);'
        'border-radius:10px;padding:11px 16px;margin:8px 0 6px">'
        f'Sıradaki otomatik ref no: <b style="color:#A5B4FC;font-family:monospace;font-size:15px">{_onizleme}</b></div>',
        unsafe_allow_html=True,
    )
    with st.form("ref_ekle_form", clear_on_submit=True):
        rc1, rc2 = st.columns([3, 1.4])
        yeni_ack = rc1.text_input("Açıklama", placeholder="örn. TEMMUZ MONİTÖR SELLOUT 5.000$")
        yeni_durum = rc2.selectbox("Durum", DURUMLAR, format_func=lambda d: DURUM_ETIKET[d], index=0)
        yeni_tarih = st.date_input("Tarih", value=date.today())
        if st.form_submit_button("➕ Ref No Ata", type="primary", use_container_width=True):
            ok, msg = ref_ekle(fid, fkod, yeni_ack.strip(), yeni_durum, yeni_tarih)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

    # ── Excel'den içe aktar ──
    with st.expander("📥 Excel'den İçe Aktar (NUMARA · REF NUMARASI · AÇIKLAMA)"):
        up = st.file_uploader("Bu firmanın ref Excel'i", type=["xlsx", "xls"], key=f"ref_up_{fid}")
        if up is not None:
            try:
                df_imp = pd.read_excel(up)
                st.dataframe(df_imp.head(20), use_container_width=True, height=200)
                imp_durum = st.selectbox("İçe aktarılan kayıtların durumu", DURUMLAR,
                                         format_func=lambda d: DURUM_ETIKET[d], index=1,
                                         key=f"ref_imp_durum_{fid}")
                if st.button("📥 İçe Aktar", type="primary", key=f"ref_imp_btn_{fid}"):
                    ok, msg, _n = excel_ice_aktar(fid, df_imp, imp_durum)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")

    # ── Geçmiş refler: görüntüle + düzenle ──
    st.markdown("#### 📋 Geçmiş Ref No'lar")
    if not refler:
        st.info("Bu firma için henüz ref no yok. Yukarıdan atayabilir veya Excel'den içe aktarabilirsiniz.")
        return

    f_durum = st.selectbox("Durum filtresi", ["Tümü"] + DURUMLAR,
                           format_func=lambda d: ("Tümü" if d == "Tümü" else DURUM_ETIKET[d]),
                           key=f"ref_durum_f_{fid}")
    goster = refler if f_durum == "Tümü" else [r for r in refler if r.get("durum") == f_durum]
    st.caption(f"{len(goster)} / {len(refler)} kayıt gösteriliyor")

    df_ed = pd.DataFrame([{
        "id": r["id"],
        "No": int(r.get("sira_no") or 0),
        "Ref No": r.get("ref_no", "") or "",
        "Açıklama": r.get("aciklama", "") or "",
        "Durum": r.get("durum", "beklemede") or "beklemede",
        "Tarih": str(r.get("tarih") or ""),
    } for r in goster])

    edited = st.data_editor(
        df_ed, use_container_width=True, hide_index=True, num_rows="fixed",
        key=f"ref_editor_{fid}_{f_durum}",
        column_config={
            "id": None,
            "No": st.column_config.NumberColumn("No", disabled=True, width="small"),
            "Ref No": st.column_config.TextColumn("Ref No", disabled=True),
            "Açıklama": st.column_config.TextColumn("Açıklama", width="large"),
            "Durum": st.column_config.SelectboxColumn("Durum", options=DURUMLAR, required=True),
            "Tarih": st.column_config.TextColumn("Tarih (YYYY-AA-GG)"),
        },
    )
    if st.button("💾 Değişiklikleri Kaydet", type="primary", key=f"ref_save_{fid}"):
        orijinal = {r["id"]: r for r in goster}
        degisen = 0
        for _, row in edited.iterrows():
            rid = row["id"]
            o = orijinal.get(rid, {})
            n_ack = str(row.get("Açıklama", "") or "")
            n_dur = str(row.get("Durum", "beklemede"))
            n_tar = (str(row.get("Tarih", "") or "").strip() or None)
            if (n_ack != (o.get("aciklama", "") or "") or
                    n_dur != (o.get("durum") or "") or
                    (n_tar or "") != (str(o.get("tarih") or ""))):
                pay = n_tar if n_dur == "paylasildi" else o.get("paylasim_tarihi")
                ref_guncelle(rid, str(row.get("Ref No", "")), n_ack, n_dur, n_tar, pay)
                degisen += 1
        st.success(f"✅ {degisen} kayıt güncellendi." if degisen else "Değişiklik yok.")
        if degisen:
            st.rerun()

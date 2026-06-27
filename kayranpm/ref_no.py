# -*- coding: utf-8 -*-
"""Firma bazlı Referans No + Havuz Bütçe (sellout / marketing destek) modülü.

Ref no formatı:  FZ<KOD>RF<YIL><SIRA:03d>   ör. FZVTNRF2025001

Havuz Bütçe mantığı:
  - TÜR = "BÜTÇE"  → önden verilen bütçe (GİRİŞ +)
  - Diğer türler   → sellout / destek harcaması (HARCAMA −)
  - Kalan havuz    = toplam giriş − toplam harcama
"""
import re
import pandas as pd
import streamlit as st
from datetime import date, datetime

from .database import get_client, _rows, _cache_temizle
from shared.utils import metrik_satiri

DURUMLAR = ["beklemede", "paylasildi", "iptal"]
DURUM_ETIKET = {
    "beklemede": "⏳ Beklemede (paylaşılmadı)",
    "paylasildi": "✅ Paylaşıldı",
    "iptal": "🚫 İptal",
}

# Havuz bütçe türleri (BÜTÇE = giriş; diğerleri = harcama)
BUTCE_TURLER = ["BÜTÇE", "KAMPANYA", "REBATE", "STOK KORUMA", "KREDİ KARTI",
                "BİRLİKTE SATIŞ", "BEDELSİZ ÜRÜN", "MARKETING", "PAZARLAMA"]
GIRIS_TURLER = {"BÜTÇE"}


def _yil():
    return datetime.now().year


def _yon_belirle(tur):
    return "giris" if str(tur).strip().upper() in {t.upper() for t in GIRIS_TURLER} else "harcama"


def _import_yon(tur, kisi, tutar):
    """Excel içe aktarımında yön tahmini: gerçek havuz depozitosu =
    TÜR=BÜTÇE + kişi yok (SIFIRLANDI/boş) + tutar >= 50.000. Diğer her şey harcama."""
    k = str(kisi or "").strip().lower()
    kisi_yok = (k == "" or k == "nan" or "sifirland" in k or "sıfırland" in k)
    if str(tur).strip().upper() == "BÜTÇE" and kisi_yok and abs(_f(tutar)) >= 50000:
        return "giris"
    return "harcama"


def ref_uret(kod, yil, sira):
    return f"FZ{kod}RF{yil}{int(sira):03d}"


def _parse_ref(ref):
    m = re.match(r"^FZ(.+?)RF(\d{4})(\d+)$", str(ref).strip())
    if not m:
        return None, None, None
    return m.group(1), int(m.group(2)), int(m.group(3))


def _f(v, d=0.0):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return d
        return float(str(v).replace(",", "").replace("$", "").strip())
    except Exception:
        return d


# ── FİRMA DB ────────────────────────────────────────────────────────
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


# ── REF NO DB ───────────────────────────────────────────────────────
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


def ref_ekle(firma_id, kod, aciklama, durum="beklemede", tarih=None, yil=None,
             ay="", kategori="", tutar=0.0, doviz="USD"):
    try:
        sb = get_client()
        sira = _sonraki_sira(firma_id)
        yil = yil or _yil()
        ref_no = ref_uret(kod, yil, sira)
        _payload = {
            "firma_id": firma_id, "sira_no": sira, "ref_no": ref_no,
            "aciklama": aciklama or "", "durum": durum, "yil": yil,
            "tarih": str(tarih) if tarih else None,
            "paylasim_tarihi": str(tarih) if (durum == "paylasildi" and tarih) else None,
            "ay": ay or "", "kategori": kategori or "",
            "tutar": _f(tutar), "doviz": doviz or "USD",
        }
        try:
            sb.table("ref_kayitlari").insert(_payload).execute()
        except Exception:
            # Yeni kolonlar (ay/kategori/tutar/doviz) tabloda yoksa onlarsız tekrar dene
            for _opt in ("ay", "kategori", "tutar", "doviz"):
                _payload.pop(_opt, None)
            sb.table("ref_kayitlari").insert(_payload).execute()
        _cache_temizle()
        return True, f"✅ {ref_no} atandı."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def ref_guncelle(ref_id, ref_no, aciklama, ay="", kategori="", tutar=0.0, doviz="USD", yil=None):
    try:
        sb = get_client()
        _payload = {
            "ref_no": ref_no, "aciklama": aciklama or "",
            "ay": ay or "", "kategori": kategori or "",
            "tutar": _f(tutar), "doviz": doviz or "USD",
        }
        if yil is not None:
            _payload["yil"] = int(yil)
        try:
            sb.table("ref_kayitlari").update(_payload).eq("id", ref_id).execute()
        except Exception:
            for _opt in ("ay", "kategori", "tutar", "doviz"):
                _payload.pop(_opt, None)
            sb.table("ref_kayitlari").update(_payload).eq("id", ref_id).execute()
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
        c_ay = _bul("ay")
        c_kat = _bul("kategori")
        c_tut = _bul("tutar")
        c_dov = _bul("döviz", "doviz")
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
            _ay = (str(r.get(c_ay, "") or "").strip() if c_ay else "")
            _kat = (str(r.get(c_kat, "") or "").strip() if c_kat else "")
            _dov = (str(r.get(c_dov, "") or "").strip() if c_dov else "") or "USD"
            _tut = _f(r.get(c_tut)) if c_tut is not None else 0.0
            rows.append({
                "firma_id": firma_id, "sira_no": sira or 0, "ref_no": ref,
                "aciklama": ack, "durum": varsayilan_durum, "yil": yil,
                "ay": ("" if _ay.lower() == "nan" else _ay),
                "kategori": ("" if _kat.lower() == "nan" else _kat),
                "tutar": _tut, "doviz": _dov,
            })
        if rows:
            try:
                sb.table("ref_kayitlari").insert(rows).execute()
            except Exception:
                # Yeni kolonlar tabloda yoksa onlarsız tekrar dene
                for _r in rows:
                    for _opt in ("ay", "kategori", "tutar", "doviz"):
                        _r.pop(_opt, None)
                sb.table("ref_kayitlari").insert(rows).execute()
        _cache_temizle()
        return True, f"✅ {len(rows)} ref içe aktarıldı.", len(rows)
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


def ref_kayitlari_temizle(firma_id):
    """Bir firmanın TÜM ref kayıtlarını siler (sıfırdan yükleme için). (ok, silinen_sayisi) döner."""
    try:
        sb = get_client()
        mevcut = get_refler(firma_id)
        n = len(mevcut)
        sb.table("ref_kayitlari").delete().eq("firma_id", firma_id).execute()
        _cache_temizle()
        return True, n
    except Exception:
        return False, 0


# ── HAVUZ BÜTÇE DB ──────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def get_butce(firma_id):
    try:
        sb = get_client()
        return _rows(sb.table("ref_butce").select("*")
                     .eq("firma_id", firma_id).order("fatura_tarih").execute())
    except Exception:
        return []


def butce_ekle(firma_id, tur, aciklama, tutar, doviz, fatura_no, fatura_tarih,
               ref_no, kisi, yon=None, marka="FAZEON"):
    try:
        sb = get_client()
        sb.table("ref_butce").insert({
            "firma_id": firma_id, "tur": tur or "", "yon": yon or _yon_belirle(tur),
            "aciklama": aciklama or "", "marka": marka or "", "tutar": _f(tutar),
            "doviz": doviz or "USD", "fatura_no": fatura_no or "",
            "fatura_tarih": str(fatura_tarih) if fatura_tarih else None,
            "ref_no": ref_no or "", "kisi": kisi or "",
        }).execute()
        _cache_temizle()
        return True, "✅ Kayıt eklendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def butce_guncelle(rid, tur, aciklama, tutar, fatura_no, fatura_tarih, ref_no, kisi, yon=None):
    try:
        sb = get_client()
        sb.table("ref_butce").update({
            "tur": tur or "", "yon": yon or _yon_belirle(tur),
            "aciklama": aciklama or "", "tutar": _f(tutar),
            "fatura_no": fatura_no or "",
            "fatura_tarih": str(fatura_tarih) if fatura_tarih else None,
            "ref_no": ref_no or "", "kisi": kisi or "",
        }).eq("id", rid).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def butce_sil(rid):
    try:
        sb = get_client()
        sb.table("ref_butce").delete().eq("id", rid).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def butce_temizle(firma_id):
    try:
        sb = get_client()
        sb.table("ref_butce").delete().eq("firma_id", firma_id).execute()
        _cache_temizle()
        return True
    except Exception:
        return False


def butce_excel_ice_aktar(firma_id, df, temizle=False):
    """ITOPYA_HAVUZ_BÜTÇE formatı (konuma göre):
    TÜR|MARKA|AÇIKLAMA|HAKEDİŞ BÜTÇE|TUTAR|DÖVİZ|FATURA NO|FATURA TARİH|FİRMA|REF NO|AÇIKLAMA(kişi)
    temizle=True ise mevcut kayıtlar SADECE geçerli yeni satır varsa silinir (veri kaybını önler)."""
    try:
        sb = get_client()
        rows = []
        for _, r in df.iterrows():
            v = list(r.values)

            def g(i):
                return v[i] if i < len(v) else None

            tur = str(g(0) or "").strip()
            if not tur or tur.lower() == "nan":
                continue
            marka = str(g(1) or "").strip()
            aciklama = str(g(2) or "").strip()
            tutar = _f(g(3))                       # HAKEDİŞ BÜTÇE = tutar
            doviz = str(g(5) or "USD").strip() or "USD"
            fatura_no = str(g(6) or "").strip()
            ft = g(7)
            if isinstance(ft, (datetime, date)):
                fatura_tarih = ft.strftime("%Y-%m-%d")
            else:
                s = str(ft or "").strip()
                fatura_tarih = s[:10] if s and s.lower() != "nan" else None
            ref_no = str(g(9) or "").strip()
            kisi = str(g(10) or "").strip()
            if kisi.lower() == "nan":
                kisi = ""
            rows.append({
                "firma_id": firma_id, "tur": tur, "yon": _import_yon(tur, kisi, tutar),
                "aciklama": (aciklama if aciklama.lower() != "nan" else ""),
                "marka": (marka if marka.lower() != "nan" else ""),
                "tutar": tutar, "doviz": doviz, "fatura_no": fatura_no,
                "fatura_tarih": fatura_tarih, "ref_no": ref_no, "kisi": kisi,
            })
        if not rows:
            return False, ("❌ Excel'de geçerli bütçe satırı bulunamadı (TÜR sütunu boş/yanlış olabilir). "
                           "Güvenlik için hiçbir mevcut kayıt silinmedi."), 0
        # Geçerli satır var → (istenirse) önce temizle, sonra ekle
        if temizle:
            sb.table("ref_butce").delete().eq("firma_id", firma_id).execute()
        for i in range(0, len(rows), 200):
            sb.table("ref_butce").insert(rows[i:i + 200]).execute()
        _cache_temizle()
        return True, f"✅ {len(rows)} bütçe kaydı içe aktarıldı.", len(rows)
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}", 0


# ════════════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════════════
def render():
    st.markdown('<div class="baslik">🔖 Ref No Takibi</div>', unsafe_allow_html=True)
    st.markdown('<div class="alt-baslik">Firma bazlı ref no atama + havuz bütçe takibi</div>',
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
    _TUMU = "🌐 Tüm Firmalar"
    sec_label = st.selectbox("Firma seç", [_TUMU] + list(fmap.keys()), key="ref_firma_sec")

    if sec_label == _TUMU:
        _render_tumu(firmalar)
        return

    firma = fmap[sec_label]

    tab1, tab2 = st.tabs(["🔖 Ref No'lar", "💰 Havuz Bütçe"])
    with tab1:
        _render_refler(firma["id"], firma["firma_kodu"])
    with tab2:
        _render_butce(firma["id"], firma)


# ── SEKME 1: REF NO'LAR ─────────────────────────────────────────────
def _render_refler(fid, fkod):
    refler = get_refler(fid)
    _bekleyen = sum(1 for r in refler if r.get("durum") == "beklemede")
    _paylasilan = sum(1 for r in refler if r.get("durum") == "paylasildi")
    metrik_satiri([
        {"label": "Toplam Ref", "value": f"{len(refler):,}", "renk": "#818CF8"},
        {"label": "⏳ Beklemede", "value": f"{_bekleyen:,}", "renk": "#FBBF24"},
        {"label": "✅ Paylaşılan", "value": f"{_paylasilan:,}", "renk": "#34D399"},
    ])

    _siradaki = _sonraki_sira(fid)
    _onizleme = ref_uret(fkod, _yil(), _siradaki)
    st.markdown(
        '<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);'
        'border-radius:10px;padding:11px 16px;margin:8px 0 6px">'
        f'Sıradaki otomatik ref no: <b style="color:#A5B4FC;font-family:monospace;font-size:15px">{_onizleme}</b></div>',
        unsafe_allow_html=True,
    )
    with st.form("ref_ekle_form", clear_on_submit=True):
        yeni_ack = st.text_input("Açıklama", placeholder="örn. FAZEON OCAK 18.126,55$ MONİTÖR SELLOUT")
        rc1, rc2, rc3, rc4, rc5 = st.columns([1.3, 1, 1.6, 1.3, 1])
        yeni_ay = rc1.text_input("Ay", placeholder="örn. OCAK")
        yeni_yil = rc2.number_input("Yıl", min_value=2000, max_value=2100, value=_yil(), step=1)
        yeni_kat = rc3.text_input("Kategori", placeholder="örn. MONİTÖR")
        yeni_tutar = rc4.number_input("Tutar", min_value=0.0, value=0.0, step=10.0, format="%.2f")
        yeni_doviz = rc5.selectbox("Döviz", ["USD", "EUR", "TL"], index=0)
        if st.form_submit_button("➕ Ref No Ata", type="primary", use_container_width=True):
            ok, msg = ref_ekle(fid, fkod, yeni_ack.strip(), yil=int(yeni_yil),
                               ay=yeni_ay.strip(), kategori=yeni_kat.strip(),
                               tutar=yeni_tutar, doviz=yeni_doviz)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

    with st.expander("📥 Excel'den İçe Aktar (REF NUMARASI · AÇIKLAMA · AY · YIL · KATEGORİ · TUTAR · DÖVİZ)"):
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

        if refler:
            st.markdown("---")
            st.markdown(f"**🗑️ Sıfırdan yükle:** bu firmanın **{len(refler)}** ref kaydını tamamen siler. "
                        "Sildikten sonra Excel'i yukarıdan yeniden içe aktarabilirsin. **Geri alınamaz.**")
            _onay = st.checkbox("Evet, bu firmanın tüm ref kayıtlarını silmeyi onaylıyorum",
                                key=f"ref_temizle_onay_{fid}")
            if st.button("🗑️ Tüm ref kayıtlarını sil", key=f"ref_temizle_btn_{fid}",
                         disabled=not _onay, use_container_width=True):
                ok, n = ref_kayitlari_temizle(fid)
                if ok:
                    st.success(f"✅ {n} ref kaydı silindi. Artık Excel'i sıfırdan yükleyebilirsin.")
                    st.rerun()
                else:
                    st.error("Silme başarısız.")

    st.markdown("#### 📋 Geçmiş Ref No'lar")
    if not refler:
        st.info("Bu firma için henüz ref no yok. Yukarıdan atayabilir veya Excel'den içe aktarabilirsiniz.")
        return

    goster = refler
    st.caption(f"{len(goster)} kayıt")

    df_ed = pd.DataFrame([{
        "id": r["id"],
        "Ref No": r.get("ref_no", "") or "",
        "Açıklama": r.get("aciklama", "") or "",
        "Ay": r.get("ay", "") or "",
        "Yıl": int(r.get("yil") or 0) or None,
        "Kategori": r.get("kategori", "") or "",
        "Tutar": float(r.get("tutar") or 0),
        "Döviz": r.get("doviz", "USD") or "USD",
    } for r in goster])

    edited = st.data_editor(
        df_ed, use_container_width=True, hide_index=True, num_rows="fixed",
        key=f"ref_editor_{fid}",
        column_config={
            "id": None,
            "Ref No": st.column_config.TextColumn("Ref No", disabled=True),
            "Açıklama": st.column_config.TextColumn("Açıklama", width="large"),
            "Ay": st.column_config.TextColumn("Ay"),
            "Yıl": st.column_config.NumberColumn("Yıl", format="%d"),
            "Kategori": st.column_config.TextColumn("Kategori"),
            "Tutar": st.column_config.NumberColumn("Tutar", format="%.2f", min_value=0.0),
            "Döviz": st.column_config.SelectboxColumn("Döviz", options=["USD", "EUR", "TL"], required=True),
        },
    )
    if st.button("💾 Değişiklikleri Kaydet", type="primary", key=f"ref_save_{fid}"):
        orijinal = {r["id"]: r for r in goster}
        degisen = 0
        for _, row in edited.iterrows():
            rid = row["id"]
            o = orijinal.get(rid, {})
            n_ack = str(row.get("Açıklama", "") or "")
            n_ay = str(row.get("Ay", "") or "")
            n_yil = int(row.get("Yıl") or 0) or None
            n_kat = str(row.get("Kategori", "") or "")
            n_tutar = float(row.get("Tutar") or 0)
            n_doviz = str(row.get("Döviz", "USD") or "USD")
            if (n_ack != (o.get("aciklama", "") or "") or n_ay != (o.get("ay", "") or "") or
                    (n_yil or 0) != int(o.get("yil") or 0) or n_kat != (o.get("kategori", "") or "") or
                    n_tutar != float(o.get("tutar") or 0) or n_doviz != (o.get("doviz", "USD") or "USD")):
                ref_guncelle(rid, str(row.get("Ref No", "")), n_ack,
                             ay=n_ay, kategori=n_kat, tutar=n_tutar, doviz=n_doviz, yil=n_yil)
                degisen += 1
        st.success(f"✅ {degisen} kayıt güncellendi." if degisen else "Değişiklik yok.")
        if degisen:
            st.rerun()


# ── SEKME 2: HAVUZ BÜTÇE ────────────────────────────────────────────
def _render_butce(fid, firma):
    kayitlar = get_butce(fid)
    giris = sum(_f(r.get("tutar")) for r in kayitlar if r.get("yon") == "giris")
    harcama = sum(_f(r.get("tutar")) for r in kayitlar if r.get("yon") != "giris")
    kalan = giris - harcama

    metrik_satiri([
        {"label": "Toplam Bütçe (giriş)", "value": f"${giris:,.2f}", "renk": "#34D399"},
        {"label": "Toplam Harcama", "value": f"${harcama:,.2f}", "renk": "#F87171"},
        {"label": "Kalan Havuz", "value": f"${kalan:,.2f}", "renk": "#A5B4FC"},
    ])

    # ── Yeni kayıt ekle ──
    with st.expander("➕ Yeni Bütçe / Harcama Kaydı Ekle"):
        ref_secenek = [""] + [r.get("ref_no", "") for r in get_refler(fid)]
        with st.form(f"butce_ekle_{fid}", clear_on_submit=True):
            b1, b2, b3, b3b = st.columns([1.3, 1.1, 1, 0.9])
            b_tur = b1.selectbox("Tür", BUTCE_TURLER, index=0,
                                 help="BÜTÇE genelde giriş; sağdaki Yön ile kesinleştir")
            b_yon = b2.selectbox("Yön", ["harcama", "giris"],
                                 format_func=lambda y: "Giriş (+)" if y == "giris" else "Harcama (−)",
                                 help="Önden verilen bütçe = Giriş; sellout/destek = Harcama")
            b_tutar = b3.number_input("Tutar", min_value=0.0, value=0.0, step=100.0)
            b_doviz = b3b.selectbox("Döviz", ["USD", "EUR", "TL"], index=0)
            b_ack = st.text_input("Açıklama", placeholder="örn. TEMMUZ FAZEON SELLOUT")
            b4, b5, b6 = st.columns(3)
            b_fno = b4.text_input("Fatura No", placeholder="örn. UYSD-8459")
            b_ftar = b5.date_input("Fatura Tarihi", value=date.today())
            b_ref = b6.selectbox("Ref No", ref_secenek, index=0)
            b_kisi = st.text_input("Kişi / Sorumlu", placeholder="örn. DERYA MOLLAOĞLU")
            if st.form_submit_button("➕ Kaydı Ekle", type="primary", use_container_width=True):
                ok, msg = butce_ekle(fid, b_tur, b_ack.strip(), b_tutar, b_doviz,
                                     b_fno.strip(), b_ftar, b_ref, b_kisi.strip(), yon=b_yon)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    # ── Excel içe aktar ──
    with st.expander("📥 Excel'den İçe Aktar (Havuz Bütçe formatı)"):
        st.caption("Sütunlar: TÜR · MARKA · AÇIKLAMA · HAKEDİŞ BÜTÇE · TUTAR · DÖVİZ · FATURA NO · FATURA TARİH · FİRMA · REF NO · AÇIKLAMA(kişi)")
        upb = st.file_uploader("Havuz bütçe Excel'i", type=["xlsx", "xls"], key=f"butce_up_{fid}")
        temizle = st.checkbox("Önce mevcut bütçe kayıtlarını sil (güncel listeyi baştan yükle)",
                              key=f"butce_temizle_{fid}")
        if upb is not None:
            try:
                df_b = pd.read_excel(upb)
                st.dataframe(df_b.head(15), use_container_width=True, height=200)
                if st.button("📥 İçe Aktar", type="primary", key=f"butce_imp_{fid}"):
                    ok, msg, _n = butce_excel_ice_aktar(fid, df_b, temizle=temizle)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")

    if not kayitlar:
        st.info("Bu firma için henüz havuz bütçe kaydı yok. Yukarıdan ekleyebilir veya Excel'den içe aktarabilirsiniz.")
        return

    # ── Hareket defteri (düzenlenebilir) ──
    st.markdown("##### 📋 Destek Kayıtları (düzenle / sil)")
    ara = st.text_input("🔍 Ara (açıklama / fatura / ref / kişi)", key=f"butce_ara_{fid}").strip().lower()

    def _eslesir(r):
        if not ara:
            return True
        return ara in (str(r.get("aciklama", "")) + " " + str(r.get("fatura_no", "")) + " " +
                       str(r.get("ref_no", "")) + " " + str(r.get("kisi", "")) + " " +
                       str(r.get("tur", ""))).lower()

    goster = [r for r in kayitlar if _eslesir(r)]
    st.caption(f"{len(goster)} / {len(kayitlar)} kayıt")

    df_b = pd.DataFrame([{
        "id": r["id"], "Sil?": False, "Tür": r.get("tur", "") or "",
        "Yön": r.get("yon", "harcama") or "harcama",
        "Açıklama": r.get("aciklama", "") or "", "Tutar": _f(r.get("tutar")),
        "Fatura No": r.get("fatura_no", "") or "", "Tarih": str(r.get("fatura_tarih") or ""),
        "Ref No": r.get("ref_no", "") or "", "Kişi": r.get("kisi", "") or "",
    } for r in goster])

    edited = st.data_editor(
        df_b, use_container_width=True, hide_index=True, num_rows="fixed",
        key=f"butce_editor_{fid}_{ara}",
        column_config={
            "id": None,
            "Sil?": st.column_config.CheckboxColumn("Sil?", width="small"),
            "Tür": st.column_config.TextColumn("Tür"),
            "Yön": st.column_config.SelectboxColumn("Yön", options=["giris", "harcama"],
                                                    required=True, width="small",
                                                    help="giris = bütçe girişi (+), harcama = destek (−)"),
            "Açıklama": st.column_config.TextColumn("Açıklama", width="large"),
            "Tutar": st.column_config.NumberColumn("Tutar ($)", format="%.2f"),
            "Fatura No": st.column_config.TextColumn("Fatura No"),
            "Tarih": st.column_config.TextColumn("Tarih (YYYY-AA-GG)"),
            "Ref No": st.column_config.TextColumn("Ref No"),
            "Kişi": st.column_config.TextColumn("Kişi"),
        },
    )
    if st.button("💾 Değişiklikleri Kaydet", type="primary", key=f"butce_save_{fid}"):
        orijinal = {r["id"]: r for r in goster}
        silinen = degisen = 0
        for _, row in edited.iterrows():
            rid = row["id"]
            if bool(row.get("Sil?")):
                if butce_sil(rid):
                    silinen += 1
                continue
            o = orijinal.get(rid, {})
            n_tur = str(row.get("Tür", "") or "")
            n_yon = str(row.get("Yön", "harcama") or "harcama")
            n_ack = str(row.get("Açıklama", "") or "")
            n_tut = _f(row.get("Tutar"))
            n_fno = str(row.get("Fatura No", "") or "")
            n_tar = (str(row.get("Tarih", "") or "").strip() or None)
            n_ref = str(row.get("Ref No", "") or "")
            n_kisi = str(row.get("Kişi", "") or "")
            if (n_tur != (o.get("tur", "") or "") or n_yon != (o.get("yon", "") or "") or
                    n_ack != (o.get("aciklama", "") or "") or
                    abs(n_tut - _f(o.get("tutar"))) > 0.001 or n_fno != (o.get("fatura_no", "") or "") or
                    (n_tar or "") != (str(o.get("fatura_tarih") or "")) or
                    n_ref != (o.get("ref_no", "") or "") or n_kisi != (o.get("kisi", "") or "")):
                butce_guncelle(rid, n_tur, n_ack, n_tut, n_fno, n_tar, n_ref, n_kisi, yon=n_yon)
                degisen += 1
        st.success(f"✅ {degisen} güncellendi, {silinen} silindi." if (degisen or silinen) else "Değişiklik yok.")
        if degisen or silinen:
            st.rerun()


@st.cache_data(ttl=120, show_spinner=False)
def get_tum_butce_harcamalari(baslangic=None, bitis=None):
    """TÜM firmaların havuz HARCAMA kayıtları (verilen destekler).
    Bütçe girişleri (firma fonu) hariç tutulur. Dönem filtresi fatura_tarih'e göre.
    Döner: [{tur, tutar, doviz, fatura_tarih, marka, firma_id}, ...]."""
    try:
        rows = _rows(get_client().table("ref_butce")
                     .select("tur, yon, tutar, doviz, fatura_tarih, marka, firma_id").execute())
    except Exception:
        return []
    out = []
    for r in rows:
        _yon = str(r.get("yon", "") or "").strip().lower()
        if _yon in ("giris", "giriş"):
            continue  # firma bütçe girişi — destek değil
        if str(r.get("tur", "") or "").strip().upper() in ("BÜTÇE", "BUTCE"):
            continue
        ft = str(r.get("fatura_tarih", "") or "")[:10]
        if baslangic and ft and ft < baslangic:
            continue
        if bitis and ft and ft > bitis:
            continue
        out.append(r)
    return out


# ── "TÜM FİRMALAR" BİRLEŞİK GÖRÜNÜM ─────────────────────────────────
def _render_tumu(firmalar):
    """Tüm firmaların ref no + havuz bütçe kayıtlarını birleşik (read-only) gösterir."""
    import pandas as pd
    tum_ref, tum_butce = [], []
    for f in firmalar:
        for r in (get_refler(f["id"]) or []):
            tum_ref.append({
                "Firma": f["firma_adi"],
                "Ref No": r.get("ref_no", ""),
                "Açıklama": (r.get("aciklama", "") or "")[:50],
                "Tür": r.get("kategori", ""),
                "Tutar": _f(r.get("tutar")),
                "Döviz": r.get("doviz", ""),
                "Durum": r.get("durum", ""),
            })
        for b in (get_butce(f["id"]) or []):
            tum_butce.append({
                "Firma": f["firma_adi"],
                "Tür": b.get("tur", ""),
                "Yön": b.get("yon", ""),
                "Açıklama": (b.get("aciklama", "") or "")[:50],
                "Tutar": _f(b.get("tutar")),
                "Döviz": b.get("doviz", ""),
                "Fatura Tarihi": (b.get("fatura_tarih", "") or "")[:10],
            })

    st.markdown("#### 🌐 Tüm Firmalar — Ref No'lar")
    if tum_ref:
        st.dataframe(pd.DataFrame(tum_ref), hide_index=True, use_container_width=True)
        st.caption(f"Toplam {len(tum_ref)} ref no kaydı.")
    else:
        st.info("Henüz ref no kaydı yok.")

    st.markdown("#### 🌐 Tüm Firmalar — Havuz Bütçe")
    if tum_butce:
        st.dataframe(pd.DataFrame(tum_butce), hide_index=True, use_container_width=True)
        _giris = sum(b["Tutar"] for b in tum_butce if str(b["Yön"]).lower() in ("giris", "giriş"))
        _harc = sum(b["Tutar"] for b in tum_butce if str(b["Yön"]).lower() not in ("giris", "giriş"))
        st.caption(f"Toplam giriş: {_giris:,.0f} · Toplam harcama: {_harc:,.0f} (karışık dövizler dahil, sadece özet).")
    else:
        st.info("Henüz havuz bütçe kaydı yok.")

    st.info("ℹ️ Detaylı işlem (ekleme/düzenleme) için üstten tek bir firma seçin.")

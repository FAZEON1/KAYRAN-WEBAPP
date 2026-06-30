# -*- coding: utf-8 -*-
"""Satış & Kârlılık modülü — arayüz (USD bazlı, tek tek işlem girişi)."""
from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st

from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici, gun_ay_yil
from shared.tarih import hizli_tarih_araligi
from .database import (
    KANALLAR, get_kanallar, get_pacal_map, get_urunler, kampanya_destek_bul,
    ekle_satis, ekle_siparis, get_satislar, sil_satis, sil_siparis, guncelle_satis,
    satir_kar, ozet_hesapla, TR_TZ,
    ice_aktar_satislar, get_mevcut_siparis_nolar,
    satis_maliyet_tazele_onizle, satis_maliyet_tazele_uygula,
    ekle_iade, get_iadeler, sil_iade, ice_aktar_iadeler, iade_satis_net_ozet,
)


def _usd(x):
    try:
        return f"${float(x):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _kart(satirlar):
    return "".join(
        f'<div style="flex:1;min-width:120px;background:rgba(255,255,255,0.04);'
        f'border:1px solid rgba(148,163,184,0.2);border-radius:12px;padding:11px 15px">'
        f'<div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px">{l}</div>'
        f'<div style="font-size:17px;font-weight:800;color:{c};font-family:monospace">{v}</div></div>'
        for l, v, c in satirlar)


def _to_date(v):
    """Excel hücresinden tarih çıkar (seri numara veya tarih/metin)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        try:
            return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(v))).date()
        except Exception:
            return None
    try:
        return pd.to_datetime(v, dayfirst=True).date()
    except Exception:
        return None


def _parse_mikro_satislar(dosya):
    """Mikro fatura dökümünü oku → (satirlar, ozet, hata).

    Gerekli sütunlar: Fatura no, Tarih, Cari adı, Hesap kodu, Hesap ismi, Mik, Net Br.fy.
    Toplam/footer satırları (Hesap kodu boş) otomatik elenir.
    """
    try:
        df = pd.read_excel(dosya, sheet_name=0)
    except Exception as e:
        return [], {}, f"Dosya okunamadı: {type(e).__name__}: {str(e)[:120]}"
    df.columns = [str(c).strip() for c in df.columns]
    gerekli = ["Fatura no", "Tarih", "Cari adı", "Hesap kodu", "Hesap ismi", "Mik", "Net Br.fy."]
    eksik = [c for c in gerekli if c not in df.columns]
    if eksik:
        return [], {}, "Beklenen sütunlar bulunamadı: " + ", ".join(eksik)
    has_belge = "Belge No" in df.columns
    has_carik = "Cari kodu" in df.columns

    satirlar = []
    tarih_min = tarih_max = None
    toplam_ciro = 0.0
    fatura_set = set()
    for _, r in df.iterrows():
        hk = str(r.get("Hesap kodu") or "").strip()
        if not hk or hk.lower() == "nan":
            continue  # toplam/footer satırı
        try:
            adet = int(float(r.get("Mik") or 0))
        except Exception:
            adet = 0
        if adet <= 0:
            continue
        try:
            bf = float(r.get("Net Br.fy.") or 0)
        except Exception:
            bf = 0.0
        d = _to_date(r.get("Tarih"))
        sno = str(r.get("Fatura no") or "").strip()
        cari = str(r.get("Cari adı") or "").strip()
        belge = str(r.get("Belge No") or "").strip() if has_belge else ""
        carik = str(r.get("Cari kodu") or "").strip() if has_carik else ""
        not_parca = []
        if belge and belge.lower() != "nan":
            not_parca.append(f"Belge: {belge}")
        if carik and carik.lower() != "nan":
            not_parca.append(f"Cari kodu: {carik}")
        satirlar.append({
            "tarih": d.isoformat() if d else "",
            "kanal": cari,
            "sku": hk,
            "urun_adi": str(r.get("Hesap ismi") or "").strip(),
            "adet": adet,
            "birim_satis": bf,
            "siparis_no": sno,
            "notlar": " · ".join(not_parca),
        })
        if sno:
            fatura_set.add(sno)
        toplam_ciro += adet * bf
        if d:
            tarih_min = d if tarih_min is None or d < tarih_min else tarih_min
            tarih_max = d if tarih_max is None or d > tarih_max else tarih_max
    ozet = {
        "satir": len(satirlar),
        "fatura": len(fatura_set),
        "ciro": toplam_ciro,
        "tarih_min": tarih_min,
        "tarih_max": tarih_max,
        "fatura_set": fatura_set,
    }
    return satirlar, ozet, None


def _siparis_excel_oku(dosya):
    """Sipariş Excel'inin tüm sayfalarını okur, her birinin türünü algılar.
    Döner: ([{sayfa, tur, df}], hata). tur ∈ {VATAN, İTOPYA, ?}."""
    try:
        xls = pd.ExcelFile(dosya)
    except Exception as e:
        return None, f"Dosya okunamadı: {type(e).__name__}: {str(e)[:120]}"
    sonuc = []
    for sn in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sn)
            df.columns = [str(c).strip() for c in df.columns]
        except Exception:
            continue
        kols = set(df.columns)
        if {"Sipariş Numarası", "Stok Kodu", "Birim Fiyat", "Miktar"}.issubset(kols):
            tur = "VATAN"
        elif {"STOKKODU", "SONALFIYAT", "MIKTAR"}.issubset(kols):
            tur = "İTOPYA"
        else:
            tur = "?"
        sonuc.append({"sayfa": sn, "tur": tur, "df": df})
    return sonuc, None


def _vatan_satirlar(df, kanal, urun_map):
    """VATAN şablonu → satış kalemleri. Sipariş no + tarih Excel'den gelir."""
    out = []
    for _, r in df.iterrows():
        sku = str(r.get("Stok Kodu") or "").strip()
        if not sku or sku.lower() == "nan":
            continue
        try:
            adet = int(float(r.get("Miktar") or 0))
        except Exception:
            adet = 0
        if adet <= 0:
            continue
        try:
            bf = float(r.get("Birim Fiyat") or 0)
        except Exception:
            bf = 0.0
        d = _to_date(r.get("Sipariş Tarih"))
        sno = str(r.get("Sipariş Numarası") or "").strip()
        if sno.endswith(".0"):
            sno = sno[:-2]
        out.append({
            "tarih": d.isoformat() if d else "",
            "kanal": kanal, "sku": sku,
            "urun_adi": (urun_map.get(sku, {}).get("urun_adi") or ""),
            "adet": adet, "birim_satis": bf,
            "siparis_no": sno, "notlar": "",
        })
    return out


def _itopya_satirlar(df, kanal, tarih_iso, siparis_no, urun_map):
    """İTOPYA şablonu → satış kalemleri. Her depo satırı AYRI kalem; tarih+sipariş no dışarıdan."""
    out = []
    for _, r in df.iterrows():
        sku = str(r.get("STOKKODU") or "").strip()
        if not sku or sku.lower() == "nan":
            continue
        try:
            adet = int(float(r.get("MIKTAR") or 0))
        except Exception:
            adet = 0
        if adet <= 0:
            continue
        try:
            bf = float(r.get("SONALFIYAT") or 0)
        except Exception:
            bf = 0.0
        depo = str(r.get("DEPOTANIM") or "").strip()
        out.append({
            "tarih": tarih_iso, "kanal": kanal, "sku": sku,
            "urun_adi": (urun_map.get(sku, {}).get("urun_adi") or ""),
            "adet": adet, "birim_satis": bf,
            "siparis_no": siparis_no,
            "notlar": (f"Depo: {depo}" if depo and depo.lower() != "nan" else ""),
        })
    return out


def iade_excel_oku(dosya):
    """İade Excel'inden SADECE iade kalemlerini ayıklar (cari başlık satırlarını atlar,
    iade adedi 0 olanları almaz; satış kolonlarına dokunmaz). Döner: (satirlar, hata)."""
    df = pd.read_excel(dosya, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]

    def _bul(*adlar):
        for a in adlar:
            for c in df.columns:
                if str(c).strip().lower() == a.lower():
                    return c
        return None

    k_sku = _bul("Stok kodu", "SKU")
    k_ad = _bul("Stok ismi", "Stok adı", "Ürün adı")
    k_smik = _bul("Satış miktarı")
    k_imik = _bul("İade miktar", "İade miktarı")
    k_ibrut = _bul("İade brüt tutar", "İade brüt")
    k_iisk = _bul("İade iskonto")
    k_imas = _bul("İade masraf")
    k_inet = _bul("İade net", "İade net tutar")
    if not k_sku or not k_imik:
        return [], "'Stok kodu' veya 'İade miktar' kolonu bulunamadı."
    out, firma = [], ""
    for _, row in df.iterrows():
        sku = str(row.get(k_sku, "") or "").strip()
        if not sku or sku.lower() == "nan":
            continue
        if "toplam" in sku.lower():           # cari ara/genel toplam satırı — ürün değil, mükerrer olur
            continue
        smik, imik = row.get(k_smik), row.get(k_imik)
        if pd.isna(smik) and pd.isna(imik):
            firma = sku                       # cari/firma başlık satırı
            continue
        adet = 0 if pd.isna(imik) else int(imik)
        if adet <= 0:
            continue                          # iadesi olmayan ürün

        def _say(k):
            return 0.0 if (k is None or pd.isna(row.get(k))) else float(row.get(k))

        out.append({
            "sku": sku, "urun_adi": str(row.get(k_ad, "") or "").strip(),
            "kanal": firma, "iade_adet": adet,
            "iade_brut": _say(k_ibrut), "iade_iskonto": _say(k_iisk),
            "iade_masraf": _say(k_imas), "iade_net": _say(k_inet),
        })
    return out, ""


def run():
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown("<style>.main .block-container{max-width:1200px !important;}</style>",
                unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(sidebar_stil(), unsafe_allow_html=True)
        st.markdown(sidebar_baslik("💰", "Satış", "Satış & Kârlılık"), unsafe_allow_html=True)
        if aktif_kullanici:
            st.markdown(sidebar_kullanici(aktif_kullanici), unsafe_allow_html=True)
            if st.button("Çıkış Yap", use_container_width=True, key="satis_cikis"):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.session_state.aktif_uygulama = "anasayfa"
                st.rerun()

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        _ssayfa = st.radio("Sayfa", ["🧾 Satış Girişi", "📋 Satışlar", "📊 Kâr / P&L",
                                     "📥 İçe Aktar", "↩️ İade"],
                           label_visibility="collapsed", key="satis_sayfa")

    st.caption("Her şey **USD**. Maliyet = güncel paçal (ağırlıklı ortalama landed), kayıt anında sabitlenir.")

    _ice_mesaj = st.session_state.pop("_ice_mesaj", None)
    if _ice_mesaj:
        st.success(_ice_mesaj)
        st.caption("Kâr/P&L sekmesinde tarih aralığını **01.01.2025 – 31.12.2025** seçerek "
                   "tüm yılı görebilirsin (varsayılan sadece son 30 gün).")

    _kanallar = get_kanallar()

    # ───────────────────────── SATIŞ GİRİŞİ ─────────────────────────
    if _ssayfa == "🧾 Satış Girişi":
        pacal = get_pacal_map()
        urunler = get_urunler()
        urun_map = {u["sku"]: u for u in urunler if u.get("sku")}
        tum_sku = sorted(set(urun_map.keys()) | set(pacal.keys()))
        st.session_state.setdefault("satis_kalemler", [])
        kalemler = st.session_state.satis_kalemler

        if not tum_sku:
            st.info("Henüz ürün/maliyet verisi yok. Önce İthalat/Ürün Yönetimi'nden ürün ve maliyet girilmeli.")
        else:
            # ── Excel ile toplu sipariş girişi (VATAN / İTOPYA) ──
            with st.expander("📄 Excel ile Toplu Sipariş Girişi (VATAN / İTOPYA)"):
                st.caption("VATAN veya İTOPYA sipariş şablonunu yükle. Maliyet paçaldan otomatik gelir, "
                           "aynı sipariş no tekrar yüklenirse atlanır.")
                _sg_dosya = st.file_uploader("Sipariş Excel'i (.xlsx / .xls)",
                                             type=["xlsx", "xls"], key="sg_excel")
                if _sg_dosya is not None:
                    _sayfalar, _sg_hata = _siparis_excel_oku(_sg_dosya)
                    if _sg_hata:
                        st.error(_sg_hata)
                    elif not _sayfalar:
                        st.warning("Dosyada sayfa bulunamadı.")
                    else:
                        _tum_satir = []
                        for _sf in _sayfalar:
                            _tur, _df, _ad = _sf["tur"], _sf["df"], _sf["sayfa"]
                            if _tur == "?":
                                st.caption(f"⚠️ **{_ad}**: tanınmayan format, atlandı.")
                                continue
                            st.markdown(f"**{_ad}** — {_tur} formatı")
                            _vk = 0
                            for _ik, _kn in enumerate(_kanallar):
                                _u = _kn.upper()
                                if _tur == "VATAN" and "VATAN" in _u:
                                    _vk = _ik
                                    break
                                if _tur == "İTOPYA" and ("EERA" in _u or "ITOPYA" in _u or "İTOPYA" in _u):
                                    _vk = _ik
                                    break
                            _kanal = st.selectbox("Kanal (cari)", _kanallar,
                                                  index=_vk if _kanallar else 0, key=f"sg_kanal_{_ad}")
                            if _tur == "İTOPYA":
                                _c1, _c2 = st.columns(2)
                                _itarih = _c1.date_input("Sipariş Tarihi", value=date.today(),
                                                         key=f"sg_tarih_{_ad}")
                                _isno = _c2.text_input("Sipariş No", key=f"sg_sno_{_ad}",
                                                       placeholder="örn. ITOPYA-2026-06-29").strip()
                                _sat = _itopya_satirlar(_df, _kanal, _itarih.isoformat(), _isno, urun_map)
                                if not _isno:
                                    st.caption("⚠️ Bu sayfa için Sipariş No girilmeli (boşsa kaydedilmez).")
                            else:
                                _sat = _vatan_satirlar(_df, _kanal, urun_map)
                            _adet = sum(s["adet"] for s in _sat)
                            _ciro = sum(s["adet"] * s["birim_satis"] for s in _sat)
                            st.caption(f"{len(_sat)} kalem • {_adet:,} adet • {_usd(_ciro)}")
                            _tum_satir.extend(_sat)

                        _gecerli = [s for s in _tum_satir if s.get("siparis_no") and s.get("tarih")]
                        _eksik = len(_tum_satir) - len(_gecerli)
                        if _eksik:
                            st.caption(f"⚠️ {_eksik} kalem sipariş no/tarih eksik — kaydedilmeyecek.")
                        if st.button("📥 Siparişleri Kaydet", type="primary",
                                     use_container_width=True, key="sg_kaydet",
                                     disabled=not _gecerli):
                            _sonuc = ice_aktar_satislar(_gecerli, atla_mevcut=True, temizle_once=False)
                            if _sonuc["hata"] and _sonuc["eklendi"] == 0:
                                st.error(f"❌ {_sonuc['hata']}")
                            else:
                                _m = f"✅ {_sonuc['eklendi']:,} kalem kaydedildi."
                                if _sonuc["atlandi"]:
                                    _m += f" {_sonuc['atlandi']:,} atlandı (zaten kayıtlı)."
                                if _sonuc["maliyetsiz"]:
                                    _m += f" {_sonuc['maliyetsiz']:,} kalemde paçal maliyet yok (maliyet 0)."
                                if _sonuc.get("hatali"):
                                    _m += f" ⚠️ {_sonuc['hatali']:,} kalem yazılamadı."
                                st.session_state["_ice_mesaj"] = _m
                                try:
                                    st.cache_data.clear()
                                except Exception:
                                    pass
                                st.rerun()

            # ── Sipariş başlığı ──
            with st.container(border=True):
                st.markdown("##### 🧾 Sipariş Bilgileri")
                h1, h2, h3 = st.columns([1, 1.4, 1])
                g_tarih = h1.date_input("Tarih", value=date.today(), key="s_tarih")
                g_kanal = h2.selectbox("Kanal / Cari", _kanallar, key="s_kanal",
                                       help="Muhasebe'ye yüklediğin cari listesinden gelir (yoksa varsayılan).")
                g_sipno = h3.text_input("Sipariş No (ops.)", key="s_sipno", placeholder="boşsa otomatik")
                g_not = st.text_input("Sipariş notu (ops.)", key="s_not")

            # ── Kalem ekle ──
            with st.container(border=True):
                st.markdown("##### ➕ Ürün Kalemi Ekle")
                _sku_opts = [f"{s} — {urun_map.get(s, {}).get('urun_adi', '') or ''}".strip(" —") for s in tum_sku]
                a1, a2, a3, a4 = st.columns([2.6, 0.9, 1.1, 1.1])
                _sec = a1.selectbox("Ürün (SKU ara)", _sku_opts, key="s_sku_sec", label_visibility="collapsed",
                                    placeholder="SKU / ürün ara")
                _sku = tum_sku[_sku_opts.index(_sec)] if _sec in _sku_opts else (tum_sku[0] if tum_sku else "")
                _urun = urun_map.get(_sku, {})
                _pacal = float(pacal.get(_sku, 0) or 0)
                _liste = _urun.get("satis_fiyat_listesi") or {}
                if isinstance(_liste, dict):
                    _oneri = float(_liste.get(g_kanal) or _liste.get(str(g_kanal).upper()) or _urun.get("satis_fiyati") or 0)
                else:
                    _oneri = float(_urun.get("satis_fiyati") or 0)
                _adet = a2.number_input("Adet", min_value=1, step=1, value=1, key="s_adet", label_visibility="collapsed")
                _bsat = a3.number_input("Birim Satış $", min_value=0.0, step=0.01, format="%.2f",
                                        value=round(_oneri, 2) if _oneri > 0 else None, placeholder="Satış $",
                                        key="s_bsat", label_visibility="collapsed")
                if a4.button("➕ Ekle", use_container_width=True, key="s_ekle"):
                    if not _bsat or _bsat <= 0:
                        st.warning("Birim satış fiyatı gir.")
                    else:
                        _kfd, _ked, _kid = kampanya_destek_bul(_sku, g_kanal, str(g_tarih))
                        kalemler.append({
                            "sku": _sku, "urun_adi": _urun.get("urun_adi", "") or "",
                            "adet": int(_adet), "birim_satis": float(_bsat),
                            "birim_maliyet": round(_pacal, 4), "birim_firma_destek": round(_kfd, 4),
                            "birim_ek_destek": round(_ked, 4), "kampanya_id": _kid,
                        })
                        st.session_state.satis_kalemler = kalemler
                        st.rerun()
                _ipucu = []
                _ipucu.append(f"Maliyet (paçal): {_usd(_pacal)}" if _pacal > 0 else "⚠️ Paçal maliyet yok — kalemde elle düzelt")
                a3.caption(_ipucu[0])

            # ── Sepet (kalemler) ──
            if not kalemler:
                st.info("Henüz kalem eklenmedi. Yukarıdan ürün ekleyerek siparişi oluştur.")
            else:
                st.markdown("##### 🛒 Sipariş Kalemleri — düzenle / sil")
                _df = pd.DataFrame([{
                    "Sil": False, "SKU": k["sku"], "Ürün": (k["urun_adi"] or "")[:30],
                    "Adet": int(k["adet"]), "B.Satış$": float(k["birim_satis"]),
                    "Maliyet$": float(k["birim_maliyet"]), "Firma Destek$": float(k["birim_firma_destek"]),
                    "Ek Destek$": float(k["birim_ek_destek"]),
                } for k in kalemler])
                _ed = st.data_editor(
                    _df, hide_index=True, use_container_width=True, num_rows="fixed",
                    key=f"satis_cart_{len(kalemler)}",
                    column_config={
                        "Sil": st.column_config.CheckboxColumn("🗑", width="small"),
                        "SKU": st.column_config.TextColumn("SKU", disabled=True),
                        "Ürün": st.column_config.TextColumn("Ürün", disabled=True),
                        "Adet": st.column_config.NumberColumn("Adet", min_value=0, step=1),
                        "B.Satış$": st.column_config.NumberColumn("B.Satış $", min_value=0.0, format="%.2f"),
                        "Maliyet$": st.column_config.NumberColumn("Maliyet $", min_value=0.0, format="%.2f"),
                        "Firma Destek$": st.column_config.NumberColumn("Firma Destek $", min_value=0.0, format="%.2f"),
                        "Ek Destek$": st.column_config.NumberColumn("Ek Destek $", min_value=0.0, format="%.2f"),
                    },
                )
                # Düzenlemeleri session'a yansıt + Sil işaretlileri çıkar
                _yeni = []
                for i, row in _ed.iterrows():
                    if bool(row.get("Sil")):
                        continue
                    k = dict(kalemler[i])
                    k["adet"] = int(row["Adet"] or 0)
                    k["birim_satis"] = float(row["B.Satış$"] or 0)
                    k["birim_maliyet"] = float(row["Maliyet$"] or 0)
                    k["birim_firma_destek"] = float(row["Firma Destek$"] or 0)
                    k["birim_ek_destek"] = float(row["Ek Destek$"] or 0)
                    _yeni.append(k)
                if _yeni != kalemler:
                    st.session_state.satis_kalemler = _yeni
                    st.rerun()
                kalemler = _yeni

                # ── Sipariş özeti (canlı) ──
                top, _, _ = ozet_hesapla(kalemler)
                _renk = "#34D399" if top["net_kar"] > 0 else ("#F87171" if top["net_kar"] < 0 else "#94A3B8")
                st.markdown(
                    '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 6px">' + _kart([
                        ("Kalem / Adet", f"{len(kalemler)} / {int(top['adet']):,}", "#93C5FD"),
                        ("Ciro", _usd(top["ciro"]), "#CBD5E1"),
                        ("Maliyet", _usd(top["maliyet"]), "#FB923C"),
                        ("Destek", _usd(top["destek"]), "#A78BFA"),
                        ("Net Kâr", _usd(top["net_kar"]), _renk),
                        ("Net Kârlılık", f"%{top['marj']:.1f}", _renk),
                    ]) + '</div>', unsafe_allow_html=True)

                b1, b2 = st.columns([3, 1])
                if b1.button("💾 Siparişi Kaydet", type="primary", use_container_width=True, key="s_kaydet"):
                    gecerli = [k for k in kalemler if k.get("sku") and int(k.get("adet", 0)) > 0
                               and float(k.get("birim_satis", 0)) > 0]
                    if not gecerli:
                        st.warning("Kaydedilecek geçerli kalem yok (adet ve satış > 0 olmalı).")
                    else:
                        # ── Akıllı kontroller: geçersiz SKU engeller; stok/zarar/mükerrer uyarır ──
                        from shared.dogrula import zararina_mi, gecerli_sku
                        _engel, _uyari, _sku_adet = [], [], {}
                        for k in gecerli:
                            _sku_adet[k["sku"]] = _sku_adet.get(k["sku"], 0) + int(k.get("adet", 0))
                            if not gecerli_sku(k["sku"], tum_sku):
                                _engel.append(f"Geçersiz SKU: {k['sku']}")
                            if zararina_mi(k.get("birim_satis"), k.get("birim_maliyet")):
                                _uyari.append(f"Zararına satış: {k['sku']} "
                                              f"(satış {_usd(k['birim_satis'])} < maliyet {_usd(k['birim_maliyet'])})")
                        try:
                            from kayranpm.database import canli_stok
                            for _sk, _ad in _sku_adet.items():
                                _cs = canli_stok(_sk)
                                if _cs.get("var") and _ad > _cs["canli"]:
                                    _uyari.append(f"Stok yetersiz: {_sk} "
                                                  f"(canlı {_cs['canli']:.0f}, satılacak {_ad})")
                        except Exception:
                            pass
                        try:
                            from satis.database import siparis_no_var_mi
                            if (g_sipno or "").strip() and siparis_no_var_mi(g_sipno):
                                _uyari.append(f"Sipariş no '{(g_sipno or '').strip()}' daha önce kullanılmış.")
                        except Exception:
                            pass

                        if _engel:
                            for _e in _engel:
                                st.error("⛔ " + _e)
                            st.info("Geçersiz SKU düzeltilmeden sipariş kaydedilemez.")
                        else:
                            for _u in _uyari:
                                st.warning("⚠️ " + _u)
                            sipno = (g_sipno or "").strip() or f"S{datetime.now(TR_TZ).strftime('%y%m%d-%H%M%S')}"
                            ok, msg, n = ekle_siparis(g_tarih, g_kanal, sipno, g_not, gecerli)
                            if ok:
                                st.success(f"{msg} · Sipariş No: {sipno} · Net kâr: {_usd(top['net_kar'])}")
                                st.session_state.satis_kalemler = []
                                for _k in ("s_sipno", "s_not", "s_adet", "s_bsat"):
                                    st.session_state.pop(_k, None)
                                if not _uyari:
                                    st.rerun()  # uyarı yoksa temiz yenile; varsa mesajlar ekranda kalsın
                            else:
                                st.error(msg)
                if b2.button("🧹 Temizle", use_container_width=True, key="s_temizle"):
                    st.session_state.satis_kalemler = []
                    st.rerun()

    # ───────────────────────── SATIŞLAR ─────────────────────────
    elif _ssayfa == "📋 Satışlar":
        _bas, _bit = hizli_tarih_araligi("l", varsayilan="Son 30 gün")
        _kanal_f = st.selectbox("Kanal", ["Tümü"] + _kanallar, key="l_kanal")

        satislar = get_satislar(_bas, _bit)
        if _kanal_f != "Tümü":
            satislar = [s for s in satislar if (s.get("kanal") or "") == _kanal_f]

        if not satislar:
            st.info("Bu aralıkta satış kaydı yok.")
        else:
            _rows_disp = []
            for s in satislar:
                k = satir_kar(s)
                _rows_disp.append({
                    "id": s.get("id"), "Tarih": pd.to_datetime(s.get("tarih"), errors="coerce"),
                    "Sipariş No": s.get("siparis_no", "") or "—", "Kanal": s.get("kanal", ""),
                    "SKU": s.get("sku", ""), "Ürün": (s.get("urun_adi", "") or "")[:30],
                    "Adet": k["adet"], "B.Satış": _usd(s.get("birim_satis")),
                    "B.Maliyet": _usd(s.get("birim_maliyet")),
                    "Destek": _usd((s.get("birim_firma_destek") or 0) + (s.get("birim_ek_destek") or 0)) if (s.get("birim_firma_destek") or s.get("birim_ek_destek")) else "—",
                    "Ciro": _usd(k["ciro"]), "Net Kâr": _usd(k["net_kar"]), "Marj": f"%{k['marj']:.1f}",
                })
            st.dataframe(pd.DataFrame(_rows_disp), hide_index=True, use_container_width=True, height=380,
                         column_config={"id": None,
                                        "Tarih": st.column_config.DateColumn("Tarih", format="DD-MM-YYYY")})
            with st.expander("🗑️ Sil — kalem veya sipariş"):
                _ds1, _ds2 = st.columns(2)
                with _ds1:
                    _sec_sil = st.selectbox(
                        "Tek kalem sil", satislar,
                        format_func=lambda s: f"#{s.get('id')} · {gun_ay_yil(s.get('tarih'))} · {s.get('kanal','')} · {s.get('sku','')} · {s.get('adet')} ad.",
                        key="l_sil_sec")
                    if st.button("🗑️ Kalemi Sil", key="l_sil_btn"):
                        if sil_satis(_sec_sil["id"]):
                            st.success("✅ Silindi.")
                            st.rerun()
                        else:
                            st.error("Silinemedi.")
                with _ds2:
                    _sipnolar = sorted({(s.get("siparis_no") or "").strip() for s in satislar if (s.get("siparis_no") or "").strip()})
                    if _sipnolar:
                        _sec_sip = st.selectbox("Tüm siparişi sil", _sipnolar, key="l_sil_sip")
                        if st.button("🗑️ Siparişi Sil", key="l_sil_sip_btn"):
                            if sil_siparis(_sec_sip):
                                st.success(f"✅ '{_sec_sip}' siparişi silindi.")
                                st.rerun()
                            else:
                                st.error("Silinemedi.")
                    else:
                        st.caption("Sipariş no'lu kayıt yok.")

    # ───────────────────────── KÂR / P&L ─────────────────────────
    elif _ssayfa == "📊 Kâr / P&L":
        _pbas, _pbit = hizli_tarih_araligi("p_pnl", varsayilan="Bu yıl")

        satislar = get_satislar(_pbas, _pbit)
        if not satislar:
            st.info("Bu aralıkta satış yok.")
        else:
            top, kanal, urun = ozet_hesapla(satislar)
            _renk = "#34D399" if top["net_kar"] > 0 else "#F87171"
            st.markdown(
                '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px">' + _kart([
                    ("Ciro", _usd(top["ciro"]), "#CBD5E1"),
                    ("Maliyet (COGS)", _usd(top["maliyet"]), "#FB923C"),
                    ("Destek", _usd(top["destek"]), "#A78BFA"),
                    ("Net Kâr", _usd(top["net_kar"]), _renk),
                    ("Marj", f"%{top['marj']:.1f}", _renk),
                    ("Adet", f"{int(top['adet']):,}", "#93C5FD"),
                ]) + '</div>', unsafe_allow_html=True)

            st.markdown("#### Kanal Kırılımı")
            _kr = sorted(kanal.items(), key=lambda x: -x[1]["net_kar"])
            st.dataframe(pd.DataFrame([{
                "Kanal": kn, "Adet": int(v["adet"]), "Ciro": _usd(v["ciro"]),
                "Net Kâr": _usd(v["net_kar"]),
                "Marj": f"%{(v['net_kar']/v['ciro']*100) if v['ciro']>0 else 0:.1f}",
            } for kn, v in _kr]), hide_index=True, use_container_width=True)

            st.markdown("#### Ürün Kırılımı (net kâra göre)")
            _ur = sorted(urun.items(), key=lambda x: -x[1]["net_kar"])
            st.dataframe(pd.DataFrame([{
                "SKU": su, "Ürün": (v["urun_adi"] or "")[:36], "Adet": int(v["adet"]),
                "Ciro": _usd(v["ciro"]), "Net Kâr": _usd(v["net_kar"]),
                "Marj": f"%{(v['net_kar']/v['ciro']*100) if v['ciro']>0 else 0:.1f}",
            } for su, v in _ur]), hide_index=True, use_container_width=True, height=320)

            st.markdown("---")
            with st.expander("🔧 Maliyeti 0 olan satışları paçaldan düzelt (%100 marj sorunu)", expanded=False):
                st.caption("Geçmişte maliyetsiz (birim maliyet 0) kaydedilmiş satışların maliyetini ithalat paçalından "
                           "yeniden yazar. SKU 'Fazeon …' yazılı olsa bile normalize edilip paçalla eşleştirilir. "
                           "Mevcut DOĞRU maliyetlere dokunmaz — yalnız 0 olanları düzeltir.")
                if st.button("🔍 Önizle — kaç satış düzelecek", key="mlyt_onizle_btn"):
                    with st.spinner("Satışlar paçalla karşılaştırılıyor…"):
                        st.session_state["_mlyt_onizle"] = satis_maliyet_tazele_onizle(sadece_sifir=True)
                _mz = st.session_state.get("_mlyt_onizle")
                if _mz is not None:
                    if not _mz:
                        st.success("Maliyeti 0 olup paçalı bilinen satış yok. Hâlâ %100 görünen SKU varsa, "
                                   "o ürünün ithalatı sistemde yok ya da SKU yazımı ithalattakiyle hiç eşleşmiyor demektir.")
                    else:
                        _mdf = pd.DataFrame([{
                            "SKU": x["sku"], "Ürün": (x["urun"] or "")[:34],
                            "Satış satırı": x["satir"], "Adet": int(x["adet"]),
                            "Yeni birim maliyet $": round(x["yeni_birim"], 2),
                        } for x in _mz])
                        st.dataframe(_mdf, hide_index=True, use_container_width=True, height=300)
                        _tsatir = sum(x["satir"] for x in _mz)
                        st.warning(f"⚠️ {len(_mz)} SKU · {_tsatir} satış satırının maliyeti güncellenecek "
                                   "(0 → paçal). Geri alınamaz.")
                        if st.button("✅ Onayla ve Maliyetleri Yaz", type="primary", use_container_width=True, key="mlyt_uygula_btn"):
                            with st.spinner("Maliyetler yazılıyor…"):
                                _okm, _msgm = satis_maliyet_tazele_uygula(sadece_sifir=True)
                            st.cache_data.clear()
                            st.session_state.pop("_mlyt_onizle", None)
                            (st.success if _okm else st.error)(_msgm)
                            st.rerun()

    # ───────────────────────── İÇE AKTAR (Excel) ─────────────────────────
    elif _ssayfa == "📥 İçe Aktar":
        st.markdown("##### 📥 Geçmiş Satışları İçe Aktar")
        st.caption("Mikro **fatura bazlı satış** dökümünü (.xls/.xlsx) yükle. "
                   "Maliyet, sistemdeki güncel **paçal** maliyetten otomatik hesaplanır. "
                   "Daha önce kaydedilmiş fatura numaraları atlanır (tekrar yüklemede mükerrer olmaz).")
        _dosya = st.file_uploader("Fatura dökümü (.xls / .xlsx)", type=["xls", "xlsx"],
                                  key="satis_ice_aktar")
        if _dosya is not None:
            _satirlar, _ozet, _hata = _parse_mikro_satislar(_dosya)
            if _hata:
                st.error(_hata)
            elif not _satirlar:
                st.warning("Dosyada geçerli satış satırı bulunamadı.")
            else:
                _ta = (f"{_ozet['tarih_min']:%d.%m.%Y} – {_ozet['tarih_max']:%d.%m.%Y}"
                       if _ozet["tarih_min"] else "—")
                st.markdown('<div style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0">' + _kart([
                    ("Satır", f"{_ozet['satir']:,}", "#93C5FD"),
                    ("Fatura", f"{_ozet['fatura']:,}", "#A5B4FC"),
                    ("Toplam Ciro", _usd(_ozet["ciro"]), "#34D399"),
                    ("Tarih Aralığı", _ta, "#FBBF24"),
                ]) + '</div>', unsafe_allow_html=True)

                _mevcut = get_mevcut_siparis_nolar()
                _cakisan = _ozet["fatura_set"] & _mevcut
                if _cakisan:
                    st.info(f"ℹ️ Bu dosyadaki **{len(_cakisan)}** fatura zaten sistemde kayıtlı. "
                            "Varsayılan olarak atlanır (yalnızca yeni faturalar eklenir).")

                _pacal = get_pacal_map()
                _maliyetsiz_sku = sorted({s["sku"] for s in _satirlar
                                          if float(_pacal.get(s["sku"], 0) or 0) <= 0})
                if _maliyetsiz_sku:
                    with st.expander(f"⚠️ Paçal maliyeti olmayan {len(_maliyetsiz_sku)} ürün "
                                     "(bu satırlarda maliyet 0 → net kâr = ciro)"):
                        st.caption(", ".join(_maliyetsiz_sku))

                with st.expander("İlk satırları gör (önizleme)"):
                    st.dataframe(pd.DataFrame(_satirlar[:8]), hide_index=True,
                                 use_container_width=True)

                _mod = st.radio(
                    "Yükleme modu",
                    ["Bu dosyadaki faturaları sıfırla ve yeniden yükle (önerilen)",
                     "Mevcut kayıtların üzerine ekle (zaten kayıtlı faturaları atla)"],
                    key="satis_ice_mod")
                _temizle_once = _mod.startswith("Bu dosyadaki")
                if _temizle_once and _cakisan:
                    st.caption(f"↻ Bu dosyadaki {len(_cakisan)} fatura önce silinip yeniden yazılacak "
                               "(eksik/kısmi kalan kayıtlar temizlenir).")
                if st.button("📥 İçe Aktar ve Kaydet", type="primary",
                             use_container_width=True, key="satis_ice_btn"):
                    _pb = st.progress(0.0, text="Kaydediliyor…")

                    def _ilerle(yapilan, toplam):
                        try:
                            _pb.progress(min(1.0, yapilan / toplam),
                                         text=f"Kaydediliyor… {yapilan}/{toplam}")
                        except Exception:
                            pass

                    _sonuc = ice_aktar_satislar(_satirlar, atla_mevcut=True,
                                                temizle_once=_temizle_once, ilerleme=_ilerle)
                    _pb.empty()
                    if _sonuc["hata"] and _sonuc["eklendi"] == 0:
                        st.error(f"❌ {_sonuc['hata']}")
                    else:
                        _msg = f"✅ {_sonuc['eklendi']:,} satış kaydedildi."
                        if _sonuc.get("silinen_fatura"):
                            _msg += f" {_sonuc['silinen_fatura']:,} eski fatura temizlendi."
                        if _sonuc["atlandi"]:
                            _msg += f" {_sonuc['atlandi']:,} satır atlandı (zaten kayıtlı)."
                        if _sonuc["maliyetsiz"]:
                            _msg += f" {_sonuc['maliyetsiz']:,} satırda paçal maliyet yok (maliyet 0)."
                        if _sonuc.get("hatali"):
                            _msg += f" ⚠️ {_sonuc['hatali']:,} satır yazılamadı ({_sonuc.get('hata')})."
                        # Tüm önbelleği temizle + sayfayı yenile ki P&L/Satışlar taze veriyi göstersin
                        st.session_state["_ice_mesaj"] = _msg
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass
                        st.rerun()

    # ───────────────────────── İADE ─────────────────────────
    elif _ssayfa == "↩️ İade":
        st.markdown("##### ↩️ İade Yönetimi")
        st.caption("İadeler satışı bozmadan AYRI tutulur; aşağıda Satış / İade / Net ayrı görünür. "
                   "Excel'den yalnızca **iade** kısmı alınır (satışlar zaten sistemde).")

        with st.expander("➕ Manuel İade Girişi", expanded=False):
            ig1, ig2, ig3 = st.columns(3)
            _i_tarih = ig1.date_input("İade tarihi", key="iade_tarih")
            _i_kanal = ig2.selectbox("Kanal / Cari", ["(Seçilmedi)"] + list(_kanallar), key="iade_kanal")
            _i_sku = ig3.text_input("Stok Kodu (SKU)", key="iade_sku")
            ig4, ig5, ig6 = st.columns(3)
            _i_ad = ig4.text_input("Ürün adı (opsiyonel)", key="iade_urunad")
            _i_adet = ig5.number_input("İade adet", min_value=1, step=1, value=1, key="iade_adet_g")
            _i_net = ig6.number_input("İade net tutar", min_value=0.0, step=1.0, format="%.2f", key="iade_net_g")
            if st.button("💾 İadeyi Kaydet", type="primary", key="iade_kaydet"):
                if not _i_sku.strip():
                    st.error("SKU zorunludur.")
                else:
                    _k = "" if str(_i_kanal).startswith("(") else _i_kanal
                    _ok, _msg = ekle_iade(str(_i_tarih)[:10], _k, _i_sku.strip(), _i_ad.strip(),
                                          int(_i_adet), iade_net=float(_i_net))
                    (st.success if _ok else st.error)(_msg)
                    if _ok:
                        st.cache_data.clear()
                        st.rerun()

        with st.expander("📄 Excel ile Toplu İade (Mikro 'iadeli satışlar' raporu)", expanded=False):
            st.caption("Rapordaki **İade** kolonları alınır; satış kolonlarına dokunulmaz. "
                       "İadesi 0 olan satırlar atlanır. Cari başlıkları otomatik tanınır.")
            _ie_dosya = st.file_uploader("İade Excel'i (.xls / .xlsx)", type=["xls", "xlsx"], key="iade_excel")
            _ie_aralik = st.date_input("Bu rapor hangi dönemi kapsıyor? (başlangıç – bitiş)",
                                       value=(date.today(), date.today()), key="iade_excel_tarih")
            if isinstance(_ie_aralik, (list, tuple)) and len(_ie_aralik) == 2:
                _ie_bas, _ie_bit = _ie_aralik
            elif isinstance(_ie_aralik, (list, tuple)) and _ie_aralik:
                _ie_bas = _ie_bit = _ie_aralik[0]
            else:
                _ie_bas = _ie_bit = _ie_aralik
            _ie_tarih = _ie_bit
            st.caption(f"İadeler dönem **bitiş** tarihine ({_ie_bit}) işlenir; özette bu dönemi seçince görünür.")
            _ie_temizle = st.checkbox("Aynı tarihli önceki iadeleri sil (tekrar yüklemede mükerrer olmasın)",
                                      value=True, key="iade_excel_temizle")
            if _ie_dosya is not None:
                try:
                    _ie_satir, _ie_hata = iade_excel_oku(_ie_dosya)
                except Exception as e:
                    _ie_satir, _ie_hata = [], f"{type(e).__name__}: {e}"
                if _ie_hata:
                    st.error(f"Okunamadı: {_ie_hata}")
                elif not _ie_satir:
                    st.warning("Dosyada iadesi olan satır bulunamadı.")
                else:
                    _tadet = sum(x["iade_adet"] for x in _ie_satir)
                    _tnet = sum(x["iade_net"] for x in _ie_satir)
                    st.success(f"{len(_ie_satir)} iade kalemi · {_tadet:,} adet · {_usd(_tnet)} bulundu.")
                    st.dataframe(pd.DataFrame([{
                        "SKU": x["sku"], "Ürün": (x["urun_adi"] or "")[:40], "Adet": x["iade_adet"],
                        "İade Net": round(x["iade_net"], 2), "Cari": (x["kanal"] or "")[:30],
                    } for x in _ie_satir[:200]]), use_container_width=True, hide_index=True)
                    if st.button("⬆️ İadeleri İçe Aktar", type="primary", key="iade_excel_btn"):
                        _r = ice_aktar_iadeler(_ie_satir, str(_ie_tarih)[:10], temizle_once=_ie_temizle)
                        if _r.get("hata"):
                            st.error(f"Hata: {_r['hata']}")
                        else:
                            st.success(f"✅ {_r['eklendi']} iade kaydedildi ({_r['atlandi']} atlandı).")
                            st.cache_data.clear()
                            st.rerun()

        st.markdown("---")
        _ib, _ibit = hizli_tarih_araligi("iade_ozet", varsayilan="Bu yıl", etiket="Özet dönemi")
        _satirlar, _top = iade_satis_net_ozet(_ib, _ibit)
        if not _satirlar:
            st.info("Bu dönemde satış/iade kaydı yok.")
        else:
            _nk_renk = "#34D399" if _top["net_kar"] > 0 else "#F87171"
            st.markdown('<div style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px">' + _kart([
                ("Satış adedi", f"{_top['s_adet']:,}", "#93C5FD"),
                ("İade adedi", f"{_top['i_adet']:,}", "#FB923C"),
                ("Net adet", f"{_top['net_adet']:,}", "#34D399"),
                ("Satış cirosu", _usd(_top["s_ciro"]), "#CBD5E1"),
                ("İade tutarı", _usd(_top["i_tutar"]), "#FB923C"),
                ("Net ciro", _usd(_top["net_ciro"]), "#34D399"),
                ("Satış kârı", _usd(_top["s_kar"]), "#A78BFA"),
                ("İade kâr kaybı", _usd(_top["i_kar"]), "#FB923C"),
                ("Net kâr", _usd(_top["net_kar"]), _nk_renk),
            ]) + '</div>', unsafe_allow_html=True)

            with st.expander("📊 SKU bazında Satış / İade / Net", expanded=True):
                _sadece_iade = st.checkbox("Yalnızca iadesi olanlar", value=True, key="iade_ozet_filtre")
                _gor = [x for x in _satirlar if x["i_adet"] > 0] if _sadece_iade else _satirlar
                st.caption(f"{len(_gor)} ürün")
                st.dataframe(pd.DataFrame([{
                    "SKU": x["sku"], "Ürün": (x["urun_adi"] or "")[:36],
                    "Satış adet": x["s_adet"], "İade adet": x["i_adet"], "Net adet": x["net_adet"],
                    "Satış ciro": round(x["s_ciro"], 2), "İade tutar": round(x["i_tutar"], 2),
                    "Net ciro": round(x["net_ciro"], 2), "Net kâr": round(x["net_kar"], 2),
                } for x in _gor]), use_container_width=True, hide_index=True)

        with st.expander("🗂️ İade Kayıtları (sil)", expanded=False):
            _kayitlar = get_iadeler(_ib, _ibit)
            if not _kayitlar:
                st.caption("Kayıt yok.")
            else:
                st.caption(f"{len(_kayitlar)} iade kaydı")
                st.dataframe(pd.DataFrame([{
                    "Tarih": (r.get("tarih") or "")[:10], "SKU": r.get("sku", ""),
                    "Ürün": (r.get("urun_adi") or "")[:34], "Adet": r.get("iade_adet", 0),
                    "İade Net": r.get("iade_net", 0), "Kanal": (r.get("kanal") or "")[:24],
                } for r in _kayitlar]), use_container_width=True, hide_index=True)
                _sil_id = st.number_input("Silinecek iade ID", min_value=0, step=1, value=0, key="iade_sil_id")
                if st.button("🗑 İadeyi Sil", key="iade_sil_btn") and _sil_id > 0:
                    if sil_iade(int(_sil_id)):
                        st.success("Silindi.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Silinemedi.")

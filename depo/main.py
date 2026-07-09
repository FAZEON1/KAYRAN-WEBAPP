"""Depo Yönetimi modülü — sidebar sayfaları: Depo Stok · Depolar Arası Sevk ·
Bekleyen Sevk Takibi (bağımsız manuel) · SKU Hareketleri (adet bazlı)."""
import streamlit as st
import pandas as pd
from datetime import date

from kayranpm.database import (get_depo_ozet, get_depo_listesi, get_depo_stok,
                               depo_sevk, get_depo_sevk_gecmisi, get_client)
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici


def _baslik(t, alt):
    # Baştaki emoji'yi ayır → ikon karosunda göster (tek standart başlık tasarımı)
    _parca = t.split(" ", 1)
    _ikon, _ad = (_parca[0], _parca[1]) if len(_parca) == 2 else ("", t)
    from shared.ui import sayfa_baslik as _sb
    st.markdown(_sb(_ikon, _ad, alt), unsafe_allow_html=True)


def run():
    with st.sidebar:
        st.markdown(sidebar_stil(), unsafe_allow_html=True)
        st.markdown(sidebar_baslik("🏬", "Depo", "Depo Yönetimi"), unsafe_allow_html=True)
        _kull = st.session_state.get("aktif_kullanici", "")
        if _kull:
            st.markdown(sidebar_kullanici(_kull), unsafe_allow_html=True)
        _dsayfa = st.radio("Sayfa", ["🏬 Depo Stok", "🚚 Depolar Arası Sevk",
                                     "📦 Bekleyen Sevk Takibi", "🔎 SKU Hareketleri",
                                     "🏭 Happy Life Kiralık Depo"],
                           label_visibility="collapsed", key="depo_sayfa")

    if _dsayfa == "🏬 Depo Stok":
        _sayfa_stok()
    elif _dsayfa == "🚚 Depolar Arası Sevk":
        _sayfa_sevk()
    elif _dsayfa == "📦 Bekleyen Sevk Takibi":
        _sayfa_bekleyen()
    elif _dsayfa == "🔎 SKU Hareketleri":
        _sayfa_sku()
    else:
        _sayfa_happylife()


# ═════════════════════════ 🏬 DEPO STOK ═════════════════════════
def _sayfa_stok():
    _baslik("🏬 Depo Stok", "Depo bazlı stok · özet kartlar · depo içeriği")
    _depolar = get_depo_listesi()
    _di_depo = st.selectbox("Depo seç", _depolar, key="dpo_icerik_depo")
    _di_urunler = get_depo_stok(_di_depo) if _di_depo else []
    if _di_urunler:
        from shared.utils import tr_buyuk as _tb
        _df = pd.DataFrame([{"SKU": _tb(u["sku"]), "Ürün": _tb(u["urun_adi"]), "Adet": u["adet"]}
                           for u in _di_urunler])
        st.caption(f"{len(_di_urunler)} çeşit · {sum(u['adet'] for u in _di_urunler):,} adet")
        st.dataframe(_df, use_container_width=True, hide_index=True)
    else:
        st.info("Bu depoda stoklu ürün yok.")


# ═════════════════════ 🚚 DEPOLAR ARASI SEVK ═════════════════════
def _sayfa_sevk():
    _baslik("🚚 Depolar Arası Sevk", "Kaynak → hedef sevk · sevk tarihi & belge no · son sevkler")
    _ozet = get_depo_ozet()
    if not _ozet:
        st.info("Henüz depo bazlı stok yok. Önce **Ürün Yönetimi → G5F Stok** Excel'ini yükle.")
        return
    st.caption("Bir kaynak ve hedef depo seç, ürünleri tek tek listeye ekle, sonra hepsini "
               "tek seferde sevk et. Aynı sevkte birden çok model taşıyabilirsin.")

    _depolar = get_depo_listesi()
    sc1, sc2 = st.columns(2)
    _kaynak = sc1.selectbox("Kaynak depo", _depolar, key="dpo_kaynak")
    _hedef_opts = [d for d in _depolar if d != _kaynak] + ["➕ Yeni depo…"]
    _hedef_sec = sc2.selectbox("Hedef depo", _hedef_opts, key="dpo_hedef")
    if _hedef_sec == "➕ Yeni depo…":
        _hedef = sc2.text_input("Yeni depo adı", key="dpo_hedef_yeni",
                                placeholder="örn. ASEL DEPO").strip()
    else:
        _hedef = _hedef_sec

    # Kaynak depo değişince listeyi sıfırla (farklı depo ürünü karışmasın)
    if st.session_state.get("_dpo_sepet_kaynak") != _kaynak:
        st.session_state["dpo_sepet"] = []
        st.session_state["_dpo_sepet_kaynak"] = _kaynak
    _sepet = st.session_state.setdefault("dpo_sepet", [])

    _kaynak_urunler = get_depo_stok(_kaynak) if _kaynak else []
    if not _kaynak_urunler:
        st.info("Bu depoda stoklu ürün yok.")

    if _kaynak_urunler:
        from shared.utils import tr_buyuk as _tb
        _urun_opts = {f'{_tb(u["sku"])} — {_tb((u["urun_adi"] or "")[:30])} ({u["adet"]} adet)': u
                      for u in _kaynak_urunler}
        ec1, ec2, ec3 = st.columns([2.4, 1, 1])
        _sec_lbl = ec1.selectbox(f"Ürün ({len(_kaynak_urunler)} stoklu)",
                                 list(_urun_opts.keys()), key="dpo_urun")
        _sec_urun = _urun_opts.get(_sec_lbl)
        _mevcut = int(_sec_urun["adet"]) if _sec_urun else 0
        _sepette = sum(s["adet"] for s in _sepet
                       if _sec_urun and s["sku"] == _sec_urun["sku"])
        _kalan = max(0, _mevcut - _sepette)
        _adet = ec2.number_input(f"Adet (kalan {_kalan})", min_value=1,
                                 max_value=max(1, _kalan), value=1, step=1, key="dpo_adet")
        ec3.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if ec3.button("➕ Listeye ekle", use_container_width=True, key="dpo_ekle"):
            if _sec_urun and _kalan >= 1:
                _bulundu = False
                for s in _sepet:
                    if s["sku"] == _sec_urun["sku"]:
                        s["adet"] += int(_adet)
                        _bulundu = True
                        break
                if not _bulundu:
                    _sepet.append({"sku": _sec_urun["sku"],
                                   "urun_adi": _sec_urun["urun_adi"],
                                   "adet": int(_adet)})
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Bu üründen eklenebilecek kalan adet yok.")

    # Sevk listesi (sepet)
    if _sepet:
        st.markdown('<div style="font-size:13px;font-weight:700;color:#94A3B8;margin:12px 0 4px;'
                    'text-transform:uppercase;letter-spacing:.5px">📋 Sevk Listesi</div>',
                    unsafe_allow_html=True)
        for _i, _s in enumerate(_sepet):
            rc1, rc2, rc3 = st.columns([3, 1, 0.5])
            rc1.markdown(f'<div style="padding:4px 0"><b style="color:#E2E8F0">{_s["sku"]}</b> '
                         f'<span style="color:#94A3B8;font-size:13px">{(_s["urun_adi"] or "")[:42]}</span></div>',
                         unsafe_allow_html=True)
            rc2.markdown(f'<div style="padding:4px 0;font-family:monospace;color:#34D399;font-weight:700">'
                         f'{_s["adet"]} adet</div>', unsafe_allow_html=True)
            if rc3.button("🗑", key=f"dpo_sil_{_i}", help="Listeden çıkar"):
                _sepet.pop(_i)
                st.cache_data.clear()
                st.rerun()
        _toplam = sum(s["adet"] for s in _sepet)
        st.caption(f"{len(_sepet)} kalem · toplam {_toplam} adet · {_kaynak} → {_hedef or '(hedef seçilmedi)'}")

        sv1, sv2 = st.columns(2)
        _sevk_tarih = sv1.date_input("Sevk Tarihi", value=date.today(), key="dpo_sevk_tarih")
        _belge_no = sv2.text_input("Belge Numarası", key="dpo_belge_no",
                                   placeholder="irsaliye / fatura / belge no")

        bc1, bc2 = st.columns([1, 1.4])
        if bc1.button("🗑 Listeyi temizle", use_container_width=True, key="dpo_temizle"):
            st.session_state["dpo_sepet"] = []
            st.cache_data.clear()
            st.rerun()
        if bc2.button("🚚 Tümünü Sevk Et", type="primary", use_container_width=True, key="dpo_sevk_hepsi"):
            if not _hedef:
                st.error("Hedef depo gerekli.")
            else:
                _ok_say, _hatalar = 0, []
                _kull = st.session_state.get("aktif_kullanici", "")
                for _s in list(_sepet):
                    _ok, _msg = depo_sevk(_s["sku"], _kaynak, _hedef, int(_s["adet"]), _kull,
                                          sevk_tarihi=str(_sevk_tarih), belge_no=_belge_no)
                    if _ok:
                        _ok_say += 1
                    else:
                        _hatalar.append(f'• {_s["sku"]}: {_msg}')
                if _ok_say:
                    st.success(f"✅ {_ok_say} kalem sevk edildi: {_kaynak} → {_hedef}")
                if _hatalar:
                    st.error("Bazı kalemler sevk edilemedi:\n" + "\n".join(_hatalar))
                st.session_state["dpo_sepet"] = []
                st.cache_data.clear()
                st.rerun()
    else:
        st.caption("Liste boş — yukarıdan ürün seçip **Listeye ekle** ile sevk listesi oluştur.")

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:15px;font-weight:800;color:#A5B4FC;margin:4px 0 8px">'
                '🕓 Son sevkler</div>', unsafe_allow_html=True)
    _gec = get_depo_sevk_gecmisi(50)
    if _gec:
        _gdf = pd.DataFrame([{
            "Tarih": (g.get("tarih") or "")[:16], "Sevk Tarihi": (g.get("sevk_tarihi") or "")[:10],
            "Belge No": g.get("belge_no", "") or "", "SKU": g.get("sku", ""),
            "Ürün": g.get("urun_adi", ""), "Kaynak": g.get("kaynak_depo", ""),
            "Hedef": g.get("hedef_depo", ""), "Adet": g.get("adet", ""),
            "Kullanıcı": g.get("kullanici", ""),
        } for g in _gec])
        st.dataframe(_gdf, use_container_width=True, hide_index=True)
    else:
        st.caption("Henüz sevk kaydı yok (veya 'depo_sevk_log' tablosu henüz oluşturulmamış).")


# ═══════════════ 📦 BEKLEYEN SEVK TAKİBİ (bağımsız · manuel) ═══════════════
def _sayfa_bekleyen():
    _baslik("📦 Bekleyen Sevk Takibi", "Faturalandı · sevk bekliyor — diğer depo hareketlerinden bağımsız, manuel")
    st.caption("Bir firmaya faturalanan toplam adet üzerinden yapılan her sevki düşerek "
               "**depoda bekleyen** miktarı izler. Örn: 100 adet faturalandı, 10 sevk edildi → 90 bekliyor.")

    def _mt_rows():
        try:
            r = get_client().table("depo_manuel_takip").select("*").order("id", desc=True).execute()
            return r.data or []
        except Exception:
            return None  # tablo yok

    _mt = _mt_rows()
    if _mt is None:
        st.warning("Bu özellik için Supabase'de bir kez şu tabloyu oluştur (SQL Editor):")
        st.code("create table depo_manuel_takip (\n"
                "  id bigint generated by default as identity primary key,\n"
                "  firma text, sku text, urun_adi text,\n"
                "  fatura_adet integer default 0,\n"
                "  sevk_edilen integer default 0,\n"
                "  hareketler jsonb default '[]'::jsonb,\n"
                "  notlar text default '',\n"
                "  olusturma timestamp default now()\n);", language="sql")
        return

    with st.expander("➕ Yeni takip kaydı (firma · ürün · faturalanan adet)", expanded=not _mt):
        y1, y2 = st.columns(2)
        _mt_firma = y1.text_input("Firma", key="mt_firma", placeholder="örn. AYKON / VATAN ...")
        _mt_sku = y2.text_input("SKU / Ürün Kodu", key="mt_sku", placeholder="örn. F1M650BBM")
        y3, y4 = st.columns(2)
        _mt_uad = y3.text_input("Ürün Adı (ops.)", key="mt_uad")
        _mt_fadet = y4.number_input("Faturalanan Adet", min_value=1, value=1, step=1, key="mt_fadet")
        _mt_not = st.text_input("Not (ops.)", key="mt_not", placeholder="fatura no / açıklama")
        if st.button("➕ Takibe Ekle", type="primary", key="mt_ekle",
                     disabled=not (_mt_firma.strip() and _mt_sku.strip())):
            try:
                get_client().table("depo_manuel_takip").insert({
                    "firma": _mt_firma.strip(), "sku": _mt_sku.strip(),
                    "urun_adi": _mt_uad.strip(), "fatura_adet": int(_mt_fadet),
                    "sevk_edilen": 0, "hareketler": [], "notlar": _mt_not.strip(),
                }).execute()
                st.success("✅ Takip kaydı oluşturuldu.")
                st.cache_data.clear()
                st.rerun()
            except Exception as _e:
                st.error(f"Kaydedilemedi: {_e}")

    if not _mt:
        st.info("Henüz takip kaydı yok — yukarıdan ilk kaydı oluştur.")
        return

    _firmalar_mt = sorted({(r.get("firma") or "").strip() for r in _mt if (r.get("firma") or "").strip()})
    _mt_ff = st.selectbox("Firma filtresi", ["Tümü"] + _firmalar_mt, key="mt_ff")
    _mt_g = [r for r in _mt if _mt_ff == "Tümü" or (r.get("firma") or "").strip() == _mt_ff]
    _mt_df = pd.DataFrame([{
        "Firma": r.get("firma", ""), "SKU": r.get("sku", ""),
        "Ürün": (r.get("urun_adi") or "")[:30],
        "Faturalanan": int(r.get("fatura_adet") or 0),
        "Sevk Edilen": int(r.get("sevk_edilen") or 0),
        "🔶 Bekleyen": int(r.get("fatura_adet") or 0) - int(r.get("sevk_edilen") or 0),
        "Not": (r.get("notlar") or "")[:30],
    } for r in _mt_g])
    if not _mt_df.empty:
        _mt_df.loc[len(_mt_df)] = ["🧮 TOPLAM", "", f"{len(_mt_g)} kayıt",
                                   int(_mt_df["Faturalanan"].sum()),
                                   int(_mt_df["Sevk Edilen"].sum()),
                                   int(_mt_df["🔶 Bekleyen"].sum()), ""]
    st.dataframe(_mt_df, use_container_width=True, hide_index=True)

    st.markdown('<div style="font-size:15px;font-weight:800;color:#A5B4FC;margin:8px 0 8px">'
                '🚚 Sevk düş (bekleyenden düşüm) / kayıt yönetimi</div>', unsafe_allow_html=True)
    _mt_sec = st.selectbox(
        "Kayıt", _mt_g,
        format_func=lambda r: (f"{r.get('firma','')} · {r.get('sku','')} · "
                               f"bekleyen {int(r.get('fatura_adet') or 0) - int(r.get('sevk_edilen') or 0)}"),
        key="mt_sec")
    if _mt_sec:
        _kalan = int(_mt_sec.get("fatura_adet") or 0) - int(_mt_sec.get("sevk_edilen") or 0)
        d1, d2, d3 = st.columns(3)
        _d_adet = d1.number_input(f"Sevk adedi (bekleyen {_kalan})", min_value=1,
                                  max_value=max(1, _kalan), value=1, step=1, key="mt_d_adet")
        _d_tarih = d2.date_input("Sevk tarihi", value=date.today(), key="mt_d_tarih")
        _d_belge = d3.text_input("Belge no (ops.)", key="mt_d_belge")
        b1, b2 = st.columns(2)
        if b1.button("🚚 Düşümü Kaydet", type="primary", key="mt_dus", disabled=_kalan <= 0):
            try:
                _hrk = list(_mt_sec.get("hareketler") or [])
                _hrk.append({"tarih": str(_d_tarih), "adet": int(_d_adet),
                             "belge_no": _d_belge.strip(),
                             "kullanici": st.session_state.get("aktif_kullanici", "")})
                get_client().table("depo_manuel_takip").update({
                    "sevk_edilen": int(_mt_sec.get("sevk_edilen") or 0) + int(_d_adet),
                    "hareketler": _hrk,
                }).eq("id", _mt_sec.get("id")).execute()
                st.success(f"✅ {int(_d_adet)} adet düşüldü.")
                st.cache_data.clear()
                st.rerun()
            except Exception as _e:
                st.error(f"Düşüm kaydedilemedi: {_e}")
        if b2.button("🗑 Kaydı Sil", key="mt_sil"):
            try:
                get_client().table("depo_manuel_takip").delete().eq("id", _mt_sec.get("id")).execute()
                st.success("Kayıt silindi.")
                st.cache_data.clear()
                st.rerun()
            except Exception as _e:
                st.error(f"Silinemedi: {_e}")
        _hrk = _mt_sec.get("hareketler") or []
        if _hrk:
            st.caption("Sevk hareketleri:")
            st.dataframe(pd.DataFrame([{
                "Tarih": h.get("tarih", ""), "Adet": h.get("adet", ""),
                "Belge No": h.get("belge_no", ""), "Kullanıcı": h.get("kullanici", ""),
            } for h in _hrk]), use_container_width=True, hide_index=True)


# ═══════════════ 🔎 SKU HAREKETLERİ (adet bazlı · tutar yok) ═══════════════
def _sayfa_sku():
    _baslik("🔎 SKU Hareketleri", "İthalat · satış · iade — yalnız adet/tarih/firma (tutar YOK)")
    # SKU listesi İTHALAT'tan gelir (ithalat kalemlerindeki tüm modeller)
    try:
        from teknikservis.database import ithalat_model_listesi
        _mods = ithalat_model_listesi()
    except Exception:
        _mods = []
    if _mods:
        from shared.utils import tr_buyuk as _tb
        _opts = ["— SKU seç —"] + [(f"{_tb(s)} — {_tb(a[:40])}" if a else _tb(s)) for s, a in _mods]
        _sec = st.selectbox(f"SKU ({len(_mods)} model · ithalattan · yazarak ara)",
                            _opts, key="sh_sku_sec")
        _sh_sku = "" if _sec == _opts[0] else _sec.split(" — ")[0].strip()
    else:
        _sh_sku = st.text_input("SKU", key="sh_sku", placeholder="örn. X24F182S").strip()
    if not _sh_sku:
        st.info("İthalattaki modellerden bir SKU seç — ithalat, satış ve iade hareketleri adet bazlı listelenecek.")
        return
    _shu = _sh_sku.upper()
    c1, c2, c3 = st.columns(3)
    # İthalat (adet · tarih)
    try:
        from ithalat.database import get_sku_ithalat_partileri
        _tum_part = get_sku_ithalat_partileri()
        _part = _tum_part.get(_shu, []) or _tum_part.get(_sh_sku, [])
    except Exception:
        _part = []
    with c1:
        st.markdown("**🚢 İthalat**")
        if _part:
            st.dataframe(pd.DataFrame([
                {"Tarih": p.get("tarih", ""), "Adet": int(p.get("adet") or 0)} for p in _part]
                + [{"Tarih": "🧮 TOPLAM", "Adet": int(sum(p.get("adet") or 0 for p in _part))}]),
                use_container_width=True, hide_index=True)
        else:
            st.caption("İthalat kaydı yok.")
    # Satış / İade (adet · tarih · firma)
    try:
        from satis.database import get_satislar, get_iadeler
        _sat = [s for s in (get_satislar() or [])
                if str(s.get("sku") or "").strip().upper() == _shu]
        _iad = [r for r in (get_iadeler() or [])
                if str(r.get("sku") or "").strip().upper() == _shu]
    except Exception:
        _sat, _iad = [], []
    with c2:
        st.markdown("**💰 Satış**")
        if _sat:
            st.dataframe(pd.DataFrame([{
                "Tarih": str(s.get("tarih") or "")[:10],
                "Firma": (s.get("kanal") or "")[:26],
                "Adet": int(s.get("adet") or 0),
            } for s in _sat] + [{"Tarih": "🧮 TOPLAM", "Firma": f"{len(_sat)} kayıt",
                                 "Adet": int(sum(int(s.get('adet') or 0) for s in _sat))}]),
                use_container_width=True, hide_index=True, height=300)
        else:
            st.caption("Satış kaydı yok.")
    with c3:
        st.markdown("**↩️ İade**")
        if _iad:
            st.dataframe(pd.DataFrame([{
                "Tarih": str(r.get("tarih") or "")[:10],
                "Firma": (r.get("kanal") or "")[:26],
                "Adet": int(r.get("iade_adet") or 0),
            } for r in _iad] + [{"Tarih": "🧮 TOPLAM", "Firma": f"{len(_iad)} kayıt",
                                 "Adet": int(sum(int(r.get('iade_adet') or 0) for r in _iad))}]),
                use_container_width=True, hide_index=True, height=300)
        else:
            st.caption("İade kaydı yok.")


# ═════════════════════════ 🏭 HAPPY LIFE KİRALIK DEPO ═════════════════════════
# Kiralık depoda (Happy Life) palet bazlı stok. Kira, stok yaşına göre ödendiği
# için stok yaşı KRİTİK. Yaş = rapor günü − giriş tarihi olarak CANLI hesaplanır
# (Excel'deki sabit yaş sayısı yok sayılır) → her gün açıldığında güncel görünür.

import io as _io
import json as _json
from datetime import datetime as _dt

_HL_TABLO = "happylife_stok"


def _hl_tarih_coz(v):
    """Excel'deki giriş tarihini ISO'ya çevirir (24.02.2026 / datetime / seri)."""
    if v is None or str(v).strip() == "":
        return None
    if isinstance(v, (_dt, date)):
        return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)[:10]
    s = str(v).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return _dt.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def _hl_yas(giris_iso, rapor_iso=None):
    """Stok yaşı (gün) = rapor tarihi − giriş tarihi. rapor yoksa bugün."""
    if not giris_iso:
        return None
    try:
        g = _dt.strptime(str(giris_iso)[:10], "%Y-%m-%d").date()
        r = _dt.strptime(str(rapor_iso)[:10], "%Y-%m-%d").date() if rapor_iso else date.today()
        return (r - g).days
    except Exception:
        return None


def hl_excel_parse(dosya):
    """Happy Life Excel'ini (G5F_Stok sayfası) okur → kayıt listesi.
    Döner: (kayitlar, hata). Yalnız istenen kolonlar + giriş tarihi tutulur."""
    try:
        xls = pd.ExcelFile(dosya)
    except Exception as e:
        return None, f"Dosya okunamadı: {type(e).__name__}: {str(e)[:120]}"
    # ham detay sayfasını bul (SKU kodu + Giriş tarihi + Palet etiketi olan)
    hedef = None
    for sn in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sn)
            df.columns = [str(c).strip() for c in df.columns]
        except Exception:
            continue
        kols = set(df.columns)
        if {"SKU kodu", "Giriş tarihi", "Palet etiketi"}.issubset(kols):
            hedef = df
            break
    if hedef is None:
        return None, "Uygun sayfa bulunamadı (SKU kodu · Giriş tarihi · Palet etiketi sütunları gerekli)."

    kayitlar = []
    for _, r in hedef.iterrows():
        sku = str(r.get("SKU kodu") or "").strip()
        if not sku or sku.lower() == "nan":
            continue
        giris = _hl_tarih_coz(r.get("Giriş tarihi"))
        def _say(x):
            try:
                return float(x or 0)
            except Exception:
                return 0.0
        kayitlar.append({
            "sku": sku,
            "sku_tanim": str(r.get("SKU tanımı") or "").strip(),
            "giris_tarihi": giris,
            "palet_etiketi": str(r.get("Palet etiketi") or "").strip(),
            "miktar": _say(r.get("Miktar")),
            "birim": str(r.get("Birim") or "").strip(),
            "miktar2": _say(r.get("Miktar-2")),
            "birim2": str(r.get("Birim.1") or r.get("Birim") or "").strip(),
        })
    return kayitlar, None


def hl_kaydet(kayitlar, rapor_tarihi=None):
    """Kayıtları DB'ye yazar. Aynı rapor tarihindeki eski kayıtları silip
    yeniden yazar (idempotent) → aynı günü iki kez yüklersen mükerrer olmaz."""
    rapor = str(rapor_tarihi or date.today().isoformat())[:10]
    try:
        sb = get_client()
        try:
            sb.table(_HL_TABLO).delete().eq("rapor_tarihi", rapor).execute()
        except Exception:
            pass
        rows = [dict(k, rapor_tarihi=rapor) for k in kayitlar]
        for i in range(0, len(rows), 200):
            sb.table(_HL_TABLO).insert(rows[i:i + 200]).execute()
        return True, f"✅ {len(rows)} palet kaydı yüklendi ({rapor})."
    except Exception as e:
        return False, f"❌ {type(e).__name__}: {str(e)[:160]}"


@st.cache_data(ttl=60, show_spinner=False)
def hl_rapor_tarihleri():
    """Yüklenmiş rapor tarihleri (yeniden eskiye)."""
    try:
        r = get_client().table(_HL_TABLO).select("rapor_tarihi").execute()
        return sorted({str(x["rapor_tarihi"])[:10] for x in (r.data or [])}, reverse=True)
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def hl_get_stok(rapor_tarihi=None):
    """Bir rapor tarihinin palet kayıtları. rapor yoksa en son yükleme."""
    try:
        sb = get_client()
        if not rapor_tarihi:
            _tarihler = hl_rapor_tarihleri()
            if not _tarihler:
                return []
            rapor_tarihi = _tarihler[0]
        r = (sb.table(_HL_TABLO).select("*")
             .eq("rapor_tarihi", str(rapor_tarihi)[:10]).execute())
        return r.data or []
    except Exception:
        return []


def _sayfa_happylife():
    _baslik("🏭 Happy Life Kiralık Depo",
            "Palet bazlı stok · stok yaşı tarihe göre canlı hesaplanır (kira takibi)")

    # ── Excel yükleme ──
    with st.expander("📥 Günlük Excel Yükle (G5F_Stok)", expanded=False):
        st.caption("Happy Life'tan gelen günlük stok Excel'ini yükle. Stok yaşı, Excel'deki "
                   "sabit sayı yerine **giriş tarihine göre her gün otomatik güncellenir** — "
                   "yani yüklemesen bile yaş bugüne göre doğru kalır.")
        up = st.file_uploader("Excel dosyası", type=["xlsx", "xls"], key="hl_upload")
        _rapor = st.date_input("Rapor tarihi", value=date.today(), key="hl_rapor_t",
                               help="Bu yüklemenin ait olduğu gün. Aynı günü tekrar yüklersen "
                                    "önceki kayıt güncellenir (mükerrer olmaz).")
        if up is not None:
            kayitlar, hata = hl_excel_parse(up)
            if hata:
                st.error(hata)
            else:
                st.success(f"📄 {len(kayitlar)} palet satırı okundu.")
                if st.button("💾 Veritabanına Kaydet", type="primary", key="hl_kaydet_btn",
                             use_container_width=True):
                    ok, msg = hl_kaydet(kayitlar, _rapor.isoformat())
                    (st.success if ok else st.error)(msg)
                    if ok:
                        try:
                            hl_rapor_tarihleri.clear(); hl_get_stok.clear()
                        except Exception:
                            pass
                        st.rerun()

    # ── Rapor tarihi seçimi ──
    _tarihler = hl_rapor_tarihleri()
    if not _tarihler:
        st.info("Henüz veri yok. Yukarıdan Happy Life Excel'ini yükle.")
        return
    c1, c2 = st.columns([1, 3])
    _sec_tarih = c1.selectbox("Rapor tarihi", _tarihler, index=0, key="hl_sec_tarih")
    kayitlar = hl_get_stok(_sec_tarih)
    if not kayitlar:
        st.info("Bu tarihte kayıt yok.")
        return

    # ── Canlı yaş hesabı (bugüne göre) ──
    from shared.utils import tr_buyuk as _tb
    bugun_iso = date.today().isoformat()
    for k in kayitlar:
        k["_yas"] = _hl_yas(k.get("giris_tarihi"), bugun_iso)

    # ── Özet metrikler ──
    _toplam_palet = len(kayitlar)
    _cesit = len({k["sku"] for k in kayitlar})
    _yaslar = [k["_yas"] for k in kayitlar if k["_yas"] is not None]
    _max_yas = max(_yaslar) if _yaslar else 0
    _ort_yas = round(sum(_yaslar) / len(_yaslar)) if _yaslar else 0
    from shared.utils import metrik_satiri
    metrik_satiri([
        {"label": "🎁 Palet Sayısı", "value": f"{_toplam_palet:,}", "renk": "#818CF8"},
        {"label": "📦 SKU Çeşidi", "value": f"{_cesit:,}", "renk": "#22D3EE"},
        {"label": "⏳ En Yaşlı Stok", "value": f"{_max_yas} gün",
         "renk": "#F87171" if _max_yas >= 120 else "#FBBF24" if _max_yas >= 60 else "#34D399"},
        {"label": "📊 Ortalama Yaş", "value": f"{_ort_yas} gün", "renk": "#A78BFA"},
    ])

    # ── SKU ÖZET (Sayfa1 gibi: SKU · toplam miktar · en yüksek yaş) ──
    st.markdown("**📊 SKU Bazında Özet** — her SKU'nun toplam stoğu ve en yaşlı paletinin yaşı")
    _ozet = {}
    for k in kayitlar:
        o = _ozet.setdefault(k["sku"], {"tanim": k["sku_tanim"], "miktar2": 0.0,
                                        "palet": 0, "max_yas": 0, "birim2": k.get("birim2") or "Adet"})
        o["miktar2"] += k.get("miktar2") or 0
        o["palet"] += 1
        if (k["_yas"] or 0) > o["max_yas"]:
            o["max_yas"] = k["_yas"] or 0
    _ozet_df = pd.DataFrame([{
        "SKU": _tb(sku), "SKU Tanımı": _tb(o["tanim"]),
        "Toplam Miktar": int(o["miktar2"]), "Birim": o["birim2"],
        "Palet Sayısı": o["palet"], "En Yüksek Stok Yaşı (gün)": o["max_yas"],
    } for sku, o in sorted(_ozet.items(), key=lambda kv: -kv[1]["max_yas"])])
    st.dataframe(_ozet_df, hide_index=True, use_container_width=True,
                 height=min(60 + len(_ozet_df) * 35, 420),
                 column_config={
                     "En Yüksek Stok Yaşı (gün)": st.column_config.NumberColumn(
                         "En Yüksek Stok Yaşı (gün)", format="%d 🗓"),
                 })
    st.download_button("⬇️ Özet CSV", _ozet_df.to_csv(index=False).encode("utf-8-sig"),
                       f"happylife_ozet_{_sec_tarih}.csv", "text/csv", key="hl_ozet_csv")

    # ── DETAY (istenen 8 kolon) ──
    st.markdown("**📋 Palet Detayı** — talep edilen kolonlar")
    _detay_df = pd.DataFrame([{
        "SKU Kodu": _tb(k["sku"]), "SKU Tanımı": _tb(k["sku_tanim"]),
        "Giriş Tarihi": _hl_gun_ay_yil(k.get("giris_tarihi")),
        "Stok Yaşı (gün)": k["_yas"] if k["_yas"] is not None else "—",
        "Palet Etiketi": k.get("palet_etiketi") or "",
        "Miktar": int(k.get("miktar") or 0), "Birim": k.get("birim") or "",
        "Miktar-2": int(k.get("miktar2") or 0), "Birim-2": k.get("birim2") or "",
    } for k in sorted(kayitlar, key=lambda x: -(x["_yas"] or 0))])
    st.caption(f"{len(_detay_df)} palet · yaşa göre azalan sıralı (en yaşlı üstte)")
    st.dataframe(_detay_df, hide_index=True, use_container_width=True,
                 height=min(60 + len(_detay_df) * 35, 640),
                 column_config={
                     "Stok Yaşı (gün)": st.column_config.NumberColumn("Stok Yaşı (gün)", format="%d"),
                 })
    st.download_button("⬇️ Detay CSV", _detay_df.to_csv(index=False).encode("utf-8-sig"),
                       f"happylife_detay_{_sec_tarih}.csv", "text/csv", key="hl_detay_csv")


def _hl_gun_ay_yil(iso):
    """ISO tarihi → GG.AA.YYYY görüntü."""
    if not iso:
        return "—"
    try:
        return _dt.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return str(iso)

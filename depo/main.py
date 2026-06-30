"""Depo Yönetimi modülü — depo bazlı stok + depolar arası sevk (canlı adet)."""
import streamlit as st
import pandas as pd

from kayranpm.database import (get_depo_ozet, get_depo_listesi, get_depo_stok,
                               depo_sevk, get_depo_sevk_gecmisi)


def run():
    st.markdown('<div style="font-size:26px;font-weight:800;color:#E2E8F0;margin:2px 0 2px">'
                '🏬 Depo Yönetimi</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#94A3B8;font-size:13px;margin-bottom:6px">'
                'Depo bazlı stok · depolar arası sevk · canlı adet revizyonu</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#6366F1,transparent);'
                'margin:6px 0 16px"></div>', unsafe_allow_html=True)

    _ozet = get_depo_ozet()
    if not _ozet:
        st.info("Henüz depo bazlı stok yok. **Ürün Yönetimi → Veri Yükleme → G5F Stok "
                "(Depo Kırılımlı)** Excel'ini yükleyince depolar burada görünür.")
        return

    # Özet kartlar
    _kart_html = '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:6px">'
    for _o in _ozet:
        _rb = "#34D399" if _o["satilabilir"] else "#94A3B8"
        _et = "satılabilir" if _o["satilabilir"] else "fiziksel"
        _kart_html += (
            f'<div style="flex:1;min-width:150px;background:rgba(255,255,255,0.03);'
            f'border:1px solid rgba(255,255,255,0.08);border-left:3px solid {_rb};'
            f'border-radius:10px;padding:10px 14px">'
            f'<div style="color:#E2E8F0;font-weight:700;font-size:13px">{_o["depo"]}</div>'
            f'<div style="color:{_rb};font-size:22px;font-weight:800;font-family:monospace">{_o["toplam_adet"]:,}</div>'
            f'<div style="color:#64748B;font-size:11px">{_o["cesit"]} çeşit · {_et}</div></div>'
        )
    _kart_html += '</div>'
    st.markdown(_kart_html, unsafe_allow_html=True)
    st.caption("Satılabilir depolar (Merkez + Happy Life) 'bizim stok' analizine girer; "
               "diğer depolar yalnız fiziksel takip içindir.")

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;font-weight:800;color:#A5B4FC;margin:4px 0 8px">'
                '🚚 Depolar Arası Sevk</div>', unsafe_allow_html=True)
    _depolar = get_depo_listesi()
    sc1, sc2 = st.columns(2)
    _kaynak = sc1.selectbox("Kaynak depo", _depolar, key="dpo_kaynak")
    _kaynak_urunler = get_depo_stok(_kaynak) if _kaynak else []
    if not _kaynak_urunler:
        sc2.info("Bu depoda stoklu ürün yok.")
    else:
        _urun_opts = {f'{u["sku"]} — {(u["urun_adi"] or "")[:32]} ({u["adet"]} adet)': u
                      for u in _kaynak_urunler}
        _sec_lbl = sc2.selectbox(f"Ürün ({len(_kaynak_urunler)} stoklu)",
                                 list(_urun_opts.keys()), key="dpo_urun")
        _sec_urun = _urun_opts.get(_sec_lbl)
        _mevcut = int(_sec_urun["adet"]) if _sec_urun else 0
        tc1, tc2, tc3 = st.columns([1, 1.4, 1])
        _adet = tc1.number_input(f"Adet (max {_mevcut})", min_value=1,
                                 max_value=max(1, _mevcut), value=1, step=1, key="dpo_adet")
        _hedef_opts = [d for d in _depolar if d != _kaynak] + ["➕ Yeni depo…"]
        _hedef_sec = tc2.selectbox("Hedef depo", _hedef_opts, key="dpo_hedef")
        if _hedef_sec == "➕ Yeni depo…":
            _hedef = tc2.text_input("Yeni depo adı", key="dpo_hedef_yeni",
                                    placeholder="örn. ASEL DEPO").strip()
        else:
            _hedef = _hedef_sec
        tc3.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if tc3.button("🚚 Sevk Et", type="primary", use_container_width=True, key="dpo_sevk_btn"):
            if not _hedef:
                st.error("Hedef depo gerekli.")
            elif not _sec_urun:
                st.error("Ürün seçilmedi.")
            else:
                _ok, _msg = depo_sevk(_sec_urun["sku"], _kaynak, _hedef, int(_adet),
                                      st.session_state.get("aktif_kullanici", ""))
                if _ok:
                    st.success(_msg)
                    st.rerun()
                else:
                    st.error(_msg)

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    with st.expander("📋 Depo içeriği — bir deponun tüm ürünleri", expanded=False):
        _di_depo = st.selectbox("Depo seç", _depolar, key="dpo_icerik_depo")
        _di_urunler = get_depo_stok(_di_depo) if _di_depo else []
        if _di_urunler:
            _df = pd.DataFrame([{"SKU": u["sku"], "Ürün": u["urun_adi"], "Adet": u["adet"]}
                               for u in _di_urunler])
            st.caption(f"{len(_di_urunler)} çeşit · {sum(u['adet'] for u in _di_urunler):,} adet")
            st.dataframe(_df, use_container_width=True, hide_index=True)
        else:
            st.info("Bu depoda stoklu ürün yok.")

    with st.expander("🕓 Son sevkler", expanded=False):
        _gec = get_depo_sevk_gecmisi(50)
        if _gec:
            _gdf = pd.DataFrame([{
                "Tarih": (g.get("tarih") or "")[:16], "SKU": g.get("sku", ""),
                "Ürün": g.get("urun_adi", ""), "Kaynak": g.get("kaynak_depo", ""),
                "Hedef": g.get("hedef_depo", ""), "Adet": g.get("adet", ""),
                "Kullanıcı": g.get("kullanici", ""),
            } for g in _gec])
            st.dataframe(_gdf, use_container_width=True, hide_index=True)
        else:
            st.caption("Henüz sevk kaydı yok (veya 'depo_sevk_log' tablosu henüz oluşturulmamış).")

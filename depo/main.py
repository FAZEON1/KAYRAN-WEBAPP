"""Depo Yönetimi modülü — sidebar sayfaları: Depo Stok · Depolar Arası Sevk ·
Bekleyen Sevk Takibi (bağımsız manuel) · SKU Hareketleri (adet bazlı)."""
import streamlit as st
import pandas as pd
from datetime import date

from kayranpm.database import (get_depo_ozet, get_depo_listesi, get_depo_stok,
                               depo_sevk, get_depo_sevk_gecmisi, get_client)
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici


def _baslik(t, alt):
    st.markdown(f'<div style="font-size:26px;font-weight:800;color:#E2E8F0;margin:2px 0 2px">{t}</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div style="color:#94A3B8;font-size:13px;margin-bottom:6px">{alt}</div>',
                unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#6366F1,transparent);'
                'margin:6px 0 16px"></div>', unsafe_allow_html=True)


def run():
    with st.sidebar:
        st.markdown(sidebar_stil(), unsafe_allow_html=True)
        st.markdown(sidebar_baslik("🏬", "Depo", "Depo Yönetimi"), unsafe_allow_html=True)
        _kull = st.session_state.get("aktif_kullanici", "")
        if _kull:
            st.markdown(sidebar_kullanici(_kull), unsafe_allow_html=True)
        _dsayfa = st.radio("Sayfa", ["🏬 Depo Stok", "🚚 Depolar Arası Sevk",
                                     "📦 Bekleyen Sevk Takibi", "🔎 SKU Hareketleri"],
                           label_visibility="collapsed", key="depo_sayfa")

    if _dsayfa == "🏬 Depo Stok":
        _sayfa_stok()
    elif _dsayfa == "🚚 Depolar Arası Sevk":
        _sayfa_sevk()
    elif _dsayfa == "📦 Bekleyen Sevk Takibi":
        _sayfa_bekleyen()
    else:
        _sayfa_sku()


# ═════════════════════════ 🏬 DEPO STOK ═════════════════════════
def _sayfa_stok():
    _baslik("🏬 Depo Stok", "Depo bazlı stok · özet kartlar · depo içeriği")
    _ozet = get_depo_ozet()
    if not _ozet:
        st.info("Henüz depo bazlı stok yok. **Ürün Yönetimi → Veri Yükleme → G5F Stok "
                "(Depo Kırılımlı)** Excel'ini yükleyince depolar burada görünür.")
        return

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
                '📋 Depo içeriği — bir deponun tüm ürünleri</div>', unsafe_allow_html=True)
    _depolar = get_depo_listesi()
    _di_depo = st.selectbox("Depo seç", _depolar, key="dpo_icerik_depo")
    _di_urunler = get_depo_stok(_di_depo) if _di_depo else []
    if _di_urunler:
        _df = pd.DataFrame([{"SKU": u["sku"], "Ürün": u["urun_adi"], "Adet": u["adet"]}
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

    # 📦 Stoğa işlenmemiş teslim dosyası varsa en üstte uyar + tek tıkla işle
    try:
        from ithalat.database import teslim_stok_bekleyenler, teslim_stok_isle
        _bek0 = teslim_stok_bekleyenler()
    except Exception:
        _bek0 = []
    if _bek0:
        _tk0 = sum(b["kalem_sayisi"] for b in _bek0)
        with st.expander(f"⚠️ {len(_bek0)} teslim dosyasının stoğu henüz işlenmemiş "
                         f"({_tk0} kalem) — depoda görünmüyorlar. Tıkla ve düzelt.", expanded=True):
            st.caption("Bu dosyalar 'Teslim Alındı' ama (çoğunlukla Model B öncesi teslim edildikleri için) "
                       "depo stoğuna hiç eklenmemiş. Aşağıdaki düğme hepsinin kalemlerini **teslim edildikleri "
                       "depoya** ekler — sonra sevk listesinde çıkarlar. Güvenli: her dosya yalnız bir kez işlenir.")
            st.dataframe(pd.DataFrame([{
                "Belge No": b["dosya_no"], "Teslim Deposu": b["teslim_deposu"] or "⚠️ boş",
                "Kalem": b["kalem_sayisi"], "Toplam Adet": b["toplam_adet"],
            } for b in _bek0]), hide_index=True, use_container_width=True,
                height=min(38 + 35 * len(_bek0), 320))
            if st.button("✅ Tüm bekleyen teslimlerin stoğunu işle", type="primary",
                         key="dpo_teslim_isle_ust", use_container_width=True):
                _is, _ek, _atl = teslim_stok_isle()
                st.cache_data.clear()
                _m = f"✅ {_is} dosya işlendi, {_ek} kalem depo stoğuna eklendi."
                if _atl:
                    _m += (" ⚠️ Atlananlar (teslim deposu boş — İthalat'tan depo ata): "
                           + ", ".join(_atl[:8]) + (" …" if len(_atl) > 8 else ""))
                st.success(_m)
                st.rerun()
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

    # 🔎 "SKU neden listede yok?" teşhis aracı
    with st.expander("🔎 Bir SKU sevk listesinde çıkmıyor mu? — nedenini gör"):
        _tsku = st.text_input("SKU yaz (örn. X24F182S)", key="dpo_teshis_sku").strip()
        if _tsku:
            try:
                _u = get_client().table("urunler").select("sku, urun_adi, depo_kirilim, bizim_stok") \
                    .eq("sku", _tsku).execute().data
                if not _u and _tsku != _tsku.upper():
                    _u = get_client().table("urunler").select("sku, urun_adi, depo_kirilim, bizim_stok") \
                        .eq("sku", _tsku.upper()).execute().data
                if not _u:
                    st.error(f"❌ **{_tsku}** için ürün kartı YOK. İthalat teslimi bu SKU'yu stoğa "
                             "işleyememiş demektir (kartsız SKU'lar atlanır). Ürün Yön.'de bu SKU için "
                             "kart aç (ya da G5F/stok kartı yükle), sonra ithalat dosyasını Düzenle'den "
                             "'Teslim Alındı'yı kaydet — stok o an işlenir.")
                else:
                    _dk = _u[0].get("depo_kirilim") or {}
                    if not isinstance(_dk, dict):
                        _dk = {}
                    _dolu = {k: v for k, v in _dk.items() if int(v or 0) != 0}
                    st.write(f"**{_u[0].get('sku')}** — {_u[0].get('urun_adi','')}")
                    if _dolu:
                        st.success("📦 Depo kırılımı: " + " · ".join(f"**{k}**: {int(v)}"
                                                                     for k, v in _dolu.items()))
                        st.caption("Sevk için, yukarıda **Kaynak depo**yu bu ürünün stoğu olan depoyla "
                                   "(örn. HAPPY LIFE) seç — o zaman listede çıkar.")
                    else:
                        st.warning("⚠️ Kart var ama **hiçbir depoda stok yok** (tüm depolar 0). "
                                   "Büyük olasılıkla bu ürünün ithalat dosyası **Model B'den önce** teslim "
                                   "alınmış; o yüzden stok işlenmemiş. Aşağıdaki düğme bunu **otomatik düzeltir** — "
                                   "senin bir şey yapmana gerek yok.")
                        try:
                            from ithalat.database import teslim_stok_bekleyenler, teslim_stok_isle
                            _bek = teslim_stok_bekleyenler()
                        except Exception:
                            _bek = []
                        if _bek:
                            _tkalem = sum(b["kalem_sayisi"] for b in _bek)
                            st.info(f"📦 Stoğa işlenmemiş **{len(_bek)} teslim dosyası** bulundu "
                                    f"(toplam {_tkalem} kalem). Bunları şimdi işleyebilirim.")
                            with st.expander("Hangi dosyalar? (detay)"):
                                st.dataframe(pd.DataFrame([{
                                    "Belge No": b["dosya_no"], "Teslim Deposu": b["teslim_deposu"] or "⚠️ boş",
                                    "Kalem": b["kalem_sayisi"], "Toplam Adet": b["toplam_adet"],
                                } for b in _bek]), hide_index=True, use_container_width=True,
                                    height=min(38 + 35 * len(_bek), 320))
                            if st.button("✅ Bekleyen teslimlerin stoğunu şimdi işle", type="primary",
                                         key="dpo_teslim_isle", use_container_width=True):
                                _is, _ek, _atl = teslim_stok_isle()
                                st.cache_data.clear()
                                _m = f"✅ {_is} dosya işlendi, {_ek} kalem depo stoğuna eklendi."
                                if _atl:
                                    _m += (" ⚠️ Atlananlar (teslim deposu boş — İthalat'tan depo ata): "
                                           + ", ".join(_atl[:8]) + (" …" if len(_atl) > 8 else ""))
                                st.success(_m)
                                st.rerun()
                        else:
                            st.caption("Şu an işlenmeyi bekleyen teslim dosyası görünmüyor. "
                                       "Bu ürün için İthalat → dosya → Düzenle'den durumu başka aşamaya "
                                       "alıp tekrar **Teslim Alındı** yapman (teslim deposu seçili) stoğu tetikler.")
            except Exception as _e:
                st.error(f"Sorgulanamadı: {type(_e).__name__}: {str(_e)[:120]}")

    if _kaynak_urunler:
        _urun_opts = {f'{u["sku"]} — {(u["urun_adi"] or "")[:30]} ({u["adet"]} adet)': u
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
                st.rerun()
            else:
                st.warning("Bu üründen eklenebilecek kalan adet yok.")

    # Sevk listesi (sepet)
    if _sepet:
        st.markdown('<div style="font-size:12px;font-weight:700;color:#94A3B8;margin:12px 0 4px;'
                    'text-transform:uppercase;letter-spacing:.5px">📋 Sevk Listesi</div>',
                    unsafe_allow_html=True)
        for _i, _s in enumerate(_sepet):
            rc1, rc2, rc3 = st.columns([3, 1, 0.5])
            rc1.markdown(f'<div style="padding:5px 0"><b style="color:#E2E8F0">{_s["sku"]}</b> '
                         f'<span style="color:#94A3B8;font-size:12px">{(_s["urun_adi"] or "")[:42]}</span></div>',
                         unsafe_allow_html=True)
            rc2.markdown(f'<div style="padding:5px 0;font-family:monospace;color:#34D399;font-weight:700">'
                         f'{_s["adet"]} adet</div>', unsafe_allow_html=True)
            if rc3.button("🗑", key=f"dpo_sil_{_i}", help="Listeden çıkar"):
                _sepet.pop(_i)
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
                st.rerun()
    else:
        st.caption("Liste boş — yukarıdan ürün seçip **Listeye ekle** ile sevk listesi oluştur.")

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;font-weight:800;color:#A5B4FC;margin:4px 0 8px">'
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

    st.markdown('<div style="font-size:14px;font-weight:800;color:#A5B4FC;margin:10px 0 8px">'
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
                st.rerun()
            except Exception as _e:
                st.error(f"Düşüm kaydedilemedi: {_e}")
        if b2.button("🗑 Kaydı Sil", key="mt_sil"):
            try:
                get_client().table("depo_manuel_takip").delete().eq("id", _mt_sec.get("id")).execute()
                st.success("Kayıt silindi.")
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
        _opts = ["— SKU seç —"] + [(f"{s} — {a[:40]}" if a else s) for s, a in _mods]
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

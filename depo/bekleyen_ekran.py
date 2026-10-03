# -*- coding: utf-8 -*-
"""Depo › Bekleyen Sevk Takibi — liste + sayfa içi detay (Ekim 2026).

Eskiden tek uzun sayfada yeni kayıt formu, TOPLAM'lı tablo, ayrı bir seçim
kutusuyla düşüm / silme ve tüm hareketler alt alta duruyordu. Tarayıcıda görülen
hatalar: iki düşüm aynı fiş numarasını aldı; "Kaydı Sil" takip kaydını tüm
geçmişiyle onaysız siliyordu; TOPLAM satırı sıralamada başa geçiyordu.
Hesaplar depo_hesap.py'de (testli).
"""
import html as _h
from datetime import date
from functools import partial

import pandas as pd
import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi
from shared.ana_veri import urun_ad   # ürün adı = kart adı, tek kaynak (Eki 2026)

from .depo_hesap import bekleyen_ozet, fis_anahtari, toplam_satiri, tarih_tr

ON_EK = "dpo_mt"
FILTRE_KEYS = ["mt_ff", "mt_h_firma", "mt_h_bas", "mt_h_bit"]


def _e(v):
    return _h.escape(str(v or "").strip())


def _client():
    from kayranpm.database import get_client
    return get_client()


def _excel_bayt(satirlar):
    from io import BytesIO
    buf = BytesIO()
    pd.DataFrame(satirlar).to_excel(buf, index=False, sheet_name="Sevk Hareketleri")
    return buf.getvalue()


# ── Az önce kaydedilen düşümün fişi ─────────────────────────────────
def _son_fis(kid):
    """Yalnız düşümün yapıldığı kaydın detayında görünür (başka kayda geçince kaybolur)."""
    son = st.session_state.get("mt_son_fis")
    if not son:
        return
    if son["kayit"].get("id") != kid:
        st.session_state.pop("mt_son_fis", None)
        return
    from depo.belge import sevk_fisi_pdf
    h = son["hareket"]
    with st.container(border=True):
        fc1, fc2, fc3 = st.columns([2.6, 1.3, 0.5], vertical_alignment="center")
        fc1.markdown(f'**{tr_sayi(h.get("adet") or 0)} adet** sevk kaydedildi · fiş no '
                     f'**{_e(h.get("fis_no"))}**')
        fc2.download_button("Sevk fişini indir", data=partial(sevk_fisi_pdf, son["kayit"], h),
                            file_name=f'{h.get("fis_no") or "sevk"}.pdf', mime="application/pdf",
                            type="primary", use_container_width=True, key="mt_fis_indir",
                            icon=":material/print:")
        fc3.button("", key="mt_fis_kapat", icon=":material/close:", help="Kapat",
                   on_click=lambda: st.session_state.pop("mt_son_fis", None))


# ── Yeni takip kaydı ────────────────────────────────────────────────
def _yeni_kayit(acik):
    with st.expander("➕ Yeni takip kaydı (firma · ürün · faturalanan adet)", expanded=acik):
        y1, y2 = st.columns(2)
        firma = y1.text_input("Firma", key="mt_firma", placeholder="örn. AYKON / VATAN ...")
        sku = y2.text_input("SKU / Ürün Kodu", key="mt_sku", placeholder="örn. F1M650BBM")
        y3, y4 = st.columns(2)
        uad = y3.text_input("Ürün Adı (ops.)", key="mt_uad")
        fadet = y4.number_input("Faturalanan Adet", min_value=1, value=1, step=1, key="mt_fadet")
        st.caption("Aşağıdakiler sevk fişine alıcı künyesi olarak basılır (opsiyonel).")
        a1, a2 = st.columns([2, 1])
        adres = a1.text_input("Alıcı Adresi", key="mt_adres", placeholder="mahalle / cadde / no — ilçe / il")
        vd = a2.text_input("Vergi Dairesi", key="mt_vd")
        vkn = st.text_input("Vergi No / TCKN", key="mt_vkn")
        notu = st.text_input("Not (ops.)", key="mt_not", placeholder="fatura no / açıklama")
        if st.button("Takibe Ekle", type="primary", key="mt_ekle",
                     disabled=not (firma.strip() and sku.strip()), icon=":material/add:"):
            try:
                kayit = {"firma": firma.strip(), "sku": sku.strip(), "urun_adi": uad.strip(),
                         "fatura_adet": int(fadet), "sevk_edilen": 0, "hareketler": [],
                         "notlar": notu.strip()}
                if any([adres.strip(), vd.strip(), vkn.strip()]):
                    kayit.update({"firma_adres": adres.strip(), "firma_vd": vd.strip(),
                                  "firma_vkn": vkn.strip()})
                _client().table("depo_manuel_takip").insert(kayit).execute()
                st.toast("✅ Takip kaydı oluşturuldu")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Kaydedilemedi: {e}")


# ── Liste ───────────────────────────────────────────────────────────
def _satir(r, secili=False):
    fa, se, bek, oran = bekleyen_ozet(r)
    renk = "amber" if bek else "yesil"
    meta = B.meta(f'<span style="font-family:var(--k-mono)">{_e(r.get("sku"))}</span>',
                  str(r.get("urun_adi") or "").strip()[:40],
                  f"{len(r.get('hareketler') or [])} sevk",
                  str(r.get("notlar") or "").strip()[:30])
    cubuk = (f'<div style="height:5px;border-radius:3px;background:var(--k-kenar2);margin-top:6px;'
             f'overflow:hidden"><div style="height:100%;width:{oran * 100:.0f}%;background:var(--k-{renk})">'
             f'</div></div>')
    B.tiklanir(
        f"{ON_EK}{r['id']}",
        '<div style="display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 16px;align-items:center'
        + (';box-shadow:inset 3px 0 0 var(--k-mor);margin-left:-8px;padding-left:8px' if secili else '') + '">'
        f'<div style="min-width:0"><div style="font-size:13.5px;font-weight:600">{_e(r.get("firma"))}</div>'
        f'{meta}{cubuk}</div>'
        f'<div style="text-align:right;white-space:nowrap"><div style="font-family:var(--k-mono);font-size:15px;'
        f'font-weight:700;color:var(--k-{renk})">{f"{tr_sayi(bek)} bekliyor" if bek else "tamamlandı"}</div>'
        f'<div style="font-size:11.5px;color:var(--k-silik)">{tr_sayi(se)} / {tr_sayi(fa)} sevk edildi</div>'
        f'</div></div>',
        B.sec, (ON_EK, r["id"]), tur="satir", renk=renk, etiket="Kaydı aç")


def _liste(mt, dar=False, secili=None):
    """dar=True: detayın yanındaki sütun — süzgeç yedeği geri yazılmaz (liste canlı, yazılırsa
    kullanıcının o an seçtiği firma ezilirdi) ve alttaki hareket tablosu çizilmez."""
    if not dar:
        B.geri_yukle(FILTRE_KEYS)
    firmalar = sorted({(r.get("firma") or "").strip() for r in mt if (r.get("firma") or "").strip()})
    c1, c2 = st.columns([1.4, 3], vertical_alignment="bottom")
    ff = c1.selectbox("Firma", ["Tümü"] + firmalar, key="mt_ff")
    g = [r for r in mt if ff == "Tümü" or (r.get("firma") or "").strip() == ff]
    oz = [bekleyen_ozet(r) for r in g]
    c2.markdown(
        f'<div style="font-size:13px;color:var(--k-soluk);padding-bottom:8px">Σ {len(g)} kayıt · '
        f'faturalanan <b style="color:var(--k-metin)">{tr_sayi(sum(o[0] for o in oz))}</b> · '
        f'sevk edilen <b style="color:var(--k-metin)">{tr_sayi(sum(o[1] for o in oz))}</b> · '
        f'bekleyen <b style="color:var(--k-amber)">{tr_sayi(sum(o[2] for o in oz))}</b></div>',
        unsafe_allow_html=True)
    acik = [r for r in g if bekleyen_ozet(r)[2] > 0]
    biten = [r for r in g if bekleyen_ozet(r)[2] <= 0]
    if acik:
        st.markdown(B.grup_basligi("Sevk bekleyenler", f"{len(acik)} kayıt"), unsafe_allow_html=True)
        for r in sorted(acik, key=lambda r: -bekleyen_ozet(r)[2]):
            _satir(r, secili=(r.get("id") == secili))
    if biten:
        st.markdown(B.grup_basligi("Tamamı sevk edilenler", f"{len(biten)} kayıt"), unsafe_allow_html=True)
        for r in biten:
            _satir(r, secili=(r.get("id") == secili))
    if not dar:
        _tum_hareketler(mt)


def _tum_hareketler(mt):
    duz = []
    for r in mt:
        for h in (r.get("hareketler") or []):
            duz.append({"_t": str(h.get("tarih") or ""), "Tarih": tarih_tr(h.get("tarih")),
                        "Firma": r.get("firma", ""), "SKU": r.get("sku", ""),
                        "Ürün": urun_ad(r.get("sku"), r.get("urun_adi"))[:28], "Adet": int(h.get("adet") or 0),
                        "Fiş No": h.get("fis_no", "") or "", "e-İrsaliye": h.get("e_irsaliye_no", "") or "",
                        "Belge No": h.get("belge_no", "") or "", "Açıklama": (h.get("aciklama") or "")[:30],
                        "Kullanıcı": h.get("kullanici", "") or ""})
    st.markdown(B.grup_basligi("📋 Tüm sevk hareketleri", f"{len(duz)} hareket"), unsafe_allow_html=True)
    if not duz:
        st.caption("Henüz sevk hareketi yok — bir kaydı açıp düşüm kaydettiğinde burada listelenir.")
        return
    duz.sort(key=lambda x: x["_t"], reverse=True)
    h1, h2, h3 = st.columns([1.2, 1, 1])
    hf = h1.selectbox("Firma", ["Tümü"] + sorted({d["Firma"] for d in duz if d["Firma"]}), key="mt_h_firma")
    hb = h2.date_input("Başlangıç", value=None, key="mt_h_bas", format="DD.MM.YYYY")
    he = h3.date_input("Bitiş", value=None, key="mt_h_bit", format="DD.MM.YYYY")
    f = [d for d in duz if (hf == "Tümü" or d["Firma"] == hf)
         and (not hb or d["_t"] >= str(hb)) and (not he or d["_t"] <= str(he))]
    if not f:
        st.info("Bu filtreye uyan sevk hareketi yok.")
        return
    gorunur = [{k: v for k, v in d.items() if k != "_t"} for d in f]
    st.dataframe(pd.DataFrame(gorunur + [toplam_satiri(list(gorunur[0]), {"Adet": sum(d["Adet"] for d in f)},
                                                       ozet={"Firma": f"{len(f)} hareket"})]),
                 use_container_width=True, hide_index=True)
    st.download_button("Excel'e aktar", data=partial(_excel_bayt, gorunur),
                       file_name=f"sevk_hareketleri_{date.today()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key="mt_h_excel", icon=":material/download:")


# ── Detay ───────────────────────────────────────────────────────────
def _detay(r, mt):
    from depo.belge import fis_no_uret, sevk_fisi_pdf
    B.koru(FILTRE_KEYS)
    B.listeye_don(ON_EK)
    from shared.tasarim import YAN_YANA
    if YAN_YANA:
        B.kapat(ON_EK)
    kid = r.get("id")
    _son_fis(kid)
    fa, se, bek, oran = bekleyen_ozet(r)
    st.markdown(
        f'<div style="font-size:18px;font-weight:700">{_e(r.get("firma"))} '
        f'<span style="font-family:var(--k-mono);font-size:14px;color:var(--k-mor2)">{_e(r.get("sku"))}</span></div>'
        + B.meta(str(r.get("urun_adi") or "").strip(), str(r.get("notlar") or "").strip()),
        unsafe_allow_html=True)
    from shared.utils import metrik_satiri
    from shared.tasarim import renk as trenk
    metrik_satiri([
        {"label": "Faturalanan", "value": tr_sayi(fa), "renk": trenk("mor")},
        {"label": "Sevk edilen", "value": tr_sayi(se), "renk": trenk("yesil"), "alt": f"%{tr_sayi(oran * 100)}"},
        {"label": "Bekleyen", "value": tr_sayi(bek), "renk": trenk("amber") if bek else trenk("yesil")},
    ])

    tum_hrk = [h for x in mt for h in (x.get("hareketler") or [])]
    if bek > 0:
        st.markdown(B.grup_basligi("🚚 Sevk düş"), unsafe_allow_html=True)
        d1, d2, d3 = st.columns(3)
        adet = d1.number_input(f"Sevk adedi (bekleyen {bek})", min_value=1, max_value=bek, value=1,
                               step=1, key=f"mt_d_adet_{kid}")
        tarih = d2.date_input("Sevk tarihi", value=date.today(), key="mt_d_tarih", format="DD.MM.YYYY")
        belge = d3.text_input("Fatura / Belge no (ops.)", key="mt_d_belge")
        e1, e2 = st.columns(2)
        # Anahtar hareket sayısına bağlı: her düşümden sonra yeni numarayla yeni kutu
        fis = e1.text_input("Fiş No", value=fis_no_uret(tum_hrk), key=fis_anahtari(kid, tum_hrk),
                            help="Otomatik üretildi, dilersen değiştir.")
        eirs = e2.text_input("e-İrsaliye No (ops.)", key="mt_d_eirs",
                             placeholder="entegratörden alınan resmî no")
        acik = st.text_input("Açıklama (ops.)", key="mt_d_acik", placeholder="taşıyıcı / plaka / şoför / not")
        if st.button("Düşümü kaydet", type="primary", key="mt_dus", icon=":material/local_shipping:"):
            try:
                yeni_h = {"tarih": str(tarih), "adet": int(adet), "belge_no": belge.strip(),
                          "fis_no": fis.strip(), "e_irsaliye_no": eirs.strip(), "aciklama": acik.strip(),
                          "kullanici": st.session_state.get("aktif_kullanici", "")}
                hrk = list(r.get("hareketler") or []) + [yeni_h]
                yeni_sevk = se + int(adet)
                _client().table("depo_manuel_takip").update(
                    {"sevk_edilen": yeni_sevk, "hareketler": hrk}).eq("id", kid).execute()
                snap = dict(r)
                snap["sevk_edilen"] = yeni_sevk
                st.session_state["mt_son_fis"] = {"kayit": snap, "hareket": yeni_h}
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Düşüm kaydedilemedi: {e}")
    else:
        st.success("✅ Bu kaydın tamamı sevk edildi.")

    hrk = r.get("hareketler") or []
    st.markdown(B.grup_basligi("Bu kaydın sevk hareketleri", f"{len(hrk)} hareket"), unsafe_allow_html=True)
    if hrk:
        satirlar = [{"Tarih": tarih_tr(h.get("tarih")), "Adet": int(h.get("adet") or 0),
                     "Fiş No": h.get("fis_no", ""), "e-İrsaliye": h.get("e_irsaliye_no", ""),
                     "Belge No": h.get("belge_no", ""), "Açıklama": (h.get("aciklama") or "")[:28],
                     "Kullanıcı": h.get("kullanici", "")} for h in hrk]
        st.dataframe(pd.DataFrame(satirlar + [toplam_satiri(list(satirlar[0]),
                                                            {"Adet": sum(s["Adet"] for s in satirlar)})]),
                     use_container_width=True, hide_index=True)
        r1, r2 = st.columns([2.2, 1], vertical_alignment="bottom")
        hsec = r1.selectbox("Fişi yeniden yazdır", list(range(len(hrk))),
                            format_func=lambda i: (f'{tarih_tr(hrk[i].get("tarih"))} · {hrk[i].get("adet", "")} adet · '
                                                   f'{hrk[i].get("fis_no") or "fiş no yok"}'),
                            key=f"mt_rep_sec_{kid}")
        r2.download_button("PDF", data=partial(sevk_fisi_pdf, r, hrk[hsec]),
                           file_name=f'{hrk[hsec].get("fis_no") or "sevk_fisi"}.pdf', mime="application/pdf",
                           use_container_width=True, key="mt_rep_indir", icon=":material/print:")
    else:
        st.caption("Henüz sevk düşülmedi.")

    st.markdown(B.grup_basligi("Kaydı sil"), unsafe_allow_html=True)
    # Onay anahtarı KAYDA bağlı (silindikten sonra onay bir başka kayda taşınmasın)
    if B.onayli_sil(f"'{r.get('firma', '')} · {r.get('sku', '')}' takip kaydını {len(hrk)} sevk hareketiyle "
                    f"birlikte kalıcı olarak sil", key=f"mt_sil_{kid}", dugme="Kaydı sil",
                    aciklama="Yanlış açılmış kayıtlar için. Geri alınamaz."):
        try:
            _client().table("depo_manuel_takip").delete().eq("id", kid).execute()
            B.birak(ON_EK)
            st.cache_data.clear()
            st.toast("🗑️ Takip kaydı silindi")
            st.rerun()
        except Exception as e:
            st.error(f"Silinemedi: {e}")


def render(mt):
    sec = B.secili(ON_EK)
    kayit = next((r for r in mt if r.get("id") == sec), None) if sec is not None else None
    if kayit:
        from shared.tasarim import YAN_YANA
        if YAN_YANA:
            # Liste ve detay yan yana (Tüm Ürünler ile aynı düzen; shared.bilesen.yan_yana_css)
            st.markdown(B.yan_yana_css(ON_EK), unsafe_allow_html=True)
            sol, sag = st.columns([1, 1.35], gap="medium")
            with sol, st.container(key=f"{ON_EK}_liste_sol"):
                _liste(mt, dar=True, secili=kayit.get("id"))
            with sag:
                _detay(kayit, mt)
        else:
            _detay(kayit, mt)
        return
    B.birak(ON_EK)
    st.session_state.pop("mt_son_fis", None)
    _yeni_kayit(acik=not mt)
    if not mt:
        st.info("Henüz takip kaydı yok — yukarıdan ilk kaydı oluştur.")
        return
    _liste(mt)

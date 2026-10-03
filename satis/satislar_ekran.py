# -*- coding: utf-8 -*-
"""Satış — Satışlar ekranı + sipariş detay penceresi (Ekim 2026).

  render_satislar()   Satış › Satışlar sayfası
     • dönem · görünüm (Sipariş | Kalem) · arama · firma filtresi
     • özet: sipariş · adet · ciro · net kâr (marj)
     • SİPARİŞ görünümü: güne göre gruplu; satırın tamamı tıklanır → detay
     • KALEM görünümü: eski ayrıntılı tablo (ham sayılar, TR biçim)
     • Excel / CSV indirme (ekrandaki filtrenin aynısı, sayılar ham)
  siparis_listesi()   Satış Girişi'ndeki "son siparişler" de bunu kullanır
  siparis_dialog()    kalemler · düzenle (adet / fiyat / maliyet) · kalem sil ·
                      siparişi sil (hepsi onaylı; stok farkı veritabanı
                      katmanında işlenir: guncelle_satis / sil_satis / sil_siparis)

Eskiden "Kalemi sil" ve "Siparişi sil" ONAYSIZ siliyordu.
"""
import html as _h
import io

import pandas as pd
import streamlit as st

from shared import bilesen as B
from shared.kar_gizle import kar_gorunur
from shared.tasarim import kpi_serit, mesaj, bos_durum, tr_sayi, sayi
from shared.utils import firma_kisa_ad
from shared.ana_veri import kategori_ad as _kat_ad   # tek yazım (Eki 2026)
from . import satis_hesap as H
from .database import (get_satislar_yalin, get_siparis_kalemleri, get_satislar_kanal_ara,
                       guncelle_satis, sil_satis, sil_siparis, satir_kar, get_sku_kategori, get_urunler)


def _usd(v):
    return "—" if v is None else sayi(v, "$")


def _usd_tam(v):
    s = f"{abs(float(v or 0)):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return ("-" if float(v or 0) < 0 else "") + "$" + s


def _salt_okur():
    return bool(st.session_state.get("salt_okur"))


def _anahtar_temiz(k):
    """Streamlit anahtarı için güvenli parça (harf/rakam/_)."""
    import re
    return re.sub(r"[^0-9A-Za-z_]", "_", str(k))[:60]


def _ac(anahtar):
    B.detay_ac("sip", anahtar)


# ════════════════════════════════════════════════════════════════════
def _css():
    from shared.tasarim import css_tek_satir
    return "<style>" + css_tek_satir("""
.sp-s{display:grid;grid-template-columns:150px minmax(0,1fr) auto;gap:4px 16px;align-items:center;}
.sp-no{font-family:var(--k-mono);font-size:12.5px;font-weight:600;color:var(--k-mor2);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;}
.sp-ust{font-size:11.5px;color:var(--k-silik);margin-top:2px;}
.sp-firma{font-size:13px;font-weight:600;color:var(--k-metin);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sp-s .k-meta{margin-top:3px;font-size:11.5px;}
.sp-tut{text-align:right;white-space:nowrap;}
.sp-tut b{display:block;font-family:var(--k-mono);font-variant-numeric:tabular-nums;font-size:14px;font-weight:600;color:var(--k-metin);}
.sp-tut small{font-size:11.5px;color:var(--k-silik);font-family:var(--k-mono);}
.sp-tut small.poz{color:var(--k-yesil);} .sp-tut small.neg{color:var(--k-kirmizi);}
.sp-dt{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:-4px 0 2px;}
.sp-dt .sp-no{font-size:19px;color:var(--k-metin);}
.sp-dt-alt{font-size:13px;color:var(--k-soluk);margin-bottom:12px;}
@media (max-width:640px){ .sp-s{grid-template-columns:minmax(0,1fr) auto;} .sp-s > div:first-child{grid-column:1 / -1;} }
""") + "</style>"


def _satir_html(o, firma_goster=True):
    urunler = ", ".join(dict.fromkeys(str(k.get("sku") or "") for k in o["kalemler"]))
    kar = ""
    if kar_gorunur():
        sinif = "poz" if o["net_kar"] >= 0 else "neg"
        marj = f" · %{tr_sayi(o['marj'], 1)}" if o["marj"] is not None else ""
        kar = f'<small class="{sinif}">kâr {_usd(o["net_kar"])}{marj}</small>'
    uyari = B.cip(f"{o['maliyetsiz']} maliyetsiz", "amber", "Paçal maliyeti olmayan kalem: kâr yüksek görünür") \
        if o["maliyetsiz"] and kar_gorunur() else ""
    firma = (f'<div class="sp-firma">{_h.escape(firma_kisa_ad(o["kanal"]) or "—")}</div>' if firma_goster else "")
    return (f'<div class="sp-s">'
            f'<div><div class="sp-no" title="{_h.escape(o["siparis_no"] or "—", quote=True)}">'
            f'{_h.escape(o["siparis_no"] or "Sipariş no yok")}</div>'
            f'<div class="sp-ust">{o["kalem"]} kalem · {tr_sayi(o["adet"])} adet</div></div>'
            f'<div style="min-width:0">{firma}'
            f'{B.meta(_h.escape(urunler[:90] + ("…" if len(urunler) > 90 else "")))}{uyari}</div>'
            f'<div class="sp-tut"><b>{_usd(o["ciro"])}</b>{kar}</div></div>')


def siparis_listesi(siparisler, anahtar="sat", firma_goster=True, sayfa=40, gunluk=True):
    """Siparişleri (güne göre gruplu) tıklanır satırlar olarak çizer; detay penceresi
    çağıranın sonunda siparis_detay_kontrol() ile açılır."""
    st.markdown(_css(), unsafe_allow_html=True)
    lim_k = f"{anahtar}_limit"
    limit = int(st.session_state.get(lim_k, sayfa))
    goster = siparisler[:limit]
    bloklar = H.gunlere_bol(goster) if gunluk else [(None, goster)]
    for gun, grup in bloklar:
        if gun is not None:
            t = H.toplam(grup)
            st.markdown(B.grup_basligi(H.gun_adi(gun), f"{len(grup)} sipariş · {_usd(t['ciro'])}"),
                        unsafe_allow_html=True)
        for o in grup:
            k = o["siparis_no"] or f"#kalem-{o['kalemler'][0].get('id')}"
            B.tiklanir(f"{anahtar}_{_anahtar_temiz(k)}", _satir_html(o, firma_goster), _ac, (k,),
                       tur="satir", renk=("amber" if o["maliyetsiz"] and kar_gorunur() else "mor"),
                       etiket=f"{o['siparis_no'] or 'Sipariş'} detay")
    if len(siparisler) > limit:
        if st.button(f"Daha fazla göster ({len(siparisler) - limit} sipariş daha)", key=f"{anahtar}_daha",
                     type="tertiary", use_container_width=True):
            st.session_state[lim_k] = limit + sayfa
            st.rerun(scope="fragment")


def siparis_detay_kontrol():
    """Sayfanın sonunda çağrılır: bir siparişe tıklandıysa detay penceresini açar."""
    sec = B.detay_istendi("sip")
    if sec:
        siparis_dialog(sec)


# ════════════════════════════════════════════════════════════════════
@st.dialog("Sipariş", width="large")
def siparis_dialog(anahtar):
    from shared.tasarim import yan_panel; yan_panel("orta")   # sağ panel (okuma)
    if str(anahtar).startswith("#kalem-"):
        kalemler = get_siparis_kalemleri(satis_id=int(str(anahtar)[7:]))
        sno = ""
    else:
        sno = str(anahtar)
        kalemler = get_siparis_kalemleri(siparis_no=sno)
    if not kalemler:
        st.markdown(mesaj("bilgi", "Bu siparişin kalemi kalmadı (silinmiş olabilir)."), unsafe_allow_html=True)
        return
    o = H.siparis_grupla(kalemler, satir_kar)[0]
    kar_ok = kar_gorunur()
    st.markdown(_css() + f'<div class="sp-dt"><span class="sp-no">{_h.escape(sno or "Sipariş no yok")}</span>'
                f'</div><div class="sp-dt-alt">{_h.escape(firma_kisa_ad(o["kanal"]) or "—")} · '
                f'{H.gun_adi(o["tarih"])}</div>', unsafe_allow_html=True)
    kal = [{"etiket": "Ciro", "deger": _usd(o["ciro"]), "renk": "cyan", "alt": f"{o['kalem']} kalem · {tr_sayi(o['adet'])} adet",
            "ipucu": _usd_tam(o["ciro"])}]
    if kar_ok:
        kal += [{"etiket": "Maliyet", "deger": _usd(o["maliyet"]), "renk": "amber"},
                {"etiket": "Net kâr", "deger": _usd(o["net_kar"]), "renk": "yesil" if o["net_kar"] >= 0 else "kirmizi",
                 "alt": f"net marj %{tr_sayi(o['marj'], 1)}" if o["marj"] is not None else "",
                 "ipucu": _usd_tam(o["net_kar"])}]
    st.markdown(kpi_serit(kal), unsafe_allow_html=True)
    if o["maliyetsiz"] and kar_ok:
        st.markdown(mesaj("uyari", f"{o['maliyetsiz']} kalemde birim maliyet 0: kâr olduğundan yüksek görünür. "
                                   "Tabloda maliyeti gir ya da Kâr / P&L → 'Maliyeti 0 düzelt' ile paçaldan doldur."),
                    unsafe_allow_html=True)

    satirlar = []
    for s in kalemler:
        k = satir_kar(s)
        r = {"_id": s["id"], "SKU": s.get("sku", ""), "Ürün": s.get("urun_adi", "") or "",
             "Adet": int(s.get("adet") or 0), "Birim satış": float(s.get("birim_satis") or 0)}
        if kar_ok:
            r.update({"Birim maliyet": float(s.get("birim_maliyet") or 0), "Kâr": k["net_kar"],
                      "Marj %": k["marj"]})
        r["Ciro"] = k["ciro"]
        r["Sil"] = False
        satirlar.append(r)
    df = pd.DataFrame(satirlar).set_index("_id")
    salt = _salt_okur()
    para = lambda b, adim=0.01: st.column_config.NumberColumn(b, format="dollar", step=adim, min_value=0.0)
    duz = st.data_editor(
        df, key=f"sip_ed_{anahtar}", hide_index=True, use_container_width=True,
        height=min(400, 38 + 35 * len(df)),
        disabled=True if salt else ["SKU", "Ürün", "Kâr", "Marj %", "Ciro"],
        column_config={"SKU": st.column_config.TextColumn("SKU", width="small"),
                       "Ürün": st.column_config.TextColumn("Ürün", width="medium"),
                       "Adet": st.column_config.NumberColumn("Adet", min_value=0, step=1, format="localized"),
                       "Birim satış": para("Birim satış", 0.0001), "Birim maliyet": para("Birim maliyet", 0.0001),
                       "Kâr": st.column_config.NumberColumn("Kâr", format="dollar", step=0.01),
                       "Marj %": st.column_config.NumberColumn("Marj %", format="localized", step=0.1),
                       "Ciro": st.column_config.NumberColumn("Ciro", format="dollar", step=0.01),
                       "Sil": st.column_config.CheckboxColumn("Sil", width="small",
                                                              help="İşaretle ve kaydet: kalem silinir, stoğu geri döner")})
    if salt:
        st.caption("Salt-okur oturum: düzenleme ve silme kapalı.")
        return
    alanlar = [c for c in ("Adet", "Birim satış", "Birim maliyet") if c in df.columns]
    degisen, silinen = [], []
    for rid, y in duz.iterrows():
        if bool(y["Sil"]):
            silinen.append(int(rid))
        elif any(str(y[c]) != str(df.loc[rid, c]) for c in alanlar):
            d = {"adet": int(y["Adet"] or 0), "birim_satis": float(y["Birim satış"] or 0)}
            if "Birim maliyet" in alanlar:
                d["birim_maliyet"] = float(y["Birim maliyet"] or 0)
            degisen.append((int(rid), d))
    st.caption("Adet, birim satış ve maliyeti tabloda düzelt; stok farkı otomatik işlenir. "
               "Silmek için satırın 'Sil' kutusunu işaretle.")
    if degisen or silinen:
        ozet = " · ".join(x for x in (f"{len(degisen)} kalem değişecek" if degisen else "",
                                       f"{len(silinen)} kalem silinecek" if silinen else "") if x)
        onay = (st.checkbox(f"Evet, {len(silinen)} kalemi sil", key=f"sip_kalem_sil_onay_{anahtar}")
                if silinen else True)
        if st.button(f"Kaydet ({ozet})", type="primary", icon=":material/save:", disabled=not onay,
                     key=f"sip_kaydet_{anahtar}"):
            hata = 0
            for rid, d in degisen:
                hata += 0 if guncelle_satis(rid, d) else 1
            for rid in silinen:
                hata += 0 if sil_satis(rid) else 1
            if hata:
                st.error(f"{hata} işlem yapılamadı; ayrıntı Sistem Kayıtları'nda.")
            else:
                kalan = len(kalemler) - len(silinen)
                B.yenile("Sipariş güncellendi", ac=("sip", anahtar) if kalan else None)
    if sno:
        with st.expander("Siparişin tamamını sil", icon=":material/delete:"):
            if B.onayli_sil(f"Evet, {sno} siparişinin {len(kalemler)} kalemini sil", key=f"sip_{anahtar}",
                            dugme="Siparişi sil",
                            aciklama="Tüm kalemler silinir, stokları depoya geri döner. Geri alınamaz."):
                if sil_siparis(sno):
                    B.yenile(f"{sno} silindi")
                else:
                    st.error("Silinemedi; ayrıntı Sistem Kayıtları'nda.")


# ════════════════════════════════════════════════════════════════════
def render_satislar(hizli_tarih_araligi, kanallar):
    """Satış › Satışlar sayfası."""
    st.markdown(_css(), unsafe_allow_html=True)
    ey = B.baslik_eylem("🧾 Satış", "Satışlar", aciklama="Siparişleri tara, ayrıntısına in, düzelt.",
                        eylemler=[{"etiket": "Kayıp kayıt ara", "key": "sat_hayalet_btn", "icon": ":material/manage_search:",
                                   "help": "Tarihi boş/bozuk olduğu için listede görünmeyen kayıtları bul"}])
    if ey.get("sat_hayalet_btn"):
        _hayalet_dialog()
    bas, bit = hizli_tarih_araligi("l", varsayilan="Son 30 gün")
    ham = get_satislar_yalin(bas, bit) or []
    firmalar = sorted({(s.get("kanal") or "").strip() for s in ham if (s.get("kanal") or "").strip()})

    c1, c2, c3 = st.columns([1.2, 3.0, 1.0], vertical_alignment="bottom")
    with c1:
        gor = st.segmented_control("Görünüm", ["Sipariş", "Kalem"], default="Sipariş", key="sat_gorunum",
                                   label_visibility="collapsed") or "Sipariş"
    aranan = c2.text_input("Ara", key="sat_ara", placeholder="Sipariş no, firma, SKU ya da ürün…",
                           label_visibility="collapsed")
    f = B.filtre(c3, [{"etiket": "Firma", "secenekler": firmalar, "key": "sat_f_firma",
                       "format_func": lambda x: x if x == "Tümü" else firma_kisa_ad(x)}])
    siparisler = H.ara(H.siparis_grupla(ham, satir_kar), aranan, f["sat_f_firma"])
    t = H.toplam(siparisler)
    kal = [{"etiket": "Sipariş", "deger": tr_sayi(t["siparis"]), "renk": "mor",
            "alt": f"{tr_sayi(sum(o['kalem'] for o in siparisler))} kalem"},
           {"etiket": "Adet", "deger": tr_sayi(t["adet"]), "renk": "cyan"},
           {"etiket": "Ciro", "deger": _usd(t["ciro"]), "renk": "cyan", "ipucu": _usd_tam(t["ciro"]),
            "alt": f"destek {_usd(t['destek'])}" if t["destek"] > 0.005 else ""}]
    if kar_gorunur():
        kal.append({"etiket": "Net kâr", "deger": _usd(t["net_kar"]), "renk": "yesil" if t["net_kar"] >= 0 else "kirmizi",
                    "alt": (f"net marj %{tr_sayi(t['marj'], 1)} · maliyet {_usd(t['maliyet'])}" if t["marj"] is not None
                            else ""), "ipucu": _usd_tam(t["net_kar"])})
    st.markdown(kpi_serit(kal), unsafe_allow_html=True)
    maliyetsiz = sum(o["maliyetsiz"] for o in siparisler)
    if maliyetsiz and kar_gorunur():
        st.markdown(mesaj("uyari", f"{maliyetsiz} kalemde birim maliyet 0: bu siparişlerin kârı olduğundan "
                                   "yüksek görünür (satırlarda turuncu işaretli)."), unsafe_allow_html=True)

    if not siparisler:
        st.markdown(bos_durum("Bu dönemde satış yok" if not ham else "Aramaya uyan sipariş yok",
                              "Dönemi genişlet ya da aramayı değiştir.", "receipt_long"), unsafe_allow_html=True)
        return
    kalemler = [k for o in siparisler for k in o["kalemler"]]
    if gor == "Sipariş":
        siparis_listesi(siparisler, "sat")
    else:
        _kalem_tablosu(kalemler)
    _indir(kalemler, bas, bit, f["sat_f_firma"])
    siparis_detay_kontrol()


def _kalem_tablosu(kalemler):
    katmap = get_sku_kategori() or {}
    kar_ok = kar_gorunur()
    rows = []
    for s in kalemler:
        k = satir_kar(s)
        r = {"Tarih": str(s.get("tarih") or "")[:10], "Sipariş No": s.get("siparis_no") or "—",
             "Firma": firma_kisa_ad(s.get("kanal")), "SKU": s.get("sku", ""),
             "Ürün": (s.get("urun_adi") or "")[:34],
             "Kategori": _kat_ad(katmap.get(str(s.get("sku") or "").strip(), "")) or "—",   # tek yazım
             "Adet": int(k["adet"] or 0), "Birim satış": round(float(s.get("birim_satis") or 0), 4),
             "Ciro": round(k["ciro"], 2)}
        if kar_ok:
            r.update({"Birim maliyet": round(float(s.get("birim_maliyet") or 0), 4),
                      "Net kâr": round(k["net_kar"], 2), "Marj %": round(k["marj"], 1)})
        rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=440,
                 key="sat_kalem_tablo",
                 column_config={"Tarih": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY"),
                                "Birim satış": st.column_config.NumberColumn("Birim satış", format="dollar", step=0.0001),
                                "Birim maliyet": st.column_config.NumberColumn("Birim maliyet", format="dollar", step=0.0001),
                                "Ciro": st.column_config.NumberColumn("Ciro", format="dollar", step=0.01),
                                "Net kâr": st.column_config.NumberColumn("Net kâr", format="dollar", step=0.01),
                                "Marj %": st.column_config.NumberColumn("Marj %", format="localized", step=0.1)})


@st.cache_data(ttl=300, show_spinner=False)
def _satis_xlsx(kayitlar):
    """Excel: ham sayılar + otomatik sütun genişliği. (Parametre adı alt çizgisiz:
    Streamlit alt çizgili parametreyi önbellek anahtarına katmaz.)"""
    df = pd.DataFrame(kayitlar)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Satışlar")
        ws = w.sheets["Satışlar"]
        for i, kol in enumerate(df.columns, start=1):
            en = max(len(str(kol)), *(len(str(v)) for v in df[kol].head(200))) if len(df) else len(str(kol))
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(en + 3, 40)
    return buf.getvalue()


def _indir(kalemler, bas, bit, firma):
    katmap = get_sku_kategori() or {}
    admap = {str(u.get("sku") or "").strip(): (u.get("urun_adi") or "") for u in (get_urunler() or [])}
    kar_ok = kar_gorunur()
    rows = []
    for s in kalemler:
        k = satir_kar(s)
        sku = str(s.get("sku") or "")
        bd = float(s.get("birim_firma_destek") or 0) + float(s.get("birim_ek_destek") or 0)
        r = {"Tarih": str(s.get("tarih") or ""), "Sipariş No": s.get("siparis_no") or "",
             "Kanal": s.get("kanal") or "", "SKU": sku,
             "Ürün": (s.get("urun_adi") or "") or admap.get(sku.strip(), ""),
             "Kategori": _kat_ad(katmap.get(sku.strip(), "")), "Adet": int(k["adet"] or 0),
             "Birim Satış": round(float(s.get("birim_satis") or 0), 2), "Birim Destek": round(bd, 2),
             "Ciro": round(k["ciro"], 2), "Destek": round(k["destek"], 2)}
        if kar_ok:
            r.update({"Birim Maliyet": round(float(s.get("birim_maliyet") or 0), 2),
                      "Maliyet": round(k["maliyet"], 2), "Net Kâr": round(k["net_kar"], 2),
                      "Marj %": round(k["marj"], 1)})
        rows.append(r)
    ad = f"satislar_{bas}_{bit}" + ("" if firma == "Tümü" else "_" + "".join(c for c in firma if c.isalnum())[:30])
    d1, d2, d3 = st.columns([1, 1, 2.4], vertical_alignment="center")
    d1.download_button("Excel indir", data=lambda: _satis_xlsx(rows), file_name=f"{ad}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True, key="l_dl_xlsx", icon=":material/download:", on_click="ignore")
    d2.download_button("CSV indir", data=lambda: pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{ad}.csv", mime="text/csv", use_container_width=True, key="l_dl_csv",
                       icon=":material/download:", on_click="ignore")
    d3.caption(f"{tr_sayi(len(rows))} kalem · ekrandaki dönem, arama ve filtrenin aynısı; sayılar ham.")


@st.dialog("Kayıp kayıt ara", width="large")
def _hayalet_dialog():
    """Tarihi boş/bozuk olduğu için normal listede görünmeyen kayıtlar (tarih filtresiz)."""
    st.caption("Tarihi boş ya da bozuk kayıtlar dönem listesinde görünmez. Firma adıyla ara.")
    q = st.text_input("Firma / müşteri adı", key="l_hayalet_q", placeholder="örn. AYKON")
    if not q or len(q.strip()) < 2:
        return
    rows = get_satislar_kanal_ara(q)
    if not rows:
        st.caption("Eşleşen kayıt yok.")
        return
    st.dataframe(pd.DataFrame([{"id": r.get("id"), "Tarih": str(r.get("tarih") or "BOŞ"),
                                "Firma": r.get("kanal", ""), "SKU": r.get("sku", ""), "Adet": r.get("adet", 0),
                                "Sipariş": r.get("siparis_no", "") or "—"} for r in rows]),
                 hide_index=True, use_container_width=True, height=min(280, 40 + 35 * len(rows)), key="l_hayalet_tablo")
    sec = st.multiselect("Silinecek kayıt id'leri", [r.get("id") for r in rows], key="l_hayalet_sec")
    if sec and B.onayli_sil(f"Evet, seçili {len(sec)} kaydı sil", key="l_hayalet", dugme=f"{len(sec)} kaydı sil"):
        n = sum(1 for i in sec if sil_satis(i))
        B.yenile(f"{n} kayıt silindi")

# -*- coding: utf-8 -*-
"""KAYRAN — Hesap Makinesi (Ekim 2026 yenileme).

Sekmeler: Ürün Kârlılık · Kırılma Noktası · Gökhan Yavuz primi · Ayhan Eroğlu primi.
Formüller hm_hesap.py'de (saf, testli) — mantık eski kodla birebir aynı.

Düzeltilenler: prim kaydı onaysız siliniyordu · aynı dönem iki kez kaydedilebiliyordu ·
kur 38'de sabitti · İngilizce sayı biçimi · kaybolan mesajlar · ISO tarih · toplamsız
geçmiş · büyük harf CSS ve dış font · sabit "1,5 maaş" etiketi · hiçbir şeyi sarmayan
kart kutuları · her tıklamada tüm sayfayı yenileyen sekmeler.
"""
import html as _h
from datetime import datetime, date

import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi, baslik as _sb
from shared.tasarim import renk as trenk
from shared.utils import metrik_satiri

from .hm_hesap import karlilik, kirilma, gokhan_prim, ayhan_prim, donem_var_mi


def _tarih_tr(v):
    from kayranpm.urun_hesap import tarih_tr
    return tarih_tr(v)



def _e(v):
    return _h.escape(str(v or ""))


def _usd(v, d=2):
    return "$" + tr_sayi(float(v or 0), d)


def _usd_h(v, d=2):
    """HTML içinde: düz "$" iki kez geçerse LaTeX sanılır."""
    return "&#36;" + tr_sayi(float(v or 0), d)


def _usd_md(v, d=2):
    """st.markdown / st.caption metninde: kaçışlı "$"."""
    return "\\$" + tr_sayi(float(v or 0), d)


def _tl(v):
    return tr_sayi(float(v or 0)) + " TL"


def _yuzde(v, d=1):
    return "%" + tr_sayi(float(v or 0), d)


def _renk(kar):
    return trenk("yesil") if kar > 0 else (trenk("kirmizi") if kar < 0 else trenk("amber"))


def _kart_baslik(t, alt=""):
    st.markdown(f'<div style="font-size:14px;font-weight:650;margin-bottom:2px">{_e(t)}</div>'
                + (f'<div style="font-size:12px;color:var(--k-silik);margin-bottom:8px">{_e(alt)}</div>' if alt else ""),
                unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _doviz_usd():
    from gunluk import get_doviz
    return float(get_doviz().get("USD") or 0)


def _guncel_kur():
    """Varsayılan USD/TL: oturumdaki kur → günlük döviz → 40 (eskiden 38'de sabitti)."""
    try:
        k = float(st.session_state.get("kur") or 0)
        if k > 1:
            return round(k, 2)
    except (TypeError, ValueError):
        pass
    try:
        k = _doviz_usd()
        if k > 1:
            return round(k, 2)
    except Exception:  # noqa: BLE001
        pass
    return 40.0


# ── Veritabanı (prim_gecmis) ────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _get_supabase():
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"].get("key")
        from shared.audit import wrap_client
        return wrap_client(create_client(url, key), "Hesap Makinesi")
    except Exception:  # noqa: BLE001
        return None


def prim_kaydet(kisi, donem, toplam_prim, odeme_tarihi, notlar=""):
    try:
        sb = _get_supabase()
        if not sb:
            return False
        sb.table("prim_gecmis").insert({
            "kisi": kisi, "donem": donem, "toplam_prim": float(toplam_prim), "odeme_tarihi": str(odeme_tarihi),
            "notlar": notlar, "olusturma_tarihi": datetime.now().isoformat(timespec="seconds")}).execute()
        return True
    except Exception as e:  # noqa: BLE001
        st.error(f"Kayıt hatası: {e}")
        return False


def prim_sil(row_id):
    try:
        sb = _get_supabase()
        if not sb:
            return False
        sb.table("prim_gecmis").delete().eq("id", row_id).execute()
        return True
    except Exception as e:  # noqa: BLE001
        st.error(f"Silme hatası: {e}")
        return False


def prim_guncelle(row_id, donem, toplam_prim, odeme_tarihi, notlar):
    try:
        sb = _get_supabase()
        if not sb:
            return False
        sb.table("prim_gecmis").update({"donem": donem, "toplam_prim": float(toplam_prim),
                                         "odeme_tarihi": str(odeme_tarihi), "notlar": notlar}).eq("id", row_id).execute()
        return True
    except Exception as e:  # noqa: BLE001
        st.error(f"Güncelleme hatası: {e}")
        return False


def prim_listele(kisi):
    try:
        sb = _get_supabase()
        if not sb:
            return []
        res = sb.table("prim_gecmis").select("*").eq("kisi", kisi).order("odeme_tarihi", desc=True).execute()
        return res.data or []
    except Exception:  # noqa: BLE001
        return []


# ── Ortak: prim ödemesi kaydet + geçmiş ─────────────────────────────
def _odeme_kaydet(kisi, pfx, donem, tutar_tl, gecmis):
    with st.container(border=True):
        _kart_baslik("Prim ödemesini kaydet", f"{donem or 'dönem girilmedi'} · {_tl(tutar_tl)}")
        c1, c2, c3 = st.columns([1.4, 1.8, 1.2], vertical_alignment="bottom")
        odt = c1.date_input("Ödeme tarihi", value=date.today(), key=f"{pfx}_odt", format="DD.MM.YYYY")
        notu = c2.text_input("Not (isteğe bağlı)", placeholder="Örn: Q1 ödemesi", key=f"{pfx}_not")
        # Aynı dönem varsa ikinci kayıt ancak açık onayla (eskiden çift tıklama çift prim yazıyordu)
        var = donem_var_mi(gecmis, donem)
        onay = True
        if var:
            st.warning(f"**{donem}** dönemi için zaten kayıtlı bir ödeme var.")
            onay = st.checkbox("Yine de ikinci kayıt olarak ekle", key=f"{pfx}_ikinci_{donem}")
        if c3.button("Ödemeyi kaydet", key=f"{pfx}_save", type="primary", use_container_width=True,
                     icon=":material/save:", disabled=not (tutar_tl > 0 and donem and onay)):
            if prim_kaydet(kisi, donem, tutar_tl, odt, notu):
                st.toast(f"✅ {donem} · {_tl(tutar_tl)} prim ödemesi kaydedildi")
                st.rerun()
        if not (tutar_tl > 0 and donem):
            st.caption("Kaydetmek için dönem adı ve sıfırdan büyük bir prim gerekir.")


def _gecmis_odemeler(kisi, pfx, gecmis):
    ek = f"{pfx}_eid"
    with st.container(border=True):
        top = sum(float(r.get("toplam_prim") or 0) for r in gecmis)
        _kart_baslik("Geçmiş prim ödemeleri",
                     f"{len(gecmis)} kayıt · Σ {_tl(top)}" if gecmis else "")
        if not gecmis:
            st.caption("Henüz kayıtlı ödeme yok.")
            return
        bas = st.columns([1.3, 1.6, 1.3, 2.4, 0.6])
        for c, t in zip(bas, ["Dönem", "Prim", "Ödeme tarihi", "Not", ""]):
            c.markdown(f'<div style="font-size:12px;color:var(--k-silik);font-weight:600">{t}</div>',
                       unsafe_allow_html=True)
        for row in gecmis:
            rid = row.get("id")
            c = st.columns([1.3, 1.6, 1.3, 2.4, 0.6], vertical_alignment="center")
            c[0].markdown(f'<b>{_e(row.get("donem"))}</b>', unsafe_allow_html=True)
            c[1].markdown(f'<span style="font-family:var(--k-mono);color:var(--k-yesil);font-weight:700">'
                          f'{_tl(row.get("toplam_prim"))}</span>', unsafe_allow_html=True)
            c[2].markdown(_tarih_tr(row.get("odeme_tarihi")) or "—")
            c[3].markdown(f'<span style="color:var(--k-soluk)">{_e(row.get("notlar")) or "—"}</span>',
                          unsafe_allow_html=True)
            if c[4].button("", key=f"{pfx}_ed_{rid}", help="Düzenle / sil", icon=":material/edit:"):
                st.session_state[ek] = None if st.session_state.get(ek) == rid else rid
        st.markdown(f'<div style="display:flex;justify-content:space-between;border-top:1px solid var(--k-kenar2);'
                    f'padding-top:6px;margin-top:4px;font-size:13px"><b>Σ Toplam</b>'
                    f'<b style="font-family:var(--k-mono)">{_tl(top)}</b></div>', unsafe_allow_html=True)

        erow = next((r for r in gecmis if r.get("id") == st.session_state.get(ek)), None)
        if not erow:
            return
        rid = erow.get("id")
        with st.container(border=True):
            _kart_baslik("Kaydı düzenle", f"{erow.get('donem', '')} · {_tl(erow.get('toplam_prim'))}")
            e1, e2, e3, e4 = st.columns([1.4, 1.4, 1.4, 2])
            e_d = e1.text_input("Dönem", value=erow.get("donem", ""), key=f"{pfx}_ed_d_{rid}")
            e_p = e2.number_input("Prim (TL)", min_value=0.0, value=float(erow.get("toplam_prim") or 0), step=100.0,
                                  format="%.0f", key=f"{pfx}_ed_p_{rid}")
            try:
                td = date.fromisoformat(str(erow.get("odeme_tarihi"))[:10])
            except ValueError:
                td = date.today()
            e_t = e3.date_input("Ödeme tarihi", value=td, key=f"{pfx}_ed_t_{rid}", format="DD.MM.YYYY")
            e_n = e4.text_input("Not", value=erow.get("notlar", "") or "", key=f"{pfx}_ed_n_{rid}")
            b1, b2, _ = st.columns([1, 1, 3])
            if b1.button("Kaydet", key=f"{pfx}_esv", type="primary", icon=":material/check_circle:"):
                if prim_guncelle(rid, e_d, e_p, e_t, e_n):
                    st.session_state[ek] = None
                    st.toast("✅ Kayıt güncellendi")
                    st.rerun()
            if b2.button("Vazgeç", key=f"{pfx}_ecl", icon=":material/close:"):
                st.session_state[ek] = None
                st.rerun()
            # Silme ONAYLI (eskiden tek tıkla, geri alınamaz şekilde siliniyordu);
            # onay anahtarı kayda bağlı — başka kayda taşınmaz.
            if B.onayli_sil(f"'{erow.get('donem', '')}' dönemine ait {_tl(erow.get('toplam_prim'))} "
                            f"ödeme kaydını kalıcı olarak sil", key=f"{pfx}_sil_{rid}", dugme="Kaydı sil"):
                if prim_sil(rid):
                    st.session_state[ek] = None
                    st.toast("🗑️ Ödeme kaydı silindi")
                    st.rerun()


# ── Prim: Gökhan Yavuz ──────────────────────────────────────────────
def _prim_gokhan():
    with st.container(border=True):
        _kart_baslik("Gökhan Yavuz · prim parametreleri",
                     "Prim = baz hakediş (maaş × katsayı) + ciro ağırlıklı bonus · NZXT/AGI hariç")
        p1, p2, p3, p4 = st.columns(4)
        donem = p1.text_input("Dönem", value="Q1 2026", key="gy_donem", placeholder="Q1 2026")
        maas = p2.number_input("Aylık maaş (TL)", min_value=0.0, value=115000.0, step=1000.0, format="%.0f",
                               key="gy_maas")
        baz_kat = p3.number_input("Baz katsayısı", min_value=0.0, value=1.5, step=0.1, format="%.1f",
                                  key="gy_baz_kat")
        kur = p4.number_input("USD/TL kuru", min_value=1.0, value=_guncel_kur(), step=0.5, format="%.2f",
                              key="gy_usd_kur")
        g = {}
        for et, on, hd, ck in (("Kasa", "k", 30.0, "kh"), ("Soğutucu", "s", 35.0, "sh")):
            st.markdown(f'<div style="font-size:13px;font-weight:600;margin-top:8px">{et}</div>',
                        unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            g[on] = (c1.number_input("Hedef (%)", min_value=0.0, value=hd, step=0.1, format="%.1f", key=f"gy_{ck}"),
                     c2.number_input("Gerçekleşen (%)", min_value=0.0, value=0.0, step=0.1, format="%.1f",
                                     key=f"gy_{on}g"),
                     c3.number_input("Ciro (USD)", min_value=0.0, value=0.0, step=100.0, format="%.0f",
                                     key=f"gy_{on}c"))
    r = gokhan_prim(maas, baz_kat, g["k"][0], g["k"][1], g["k"][2], g["s"][0], g["s"][1], g["s"][2], kur)

    def _c(x):
        return trenk("yesil") if x >= 1 else (trenk("amber") if x >= 0.8 else trenk("kirmizi"))
    with st.container(border=True):
        _kart_baslik("Hesap sonucu", f"Baz {_tl(r['baz'])} + bonus {_tl(r['bonus'])} = {_tl(r['toplam'])}")
        metrik_satiri([
            {"label": f"Baz hakediş ({tr_sayi(baz_kat, 1)} maaş)", "value": _tl(r["baz"]), "renk": trenk("mor")},
            {"label": "Kasa çarpanı", "value": f"{tr_sayi(r['kasa_carpan'], 2)}x", "renk": _c(r["kasa_carpan"]),
             "alt": f"ciro payı {_yuzde(r['kasa_pay'] * 100)}"},
            {"label": "Soğutucu çarpanı", "value": f"{tr_sayi(r['sog_carpan'], 2)}x", "renk": _c(r["sog_carpan"]),
             "alt": f"ciro payı {_yuzde(r['sog_pay'] * 100)}"},
            {"label": "Ciro ağırlıklı bonus", "value": _tl(r["bonus"]), "renk": trenk("amber"),
             "alt": f"ağırlıklı çarpan {tr_sayi(r['agirlikli'], 2)}x"},
            {"label": "Toplam prim", "value": _tl(r["toplam"]), "renk": trenk("yesil")},
        ])
        # "\\$": aynı satırda birden çok "$" LaTeX sanılıp metni bozuyordu (tarayıcıda görüldü)
        st.caption(f"Toplam ciro {_usd_md(r['toplam_ciro'], 0)} ≈ {_tl(r['toplam_ciro_tl'])} · "
                   f"kasa {_usd_md(g['k'][2], 0)} · soğutucu {_usd_md(g['s'][2], 0)}")
    gecmis = prim_listele("gokhan_yavuz")
    _odeme_kaydet("gokhan_yavuz", "gy", donem, r["toplam"], gecmis)
    _gecmis_odemeler("gokhan_yavuz", "gy", gecmis)


# ── Prim: Ayhan Eroğlu ──────────────────────────────────────────────
def _prim_ayhan():
    with st.container(border=True):
        _kart_baslik("Ayhan Eroğlu · birim prim oranları ve kur",
                     "Monitör / kasa / SSD&RAM: ciro × oran % · ekran kartı: adet × birim USD")
        b1, b2, b3, b4, b5 = st.columns(5)
        mon_b = b1.number_input("Monitör oranı (%)", min_value=0.0, value=0.05, step=0.01, format="%.2f", key="ay_mb")
        kasa_b = b2.number_input("Kasa oranı (%)", min_value=0.0, value=1.0, step=0.01, format="%.2f", key="ay_kb")
        ek_b = b3.number_input("Ekran kartı ($/adet)", min_value=0.0, value=1.0, step=0.01, format="%.2f", key="ay_ek")
        ssd_b = b4.number_input("SSD&RAM oranı (%)", min_value=0.0, value=0.05, step=0.01, format="%.2f", key="ay_sb")
        kur = b5.number_input("USD/TL kuru", min_value=1.0, value=_guncel_kur(), step=0.5, format="%.2f", key="ay_kur")
    with st.container(border=True):
        _kart_baslik("Dönem ve gerçekleşenler")
        a1, _ = st.columns([1, 3])
        donem = a1.text_input("Dönem", value="Q1 2026", key="ay_d")
        c1, c2, c3, c4 = st.columns(4)
        mon_c = c1.number_input("Monitör ciro (USD)", min_value=0.0, value=0.0, step=1000.0, format="%.0f",
                                key="ay_mon_ciro")
        kasa_c = c2.number_input("Kasa ciro (USD)", min_value=0.0, value=0.0, step=1000.0, format="%.0f",
                                 key="ay_kasa_ciro")
        ssd_c = c3.number_input("SSD&RAM ciro (USD)", min_value=0.0, value=0.0, step=1000.0, format="%.0f",
                                key="ay_ssd_ciro")
        ek_a = c4.number_input("Ekran kartı adedi", min_value=0, value=0, step=1, key="ay_ea")
    r = ayhan_prim(mon_b, kasa_b, ek_b, ssd_b, kur, mon_c, kasa_c, ssd_c, ek_a)
    with st.container(border=True):
        _kart_baslik("Hesap sonucu", f"{_usd(r['toplam_usd'])} × {tr_sayi(kur, 2)} = {_tl(r['toplam_tl'])}")
        metrik_satiri([
            {"label": "Monitör", "value": _usd(r["mon"]), "renk": trenk("mavi")},
            {"label": "Kasa", "value": _usd(r["kasa"]), "renk": trenk("mavi")},
            {"label": "Ekran kartı", "value": _usd(r["ek"]), "renk": trenk("mavi")},
            # "SSD&RAM" tamamen büyük harf → kart etiketinde "Ssd&ram" oluyordu (cümle düzeni)
            {"label": "SSD ve RAM", "value": _usd(r["ssd"]), "renk": trenk("mavi")},
            {"label": "Toplam (USD)", "value": _usd(r["toplam_usd"]), "renk": trenk("amber")},
            {"label": "Toplam (TL)", "value": _tl(r["toplam_tl"]), "renk": trenk("yesil")},
        ])
    gecmis = prim_listele("ayhan_eroglu")
    _odeme_kaydet("ayhan_eroglu", "ay", donem, r["toplam_tl"], gecmis)
    _gecmis_odemeler("ayhan_eroglu", "ay", gecmis)


# ── Ürün kârlılık ───────────────────────────────────────────────────
def _urun_karlilik():
    with st.container(border=True):
        _kart_baslik("Hızlı hesap", "Alış + ek masraf = maliyet · marj satış fiyatı üzerinden")
        c1, c2, c3 = st.columns([1.5, 1, 1])
        ad = c1.text_input("Ürün adı (isteğe bağlı)", placeholder="Örn: Monitör XG27", key="uk_ad")
        alis = c2.number_input("Alış fiyatı ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="uk_alis")
        mt = c3.selectbox("Ek masraf tipi", ["%", "$"], key="uk_masraf_tipi")
        c4, c5, c6 = st.columns([1.5, 1, 1])
        md = c4.number_input("Ek masraf (%)" if mt == "%" else "Ek masraf ($)", min_value=0.0, value=0.0,
                             step=(0.1 if mt == "%" else 0.01), format=("%.1f" if mt == "%" else "%.2f"),
                             key="uk_masraf")
        satis = c5.number_input("Satış fiyatı ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="uk_satis")
        ind = c6.number_input("İndirim ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="uk_indirim")
        if alis > 0 and satis > 0:
            r = karlilik(alis, mt, md, satis, ind)
            st.caption((f"{ad} · " if ad else "") + f"toplam maliyet {_usd(r['maliyet'])}")
            kartlar = [{"label": "Satış fiyatı", "value": _usd(satis), "renk": trenk("metin")},
                       {"label": "Kâr", "value": _usd(r["kar"]), "renk": _renk(r["kar"])},
                       {"label": "Marj", "value": _yuzde(r["marj"]), "renk": _renk(r["kar"])}]
            if r["ind_satis"] is not None:
                kartlar += [{"label": "İndirimli fiyat", "value": _usd(r["ind_satis"]), "renk": trenk("amber")},
                            {"label": "İndirimli kâr", "value": _usd(r["ind_kar"]), "renk": _renk(r["ind_kar"]),
                             "alt": f"marj {_yuzde(r['ind_marj'])}"}]
            metrik_satiri(kartlar)
        else:
            st.caption("Alış ve satış fiyatını girince sonuç burada görünür.")

    with st.container(border=True):
        _kart_baslik("Toplu kıyaslama", "Birden fazla ürünü yan yana ekleyip kıyasla")
        st.session_state.setdefault("uk_liste", [])
        st.session_state.setdefault("uk_sayac", 0)
        with st.expander("Ürün ekle", expanded=not st.session_state.uk_liste, icon=":material/add:"):
            f1, f2, f3 = st.columns([2, 1, 1])
            fa_ad = f1.text_input("Ürün adı", placeholder="Ürün adı veya kodu", key="fa_ad")
            fa_alis = f2.number_input("Alış ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="fa_alis")
            fa_mt = f3.selectbox("Masraf tipi", ["%", "$"], key="fa_masraf_tipi")
            g1, g2, g3 = st.columns([2, 1, 1])
            fa_m = g1.number_input("Ek masraf (%)" if fa_mt == "%" else "Ek masraf ($)", min_value=0.0, value=0.0,
                                   step=(0.1 if fa_mt == "%" else 0.01), format=("%.1f" if fa_mt == "%" else "%.2f"),
                                   key="fa_masraf")
            fa_s = g2.number_input("Satış ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="fa_satis")
            fa_i = g3.number_input("İndirim ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="fa_indirim")
            if st.button("Listeye ekle", key="fa_ekle", type="primary", icon=":material/add:",
                         disabled=not (fa_alis > 0 and fa_s > 0)):
                st.session_state.uk_sayac += 1
                r = karlilik(fa_alis, fa_mt, fa_m, fa_s, fa_i)
                st.session_state.uk_liste.append(dict(r, id=st.session_state.uk_sayac, alis=fa_alis, satis=fa_s,
                                                      ad=fa_ad or f"Ürün {st.session_state.uk_sayac}"))
                st.rerun()
        if not st.session_state.uk_liste:
            st.caption("Henüz ürün eklenmedi.")
            return
        import pandas as pd
        st.dataframe(pd.DataFrame([{
            "Ürün": u["ad"], "Alış ($)": round(u["alis"], 2), "Maliyet ($)": round(u["maliyet"], 2),
            "Satış ($)": round(u["satis"], 2), "Kâr ($)": round(u["kar"], 2), "Marj (%)": round(u["marj"], 1),
            "İnd. kâr ($)": (round(u["ind_kar"], 2) if u.get("ind_kar") is not None else None),
        } for u in st.session_state.uk_liste]), hide_index=True, use_container_width=True)
        s1, s2, _ = st.columns([2, 1, 2], vertical_alignment="bottom")
        cik = s1.selectbox("Listeden çıkar", [None] + [u["id"] for u in st.session_state.uk_liste],
                           format_func=lambda i: "— seç —" if i is None else
                           next(u["ad"] for u in st.session_state.uk_liste if u["id"] == i), key="uk_cikar")
        if s2.button("Çıkar", key="uk_cikar_btn", disabled=cik is None, use_container_width=True):
            st.session_state.uk_liste = [x for x in st.session_state.uk_liste if x["id"] != cik]
            st.session_state.pop("uk_cikar", None)
            st.rerun()
        if st.button("Listeyi temizle", key="uk_temizle", type="tertiary", icon=":material/delete_sweep:"):
            st.session_state.uk_liste = []
            st.rerun()


# ── Kırılma noktası ─────────────────────────────────────────────────
def _breakeven():
    sol, sag = st.columns(2, gap="large")
    with sol, st.container(border=True):
        _kart_baslik("Parametreler", "Hedef ciro = sabit gider ÷ marj")
        periyot = st.selectbox("Periyot", ["Günlük", "Haftalık", "Aylık", "Yıllık"], index=2, key="be_periyot")
        gider = st.number_input(f"Sabit gider ($) · {periyot.lower()}", min_value=0.0, value=0.0, step=10.0,
                                format="%.2f", key="be_gider")
        marj = st.number_input("Ortalama marj (%)", min_value=0.1, max_value=99.9, value=30.0, step=0.1,
                               format="%.1f", key="be_marj")
        ort = st.number_input("Ortalama ürün fiyatı ($)", min_value=0.0, value=0.0, step=1.0, format="%.2f",
                              key="be_ort_fiyat")
        mevcut = st.number_input(f"Mevcut ciro ($) · {periyot.lower()}", min_value=0.0, value=0.0, step=100.0,
                                 format="%.2f", key="be_mevcut")
    with sag, st.container(border=True):
        _kart_baslik("Sonuç")
        if not (gider > 0 and marj > 0):
            st.caption("Sabit gider ve marj girince kırılma noktası burada görünür.")
            return
        r = kirilma(gider, marj, mevcut, ort, periyot)
        renk = "yesil" if r["asildi"] else "mor"
        st.markdown(
            f'<div style="font-size:12px;color:var(--k-silik)">Hedef ciro · {periyot.lower()}</div>'
            f'<div style="font-family:var(--k-mono);font-size:24px;font-weight:700;color:var(--k-mor2)">'
            f'{_usd_h(r["hedef"], 0)}</div>'
            f'<div style="font-size:12px;color:var(--k-silik);margin-top:10px">İlerleme · {_yuzde(r["ilerleme"])}</div>'
            f'<div style="height:10px;background:var(--k-kenar2);border-radius:5px;overflow:hidden;margin:6px 0 12px">'
            f'<div style="height:100%;width:{r["ilerleme"]:.1f}%;background:var(--k-{renk})"></div></div>',
            unsafe_allow_html=True)
        if r["asildi"]:
            st.markdown(f'<b style="color:var(--k-yesil)">Hedef aşıldı · +{_usd_h(r["fazla"], 0)} fazla</b>',
                        unsafe_allow_html=True)
            return
        kartlar = [{"label": "Kalan ciro", "value": _usd(r["kalan"], 0), "renk": trenk("amber")},
                   {"label": "Günlük gereken", "value": _usd(r["gunluk"], 0), "renk": trenk("amber2"),
                    "alt": "dönem boyunca ortalama"}]
        if r["hedef_adet"] is not None:
            kartlar.append({"label": "Hedef / kalan adet", "value": tr_sayi(r["hedef_adet"]),
                            "renk": trenk("mor"), "alt": f"{tr_sayi(r['kalan_adet'])} adet kaldı"})
        metrik_satiri(kartlar)


# ── Çalıştır ────────────────────────────────────────────────────────
SEKMELER = {"karlilik": "Ürün kârlılık", "breakeven": "Kırılma noktası",
            "prim_gokhan": "Gökhan Yavuz primi", "prim_ayhan": "Ayhan Eroğlu primi"}


def run():
    st.markdown(_sb("🧮 Hesap Makinesi", "Hesaplayıcılar",
                    aciklama="Ürün kârlılığı · kırılma noktası · prim hesabı"), unsafe_allow_html=True)
    st.session_state.setdefault("hm_sekme", "karlilik")
    if st.session_state.get("hm_sekme") not in SEKMELER:
        st.session_state["hm_sekme"] = "karlilik"

    # Sekme seçici parçanın İÇİNDE: sekme değişince yalnız gövde yenilenir
    # (eskiden düğme + tüm sayfayı yeniden çalıştırma).
    @st.fragment
    def _sayfa_parcasi():
        sekme = st.segmented_control("Sekme", list(SEKMELER), format_func=SEKMELER.get, key="hm_sekme",
                                     label_visibility="collapsed") or "karlilik"
        {"karlilik": _urun_karlilik, "breakeven": _breakeven,
         "prim_gokhan": _prim_gokhan, "prim_ayhan": _prim_ayhan}[sekme]()

    _sayfa_parcasi()

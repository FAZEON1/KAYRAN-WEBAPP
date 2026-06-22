# -*- coding: utf-8 -*-
"""Teknik Servis / İade modülü — arayüz (V1)."""
from datetime import datetime, date

import streamlit as st
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici

from .database import (
    ARAYUZLER, ARAYUZ_ETIKET, DURUMLAR, BITMIS_DURUMLAR, DURUM_RENK,
    DEPOLAR, FIRMA_ONERILER,
    get_kayitlar, get_kayit, get_gecmis, ekle_kayit, durum_guncelle,
    kayit_guncelle, urun_getir, is_gunu_farki, sla_renk, ithalat_model_listesi,
)


# ── Başlık yardımcıları (portal teması) ──────────────────────────────
def _baslik(ikon, ad, alt):
    st.markdown(
        f'<div style="margin:2px 0 18px">'
        f'<div style="font-family:Inter,sans-serif;font-size:24px;font-weight:800;color:#FFFFFF;letter-spacing:-0.3px">{ikon} {ad}</div>'
        f'<div style="color:#94A3B8;font-size:13px;margin-top:4px">{alt}</div>'
        f'<div style="height:1px;background:linear-gradient(90deg,rgba(244,114,182,0.4),transparent);margin-top:12px"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _alt_baslik(t):
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#FDA4AF;letter-spacing:1.2px;'
        f'text-transform:uppercase;margin:14px 0 10px">{t}</div>',
        unsafe_allow_html=True,
    )


def _durum_chip(durum):
    renk = DURUM_RENK.get(durum, "#94A3B8")
    return (f'<span style="background:{renk}22;border:1px solid {renk}55;color:{renk};'
            f'border-radius:6px;padding:2px 9px;font-size:11px;font-weight:700;white-space:nowrap">{durum}</span>')


def _sla_chip(kayit):
    bitmis = kayit.get("mevcut_durum") in BITMIS_DURUMLAR
    g = is_gunu_farki(kayit.get("mal_kabul_tarihi"))
    renk, txt = sla_renk(g, bitmis)
    return (f'<span style="background:{renk}22;border:1px solid {renk}55;color:{renk};'
            f'border-radius:6px;padding:2px 9px;font-size:11px;font-weight:700;white-space:nowrap">{txt}</span>')


def _tarih_kisa(v):
    if not v:
        return "—"
    s = str(v)
    try:
        dt = datetime.fromisoformat(s[:19])
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return s[:16]


def _g(kayit, alan, bos="—"):
    v = kayit.get(alan)
    return v if (v not in (None, "")) else bos


# ── Mal Kabül ────────────────────────────────────────────────────────
def _mal_kabul():
    _baslik("📥", "Mal Kabül", "Servise/iadeye gelen ürünü kaydet · Servis No otomatik üretilir (G5F)")

    arayuz_lbl = st.radio("Arayüz", ["🔧 Teknik Servis", "↩️ İade"],
                          horizontal=True, key="mk_arayuz")
    arayuz = "teknik" if "Teknik" in arayuz_lbl else "iade"

    # Stok kodu eşleştirme (form dışı — Ürün Yönetimi'nden otomatik çekme)
    # 📦 İthalat'tan model seç (tüm modeller) — seçince stok kodu + stok adı dolar
    _modeller = ithalat_model_listesi()
    if _modeller:
        _opts = ["— İthalat'tan model seç —"] + [(f"{s} — {a}" if a else s) for s, a in _modeller]
        _sec_model = st.selectbox(f"📦 İthalat modeli seç ({len(_modeller)} model · yazarak ara)",
                                  _opts, key="mk_model_sec")
        if _sec_model != _opts[0] and st.session_state.get("_mk_model_son") != _sec_model:
            st.session_state["_mk_model_son"] = _sec_model
            _sku_sel = _sec_model.split(" — ")[0].strip()
            st.session_state["mk_sk"] = _sku_sel
            for _s, _a in _modeller:
                if _s == _sku_sel and _a:
                    st.session_state["mk_stok_adi"] = _a
                    break
            st.rerun()

    es1, es2 = st.columns([3, 1])
    with es1:
        sk = st.text_input("Stok Kodu *", key="mk_sk", placeholder="EAN okut veya stok kodu yaz")
    with es2:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("🔍 Eşleştir", use_container_width=True, key="mk_eslestir"):
            u = urun_getir(sk)
            if u and (u.get("stok_adi") or u.get("urun_grubu")):
                st.session_state["mk_stok_adi"] = u.get("stok_adi", "")
                st.session_state["mk_urun_grubu"] = u.get("urun_grubu", "")
                st.session_state["mk_ean"] = u.get("ean", "")
                st.toast("✅ Ürün Yönetimi'nden eşleşti")
            else:
                st.toast("⚠ Ürün Yönetimi'nde bulunamadı — bilgileri elle gir")
            st.rerun()

    with st.form("mk_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        stok_adi = c1.text_input("Stok Adı", value=st.session_state.get("mk_stok_adi", ""))
        urun_grubu = c2.text_input("Ürün Grubu", value=st.session_state.get("mk_urun_grubu", ""))
        ean = c3.text_input("EAN (opsiyonel)", value=st.session_state.get("mk_ean", ""))

        d1, d2, d3 = st.columns(3)
        seri = d1.text_input("Seri No *")
        firma = d2.selectbox("Firma Bilgisi", FIRMA_ONERILER)
        sevk = d3.text_input("Sevk / Kargo Bilgisi", placeholder="UPS takip no / firma sevkiyat")

        ariza = st.text_input("Arıza *", placeholder="örn: güç kaynağı bozuk")
        detay = st.text_area("Detay / Not", height=68, placeholder="örn: hiç açılmıyor")

        _alt_baslik("Müşteri / Firma Bilgisi")
        m1, m2, m3 = st.columns(3)
        m_adi = m1.text_input("Müşteri / Firma Adı", placeholder="örn: Vatan - Buyaka")
        m_mail = m2.text_input("Mail")
        m_tel = m3.text_input("Telefon")
        m_adres = st.text_input("Adres")

        _alt_baslik("Belge — faturasız/irsaliyesiz ürün kabul edilmez")
        f1, f2 = st.columns(2)
        fatura = f1.text_input("Fatura No *")
        irsaliye = f2.text_input("İrsaliye No")
        firma_servis_no = f1.text_input("Firma Servis Form No", placeholder="ör. 11MS0072257")

        _alt_baslik("Ön Kontrol")
        i1, i2 = st.columns(2)
        icerik = i1.text_input("İçerik Durumu", placeholder="tam / eksik — (monitör: hdmi, dp, adaptör...)")
        fiziksel = i2.text_input("Fiziksel Durum", placeholder="hasarsız / çizik / tozlu / kullanılmış")

        personel = st.text_input("Kayıt Yapan Personel",
                                 value=st.session_state.get("aktif_kullanici", "").capitalize())

        kaydet = st.form_submit_button("✅ Kayıt Tamamla", type="primary", use_container_width=True)

    if kaydet:
        if not (sk or "").strip():
            st.error("Stok Kodu zorunludur.")
            return
        if not seri.strip():
            st.error("Seri No zorunludur.")
            return
        if not ariza.strip():
            st.error("Arıza alanı zorunludur.")
            return
        if not fatura.strip():
            st.error("Fatura No zorunludur — faturasız ürün kabul edilmez.")
            return
        data = {
            "arayuz": arayuz, "stok_kodu": sk.strip(), "ean": ean.strip(),
            "urun_grubu": urun_grubu.strip(), "stok_adi": stok_adi.strip(),
            "seri_no": seri.strip(), "ariza": ariza.strip(), "detay": detay.strip(),
            "firma_bilgisi": firma, "sevk_kargo_bilgisi": sevk.strip(),
            "musteri_adi": m_adi.strip(), "musteri_mail": m_mail.strip(),
            "musteri_tel": m_tel.strip(), "musteri_adres": m_adres.strip(),
            "fatura_no": fatura.strip(), "irsaliye_no": irsaliye.strip(),
            "firma_servis_form_no": firma_servis_no.strip(),
            "icerik_durumu": icerik.strip(), "fiziksel_durum": fiziksel.strip(),
        }
        ok, msg, form_no = ekle_kayit(data, personel.strip())
        if ok:
            st.success(msg)
            for k in ("mk_stok_adi", "mk_urun_grubu", "mk_ean"):
                st.session_state.pop(k, None)
            st.balloons()
        else:
            st.error(msg)


# ── Liste (Teknik Servis / İade) ─────────────────────────────────────
def _liste(arayuz):
    etk = "Teknik Servis" if arayuz == "teknik" else "İade"
    ikon = "🔧" if arayuz == "teknik" else "↩️"
    _baslik(ikon, f"{etk} Arayüzü", "Aktif kayıtlar · 21 iş günü SLA renkleri · detay için kayıt seç")

    kayitlar = get_kayitlar(arayuz=arayuz, depolu=False)
    if not kayitlar:
        st.info(f"Henüz {etk.lower()} kaydı yok. **Mal Kabül**'den ekleyebilirsin.")
        return

    fc1, fc2 = st.columns([1.4, 2])
    with fc1:
        durum_f = st.selectbox("Durum filtresi", ["Aktif (bitmemiş)", "Tümü"] + DURUMLAR,
                               key=f"ts_durf_{arayuz}")
    with fc2:
        ara = st.text_input("🔍 Ara — Servis No · Stok · Seri · Firma · Müşteri",
                            key=f"ts_ara_{arayuz}")

    def _uyar(k):
        if durum_f == "Tümü":
            pass
        elif durum_f == "Aktif (bitmemiş)":
            if k.get("mevcut_durum") in BITMIS_DURUMLAR:
                return False
        elif k.get("mevcut_durum") != durum_f:
            return False
        if ara:
            blob = " ".join(str(k.get(a, "") or "") for a in
                            ("servis_form_no", "stok_kodu", "stok_adi", "seri_no",
                             "firma_bilgisi", "musteri_adi")).lower()
            if ara.lower() not in blob:
                return False
        return True

    goster = [k for k in kayitlar if _uyar(k)]
    st.caption(f"{len(goster)} / {len(kayitlar)} kayıt")

    # HTML tablo
    satirlar = ""
    for k in goster:
        satirlar += (
            "<tr>"
            f'<td style="font-weight:700;color:#FDA4AF">{_g(k, "servis_form_no")}</td>'
            f'<td>{_g(k, "stok_kodu")}</td>'
            f'<td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{_g(k, "stok_adi", "")}">{_g(k, "stok_adi")}</td>'
            f'<td>{_g(k, "seri_no")}</td>'
            f'<td>{_g(k, "firma_bilgisi")}</td>'
            f'<td>{_durum_chip(k.get("mevcut_durum", ""))}</td>'
            f'<td>{_sla_chip(k)}</td>'
            f'<td style="color:#94A3B8;font-size:11px">{_tarih_kisa(k.get("mal_kabul_tarihi"))}</td>'
            "</tr>"
        )
    st.html(
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px">'
        '<thead><tr style="text-align:left;color:#64748B;font-size:10.5px;text-transform:uppercase;letter-spacing:0.5px">'
        '<th style="padding:6px 8px">Servis No</th><th>Stok Kodu</th><th>Stok Adı</th>'
        '<th>Seri No</th><th>Firma</th><th>Durum</th><th>SLA</th><th>Mal Kabül</th>'
        '</tr></thead>'
        '<tbody style="color:#E2E8F0">'
        + satirlar.replace("<td>", '<td style="padding:7px 8px;border-top:1px solid rgba(255,255,255,0.05)">')
        + '</tbody></table></div>'
    )

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    if goster:
        secenekler = {f'{k.get("servis_form_no","")} — {(k.get("stok_adi") or k.get("stok_kodu") or "")[:45]}': k
                      for k in goster}
        sec = st.selectbox("🔎 Detay / işlem için kayıt seç", list(secenekler.keys()),
                           key=f"ts_sec_{arayuz}")
        if sec:
            _kontrol_paneli(secenekler[sec])


# ── Kontrol Paneli (detay) ───────────────────────────────────────────
def _kontrol_paneli(kayit):
    kid = kayit["id"]
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    bitmis = kayit.get("mevcut_durum") in BITMIS_DURUMLAR
    g = is_gunu_farki(kayit.get("mal_kabul_tarihi"))
    renk, sla_txt = sla_renk(g, bitmis)

    # Üst kart
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);'
        f'border-radius:12px;padding:18px 20px;margin-bottom:14px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
        f'<div><div style="color:#FDA4AF;font-size:20px;font-weight:800">{_g(kayit, "servis_form_no")}</div>'
        f'<div style="color:#94A3B8;font-size:12px;margin-top:2px">{ARAYUZ_ETIKET.get(kayit.get("arayuz",""),"")} · {_g(kayit,"stok_kodu")} · Seri {_g(kayit,"seri_no")}</div></div>'
        f'<div style="display:flex;gap:8px;align-items:center">{_durum_chip(kayit.get("mevcut_durum",""))}'
        f'<span style="background:{renk}22;border:1px solid {renk}55;color:{renk};border-radius:6px;padding:3px 10px;font-size:12px;font-weight:700">⏱ {sla_txt}</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    sol, sag = st.columns([1.6, 1])

    with sol:
        def _satir(et, deg):
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)">'
                f'<div style="color:#64748B;font-size:12px;min-width:150px">{et}</div>'
                f'<div style="color:#E2E8F0;font-size:12.5px">{deg}</div></div>',
                unsafe_allow_html=True)

        _alt_baslik("Ürün Bilgisi")
        _satir("Stok Adı", _g(kayit, "stok_adi"))
        _satir("Ürün Grubu", _g(kayit, "urun_grubu"))
        _satir("EAN", _g(kayit, "ean"))
        _satir("İçerik Durumu", _g(kayit, "icerik_durumu"))
        _satir("Fiziksel Durum", _g(kayit, "fiziksel_durum"))

        _alt_baslik("Arıza / İşlem")
        _satir("Müşteri Şikayet", _g(kayit, "ariza"))
        _satir("Detay", _g(kayit, "detay"))
        _satir("Yapılan İşlem", _g(kayit, "yapilan_islem"))
        _satir("Test Süreci", _g(kayit, "test_sureci"))

        _alt_baslik("Müşteri / Firma")
        _satir("Firma Bilgisi", _g(kayit, "firma_bilgisi"))
        _satir("Müşteri / Firma Adı", _g(kayit, "musteri_adi"))
        _satir("Mail", _g(kayit, "musteri_mail"))
        _satir("Telefon", _g(kayit, "musteri_tel"))
        _satir("Adres", _g(kayit, "musteri_adres"))

        _alt_baslik("Belge / Sevk")
        _satir("Fatura No", _g(kayit, "fatura_no"))
        _satir("İrsaliye No", _g(kayit, "irsaliye_no"))
        _satir("Firma Servis Form No", _g(kayit, "firma_servis_form_no"))
        _satir("Sevk / Kargo", _g(kayit, "sevk_kargo_bilgisi"))
        _satir("Kayıt Yapan", _g(kayit, "personel"))

        if any(kayit.get(a) for a in ("degisim_stok_kodu", "degisim_stok_adi", "degisim_seri_no")):
            _alt_baslik("Değişim Yapılan Ürün")
            _satir("Stok Kodu", _g(kayit, "degisim_stok_kodu"))
            _satir("Stok Adı", _g(kayit, "degisim_stok_adi"))
            _satir("Seri No", _g(kayit, "degisim_seri_no"))

    with sag:
        _alt_baslik("İşlem Geçmişi")
        gecmis = get_gecmis(kid)
        if gecmis:
            tl = ""
            for h in gecmis:
                rk = DURUM_RENK.get(h.get("durum", ""), "#94A3B8")
                tl += (
                    f'<div style="display:flex;gap:10px;padding:6px 0">'
                    f'<div style="width:9px;height:9px;border-radius:50%;background:{rk};margin-top:4px;flex-shrink:0"></div>'
                    f'<div><div style="color:{rk};font-size:12px;font-weight:700">{h.get("durum","")}</div>'
                    f'<div style="color:#64748B;font-size:10.5px">{_tarih_kisa(h.get("tarih"))} · {h.get("personel","") or "—"}</div>'
                    + (f'<div style="color:#94A3B8;font-size:11px">{h.get("aciklama")}</div>' if h.get("aciklama") else "")
                    + '</div></div>'
                )
            st.markdown(
                f'<div style="border-left:2px solid rgba(255,255,255,0.08);padding-left:12px;margin-left:4px">{tl}</div>',
                unsafe_allow_html=True)
        else:
            st.caption("Henüz işlem geçmişi yok.")

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    # ── İşlemler ──
    with st.expander("⚙️ Durum Güncelle / İşlem Yap", expanded=False):
        with st.form(f"ts_durum_{kid}"):
            u1, u2 = st.columns(2)
            mevcut = kayit.get("mevcut_durum", "mal kabül")
            idx = DURUMLAR.index(mevcut) if mevcut in DURUMLAR else 0
            yeni_durum = u1.selectbox("Yeni Durum", DURUMLAR, index=idx)
            personel = u2.text_input("İşlemi Yapan",
                                     value=st.session_state.get("aktif_kullanici", "").capitalize())
            yapilan = st.text_input("Yapılan İşlem / Açıklama",
                                    placeholder="örn: güç kaynağı değiştirildi")
            test = st.text_area("Test Süreci (opsiyonel)", height=60)
            if st.form_submit_button("💾 Durumu Güncelle", type="primary", use_container_width=True):
                ekstra = {}
                if yapilan.strip():
                    ekstra["yapilan_islem"] = yapilan.strip()
                if test.strip():
                    ekstra["test_sureci"] = test.strip()
                if durum_guncelle(kid, yeni_durum, personel.strip(), yapilan.strip(), ekstra):
                    st.success(f"✅ Durum güncellendi: {yeni_durum}")
                    st.rerun()
                else:
                    st.error("Güncelleme başarısız.")

    with st.expander("📦 Depoya Transfer (işlem bitti)", expanded=False):
        st.caption("İşlemi biten ürünü ilgili depoya aktar. Aktif arayüzden düşmez, Depolar sekmesinde görünür.")
        t1, t2 = st.columns([2, 1])
        depo = t1.selectbox("Hedef Depo", DEPOLAR, key=f"ts_depo_{kid}")
        t2.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if t2.button("Transfer Et", use_container_width=True, key=f"ts_tbtn_{kid}"):
            durum_haritasi = {"outlet": "satışa hazır", "ikinci el": "satışa hazır",
                              "hurda": "hurda", "merkez": "gönderildi"}
            yeni = durum_haritasi.get(depo, kayit.get("mevcut_durum"))
            if durum_guncelle(kid, yeni, st.session_state.get("aktif_kullanici", ""),
                              f"{depo} deposuna transfer", {"depo": depo}):
                st.success(f"✅ {depo} deposuna aktarıldı")
                st.rerun()
            else:
                st.error("Transfer başarısız.")


# ── Depolar ──────────────────────────────────────────────────────────
def _depolar():
    _baslik("📦", "Depolar", "İşlemi biten ürünler · outlet / 2.el / hurda / merkez · satışa hazır → satıldı")
    kayitlar = get_kayitlar(depolu=True)
    if not kayitlar:
        st.info("Henüz depoya aktarılmış ürün yok. Bir kaydın Kontrol Paneli'nden **Depoya Transfer** yapabilirsin.")
        return

    f1, f2 = st.columns([1.4, 2])
    depo_f = f1.selectbox("Depo filtresi", ["Tümü"] + DEPOLAR, key="depo_filtre")
    ara = f2.text_input("🔍 Ara — Servis No · Stok · Seri", key="depo_ara")

    def _uy(k):
        if depo_f != "Tümü" and (k.get("depo") or "") != depo_f:
            return False
        if ara:
            blob = " ".join(str(k.get(a, "") or "") for a in
                            ("servis_form_no", "stok_kodu", "stok_adi", "seri_no")).lower()
            if ara.lower() not in blob:
                return False
        return True

    goster = [k for k in kayitlar if _uy(k)]
    st.caption(f"{len(goster)} / {len(kayitlar)} ürün")

    for k in goster:
        kid = k["id"]
        satildi = k.get("mevcut_durum") == "satıldı"
        with st.container():
            c1, c2, c3 = st.columns([3, 1.4, 1.4])
            with c1:
                st.markdown(
                    f'<div style="padding:6px 0"><span style="color:#FDA4AF;font-weight:700">{_g(k,"servis_form_no")}</span> · '
                    f'{_g(k,"stok_kodu")} · <span style="color:#94A3B8">{(_g(k,"stok_adi","")[:50])}</span><br>'
                    f'<span style="color:#64748B;font-size:11px">Seri {_g(k,"seri_no")} · Depo: {_g(k,"depo")}</span> '
                    f'{_durum_chip(k.get("mevcut_durum",""))}</div>',
                    unsafe_allow_html=True)
            with c2:
                if not satildi:
                    if k.get("mevcut_durum") != "satışa hazır":
                        if st.button("✅ Satışa Hazır", key=f"sh_{kid}", use_container_width=True):
                            durum_guncelle(kid, "satışa hazır", st.session_state.get("aktif_kullanici", ""),
                                           "Satışa hazır işaretlendi")
                            st.rerun()
            with c3:
                if not satildi:
                    with st.popover("💰 Satıldı", use_container_width=True):
                        sf = st.text_input("Satış Firma/Kişi", key=f"sf_{kid}")
                        sfiyat = st.number_input("Satış Fiyatı ($)", min_value=0.0, step=1.0,
                                                 format="%.2f", key=f"sfi_{kid}")
                        bedelsiz = st.checkbox("Bedelsiz", key=f"bd_{kid}")
                        if st.button("Kaydet", key=f"sk_{kid}", type="primary", use_container_width=True):
                            durum_guncelle(kid, "satıldı", st.session_state.get("aktif_kullanici", ""),
                                           "Satış yapıldı",
                                           {"satis_firma": sf.strip(),
                                            "satis_fiyati": float(sfiyat or 0),
                                            "bedelsiz": bool(bedelsiz),
                                            "satis_tarihi": date.today().isoformat()})
                            st.rerun()
                else:
                    st.markdown('<div style="text-align:center;color:#10B981;font-weight:700;padding:8px 0">✓ Satıldı</div>',
                                unsafe_allow_html=True)
        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.05);margin:4px 0"></div>',
                    unsafe_allow_html=True)


# ── Ana çalıştırıcı ──────────────────────────────────────────────────
def run():
    """Teknik Servis modülü — portal tarafından çağrılır."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown(
        "<style>"
        ".main .block-container{max-width:1200px !important;}"
        "[data-testid=\"stMetric\"]{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);"
        "border-radius:12px;padding:12px 16px;}"
        "</style>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(sidebar_stil(), unsafe_allow_html=True)
        st.markdown(sidebar_baslik("🛠️", "Teknik Servis", "Servis & İade"), unsafe_allow_html=True)
        if aktif_kullanici:
            st.markdown(sidebar_kullanici(aktif_kullanici), unsafe_allow_html=True)
            if st.button("Çıkış Yap", use_container_width=True, key="ts_cikis"):
                st.session_state.giris_yapildi = False
                st.session_state.aktif_kullanici = ""
                st.session_state.aktif_uygulama = "anasayfa"
                st.rerun()
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        sayfa = st.radio(
            "Sayfa",
            ["📥  Mal Kabül", "🔧  Teknik Servis", "↩️  İade", "📦  Depolar"],
            label_visibility="collapsed", key="ts_sayfa",
        )

    if sayfa == "📥  Mal Kabül":
        _mal_kabul()
    elif sayfa == "🔧  Teknik Servis":
        _liste("teknik")
    elif sayfa == "↩️  İade":
        _liste("iade")
    else:
        _depolar()

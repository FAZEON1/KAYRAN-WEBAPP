# -*- coding: utf-8 -*-
"""Teknik Servis / İade modülü — arayüz (V1)."""
from datetime import datetime, date
from io import BytesIO

import pandas as pd
import streamlit as st
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici

from .database import (
    ARAYUZLER, ARAYUZ_ETIKET, DURUMLAR, BITMIS_DURUMLAR, DURUM_RENK,
    DEPOLAR, FIRMA_ONERILER, TS_FIRMALAR,
    get_kayitlar, get_kayit, get_gecmis, ekle_kayit, durum_guncelle,
    kayit_guncelle, sil_kayit, urun_getir, is_gunu_farki, sla_renk, sla_is_gunu, ithalat_model_listesi,
    ts_urun_gruplari, servis_formu_pdf,
    depo_etiket_pdf,
)


# İçerik durumu / Eksik içerik için seçilebilir standart seçenekler (madde 4-5).
# Kullanıcı bunlardan seçebilir + serbestçe yenisini yazabilir (multiselect accept_new_options).
ICERIK_SECENEKLER = [
    "Tam / eksiksiz", "Kutulu", "Kutusuz", "Adaptör", "Güç kablosu", "HDMI kablo",
    "DisplayPort kablo", "USB kablo", "Ayak / Stand", "Vida / Montaj aparatı",
    "Kumanda", "Kullanım kılavuzu", "Fatura / İrsaliye", "Poşet / Köpük",
]
EKSIK_ICERIK_SECENEKLER = [
    "Adaptör yok", "Güç kablosu yok", "HDMI kablo yok", "DisplayPort kablo yok",
    "USB kablo yok", "Ayak / Stand yok", "Vida / Montaj aparatı yok", "Kumanda yok",
    "Kutu yok", "Kullanım kılavuzu yok", "Poşet / Köpük yok", "Aksesuar eksik",
]


def _coklu_deger(kayit_deger):
    """DB'deki ' · ' ile ayrılmış metni multiselect default listesine çevirir."""
    s = str(kayit_deger or "").strip()
    if not s:
        return []
    return [p.strip() for p in s.split("·") if p.strip()]


def _icerik_multiselect(st_col, etiket, secenekler, kayit_deger, key):
    """Seçilebilir + serbest metin girilebilir içerik alanı. ' · ' ile birleşik string döner."""
    _mevcut = _coklu_deger(kayit_deger)
    _opts = list(dict.fromkeys(secenekler + _mevcut))  # mevcut özel değerler de listede görünsün
    try:
        _sec = st_col.multiselect(etiket, _opts, default=_mevcut, key=key,
                                  accept_new_options=True,
                                  help="Listeden seç ya da yaz + Enter ile yeni ekle.")
    except TypeError:
        # Eski Streamlit: accept_new_options yoksa serbest metni ayrı kutudan al
        _sec = st_col.multiselect(etiket, _opts, default=_mevcut, key=key)
        _ek = st_col.text_input(f"{etiket} — listede yoksa yaz", key=f"{key}_yeni",
                                placeholder="virgülle birden çok: hdmi, adaptör")
        if _ek.strip():
            _sec = list(_sec) + [x.strip() for x in _ek.split(",") if x.strip()]
    return " · ".join(dict.fromkeys(_sec))


# ── Başlık yardımcıları (portal teması) ──────────────────────────────
def _baslik(ikon, ad, alt):
    from shared.ui import sayfa_baslik as _sb
    st.markdown(_sb(ikon, ad, alt), unsafe_allow_html=True)

def _alt_baslik(t):
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:#FDA4AF;letter-spacing:1.2px;'
        f'text-transform:uppercase;margin:16px 0 8px">{t}</div>',
        unsafe_allow_html=True,
    )


def _durum_chip(durum):
    renk = DURUM_RENK.get(durum, "#94A3B8")
    return (f'<span style="background:{renk}22;border:1px solid {renk}55;color:{renk};'
            f'border-radius:6px;padding:0px 8px;font-size:11px;font-weight:700;white-space:nowrap">{durum}</span>')


def _sla_chip(kayit):
    bitmis = kayit.get("mevcut_durum") in BITMIS_DURUMLAR
    g = sla_is_gunu(kayit)
    renk, txt = sla_renk(g, bitmis)
    return (f'<span style="background:{renk}22;border:1px solid {renk}55;color:{renk};'
            f'border-radius:6px;padding:0px 8px;font-size:11px;font-weight:700;white-space:nowrap">{txt}</span>')


def _tarih_kisa(v):
    if not v:
        return "—"
    s = str(v)
    try:
        dt = datetime.fromisoformat(s[:19])
        return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        return s[:16]


def _g(kayit, alan, bos="—"):
    v = kayit.get(alan)
    return v if (v not in (None, "")) else bos


# ── Mal Kabül ────────────────────────────────────────────────────────
def _mal_kabul():
    _baslik("📥", "Mal Kabül", "Servise/iadeye gelen ürünü kaydet · Servis No otomatik üretilir (G5F)")

    # Bir önceki kaydın başarı mesajı (rerun sonrası kaybolmasın)
    _son_ok = st.session_state.pop("_mk_kayit_ok", None)
    if _son_ok:
        st.success(f"✅ Kayıt tamamlandı: {_son_ok} — yeni kayda hazır.")

    # ➕ Yeni Mal Kabül — AÇILIR PENCERE (ana ekran uzamaz)
    _mk1, _mk2 = st.columns([1, 4])
    if _mk1.button("📥 Yeni Mal Kabül", type="primary", use_container_width=True, key="mk_ac_btn"):
        st.session_state["_mk_dialog_ac"] = True
        # yeni kayda temiz başla
        for _k in ("mk_stok_adi", "mk_urun_grubu", "mk_ean", "mk_grup_yeni", "mk_grup_sec",
                   "mk_m_adi", "mk_m_mail", "mk_m_tel", "mk_m_adres", "mk_kargo",
                   "mk_mgz_sec", "_mk_mgz_son", "mk_firma_yeni", "_mk_firma_hedef",
                   "mk_sk", "_mk_model_son", "mk_model_sec"):
            st.session_state.pop(_k, None)
        st.rerun()
    _mk2.caption("Servise/iadeye gelen ürünü kaydetmek için butona bas — açılır pencerede doldur.")

    if st.session_state.pop("_mk_dialog_ac", False):
        _mal_kabul_dialog()


@st.dialog("📥 Yeni Mal Kabül", width="large")
def _mal_kabul_dialog():
    # 1️⃣ İşlem türü — en başta ve BELİRGİN (yanlış türde kayıt açılmasın)
    st.markdown('<div style="font-size:15px;font-weight:800;color:#FBBF24;margin:8px 0 0px">'
                '1️⃣ Önce işlem türünü seç</div>', unsafe_allow_html=True)
    arayuz_lbl = st.radio("İşlem türü", ["🔧 Teknik Servis", "↩️ İade"],
                          horizontal=True, key="mk_arayuz", label_visibility="collapsed")
    arayuz = "teknik" if "Teknik" in arayuz_lbl else "iade"
    if arayuz == "teknik":
        st.markdown('<div style="background:rgba(167,139,250,.15);border:1px solid #A78BFA;'
                    'border-radius:8px;padding:8px 12px;margin:4px 0 12px;color:#C4B5FD;'
                    'font-weight:700;font-size:13px">🔧 TEKNİK SERVİS kaydı oluşturuyorsun</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:rgba(244,114,182,.15);border:1px solid #F472B6;'
                    'border-radius:8px;padding:8px 12px;margin:4px 0 12px;color:#F9A8D4;'
                    'font-weight:700;font-size:13px">↩️ İADE kaydı oluşturuyorsun</div>',
                    unsafe_allow_html=True)

    # 📦 İthalat'tan model seç — seçince stok kodu + stok adı dolar
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
            st.session_state["_mk_dialog_ac"] = True
            st.rerun()

    es1, es2 = st.columns([3, 1])
    with es1:
        sk = st.text_input("Stok Kodu *", key="mk_sk", placeholder="Stok kodu yaz")
    with es2:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("🔍 Eşleştir", use_container_width=True, key="mk_eslestir"):
            u = urun_getir(sk)
            if u and (u.get("stok_adi") or u.get("urun_grubu")):
                st.session_state["mk_stok_adi"] = u.get("stok_adi", "")
                st.session_state["mk_urun_grubu"] = u.get("urun_grubu", "")
                st.toast("✅ Ürün Yönetimi'nden eşleşti")
            else:
                st.toast("⚠ Ürün Yönetimi'nde bulunamadı — bilgileri elle gir")
            st.session_state["_mk_dialog_ac"] = True
            st.rerun()


    # 🏢 Firma cari — form DIŞINDA (değişince mağaza listesi anında filtrelensin, madde 6)
    from .magazalar import magaza_listesi, magaza_cari, _cari_grup
    # Mağaza seçiminden gelen otomatik cari (rerun sonrası index olarak uygulanır — session_state
    # widget'ı çizildikten SONRA değiştirilemeyeceği için index yöntemi kullanılır)
    _hedef_cari = st.session_state.pop("_mk_firma_hedef", None)
    _fi = 0
    if _hedef_cari and _hedef_cari in TS_FIRMALAR:
        _fi = TS_FIRMALAR.index(_hedef_cari)
    elif st.session_state.get("mk_firma_sec") in TS_FIRMALAR:
        _fi = TS_FIRMALAR.index(st.session_state["mk_firma_sec"])
    _fc1, _fc2 = st.columns(2)
    firma_sec = _fc1.selectbox("Firma (cari unvan)", TS_FIRMALAR, index=_fi, key="mk_firma_sec")
    firma_yeni = _fc2.text_input("Firma listede yoksa tam cari unvanı yaz (yeni firma)",
                                 key="mk_firma_yeni", placeholder="örn. ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ")

    # 🏬 Mağaza seç — firma cari'ye göre; mağaza seçilince firma cari OTOMATİK atanır (madde 6)
    _cur_firma = firma_sec or ""
    _grup = _cari_grup(_cur_firma)  # seçili cariye ait mağaza grubu (yoksa None → tüm mağazalar)
    _mgz = magaza_listesi(_grup) if _grup else magaza_listesi()
    if _mgz:
        _grup_ad = _grup if _grup else "tüm firmalar"
        _mopts = [f"— Mağaza seç ({_grup_ad}) —"] + [m["ad"] for m in _mgz]
        _msec = st.selectbox(f"🏬 Mağaza seç ({len(_mgz)} mağaza · yazarak ara)",
                             _mopts, key="mk_mgz_sec")
        if _msec != _mopts[0] and st.session_state.get("_mk_mgz_son") != _msec:
            st.session_state["_mk_mgz_son"] = _msec
            for _m in _mgz:
                if _m["ad"] == _msec:
                    st.session_state["mk_m_adi"] = _m["ad"]
                    st.session_state["mk_m_tel"] = _m.get("tel", "")
                    if _m.get("mail"):
                        st.session_state["mk_m_mail"] = _m.get("mail", "")
                    _adr = _m.get("adres", "")
                    _yer = " / ".join([x for x in (_m.get("ilce", ""), _m.get("sehir", "")) if x])
                    st.session_state["mk_m_adres"] = (f"{_adr} — {_yer}".strip(" —") if _yer else _adr)
                    # Mağaza → firma cari OTOMATİK set: widget key'e DEĞİL, hedef key'e yaz + rerun
                    _oto_cari = magaza_cari(_m["ad"])
                    if _oto_cari and _oto_cari in TS_FIRMALAR:
                        st.session_state["_mk_firma_hedef"] = _oto_cari
                    break
            st.session_state["_mk_dialog_ac"] = True
            st.rerun()

    # Sevk / Teslim Şekli — form DIŞINDA (Kargo seçilince Kargo Takip No görünsün)
    sevk_yontemi = st.selectbox(
        "Sevk / Teslim Şekli",
        ["(Seçilmedi)", "Selçuk Aydoğan", "Firma sevkiyat", "Depodan teslimat", "Kargo"],
        key="mk_sevk_y")

    # Barkod okuyucular her okutmada Enter gönderir; Enter formu GÖNDERMESİN
    # (kayıt yalnız "✅ Kayıt Tamamla" butonuyla tamamlanır)
    with st.form("mk_form", clear_on_submit=False, enter_to_submit=False):
        c1, c2 = st.columns(2)
        stok_adi = c1.text_input("Stok Adı", value=st.session_state.get("mk_stok_adi", ""))
        _gruplar = ts_urun_gruplari()
        _pre_grup = st.session_state.get("mk_urun_grubu", "").strip()
        _grup_opts = ["— ürün grubu seç —"] + _gruplar
        if _pre_grup and _pre_grup not in _grup_opts:
            _grup_opts.insert(1, _pre_grup)
        _gidx = _grup_opts.index(_pre_grup) if _pre_grup in _grup_opts else 0
        urun_grubu_sec = c2.selectbox("Ürün Grubu", _grup_opts, index=_gidx, key="mk_grup_sec")
        urun_grubu_yeni = st.text_input("Ürün grubu listede yoksa yaz (yeni grup)",
                                        key="mk_grup_yeni", placeholder="örn. Monitör / Kasa / Klavye")
        urun_grubu = (urun_grubu_yeni.strip()
                      or (urun_grubu_sec if urun_grubu_sec != "— ürün grubu seç —" else "")).strip()

        seri = st.text_input("Seri No *")
        firma = (st.session_state.get("mk_firma_yeni", "").strip()
                 or st.session_state.get("mk_firma_sec", "")).strip()

        # Kargo Takip No — yalnızca "Kargo" seçilirse görünür
        kargo_takip = ""
        if str(st.session_state.get("mk_sevk_y", "")) == "Kargo":
            kargo_takip = st.text_input("Kargo Takip No", key="mk_kargo",
                                        placeholder="kargo takip numarası")

        ariza = st.text_input("Arıza *", placeholder="örn: güç kaynağı bozuk")

        _alt_baslik("Müşteri / Mağaza İletişim Bilgisi")
        m1, m2, m3 = st.columns(3)
        m_adi = m1.text_input("Müşteri / Mağaza Adı", key="mk_m_adi",
                              placeholder="örn: Vatan - Buyaka / son kullanıcı adı")
        m_mail = m2.text_input("Mail", key="mk_m_mail")
        m_tel = m3.text_input("Telefon", key="mk_m_tel")
        m_adres = st.text_input("Adres", key="mk_m_adres")

        _alt_baslik("Belge — fatura veya irsaliye ile kabul")
        fbz = st.columns([1.3, 3])
        fatura_mevcut = fbz[0].checkbox("Fatura mevcut", value=True, key="mk_fat_mevcut")
        fbz[1].caption("Fatura No / İrsaliye No **opsiyoneldir** — ürün belge beklemeden işleme alınır. "
                       "Fatura sonradan kesilince Muhasebe ya da Teknik Servis, kaydı **Düzenle**'den "
                       "girip ✓'e çevirebilir.")
        f1, f2 = st.columns(2)
        fatura = f1.text_input("Fatura No")
        irsaliye = f2.text_input("İrsaliye No")
        firma_servis_no = f1.text_input("Firma Servis Form No", placeholder="ör. 11MS0072257")

        _alt_baslik("Ön Kontrol")
        fiziksel = st.text_input("Fiziksel Durum", placeholder="hasarsız / çizik / tozlu / kullanılmış")

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
        _sevk_txt = "" if str(sevk_yontemi).startswith("(") else sevk_yontemi
        if kargo_takip.strip():
            _sevk_txt = (f"{_sevk_txt} · Kargo No: {kargo_takip.strip()}").strip(" ·")
        data = {
            "arayuz": arayuz, "stok_kodu": sk.strip(),
            "urun_grubu": urun_grubu, "stok_adi": stok_adi.strip(),
            "seri_no": seri.strip(), "ariza": ariza.strip(),
            "firma_bilgisi": firma, "sevk_kargo_bilgisi": _sevk_txt,
            "musteri_adi": m_adi.strip(), "musteri_mail": m_mail.strip(),
            "musteri_tel": m_tel.strip(), "musteri_adres": m_adres.strip(),
            "fatura_no": fatura.strip(), "irsaliye_no": irsaliye.strip(),
            "fatura_mevcut": bool(fatura_mevcut),
            "firma_servis_form_no": firma_servis_no.strip(),
            "fiziksel_durum": fiziksel.strip(),
        }
        _personel = st.session_state.get("aktif_kullanici", "") or ""
        ok, msg, form_no = ekle_kayit(data, _personel)
        if ok:
            st.success(msg)
            # Bir sonraki kayda temiz başla — tüm form alanlarını sıfırla (madde 3: mükerrer kayıt önlenir)
            for k in ("mk_stok_adi", "mk_urun_grubu", "mk_ean", "mk_grup_yeni", "mk_grup_sec",
                      "mk_m_adi", "mk_m_mail", "mk_m_tel", "mk_m_adres", "mk_kargo",
                      "mk_mgz_sec", "_mk_mgz_son", "mk_firma_yeni", "_mk_firma_hedef"):
                st.session_state.pop(k, None)
            st.session_state["_mk_kayit_ok"] = form_no or msg
            st.balloons()
            st.rerun()
        else:
            st.error(msg)



# ── Liste (Teknik Servis / İade) ─────────────────────────────────────
def _liste(arayuz):
    etk = "Teknik Servis" if arayuz == "teknik" else "İade"
    ikon = "🔧" if arayuz == "teknik" else "↩️"
    _baslik(ikon, f"{etk} Arayüzü", "Aktif kayıtlar · 21 iş günü SLA renkleri · detay için kayıt seç")

    dep_dahil = st.checkbox("📦 Depodaki (işlemi bitmiş) kayıtları da göster",
                            key=f"ts_depdahil_{arayuz}",
                            help="Tüm ürünler depoya geçmiş olsa bile buradan detay/geçmişe ulaşmak için işaretle.")
    kayitlar = get_kayitlar(arayuz=arayuz, depolu=(None if dep_dahil else False))
    if not kayitlar:
        st.info(f"Henüz {etk.lower()} kaydı yok. "
                + ("Yukarıdaki kutuyu işaretleyip depodaki kayıtları görebilir veya " if not dep_dahil else "")
                + "**Mal Kabül**'den ekleyebilirsin.")
        return

    fc1, fc2, fc3 = st.columns([1.4, 1.1, 2])
    with fc1:
        durum_f = st.selectbox("Durum filtresi", ["Aktif (bitmemiş)", "Tümü"] + DURUMLAR,
                               key=f"ts_durf_{arayuz}")
    with fc2:
        fatura_f = st.selectbox("Fatura", ["Tümü", "✓ Mevcut", "✗ Yok"], key=f"ts_fatf_{arayuz}")
    with fc3:
        ara = st.text_input("🔍 Ara — Servis No · Stok · Seri · Fatura · İrsaliye · Firma · Müşteri · Servis Formu",
                            key=f"ts_ara_{arayuz}")

    def _fm_of(k):
        v = k.get("fatura_mevcut")
        return bool((k.get("fatura_no") or "").strip()) if v is None else bool(v)

    def _uyar(k):
        if durum_f == "Tümü":
            pass
        elif durum_f == "Aktif (bitmemiş)":
            if k.get("mevcut_durum") in BITMIS_DURUMLAR:
                return False
        elif k.get("mevcut_durum") != durum_f:
            return False
        if fatura_f == "✓ Mevcut" and not _fm_of(k):
            return False
        if fatura_f == "✗ Yok" and _fm_of(k):
            return False
        if ara:
            blob = " ".join(str(k.get(a, "") or "") for a in
                            ("servis_form_no", "stok_kodu", "stok_adi", "seri_no",
                             "fatura_no", "irsaliye_no", "firma_servis_form_no",
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
            f'<td style="padding:8px 8px;border-top:1px solid rgba(255,255,255,0.05);text-align:center;font-weight:700;color:{"#34D399" if _fm_of(k) else "#F87171"}">{"✓" if _fm_of(k) else "✗"}</td>'
            f'<td>{_durum_chip(k.get("mevcut_durum", ""))}</td>'
            f'<td>{_sla_chip(k)}</td>'
            f'<td style="color:#94A3B8;font-size:11px">{_tarih_kisa(k.get("mal_kabul_tarihi"))}</td>'
            "</tr>"
        )
    st.html(
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px">'
        '<thead><tr style="text-align:left;color:#64748B;font-size:11px;text-transform:uppercase;letter-spacing:0.5px">'
        '<th style="padding:8px 8px">Servis No</th><th>Stok Kodu</th><th>Stok Adı</th>'
        '<th>Seri No</th><th>Firma</th><th>Fatura</th><th>Durum</th><th>SLA</th><th>Mal Kabül</th>'
        '</tr></thead>'
        '<tbody style="color:#E2E8F0">'
        + satirlar.replace("<td>", '<td style="padding:8px 8px;border-top:1px solid rgba(255,255,255,0.05)">')
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
    g = sla_is_gunu(kayit)
    renk, sla_txt = sla_renk(g, bitmis)

    # Üst kart
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);'
        f'border-radius:12px;padding:16px 20px;margin-bottom:16px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
        f'<div><div style="color:#FDA4AF;font-size:19px;font-weight:800">{_g(kayit, "servis_form_no")}</div>'
        f'<div style="color:#94A3B8;font-size:13px;margin-top:0px">{ARAYUZ_ETIKET.get(kayit.get("arayuz",""),"")} · {_g(kayit,"stok_kodu")} · Seri {_g(kayit,"seri_no")}</div></div>'
        f'<div style="display:flex;gap:8px;align-items:center">{_durum_chip(kayit.get("mevcut_durum",""))}'
        f'<span style="background:{renk}22;border:1px solid {renk}55;color:{renk};border-radius:6px;padding:4px 8px;font-size:13px;font-weight:700">⏱ {sla_txt}</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # 📄 PDF form indir + 🧾 Fatura mevcut durumu / muhasebe işaretleme
    pc1, pc2 = st.columns([1, 2])
    with pc1:
        try:
            _pdf = servis_formu_pdf(kayit, get_gecmis(kid))
            st.download_button("📄 PDF Form indir", _pdf,
                               f'{_g(kayit, "servis_form_no", "servis_formu")}.pdf',
                               mime="application/pdf", use_container_width=True, key=f"ts_pdf_{kid}")
        except Exception as _e:
            st.caption(f"PDF oluşturulamadı: {type(_e).__name__}")
    with pc2:
        _fm = kayit.get("fatura_mevcut")
        if _fm is None:  # eski kayıt: fatura no doluysa var say
            _fm = bool((kayit.get("fatura_no") or "").strip())
        if _fm:
            st.markdown('<div style="padding:8px 0;color:#34D399;font-size:13px;font-weight:700">🧾 Fatura: ✓ Mevcut</div>',
                        unsafe_allow_html=True)
        else:
            with st.popover("🧾 Fatura: ✗ Yok — fatura geldi olarak işaretle (muhasebe)", use_container_width=True):
                st.caption("Fatura kesilip ürün kaydına ulaşıldıysa Fatura No girip ✓'e çevir. "
                           "Seri/İrsaliye ile aratıp bu kaydı bulabilirsin.")
                _yeni_fno = st.text_input("Fatura No", value=kayit.get("fatura_no", "") or "", key=f"ts_fno_{kid}")
                if st.button("✓ Fatura geldi olarak işaretle", key=f"ts_fmbtn_{kid}", type="primary"):
                    if kayit_guncelle(kid, {"fatura_mevcut": True, "fatura_no": _yeni_fno.strip()}):
                        durum_guncelle(kid, kayit.get("mevcut_durum", "mal kabül"),
                                       st.session_state.get("aktif_kullanici", ""),
                                       f"Fatura geldi ✓ (No: {_yeni_fno.strip()})")
                        st.success("✅ Fatura ✓ olarak işaretlendi.")
                        st.rerun()
                    else:
                        st.error("Güncellenemedi.")

    sol, sag = st.columns([1.6, 1])

    with sol:
        def _satir(et, deg):
            st.markdown(
                f'<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">'
                f'<div style="color:#64748B;font-size:13px;min-width:150px">{et}</div>'
                f'<div style="color:#E2E8F0;font-size:13px">{deg}</div></div>',
                unsafe_allow_html=True)

        _alt_baslik("Ürün Bilgisi")
        _satir("Stok Adı", _g(kayit, "stok_adi"))
        _satir("Ürün Grubu", _g(kayit, "urun_grubu"))
        _satir("EAN", _g(kayit, "ean"))
        _satir("İçerik Durumu", _g(kayit, "icerik_durumu"))
        if (_g(kayit, "eksik_icerik") or "").strip():
            _satir("⚠️ Eksik İçerik", _g(kayit, "eksik_icerik"))
        _satir("Fiziksel Durum", _g(kayit, "fiziksel_durum"))

        _alt_baslik("Arıza / İşlem")
        _satir("Müşteri Şikayet", _g(kayit, "ariza"))
        _satir("Detay", _g(kayit, "detay"))
        _satir("Yapılan İşlem", _g(kayit, "yapilan_islem"))
        _satir("Test Süreci", _g(kayit, "test_sureci"))

        _alt_baslik("Müşteri / Firma")
        _satir("Firma Bilgisi", _g(kayit, "firma_bilgisi"))
        _satir("Mağaza Adı", _g(kayit, "musteri_adi"))
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
                    f'<div style="display:flex;gap:8px;padding:8px 0">'
                    f'<div style="width:9px;height:9px;border-radius:50%;background:{rk};margin-top:4px;flex-shrink:0"></div>'
                    f'<div><div style="color:{rk};font-size:13px;font-weight:700">{h.get("durum","")}</div>'
                    f'<div style="color:#64748B;font-size:11px">{_tarih_kisa(h.get("tarih"))} · {h.get("personel","") or "—"}</div>'
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
    @st.dialog("⚙️ Durum Güncelle / İşlem Yap", width="large")
    def _dlg_ts_durum():
        # Yeni durum form DIŞINDA — 'ürün değişimi' seçilince değişim alanları anında görünsün
        mevcut = kayit.get("mevcut_durum", "mal kabül")
        idx = DURUMLAR.index(mevcut) if mevcut in DURUMLAR else 0
        yeni_durum = st.selectbox("Yeni Durum", DURUMLAR, index=idx, key=f"ts_yd_{kid}")
        # "gönderildi" seçilince Sevk/Teslim Şekli (form DIŞINDA → Kargo seçilince takip no görünür)
        _ts_sevk = None
        if yeni_durum == "gönderildi":
            _ts_sevk = st.selectbox(
                "Sevk / Teslim Şekli",
                ["(Seçilmedi)", "Selçuk Aydoğan", "Firma sevkiyat", "Depodan teslimat", "Kargo"],
                key=f"ts_sevk_{kid}")
        # "ürün değişimi" seçilince → İthalat'tan yeni ürün seç (form DIŞINDA; seçince stok kodu+adı dolar)
        if yeni_durum == "ürün değişimi":
            _dmods = ithalat_model_listesi()
            if _dmods:
                _dopts = ["— İthalat'tan yeni ürün seç —"] + [(f"{s} — {a}" if a else s) for s, a in _dmods]
                _dsec = st.selectbox(f"🔄 Değişim ürününü ithalattan seç ({len(_dmods)} model · yazarak ara)",
                                     _dopts, key=f"ts_dgmodel_{kid}")
                if _dsec != _dopts[0] and st.session_state.get(f"_ts_dgmodel_son_{kid}") != _dsec:
                    st.session_state[f"_ts_dgmodel_son_{kid}"] = _dsec
                    _dsku = _dsec.split(" — ")[0].strip()
                    st.session_state[f"ts_dgsk_{kid}"] = _dsku
                    for _s, _a in _dmods:
                        if _s == _dsku and _a:
                            st.session_state[f"ts_dgsa_{kid}"] = _a
                            break
                    st.rerun()
        with st.form(f"ts_durum_{kid}", enter_to_submit=False):
            # İşlemi yapan gösterilmez; oturumdaki kullanıcı otomatik kaydedilir
            personel = st.session_state.get("aktif_kullanici", "") or ""
            yapilan = st.text_input("Yapılan İşlem / Açıklama",
                                    placeholder="örn: güç kaynağı değiştirildi")
            test = st.text_area("Test Süreci (opsiyonel)", height=60)

            # "gönderildi" + Kargo → Kargo Takip No
            _ts_kargo = ""
            if yeni_durum == "gönderildi" and str(st.session_state.get(f"ts_sevk_{kid}", "")) == "Kargo":
                _ts_kargo = st.text_input("Kargo Takip No", key=f"ts_kargo_{kid}",
                                          placeholder="kargo takip numarası")

            # 🔄 Ürün değişimi seçiliyse — değişim ürünü bilgileri
            _dg = {}
            if yeni_durum == "ürün değişimi":
                st.markdown('<div style="color:#FBBF24;font-size:13px;font-weight:700;'
                            'text-transform:uppercase;letter-spacing:.5px;margin:8px 0 0px">'
                            '🔄 Değişim Yapılan Ürün</div>', unsafe_allow_html=True)
                dg1, dg2 = st.columns(2)
                st.session_state.setdefault(f"ts_dgsk_{kid}", kayit.get("degisim_stok_kodu", "") or "")
                _dg["degisim_stok_kodu"] = dg1.text_input("Stok Kodu", key=f"ts_dgsk_{kid}")
                st.session_state.setdefault(f"ts_dgsa_{kid}", kayit.get("degisim_stok_adi", "") or "")
                _dg["degisim_stok_adi"] = dg2.text_input("Stok Adı", key=f"ts_dgsa_{kid}")
                dg3, dg4 = st.columns(2)
                _dg["degisim_seri_no"] = dg3.text_input("Seri No", value=kayit.get("degisim_seri_no", "") or "",
                                                        key=f"ts_dgsn_{kid}")
                _depo_opts = ["(Seçilmedi)"] + DEPOLAR
                _cur_dp = kayit.get("degisim_depo") or ""
                _dg_depo = dg4.selectbox("Depo", _depo_opts,
                                         index=_depo_opts.index(_cur_dp) if _cur_dp in _depo_opts else 0,
                                         key=f"ts_dgdp_{kid}")
                _dg["degisim_depo"] = "" if str(_dg_depo).startswith("(") else _dg_depo

            st.markdown('<div style="color:#64748B;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;margin:8px 0 0px">Ön Kontrol Bilgileri (güncellenebilir)</div>', unsafe_allow_html=True)
            k1, k2 = st.columns(2)
            d_icerik = _icerik_multiselect(
                k1, "İçerik Durumu", ICERIK_SECENEKLER,
                kayit.get("icerik_durumu", ""), key=f"ts_ic_{kid}")
            d_fiziksel = k2.text_input("Fiziksel Durum", value=kayit.get("fiziksel_durum", "") or "",
                                       key=f"ts_fz_{kid}", placeholder="hasarsız / çizik / tozlu")
            # Eksik İçerik — YALNIZ durum güncelle ekranında görünür (madde 5)
            d_eksik = _icerik_multiselect(
                st, "⚠️ Eksik İçerik", EKSIK_ICERIK_SECENEKLER,
                kayit.get("eksik_icerik", ""), key=f"ts_eksik_{kid}")
            d_detay = st.text_area("Detay / Not", value=kayit.get("detay", "") or "",
                                   key=f"ts_dt_{kid}", height=68)

            if st.form_submit_button("💾 Durumu Güncelle", type="primary", use_container_width=True):
                ekstra = {
                    "icerik_durumu": d_icerik.strip(),
                    "eksik_icerik": d_eksik.strip(),
                    "fiziksel_durum": d_fiziksel.strip(),
                    "detay": d_detay.strip(),
                }
                for _dk, _dv in _dg.items():
                    ekstra[_dk] = (_dv or "").strip() if isinstance(_dv, str) else _dv
                if yapilan.strip():
                    ekstra["yapilan_islem"] = yapilan.strip()
                if test.strip():
                    ekstra["test_sureci"] = test.strip()
                if yeni_durum == "gönderildi":
                    _sv = "" if (not _ts_sevk or str(_ts_sevk).startswith("(")) else _ts_sevk
                    if _ts_kargo.strip():
                        _sv = (f"{_sv} · Kargo No: {_ts_kargo.strip()}").strip(" ·")
                    if _sv:
                        ekstra["sevk_kargo_bilgisi"] = _sv
                if durum_guncelle(kid, yeni_durum, personel.strip(), yapilan.strip(), ekstra):
                    st.success(f"✅ Durum güncellendi: {yeni_durum}")
                    st.rerun()
                else:
                    st.error("Güncelleme başarısız.")
    if st.button("⚙️ Durum Güncelle / İşlem Yap", key="btn_ts_durum", use_container_width=True):
        _dlg_ts_durum()

    @st.dialog("📦 Depoya Transfer (işlem bitti)", width="large")
    def _dlg_ts_transfer():
        st.caption("İşlemi biten ürünü ilgili depoya aktar. Aktif arayüzden düşmez, Depolar sekmesinde görünür.")
        depo = st.selectbox("Hedef Depo", DEPOLAR, key=f"ts_depo_{kid}")
        depo_aciklama = st.text_input("Ürün Son Durumu / Açıklama (rapor için)",
                                      key=f"ts_depoack_{kid}",
                                      value=kayit.get("depo_aciklama", "") or "",
                                      placeholder="örn: panel değişti, sıfır ayarında / 2.el A kalite / hurda - anakart yanmış")
        if st.button("Transfer Et", use_container_width=True, key=f"ts_tbtn_{kid}"):
            durum_haritasi = {"outlet": "satışa hazır", "ikinci el": "satışa hazır",
                              "hurda": "hurda", "merkez": "gönderildi"}
            yeni = durum_haritasi.get(depo, kayit.get("mevcut_durum"))
            if durum_guncelle(kid, yeni, st.session_state.get("aktif_kullanici", ""),
                              f"{depo} deposuna transfer" + (f" — {depo_aciklama.strip()}" if depo_aciklama.strip() else ""),
                              {"depo": depo, "depo_aciklama": depo_aciklama.strip(),
                               "depo_tarihi": date.today().isoformat()}):
                # Transfer sonrası Depolar sekmesine geç (madde 3)
                st.session_state["ts_sayfa"] = "📦  Depolar"
                st.session_state["_ts_depo_bilgi"] = f"✅ {depo} deposuna aktarıldı — Depolar sekmesine yönlendirildin."
                st.rerun()
            else:
                st.error("Transfer başarısız.")
    if st.button("📦 Depoya Transfer (işlem bitti)", key="btn_ts_transfer", use_container_width=True):
        _dlg_ts_transfer()

    @st.dialog("🗑️ Hatalı / Mükerrer Kaydı Sil", width="large")
    def _dlg_ts_sil():
        st.caption("Yanlışlıkla oluşmuş ya da mükerrer kayıtları kalıcı siler. Geri alınamaz; "
                   "durum geçmişi de silinir. Gerçekten iptal edilen (ama kayıtta kalması gereken) "
                   "servisler için bunun yerine yukarıdan durumu **iptal** yap.")
        _sil_onay = st.checkbox(f"⚠️ '{_g(kayit, 'servis_form_no')}' kaydını kalıcı silmek istiyorum",
                                key=f"ts_sil_onay_{kid}")
        if st.button("🗑️ Kaydı Kalıcı Sil", disabled=not _sil_onay,
                     use_container_width=True, key=f"ts_sil_btn_{kid}"):
            ok, hata = sil_kayit(kid)
            if ok:
                st.success("🗑️ Kayıt silindi.")
                st.rerun()
            else:
                st.error(f"Silinemedi: {hata}")
    if st.button("🗑️ Hatalı / Mükerrer Kaydı Sil", key="btn_ts_sil", use_container_width=True):
        _dlg_ts_sil()


# ── Depolar ──────────────────────────────────────────────────────────
def _depolar():
    _baslik("📦", "Depolar", "İşlemi biten ürünler · outlet / 2.el / hurda / merkez · satışa hazır → satıldı")
    _depo_bilgi = st.session_state.pop("_ts_depo_bilgi", None)
    if _depo_bilgi:
        st.success(_depo_bilgi)
    kayitlar = get_kayitlar(depolu=True)
    if not kayitlar:
        st.info("Henüz depoya aktarılmış ürün yok. Bir kaydın Kontrol Paneli'nden **Depoya Transfer** yapabilirsin.")
        return

    _gruplar = sorted({(k.get("urun_grubu") or "").strip() for k in kayitlar
                       if (k.get("urun_grubu") or "").strip()})
    _firmalar = sorted({(k.get("firma_bilgisi") or "").strip() for k in kayitlar
                        if (k.get("firma_bilgisi") or "").strip()})
    f1, f2, f3, f4 = st.columns(4)
    depo_f = f1.selectbox("Depo filtresi", ["Tümü"] + DEPOLAR, key="depo_filtre")
    grup_f = f2.selectbox("Ürün grubu", ["Tümü"] + _gruplar, key="depo_grup_f")
    firma_f = f3.selectbox("Firma", ["Tümü"] + _firmalar, key="depo_firma_f")
    kaynak_f = f4.selectbox("Kaynak", ["Tümü", "🔧 Teknik Servis", "↩️ İade"], key="depo_kaynak_f")
    g1, g2 = st.columns([1, 3])
    fatura_f = g1.selectbox("Fatura", ["Tümü", "✓ Mevcut", "✗ Yok"], key="depo_fat_f")
    ara = g2.text_input("🔍 Ara — Servis No · Stok · Seri · Firma · Fatura · İrsaliye · Firma Servis No",
                        key="depo_ara")

    def _fm_of(k):
        v = k.get("fatura_mevcut")
        return bool((k.get("fatura_no") or "").strip()) if v is None else bool(v)

    def _uy(k):
        if depo_f != "Tümü" and (k.get("depo") or "") != depo_f:
            return False
        if grup_f != "Tümü" and (k.get("urun_grubu") or "").strip() != grup_f:
            return False
        if firma_f != "Tümü" and (k.get("firma_bilgisi") or "").strip() != firma_f:
            return False
        if kaynak_f != "Tümü" and ARAYUZ_ETIKET.get(k.get("arayuz", ""), "") != kaynak_f:
            return False
        if fatura_f == "✓ Mevcut" and not _fm_of(k):
            return False
        if fatura_f == "✗ Yok" and _fm_of(k):
            return False
        if ara:
            blob = " ".join(str(k.get(a, "") or "") for a in
                            ("servis_form_no", "stok_kodu", "stok_adi", "seri_no", "firma_bilgisi",
                             "fatura_no", "irsaliye_no", "firma_servis_form_no")).lower()
            if ara.lower() not in blob:
                return False
        return True

    goster = [k for k in kayitlar if _uy(k)]

    # Excel dışa aktarma (filtrelenmiş liste)
    if goster:
        _df = pd.DataFrame([{
            "Servis No": k.get("servis_form_no", ""), "Stok Kodu": k.get("stok_kodu", ""),
            "Stok Adı": k.get("stok_adi", ""), "Ürün Grubu": k.get("urun_grubu", ""),
            "Seri No": k.get("seri_no", ""), "Firma": k.get("firma_bilgisi", ""),
            "Kaynak": ARAYUZ_ETIKET.get(k.get("arayuz", ""), ""),
            "Depo": k.get("depo", ""), "Durum": k.get("mevcut_durum", ""),
            "Mal Kabül": _tarih_kisa(k.get("mal_kabul_tarihi")),
            "Fatura No": k.get("fatura_no", ""), "İrsaliye No": k.get("irsaliye_no", ""),
            "Depo Açıklaması": k.get("depo_aciklama", ""),
            "Satış Firma": k.get("satis_firma", ""), "Satış Fiyatı": k.get("satis_fiyati", ""),
            "Satış Tarihi": k.get("satis_tarihi", ""),
        } for k in goster])
        _buf = BytesIO()
        with pd.ExcelWriter(_buf, engine="openpyxl") as _w:
            _df.to_excel(_w, index=False, sheet_name="Depolar")
        st.download_button("⬇️ Excel indir", _buf.getvalue(), "depolar.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="depo_excel")

    st.caption(f"{len(goster)} / {len(kayitlar)} ürün")

    for k in goster:
        kid = k["id"]
        satildi = k.get("mevcut_durum") == "satıldı"
        with st.container():
            c1, c2, c3, c4 = st.columns([3, 1.15, 1.15, 0.95])
            with c1:
                st.markdown(
                    f'<div style="padding:8px 0"><span style="color:#FDA4AF;font-weight:700">{_g(k,"servis_form_no")}</span> · '
                    f'{_g(k,"stok_kodu")} · <span style="color:#94A3B8">{(_g(k,"stok_adi","")[:50])}</span><br>'
                    f'<span style="color:#64748B;font-size:11px">{ARAYUZ_ETIKET.get(k.get("arayuz",""),"")} · Seri {_g(k,"seri_no")} · Depo: {_g(k,"depo")}</span> '
                    f'{_durum_chip(k.get("mevcut_durum",""))}</div>',
                    unsafe_allow_html=True)
            with c2:
                if not satildi:
                    if k.get("mevcut_durum") != "satışa hazır":
                        if st.button("✅ Satışa Hazır", key=f"sh_{kid}", use_container_width=True):
                            durum_guncelle(kid, "satışa hazır", st.session_state.get("aktif_kullanici", ""),
                                           "Satışa hazır işaretlendi")
                            st.rerun()
            with c4:
                if st.button("🏷 Etiket", key=f"etk_{kid}", use_container_width=True,
                             help="100×135mm barkodlu depo etiketi"):
                    st.session_state["_etiket_kid"] = kid
                if st.session_state.get("_etiket_kid") == kid:
                    try:
                        _epdf = depo_etiket_pdf(k)
                        st.download_button("⬇ PDF", _epdf,
                                           file_name=f"etiket_{(k.get('seri_no') or kid)}.pdf",
                                           mime="application/pdf",
                                           key=f"etkd_{kid}", type="primary",
                                           use_container_width=True)
                    except Exception as _ee:
                        st.error(f"Etiket üretilemedi: {_ee}")
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
            with st.expander("📋 Detay & İşlem Geçmişi"):
                dd1, dd2 = st.columns(2)
                with dd1:
                    st.markdown(
                        f'<div style="font-size:13px;line-height:1.9;color:#CBD5E1">'
                        f'<b>Ürün Grubu:</b> {_g(k,"urun_grubu")}<br>'
                        f'<b>Arıza:</b> {_g(k,"ariza")}<br>'
                        f'<b>İçerik:</b> {_g(k,"icerik_durumu")}<br>'
                        f'<b>Fiziksel:</b> {_g(k,"fiziksel_durum")}<br>'
                        f'<b>Detay/Not:</b> {_g(k,"detay")}</div>', unsafe_allow_html=True)
                with dd2:
                    st.markdown(
                        f'<div style="font-size:13px;line-height:1.9;color:#CBD5E1">'
                        f'<b>Firma:</b> {_g(k,"firma_bilgisi")}<br>'
                        f'<b>Müşteri:</b> {_g(k,"musteri_adi")}<br>'
                        f'<b>Fatura No:</b> {_g(k,"fatura_no")}<br>'
                        f'<b>İrsaliye No:</b> {_g(k,"irsaliye_no")}<br>'
                        f'<b>Firma Servis Form No:</b> {_g(k,"firma_servis_form_no")}<br>'
                        f'<b>Depo Açıklaması:</b> {_g(k,"depo_aciklama")}</div>', unsafe_allow_html=True)
                _gec = get_gecmis(kid)
                if _gec:
                    st.markdown('<div style="color:#64748B;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;margin:8px 0 0px">İşlem Geçmişi</div>', unsafe_allow_html=True)
                    for _h in _gec:
                        st.markdown(
                            f'<div style="font-size:13px;color:#94A3B8;padding:0px 0">'
                            f'<span style="color:#E2E8F0">{_tarih_kisa(_h.get("tarih"))}</span> · '
                            f'{_durum_chip(_h.get("durum",""))} '
                            f'{_h.get("aciklama","") or ""} '
                            f'<span style="color:#64748B">({_h.get("personel","") or "—"})</span></div>',
                            unsafe_allow_html=True)
                try:
                    _pdf = servis_formu_pdf(k, _gec)
                    st.download_button("📄 PDF Form indir", _pdf,
                                       f'{_g(k, "servis_form_no", "servis_formu")}.pdf',
                                       mime="application/pdf", key=f"depo_pdf_{kid}")
                except Exception:
                    pass
        st.markdown('<div style="height:1px;background:rgba(255,255,255,0.05);margin:4px 0"></div>',
                    unsafe_allow_html=True)


# ── Ana çalıştırıcı ──────────────────────────────────────────────────
def run():
    """Teknik Servis modülü — portal tarafından çağrılır."""
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")

    st.markdown(
        "<style>"
        ".main .block-container{max-width:1200px !important;}"
        "[data-testid=\"stMetric\"]{background:linear-gradient(180deg,#152036,#0F172A);border:1px solid rgba(255,255,255,0.08);"
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

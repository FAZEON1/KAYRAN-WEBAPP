# -*- coding: utf-8 -*-
"""Teknik Servis / İade modülü — arayüz (V1)."""
from datetime import datetime, date
from io import BytesIO

import pandas as pd
import streamlit as st
from shared.utils import sidebar_stil, sidebar_baslik, sidebar_kullanici

from .database import (
    ARAYUZLER, ARAYUZ_ETIKET, DURUMLAR, BITMIS_DURUMLAR, DURUM_RENK,
    ts_firmalar_tam, ekle_ts_firma, seri_kayitlari, tum_seriler,
    depo_aciklamalar, ekle_depo_aciklama,
    DEPOLAR, FIRMA_ONERILER, TS_FIRMALAR,
    get_kayitlar, get_kayit, get_gecmis, ekle_kayit, durum_guncelle,
    kayit_guncelle, sil_kayit, urun_getir, is_gunu_farki, sla_renk, sla_is_gunu, ithalat_model_listesi,
    ts_urun_gruplari, servis_formu_pdf,
    depo_etiket_pdf, evraksiz_depo_kayit,
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
    """Seçilebilir + serbest metin girilebilir içerik alanı. ' · ' ile birleşik string döner.
    NOT: st.pills kullanılır (seçenekler pencere İÇİNDE düğme olarak durur) —
    multiselect'in açılır listesi dialog arkasında kalabildiği için terk edildi.
    pills mevcut değilse eski multiselect yoluna düşer."""
    _mevcut = _coklu_deger(kayit_deger)
    _opts = list(dict.fromkeys(secenekler + _mevcut))  # mevcut özel değerler de listede görünsün
    # Önceki oturumdan session'da kalan, listede olmayan değerler pills'i
    # patlatmasın → süz (yalnız geçerli seçenekler kalsın)
    _ss = st.session_state.get(key)
    if isinstance(_ss, list) and any(v not in _opts for v in _ss):
        st.session_state[key] = [v for v in _ss if v in _opts]
    try:
        _sec = st_col.pills(etiket, _opts, selection_mode="multi",
                            default=[m for m in _mevcut if m in _opts], key=key,
                            help="Tıklayarak seç / kaldır — açılır liste yok, hepsi pencere içinde.")
    except Exception:
        # pills yoksa (eski Streamlit) → multiselect'e düş
        try:
            _sec = st_col.multiselect(etiket, _opts, default=_mevcut, key=key,
                                      accept_new_options=True,
                                      help="Listeden seç ya da yaz + Enter ile yeni ekle.")
        except TypeError:
            _sec = st_col.multiselect(etiket, _opts, default=_mevcut, key=key)
    # Listede olmayanı serbest metinle ekleme (virgülle çoklu)
    _ek = st_col.text_input(f"➕ {etiket} — listede yoksa yaz", key=f"{key}_yeni",
                            placeholder="virgülle birden çok: hdmi, adaptör")
    if (_ek or "").strip():
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

    # ── 📥 TOPLU MAL KABUL (Excel) — VATAN gibi 50-100'lük toplu iadeler için ──
    with st.expander("📥 Toplu Mal Kabul — Excel ile (50-100 kaydı tek seferde al)"):
        _TK = ["İşlem Türü (Teknik/İade)", "Stok Kodu", "Stok Adı", "Ürün Grubu",
               "Seri No", "Arıza", "Firma (Cari Unvan)", "Mağaza / Müşteri Adı",
               "Telefon", "Mail", "Adres", "Sevk / Teslim Şekli", "Kargo Takip No",
               "Fatura No", "İrsaliye No", "Firma Servis Form No", "Fiziksel Durum"]
        _tb = BytesIO()
        with pd.ExcelWriter(_tb, engine="openpyxl") as _tw:
            pd.DataFrame(columns=_TK).to_excel(_tw, index=False, sheet_name="MalKabul")
        st.download_button("📋 Boş şablonu indir", _tb.getvalue(), "toplu_mal_kabul_sablon.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="tmk_sablon")
        st.caption("Zorunlu sütunlar: **İşlem Türü, Stok Kodu, Seri No** (yoksa NO SERIAL NUMBER yaz), "
                   "**Arıza, Firma**. Stok Adı/Ürün Grubu boşsa Ürün Yönetimi'nden otomatik doldurulur.")
        _tyk = st.file_uploader("Doldurulmuş Excel'i yükle", type=["xlsx", "xls"], key="tmk_yukle")
        if _tyk is not None:
            try:
                _tdf = pd.read_excel(_tyk, dtype=str).fillna("")
                _tdf.columns = [str(c).strip() for c in _tdf.columns]
                _kolmap = {c.lower(): c for c in _tdf.columns}

                def _tv(r, ad, *alt):
                    for a in (ad,) + alt:
                        c = _kolmap.get(a.lower())
                        if c is not None:
                            v = str(r.get(c, "") or "").strip()
                            if v:
                                return v
                    return ""
                _mevcut_seri = tum_seriler()
                _gecerli, _hatali = [], []
                _dosya_seri = set()
                for _i, _r in _tdf.iterrows():
                    # Türkçe 'İ' tuzağı: "İade".lower() bozuk karakter üretir → önce I'ya çevir
                    _tur_h = (_tv(_r, "İşlem Türü (Teknik/İade)", "İşlem Türü", "Tür")
                              .replace("İ", "I").replace("ı", "i").lower())
                    _tur = "teknik" if "tek" in _tur_h else ("iade" if "iade" in _tur_h else "")
                    _sk_t = _tv(_r, "Stok Kodu", "SKU")
                    _seri_t = _tv(_r, "Seri No", "Seri") or "NO SERIAL NUMBER"
                    _ariza_t = _tv(_r, "Arıza")
                    _firma_t = _tv(_r, "Firma (Cari Unvan)", "Firma")
                    _sorunlar = []
                    if not _tur:
                        _sorunlar.append("İşlem Türü (Teknik/İade)")
                    if not _sk_t:
                        _sorunlar.append("Stok Kodu")
                    if not _ariza_t:
                        _sorunlar.append("Arıza")
                    if not _firma_t:
                        _sorunlar.append("Firma")
                    if _sorunlar:
                        _hatali.append(f"Satır {_i + 2}: eksik → {', '.join(_sorunlar)}")
                        continue
                    _ad_t, _grp_t = _tv(_r, "Stok Adı"), _tv(_r, "Ürün Grubu")
                    if not _ad_t or not _grp_t:
                        try:
                            _u_t = urun_getir(_sk_t) or {}
                            _ad_t = _ad_t or _u_t.get("stok_adi", "")
                            _grp_t = _grp_t or _u_t.get("urun_grubu", "")
                        except Exception:
                            pass
                    _seri_u = _seri_t.upper()
                    _muk = (_seri_u not in {"NO SERIAL NUMBER", "N/A", "YOK", "-"} and
                            (_seri_u in _mevcut_seri or _seri_u in _dosya_seri))
                    _dosya_seri.add(_seri_u)
                    _sevk_t = _tv(_r, "Sevk / Teslim Şekli", "Sevk")
                    _kargo_t = _tv(_r, "Kargo Takip No", "Kargo No")
                    if _kargo_t:
                        _sevk_t = (f"{_sevk_t} · Takip No: {_kargo_t}").strip(" ·")
                    _fno_t = _tv(_r, "Fatura No")
                    _gecerli.append({"_muk": _muk, "veri": {
                        "arayuz": _tur, "stok_kodu": _sk_t, "stok_adi": _ad_t,
                        "urun_grubu": _grp_t, "seri_no": _seri_t, "ariza": _ariza_t,
                        "firma_bilgisi": _firma_t, "sevk_kargo_bilgisi": _sevk_t,
                        "musteri_adi": _tv(_r, "Mağaza / Müşteri Adı", "Müşteri", "Mağaza"),
                        "musteri_tel": _tv(_r, "Telefon"), "musteri_mail": _tv(_r, "Mail"),
                        "musteri_adres": _tv(_r, "Adres"),
                        "fatura_no": _fno_t, "irsaliye_no": _tv(_r, "İrsaliye No"),
                        "fatura_mevcut": bool(_fno_t),
                        "firma_servis_form_no": _tv(_r, "Firma Servis Form No"),
                        "fiziksel_durum": _tv(_r, "Fiziksel Durum"),
                    }})
                _muk_say = sum(1 for g in _gecerli if g["_muk"])
                st.markdown(f"**{len(_gecerli)}** geçerli satır · **{len(_hatali)}** hatalı"
                            + (f" · ⚠️ **{_muk_say}** mükerrer seri" if _muk_say else ""))
                if _hatali:
                    st.error("Düzeltilmesi gerekenler:\n\n" + "\n".join("• " + h for h in _hatali[:15])
                             + ("" if len(_hatali) <= 15 else f"\n• … +{len(_hatali) - 15} satır daha"))
                if _gecerli:
                    st.dataframe(pd.DataFrame([{
                        "Tür": ("🔧" if g["veri"]["arayuz"] == "teknik" else "↩️"),
                        "Stok": g["veri"]["stok_kodu"], "Ad": g["veri"]["stok_adi"][:36],
                        "Seri": g["veri"]["seri_no"], "Firma": g["veri"]["firma_bilgisi"][:28],
                        "Arıza": g["veri"]["ariza"][:32],
                        "Mükerrer": "⚠️" if g["_muk"] else "",
                    } for g in _gecerli[:100]]), hide_index=True, use_container_width=True,
                        height=min(320, 60 + 36 * min(len(_gecerli), 8)))
                    _muk_ok = True
                    if _muk_say:
                        _muk_ok = st.checkbox(f"⚠️ {_muk_say} mükerrer seriye RAĞMEN hepsini kaydet",
                                              key="tmk_muk_ok")
                    if st.button(f"✅ {len(_gecerli)} kaydı içeri al", type="primary",
                                 use_container_width=True, key="tmk_kaydet",
                                 disabled=not (_gecerli and _muk_ok)):
                        _bar = st.progress(0.0, text="Kaydediliyor…")
                        _ok_s, _hata_s = 0, []
                        _prs = st.session_state.get("aktif_kullanici", "") or ""
                        for _n, _g in enumerate(_gecerli, 1):
                            _okk, _msgk, _fnok = ekle_kayit(_g["veri"], _prs)
                            if _okk:
                                _ok_s += 1
                            else:
                                _hata_s.append(f"{_g['veri']['seri_no']}: {_msgk[:60]}")
                            _bar.progress(_n / len(_gecerli),
                                          text=f"Kaydediliyor… {_n}/{len(_gecerli)}")
                        _bar.empty()
                        st.success(f"✅ {_ok_s} mal kabul kaydı oluşturuldu."
                                   + (f" ⚠️ {len(_hata_s)} satır yazılamadı." if _hata_s else ""))
                        if _hata_s:
                            st.caption(" · ".join(_hata_s[:5]))
                        st.balloons()
            except Exception as _te:
                st.error(f"Excel okunamadı: {type(_te).__name__}: {str(_te)[:150]}")

    if st.session_state.pop("_mk_dialog_ac", False):
        _mal_kabul_dialog()


@st.dialog("📥 Yeni Mal Kabül", width="large")
def _mal_kabul_dialog():
    # 1️⃣ İşlem türü — en başta ve BELİRGİN (yanlış türde kayıt açılmasın)
    st.markdown('<div style="font-size:15px;font-weight:800;color:#FBBF24;margin:8px 0 0px">'
                '1️⃣ Önce işlem türünü seç</div>', unsafe_allow_html=True)
    arayuz_lbl = st.radio("İşlem türü", ["🔧 Teknik Servis", "↩️ İade"],
                          horizontal=True, key="mk_arayuz", index=None,
                          label_visibility="collapsed")
    if not arayuz_lbl:
        # Madde 1: tür seçilmeden form AÇILMAZ → iade ürünün yanlışlıkla
        # teknik servise kaydedilmesi baştan imkânsız hale gelir.
        st.info("👆 Devam etmek için önce işlem türünü seç: **Teknik Servis** mi, **İade** mi?")
        return
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
            # Madde 2: ürün grubu otomatik — önce Ürün Yönetimi kartından,
            # yoksa ürün ADINDAN tahmin (kategori kuralları)
            try:
                _u_pm = urun_getir(_sku_sel)
                _grp_oto = (_u_pm or {}).get("urun_grubu", "") or ""
                if not _grp_oto:
                    from kayranpm.database import kategori_oner as _ko_ts
                    _grp_oto = _ko_ts(st.session_state.get("mk_stok_adi", "")) or ""
                if _grp_oto:
                    st.session_state["mk_urun_grubu"] = _grp_oto
            except Exception:
                pass
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
    _TS_FIRMA_OPTS = ["— Firma seç —"] + ts_firmalar_tam()   # kalıcı manuel firmalar dahil (madde 5)
    _fi = 0
    if _hedef_cari and _hedef_cari in _TS_FIRMA_OPTS:
        _fi = _TS_FIRMA_OPTS.index(_hedef_cari)
    elif st.session_state.get("mk_firma_sec") in _TS_FIRMA_OPTS:
        _fi = _TS_FIRMA_OPTS.index(st.session_state["mk_firma_sec"])
    def _mk_acik_tut():
        # Form dışı bir widget değiştiğinde Streamlit sayfayı yeniden çalıştırır;
        # bu bayrak olmazsa pencere KAPANIR ve girilen her şey kaybolur (madde 5'in
        # kök nedeni buydu — yeni firma yazıp Enter'a basınca kayıt "kaybolyordu").
        st.session_state["_mk_dialog_ac"] = True

    _fc1, _fc2 = st.columns(2)
    firma_sec = _fc1.selectbox("Firma (cari unvan) *", _TS_FIRMA_OPTS, index=_fi,
                               key="mk_firma_sec", on_change=_mk_acik_tut)
    firma_yeni = _fc2.text_input("Firma listede yoksa tam cari unvanı yaz (yeni firma)",
                                 key="mk_firma_yeni", on_change=_mk_acik_tut,
                                 placeholder="örn. ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ")
    _son_kullanici = (firma_sec == "SON KULLANICI")
    if _son_kullanici:
        st.caption("👤 **SON KULLANICI:** mağaza ve belge (fatura/irsaliye) istenmez. "
                   "İade onayı sonrası fatura, kayıt üzerinden **Fatura geldi ✓** ile "
                   "muhasebe tarafından sonradan işlenir.")

    # 🏬 Mağaza seç — firma cari'ye göre; mağaza seçilince firma cari OTOMATİK atanır (madde 6)
    _cur_firma = firma_sec or ""
    _grup = _cari_grup(_cur_firma)  # seçili cariye ait mağaza grubu (yoksa None → tüm mağazalar)
    _mgz = magaza_listesi(_grup) if _grup else magaza_listesi()
    if _son_kullanici:
        _mgz = []          # Madde 13: son kullanıcıda mağaza seçimi yok
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
        "Sevk / Teslim Şekli *",
        ["(Seçilmedi)", "Selçuk Aydoğan", "Firma sevkiyat", "Depodan teslimat", "Kargo"],
        key="mk_sevk_y", on_change=_mk_acik_tut)

    # Madde 6: mükerrer seri uyarısı — bekleyen onay varsa formun ÜSTÜNDE göster
    _dup = st.session_state.get("_mk_seri_dup")
    if _dup:
        st.warning(f"⚠️ **{_dup['seri']}** seri numarasıyla daha önce kayıt yapılmıştır: "
                   f"{_dup['ozet']}. İşleme devam etmek istiyor musun?")
        st.checkbox("Evet — aynı seri numarasıyla YENİ bir kayıt açmak istiyorum",
                    key="mk_dup_onay")

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

        _sr1, _sr2 = st.columns([2.6, 1.4])
        seri = _sr1.text_input("Seri No *", key="mk_seri")
        _seri_yok = _sr2.checkbox("🚫 Seri no yok / okunamıyor", key="mk_seri_yok",
                                  help="İşaretlersen kayda 'NO SERIAL NUMBER' yazılır ve "
                                       "mükerrer seri uyarısından muaf tutulur.")
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

        if not _son_kullanici:
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
        else:
            # Madde 13: SON KULLANICI → belge bölümü yok; fatura iade onayı
            # sonrası muhasebe tarafından "Fatura geldi ✓" ile işlenecek
            fatura_mevcut, fatura, irsaliye, firma_servis_no = False, "", "", ""

        _alt_baslik("Ön Kontrol")
        fiziksel = st.text_input("Fiziksel Durum", placeholder="hasarsız / çizik / tozlu / kullanılmış")

        kaydet = st.form_submit_button("✅ Kayıt Tamamla", type="primary", use_container_width=True)

    if kaydet:
        if not (sk or "").strip():
            st.error("Stok Kodu zorunludur.")
            return
        # Madde 6: seri yoksa 'NO SERIAL NUMBER'
        if _seri_yok and not seri.strip():
            seri = "NO SERIAL NUMBER"
        if not seri.strip():
            st.error("Seri No zorunludur — okunamıyorsa 🚫 kutusunu işaretle.")
            return
        if not ariza.strip():
            st.error("Arıza alanı zorunludur.")
            return
        # ── Madde 3: zorunlu alanlar ──
        _firma_kayit = (firma_yeni or "").strip() or ("" if firma_sec == "— Firma seç —" else firma_sec)
        if not _firma_kayit:
            st.error("Firma (cari unvan) zorunludur — listeden seç ya da yeni firma yaz.")
            return
        if not urun_grubu:
            st.error("Ürün Grubu zorunludur — listeden seç ya da yeni grup yaz.")
            return
        if str(sevk_yontemi).startswith("("):
            st.error("Sevk / Teslim Şekli zorunludur.")
            return
        if str(sevk_yontemi) == "Kargo" and not kargo_takip.strip():
            st.error("Kargo seçildi — Kargo Takip No zorunludur.")
            return
        if not m_adi.strip():
            st.error("Mağaza / Müşteri Adı zorunludur.")
            return
        # ── Madde 6: mükerrer seri kontrolü (muaf: NO SERIAL NUMBER vb.) ──
        _MUAF_SERI = {"NO SERIAL NUMBER", "NOSERIALNUMBER", "N/A", "YOK", "-", "SERİ YOK"}
        _seri_norm = seri.strip().upper()
        if _seri_norm not in _MUAF_SERI and not st.session_state.get("mk_dup_onay"):
            _eski_k = seri_kayitlari(seri.strip())
            if _eski_k:
                st.session_state["_mk_seri_dup"] = {
                    "seri": seri.strip(),
                    "ozet": " · ".join(f"{e.get('servis_form_no','')}"
                                       f" ({e.get('mevcut_durum','') or '—'})"
                                       for e in _eski_k[:3]),
                }
                st.session_state["_mk_dialog_ac"] = True
                st.rerun()
        _sevk_txt = "" if str(sevk_yontemi).startswith("(") else sevk_yontemi
        if kargo_takip.strip():
            # Madde 9: PDF'te "Sevk/Kargo Kargo · Kargo No" tekrarı → tek ve temiz metin
            _sevk_txt = (f"{_sevk_txt} · Takip No: {kargo_takip.strip()}").strip(" ·")
        data = {
            "arayuz": arayuz, "stok_kodu": sk.strip(),
            "urun_grubu": urun_grubu, "stok_adi": stok_adi.strip(),
            "seri_no": seri.strip(), "ariza": ariza.strip(),
            "firma_bilgisi": _firma_kayit, "sevk_kargo_bilgisi": _sevk_txt,
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
            # Madde 5: elle yazılan yeni cari kalıcı listeye eklenir —
            # bir dahaki kayıtta seçim listesinde hazır bekler
            if (firma_yeni or "").strip():
                ekle_ts_firma(firma_yeni.strip())
            st.success(msg)
            # Bir sonraki kayda temiz başla — tüm form alanlarını sıfırla (madde 3: mükerrer kayıt önlenir)
            for k in ("mk_stok_adi", "mk_urun_grubu", "mk_ean", "mk_grup_yeni", "mk_grup_sec",
                      "mk_m_adi", "mk_m_mail", "mk_m_tel", "mk_m_adres", "mk_kargo",
                      "mk_mgz_sec", "_mk_mgz_son", "mk_firma_yeni", "_mk_firma_hedef",
                      "mk_seri", "mk_seri_yok", "_mk_seri_dup", "mk_dup_onay"):
                st.session_state.pop(k, None)
            st.session_state["_mk_kayit_ok"] = form_no or msg
            st.balloons()
            st.rerun()
        else:
            st.error(msg)



# ── Liste (Teknik Servis / İade) ─────────────────────────────────────
def _evraksiz_kayit():
    """📋 EVRAKSIZ ÜRÜN KAYIT — geçmiş/evraksız stok ürünlerini tek ekranda
    kaydedip doğrudan depoya aktarır (mini mal kabul). Etiket hazır olur."""
    _baslik("📋", "Evraksız Ürün Kayıt", "geçmiş / evraksız stok ürünü · tek ekranda depoya al")
    st.caption("Evraksız (geçmiş) stok ürünlerini buradan kaydet → seçtiğin depoya **doğrudan** aktarılır, "
               "Depolar sekmesinde diğer ürünler gibi listelenir ve **etiketi hazır olur**. "
               "Aktif teknik servis listesine düşmez.")

    # ── İthalat'tan ürün çek (opsiyonel) ──
    _modeller = ithalat_model_listesi()
    if _modeller:
        _opts = ["— İthalat'tan model seç (opsiyonel) —"] + [(f"{s} — {a}" if a else s) for s, a in _modeller]
        _sec = st.selectbox(f"📦 İthalat modeli seç ({len(_modeller)} model · yazarak ara)",
                            _opts, key="ev_model_sec")
        if _sec != _opts[0] and st.session_state.get("_ev_model_son") != _sec:
            st.session_state["_ev_model_son"] = _sec
            _sku_sel = _sec.split(" — ")[0].strip()
            st.session_state["ev_sk"] = _sku_sel
            for _s, _a in _modeller:
                if _s == _sku_sel:
                    if _a:
                        st.session_state["ev_stok_adi"] = _a
                    # ürün grubunu da ürün kartından çekmeye çalış
                    try:
                        _u = urun_getir(_sku_sel)
                        if _u and _u.get("urun_grubu"):
                            st.session_state["ev_urun_grubu"] = _u.get("urun_grubu", "")
                    except Exception:
                        pass
                    break
            st.rerun()

    with st.form("ev_form", clear_on_submit=False, enter_to_submit=False):
        c1, c2 = st.columns(2)
        stok_kodu = c1.text_input("Stok Kodu *", key="ev_sk", placeholder="Stok kodu")
        stok_adi = c2.text_input("Stok Adı", key="ev_stok_adi", placeholder="Ürün adı (opsiyonel)")

        c3, c4 = st.columns(2)
        _gruplar = ts_urun_gruplari()
        _grup_opts = ["— Ürün grubu seç —"] + _gruplar + ["➕ Yeni grup…"]
        _pre = (st.session_state.get("ev_urun_grubu", "") or "").strip()
        _gidx = _grup_opts.index(_pre) if _pre in _grup_opts else 0
        _grup_secim = c3.selectbox("Ürün Grubu", _grup_opts, index=_gidx, key="ev_grup_sec")
        _grup_yeni = ""
        if _grup_secim == "➕ Yeni grup…":
            _grup_yeni = c4.text_input("Yeni grup adı", key="ev_grup_yeni", placeholder="örn. SSD, RAM, EKRAN KARTI")
        else:
            c4.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
            c4.caption("Ürün grubunu listeden seç ya da 'Yeni grup…' ile ekle.")

        seri_no = st.text_input("Seri No *", key="ev_seri", placeholder="Ürün seri numarası (barkod bundan üretilir)")

        icerik_durumu = st.text_area("İçerik Durumu", key="ev_icerik", height=70,
                                     placeholder="örn. Kutu orijinal, tüm aksesuarlar mevcut ve sağlam")
        eksik_icerik = st.text_area("Eksik İçerik", key="ev_eksik", height=70,
                                    placeholder="örn. HDMI kablosu ve adaptör eksik (yoksa boş bırak)")

        st.markdown("---")
        d1, d2 = st.columns(2)
        hedef_depo = d1.selectbox("Hedef Depo *", DEPOLAR, key="ev_depo")
        depo_aciklama = d2.text_input("Ürün Son Durumu / Açıklama (etikete yazılır)",
                                      key="ev_depoack",
                                      placeholder="örn. 2.el A kalite / sıfır ayarında / hurda")

        _gonder = st.form_submit_button("📦 Kaydet ve Depoya Aktar", type="primary",
                                        use_container_width=True)

    if _gonder:
        _sk = (stok_kodu or "").strip()
        _seri = (seri_no or "").strip()
        _grup = (_grup_yeni.strip() if _grup_secim == "➕ Yeni grup…"
                 else ("" if _grup_secim.startswith("—") else _grup_secim))
        if not _sk:
            st.error("Stok Kodu zorunlu.")
            st.stop()
        if not _seri:
            st.error("Seri No zorunlu (barkod bundan üretilir).")
            st.stop()
        data = {
            "stok_kodu": _sk, "stok_adi": (stok_adi or "").strip(),
            "urun_grubu": _grup, "seri_no": _seri,
            "icerik_durumu": (icerik_durumu or "").strip(),
            "eksik_icerik": (eksik_icerik or "").strip(),
        }
        ok, msg, form_no = evraksiz_depo_kayit(
            data, hedef_depo, (depo_aciklama or "").strip(),
            personel=st.session_state.get("aktif_kullanici", ""))
        if ok:
            # Form alanlarını temizle
            for _k in ("ev_sk", "ev_stok_adi", "ev_urun_grubu", "ev_seri", "ev_icerik",
                       "ev_eksik", "ev_depoack", "ev_grup_yeni", "_ev_model_son"):
                st.session_state.pop(_k, None)
            st.success(msg)
            st.session_state["_ts_depo_bilgi"] = f"{msg} · Depolar sekmesinde etiketini alabilirsin."
            st.session_state["_ts_git"] = "📦  Depolar"  # radio oluşmadan önce işlenir
            st.rerun()
        else:
            st.error(msg)


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

    fc1, fc2, fc3, fc4 = st.columns([1.3, 1, 1.2, 1.9])
    with fc1:
        durum_f = st.selectbox("Durum filtresi", ["Aktif (bitmemiş)", "Tümü"] + DURUMLAR,
                               key=f"ts_durf_{arayuz}")
    with fc2:
        fatura_f = st.selectbox("Fatura", ["Tümü", "✓ Mevcut", "✗ Yok"], key=f"ts_fatf_{arayuz}")
    with fc3:
        # Madde 10: başlık sıralaması
        sira_f = st.selectbox("Sıralama", ["Yeni → Eski", "Eski → Yeni", "Servis No ↓",
                                           "Servis No ↑", "SLA (aciliyet)", "Durum", "Firma"],
                              key=f"ts_sira_{arayuz}")
    with fc4:
        ara = st.text_input("🔍 Ara — Servis No · Stok · Seri · Fatura · İrsaliye · Firma · Müşteri · Servis Formu",
                            key=f"ts_ara_{arayuz}")
    # Madde 17: 'gönderildi' seçilince SONUÇ alt filtresi (sorunsuz mu, değişim mi…)
    sonuc_f = "Tümü"
    if durum_f == "gönderildi":
        sonuc_f = st.selectbox("Gönderim sonucu", ["Tümü", "sorunsuz", "tamir edildi",
                                                   "ürün değişimi", "iade alındı"],
                               key=f"ts_soncf_{arayuz}")

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
            # Madde 17: "sorunsuz" seçilince sorunsuz olarak GÖNDERİLMİŞLER de görünsün
            if not (k.get("mevcut_durum") == "gönderildi"
                    and (k.get("sonuc_durumu") or "") == durum_f):
                return False
        if durum_f == "gönderildi" and sonuc_f != "Tümü" \
                and (k.get("sonuc_durumu") or "") != sonuc_f:
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
    # Madde 10: sıralama uygula
    if sira_f == "Eski → Yeni":
        goster = goster[::-1]                      # get_kayitlar zaten yeni→eski
    elif sira_f == "Servis No ↓":
        goster = sorted(goster, key=lambda k: str(k.get("servis_form_no") or ""), reverse=True)
    elif sira_f == "Servis No ↑":
        goster = sorted(goster, key=lambda k: str(k.get("servis_form_no") or ""))
    elif sira_f == "SLA (aciliyet)":
        goster = sorted(goster, key=lambda k: sla_is_gunu(k) if sla_is_gunu(k) is not None else -999,
                        reverse=True)
    elif sira_f == "Durum":
        goster = sorted(goster, key=lambda k: str(k.get("mevcut_durum") or ""))
    elif sira_f == "Firma":
        goster = sorted(goster, key=lambda k: str(k.get("firma_bilgisi") or "").lower())
    st.caption(f"{len(goster)} / {len(kayitlar)} kayıt")

    # Madde 17: kapsamlı Excel raporu — tüm süreç tek dosyada (istatistik için)
    if goster:
        _rdf = pd.DataFrame([{
            "Servis No": k.get("servis_form_no", ""), "Kaynak": ARAYUZ_ETIKET.get(k.get("arayuz", ""), ""),
            "Stok Kodu": k.get("stok_kodu", ""), "Stok Adı": k.get("stok_adi", ""),
            "Ürün Grubu": k.get("urun_grubu", ""), "Seri No": k.get("seri_no", ""),
            "Arıza": k.get("ariza", ""), "Firma": k.get("firma_bilgisi", ""),
            "Mağaza / Müşteri": k.get("musteri_adi", ""), "Telefon": k.get("musteri_tel", ""),
            "Mail": k.get("musteri_mail", ""), "Adres": k.get("musteri_adres", ""),
            "Sevk / Teslim Şekli": k.get("sevk_kargo_bilgisi", ""),
            "Durum": k.get("mevcut_durum", ""), "Sonuç": k.get("sonuc_durumu", ""),
            "SLA İş Günü": sla_is_gunu(k), "Mal Kabül": _tarih_kisa(k.get("mal_kabul_tarihi")),
            "Depo": k.get("depo", ""), "Depo Açıklaması": k.get("depo_aciklama", ""),
            "Fatura No": k.get("fatura_no", ""), "Fatura Mevcut": ("✓" if _fm_of(k) else "✗"),
            "İrsaliye No": k.get("irsaliye_no", ""),
            "Firma Servis Form No": k.get("firma_servis_form_no", ""),
            "Test Süreci": k.get("test_sureci", ""), "Detay / Not": k.get("detay", ""),
            "Fiziksel Durum": k.get("fiziksel_durum", ""), "İçerik": k.get("icerik_durumu", ""),
            "Personel": k.get("personel", ""),
            "Satış Firma": k.get("satis_firma", ""), "Satış Fiyatı": k.get("satis_fiyati", ""),
            "Satış Tarihi": k.get("satis_tarihi", ""),
        } for k in goster])
        _rbuf = BytesIO()
        with pd.ExcelWriter(_rbuf, engine="openpyxl") as _rw:
            _rdf.to_excel(_rw, index=False, sheet_name=etk[:28])
        st.download_button(f"⬇️ {etk} Excel raporu ({len(goster)} kayıt · tüm süreç)",
                           _rbuf.getvalue(), f"{arayuz}_rapor.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"ts_rapor_{arayuz}")

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
            f'<td>{_durum_chip(k.get("mevcut_durum", ""))}'
            + ((f' <span style="color:#94A3B8;font-size:11px">({k.get("sonuc_durumu")})</span>')
               if k.get("mevcut_durum") == "gönderildi" and (k.get("sonuc_durumu") or "").strip()
               else "") + '</td>'
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
            _fx1, _fx2 = st.columns([2, 1])
            _fx1.markdown('<div style="padding:8px 0;color:#34D399;font-size:13px;font-weight:700">🧾 Fatura: ✓ Mevcut</div>',
                          unsafe_allow_html=True)
            # Madde 12 (muhasebe talebi): yanlış işaretlenen "fatura geldi" düzenlenebilir/geri alınabilir
            with _fx2.popover("✏️ Düzenle", use_container_width=True):
                st.caption("Fatura No'yu düzelt ya da yanlış işaretlendiyse ✗'e geri al.")
                _fno_dz = st.text_input("Fatura No", value=kayit.get("fatura_no", "") or "",
                                        key=f"ts_fno_dz_{kid}")
                if st.button("💾 Fatura No'yu güncelle", key=f"ts_fno_kaydet_{kid}",
                             use_container_width=True):
                    if kayit_guncelle(kid, {"fatura_no": _fno_dz.strip()}):
                        durum_guncelle(kid, kayit.get("mevcut_durum", "mal kabül"),
                                       st.session_state.get("aktif_kullanici", ""),
                                       f"Fatura No düzeltildi: {_fno_dz.strip()}")
                        st.rerun()
                if st.button("↩️ Fatura durumunu ✗'e geri al", key=f"ts_fno_geri_{kid}",
                             use_container_width=True):
                    if kayit_guncelle(kid, {"fatura_mevcut": False}):
                        durum_guncelle(kid, kayit.get("mevcut_durum", "mal kabül"),
                                       st.session_state.get("aktif_kullanici", ""),
                                       "Fatura durumu ✗'e geri alındı (düzeltme)")
                        st.rerun()
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
                # Seçim değişince: değeri AYRI bir 'bekleyen' anahtarda tut. Form
                # text_input'unun widget key'ine (ts_dgsk_) doğrudan yazmak +
                # rerun etmek StreamlitAPIException'a yol açıyordu (widget zaten
                # oluşmuşken key değiştirilemez → sekme kapanıyordu). Artık
                # bekleyen değer form OLUŞMADAN önce (aşağıda) uygulanır.
                if _dsec != _dopts[0] and st.session_state.get(f"_ts_dgmodel_son_{kid}") != _dsec:
                    st.session_state[f"_ts_dgmodel_son_{kid}"] = _dsec
                    _dsku = _dsec.split(" — ")[0].strip()
                    _dadi = ""
                    for _s, _a in _dmods:
                        if _s == _dsku and _a:
                            _dadi = _a
                            break
                    st.session_state[f"_ts_dgsk_bekleyen_{kid}"] = _dsku
                    st.session_state[f"_ts_dgsa_bekleyen_{kid}"] = _dadi

        # Bekleyen ithalat seçimini, form text_input'ları OLUŞMADAN önce uygula.
        # (widget key'i sonradan değiştirilemediği için tek güvenli yer burası)
        _bek_sk = st.session_state.pop(f"_ts_dgsk_bekleyen_{kid}", None)
        if _bek_sk is not None:
            st.session_state[f"ts_dgsk_{kid}"] = _bek_sk
        _bek_sa = st.session_state.pop(f"_ts_dgsa_bekleyen_{kid}", None)
        if _bek_sa is not None:
            st.session_state[f"ts_dgsa_{kid}"] = _bek_sa

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
        # Madde 11: daha önce kullanılan açıklamalar hatırlanır — seç, yeniden yazma
        _eski_acks = depo_aciklamalar()
        _hazir_ack = "—"
        if _eski_acks:
            _hazir_ack = st.selectbox("📝 Kayıtlı açıklamalardan seç (en sık kullandıkların)",
                                      ["—"] + _eski_acks, key=f"ts_depoack_sec_{kid}")
        depo_aciklama = st.text_input("Ürün Son Durumu / Açıklama (rapor için)",
                                      key=f"ts_depoack_{kid}",
                                      value=(_hazir_ack if _hazir_ack != "—"
                                             else (kayit.get("depo_aciklama", "") or "")),
                                      placeholder="örn: panel değişti, sıfır ayarında / 2.el A kalite / hurda - anakart yanmış")
        if st.button("Transfer Et", use_container_width=True, key=f"ts_tbtn_{kid}"):
            durum_haritasi = {"outlet": "satışa hazır", "ikinci el": "satışa hazır",
                              "hurda": "hurda", "merkez": "gönderildi"}
            yeni = durum_haritasi.get(depo, kayit.get("mevcut_durum"))
            if depo_aciklama.strip():
                ekle_depo_aciklama(depo_aciklama.strip())   # madde 11: sonraki transferde hazır
            if durum_guncelle(kid, yeni, st.session_state.get("aktif_kullanici", ""),
                              f"{depo} deposuna transfer" + (f" — {depo_aciklama.strip()}" if depo_aciklama.strip() else ""),
                              {"depo": depo, "depo_aciklama": depo_aciklama.strip(),
                               "depo_tarihi": date.today().isoformat(),
                               # Madde 17: gönderim SONUCU saklanır (sorunsuz mu, değişim mi…)
                               "sonuc_durumu": kayit.get("mevcut_durum", "")}):
                # Transfer sonrası Depolar sekmesine geç (madde 3)
                st.session_state["_ts_git"] = "📦  Depolar"  # radio oluşmadan önce işlenir
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
    g1, g2, g3 = st.columns([1, 1.2, 2.4])
    fatura_f = g1.selectbox("Fatura", ["Tümü", "✓ Mevcut", "✗ Yok"], key="depo_fat_f")
    # Madde 16: son transfer edilen ürün EN ÜSTTE (etiket hemen elinin altında)
    depo_sira = g2.selectbox("Sıralama", ["Son transfer → en üstte", "Servis No ↓",
                                          "Servis No ↑", "Satış tarihi ↓"], key="depo_sira")
    ara = g3.text_input("🔍 Ara — Servis No · Stok · Seri · Firma · Fatura · İrsaliye · Firma Servis No",
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
    # Madde 16: sıralamayı uygula (varsayılan: en son depoya transfer edilen en üstte)
    if depo_sira == "Son transfer → en üstte":
        goster = sorted(goster, key=lambda k: (str(k.get("depo_tarihi") or ""),
                                               str(k.get("servis_form_no") or "")), reverse=True)
    elif depo_sira == "Servis No ↓":
        goster = sorted(goster, key=lambda k: str(k.get("servis_form_no") or ""), reverse=True)
    elif depo_sira == "Servis No ↑":
        goster = sorted(goster, key=lambda k: str(k.get("servis_form_no") or ""))
    elif depo_sira == "Satış tarihi ↓":
        goster = sorted(goster, key=lambda k: str(k.get("satis_tarihi") or ""), reverse=True)

    # Excel dışa aktarma (filtrelenmiş liste)
    if goster:
        _df = pd.DataFrame([{
            "Servis No": k.get("servis_form_no", ""), "Stok Kodu": k.get("stok_kodu", ""),
            "Stok Adı": k.get("stok_adi", ""), "Ürün Grubu": k.get("urun_grubu", ""),
            "Seri No": k.get("seri_no", ""), "Firma": k.get("firma_bilgisi", ""),
            "Mağaza / Müşteri Adı": k.get("musteri_adi", ""),
            "Telefon": k.get("musteri_tel", ""), "Mail": k.get("musteri_mail", ""),
            "Adres": k.get("musteri_adres", ""),
            "Sevk / Teslim Şekli": k.get("sevk_kargo_bilgisi", ""),
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
        # Bekleyen sayfa yönlendirmesi (kayıt/transfer sonrası) — widget
        # OLUŞMADAN önce uygulanmalı, yoksa StreamlitAPIException fırlar.
        _git = st.session_state.pop("_ts_git", None)
        if _git:
            st.session_state["ts_sayfa"] = _git
        sayfa = st.radio(
            "Sayfa",
            ["📥  Mal Kabül", "📋  Evraksız Ürün Kayıt", "🔧  Teknik Servis", "↩️  İade", "📦  Depolar"],
            label_visibility="collapsed", key="ts_sayfa",
        )

    if sayfa == "📥  Mal Kabül":
        _mal_kabul()
    elif sayfa == "📋  Evraksız Ürün Kayıt":
        _evraksiz_kayit()
    elif sayfa == "🔧  Teknik Servis":
        _liste("teknik")
    elif sayfa == "↩️  İade":
        _liste("iade")
    else:
        _depolar()

# -*- coding: utf-8 -*-
"""Muhasebe — Bu Hafta (ödeme masası) ve Ertelenen Ödemeler ekranları (Ekim 2026).

BU HAFTA
  Başlık        : + Manuel ödeme · Excel indir
  Özet          : bugün vadeli · gecikmiş · bu hafta kalan · hafta sonu tahmini bakiye
  Komut çubuğu  : görünüm (Bekleyen | Tümü) · kategori filtresi · arama
  Liste         : güne göre gruplu (Türkçe gün/ay adı); günler açık, tek tek açmak yok.
                  Gün başlığında "Toplu öde" — günün bekleyenlerini tek seferde.
                  Satırın tamamı tıklanır → ödeme penceresi.
  Ödeme penceresi:
     • Ödendi — banka seçimi AÇIK bir karar ("bakiyeden düşme" ayrı seçenek;
       eskiden banka seçilmeden basılınca bakiye sessizce düşülmüyordu)
     • Kısmi öde · Vadeyi ötele (+1/+3/+7/+30 ya da tarih, KALICI kayıt)
     • Düzenle (tutar, kategori, açıklama) · Sil (onaylı) · Geri al (ödenmişse)

İş kuralları değişmedi: odeme_durum_guncelle (bakiye düşme/iade),
odeme_kismi_ode, odeme_*_guncelle, odeme_sil — kayranacc/database.py.
"""
import html as _h
from datetime import timedelta

import streamlit as st

from shared import bilesen as B
from shared.tasarim import kpi_serit, mesaj, bos_durum, tr_sayi
from shared.utils import tr_today
from . import odeme_hesap as H
from .database import (get_aktif_odemeler, get_bankalar, hafta_ekle, odeme_ekle_manuel,
                       odeme_durum_guncelle, odeme_kismi_ode, odeme_vade_guncelle, odeme_tutar_guncelle,
                       odeme_kategori_guncelle, odeme_aciklama_guncelle, odeme_sil, get_ertelenen_odemeler)

_BANKASIZ = "__bankasiz__"


def _tl(v):
    return f"₺{tr_sayi(v, 2)}"


def _usd(v):
    return f"${tr_sayi(v, 2)}"


def _tutar(o):
    p = []
    if H._f(o.get("tutar_tl")):
        p.append(_tl(o["tutar_tl"]))
    if H._f(o.get("tutar_usd")):
        p.append(_usd(o["tutar_usd"]))
    return " + ".join(p) or "—"


def _salt():
    return bool(st.session_state.get("salt_okur"))


def _css():
    from shared.tasarim import css_tek_satir
    return "<style>" + css_tek_satir("""
.od-s{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 16px;align-items:center;}
.od-f{display:flex;align-items:center;gap:8px;min-width:0;}
.od-f b{font-size:13.5px;font-weight:600;color:var(--k-metin);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.od-s .k-meta{margin-top:3px;font-size:12px;}
.od-t{text-align:right;white-space:nowrap;}
.od-t b{display:block;font-family:var(--k-mono);font-variant-numeric:tabular-nums;font-size:14px;font-weight:600;color:var(--k-metin);}
.od-t small{font-size:11.5px;color:var(--d);font-weight:600;}
.od-odendi{opacity:.55;}
.od-odendi .od-t b{text-decoration:line-through;text-decoration-color:color-mix(in srgb,var(--k-metin) 35%,transparent);}
.od-dt-ad{font-size:19px;font-weight:650;color:var(--k-metin);}
.od-dt-alt{font-size:13px;color:var(--k-soluk);margin:2px 0 12px;}
""") + "</style>"


_DURUM = {"odendi": ("Ödendi", "yesil"), "gecikmis": ("Gecikmiş", "kirmizi"), "bugun": ("Bugün vadeli", "amber"),
          "yarin": ("Yarın", "cyan"), "ileri": ("Bekliyor", "mor"), "tarihsiz": ("Vadesiz", "silik")}


def _satir_html(o, kat, bugun, banka_ad):
    d = H.vade_durumu(o, bugun)
    ad, renk = _DURUM[d]
    kat_lbl = kat.get(o.get("kategori") or "diger", kat.get("diger", {})).get("label", o.get("kategori") or "")
    alt = banka_ad.get(o.get("banka_id"), "") if d == "odendi" else ""
    return (f'<div class="od-s{" od-odendi" if d == "odendi" else ""}">'
            f'<div style="min-width:0"><div class="od-f"><b>{_h.escape(str(o.get("firma") or "—"))}</b></div>'
            f'{B.meta(B.cip(kat_lbl, "mor2"), _h.escape(str(o.get("aciklama") or ""))[:70], alt)}</div>'
            f'<div class="od-t"><b>{_tutar(o)}</b><small>{ad}</small></div></div>')


def _ac(oid):
    B.detay_ac("od", oid)


def _toplu_ac(gun):
    st.session_state["_od_toplu"] = gun


# ════════════════════════════════════════════════════════════════════
def render_bu_hafta(kategoriler, export_excel, kur):
    """kur: Muhasebe'nin kendi kuru (sol menüdeki USD/TL kutusu) — Genel Bakış ile
    AYNI kaynak, yoksa hafta sonu tahmini iki sayfada farklı çıkar."""
    st.markdown(_css(), unsafe_allow_html=True)
    bugun = tr_today()
    kur = float(kur or 0)
    odemeler, hafta = get_aktif_odemeler()
    bankalar = get_bankalar() or []
    ey = B.baslik_eylem("💳 Muhasebe", "Bu Hafta",
                        aciklama=(hafta or {}).get("hafta_adi") or "Aktif hafta yok",
                        eylemler=[{"etiket": "Manuel ödeme", "key": "btn_acc_manuel", "icon": ":material/add:",
                                   "birincil": True, "disabled": _salt()}])
    if ey.get("btn_acc_manuel"):
        _manuel_dialog(kategoriler, hafta)
    if not odemeler:
        st.markdown(bos_durum("Bu hafta ödeme yok", "Veri Yükleme'den haftanın Excel'ini yükle ya da "
                              "'Manuel ödeme' ile tek tek ekle.", "payments"), unsafe_allow_html=True)
        return

    oz = H.ozet(odemeler, bankalar, kur, bugun)
    hs = oz["hafta_sonu_tl"]
    st.markdown(kpi_serit([
        {"etiket": "Bugün vadeli", "deger": f"{len(oz['bugun'])} ödeme", "renk": "amber" if oz["bugun"] else "silik",
         "alt": " + ".join(x for x in (_tl(oz["bugun_tl"]) if oz["bugun_tl"] else "",
                                       _usd(oz["bugun_usd"]) if oz["bugun_usd"] else "") if x) or "bugün ödeme yok"},
        {"etiket": "Gecikmiş", "deger": f"{len(oz['gecikmis'])} ödeme", "renk": "kirmizi" if oz["gecikmis"] else "silik",
         "alt": " + ".join(x for x in (_tl(oz["gecikmis_tl"]) if oz["gecikmis_tl"] else "",
                                       _usd(oz["gecikmis_usd"]) if oz["gecikmis_usd"] else "") if x) or "gecikme yok"},
        {"etiket": "Bu hafta kalan", "deger": _tl(oz["bekleyen_tl"]), "renk": "mor",
         "alt": (f"+ {_usd(oz['bekleyen_usd'])} · " if oz["bekleyen_usd"] else "")
                + f"{oz['odendi_adet']}/{oz['adet']} ödendi"},
        {"etiket": "Hafta sonu tahmini" if hs >= 0 else "Nakit açığı", "deger": _tl(abs(hs)),
         "renk": "yesil" if hs >= 0 else "kirmizi",
         "alt": "TL bankalar − bekleyenler",
         "ipucu": f"TL banka bakiyesi − bekleyen TL − bekleyen USD × kur ({tr_sayi(kur, 4)})"},
    ]), unsafe_allow_html=True)

    # Komut çubuğu
    say = {}
    for o in odemeler:
        say[o.get("kategori") or "diger"] = say.get(o.get("kategori") or "diger", 0) + 1
    c1, c2, c3 = st.columns([1.6, 3.0, 1.0], vertical_alignment="bottom")
    with c1:
        gor = st.segmented_control("Görünüm", [f"Bekleyen ({oz['adet'] - oz['odendi_adet']})", f"Tümü ({oz['adet']})"],
                                   default=f"Bekleyen ({oz['adet'] - oz['odendi_adet']})", key="od_gorunum",
                                   label_visibility="collapsed") or "Bekleyen"
    ara = c2.text_input("Ara", key="od_ara", placeholder="Firma, açıklama, tutar…", label_visibility="collapsed")
    f = B.filtre(c3, [{"etiket": "Kategori", "key": "od_f_kat",
                       "secenekler": sorted(say, key=lambda k: kategoriler.get(k, {}).get("oncelik", 99)),
                       "format_func": lambda k: k if k == "Tümü" else f"{kategoriler.get(k, {}).get('label', k)} ({say.get(k, 0)})"}])
    liste = [o for o in odemeler
             if (not gor.startswith("Bekleyen") or not H.odendi_mi(o))
             and (f["od_f_kat"] == "Tümü" or (o.get("kategori") or "diger") == f["od_f_kat"])]
    if ara.strip():
        from shared.utils import tr_kucuk
        a = tr_kucuk(ara)
        liste = [o for o in liste if a in tr_kucuk(f"{o.get('firma','')} {o.get('aciklama','')} "
                                                     f"{o.get('tutar_tl') or ''} {o.get('tutar_usd') or ''}")]
    if not liste:
        st.markdown(bos_durum("Bekleyen ödeme kalmadı" if gor.startswith("Bekleyen") and not ara and f["od_f_kat"] == "Tümü"
                              else "Filtreye uyan ödeme yok",
                              "Ödenenleri görmek için 'Tümü'ne geç." if gor.startswith("Bekleyen") else "Filtreyi değiştir.",
                              "task_alt"), unsafe_allow_html=True)
    banka_ad = {b["id"]: b.get("hesap_adi", "") for b in bankalar}
    oncelik = {k: v.get("oncelik", 99) for k, v in kategoriler.items()}
    for gun, glist in H.gunlere_bol(liste, oncelik):
        t = H.gun_toplam(glist)
        tutar = " + ".join(x for x in (_tl(t["tl"]) if t["tl"] else "", _usd(t["usd"]) if t["usd"] else "") if x)
        g1, g2 = st.columns([5, 1.1], vertical_alignment="bottom")
        g1.markdown(B.grup_basligi(H.gun_basligi(gun, tr_today()), f"{len(glist)} ödeme · {tutar}"),
                    unsafe_allow_html=True)
        if t["bekleyen"] >= 2 and not _salt():
            g2.button(f"Toplu öde ({t['bekleyen']})", key=f"od_toplu_{gun}", type="tertiary", icon=":material/done_all:",
                      on_click=_toplu_ac, args=(gun,), use_container_width=True)
        for o in glist:
            B.tiklanir(f"od{o['id']}", _satir_html(o, kategoriler, bugun, banka_ad), _ac, (o["id"],), tur="satir",
                       renk=_DURUM[H.vade_durumu(o, bugun)][1], etiket=f"{o.get('firma','')} ödemesi")

    e1, e2 = st.columns([1, 3], vertical_alignment="center")
    e1.download_button("Excel indir", data=lambda: export_excel(odemeler, (hafta or {}).get("hafta_adi", ""), kur),
                       file_name=f"odeme_listesi_{bugun}.xlsx", on_click="ignore",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True, icon=":material/download:", key="od_excel")
    e2.caption("Haftanın tüm ödemeleri; özet, günlük ayrıntı ve kategori analizi sayfalarıyla.")

    gun = st.session_state.pop("_od_toplu", None)
    if gun:
        _toplu_dialog([o for o in odemeler if str(o.get("vade") or "")[:10] == gun and not H.odendi_mi(o)],
                      bankalar, kur, gun)
    sec = B.detay_istendi("od")
    if sec:
        o = next((x for x in odemeler if x.get("id") == sec), None)
        if o:
            _odeme_dialog(o, kategoriler, bankalar, kur)


# ════════════════════════════════════════════════════════════════════
def _banka_secimi(bankalar, key, o=None):
    """Banka seçimi AÇIK bir karar: liste boş başlar; 'Bakiyeden düşme' ayrı seçenek."""
    secenek = [b["id"] for b in bankalar] + [_BANKASIZ]
    para = "USD" if o and H._f(o.get("tutar_usd")) and not H._f(o.get("tutar_tl")) else "TL"
    ad = {b["id"]: f"{b.get('hesap_adi', '')} · {tr_sayi(H._f(b.get('bakiye')), 2)} {b.get('para_birimi', '')}"
          for b in bankalar}
    ad[_BANKASIZ] = "Bakiyeden düşme (yalnız ödendi işaretle)"
    sirali = sorted(secenek, key=lambda i: (i == _BANKASIZ, next((b.get("para_birimi") != para for b in bankalar
                                                                  if b["id"] == i), True)))
    return st.selectbox("Hangi bankadan ödendi?", sirali, index=None, key=key, format_func=ad.get,
                        placeholder="Banka seç…",
                        help="Seçilen hesabın bakiyesinden düşülür. Ödeme başka yerden yapıldıysa "
                             "'Bakiyeden düşme'yi seç.")


@st.dialog("Ödeme", width="large")
def _odeme_dialog(o, kategoriler, bankalar, kur):
    bugun = tr_today()
    d = H.vade_durumu(o, bugun)
    ad, renk = _DURUM[d]
    kat_lbl = kategoriler.get(o.get("kategori") or "diger", {}).get("label", o.get("kategori") or "")
    st.markdown(_css() + f'<div class="od-dt-ad">{_h.escape(str(o.get("firma") or ""))} {B.cip(ad, renk)}</div>'
                f'<div class="od-dt-alt">{_h.escape(str(o.get("aciklama") or ""))} · {kat_lbl} · vade '
                f'{H.gun_basligi(o.get("vade"), bugun)} · <b style="color:var(--k-metin)">{_tutar(o)}</b></div>',
                unsafe_allow_html=True)
    if _salt():
        st.caption("Salt-okur oturum: işlem yapılamaz.")
        return
    oid = o["id"]
    if d == "odendi":
        ban = next((b.get("hesap_adi") for b in bankalar if b["id"] == o.get("banka_id")), None)
        st.markdown(mesaj("basari", f"Ödendi · {o.get('odendi_tarih') or ''}"
                                    + (f" · {ban} hesabından düşüldü" if ban else " · bakiyeden düşülmedi")),
                    unsafe_allow_html=True)
        if st.button("Geri al (bekliyor yap)", icon=":material/undo:", key=f"od_geri_{oid}",
                     help="Bankadan düşüldüyse bakiye iade edilir"):
            odeme_durum_guncelle(oid, "bekliyor", kur=kur)
            B.yenile("Ödeme bekliyor durumuna alındı", ac=("od", oid))
    else:
        t1, t2, t3, t4 = st.tabs(["Öde", "Vadeyi ötele", "Düzenle", "Sil"])
        with t1:
            b1, b2 = st.columns([2.4, 1.2], vertical_alignment="bottom")
            with b1:
                bsec = _banka_secimi(bankalar, f"od_banka_{oid}", o)
            if b2.button("Ödendi", type="primary", icon=":material/check_circle:", disabled=bsec is None,
                         use_container_width=True, key=f"od_ode_{oid}"):
                odeme_durum_guncelle(oid, "odendi", None if bsec == _BANKASIZ else bsec, kur)
                B.yenile(f"{o.get('firma')} ödendi")
            with st.expander("Kısmi öde", icon=":material/payments:"):
                st.caption("Ödenen kısım ayrı bir 'ödendi' kaydı olur; kalan bekliyor olarak devam eder. "
                           "Banka seçimi yukarıdan alınır.")
                k1, k2 = st.columns(2)
                mtl, musd = H._f(o.get("tutar_tl")), H._f(o.get("tutar_usd"))
                ktl = k1.number_input(f"Ödenen TL (en çok {_tl(mtl)})", min_value=0.0, max_value=max(0.0, mtl),
                                      step=100.0, format="%.2f", key=f"od_ktl_{oid}", disabled=mtl <= 0)
                kusd = k2.number_input(f"Ödenen USD (en çok {_usd(musd)})", min_value=0.0, max_value=max(0.0, musd),
                                       step=100.0, format="%.2f", key=f"od_kusd_{oid}", disabled=musd <= 0)
                if st.button("Kısmi öde", key=f"od_kode_{oid}", icon=":material/payments:",
                             disabled=(ktl <= 0 and kusd <= 0) or bsec is None):
                    ok, msg = odeme_kismi_ode(oid, ktl, kusd, None if bsec == _BANKASIZ else bsec, kur)
                    (B.yenile(msg, ac=("od", oid)) if ok else st.error(msg))
        with t2:
            mevcut = H._tarih(o.get("vade")) or bugun
            st.caption(f"Mevcut vade {H.gun_basligi(mevcut.isoformat(), bugun)}. Erteleme kaydı kalıcıdır "
                       "(Ertelenen Ödemeler'de görünür).")
            hcols = st.columns(4)
            for col, gun in zip(hcols, (1, 3, 7, 30)):
                if col.button(f"+{gun} gün", key=f"od_v{gun}_{oid}", use_container_width=True):
                    _otele(o, mevcut, mevcut + timedelta(days=gun))
            v1, v2 = st.columns([2, 1], vertical_alignment="bottom")
            yv = v1.date_input("Ya da tarih seç", value=mevcut, key=f"od_vtar_{oid}", format="DD.MM.YYYY")
            if v2.button("Ötele", key=f"od_vkay_{oid}", type="primary", use_container_width=True,
                         icon=":material/event:", disabled=yv == mevcut):
                _otele(o, mevcut, yv)
        with t3:
            with st.form(f"od_duz_{oid}", border=False):
                f1, f2, f3 = st.columns(3)
                ytl = f1.number_input("Tutar TL", min_value=0.0, step=100.0, format="%.2f", value=H._f(o.get("tutar_tl")))
                yusd = f2.number_input("Tutar USD", min_value=0.0, step=100.0, format="%.2f", value=H._f(o.get("tutar_usd")))
                anahtarlar = list(kategoriler)
                mk = o.get("kategori") or "diger"
                ykat = f3.selectbox("Kategori", anahtarlar, index=anahtarlar.index(mk) if mk in anahtarlar else len(anahtarlar) - 1,
                                    format_func=lambda k: kategoriler[k]["label"])
                yack = st.text_input("Açıklama", value=o.get("aciklama") or "")
                if st.form_submit_button("Kaydet", type="primary", icon=":material/save:"):
                    if ytl <= 0 and yusd <= 0:
                        st.error("En az bir tutar (TL ya da USD) 0'dan büyük olmalı.")
                    else:
                        odeme_tutar_guncelle(oid, tutar_tl=ytl, tutar_usd=yusd)
                        if ykat != mk:
                            odeme_kategori_guncelle(oid, ykat)
                        if yack.strip() != (o.get("aciklama") or "").strip():
                            odeme_aciklama_guncelle(oid, yack.strip())
                        B.yenile("Ödeme güncellendi", ac=("od", oid))
        with t4:
            if B.onayli_sil(f"Evet, {o.get('firma')} ödemesini sil", key=f"od_{oid}", dugme="Ödemeyi sil",
                            aciklama="Kayıt kalıcı olarak silinir."):
                odeme_sil(oid)
                B.yenile("Ödeme silindi")


def _otele(o, eski, yeni):
    if odeme_vade_guncelle(o["id"], yeni, ertele=True, eski_vade=eski):
        B.yenile(f"Vade {yeni:%d.%m.%Y} olarak ötelendi")
    else:
        st.error("Vade güncellenemedi; ayrıntı Sistem Kayıtları'nda. Ödemenin vadesi DEĞİŞMEDİ.")


@st.dialog("Toplu öde", width="large")
def _toplu_dialog(liste, bankalar, kur, gun):
    st.caption(f"{H.gun_basligi(gun, tr_today())} · seçtiklerin aynı bankadan ödendi işaretlenir.")
    if not liste:
        st.caption("Bu günde bekleyen ödeme kalmadı.")
        return
    secili = []
    for o in liste:
        if st.checkbox(f"{o.get('firma')} · {_tutar(o)}", value=True, key=f"od_ts_{o['id']}"):
            secili.append(o)
    bsec = _banka_secimi(bankalar, f"od_tbanka_{gun}")
    tl = sum(H._f(o.get("tutar_tl")) for o in secili)
    usd = sum(H._f(o.get("tutar_usd")) for o in secili)
    if st.button(f"{len(secili)} ödemeyi ödendi işaretle · " + " + ".join(
            x for x in (_tl(tl) if tl else "", _usd(usd) if usd else "") if x),
            type="primary", icon=":material/done_all:", disabled=not secili or bsec is None, key=f"od_tkay_{gun}"):
        for o in secili:
            odeme_durum_guncelle(o["id"], "odendi", None if bsec == _BANKASIZ else bsec, kur)
        B.yenile(f"{len(secili)} ödeme ödendi")


@st.dialog("Manuel ödeme", width="large")
def _manuel_dialog(kategoriler, hafta):
    with st.form("manuel_form", border=False):
        c1, c2 = st.columns(2)
        firma = c1.text_input("Firma / kişi")
        aciklama = c2.text_input("Açıklama")
        d1, d2, d3, d4 = st.columns([1.3, 1.3, 1.2, 1.2])
        vade = d1.date_input("Vade", value=tr_today(), format="DD.MM.YYYY")
        kategori = d2.selectbox("Kategori", list(kategoriler), format_func=lambda k: kategoriler[k]["label"])
        tl = d3.number_input("Tutar TL", min_value=0.0, step=100.0, format="%.2f")
        usd = d4.number_input("Tutar USD", min_value=0.0, step=100.0, format="%.2f")
        if st.form_submit_button("Ekle", type="primary", icon=":material/add:"):
            if not firma.strip():
                st.error("Firma / kişi gerekli.")
            elif tl <= 0 and usd <= 0:
                st.error("En az bir tutar gir.")
            else:
                hid = hafta["id"] if hafta else hafta_ekle("Manuel Girişler")
                odeme_ekle_manuel(hid, firma.strip(), aciklama.strip(), "", vade.isoformat(),
                                  tl if tl > 0 else None, usd if usd > 0 else None, kategori)
                B.yenile(f"{firma.strip()} eklendi")


# ════════════════════════════════════════════════════════════════════
def render_ertelenenler(kategoriler):
    """Ertelenen ödemeler — KALICI kayıttan (ödeme kaydındaki orijinal_vade /
    ertelendi_sayisi). Eskiden yalnız tarayıcı oturumundaki liste okunuyordu."""
    st.markdown(_css(), unsafe_allow_html=True)
    B.baslik_eylem("⏳ Muhasebe", "Ertelenen Ödemeler",
                   aciklama="Vadesi ötelenmiş ödemeler: ilk vade, kaç kez ertelendiği, şimdiki durumu.")
    from .database import erteleme_sutunlari_var
    if erteleme_sutunlari_var():
        st.markdown('<div style="font-size:12px;color:var(--k-yesil);margin:-4px 0 10px">✓ Veritabanı güncel: '
                    'erteleme geçmişi kalıcı olarak tutuluyor (07_odeme_erteleme.sql uygulanmış).</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(mesaj("uyari", "Veritabanında erteleme sütunları yok: veritabani/07_odeme_erteleme.sql henüz "
                                   "çalıştırılmamış. Ötelemeler yapılır ama geçmişi tutulmaz. Supabase → SQL Editor'de "
                                   "bir kez çalıştırın."), unsafe_allow_html=True)
    liste = get_ertelenen_odemeler() or []
    if not liste:
        st.markdown(bos_durum("Ertelenmiş ödeme yok",
                              "Bu Hafta'da bir ödemeye tıkla → 'Vadeyi ötele'. Erteleme geçmişi için "
                              "veritabani/07_odeme_erteleme.sql bir kez çalıştırılmış olmalı.", "event_repeat"),
                    unsafe_allow_html=True)
        return
    bugun = tr_today()
    bek = [o for o in liste if not H.odendi_mi(o)]
    st.markdown(kpi_serit([
        {"etiket": "Ertelenmiş", "deger": f"{len(liste)} ödeme", "renk": "amber",
         "alt": f"{len(bek)} hâlâ bekliyor"},
        {"etiket": "Bekleyen tutar", "deger": _tl(sum(H._f(o.get("tutar_tl")) for o in bek)), "renk": "mor",
         "alt": (f"+ {_usd(sum(H._f(o.get('tutar_usd')) for o in bek))}"
                 if sum(H._f(o.get('tutar_usd')) for o in bek) else "")},
        {"etiket": "En çok ertelenen", "deger": f"{max(int(o.get('ertelendi_sayisi') or 1) for o in liste)} kez",
         "renk": "kirmizi", "anlam": "notr"},
    ]), unsafe_allow_html=True)
    for o in sorted(liste, key=lambda x: (H.odendi_mi(x), str(x.get("vade") or ""))):
        ilk = H._tarih(o.get("orijinal_vade"))
        simdi = H._tarih(o.get("vade"))
        fark = f"{(simdi - ilk).days} gün kaydı" if ilk and simdi else ""
        kat_lbl = kategoriler.get(o.get("kategori") or "diger", {}).get("label", "")
        ad, renk = _DURUM[H.vade_durumu(o, bugun)]
        st.markdown(
            f'<div style="padding:10px 14px;border:1px solid var(--k-kenar);border-left:3px solid var(--k-{renk});'
            f'border-radius:10px;background:var(--k-yuzey1);margin-bottom:6px">'
            f'<div class="od-s"><div style="min-width:0"><div class="od-f"><b>{_h.escape(str(o.get("firma") or ""))}</b>'
            f'{B.cip(str(int(o.get("ertelendi_sayisi") or 1)) + "× ertelendi", "amber")}</div>'
            f'{B.meta(kat_lbl, (f"ilk vade {ilk:%d.%m.%Y}" if ilk else ""), (f"şimdi {simdi:%d.%m.%Y}" if simdi else ""), fark)}</div>'
            f'<div class="od-t" style="--d:var(--k-{renk})"><b>{_tutar(o)}</b><small>{ad}</small></div></div></div>',
            unsafe_allow_html=True)

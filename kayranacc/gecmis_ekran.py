# -*- coding: utf-8 -*-
"""Muhasebe › Ödenenler & Geçmiş (Ekim 2026).

Üç görünüm (sekme yerine seçici):
  Bu hafta ödenenler — ödeme günüyle gruplu; tıkla → ayrıntı · geri al
  Geçmiş haftalar    — hafta kartları (ödendi oranı); tıkla → ödemeler ·
                       aktif yap · ONAYLI sil (kaç ödemenin de silineceği yazar)
  Çek arşivi         — TL / USD, arama; tıkla → ayrıntı · ONAYLI sil; toplu sil onaylı

Giderilen hatalar:
  • "Ödenen Ödemeler" sekmesi bu hafta ödeme yoksa SAYFAYI
    durduruyordu → "Geçmiş Haftalar" ve "Çek Arşivi" boş görünüyordu.
  • Hafta "Sil" düğmesi haftayı TÜM ödemeleriyle ONAYSIZ siliyordu.
  • Çek arşivindeki çöp kutusu çeki onaysız siliyordu.
"""
import html as _h

import streamlit as st

from shared import bilesen as B
from shared.tasarim import kpi_serit, bos_durum, mesaj, tr_sayi


def gun_ay_yil(v):
    """'2026-09-30' → '30.09.2026' (Muhasebe'nin tarih biçimi; ortak gun_ay_yil tire kullanıyor)."""
    t = str(v or "")[:10]
    return f"{t[8:10]}.{t[5:7]}.{t[:4]}" if len(t) == 10 and t[4] == "-" else (t or "—")
from .database import (cek_durum_norm, cek_sil, cek_sil_hepsi, cek_tutarlari, get_aktif_hafta,
                       get_aktif_odemeler, get_bankalar, get_cekler, get_hafta_odemeler, get_hafta_ozet,
                       get_kur, get_tum_haftalar, hafta_aktif_yap, hafta_sil, odeme_durum_guncelle)
from .odeme_hesap import KATEGORI_AD, gun_basligi

SEMBOL = {"TL": "₺", "USD": "$", "EUR": "€"}


def _tl(v):
    return f"₺{tr_sayi(float(v or 0), 2)}"


def _usd(v):
    return f"${tr_sayi(float(v or 0), 2)}"


def _tutar(o):
    p = []
    if float(o.get("tutar_tl") or 0):
        p.append(_tl(o.get("tutar_tl")))
    if float(o.get("tutar_usd") or 0):
        p.append(_usd(o.get("tutar_usd")))
    return " + ".join(p) or "—"


def _satir(sol_ust, sol_alt, orta_ust, orta_meta, sag_ust, sag_alt=""):
    return (f'<div style="display:grid;grid-template-columns:120px minmax(0,1fr) auto;gap:4px 16px;align-items:center">'
            f'<div><div style="font-size:12.5px;color:var(--k-soluk)">{sol_ust}</div>'
            f'<div style="font-size:11.5px;color:var(--k-silik)">{sol_alt}</div></div>'
            f'<div style="min-width:0"><div style="font-size:13.5px;font-weight:600;color:var(--k-metin);white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis">{orta_ust}</div>{orta_meta}</div>'
            f'<div style="text-align:right;white-space:nowrap"><b style="font-family:var(--k-mono);font-size:14px">{sag_ust}</b>'
            f'<div style="font-size:11.5px;color:var(--k-silik)">{sag_alt}</div></div></div>')


def render_gecmis():
    B.baslik_eylem("🕐 Muhasebe", "Ödenenler & Geçmiş",
                   aciklama="Bu haftanın ödenenleri, geçmiş haftalar ve çek arşivi.")
    gor = st.segmented_control("Görünüm", ["Bu hafta ödenenler", "Geçmiş haftalar", "Çek arşivi"],
                               default="Bu hafta ödenenler", key="gec_gorunum",
                               label_visibility="collapsed") or "Bu hafta ödenenler"
    if gor == "Bu hafta ödenenler":
        _odenenler()
    elif gor == "Geçmiş haftalar":
        _haftalar()
    else:
        _cek_arsivi()


# ── Bu hafta ödenenler ──────────────────────────────────────────────
def _odenenler():
    odemeler, hafta = get_aktif_odemeler()
    od = [o for o in odemeler if o.get("durum") == "odendi"]
    if not od:
        st.markdown(bos_durum("Bu hafta henüz ödenen yok", "Ödemeler 'Bu Hafta' sayfasından ödendi işaretlenir.",
                              "task_alt"), unsafe_allow_html=True)
        return
    bmap = {b["id"]: b.get("hesap_adi") for b in (get_bankalar() or [])}
    st.markdown(kpi_serit([
        {"etiket": "Ödenen TL", "deger": _tl(sum(float(o.get("tutar_tl") or 0) for o in od)), "renk": "yesil"},
        {"etiket": "Ödenen USD", "deger": _usd(sum(float(o.get("tutar_usd") or 0) for o in od)), "renk": "cyan"},
        {"etiket": "Ödeme", "deger": tr_sayi(len(od)), "renk": "mor", "alt": f"{len(odemeler)} ödemeden"},
    ]), unsafe_allow_html=True)
    from datetime import date
    bugun = date.today()
    gruplar = {}
    for o in sorted(od, key=lambda o: str(o.get("odendi_tarih") or o.get("vade") or ""), reverse=True):
        gruplar.setdefault(str(o.get("odendi_tarih") or o.get("vade") or "")[:10], []).append(o)
    for gun, g in gruplar.items():
        st.markdown(B.grup_basligi(gun_basligi(gun, bugun) if gun else "Tarihsiz", f"{len(g)} ödeme"),
                    unsafe_allow_html=True)
        for o in g:
            kat = KATEGORI_AD.get(o.get("kategori") or "diger", "Diğer")
            B.tiklanir(f"gecod{o['id']}",
                       _satir(f"vade {gun_ay_yil(o.get('vade'))}", "", _h.escape(o.get("firma") or "—"),
                              B.meta(B.cip(kat), bmap.get(o.get("banka_id")) or "banka seçilmemiş",
                                     _h.escape((o.get("aciklama") or "")[:60])),
                              _tutar(o), "ödendi"),
                       B.detay_ac, ("gecod", o["id"]), tur="satir", renk="yesil", etiket="Ödeme ayrıntısı")
    sec = B.detay_istendi("gecod")
    if sec:
        o = next((x for x in od if x.get("id") == sec), None)
        if o:
            _odenen_dialog(o, bmap)


@st.dialog("Ödenmiş ödeme", width="medium")
def _odenen_dialog(o, bmap):
    st.markdown(f'<div style="font-size:18px;font-weight:650">{_h.escape(o.get("firma") or "")}</div>'
                f'<div style="font-family:var(--k-mono);font-size:20px;font-weight:600;margin:4px 0 12px">{_tutar(o)}</div>',
                unsafe_allow_html=True)
    for etk, v in (("Açıklama", o.get("aciklama") or "—"), ("Kategori", KATEGORI_AD.get(o.get("kategori") or "diger")),
                   ("Vade", gun_ay_yil(o.get("vade"))), ("Ödendi", gun_ay_yil(o.get("odendi_tarih"))),
                   ("Banka", bmap.get(o.get("banka_id")) or "—")):
        st.markdown(f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--k-kenar)">'
                    f'<span style="width:90px;color:var(--k-silik);font-size:12.5px">{etk}</span>'
                    f'<span style="font-size:13px">{_h.escape(str(v))}</span></div>', unsafe_allow_html=True)
    if st.session_state.get("salt_okur"):
        return
    st.caption("Geri alınca ödeme yeniden 'bekliyor' olur; ödendiği bankanın bakiyesine tutar iade edilir.")
    if st.button("Geri al (bekliyor yap)", icon=":material/undo:", key=f"gec_geri_{o['id']}"):
        odeme_durum_guncelle(o["id"], "bekliyor", kur=get_kur())
        B.yenile(f"{o.get('firma')} ödemesi geri alındı")


# ── Geçmiş haftalar ─────────────────────────────────────────────────
def _haftalar():
    haftalar = get_tum_haftalar() or []
    if not haftalar:
        st.markdown(bos_durum("Henüz hafta yok", "Haftalık ödeme listesi Veri Yükleme sayfasından yüklenir.",
                              "calendar_month"), unsafe_allow_html=True)
        return
    aktif = get_aktif_hafta()
    aktif_id = aktif["id"] if aktif else None
    for i in range(0, len(haftalar), 3):
        for col, h in zip(st.columns(3, gap="small"), haftalar[i:i + 3]):
            with col:
                oz = get_hafta_ozet(h["id"])
                oran = (oz["odendi"] / oz["toplam"]) if oz["toplam"] else 0
                cip = B.cip("Aktif", "mor") if h["id"] == aktif_id else ""
                B.tiklanir(f"gech{h['id']}",
                           f'<div style="display:flex;align-items:center;gap:8px"><b style="flex:1;font-size:14px">'
                           f'{_h.escape(h.get("hafta_adi") or "")}</b>{cip}</div>'
                           f'<div style="font-size:12px;color:var(--k-silik);margin:3px 0 10px">{oz["odendi"]}/{oz["toplam"]} '
                           f'ödendi · yüklendi {_h.escape(str(h.get("yuklendi_tarih") or "—"))}</div>'
                           f'<div style="height:5px;border-radius:99px;background:var(--k-ortu2);overflow:hidden">'
                           f'<div style="height:100%;width:{oran*100:.0f}%;background:var(--k-yesil)"></div></div>'
                           f'<div style="font-family:var(--k-mono);font-size:13px;margin-top:10px">{_tl(oz["tl_toplam"])}'
                           f'<span style="color:var(--k-silik)"> + </span>{_usd(oz["usd_toplam"])}</div>',
                           B.detay_ac, ("gech", h["id"]), tur="kart", renk="mor" if h["id"] == aktif_id else None,
                           etiket=f"{h.get('hafta_adi')} ayrıntısı")
    sec = B.detay_istendi("gech")
    if sec:
        h = next((x for x in haftalar if x.get("id") == sec), None)
        if h:
            _hafta_dialog(h, h["id"] == aktif_id)


@st.dialog("Hafta", width="large")
def _hafta_dialog(h, aktif_mi):
    odemeler = get_hafta_odemeler(h["id"]) or []
    st.markdown(f'<div style="font-size:19px;font-weight:650">{_h.escape(h.get("hafta_adi") or "")}</div>'
                f'<div style="font-size:13px;color:var(--k-soluk);margin:2px 0 12px">{len(odemeler)} ödeme · '
                f'{sum(1 for o in odemeler if o.get("durum") == "odendi")} ödendi</div>', unsafe_allow_html=True)
    for o in sorted(odemeler, key=lambda o: str(o.get("vade") or "")):
        durum = "✓ ödendi" if o.get("durum") == "odendi" else "bekliyor"
        st.markdown(f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--k-kenar);font-size:13px">'
                    f'<span style="width:80px;color:var(--k-silik)">{gun_ay_yil(o.get("vade"))}</span>'
                    f'<span style="flex:1;min-width:0">{_h.escape(o.get("firma") or "")}</span>'
                    f'<b style="font-family:var(--k-mono)">{_tutar(o)}</b>'
                    f'<span style="width:70px;text-align:right;color:var(--k-silik)">{durum}</span></div>',
                    unsafe_allow_html=True)
    if st.session_state.get("salt_okur"):
        return
    st.markdown("")
    if not aktif_mi:
        if st.button("Bu haftayı aktif yap", icon=":material/folder_open:", type="primary", key=f"gech_ac_{h['id']}"):
            hafta_aktif_yap(h["id"])
            B.yenile(f"'{h.get('hafta_adi')}' aktif yapıldı")
    with st.expander("Haftayı sil", icon=":material/delete:"):
        st.markdown(mesaj("uyari", f"Hafta, içindeki {len(odemeler)} ödemeyle birlikte kalıcı olarak silinir. "
                                   "Ödendi işaretlenmiş ödemelerin banka hareketleri geri alınmaz."),
                    unsafe_allow_html=True)
        if B.onayli_sil(f"Evet, '{h.get('hafta_adi')}' haftasını {len(odemeler)} ödemesiyle sil",
                        key=f"gech_{h['id']}", dugme="Haftayı sil"):
            hafta_sil(h["id"])
            B.yenile("Hafta silindi")


# ── Çek arşivi ──────────────────────────────────────────────────────
def _cek_arsivi():
    c1, c2 = st.columns([1.1, 3.5], vertical_alignment="bottom")
    with c1:
        pb = st.segmented_control("Para birimi", ["TL", "USD"], default="TL", key="gec_cek_pb",
                                  label_visibility="collapsed") or "TL"
    ara = c2.text_input("Ara", key="gec_cek_ara", placeholder="Firma, çek no, ref no, banka…",
                        label_visibility="collapsed")
    cekler = get_cekler(pb) or []
    sym = SEMBOL[pb]
    if not cekler:
        st.markdown(bos_durum(f"Kayıtlı {pb} çeki yok", "Çek dökümü Veri Yükleme sayfasından yüklenir.", "receipt"),
                    unsafe_allow_html=True)
        return
    from shared.utils import tr_kucuk
    a = tr_kucuk(ara)
    liste = [c for c in cekler if not a or a in tr_kucuk(
        f"{c.get('ch_ismi','')} {c.get('cek_no','')} {c.get('ref_no','')} {c.get('banka','')}")]
    t = [cek_tutarlari(c) for c in cekler]
    st.markdown(kpi_serit([
        {"etiket": "Çek", "deger": tr_sayi(len(cekler)), "renk": "mor", "alt": f"{sum(1 for x in t if x['odendi'])} ödendi"},
        {"etiket": "Toplam meblağ", "deger": f"{sym}{tr_sayi(sum(x['meblag'] for x in t), 2)}", "renk": "cyan"},
        {"etiket": "Kalan", "deger": f"{sym}{tr_sayi(sum(x['kalan'] for x in t), 2)}", "renk": "amber"},
    ]), unsafe_allow_html=True)
    if ara:
        st.caption(f"{len(liste)} / {len(cekler)} çek")
    for c in sorted(liste, key=lambda c: str(c.get("vade") or ""), reverse=True)[:200]:
        ct = cek_tutarlari(c)
        durum = c.get("durum") or "Bekliyor"
        renk = "yesil" if ct["odendi"] else ("mavi" if "ciro" in cek_durum_norm(durum) else "amber")
        B.tiklanir(f"geccek{c['id']}",
                   _satir(f"vade {gun_ay_yil(c.get('vade'))}", f"no {_h.escape(str(c.get('cek_no') or '—'))}",
                          _h.escape(c.get("ch_ismi") or "—"),
                          B.meta(B.cip(durum, renk), _h.escape(c.get("banka") or ""),
                                 f"ref {_h.escape(str(c.get('ref_no')))}" if c.get("ref_no") else ""),
                          f"{sym}{tr_sayi(ct['meblag'], 2)}",
                          f"kalan {sym}{tr_sayi(ct['kalan'], 2)}" if ct["kalan"] else "kapandı"),
                   B.detay_ac, ("geccek", c["id"]), tur="satir", renk=renk, etiket="Çek ayrıntısı")
    if not st.session_state.get("salt_okur"):
        with st.expander(f"Tüm {pb} çeklerini sil", icon=":material/delete_sweep:"):
            st.markdown(mesaj("uyari", f"{len(cekler)} {pb} çekinin tamamı silinir; yeni döküm yüklemeden önce "
                                       "temizlemek için."), unsafe_allow_html=True)
            if B.onayli_sil(f"Evet, {len(cekler)} {pb} çekinin tamamını sil", key=f"gec_cek_hepsi_{pb}",
                            dugme=f"Tüm {pb} çeklerini sil"):
                cek_sil_hepsi(pb)
                B.yenile(f"Tüm {pb} çekleri silindi")
    sec = B.detay_istendi("geccek")
    if sec:
        c = next((x for x in cekler if x.get("id") == sec), None)
        if c:
            _cek_dialog(c, sym)


@st.dialog("Çek", width="medium")
def _cek_dialog(c, sym):
    ct = cek_tutarlari(c)
    st.markdown(f'<div style="font-size:18px;font-weight:650">{_h.escape(c.get("ch_ismi") or "—")}</div>'
                f'<div style="font-family:var(--k-mono);font-size:20px;font-weight:600;margin:4px 0 12px">'
                f'{sym}{tr_sayi(ct["meblag"], 2)}</div>', unsafe_allow_html=True)
    for etk, v in (("Çek no", c.get("cek_no")), ("Ref no", c.get("ref_no")), ("Banka", c.get("banka")),
                   ("Vade", gun_ay_yil(c.get("vade"))), ("Durum", c.get("durum") or "Bekliyor"),
                   ("Ödenen", f"{sym}{tr_sayi(ct['odenen'], 2)}"), ("Kalan", f"{sym}{tr_sayi(ct['kalan'], 2)}")):
        st.markdown(f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--k-kenar)">'
                    f'<span style="width:90px;color:var(--k-silik);font-size:12.5px">{etk}</span>'
                    f'<span style="font-size:13px">{_h.escape(str(v or "—"))}</span></div>', unsafe_allow_html=True)
    if st.session_state.get("salt_okur"):
        return
    st.markdown("")
    if B.onayli_sil("Evet, bu çeki sil", key=f"geccek_{c['id']}", dugme="Çeki sil"):
        cek_sil(c["id"])
        B.yenile("Çek silindi")

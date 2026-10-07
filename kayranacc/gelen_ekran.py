# -*- coding: utf-8 -*-
"""Muhasebe › Gelenler Geçmişi (Ekim 2026).

Önce: tek "Tutar" sütunu vardı ve ortak tablo onu döviz ne olursa olsun "$"
ile biçimliyordu — TL tahsilatlar dolar gibi görünüyordu ("$180.446,16").
Şimdi: her giriş kendi para birimiyle; aya göre gruplu; tıklayınca ayrıntı
ve ONAYLI geri alma (tahsilat_geri_al banka bakiyesini de düzeltir).
Ekim 2026: girişi silmeden DÜZENLEME — tutar, banka, kimden, açıklama, tarih
(tahsilat_guncelle; tutar/banka değişirse bakiyeler farkla düzelir).
"""
import html as _h

import streamlit as st

from shared import bilesen as B
from shared.tasarim import kpi_serit, bos_durum, tr_sayi
from .database import get_bankalar, get_tahsilatlar, tahsilat_bakiye_farki, tahsilat_geri_al, tahsilat_guncelle
from .odeme_hesap import AY, GUN_KISA

SEMBOL = {"TL": "₺", "TRY": "₺", "USD": "$", "EUR": "€"}


def _para(v, pb):
    return f"{SEMBOL.get(pb or 'TL', '')}{tr_sayi(float(v or 0), 2)}"


def _ac(tid):
    B.detay_ac("gel", tid)


def _gun(iso):
    from datetime import date
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{d.day} {AY[d.month]}, {GUN_KISA[d.weekday()]}"
    except ValueError:
        return "Tarihsiz"


def render_gelenler():
    B.baslik_eylem("💵 Muhasebe", "Gelenler Geçmişi",
                   aciklama="Kimden, ne kadar, hangi bankaya, ne zaman: tüm para girişleri. "
                            "Yeni giriş: Banka Bakiyeleri → Tahsilat.")
    kayit = get_tahsilatlar(limit=2000) or []
    if not kayit:
        st.markdown(bos_durum("Henüz para girişi yok", "Banka Bakiyeleri sayfasındaki 'Tahsilat' düğmesiyle "
                              "ilk girişi yap.", "payments"), unsafe_allow_html=True)
        return
    c1, c2 = st.columns([3.6, 1.1], vertical_alignment="bottom")
    ara = c1.text_input("Ara", key="gel_ara", placeholder="Kimden, açıklama, banka, tutar…",
                        label_visibility="collapsed")
    kaynaklar = sorted({(t.get("kaynak") or "").strip() for t in kayit if (t.get("kaynak") or "").strip()})
    bankalar = sorted({t.get("hesap_adi") or "—" for t in kayit})
    f = B.filtre(c2, [{"etiket": "Kimden", "secenekler": kaynaklar, "key": "gel_f_kaynak"},
                      {"etiket": "Banka", "secenekler": bankalar, "key": "gel_f_banka"},
                      {"etiket": "Döviz", "secenekler": ["TL", "USD", "EUR"], "key": "gel_f_doviz"}])
    from shared.utils import tr_kucuk
    a = tr_kucuk(ara)
    liste = [t for t in kayit
             if (f["gel_f_kaynak"] == "Tümü" or (t.get("kaynak") or "").strip() == f["gel_f_kaynak"])
             and (f["gel_f_banka"] == "Tümü" or (t.get("hesap_adi") or "—") == f["gel_f_banka"])
             and (f["gel_f_doviz"] == "Tümü" or (t.get("para_birimi") or "TL") == f["gel_f_doviz"])
             and (not a or a in tr_kucuk(f"{t.get('kaynak','')} {t.get('aciklama','')} {t.get('hesap_adi','')} "
                                         f"{t.get('tutar','')}"))]
    top = {pb: sum(float(t.get("tutar") or 0) for t in liste if (t.get("para_birimi") or "TL") == pb)
           for pb in ("TL", "USD", "EUR")}
    kal = [{"etiket": "Gelen TL", "deger": _para(top["TL"], "TL"), "renk": "yesil"},
           {"etiket": "Gelen USD", "deger": _para(top["USD"], "USD"), "renk": "cyan"}]
    if top["EUR"]:
        kal.append({"etiket": "Gelen EUR", "deger": _para(top["EUR"], "EUR"), "renk": "mavi"})
    kal.append({"etiket": "Giriş", "deger": tr_sayi(len(liste)), "renk": "mor",
                "alt": f"{len({(t.get('kaynak') or '').strip() for t in liste})} kaynak"})
    st.markdown(kpi_serit(kal), unsafe_allow_html=True)
    if not liste:
        st.markdown(bos_durum("Filtreye uyan giriş yok", "Aramayı ya da filtreyi değiştir.", "filter_alt_off"),
                    unsafe_allow_html=True)
        return

    # Kimden ne kadar — kısa özet (döviz ayrı ayrı)
    oz = {}
    for t in liste:
        k = (t.get("kaynak") or "—").strip() or "—"
        pb = t.get("para_birimi") or "TL"
        oz.setdefault(k, {}).setdefault(pb, 0.0)
        oz[k][pb] += float(t.get("tutar") or 0)
    sira = sorted(oz.items(), key=lambda kv: -(kv[1].get("TL", 0) + kv[1].get("USD", 0) * 40 + kv[1].get("EUR", 0) * 44))
    st.markdown(B.grup_basligi("Kimden ne kadar", f"{len(oz)} kaynak"), unsafe_allow_html=True)
    st.markdown('<div style="display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;margin:0 2px 6px">' + "".join(
        f'<span><b style="color:var(--k-metin)">{_h.escape(k)}</b> '
        f'<span style="font-family:var(--k-mono);color:var(--k-soluk)">'
        f'{" + ".join(_para(v, pb) for pb, v in d.items() if v)}</span></span>' for k, d in sira[:12])
        + "</div>", unsafe_allow_html=True)

    gruplar = {}
    for t in sorted(liste, key=lambda t: (str(t.get("tarih") or ""), t.get("id") or 0), reverse=True):
        gruplar.setdefault(str(t.get("tarih") or "")[:7], []).append(t)
    limit = int(st.session_state.get("gel_limit", 40))
    n = 0
    for ay, g in gruplar.items():
        if n >= limit:
            break
        try:
            bas = f"{AY[int(ay[5:7])]} {ay[:4]}"
        except (ValueError, IndexError):
            bas = "Tarihsiz"
        toplam = " + ".join(_para(sum(float(t.get('tutar') or 0) for t in g if (t.get('para_birimi') or 'TL') == pb), pb)
                            for pb in ("TL", "USD", "EUR") if any((t.get('para_birimi') or 'TL') == pb for t in g))
        st.markdown(B.grup_basligi(bas, f"{len(g)} giriş · {toplam}"), unsafe_allow_html=True)
        for t in g[:max(0, limit - n)]:
            pb = t.get("para_birimi") or "TL"
            B.tiklanir(f"gel{t['id']}",
                       f'<div style="display:grid;grid-template-columns:110px minmax(0,1fr) auto;gap:4px 16px;align-items:center">'
                       f'<div style="font-size:12.5px;color:var(--k-soluk)">{_gun(t.get("tarih"))}</div>'
                       f'<div style="min-width:0"><div style="font-size:13.5px;font-weight:600;color:var(--k-metin);'
                       f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_h.escape((t.get("kaynak") or "—").strip())}</div>'
                       f'{B.meta(t.get("hesap_adi") or "", (t.get("aciklama") or "").strip())}</div>'
                       f'<div style="text-align:right;white-space:nowrap"><b style="font-family:var(--k-mono);font-size:14px;'
                       f'color:var(--k-yesil)">{_para(t.get("tutar"), pb)}</b>'
                       f'<div style="font-size:11.5px;color:var(--k-silik)">{pb}</div></div></div>',
                       _ac, (t["id"],), tur="satir", renk="yesil", etiket="Giriş ayrıntısı")
            n += 1
    if len(liste) > n:
        if st.button(f"Daha fazla göster ({len(liste) - n} giriş daha)", key="gel_daha", type="tertiary",
                     use_container_width=True):
            st.session_state["gel_limit"] = limit + 40
            st.rerun(scope="fragment")
    sec = B.detay_istendi("gel")
    if sec:
        t = next((x for x in kayit if x.get("id") == sec), None)
        if t:
            _gelen_dialog(t)


@st.dialog("Para girişi", width="medium")
def _gelen_dialog(t):
    pb = t.get("para_birimi") or "TL"
    st.markdown(f'<div style="font-size:18px;font-weight:650">{_h.escape((t.get("kaynak") or "—").strip())}</div>'
                f'<div style="font-family:var(--k-mono);font-size:22px;font-weight:600;color:var(--k-yesil);margin:4px 0 12px">'
                f'{_para(t.get("tutar"), pb)}</div>', unsafe_allow_html=True)
    for etk, v in (("Tarih", str(t.get("tarih") or "")[:10]), ("Banka", t.get("hesap_adi") or "—"),
                   ("Döviz", pb), ("Açıklama", t.get("aciklama") or "—")):
        st.markdown(f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--k-kenar)">'
                    f'<span style="width:90px;color:var(--k-silik);font-size:12.5px">{etk}</span>'
                    f'<span style="font-size:13px">{_h.escape(str(v))}</span></div>', unsafe_allow_html=True)
    if st.session_state.get("salt_okur"):
        return
    st.markdown("")
    with st.expander("Düzenle", icon=":material/edit:"):
        _duzenle(t)
    if B.onayli_sil("Evet, bu girişi geri al", key=f"gel_{t['id']}", dugme="Girişi geri al",
                    aciklama="Kayıt silinir ve tutar banka bakiyesinden düşülür (yanlış girilmiş tahsilat için)."):
        ok, msg = tahsilat_geri_al(t["id"])
        if ok:
            B.yenile(msg)
        else:
            st.error(msg)


def _duzenle(t):
    """Girişi silmeden düzeltir. Banka ya da tutar değişirse bakiye etkisi kaydetmeden önce yazılır."""
    from datetime import date
    tid = t["id"]
    try:
        bankalar = get_bankalar() or []
    except Exception:  # noqa: BLE001
        bankalar = []
    if not bankalar:
        st.caption("Banka listesi okunamadı; düzenleme şu an yapılamıyor.")
        return
    ids = [b["id"] for b in bankalar]
    adlar = {b["id"]: f'{b.get("hesap_adi") or "—"} ({b.get("para_birimi") or "TL"})' for b in bankalar}
    eski_bid = t.get("banka_id")
    bid = st.selectbox("Banka", ids, index=ids.index(eski_bid) if eski_bid in ids else 0,
                       format_func=lambda i: adlar.get(i, str(i)), key=f"gel_d_banka_{tid}")
    pb = next((b.get("para_birimi") or "TL" for b in bankalar if b["id"] == bid), "TL")
    c1, c2 = st.columns(2)
    tutar = c1.number_input(f"Tutar ({pb})", min_value=0.0, step=0.01, format="%.2f",
                            value=float(t.get("tutar") or 0), key=f"gel_d_tutar_{tid}")
    try:
        _t0 = date.fromisoformat(str(t.get("tarih") or "")[:10])
    except ValueError:
        _t0 = date.today()
    tarih = c2.date_input("Tarih", value=_t0, format="DD.MM.YYYY", key=f"gel_d_tarih_{tid}")
    kaynak = st.text_input("Kimden / Kaynak", value=t.get("kaynak") or "", key=f"gel_d_kaynak_{tid}")
    aciklama = st.text_input("Açıklama", value=t.get("aciklama") or "", key=f"gel_d_acik_{tid}")
    fark = tahsilat_bakiye_farki(eski_bid, t.get("tutar"), bid, tutar)
    if fark:
        _pb = {b["id"]: b.get("para_birimi") or "TL" for b in bankalar}
        st.caption("Bakiye etkisi: " + " · ".join(
            f'{adlar.get(k, k)} {"+" if v > 0 else "−"}{_para(abs(v), _pb.get(k))}' for k, v in fark.items()))
    if st.button("Değişiklikleri kaydet", type="primary", icon=":material/save:", key=f"gel_d_kaydet_{tid}",
                 disabled=tutar <= 0, use_container_width=True):
        ok, msg = tahsilat_guncelle(tid, bid, tutar, kaynak.strip(), aciklama.strip(), tarih)
        if ok:
            B.yenile(msg)
        else:
            st.error(msg)

# -*- coding: utf-8 -*-
"""İthalat › Geçmiş İthalatlar — Akış ve Liste görünümleri (Ekim 2026).

  akis()   Yoldaki dosyalar aşama sütunlarında (Üretimde → Yolda → Gümrükte →
           Antrepoda): belge, tedarikçi, tahmini varışa kalan gün, mal bedeli.
           Altında son teslim alınanlar.
  liste()  Bütün dosyalar, sipariş ayına göre gruplu.
Kart / satıra tıklayınca main.py'deki MEVCUT detay penceresi açılır
(masraf, düzenleme, çoklu ürün grubu, teslim, stok — hiçbirine dokunulmadı).

Eskiden sayfa düz bir tabloydu; en önemli bilgi olan AŞAMA sağa taşıp
görünmüyordu, detay için satır kutucuğu seçmek gerekiyordu.
"""
import html as _h
from datetime import date

import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi

AKIS_ASAMALARI = ["Üretimde", "Yolda", "Gümrükte", "Antrepoda"]
ASAMA_RENK = {"Üretimde": "silik", "Yolda": "cyan", "Gümrükte": "amber", "Antrepoda": "mor",
              "Teslim Alındı": "yesil"}
AY = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
      "Ekim", "Kasım", "Aralık"]


def _tarih(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def varis_metni(d, bugun):
    """Tahmini varışa göre kısa metin ve renk: ('12 gün sonra', 'cyan')."""
    t = _tarih(d.get("tahmini_varis"))
    if not t:
        return "varış tarihi yok", "silik"
    g = (t - bugun).days
    if g > 1:
        return f"varış {g} gün sonra", "cyan"
    if g == 1:
        return "varış yarın", "amber"
    if g == 0:
        return "varış bugün", "amber"
    return f"varış {-g} gün gecikti", "kirmizi"


def _para(v):
    return f"${tr_sayi(float(v or 0))}"


def _ac(did):
    B.detay_ac("ith", did)


def akis(dosyalar, hesap_map, bugun=None):
    bugun = bugun or date.today()
    yolda = [d for d in dosyalar if str(d.get("durum") or "").strip() in AKIS_ASAMALARI]
    if not yolda:
        st.caption("Yolda dosya yok. Bütün dosyalar teslim alınmış.")
    else:
        cols = st.columns(len(AKIS_ASAMALARI), gap="small")
        for col, asama in zip(cols, AKIS_ASAMALARI):
            grup = sorted([d for d in yolda if str(d.get("durum")).strip() == asama],
                          key=lambda d: str(d.get("tahmini_varis") or "9999"))
            fob = sum(hesap_map[d["id"]][2]["net_mal_bedeli"] for d in grup)
            with col:
                st.markdown(f'<div style="display:flex;align-items:baseline;gap:8px;margin:2px 2px 8px">'
                            f'<span style="width:8px;height:8px;border-radius:50%;background:var(--k-{ASAMA_RENK[asama]})"></span>'
                            f'<b style="font-size:13.5px">{asama}</b><span style="font-size:12px;color:var(--k-silik)">'
                            f'{len(grup)} · {_para(fob)}</span></div>', unsafe_allow_html=True)
                if not grup:
                    st.markdown('<div style="font-size:12px;color:var(--k-silik);padding:10px 4px;border:1px dashed '
                                'var(--k-kenar);border-radius:10px;text-align:center">boş</div>', unsafe_allow_html=True)
                for d in grup:
                    h = hesap_map[d["id"]][2]
                    vm, vr = varis_metni(d, bugun)
                    B.tiklanir(f"ithak{d['id']}",
                               f'<div style="font-family:var(--k-mono);font-size:12.5px;font-weight:600;color:var(--k-mor2)">'
                               f'{_h.escape(str(d.get("pi_no") or d.get("dosya_no") or "—"))}</div>'
                               f'<div style="font-size:13px;font-weight:600;margin-top:2px;white-space:nowrap;overflow:hidden;'
                               f'text-overflow:ellipsis">{_h.escape(str(d.get("tedarikci") or "—"))}</div>'
                               f'<div style="font-size:12px;color:var(--k-{vr});margin-top:6px">{vm}</div>'
                               f'<div style="display:flex;justify-content:space-between;margin-top:6px;font-size:12px;'
                               f'color:var(--k-silik)"><span>{h["kalem_sayisi"]} kalem</span>'
                               f'<b style="font-family:var(--k-mono);color:var(--k-metin)">{_para(h["net_mal_bedeli"])}</b></div>',
                               _ac, (d["id"],), tur="kart", renk=ASAMA_RENK[asama], etiket="Dosya ayrıntısı")
    teslim = sorted([d for d in dosyalar if str(d.get("durum") or "").strip() == "Teslim Alındı"],
                    key=lambda d: str(d.get("teslim_tarihi") or ""), reverse=True)
    if teslim:
        st.markdown(B.grup_basligi("Son teslim alınanlar", f"{len(teslim)} dosya · tamamı için Liste görünümü"),
                    unsafe_allow_html=True)
        for d in teslim[:6]:
            _satir(d, hesap_map)


def _satir(d, hesap_map):
    h = hesap_map[d["id"]][2]
    asama = str(d.get("durum") or "—").strip()
    depo = (d.get("teslim_deposu") or "").strip()
    uyari = B.cip("depo seçilmedi", "kirmizi") if asama == "Teslim Alındı" and not depo else ""
    masraf = B.cip("masraf girilmedi", "amber") if h["toplam_masraf"] <= 0 else ""
    tarih = str(d.get("teslim_tarihi") or d.get("tarih") or "")[:10]
    tlab = "teslim" if d.get("teslim_tarihi") else "sipariş"
    kalem = f"{h['kalem_sayisi']} kalem"
    B.tiklanir(f"ithls{d['id']}",
               f'<div style="display:grid;grid-template-columns:130px minmax(0,1fr) auto;gap:4px 16px;align-items:center">'
               f'<div><div style="font-family:var(--k-mono);font-size:12.5px;font-weight:600;color:var(--k-mor2)">'
               f'{_h.escape(str(d.get("pi_no") or d.get("dosya_no") or "—"))}</div>'
               f'<div style="font-size:11.5px;color:var(--k-silik)">{tlab} {tarih[8:10]}.{tarih[5:7]}.{tarih[:4]}</div></div>'
               f'<div style="min-width:0"><div style="font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;'
               f'text-overflow:ellipsis">{_h.escape(str(d.get("tedarikci") or "—"))}</div>'
               f'{B.meta(B.cip(asama, ASAMA_RENK.get(asama, "silik")), depo, kalem, uyari, masraf)}</div>'
               f'<div style="text-align:right;white-space:nowrap"><b style="font-family:var(--k-mono);font-size:14px">'
               f'{_para(h["net_mal_bedeli"])}</b><div style="font-size:11.5px;color:var(--k-silik)">masraf %'
               f'{tr_sayi(h["maliyet_yuzde"], 1)}</div></div></div>',
               _ac, (d["id"],), tur="satir", renk=ASAMA_RENK.get(asama, "silik"), etiket="Dosya ayrıntısı")


def liste(dosyalar, hesap_map):
    gruplar = {}
    for d in sorted(dosyalar, key=lambda d: str(d.get("tarih") or ""), reverse=True):
        gruplar.setdefault(str(d.get("tarih") or "")[:7], []).append(d)
    limit = int(st.session_state.get("ith_ls_limit", 40))
    n = 0
    for ay, g in gruplar.items():
        if n >= limit:
            break
        try:
            bas = f"{AY[int(ay[5:7])]} {ay[:4]}"
        except (ValueError, IndexError):
            bas = "Tarihsiz"
        fob = sum(hesap_map[d["id"]][2]["net_mal_bedeli"] for d in g)
        st.markdown(B.grup_basligi(bas, f"{len(g)} dosya · {_para(fob)}"), unsafe_allow_html=True)
        for d in g[:max(0, limit - n)]:
            _satir(d, hesap_map)
            n += 1
    if len(dosyalar) > n:
        if st.button(f"Daha fazla göster ({len(dosyalar) - n} dosya daha)", key="ith_ls_daha", type="tertiary",
                     use_container_width=True):
            st.session_state["ith_ls_limit"] = limit + 40
            st.rerun(scope="fragment")

# -*- coding: utf-8 -*-
"""Teknik Servis — liste ekranları (Ekim 2026).

  kayit_listesi()  Teknik Servis / İade: tıklanır satırlar, gruplu (aktif
                   görünümde SLA kademesine göre, en acil önce).
  depo_listesi()   Depolar: tıklanır satırlar, depo bazında gruplu.
  sec / secili / birak / geri_dugmesi / koru
                   Sayfa İÇİ detay akışı. Detay bir pencere (st.dialog) DEĞİL:
                   kontrol paneli kendi içinden durum, transfer, stok kartı ve
                   silme pencereleri açıyor; Streamlit pencere içinden pencere
                   açtırmaz. Satıra tıklayınca liste yerine detay gelir.

Eskiden liste bir HTML tablosuydu ve kayıt, tablonun altındaki uzun bir seçim
kutusundan seçiliyordu; Depolar her kayıt için düğmeler, açılır menüler ve
(kapalı açılır bölüm içinde bile) PDF üretiyordu.
"""
import html as _h

import streamlit as st

from shared import bilesen as B
from shared.tasarim import tr_sayi

from .database import ARAYUZ_ETIKET, DURUM_RENK
from .ts_hesap import sla_kademe, depo_gruplari

ADIM = 50          # "Daha fazla göster" her basışta

# Satır düzeni: geniş ekranda 3 sütun; telefonda servis no + rozetler üstte,
# ürün bilgisi altta tam genişlikte (3 sütunda orta alan kelime kelime kırılıyordu).
SATIR_CSS = (
    "<style>.ts-sr{display:grid;grid-template-columns:118px minmax(0,1fr) auto;gap:4px 16px;"
    "align-items:center}.ts-orta{min-width:0}.ts-sag{text-align:right;white-space:nowrap}"
    "@media (max-width:640px){.ts-sr{grid-template-columns:minmax(0,1fr) auto}"
    ".ts-sag{order:2}.ts-orta{order:3;grid-column:1 / -1}}</style>")


# ── Sayfa içi detay seçimi ───────────────────────────────────────────
def _anahtar(on_ek):
    return f"_{on_ek}_secili"


def sec(on_ek, kid):
    st.session_state[_anahtar(on_ek)] = kid


def secili(on_ek):
    return st.session_state.get(_anahtar(on_ek))


def birak(on_ek):
    st.session_state.pop(_anahtar(on_ek), None)


def geri_dugmesi(on_ek):
    st.button("Listeye dön", key=f"{on_ek}_geri", icon=":material/arrow_back:", type="tertiary",
              on_click=birak, args=(on_ek,))


def koru(keys):
    """Detay açıkken çizilmeyen filtre kutularının değeri kaybolmasın
    (Streamlit çizilmeyen kutunun durumunu çalışma sonunda siler)."""
    for k in keys:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


# ── Küçük parçalar ───────────────────────────────────────────────────
def _e(v, bos="—"):
    v = "" if v is None else str(v).strip()
    return _h.escape(v) if v else bos


def kisa(v, n):
    """Düz metin kısaltma; kaçışı B.meta yapar (ortak kısaltıcı kaçışlı döndürdüğü
    için burada kullanılırsa metin iki kez kaçırılırdı)."""
    s = str(v or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def gun_metni(v):
    """'2026-09-30T…' → '30.09.2026'."""
    s = str(v or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
    return s[:10] or "—"


def tr_bas(s):
    """Türkçe baş harf büyütme: 'ikinci el' → 'İkinci el' ('Ikinci' değil)."""
    s = str(s or "")
    if not s:
        return s
    ilk = {"i": "İ", "ı": "I"}.get(s[0], s[0].upper())
    return ilk + s[1:]


def durum_cip(durum):
    renk = DURUM_RENK.get(durum, "#94A3B8")
    return (f'<span style="background:{renk}22;border:1px solid {renk}55;color:{renk};border-radius:6px;'
            f'padding:0 8px;font-size:11.5px;font-weight:700;white-space:nowrap">{_e(durum)}</span>')


def _daha_fazla(limit_key, kalan):
    st.button(f"Daha fazla göster ({kalan} kayıt daha)", key=f"{limit_key}_daha", type="tertiary",
              use_container_width=True, on_click=_limit_arttir, args=(limit_key,))


def _limit_arttir(limit_key):
    st.session_state[limit_key] = int(st.session_state.get(limit_key, ADIM)) + ADIM


# ── Teknik Servis / İade listesi ─────────────────────────────────────
def _kayit_satiri(k, gun, bitmis, fatura_var, on_ek):
    _ad, renk, _s = sla_kademe(gun, bitmis)
    sla = "tamamlandı" if bitmis else f"{gun} iş günü"
    sonuc = (k.get("sonuc_durumu") or "").strip() if k.get("mevcut_durum") == "gönderildi" else ""
    meta = B.meta(f'<span style="font-family:var(--k-mono)">{_e(k.get("stok_kodu"))}</span>',
                  f'<span>seri <span style="font-family:var(--k-mono)">{_e(k.get("seri_no"))}</span></span>',
                  kisa(k.get("firma_bilgisi"), 28),
                  kisa(k.get("musteri_adi"), 28),
                  "" if fatura_var else B.cip("fatura yok", "amber"))
    B.tiklanir(
        f"{on_ek}{k['id']}",
        f'<div class="ts-sr">'
        f'<div><div style="font-family:var(--k-mono);font-size:12.5px;font-weight:700;color:var(--k-kirmizi)">'
        f'{_e(k.get("servis_form_no"))}</div>'
        f'<div style="font-size:11.5px;color:var(--k-silik)">kabul {gun_metni(k.get("mal_kabul_tarihi"))}</div></div>'
        f'<div class="ts-orta"><div style="font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;'
        f'text-overflow:ellipsis">{_e(k.get("stok_adi") or k.get("stok_kodu"))}</div>{meta}</div>'
        f'<div class="ts-sag">{durum_cip(k.get("mevcut_durum"))}'
        + (f'<div style="font-size:11.5px;color:var(--k-silik);margin-top:3px">{_e(sonuc)}</div>' if sonuc else "")
        + f'<div style="font-size:12px;font-weight:600;color:var(--k-{renk});margin-top:3px">{sla}</div></div></div>',
        sec, (on_ek, k["id"]), tur="satir", renk=renk, etiket="Kaydı aç")


def kayit_listesi(gruplar, gun_fn, bitmis_fn, fatura_fn, on_ek):
    """gruplar: [(başlık, [kayıt…])]. Satıra tıklayınca sec(on_ek, id)."""
    st.markdown(SATIR_CSS, unsafe_allow_html=True)
    limit_key = f"{on_ek}_limit"
    limit = int(st.session_state.get(limit_key, ADIM))
    toplam = sum(len(g) for _b, g in gruplar)
    n = 0
    for bas, g in gruplar:
        if n >= limit:
            break
        st.markdown(B.grup_basligi(bas, f"{len(g)} kayıt"), unsafe_allow_html=True)
        for k in g[:max(0, limit - n)]:
            _kayit_satiri(k, gun_fn(k), bitmis_fn(k), fatura_fn(k), on_ek)
            n += 1
    if toplam > n:
        _daha_fazla(limit_key, toplam - n)


# ── Depolar listesi ──────────────────────────────────────────────────
_DEPO_DURUM_RENK = {"satışa hazır": "yesil", "satıldı": "mor", "hurda": "kirmizi", "gönderildi": "cyan"}


def _depo_satiri(k, on_ek):
    satildi = k.get("mevcut_durum") == "satıldı"
    sag = ""
    if satildi:
        if k.get("bedelsiz"):
            sag = '<div style="font-size:12px;color:var(--k-silik);margin-top:3px">bedelsiz</div>'
        else:
            try:
                f = float(k.get("satis_fiyati") or 0)
            except (TypeError, ValueError):
                f = 0.0
            if f:
                # "&#36;": düz dolar işareti iki kez geçerse LaTeX sanılıyor
                sag = (f'<div style="font-family:var(--k-mono);font-size:13px;font-weight:700;margin-top:3px">'
                       f'&#36;{tr_sayi(f, 2)}</div>')
    tarih = gun_metni(k.get("depo_tarihi") or k.get("mal_kabul_tarihi"))
    meta = B.meta(f'<span style="font-family:var(--k-mono)">{_e(k.get("stok_kodu"))}</span>',
                  f'<span>seri <span style="font-family:var(--k-mono)">{_e(k.get("seri_no"))}</span></span>',
                  ARAYUZ_ETIKET.get(k.get("arayuz", ""), "evraksız").split(" ", 1)[-1],
                  kisa(k.get("depo_aciklama"), 40))
    B.tiklanir(
        f"{on_ek}{k['id']}",
        f'<div class="ts-sr">'
        f'<div><div style="font-family:var(--k-mono);font-size:12.5px;font-weight:700;color:var(--k-kirmizi)">'
        f'{_e(k.get("servis_form_no"))}</div>'
        f'<div style="font-size:11.5px;color:var(--k-silik)">transfer {tarih}</div></div>'
        f'<div class="ts-orta"><div style="font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;'
        f'text-overflow:ellipsis">{_e(k.get("stok_adi") or k.get("stok_kodu"))}</div>{meta}</div>'
        f'<div class="ts-sag">{durum_cip(k.get("mevcut_durum"))}{sag}</div></div>',
        sec, (on_ek, k["id"]), tur="satir", renk=_DEPO_DURUM_RENK.get(k.get("mevcut_durum"), "silik"),
        etiket="Kaydı aç")


def depo_listesi(kayitlar, depo_sirasi, on_ek):
    st.markdown(SATIR_CSS, unsafe_allow_html=True)
    limit_key = f"{on_ek}_limit"
    limit = int(st.session_state.get(limit_key, ADIM))
    n = 0
    for depo, g in depo_gruplari(kayitlar, depo_sirasi):
        if n >= limit:
            break
        elde = sum(1 for k in g if k.get("mevcut_durum") == "satışa hazır")
        st.markdown(B.grup_basligi(tr_bas(depo), f"{len(g)} ürün · {elde} satışa hazır"),
                    unsafe_allow_html=True)
        for k in g[:max(0, limit - n)]:
            _depo_satiri(k, on_ek)
            n += 1
    if len(kayitlar) > n:
        _daha_fazla(limit_key, len(kayitlar) - n)

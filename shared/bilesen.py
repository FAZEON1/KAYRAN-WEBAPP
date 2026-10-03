# -*- coding: utf-8 -*-
"""KAYRAN — ORTAK EKRAN BİLEŞENLERİ (Ekim 2026, modül yenileme projesi Adım 0)

Kampanya Takip ve Ref No yeniden tasarlanırken aynı kalıplar iki kez yazıldı.
Burada TEK kez tanımlıdır; her yenilenen sayfa bunları kullanır. Stilleri
shared/tasarim.py → ORTAK_BILESEN_CSS içindedir (cekirdek_css ile her sayfada
bir kez basılır; sayfaların ayrıca CSS basması gerekmez).

  tiklanir(...)        Tamamı tıklanan kart / liste satırı / ray öğesi.
                       Görünmez bir düğme kabı kaplar: klavyeyle Tab + Enter de
                       çalışır, odakta kenar çizgisi görünür. tur="kart" | "satir" | "ray"
  baslik_eylem(...)    Sayfa başlığı + sağda 1-3 eylem düğmesi, tek satır.
  filtre(...)          "Filtre · 2" düğmesi + açılır seçim kutuları; etkin filtre sayısı etikette.
  grup_basligi(...)    "Eylül 2026  4 kayıt · ≈ $20.716 ─────" ara başlığı.
  cip(...)             Renkli küçük etiket (durum, kategori, tür).
  onayli_sil(...)      Onay kutusu işaretlenmeden pasif kalan silme düğmesi.
  detay_ac / detay_istendi / yenile
                       Detay penceresini aç-kaydet-yeniden aç akışı:
                       düğmenin on_click'i detay_ac(...) çağırır; sayfanın sonunda
                       detay_istendi(...) değer dönerse pencere açılır; kayıttan
                       sonra yenile(..., ac=...) önbelleği boşaltır, pencereyi
                       yeniden açtırır ve sayfayı yeniler.
"""
import html as _h

import streamlit as st

from shared.tasarim import baslik as _baslik, rv


# ── Tıklanır kap ─────────────────────────────────────────────────────
def tiklanir(anahtar, icerik_html, on_click, args=(), tur="kart", renk=None, secili=False,
             etiket="Aç"):
    """Tamamı tıklanan kap. renk: RENK anahtarı (sol şerit / vurgu, --d).
    anahtar sayfada benzersiz olmalı (ör. f"kmp_{id}")."""
    k = f"tk_{tur}_{anahtar}" + ("__sec" if secili else "")
    css = f"<style>.st-key-{k}{{--d:{rv(renk)};}}</style>" if renk else ""
    with st.container(key=k):
        st.markdown(css + icerik_html, unsafe_allow_html=True)
        st.button(etiket, key=f"tkb_{tur}_{anahtar}", on_click=on_click, args=args)


# ── Başlık + eylemler ───────────────────────────────────────────────
def baslik_eylem(modul, sayfa, aciklama="", eylemler=()):
    """eylemler: [{"etiket","key","icon"?,"birincil"?,"help"?,"disabled"?}]
    Döner: {key: tıklandı_mı}. Düğmeler başlığın sağında, aynı satırda."""
    n = len(eylemler)
    gen = 1.45 if n > 3 else 1.3          # 4 eylemde etiketler kesilmesin
    oran = [max(3.6, 5.2 - 0.4 * max(0, n - 2))] + [gen] * n
    kol = st.columns(oran, vertical_alignment="center")
    kol[0].markdown(_baslik(modul, sayfa, aciklama=aciklama), unsafe_allow_html=True)
    out = {}
    for c, e in zip(kol[1:], eylemler):
        out[e["key"]] = c.button(e["etiket"], key=e["key"], icon=e.get("icon"), help=e.get("help"),
                                 type="primary" if e.get("birincil") else "secondary",
                                 disabled=bool(e.get("disabled")), use_container_width=True)
    return out


# ── Filtre düğmesi ──────────────────────────────────────────────────
def filtre(kap, alanlar, tumu="Tümü"):
    """kap: st.columns sütunu ya da st. alanlar: [{"etiket","secenekler","key","format_func"?}]
    Her alanın ilk seçeneği 'Tümü'. Döner: {key: seçilen}."""
    n = sum(1 for a in alanlar if st.session_state.get(a["key"], tumu) != tumu)
    out = {}
    with kap.popover(f"Filtre{f' · {n}' if n else ''}", icon=":material/tune:", use_container_width=True):
        for a in alanlar:
            out[a["key"]] = st.selectbox(a["etiket"], [tumu] + list(a["secenekler"]), key=a["key"],
                                         format_func=a.get("format_func") or (lambda x: x))
        if n:
            st.button("Filtreleri temizle", key=f"{alanlar[0]['key']}__temizle", type="tertiary",
                      on_click=_filtre_temizle, args=([a["key"] for a in alanlar], tumu))
    return out


def _filtre_temizle(keys, tumu):
    for k in keys:
        st.session_state[k] = tumu


# ── Küçük HTML parçaları ────────────────────────────────────────────
def grup_basligi(baslik, ozet=""):
    o = f"<span>{_h.escape(str(ozet))}</span>" if ozet else ""
    ik = ""
    try:                                   # baştaki emoji → çizgi ikon (shared/ikon.py, IKON_YENI)
        from shared.tasarim import IKON_YENI, ikon_html
        if IKON_YENI:
            from shared.ikon import bas_emoji
            ad, kalan = bas_emoji(str(baslik))
            if kalan is not baslik and kalan != str(baslik):
                baslik = kalan
                ik = ikon_html(ad, 16) + " " if ad else ""
    except Exception:  # noqa: BLE001
        pass
    return f'<div class="k-grup"><b>{ik}{_h.escape(str(baslik))}</b>{o}<i></i></div>'


def cip(metin, renk="mor2", title=""):
    if not metin:
        return ""
    t = f' title="{_h.escape(str(title), quote=True)}"' if title else ""
    return f'<span class="k-cip" style="--d:{rv(renk)}"{t}>{_h.escape(str(metin))}</span>'


def meta(*parcalar):
    """'a · b · c' — boş parçalar atlanır; ayraçları CSS çizer."""
    ic = "".join(p if str(p).startswith("<span") else f"<span>{_h.escape(str(p))}</span>"
                 for p in parcalar if p)
    return f'<div class="k-meta">{ic}</div>'


# ── Onaylı silme ────────────────────────────────────────────────────
def onayli_sil(onay_metni, key, dugme="Sil", aciklama=""):
    """Onay kutusu işaretlenmeden pasif silme düğmesi. Döner: tıklandı_mı.
    key'de '_sil' geçtiği için düğme kırmızı çizilir (DUGME_CSS)."""
    if aciklama:
        st.caption(aciklama)
    onay = st.checkbox(onay_metni, key=f"{key}_onay")
    return st.button(dugme, key=f"{key}_sil", icon=":material/delete:", disabled=not onay)


# ── Detay penceresi akışı ───────────────────────────────────────────
def detay_ac(on_ek, deger):
    """on_click için: detay penceresinin açılmasını ister."""
    st.session_state[f"_{on_ek}_sec"] = deger
    st.session_state[f"_{on_ek}_ac"] = True


def detay_istendi(on_ek):
    """Sayfanın sonunda: pencere istendiyse seçili değeri döner (bir kez)."""
    if st.session_state.pop(f"_{on_ek}_ac", False):
        return st.session_state.get(f"_{on_ek}_sec")
    return None


def yenile(toast=None, ac=None):
    """Kayıttan sonra: önbellek boşalır, (istenirse) pencere yeniden açılır,
    sayfa yenilenir. ac=(on_ek, deger)."""
    st.cache_data.clear()
    if toast:
        st.toast(toast)
    if ac:
        detay_ac(*ac)
    st.rerun()


# ── Sayfa içi detay (pencere DEĞİL) ─────────────────────────────────
# Detayın içinden başka pencere açılıyorsa detay pencere olamaz (Streamlit
# pencere içinden pencere açtırmaz). Satıra tıklayınca liste yerine detay
# çizilir; "Listeye dön" geri getirir. Örnek: teknikservis, kayranpm Tüm Ürünler.
def sec(on_ek, deger):
    """on_click için: detayı açar."""
    st.session_state[f"_{on_ek}_secili"] = deger


def secili(on_ek):
    return st.session_state.get(f"_{on_ek}_secili")


def birak(on_ek):
    st.session_state.pop(f"_{on_ek}_secili", None)


def listeye_don(on_ek):
    st.button("Listeye dön", key=f"{on_ek}_geri", icon=":material/arrow_back:", type="tertiary",
              on_click=birak, args=(on_ek,))


def kapat(on_ek):
    """Yan yana düzende detayı kapatır (geniş ekranda; dar ekranda "Listeye dön" görünür)."""
    st.button("Kapat", key=f"{on_ek}_kapat", icon=":material/close:", type="tertiary",
              on_click=birak, args=(on_ek,))


def yan_yana_css(on_ek, liste_key=None):
    """Liste ve detay yan yana (shared.tasarim.YAN_YANA): 900 px altında sol liste gizlenir,
    "Kapat" yerine "Listeye dön" görünür — sunucu ekran genişliğini bilmediği için ikisi de
    çizilir, hangisinin görüneceğine CSS karar verir."""
    sol = liste_key or f"{on_ek}_liste_sol"
    return (f"<style>.st-key-{on_ek}_geri{{display:none !important}}"
            f"@media (max-width:900px){{[data-testid=\"stColumn\"]:has(.st-key-{sol}),.st-key-{sol}"
            f"{{display:none !important}}.st-key-{on_ek}_kapat{{display:none !important}}"
            f".st-key-{on_ek}_geri{{display:block !important}}}}</style>")


def koru(keys):
    """Detay açıkken: çizilmeyen filtre kutularının değerini gölge anahtara kopyalar.
    Listeye dönünce geri_yukle() kutular oluşmadan ÖNCE geri yazar.
    (Değeri kendi anahtarına yeniden atama hilesi 1.64'te değeri oturumda tutuyor
    ama yeniden çizilen kutu BOŞ görünüyordu — tarayıcıda görüldü.)"""
    for k in keys:
        if k in st.session_state:
            st.session_state[f"_koru_{k}"] = st.session_state[k]


def geri_yukle(keys):
    """Liste çizilmeden önce çağır: koru() ile saklanan değerleri kutulara geri yazar."""
    for k in keys:
        if f"_koru_{k}" in st.session_state:
            st.session_state[k] = st.session_state.pop(f"_koru_{k}")

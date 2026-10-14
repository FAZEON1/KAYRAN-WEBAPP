# -*- coding: utf-8 -*-
"""Emoji → çizgi ikon: merkezi katman (Ekim 2026), 1. adım.

Streamlit'in mesaj (success/info/warning/error/toast), pencere (dialog), sekme
(tabs), açılır bölüm (expander) ve düğme çağrıları sarılır: etiketin BAŞINDAKİ
emoji Material ikona çevrilir (shared.tasarim.EMOJI_IKON), tanınmazsa atılır.

Dokunulmayanlar: markdown/HTML metinleri (2. adım, ekran ekran), seçim seçenekleri
(değerleri kodda karşılaştırılıyor) ve anahtarsız onay kutusu/anahtar: onların
kimliği etiketten türetilir, etiket değişirse tuttukları değer sıfırlanırdı.
Düğmeler durumsuzdur; etiket değişince kimliğin değişmesi zararsız.

Geri alma: shared/tasarim.py → IKON_YENI = False.
"""
import re
from shared.kayit import sessiz

# Resimli emoji aralıkları. Oklar (→ ←), ✓ ✗ • gibi tipografik işaretler HARİÇ.
_EMO = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u2139\u24C2\u21A9\u21AA]")
_TIPO = set("✓✗✕✖✔︎•●○■□▲▼◆◇★☆")
_EK = "\ufe0f\u200d\u20e3"
# Durum noktaları rengiyle anlam taşır (acil talep, aktif/kapalı) → dokunulmaz
_DURUM = set("🔴🟠🟡🟢🔵🟣⚪⚫🟤")

_MESAJ_IKON = {"success": "check_circle", "info": "info", "warning": "warning", "error": "error"}


def _emoji_mi(c):
    return bool(_EMO.match(c)) and c not in _TIPO


def bas_emoji(metin):
    """('ikon adı' | None, kalan) — yalnız metin GERÇEK bir emojiyle başlıyorsa.
    Emoji yoksa (None, metin) — metin olduğu gibi döner (markdown, ok, sayı…)."""
    if not isinstance(metin, str) or not metin:
        return None, metin
    s = metin.lstrip()
    if not s or not _emoji_mi(s[0]) or s[0] in _DURUM:
        return None, metin
    i = 0
    while i < len(s) and (_emoji_mi(s[i]) or s[i] in _EK):
        i += 1
    bas = s[:i]
    ilk = bas[0]
    from shared.tasarim import EMOJI_IKON
    ad = EMOJI_IKON.get(bas.replace("\ufe0f", "").replace("\u200d", "")) or EMOJI_IKON.get(ilk)
    return ad, s[i:].strip()


def _ikon_param(icon):
    """icon= emoji verilmişse Material'a çevir; Material/None aynen."""
    if not icon or not isinstance(icon, str) or icon.startswith(":material/"):
        return icon
    ad, _ = bas_emoji(icon)
    return f":material/{ad}:" if ad else icon


# Metnin İÇİNDEKİ emoji (2. adım, Ekim 2026): ardından gelen tek boşlukla birlikte atılır ("**📦 Ürünler**" →
# "**Ürünler**"; boşluk kalsaydı kalın yazı bozulurdu). Durum noktaları ve tipografik işaretler kalır.
_IC = re.compile("(?:" + _EMO.pattern + "[" + _EK + "]*)+ ?")       # _EMO ile aynı aralıklar


def ic_temizle(metin):
    """Metindeki resimli emojileri atar (durum noktaları 🔴🟢…, ✓ ✗ • ▲ gibi işaretler kalır).
    Emoji yoksa metnin kendisi döner (hızlı yol)."""
    if not isinstance(metin, str) or not _EMO.search(metin):
        return metin

    def _at(m):
        parca = m.group(0)
        kalan = "".join(c for c in parca if c in _DURUM or c in _TIPO)
        return (kalan + " ") if kalan and parca.endswith(" ") else kalan
    return _IC.sub(_at, metin)


def metin(govde, html=False):
    """st.markdown / st.caption gövdesi: düz markdown'da baştaki emoji Material ikona çevrilir
    (':material/x:' markdown'da çalışır), HTML'de yalnız atılır; içerdeki emojiler atılır."""
    if not isinstance(govde, str) or not _EMO.search(govde):
        return govde
    if not html:
        ad, kalan = bas_emoji(govde)
        if ad and kalan is not govde:
            return f":material/{ad}: {ic_temizle(kalan)}"
    return ic_temizle(govde)


def mesaj(tur, govde, icon):
    """st.success/info/warning/error: baştaki emoji atılır; ikon kutu türünden."""
    _, kalan = bas_emoji(govde)
    return ic_temizle(kalan), (_ikon_param(icon) if icon else f":material/{_MESAJ_IKON[tur]}:")


def toast(govde, icon):
    ad, kalan = bas_emoji(govde)
    kalan = ic_temizle(kalan)
    if icon:
        return kalan, _ikon_param(icon)
    return kalan, (f":material/{ad}:" if ad else None)


def etiket(metin, icon):
    """Düğme / açılır bölüm: (etiket, icon=)."""
    ad, kalan = bas_emoji(metin)
    if icon:
        return kalan, _ikon_param(icon)
    return kalan, (f":material/{ad}:" if ad else None)


def acilir(metin, icon):
    """Açılır bölüm: emoji yalnız atılır. Streamlit 1.64'te icon= açma okunun yerine
    geçiyor (bölümün açılabildiği belli olmuyordu) → ikon verilmez."""
    return bas_emoji(metin)[1], icon


def sekme(metin):
    """Sekme etiketi markdown destekler: ':material/x: Ad'."""
    ad, kalan = bas_emoji(metin)
    if kalan is metin:
        return metin
    return f":material/{ad}: {kalan}" if ad else kalan


def durumlu(metin, key):
    """Onay kutusu / anahtar: yalnız sabit anahtarı varsa etiket sadeleşir."""
    if not key:
        return metin, None
    return bas_emoji(metin)[1], None


# ── Kurulum (app.py) ────────────────────────────────────────────────
def kur(st):
    """Streamlit çağrılarını sarar. Hata olursa sessizce eski davranışta kalır
    (bu katman yalnız görünüm; çalışmayı asla durdurmamalı)."""
    try:
        from shared.tasarim import IKON_YENI
        if not IKON_YENI:
            return
        from streamlit.delta_generator import DeltaGenerator as DG
        if not getattr(DG.success, "_kayran_ikon", False):
            _sar_sinif(DG)
        if not getattr(DG.markdown, "_kayran_ikon2", False):
            _sar_metin(DG)
        kok = None
        for ad in ("success", "info", "warning", "error", "expander", "tabs", "button",
                   "download_button", "popover", "link_button", "checkbox", "toggle", "form_submit_button",
                   "markdown", "caption", "title", "header", "subheader") + _ETIKETLI:
            f = getattr(st, ad, None)
            kok = kok or getattr(f, "__self__", None)
            if kok is not None and getattr(f, "__self__", None) is kok:
                setattr(st, ad, getattr(DG, ad).__get__(kok, DG))
        if not getattr(st.toast, "_kayran_ikon", False):
            st.toast = _sar_toast(st.toast)
        if not getattr(st.dialog, "_kayran_ikon", False):
            st.dialog = _sar_dialog(st.dialog)
    except Exception as _e:  # noqa: BLE001
        sessiz("shared.ikon.kur", _e)


def _isaretle(f):
    f._kayran_ikon = True
    return f


def _sar_sinif(DG):
    for tur in ("success", "info", "warning", "error"):
        def _yap(tur, orij):
            def f(self, body, *a, icon=None, **kw):
                try:
                    body, icon = mesaj(tur, body, icon)
                except Exception as _e:  # noqa: BLE001
                    sessiz("shared.ikon._sar_sinif._yap.f", _e, "debug")
                return orij(self, body, *a, icon=icon, **kw)
            return _isaretle(f)
        setattr(DG, tur, _yap(tur, getattr(DG, tur)))

    orij_exp = DG.expander

    def expander(self, label, *a, **kw):
        try:
            label, _ = acilir(label, None)
        except Exception as _e:  # noqa: BLE001
            sessiz("shared.ikon._sar_sinif.expander", _e, "debug")
        return orij_exp(self, label, *a, **kw)
    DG.expander = _isaretle(expander)

    for ad in ("button", "download_button", "popover", "link_button", "form_submit_button"):
        orij = getattr(DG, ad, None)
        if orij is None:
            continue

        def _yap(orij):
            def f(self, label, *a, icon=None, **kw):
                try:
                    label, icon = etiket(label, icon)
                except Exception as _e:  # noqa: BLE001
                    sessiz("shared.ikon._sar_sinif._yap.f", _e, "debug")
                return orij(self, label, *a, icon=icon, **kw) if icon else orij(self, label, *a, **kw)
            return _isaretle(f)
        setattr(DG, ad, _yap(orij))

    for ad, kpos in (("checkbox", 1), ("toggle", 1)):
        orij = getattr(DG, ad)

        def _yap(orij, kpos):
            def f(self, label, *a, **kw):
                try:
                    key = kw.get("key") or (a[kpos] if len(a) > kpos else None)
                    label, _ = durumlu(label, key)
                except Exception as _e:  # noqa: BLE001
                    sessiz("shared.ikon._sar_sinif._yap.f", _e, "debug")
                return orij(self, label, *a, **kw)
            return _isaretle(f)
        setattr(DG, ad, _yap(orij, kpos))

    orij_tabs = DG.tabs

    def tabs(self, tabs, *a, **kw):
        try:
            tabs = [sekme(t) for t in tabs]
        except Exception as _e:  # noqa: BLE001
            sessiz("shared.ikon._sar_sinif.tabs", _e, "debug")
        return orij_tabs(self, tabs, *a, **kw)
    DG.tabs = _isaretle(tabs)


def _sar_toast(orij):
    def f(body, *a, icon=None, **kw):
        try:
            body, icon = toast(body, icon)
        except Exception as _e:  # noqa: BLE001
            sessiz("shared.ikon._sar_toast.f", _e, "debug")
        return orij(body, *a, icon=icon, **kw)
    return _isaretle(f)


def _sar_dialog(orij):
    def f(title="", *a, **kw):
        try:
            if isinstance(title, str):
                title = bas_emoji(title)[1] or title
        except Exception as _e:  # noqa: BLE001
            sessiz("shared.ikon._sar_dialog.f", _e, "debug")
        return orij(title, *a, **kw)
    return _isaretle(f)


# ── 2. adım (Ekim 2026): metinler ve kutu etiketleri ────────────────
# Seçim / yazı kutularının ETİKETİ (seçenekleri değil: değerleri kodda karşılaştırılıyor). Yalnız sabit
# anahtarı olan kutuda: anahtarsız kutunun kimliği etiketten türetilir (etiket değişince değeri sıfırlanırdı).
_ETIKETLI = ("selectbox", "multiselect", "radio", "text_input", "text_area", "number_input", "date_input",
             "time_input", "file_uploader", "slider", "select_slider", "color_picker", "segmented_control", "pills")


def _isaretle2(f):
    f._kayran_ikon2 = True
    return f


def _sar_metin(DG):
    for ad in ("markdown", "caption"):
        orij = getattr(DG, ad)

        def _yap(orij):
            def f(self, body, *a, **kw):
                try:
                    body = metin(body, html=bool(kw.get("unsafe_allow_html")))
                except Exception as _e:  # noqa: BLE001
                    sessiz("shared.ikon._sar_metin._yap.f", _e, "debug")
                return orij(self, body, *a, **kw)
            return _isaretle2(f)
        setattr(DG, ad, _yap(orij))
    for ad in ("title", "header", "subheader"):
        orij = getattr(DG, ad, None)
        if orij is None:
            continue

        def _yap(orij):
            def f(self, body, *a, **kw):
                try:
                    body = metin(body)
                except Exception as _e:  # noqa: BLE001
                    sessiz("shared.ikon._sar_metin._yap.f", _e, "debug")
                return orij(self, body, *a, **kw)
            return _isaretle2(f)
        setattr(DG, ad, _yap(orij))
    for ad in _ETIKETLI:
        orij = getattr(DG, ad, None)
        if orij is None:
            continue

        def _yap(orij):
            def f(self, label, *a, **kw):
                try:
                    if kw.get("key") and isinstance(label, str):
                        label = ic_temizle(bas_emoji(label)[1])
                except Exception as _e:  # noqa: BLE001
                    sessiz("shared.ikon._sar_metin._yap.f", _e, "debug")
                return orij(self, label, *a, **kw)
            return _isaretle2(f)
        setattr(DG, ad, _yap(orij))

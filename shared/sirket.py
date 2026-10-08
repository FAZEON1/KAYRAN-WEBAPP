"""Şirket (gönderen) künyesi — yazdırılan belgelerin başlığında kullanılır.

Künye kişi menüsü › Şirket belgeleri ekranından girilir (Ekim 2026). Değerler Streamlit Secrets'tan da
verilebilir (ekranda kaydedilen kazanır):

    [sirket]
    unvan = "KAYRAN ... A.Ş."
    adres = "..."

Secrets'ta karşılığı varsa o kazanır; yoksa aşağıdaki varsayılan kullanılır.
"""

_VARSAYILAN = {
    "unvan":  "KAYRAN ELEKTRONİK",          # ← resmî ticari unvan
    "marka":  "FAZEON",                     # ← belge başlığında görünen marka
    "adres":  "",                           # ← tam adres (mahalle/cadde/no/ilçe/il)
    "vd":     "",                           # ← vergi dairesi
    "vkn":    "",                           # ← vergi kimlik / TC no
    "mersis": "",
    "tel":    "",
    "mail":   "",
}


def sirket_bilgi():
    """Şirket künyesi (dict). Öncelik (Ekim 2026): Şirket belgeleri ekranında kaydedilen >
    secrets > yukarıdaki varsayılan. Boş alan bir alttakini ezmez."""
    from shared.sirket_belge_hesap import kunye_birlestir
    _s, _k = {}, {}
    try:
        import streamlit as st
        _s = {k: v for k, v in (st.secrets.get("sirket", {}) or {}).items() if k in _VARSAYILAN}
    except Exception:
        pass
    try:
        from shared.sirket_belge import kunye_oku
        _k = kunye_oku()
    except Exception:
        pass
    return kunye_birlestir(_VARSAYILAN, _s, _k)

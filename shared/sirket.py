"""Şirket (gönderen) künyesi — yazdırılan belgelerin başlığında kullanılır.

⚠️ BURAYI BİR KEZ DOLDURUN. Değerler Streamlit Secrets'tan da ezilebilir:

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
    """Secrets ile birleştirilmiş şirket künyesi (dict)."""
    bilgi = dict(_VARSAYILAN)
    try:
        import streamlit as st
        _s = st.secrets.get("sirket", {}) or {}
        for k in bilgi:
            if str(_s.get(k, "") or "").strip():
                bilgi[k] = str(_s[k]).strip()
    except Exception:
        pass
    return bilgi

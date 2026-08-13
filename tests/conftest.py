# -*- coding: utf-8 -*-
"""
Test ortamı kurulumu.

AMAÇ: Test edilen fonksiyonlar SAF (veritabanına gitmiyor) ama içinde
bulundukları modüller `import streamlit` / `from supabase import ...`
yapıyor. Sırf modül içe aktarılabilsin diye CI'ya streamlit + supabase
kurmak hem yavaş hem gereksiz.

ÇÖZÜM: Gerçek paket yoksa yerine iş görecek kadar sahtesini koyuyoruz.
Gerçek paket KURULUYSA ona dokunmuyoruz — yani yerelde tam kurulumla da,
CI'da yalnız `pytest` + `pandas` ile de aynı testler koşar.

DİKKAT: Sahte streamlit yalnız İÇE AKTARMAYI mümkün kılar. Veritabanına
giden bir fonksiyonu test etmeye kalkarsan sahte istemci sessizce boş
veri döndürür ve test yanlış yeşil olur. Bu yüzden buradaki testler
yalnız saf fonksiyonlara dokunur; DB'ye giden fonksiyonlar için
monkeypatch ile açıkça sahte veri verilir (bkz. test dosyalarındaki
`_sahte_rows`).
"""

import sys
import types
from pathlib import Path

# Repo kökü import yoluna girsin (tests/ alt klasöründen çalıştırılıyor)
KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))


def _sahte_streamlit():
    """streamlit'in yalnız içe aktarma sırasında kullanılan yüzeyi."""
    st = types.ModuleType("streamlit")

    def _bezeme(*a, **kw):
        """@st.cache_data ve @st.cache_data(ttl=300) — iki kullanımı da destekler."""
        # @st.cache_data  (parantezsiz) → tek argüman: fonksiyonun kendisi
        if len(a) == 1 and not kw and callable(a[0]):
            fn = a[0]
            fn.clear = lambda *_a, **_k: None   # get_client.clear() çağrılıyor
            return fn

        # @st.cache_data(ttl=..., show_spinner=...) → dekoratör döndür
        def sar(fn):
            fn.clear = lambda *_a, **_k: None
            return fn
        return sar

    st.cache_data = _bezeme
    st.cache_resource = _bezeme
    # @st.dialog("başlık") ve @st.fragment — modül düzeyinde kullanılıyor
    st.dialog = lambda *a, **kw: (lambda fn: fn)
    st.fragment = _bezeme

    class _Secrets(dict):
        def __getitem__(self, k):
            raise KeyError(
                "Testte st.secrets okunmaya çalışıldı — bu fonksiyon SAF DEĞİL, "
                "veritabanına gidiyor. Testi monkeypatch ile kur."
            )

    st.secrets = _Secrets()
    st.session_state = {}

    # Arayüz çağrıları testte sessizce yutulsun (modül düzeyinde çağrılırsa)
    def _yut(*a, **kw):
        return None

    for ad in ("write", "error", "warning", "info", "success", "caption",
               "markdown", "html", "dataframe", "cache_data_clear", "stop",
               "rerun", "toast", "spinner", "empty", "container"):
        setattr(st, ad, _yut)

    return st


def _sahte_supabase():
    sb = types.ModuleType("supabase")

    class Client:  # yalnız tip ipucu için
        pass

    def create_client(*a, **kw):
        raise RuntimeError(
            "Testte gerçek Supabase istemcisi kurulmaya çalışıldı. "
            "Bu fonksiyon saf değil; testi monkeypatch ile kur."
        )

    sb.Client = Client
    sb.create_client = create_client
    return sb


try:
    import streamlit  # noqa: F401
except ModuleNotFoundError:
    sys.modules["streamlit"] = _sahte_streamlit()

try:
    import supabase  # noqa: F401
except ModuleNotFoundError:
    sys.modules["supabase"] = _sahte_supabase()

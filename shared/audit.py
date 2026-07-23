# -*- coding: utf-8 -*-
"""Merkezi değişiklik günlüğü (audit log).

wrap_client(real, modul): Supabase bağlantısını saran proxy döndürür. Bu proxy
tüm insert/update/delete/upsert işlemlerini otomatik 'audit_log' tablosuna yazar.
Böylece her modülün get_client'ine tek satır eklenir, 60 fonksiyona dokunulmaz.

log_yaz: SARMALANMAMIŞ ham bağlantı kullanır → audit_log yazımı tekrar loglanmaz
(sonsuz döngü olmaz). Ayrıca proxy, tablo 'audit_log' ise loglamayı atlar.
Tüm loglama hataları sessizce yutulur; ana iş akışı ASLA bozulmaz."""
from datetime import datetime, timedelta



def _st_cache_resource_guvenli(fn):
    """st.cache_resource varsa uygular; streamlit dışı bağlamda (gece yedek) sade bellek cache."""
    try:
        import streamlit as _st
        return _st.cache_resource(show_spinner=False)(fn)
    except Exception:
        _c = {}
        def _sarici(*a, **k):
            if "v" not in _c:
                _c["v"] = fn(*a, **k)
            return _c["v"]
        return _sarici

def _tr_now():
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")


@_st_cache_resource_guvenli
def _raw_client():
    """Sarmalanmamış ham Supabase bağlantısı (yalnız audit_log yaz/oku için)."""
    import streamlit as st
    from supabase import create_client
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"].get("key")
    return create_client(url, key)


def _aktif_kullanici():
    try:
        import streamlit as st
        return st.session_state.get("aktif_kullanici") or "?"
    except Exception:
        return "?"


# ── SALT-OKUR (read-only) KORUMASI ───────────────────────────────────
# Oturum 'salt_okur' işaretliyse, sarmalanmış bağlantı üzerinden yapılan
# TÜM insert/update/upsert/delete çağrıları burada durdurulur. Tek nokta:
# her modülün get_client'i wrap_client'ten geçtiği için ek koda gerek yok.
class SaltOkurHatasi(Exception):
    """Salt-okur kullanıcı yazma denemesi yaptı."""


def salt_okur_mu():
    try:
        import streamlit as st
        return bool(st.session_state.get("salt_okur"))
    except Exception:
        return False


def _salt_okur_engelle(islem, tablo):
    """Yazma işlemini durdurur; ekrana da uyarı basar (çağıran hatayı yutsa bile
    kullanıcı 'kaydedildi' sanmasın diye)."""
    _msg = (f"🔒 Salt-okur hesap — '{tablo}' tablosunda **{islem}** işlemi yapılamaz. "
            "Bu hesap tüm modülleri görüntüleyebilir, veri değiştiremez.")
    try:
        import streamlit as st
        st.error(_msg)
    except Exception:
        pass
    raise SaltOkurHatasi(_msg)


def log_yaz(islem, tablo, kayit_id="", detay="", modul=""):
    """Tek bir değişiklik kaydı yazar. Hata olsa bile sessiz."""
    try:
        _raw_client().table("audit_log").insert({
            "zaman": _tr_now(),
            "kullanici": _aktif_kullanici(),
            "modul": modul or "",
            "islem": islem or "",
            "tablo": tablo or "",
            "kayit_id": str(kayit_id or ""),
            "detay": (detay or "")[:400],
        }).execute()
    except Exception:
        pass


def _detay_yap(payload):
    try:
        if isinstance(payload, dict):
            parts = []
            for k, v in list(payload.items())[:5]:
                sv = str(v)
                if len(sv) > 40:
                    sv = sv[:40] + "…"
                parts.append(f"{k}={sv}")
            return ", ".join(parts)
        if isinstance(payload, list):
            return f"{len(payload)} kayıt"
    except Exception:
        pass
    return ""


def _kayit_id(filtre, res):
    if filtre.get("id") not in (None, ""):
        return filtre["id"]
    try:
        data = getattr(res, "data", None)
        if data and isinstance(data, list) and isinstance(data[0], dict):
            return data[0].get("id", "")
    except Exception:
        pass
    return ""


class _LoggingTable:
    """Supabase query builder sarmalayıcısı. insert/update/delete/upsert/eq yakalanır;
    diğer tüm metotlar (select, order, neq, gt, in_, single, ...) gerçek builder'a delege."""

    def __init__(self, real, tablo, modul, yeniden=None):
        self._b = real
        self._tablo = tablo
        self._modul = modul
        self._islem = None
        self._payload = None
        self._filtre = {}
        # Oto-sayfalama takibi: select çağrıldı mı, satır sınırı kondu mu?
        self._select_var = False
        self._sinir_var = False
        # PARALEL sayfalama için: sorgu zinciri kaydı + taze builder fabrikası.
        # Zincir, aynı sorguyu yeni bir builder üzerinde yeniden kurmayı sağlar;
        # böylece sayfalar AYNI ANDA (dalga halinde) çekilebilir.
        self._yeniden = yeniden
        self._zincir = []

    def insert(self, data, *a, **k):
        self._islem = "ekle"
        self._payload = data
        self._b = self._b.insert(data, *a, **k)
        return self

    def update(self, data, *a, **k):
        self._islem = "güncelle"
        self._payload = data
        self._b = self._b.update(data, *a, **k)
        return self

    def upsert(self, data, *a, **k):
        self._islem = "ekle/güncelle"
        self._payload = data
        self._b = self._b.upsert(data, *a, **k)
        return self

    def delete(self, *a, **k):
        self._islem = "sil"
        self._b = self._b.delete(*a, **k)
        return self

    def eq(self, col, val):
        self._filtre[col] = val
        self._b = self._b.eq(col, val)
        return self

    def execute(self, *a, **k):
        # SALT-OKUR: yazma işlemi Supabase'e HİÇ gitmeden burada durur.
        if self._islem and salt_okur_mu():
            _salt_okur_engelle(self._islem, self._tablo)
        res = self._b.execute(*a, **k)
        if self._islem and self._tablo != "audit_log":
            try:
                log_yaz(self._islem, self._tablo, _kayit_id(self._filtre, res),
                        _detay_yap(self._payload), self._modul)
            except Exception:
                pass
        # ── OTO-SAYFALAMA (PARALEL) ──────────────────────────────────────
        # Supabase tek sorguda en fazla 1000 satır döndürür. Elle .range()
        # yazılmamış select'ler tam 1000 dönerse kesilmiş demektir; kalan
        # sayfalar burada tamamlanır. HIZ: sayfalar teker teker değil,
        # 8'erli DALGALAR halinde AYNI ANDA çekilir (sorgu zinciri taze
        # builder'lar üzerinde yeniden kurulur). 100 sayfalık tablo ~100
        # ardışık istek yerine ~13 paralel dalgada iner (≈8 kat hızlı).
        try:
            if (self._islem is None and self._select_var and not self._sinir_var
                    and self._tablo != "audit_log"):
                _data = getattr(res, "data", None)
                if isinstance(_data, list) and len(_data) == 1000:
                    _tum = list(_data)
                    if self._yeniden is not None:
                        # PARALEL yol: zinciri taze builder'da yeniden kur
                        from concurrent.futures import ThreadPoolExecutor

                        def _sayfa(_ab):
                            _a0, _b0 = _ab
                            try:
                                _nb = self._yeniden()
                                for _nm, _aa, _kk in self._zincir:
                                    _nb = getattr(_nb, _nm)(*_aa, **_kk)
                                return getattr(_nb.range(_a0, _b0).execute(),
                                               "data", None) or []
                            except Exception:
                                return None          # hata → ardışık yola düş
                        _bas, _dalga, _hata = 1000, 8, False
                        while _bas <= 500_000:
                            _arlk = [(_bas + _i * 1000, _bas + (_i + 1) * 1000 - 1)
                                     for _i in range(_dalga)]
                            with ThreadPoolExecutor(max_workers=_dalga) as _ex:
                                _sonuc = list(_ex.map(_sayfa, _arlk))
                            _kisa = False
                            for _cd in _sonuc:
                                if _cd is None:
                                    _hata = True
                                    break
                                _tum.extend(_cd)
                                if len(_cd) < 1000:
                                    _kisa = True
                                    break
                            if _hata or _kisa:
                                break
                            _bas += _dalga * 1000
                    else:
                        _hata = True                 # fabrika yok → ardışık yol
                    if self._yeniden is None or _hata:
                        # ARDIŞIK yedek yol (eski davranış — her koşulda çalışır)
                        _bas = len(_tum)
                        while _bas <= 500_000:
                            _cd = getattr(self._b.range(_bas, _bas + 999)
                                          .execute(*a, **k), "data", None) or []
                            _tum.extend(_cd)
                            if len(_cd) < 1000:
                                break
                            _bas += 1000
                    try:
                        res.data = _tum
                    except Exception:
                        pass        # atanamazsa ilk 1000 ile devam (eski davranış)
        except Exception:
            pass                    # sayfalama hatası ana akışı ASLA bozmaz
        return res

    def __getattr__(self, name):
        # _b henüz yoksa (init sırası) AttributeError ver — sonsuz döngü engeli
        if name == "_b":
            raise AttributeError(name)
        attr = getattr(self._b, name)
        if callable(attr):
            def _wrap(*a, **k):
                # Oto-sayfalama için sorgu tipini işaretle + zinciri kaydet
                if name == "select":
                    self._select_var = True
                elif name in ("limit", "range", "single", "maybe_single", "csv"):
                    self._sinir_var = True
                try:
                    self._zincir.append((name, a, k))
                except Exception:
                    pass
                self._b = attr(*a, **k)
                return self
            return _wrap
        return attr


class _LoggingClient:
    def __init__(self, real, modul):
        self._c = real
        self._modul = modul

    def table(self, name):
        # yeniden: paralel sayfalama için aynı tabloya TAZE builder üretir
        return _LoggingTable(self._c.table(name), name, self._modul,
                             yeniden=lambda _n=name: self._c.table(_n))

    def __getattr__(self, name):
        if name == "_c":
            raise AttributeError(name)
        return getattr(self._c, name)


def wrap_client(real, modul):
    """Gerçek client'ı loglayan sarmalayıcıyla döndürür; hata olursa gerçek client'a düşer."""
    try:
        return _LoggingClient(real, modul)
    except Exception:
        return real


def get_loglar(limit=500, kullanici=None, modul=None, islem=None, baslangic=None, bitis=None):
    """Audit log kayıtları (yeni→eski), filtreli."""
    try:
        q = _raw_client().table("audit_log").select("*")
        if kullanici:
            q = q.eq("kullanici", kullanici)
        if modul:
            q = q.eq("modul", modul)
        if islem:
            q = q.eq("islem", islem)
        if baslangic:
            q = q.gte("zaman", str(baslangic))
        if bitis:
            q = q.lte("zaman", str(bitis) + " 23:59:59")
        return q.order("zaman", desc=True).limit(limit).execute().data or []
    except Exception:
        return []

# -*- coding: utf-8 -*-
"""Oto-sayfalama süzgeçleri korumalı (shared/audit.py, 21.10.2026 olayı).

Supabase tek sorguda en fazla 1000 satır döndürür; sarmalayıcı kalan sayfaları sorgu zincirini taze
builder üzerinde yeniden kurarak çeker. `eq` sınıfta ayrı tanımlı olduğu için zincire yazılmıyordu: 2. ve
sonraki sayfalar `eq` süzgeci OLMADAN geliyordu. Canlıda mikro_fatura (1.063 satış faturası, tablo
daha büyük) okunurken aynı fatura iki kez geldi; satış eşitlemesi kopya denetimine takılıp durdu.
Denetim olmayan her ekranda da 1000 satırı aşan `eq` süzgeçli okuma yanlış satır getiriyordu."""
from shared import audit as A


class _Sonuc:
    def __init__(self, data):
        self.data = data


class _Sahte:
    """PostgREST builder'ının küçük kopyası: select / eq / gte / order / range / execute, en fazla 1000 satır."""

    def __init__(self, satirlar):
        self._s = satirlar
        self._suz = []
        self._sira = None
        self._ar = None

    def select(self, *a, **k):
        return self

    def eq(self, kol, deger):
        self._suz.append(lambda r: r.get(kol) == deger)
        return self

    def gte(self, kol, deger):
        self._suz.append(lambda r: r.get(kol) >= deger)
        return self

    def order(self, kol, **k):
        self._sira = kol
        return self

    def range(self, a, b):
        self._ar = (a, b)
        return self

    def execute(self):
        r = [x for x in self._s if all(f(x) for f in self._suz)]
        if self._sira:
            r.sort(key=lambda x: x[self._sira])
        a, b = self._ar or (0, 999)
        return _Sonuc(r[a:min(b, a + 999) + 1])


def _tablo(satirlar):
    return A._LoggingTable(_Sahte(satirlar), "mikro_fatura", "test", yeniden=lambda: _Sahte(satirlar))


def test_eq_suzgeci_sonraki_sayfalarda_da_gecerli():
    # 3.000 fatura; yalnız 1.500'ü satış (tip 63) — 1000'i aşan süzülmüş okuma
    satirlar = [{"id": f"{i:05d}", "tip": 63 if i % 2 else 0, "t": "2026-07-01"} for i in range(3000)]
    r = _tablo(satirlar).select("*").eq("tip", 63).gte("t", "2026-07-01").order("id").execute().data
    assert len(r) == 1500
    assert all(x["tip"] == 63 for x in r)
    assert len({x["id"] for x in r}) == 1500          # kopya yok


def test_eq_zincirde_kayitli():
    t = _tablo([])
    t.select("*").eq("tip", 63)
    assert ("eq", ("tip", 63), {}) in t._zincir

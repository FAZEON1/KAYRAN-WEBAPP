# -*- coding: utf-8 -*-
"""Sayfa testi için bellekte sahte Supabase (tests/duman).

Uygulamanın her sorgu zincirini kabul eder (select / eq / in_ / order / range / insert / rpc …) ve
bellekteki tablolardan basit süzgeçle cevap verir; tanımadığı her metodu sessizce geçer. Amaç
verinin doğruluğu değil, sayfaların ÇİZİLEBİLMESİ: içe aktarma hatası, ad hatası, imza uyuşmazlığı,
boş veride çökme. Yazma işlemleri bellekte kalır, hiçbir yere gitmez.
"""
import sys
import types

KULLANICI = "ibrahim"
_MODULLER = ["kayranacc", "kayranpm", "depo", "ithalat", "teknikservis", "satis", "hesap_makinesi"]
_OZEL = ["yonetim", "patron_panel", "talep_yonetici", "kullanici_yonetimi", "toplam_aktifler", "kar"]

YETKI = [{"id": 1, "kullanici": KULLANICI, "moduller": _MODULLER, "ozel": _OZEL,
          "salt_okur": False, "aktif": True}]
TABLOLAR = {"kullanici_yetkileri": [dict(r) for r in YETKI]}


class _Sonuc:
    def __init__(self, data):
        self.data = data
        self.count = len(data) if isinstance(data, list) else (1 if data else 0)


class Sorgu:
    def __init__(self, tablo):
        self.tablo, self._suz, self._tek, self._yaz = tablo, [], False, None
        self._aralik = None

    # Tanınmayan her zincir halkası (not_, or_, filter, ilike, text_search, storage …) geçer
    def __getattr__(self, ad):
        if ad.startswith("__"):
            raise AttributeError(ad)
        return self

    def __call__(self, *a, **k):
        return self

    def eq(self, s, v):
        self._suz.append(lambda r: str(r.get(s)) == str(v))
        return self

    def in_(self, s, vs):
        vs = {str(x) for x in (vs or [])}
        self._suz.append(lambda r: str(r.get(s)) in vs)
        return self

    def range(self, a, b):
        self._aralik = (a, b)
        return self

    def single(self):
        self._tek = True
        return self

    maybe_single = single

    def insert(self, satirlar, **_):
        self._yaz = satirlar if isinstance(satirlar, list) else [satirlar]
        return self

    upsert = insert

    def execute(self):
        if self._yaz is not None:
            satirlar = []
            tablo = TABLOLAR.setdefault(self.tablo, [])
            for r in self._yaz:
                r = dict(r)
                r.setdefault("id", len(tablo) + 1)
                tablo.append(r)
                satirlar.append(r)
            return _Sonuc(satirlar)
        r = [dict(x) for x in TABLOLAR.get(self.tablo, []) if all(f(x) for f in self._suz)]
        if self._aralik:
            r = r[self._aralik[0]:self._aralik[1] + 1]
        if self._tek:
            return _Sonuc(r[0] if r else None)
        return _Sonuc(r)


class Istemci:
    def __getattr__(self, ad):
        if ad.startswith("__"):
            raise AttributeError(ad)
        return Sorgu(ad)

    def table(self, ad):
        return Sorgu(ad)

    from_ = table

    def rpc(self, ad, *a, **k):
        return Sorgu("_rpc_" + ad)


def kur():
    """sys.modules['supabase'] yerine sahtesini koyar (uygulama içe aktarmadan ÖNCE)."""
    m = types.ModuleType("supabase")
    m.Client = Istemci
    m.create_client = lambda *a, **k: Istemci()
    sys.modules["supabase"] = m

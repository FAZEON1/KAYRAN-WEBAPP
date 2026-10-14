# -*- coding: utf-8 -*-
"""Davranış (karakterizasyon) testleri için bellekte sahte Supabase.

AMAÇ: Para / stok hesaplarının SONUCUNU kesin sayılarla kilitlemek. tests/duman/sahte_db.py
sayfaların çizilebilmesi içindir, veri doğruluğu gözetmez; buradaki istemci ise yazılan
değeri gerçekten saklar ve bir sonraki okumada geri verir (select → kopya, update → kalıcı).

  · Yalnız uygulamanın kullandığı zincir halkaları: select / eq / neq / in_ / gte / lte /
    ilike / order / limit / range / single / insert / upsert / update / delete / execute.
  · rpc(...) HER ZAMAN hata fırlatır ("fonksiyon kurulu değil"): yeni veritabanı nesnesi
    (ör. atomik stok fonksiyonu) kurulmamışken kodun eski yola düştüğü yol sınanır.
  · Okunan satırlar derin kopyadır: kod sözlüğü yerinde değiştirip update etmezse tabloya yansımaz
    (gerçek Supabase gibi).
"""
import copy

import pytest


class _Sonuc:
    def __init__(self, data):
        self.data = data
        self.count = len(data) if isinstance(data, list) else (1 if data else 0)


class RpcYok(Exception):
    """PostgREST'in kurulmamış fonksiyon cevabına benzer."""


class _Sorgu:
    def __init__(self, db, tablo):
        self.db, self.tablo = db, tablo
        self._suz, self._sira, self._limit, self._aralik = [], [], None, None
        self._tek = False
        self._islem, self._veri = "select", None

    # ── okuma ──
    def select(self, *_a, **_k):
        return self

    def eq(self, s, v):
        self._suz.append(lambda r, s=s, v=v: str(r.get(s)) == str(v))
        return self

    def neq(self, s, v):
        self._suz.append(lambda r, s=s, v=v: str(r.get(s)) != str(v))
        return self

    def in_(self, s, vs):
        kume = {str(x) for x in (vs or [])}
        self._suz.append(lambda r, s=s: str(r.get(s)) in kume)
        return self

    def gte(self, s, v):
        self._suz.append(lambda r, s=s, v=v: r.get(s) is not None and str(r.get(s)) >= str(v))
        return self

    def lte(self, s, v):
        self._suz.append(lambda r, s=s, v=v: r.get(s) is not None and str(r.get(s)) <= str(v))
        return self

    def ilike(self, s, desen):
        parca = str(desen).strip("%").lower()
        self._suz.append(lambda r, s=s: parca in str(r.get(s) or "").lower())
        return self

    def order(self, s, desc=False, **_k):
        self._sira.append((s, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def range(self, a, b):
        self._aralik = (a, b)
        return self

    def single(self):
        self._tek = True
        return self

    maybe_single = single

    # ── yazma ──
    def insert(self, veri, **_k):
        self._islem, self._veri = "insert", veri
        return self

    def upsert(self, veri, **_k):
        self._islem, self._veri = "insert", veri
        return self

    def update(self, veri):
        self._islem, self._veri = "update", veri
        return self

    def delete(self):
        self._islem = "delete"
        return self

    def _eslesen(self):
        return [r for r in self.db.tablolar.setdefault(self.tablo, []) if all(f(r) for f in self._suz)]

    def execute(self):
        tablo = self.db.tablolar.setdefault(self.tablo, [])
        if self._islem == "insert":
            satirlar = self._veri if isinstance(self._veri, list) else [self._veri]
            eklenen = []
            for r in satirlar:
                r = copy.deepcopy(dict(r))
                if "id" not in r:
                    self.db.sayac += 1
                    r["id"] = self.db.sayac
                tablo.append(r)
                eklenen.append(copy.deepcopy(r))
            self.db.gunluk.append(("insert", self.tablo, copy.deepcopy(satirlar)))
            return _Sonuc(eklenen)
        if self._islem == "update":
            hedef = self._eslesen()
            for r in hedef:
                r.update(copy.deepcopy(self._veri))
            self.db.gunluk.append(("update", self.tablo, copy.deepcopy(self._veri)))
            return _Sonuc([copy.deepcopy(r) for r in hedef])
        if self._islem == "delete":
            hedef = self._eslesen()
            self.db.tablolar[self.tablo] = [r for r in tablo if r not in hedef]
            self.db.gunluk.append(("delete", self.tablo, len(hedef)))
            return _Sonuc([copy.deepcopy(r) for r in hedef])
        r = [copy.deepcopy(x) for x in self._eslesen()]
        for s, desc in reversed(self._sira):
            r.sort(key=lambda x, s=s: (x.get(s) is None, str(x.get(s) if x.get(s) is not None else "")),
                   reverse=desc)
        if self._aralik:
            r = r[self._aralik[0]:self._aralik[1] + 1]
        if self._limit is not None:
            r = r[: self._limit]
        if self._tek:
            return _Sonuc(r[0] if r else None)
        return _Sonuc(r)


class SahteDB:
    """Bellekte tablolar: {ad: [satır, ...]}. get_client() yerine bu nesne verilir."""

    def __init__(self, **tablolar):
        self.tablolar = {k: copy.deepcopy(list(v)) for k, v in tablolar.items()}
        self.sayac = 1000
        self.gunluk = []

    def table(self, ad):
        return _Sorgu(self, ad)

    def rpc(self, ad, *_a, **_k):
        raise RpcYok(f"Could not find the function public.{ad} in the schema cache (PGRST202)")

    def satir(self, tablo, **kosul):
        for r in self.tablolar.get(tablo, []):
            if all(str(r.get(k)) == str(v) for k, v in kosul.items()):
                return r
        return None


@pytest.fixture
def sahte_db():
    """SahteDB sınıfı (testte tablolarla kurulur)."""
    return SahteDB

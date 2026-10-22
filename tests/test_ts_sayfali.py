# -*- coding: utf-8 -*-
"""Teknik servis okumaları 1000 satır sınırına takılmaz (22.10.2026).

Supabase tek sorguda en fazla 1000 satır döndürür. ts_kayitlar 791 kayıttaydı; Mikro iadesi her adet için ayrı
kayıt açtığından sınır yakında aşılacaktı: listeler, sayılar, G5F no sırası ve otomatik satıldı sessizce eksik
çalışırdı. Ayrıca geciken mal kabul bildirimi Berkay'a da gider (kullanıcı: "berkayı da ekle").
"""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


class _Sorgu:
    def __init__(self, satirlar, kayit):
        self.s, self.k, self.ar = satirlar, kayit, None

    def __getattr__(self, ad):
        return lambda *a, **k: self

    def range(self, a, b):
        self.ar = (a, b)
        return self

    def execute(self):
        a, b = self.ar if self.ar else (0, 999)
        b = min(b, a + 999)                     # sunucu sınırı
        self.k.append((a, b))

        class R:
            pass
        r = R()
        r.data = self.s[a:b + 1]
        return r


class _Istemci:
    def __init__(self, n):
        self.s = [{"id": i, "servis_form_no": f"G5F{i:05d}", "seri_no": f"S{i}", "depo": "" if i % 2 else "outlet",
                   "arayuz": "iade"} for i in range(1, n + 1)]
        self.k = []

    def table(self, ad):
        return _Sorgu(self.s, self.k)


def test_get_kayitlar_ve_form_no_1000_ustu(monkeypatch):
    import teknikservis.database as D
    cli = _Istemci(2345)
    monkeypatch.setattr(D, "get_client", lambda: cli)
    getattr(D.get_kayitlar, "clear", lambda: None)()
    assert len(D.get_kayitlar()) == 2345
    assert len(D.get_kayitlar(depolu=True)) == 1172
    assert D._sonraki_form_no() == "G5F02346"            # eskiden ilk 1000 kayda göre G5F01001 verirdi
    assert len(D.tum_seriler()) == 2345
    assert cli.k[:3] == [(0, 999), (1000, 1999), (2000, 2999)]


def test_sayfali_tam_1000_de_durur():
    import teknikservis.database as D
    cli = _Istemci(1000)
    assert len(D.sayfali(lambda: cli.table("ts_kayitlar"))) == 1000 and cli.k == [(0, 999), (1000, 1999)]


def test_bildirim_berkaya_da_gider_ve_okumalar_sayfali():
    from teknikservis import mikro_iade
    assert mikro_iade.BILDIRIM_ALICILARI == ("ibrahim", "berkay")
    for yol in ("teknikservis/mikro_iade.py", "teknikservis/mikro_satis.py"):
        m = (KOK / yol).read_text(encoding="utf-8")
        assert "sayfali(lambda:" in m and ".limit(5000)" not in m


def test_esitleme_kod_birlesince_calisir():
    y = (KOK / ".github" / "workflows" / "mikro-esitle.yml").read_text(encoding="utf-8")
    i = y.index("on:")
    assert "push:" in y[i:i + 300] and '"araclar/mikro_aktarici/**"' in y and "branches: [main]" in y

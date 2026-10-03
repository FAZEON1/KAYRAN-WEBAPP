# -*- coding: utf-8 -*-
"""Firma adları cari kartındaki TAM adla (Ekim 2026): Kampanyalar, Müşteri Satışları, Ref No.
Eskiden kısaltılıyordu ("VATAN BİLGİSAYAR SANAYİ VE TİCARET A.Ş." → "Vatan Bilgisayar")."""
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
TAM = "VATAN BİLGİSAYAR SANAYİ VE TİCARET A.Ş."


def test_kampanya_tam_cari_adi(monkeypatch):
    import kayranpm.ref_no as R
    monkeypatch.setattr(R, "firma_tam_cari_adi", lambda kod: TAM if kod == "VATAN" else "")
    from kayranpm.kampanya import _firma_ad
    assert _firma_ad("VATAN") == TAM


def test_ref_no_kisaltmasiz():
    s = (KOK / "kayranpm/ref_ekran.py").read_text(encoding="utf-8")
    assert "firma_kisa_ad(" not in s


def test_musteri_satislari_ve_stok_karti_tam_ad():
    g = (KOK / "kayranpm/musteri_ekran.py").read_text(encoding="utf-8")   # Ekim 2026: yeni ekran
    assert "firma_gorunen_ad(kod, kisa=False)" in g
    k = (KOK / "kayranpm/stok_karti.py").read_text(encoding="utf-8")
    assert '"Firma": _k.get("firma", "") or "—"' not in k

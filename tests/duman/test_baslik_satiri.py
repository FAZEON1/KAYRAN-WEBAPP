# -*- coding: utf-8 -*-
"""Sayfa testi · görünüm cilası (Ekim 2026): Muhasebe'de sayfa başlığı (sekmedeki adla) hafta / kur
seçicilerinin SOLUNA, aynı satıra yazılır; eskiden seçicilerin altında ayrı satırdaydı ve sayfa adı
gizliydi. Sayfa gövdesi bir parça (fragment) olduğu için başlık yuvası oturumda tutulur.
Yalnız gerçek Streamlit kuruluyken çalışır (CI: "Sayfa testi")."""
import pytest

pytest.importorskip("streamlit.testing.v1")

from test_dosya_kapisi import _sorunlar  # noqa: E402
from test_sayfalar import BETIK, SURE  # noqa: E402


def _ac(sayfa):
    import sahte_db
    from streamlit.testing.v1 import AppTest
    sahte_db.TABLOLAR.clear()
    sahte_db.TABLOLAR["kullanici_yetkileri"] = [dict(r) for r in sahte_db.YETKI]
    sahte_db.TABLOLAR["haftalar"] = [
        {"id": 8, "hafta_adi": "12.10.2026 GÜNCEL ÖDEME LİSTESİ", "yuklendi_tarih": "12.10.2026", "aktif": 1}]
    at = AppTest.from_file(BETIK, default_timeout=SURE)
    at.secrets["supabase"] = {"url": "http://sahte.local", "key": "sahte", "service_role_key": "sahte"}
    at.session_state["giris_yapildi"] = True
    at.session_state["aktif_kullanici"] = sahte_db.KULLANICI
    at.session_state["aktif_uygulama"] = "kayranacc"
    at.session_state["acc_sayfa"] = sayfa
    at.run()
    assert not _sorunlar(at), _sorunlar(at)
    return at


def _sira(dugum, out):
    """Ağacı ekrandaki sırayla gez: (tür, metin)."""
    for c in getattr(dugum, "children", {}).values():
        tur = type(c).__name__
        if tur == "Markdown":
            out.append(("md", str(c.value)))
        elif tur == "Button":
            out.append(("btn", str(c.label)))
        elif tur == "Block" and getattr(c.proto, "WhichOneof", None) and c.proto.WhichOneof("type") == "popover":
            out.append(("pop", str(c.proto.popover.label)))
        _sira(c, out)
    return out


def _baslik_ve_secici(at, ad):
    sira = _sira(at.main, [])
    i_bas = next((i for i, (t, m) in enumerate(sira) if t == "md" and "k-baslik-sekme" in m and f">{ad}<" in m), None)
    i_kur = next((i for i, (t, m) in enumerate(sira) if t == "pop" and m.startswith("USD/TL")), None)
    assert i_bas is not None, f"sayfa başlığı '{ad}' sekme adıyla yazılmadı: {[m[:90] for t, m in sira if 'k-baslik' in m]}"
    assert i_kur is not None, "kur seçicisi yok"
    return sira, i_bas, i_kur


@pytest.mark.parametrize("sayfa, ad", [("📊 Dashboard", "Genel bakış"), ("📋 Firma Çekleri", "Firma çekleri")])
def test_baslik_seciciyle_ayni_satirda_solda(sayfa, ad):
    at = _ac(sayfa)
    sira, i_bas, i_kur = _baslik_ve_secici(at, ad)
    assert i_bas < i_kur, sira[:12]
    # hafta düğmesi Türkçe 'İ' bozulmadan (eskiden str.title() → 'Li̇stesi̇')
    hafta = [m for t, m in sira if t == "pop" and "12.10.2026" in m]
    assert hafta == ["12.10.2026 güncel ödeme listesi"], hafta


def test_bu_hafta_basligi_ve_eylem_dugmesi_ust_satirda():
    at = _ac("💳 Bu Hafta")
    sira, i_bas, i_kur = _baslik_ve_secici(at, "Bu hafta")
    i_manuel = next((i for i, (t, m) in enumerate(sira) if t == "btn" and m == "Manuel ödeme"), -1)
    assert i_bas < i_manuel < i_kur, sira[:14]
    assert "12.10.2026 güncel ödeme listesi" in sira[i_bas][1]

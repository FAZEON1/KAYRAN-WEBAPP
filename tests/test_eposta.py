# -*- coding: utf-8 -*-
"""Kişiye özel e-posta bildirimleri (Ekim 2026).

  · Yükleme hatırlatmaları: her sorumluya günde EN ÇOK bir toplu mail —
    son günden 2 gün önce, son gün, gecikmede her iş günü; gecikme 5 iş gününü
    geçince yöneticiye kopya. Söylenecek bir şey yoksa mail gitmez.
  · Talepler: yeni talep → talep yöneticileri; yanıt / durum değişikliği → talep sahibi.
  · Adresler kodda değil veritabanında (Kullanıcı Yönetimi'nden girilir).
Eskiden: talep mail fonksiyonu yazılmış ama HİÇ çağrılmıyordu; adres tutulmuyordu.
"""
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _oku(y):
    return (KOK / y).read_text(encoding="utf-8")


def _d(anahtar, sorumlu, seviye, kalan=None, gecikme=0, ad=None):
    return {"anahtar": anahtar, "ad": ad or anahtar, "sorumlu": sorumlu, "sorumlu_ad": sorumlu.title(),
            "modul": "kayranpm", "sayfa": "Ürün Yönetimi › Müşteri Satışları", "seviye": seviye,
            "kalan_gun": kalan, "gecikme_gun": gecikme, "eksik_adlar": ["Hafta 39 (21.09–27.09)"],
            "siklik": "haftalik", "sonraki_adi": "Hafta 40 (28.09–04.10)", "vade_metni": "05.10 Pzt"}


ADR = {"derya": "derya@g5f.com", "serdar": "serdar@g5f.com", "ibrahim": "ibrahim@g5f.com"}


# ── Hatırlatma kuralları ────────────────────────────────────────────
def test_yaklasan_son_gunden_iki_gun_once_ve_son_gun():
    from shared.eposta import hatirlatma_mailleri
    ps = hatirlatma_mailleri([_d("a", "derya", "yaklasiyor", kalan=2)], date(2026, 10, 1), ADR)
    assert len(ps) == 1 and ps[0]["kime"] == ["derya@g5f.com"]
    assert hatirlatma_mailleri([_d("a", "derya", "yaklasiyor", kalan=1)], date(2026, 10, 1), ADR) == []
    p = hatirlatma_mailleri([_d("a", "derya", "yaklasiyor", kalan=0)], date(2026, 10, 1), ADR)[0]
    assert "son gün bugün" in p["konu"].lower()


def test_gecikme_is_gunu_ve_hafta_sonu_yok():
    from shared.eposta import hatirlatma_mailleri
    d = [_d("a", "derya", "gecikti", gecikme=3)]
    assert hatirlatma_mailleri(d, date(2026, 10, 1), ADR)                # Perşembe
    assert hatirlatma_mailleri(d, date(2026, 10, 3), ADR) == []          # Cumartesi


def test_kisi_basina_tek_toplu_mail():
    from shared.eposta import hatirlatma_mailleri
    ps = hatirlatma_mailleri([_d("a", "serdar", "gecikti", gecikme=2), _d("b", "serdar", "yaklasiyor", kalan=2),
                              _d("c", "derya", "gecikti", gecikme=1)], date(2026, 10, 1), ADR)
    s = next(p for p in ps if p["kullanici"] == "serdar")
    assert len(ps) == 2 and len(s["kalemler"]) == 2 and "1 yükleme gecikti" in s["konu"]


def test_bes_is_gunu_gecikmede_yoneticiye_kopya():
    from shared.eposta import hatirlatma_mailleri, is_gunu_gecikme
    # 1 Ekim Perşembe; 7 takvim günü önce (24 Eylül Perşembe) son gündü → 5 iş günü
    assert is_gunu_gecikme(date(2026, 10, 1), 7) == 5
    assert hatirlatma_mailleri([_d("a", "serdar", "gecikti", gecikme=7)], date(2026, 10, 1), ADR)[0]["cc"] == []
    p = hatirlatma_mailleri([_d("a", "serdar", "gecikti", gecikme=8)], date(2026, 10, 1), ADR)[0]
    assert p["cc"] == ["ibrahim@g5f.com"]                                # 6 iş günü > 5
    # sorumlu yöneticinin kendisiyse kopya yok
    assert hatirlatma_mailleri([_d("a", "ibrahim", "gecikti", gecikme=20)], date(2026, 10, 1), ADR)[0]["cc"] == []


def test_adresi_olmayan_atlanir_ve_bildirilir():
    from shared.eposta import hatirlatma_mailleri
    ps = hatirlatma_mailleri([_d("a", "samet", "gecikti", gecikme=1), _d("b", "", "gecikti", gecikme=1)],
                             date(2026, 10, 1), ADR)
    assert ps == [] or all(p["kime"] for p in ps)
    from shared.eposta import adressizler
    assert adressizler([_d("a", "samet", "gecikti", gecikme=1)], date(2026, 10, 1), ADR) == ["samet"]


def test_bugun_zaten_gonderilene_tekrar_gitmez():
    from shared.eposta import gonderilecekler
    ps = [{"kullanici": "derya"}, {"kullanici": "serdar"}]
    assert [p["kullanici"] for p in gonderilecekler(ps, {"derya": "2026-10-01"}, date(2026, 10, 1))] == ["serdar"]


def test_mail_icerigi_baglanti_ve_kacis():
    from shared.eposta import hatirlatma_mailleri
    p = hatirlatma_mailleri([_d("a", "derya", "gecikti", gecikme=3, ad="<b>X</b>")], date(2026, 10, 1), ADR)[0]
    assert "?s=kayranpm" in p["html"] and "&lt;b&gt;X&lt;/b&gt;" in p["html"] and "<b>X</b>" not in p["html"]


# ── Gönderim ────────────────────────────────────────────────────────
class _SMTP:
    gonderilen = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        pass

    def login(self, u, p):
        pass

    def sendmail(self, frm, to, msg):
        _SMTP.gonderilen.append((frm, list(to), msg))


def test_gonder_ve_ayarlar(monkeypatch):
    import shared.eposta as E
    monkeypatch.setattr(E.smtplib, "SMTP", _SMTP)
    monkeypatch.setenv("SMTP_USER", "bot@g5f.com")
    monkeypatch.setenv("SMTP_PASS", "x")
    _SMTP.gonderilen.clear()
    ok, kod = E.gonder(["a@g5f.com"], "Konu", "<p>x</p>", cc=["b@g5f.com"])
    assert ok and kod == "ok"
    frm, to, msg = _SMTP.gonderilen[0]
    assert to == ["a@g5f.com", "b@g5f.com"] and "Cc: b@g5f.com" in msg
    assert E.gonder([], "K", "x") == (False, "alici_yok")
    monkeypatch.delenv("SMTP_USER")
    monkeypatch.setattr(E, "_secrets", lambda: {})
    assert E.gonder(["a@g5f.com"], "K", "x") == (False, "smtp_yok")


def test_talep_mailleri_kacisli():
    from shared.eposta import talep_yeni_mail, talep_yanit_mail
    konu, html = talep_yeni_mail("Serdar", "<script>x</script>", "Ödeme ekranı", "Hata", "Yüksek")
    assert "<script>" not in html and "Serdar" in html and "Ödeme ekranı" in konu
    konu, html = talep_yanit_mail("Ödeme ekranı", "Düzeltildi", "tamamlandi")
    assert "Düzeltildi" in html and "Tamamlandı" in html


# ── Bağlantılar ─────────────────────────────────────────────────────
def test_uygulama_baglantilari():
    a = _oku("app.py")
    yeni = a[a.index("_ok = ekle_talep("):]
    yeni = yeni[:yeni.index('st.success("✅ Talebin kaydedildi')]
    assert "talep_yeni_mail(" in yeni and "arka_planda(" in yeni
    yanit = a[a.index("guncelle_talep_cevap(_tid"):]
    yanit = yanit[:yanit.index("st.rerun()")]
    assert "talep_yanit_mail(" in yanit and "arka_planda(" in yanit
    ky = a[a.index("def kullanici_yonetimi("):]
    assert "E-posta bildirimleri" in ky and "Deneme maili" in ky and "adres_kaydet(" in ky


def test_sabah_isi():
    w = _oku(".github/workflows/telegram-brifing.yml")
    assert "python otonom/eposta_hatirlatma.py" in w and "SMTP_USER: ${{ secrets.SMTP_USER }}" in w
    i = w.index("python otonom/eposta_hatirlatma.py")
    assert "if: always()" in w[w.rindex("- name:", 0, i):i]          # Telegram düşse de çalışır
    s = _oku("otonom/eposta_hatirlatma.py")
    assert "gonderilecekler(" in s and "hatirlatma_mailleri(" in s

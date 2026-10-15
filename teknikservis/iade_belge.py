# -*- coding: utf-8 -*-
"""Değişim / İade Belgesi (Ekim 2026, teknik servis isteği).

Onarımı mümkün olmayan ürün için tüketiciye verilen belge: tüketici bu belge ve satış faturasının aslıyla
ürünü aldığı firmaya başvurur; satıcı firma değişim / ücret iadesini yapar, iade faturasını bize keser.
Örnek: başka bir ithalatçının (Arena) aynı amaçlı belgesi — bölümler onunla aynı sırada.

Belge "iade alındı" durumundaki (ya da arıza sonucu "iade alındı" olan) kayıtlar için üretilir.
Metin saf fonksiyonda (belge_metni, test edilir); PDF reportlab ile, stil servis formuyla aynı.
"""
from datetime import date, datetime
from io import BytesIO

GECERLILIK_GUN = 30          # belgenin geçerlilik süresi (gün)
IADE_DURUM = "iade alındı"


def iade_belgesi_uygun(kayit):
    """Bu kayıt için değişim / iade belgesi verilebilir mi."""
    k = kayit or {}
    return IADE_DURUM in {str(k.get("mevcut_durum") or "").strip().lower(),
                          str(k.get("ariza_sonucu") or "").strip().lower()}


def _gun(v):
    """'2026-10-12T14:05:00' / date → date; okunamazsa None."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.fromisoformat(str(v or "")[:10]).date()
    except ValueError:
        return None


def iade_onay_tarihi(kayit, gecmis=None):
    """İade onay tarihi: geçmişteki İLK 'iade alındı' satırının tarihi; yoksa depo tarihi, yoksa mal kabul."""
    for h in sorted(gecmis or [], key=lambda x: str(x.get("tarih") or "")):
        if str(h.get("durum") or "").strip().lower() == IADE_DURUM and _gun(h.get("tarih")):
            return _gun(h.get("tarih"))
    k = kayit or {}
    return _gun(k.get("depo_tarihi")) or _gun(k.get("mal_kabul_tarihi"))


def _tr_tarih(g):
    return g.strftime("%d.%m.%Y") if g else "—"


def belge_metni(kayit, sirket, onay=None, bugun=None):
    """Belgedeki bütün metin (dict). sirket: shared.sirket.sirket_bilgi() çıktısı."""
    k, s = kayit or {}, sirket or {}
    bugun = bugun or date.today()

    def v(a):
        x = str(k.get(a) or "").strip()
        return x or "—"

    unvan = (s.get("unvan") or "").strip() or "—"
    tel = (s.get("tel") or "").strip()
    model = " — ".join(x for x in (str(k.get("stok_kodu") or "").strip(), str(k.get("stok_adi") or "").strip()) if x)
    return {
        "baslik": "DEĞİŞİM / İADE BELGESİ",
        "ust": [("Referans No", v("servis_form_no")), ("Belge Tarihi", _tr_tarih(bugun)),
                ("İade Onay Tarihi", _tr_tarih(onay))],
        "giris": ("Teknik servisimize ulaştırılmış olan, aşağıda bilgileri yazılı ürününüzün onarımı mümkün "
                  "olmadığından müşteri memnuniyeti anlayışımız kapsamında ürününüz için değişim / iade hakkı "
                  "tanınmıştır."),
        "basvuru": ("Bu Değişim / İade Belgesi ve satış faturanızın aslı ile birlikte ürünü satın aldığınız "
                    "firmaya başvurarak değişim / iade işleminizi gerçekleştirebilirsiniz."),
        "gecerlilik": f"İşbu Değişim / İade Belgesi {GECERLILIK_GUN} gün geçerlidir.",
        "urun": [("İthalatçı Firma", unvan), ("Belge No", v("servis_form_no")),
                 ("Ürün Modeli", model or "—"), ("Seri No", v("seri_no")),
                 ("Arıza", v("ariza")), ("Tüketici Adı", v("musteri_adi")),
                 ("Telefon No", v("musteri_tel")), ("Satıcı Firma", v("firma_bilgisi")),
                 ("Değişim / İade Onay Tarihi", _tr_tarih(onay))],
        "dikkat": [
            ("Ürüne ücret iadesi veya değişim işlemi yapmadan önce belge numarasını teknik servisimize"
             + (f" ({tel})" if tel else "") + " doğrulatınız."),
            ("Arızalı ürün, iade işlemi tamamlanana kadar teknik servisimizde kalır. Son kullanıcıya ürün "
             "değişimi veya ücret iadesi yaptıktan sonra bu belgeyle birlikte iade faturanızı düzenleyerek "
             "teknik servisimize iletiniz."),
            ("Değişim / iade uygulamasında doğabilecek anlaşmazlıklarda ithalatçı firmanın onayına "
             "başvurulmalıdır."),
        ],
        "imza": [unvan, "Teknik Servis"],
    }


def iade_belgesi_pdf(kayit, gecmis=None, sirket=None, bugun=None):
    """Değişim / İade Belgesi PDF'i (bytes)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from shared.utils import pdf_turkce_font, pdf_stilleri_turkcele
    from xml.sax.saxutils import escape

    if sirket is None:
        from shared.sirket import sirket_bilgi
        sirket = sirket_bilgi()
    m = belge_metni(kayit, sirket, iade_onay_tarihi(kayit, gecmis), bugun)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            title=f"{(kayit or {}).get('servis_form_no', '')} Değişim İade Belgesi")
    styles = getSampleStyleSheet()
    normal_f, kalin_f = pdf_turkce_font()
    pdf_stilleri_turkcele(styles, normal_f, kalin_f)
    govde = ParagraphStyle("govde", parent=styles["Normal"], fontName=normal_f, fontSize=10, leading=14)
    kalin = ParagraphStyle("kalin", parent=govde, fontName=kalin_f)
    baslik = ParagraphStyle("baslik", parent=styles["Title"], fontName=kalin_f, fontSize=15, spaceAfter=4)
    bolum = ParagraphStyle("bolum", parent=govde, fontName=kalin_f, fontSize=10.5, spaceBefore=10, spaceAfter=3)
    uyari = ParagraphStyle("uyari", parent=govde, textColor=colors.HexColor("#B91C1C"))
    e = lambda x: escape(str(x))  # noqa: E731
    el = []

    from shared.izin_belge import LOGO, LOGO_ORAN
    import os
    if os.path.exists(LOGO):
        from reportlab.platypus import Image
        logo = Image(LOGO, width=30 * mm, height=30 * mm * LOGO_ORAN)
        logo.hAlign = "CENTER"
        el += [logo, Spacer(1, 4)]
    el.append(Paragraph(e(m["baslik"]), baslik))

    ust = Table([[Paragraph(f"<b>{e(a)}:</b> {e(b)}", govde) for a, b in m["ust"]]],
                colWidths=[52 * mm, 52 * mm, 70 * mm])
    ust.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el += [ust, Spacer(1, 8), Paragraph(e(m["giris"]), govde), Spacer(1, 6),
           Paragraph(e(m["basvuru"]), govde), Spacer(1, 6), Paragraph(e(m["gecerlilik"]), kalin)]

    el.append(Paragraph("Ürün Bilgileri", bolum))
    t = Table([[Paragraph(f"<b>{e(a)}</b>", govde), Paragraph(e(b), govde)] for a, b in m["urun"]],
              colWidths=[55 * mm, 119 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    el.append(t)

    el.append(Paragraph("Satıcı Firmanın Dikkatine", bolum))
    for i, d in enumerate(m["dikkat"]):
        el += [Paragraph(e(d), uyari if i == len(m["dikkat"]) - 1 else govde), Spacer(1, 4)]

    el += [Spacer(1, 16)] + [Paragraph(f"<b>{e(x)}</b>", govde) for x in m["imza"]]
    doc.build(el)
    return buf.getvalue()

# -*- coding: utf-8 -*-
"""Depo stok listesi — yazdırmaya hazır A4 PDF.

Depo Stok ekranındaki "Yazdır" düğmesi bunu çağırır. Ekrandan bağımsızdır
(streamlit içe aktarmaz): veriyi alır, PDF bayt'ı döner.

Sayfa düzeni (A4 dikey):
  • Üst: KAYRAN · Depo stok listesi · depo adı · çeşit/adet özeti · hazırlayan
  • Tablo: # · SKU · Ürün · Adet  (+ isteğe bağlı "Sayılan" ve "Fark" boş
    sütunları: depo sayımında elle doldurmak için)
  • Başlık satırı her sayfada tekrar eder; uzun ürün adı satır kaydırır
  • Son: toplam satırı + imza alanları (Hazırlayan · Kontrol eden)
  • Alt bilgi her sayfada: depo · yazdırma zamanı · Sayfa n / N
"""
from io import BytesIO

SIRALAMALAR = {
    "adet": "Adet (çoktan aza)",
    "sku": "SKU (A → Z)",
    "urun": "Ürün adı (A → Z)",
}


def _tr_kucuk(s):
    """Arama anahtarı: i/ı/İ/I aynı sayılır. Ekran ürün adlarını marka yazımıyla
    noktasız I'lı büyütüyor ('MONITÖR'); kullanıcı 'monitör' yazınca bulunmalı."""
    return str(s or "").replace("İ", "i").replace("I", "i").lower().replace("ı", "i")


def liste_hazirla(urunler, ara="", sira="adet"):
    """Ekranda ve kâğıtta AYNI liste: arama süzgeci + sıralama (saf)."""
    a = _tr_kucuk(ara).strip()
    out = [u for u in (urunler or [])
           if not a or a in _tr_kucuk(f"{u.get('sku', '')} {u.get('urun_adi', '')}")]
    if sira == "sku":
        out.sort(key=lambda u: _tr_kucuk(u.get("sku")))
    elif sira == "urun":
        out.sort(key=lambda u: _tr_kucuk(u.get("urun_adi")))
    else:
        out.sort(key=lambda u: (-int(u.get("adet") or 0), _tr_kucuk(u.get("sku"))))
    return out


def _sayi(n):
    return f"{int(n):,}".replace(",", ".")


def depo_stok_pdf(depo, urunler, hazirlayan="", sayim_sutunu=False, not_metni="", zaman=None):
    """A4 PDF (bytes). urunler: [{sku, urun_adi, adet}] — liste_hazirla çıktısı."""
    from datetime import datetime
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
                                    KeepTogether)
    from shared.utils import pdf_turkce_font

    NORMAL, BOLD = pdf_turkce_font()
    zaman = zaman or datetime.now()
    z_metin = zaman.strftime("%d.%m.%Y %H:%M")
    MUREKKEP = colors.HexColor("#111827")
    SOLUK = colors.HexColor("#4B5563")
    CIZGI = colors.HexColor("#D1D5DB")
    ZEBRA = colors.HexColor("#F3F4F6")
    BANT = colors.HexColor("#E5E7EB")

    s_baslik = ParagraphStyle("b", fontName=BOLD, fontSize=16, leading=19, textColor=MUREKKEP)
    s_alt = ParagraphStyle("a", fontName=NORMAL, fontSize=9.5, leading=13, textColor=SOLUK)
    s_hucre = ParagraphStyle("h", fontName=NORMAL, fontSize=9, leading=11.5, textColor=MUREKKEP)
    s_sku = ParagraphStyle("s", parent=s_hucre, fontName=BOLD)
    s_bas = ParagraphStyle("t", fontName=BOLD, fontSize=8.5, leading=10, textColor=SOLUK)
    s_bas_sag = ParagraphStyle("ts", parent=s_bas, alignment=TA_RIGHT)
    s_sag = ParagraphStyle("hs", parent=s_hucre, alignment=TA_RIGHT, fontName=BOLD)

    toplam = sum(int(u.get("adet") or 0) for u in urunler)
    hikaye = [
        Paragraph(f"Depo stok listesi · {_esc(depo)}", s_baslik),
        Spacer(1, 2 * mm),
        Paragraph(f"{_sayi(len(urunler))} çeşit · toplam {_sayi(toplam)} adet · {z_metin}"
                  + (f" · Hazırlayan: {_esc(hazirlayan)}" if hazirlayan else ""), s_alt),
    ]
    if not_metni:
        hikaye += [Spacer(1, 1 * mm), Paragraph(_esc(not_metni), s_alt)]
    hikaye.append(Spacer(1, 5 * mm))

    bas = [Paragraph("#", s_bas), Paragraph("SKU", s_bas), Paragraph("Ürün", s_bas),
           Paragraph("Adet", s_bas_sag)]
    gen = [10 * mm, 38 * mm, None, 18 * mm]
    if sayim_sutunu:
        bas += [Paragraph("Sayılan", s_bas_sag), Paragraph("Fark", s_bas_sag)]
        gen += [20 * mm, 16 * mm]
    kullanilir = A4[0] - 30 * mm
    gen[2] = kullanilir - sum(g for g in gen if g)

    satirlar = [bas]
    for i, u in enumerate(urunler, 1):
        s = [Paragraph(str(i), s_hucre), Paragraph(_esc(u.get("sku")), s_sku),
             Paragraph(_esc(u.get("urun_adi")), s_hucre), Paragraph(_sayi(u.get("adet") or 0), s_sag)]
        if sayim_sutunu:
            s += ["", ""]
        satirlar.append(s)
    top = ["", "", Paragraph("Toplam", s_sku), Paragraph(_sayi(toplam), s_sag)] + (["", ""] if sayim_sutunu else [])
    satirlar.append(top)

    stil = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), BANT),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, SOLUK),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, SOLUK),
        ("BACKGROUND", (0, -1), (-1, -1), BANT),
    ]
    for r in range(1, len(satirlar) - 1):
        if r % 2 == 0:
            stil.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
        stil.append(("LINEBELOW", (0, r), (-1, r), 0.25, CIZGI))
    if sayim_sutunu:   # elle yazılacak kutular belirgin olsun
        stil.append(("BOX", (4, 1), (5, len(satirlar) - 2), 0.4, CIZGI))
        stil.append(("INNERGRID", (4, 1), (5, len(satirlar) - 2), 0.4, CIZGI))
    tablo = Table(satirlar, colWidths=gen, repeatRows=1)
    tablo.setStyle(TableStyle(stil))
    hikaye.append(tablo)

    # İmza alanları
    s_imza = ParagraphStyle("i", fontName=NORMAL, fontSize=9, leading=12, textColor=SOLUK)
    imza = Table([[Paragraph("Hazırlayan", s_imza), "", Paragraph("Kontrol eden / teslim alan", s_imza)],
                  [Paragraph(_esc(hazirlayan) or " ", s_hucre), "", Paragraph(" ", s_hucre)],
                  [Paragraph("Tarih · İmza", s_imza), "", Paragraph("Tarih · İmza", s_imza)]],
                 colWidths=[75 * mm, kullanilir - 150 * mm, 75 * mm], rowHeights=[6 * mm, 14 * mm, 6 * mm])
    imza.setStyle(TableStyle([("LINEBELOW", (0, 1), (0, 1), 0.6, SOLUK),
                              ("LINEBELOW", (2, 1), (2, 1), 0.6, SOLUK),
                              ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    hikaye += [Spacer(1, 12 * mm), KeepTogether(imza)]

    depo_adi = str(depo or "")

    class _Numarali(_canvas.Canvas):
        """Alt bilgiye 'Sayfa n / N' yazmak için sayfaları sonda basar."""
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._sayfalar = []

        def showPage(self):
            self._sayfalar.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._sayfalar)
            for d in self._sayfalar:
                self.__dict__.update(d)
                self.setFont(NORMAL, 8)
                self.setFillColor(SOLUK)
                self.setStrokeColor(CIZGI)
                self.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
                self.drawString(15 * mm, 8 * mm, f"KAYRAN Workspace · Depo stok listesi · {depo_adi}")
                self.drawRightString(A4[0] - 15 * mm, 8 * mm, f"{z_metin} · Sayfa {self._pageNumber} / {n}")
                super().showPage()
            super().save()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"Depo stok listesi - {depo_adi}", author="KAYRAN")
    doc.build(hikaye, canvasmaker=_Numarali)
    return buf.getvalue()


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

# -*- coding: utf-8 -*-
"""Teknik Servis — çok kalemli sevk irsaliyesi / sevk fişi PDF'i.

Madde 8. Aynı alıcıya giden BİRDEN FAZLA ürün tek belgede toplanır:
  · değişim yapılan ürünün gönderimi
  · teknik servis ürününün geri gönderimi

⚠️ ÖNEMLİ — RESMÎ BELGE DEĞİLDİR
Şirket e-İrsaliye mükellefi olduğu için buradan çıkan belge resmî sevk
irsaliyesi YERİNE GEÇMEZ; sevkin depo/müşteri nüshasıdır. Resmî e-İrsaliye
entegratörden kesilir, numarası bu belgedeki "e-İrsaliye No" alanına yazılır.
(Aynı yaklaşım depo/belge.py::sevk_fisi_pdf içinde de kullanılıyor.)

Stil, teknikservis/database.py::servis_formu_pdf ve depo/belge.py ile
bilinçli olarak aynıdır.
"""
from io import BytesIO
from datetime import datetime


# Sevk nedenleri — belgenin başlığını ve açıklamasını belirler
SEVK_NEDENLERI = [
    "Değişim ürünü gönderimi",
    "Teknik servis ürünü geri gönderim",
    "İade ürünü gönderimi",
    "Depo transferi",
    "Diğer",
]


def irsaliye_no_uret(mevcut_nolar, yil=None):
    """Yıl bazlı sıradaki irsaliye numarası: TS-2026-00001.

    mevcut_nolar: daha önce kullanılmış numaraların listesi (str).
    Aynı yıl içindeki en büyük sırayı bulup bir artırır.
    """
    yil = int(yil or datetime.now().year)
    onek = f"TS-{yil}-"
    enb = 0
    for no in (mevcut_nolar or []):
        s = str(no or "").strip().upper()
        if s.startswith(onek):
            try:
                enb = max(enb, int(s[len(onek):]))
            except ValueError:
                pass
    return f"{onek}{enb + 1:05d}"


def sevk_irsaliyesi_pdf(kalemler, bilgi=None, sirket=None):
    """Çok kalemli sevk irsaliyesi PDF'i üretir (bytes döner).

    kalemler : ts_kayitlar satırlarının listesi (her biri bir sevk kalemi).
               Değişim yapılmış kayıtlarda GÖNDERİLEN ürün, değişim ürünüdür —
               bu fonksiyon onu otomatik olarak doğru seçer.
    bilgi    : {irsaliye_no, sevk_tarihi, sevk_nedeni, e_irsaliye_no,
                kargo_no, tasiyici, aciklama, duzenleyen,
                alici_unvan, alici_adres, alici_vd, alici_vkn, alici_ilgili}
    sirket   : shared.sirket.sirket_bilgi() çıktısı (None ise kendi çeker)
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from shared.utils import pdf_turkce_font, pdf_stilleri_turkcele

    if sirket is None:
        from shared.sirket import sirket_bilgi
        sirket = sirket_bilgi()
    kalemler = list(kalemler or [])
    bilgi = dict(bilgi or {})
    if not kalemler:
        raise ValueError("İrsaliye için en az bir kalem gerekir.")

    def _b(alan, bos="—"):
        v = bilgi.get(alan)
        return str(v).strip() if v not in (None, "") else bos

    irs_no = _b("irsaliye_no", "")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=14 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title=f"{irs_no} Sevk İrsaliyesi")
    styles = getSampleStyleSheet()
    PDF_NORMAL, PDF_BOLD = pdf_turkce_font()
    pdf_stilleri_turkcele(styles, PDF_NORMAL, PDF_BOLD)

    h_style = ParagraphStyle("h", parent=styles["Title"], fontName=PDF_BOLD,
                             fontSize=16, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontName=PDF_NORMAL,
                         fontSize=9, textColor=colors.HexColor("#666666"))
    sec = ParagraphStyle("sec", parent=styles["Normal"], fontName=PDF_BOLD, fontSize=10,
                         textColor=colors.white, backColor=colors.HexColor("#334155"),
                         leftIndent=4, spaceBefore=8, spaceAfter=2, leading=16)
    kucuk = ParagraphStyle("kucuk", parent=styles["Normal"], fontName=PDF_NORMAL,
                           fontSize=7.5, textColor=colors.HexColor("#94A3B8"))
    hucre = ParagraphStyle("hucre", parent=styles["Normal"], fontName=PDF_NORMAL,
                           fontSize=8.5, leading=11)
    hucre_b = ParagraphStyle("hucreb", parent=styles["Normal"], fontName=PDF_BOLD,
                             fontSize=8.5, leading=11)
    el = []

    # ── Başlık ────────────────────────────────────────────────────────
    _marka = sirket.get("marka") or ""
    _ust = sirket.get("unvan") or "—"
    if _marka and _marka.upper() not in _ust.upper():
        _ust = f"{_ust} / {_marka}"
    el.append(Paragraph(_ust, ParagraphStyle("co", parent=styles["Normal"],
              fontName=PDF_BOLD, fontSize=11, textColor=colors.HexColor("#0EA5E9"))))
    el.append(Paragraph("SEVK İRSALİYESİ", h_style))
    el.append(Paragraph(
        f"İrsaliye No: <b>{irs_no or '—'}</b> &nbsp;|&nbsp; "
        f"Sevk Tarihi: {_b('sevk_tarihi')} &nbsp;|&nbsp; "
        f"Düzenleme: {datetime.now().strftime('%d.%m.%Y %H:%M')} &nbsp;|&nbsp; "
        f"Kalem: <b>{len(kalemler)}</b>", sub))
    el.append(Spacer(1, 6))

    def _tablo(satirlar, gen=(45 * mm, 133 * mm)):
        t = Table([[Paragraph(f"<b>{a}</b>", styles["Normal"]),
                    Paragraph(str(b), styles["Normal"])] for a, b in satirlar],
                  colWidths=list(gen))
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    # ── Gönderen / Alıcı ──────────────────────────────────────────────
    el.append(Paragraph("GÖNDEREN", sec))
    el.append(_tablo([
        ("Unvan", sirket.get("unvan") or "—"),
        ("Adres", sirket.get("adres") or "—"),
        ("Vergi Dairesi / No", f'{sirket.get("vd") or "—"} / {sirket.get("vkn") or "—"}'),
        ("Telefon / E-posta", f'{sirket.get("tel") or "—"} · {sirket.get("mail") or "—"}'),
    ]))

    el.append(Paragraph("ALICI", sec))
    el.append(_tablo([
        ("Unvan", _b("alici_unvan")),
        ("Mağaza / İlgili", _b("alici_ilgili")),
        ("Adres", _b("alici_adres")),
        ("Vergi Dairesi / No", f'{_b("alici_vd")} / {_b("alici_vkn")}'),
    ]))

    # ── Sevk edilen mallar (ÇOK KALEMLİ) ──────────────────────────────
    el.append(Paragraph("SEVK EDİLEN MALLAR", sec))
    basliklar = ["Sıra", "Servis No", "Stok Kodu", "Ürün Adı", "Seri No", "Miktar"]
    veri = [[Paragraph(f"<b>{c}</b>", hucre_b) for c in basliklar]]

    for i, k in enumerate(kalemler, 1):
        k = k or {}
        # Ürün değişimi yapıldıysa GÖNDERİLEN ürün değişim ürünüdür
        _dg_sk = str(k.get("degisim_stok_kodu") or "").strip()
        if _dg_sk:
            sk = _dg_sk
            ad = str(k.get("degisim_stok_adi") or "").strip() or "—"
            sn = str(k.get("degisim_seri_no") or "").strip() or "—"
            ad = f"{ad}<br/><font size=7 color='#64748B'>(değişim ürünü · "\
                 f"iade alınan: {str(k.get('stok_kodu') or '—')} / "\
                 f"{str(k.get('seri_no') or '—')})</font>"
        else:
            sk = str(k.get("stok_kodu") or "—")
            ad = str(k.get("stok_adi") or "—")
            sn = str(k.get("seri_no") or "—")
        veri.append([
            Paragraph(str(i), hucre),
            Paragraph(str(k.get("servis_form_no") or "—"), hucre),
            Paragraph(sk, hucre),
            Paragraph(ad, hucre),
            Paragraph(sn, hucre),
            Paragraph("1 Adet", hucre),
        ])

    # Toplam satırı
    veri.append([Paragraph("", hucre), Paragraph("", hucre), Paragraph("", hucre),
                 Paragraph("<b>TOPLAM</b>", hucre_b), Paragraph("", hucre),
                 Paragraph(f"<b>{len(kalemler)} Adet</b>", hucre_b)])

    mt = Table(veri, colWidths=[13 * mm, 24 * mm, 28 * mm, 59 * mm, 34 * mm, 20 * mm],
               repeatRows=1)
    mt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (5, 0), (5, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    el.append(mt)

    # ── Sevk / belge bilgileri ────────────────────────────────────────
    el.append(Paragraph("SEVK VE BELGE BİLGİLERİ", sec))
    el.append(_tablo([
        ("Sevk Nedeni", _b("sevk_nedeni")),
        ("Taşıyıcı / Sevk Şekli", _b("tasiyici")),
        ("Kargo Takip No", _b("kargo_no")),
        ("e-İrsaliye No", _b("e_irsaliye_no")),
        ("Açıklama", _b("aciklama")),
        ("Düzenleyen", _b("duzenleyen")),
    ]))

    # ── İmza ──────────────────────────────────────────────────────────
    el.append(Spacer(1, 18))
    imza = Table([[Paragraph("Teslim Eden<br/>Ad Soyad / İmza<br/><br/>_______________",
                             styles["Normal"]),
                   Paragraph("Teslim Alan<br/>Ad Soyad / İmza<br/><br/>_______________",
                             styles["Normal"])]],
                 colWidths=[89 * mm, 89 * mm])
    imza.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9),
                              ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    el.append(imza)

    el.append(Spacer(1, 10))
    el.append(Paragraph(
        "Bu belge sevkin depo/müşteri nüshasıdır, resmî sevk irsaliyesi yerine geçmez. "
        "Resmî e-İrsaliye ayrıca düzenlenir ve numarası yukarıdaki "
        "\"e-İrsaliye No\" alanına işlenir.", kucuk))

    doc.build(el)
    return buf.getvalue()

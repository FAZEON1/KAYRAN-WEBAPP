"""Depo sevk belgeleri — yazdırılabilir PDF üretimi.

Şirket e-İrsaliye mükellefi olduğu için buradan çıkan belge RESMÎ İRSALİYE
DEĞİLDİR; sevkin depo/müşteri nüshasıdır. Resmî e-İrsaliye entegratörden
kesilir ve numarası bu fişin üzerine "e-İrsaliye No" alanına yazılır.

Stil, teknikservis/database.py::servis_formu_pdf ile bilinçli olarak aynı.
"""
from io import BytesIO
from datetime import datetime


def fis_no_uret(mevcut_hareketler, yil=None):
    """Yıl bazlı sıradaki fiş numarasını üretir: KYR-2026-00001.

    mevcut_hareketler: tüm takip kayıtlarındaki hareket dict'lerinin düz listesi.
    Aynı yıl içinde kullanılmış en büyük sırayı bulup bir artırır.
    """
    yil = int(yil or datetime.now().year)
    onek = f"KYR-{yil}-"
    enb = 0
    for h in (mevcut_hareketler or []):
        no = str((h or {}).get("fis_no") or "").strip().upper()
        if no.startswith(onek):
            try:
                enb = max(enb, int(no[len(onek):]))
            except Exception:
                pass
    return f"{onek}{enb + 1:05d}"


def sevk_fisi_pdf(kayit, hareket, sirket=None):
    """Tek bir sevk hareketi için A4 sevk/teslim fişi üretir (bytes döner).

    kayit   : depo_manuel_takip satırı (firma, sku, urun_adi, fatura_adet,
              sevk_edilen, firma_adres, firma_vd, firma_vkn ...)
    hareket : {tarih, adet, belge_no, fis_no, e_irsaliye_no, aciklama, kullanici}
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
    kayit = kayit or {}
    hareket = hareket or {}

    def _k(alan, bos="—"):
        v = kayit.get(alan)
        return str(v).strip() if v not in (None, "") else bos

    def _h(alan, bos="—"):
        v = hareket.get(alan)
        return str(v).strip() if v not in (None, "") else bos

    fis_no = _h("fis_no", "")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=14 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title=f"{fis_no} Sevk Fişi")
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
    el = []

    # ── Başlık ────────────────────────────────────────────────────────
    _marka = sirket.get("marka") or ""
    _ust = sirket.get("unvan") or "—"
    if _marka and _marka.upper() not in _ust.upper():
        _ust = f"{_ust} / {_marka}"
    el.append(Paragraph(_ust, ParagraphStyle("co", parent=styles["Normal"],
              fontName=PDF_BOLD, fontSize=11, textColor=colors.HexColor("#0EA5E9"))))
    el.append(Paragraph("SEVK / TESLİM FİŞİ", h_style))
    el.append(Paragraph(
        f"Fiş No: <b>{fis_no or '—'}</b> &nbsp;|&nbsp; "
        f"Sevk Tarihi: {_h('tarih')} &nbsp;|&nbsp; "
        f"Düzenleme: {datetime.now().strftime('%d.%m.%Y %H:%M')}", sub))
    el.append(Spacer(1, 6))

    def _tablo(satirlar, gen=(45 * mm, 120 * mm)):
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
        ("Firma", _k("firma")),
        ("Adres", _k("firma_adres")),
        ("Vergi Dairesi / No", f'{_k("firma_vd")} / {_k("firma_vkn")}'),
    ]))

    # ── Sevk edilen mal ───────────────────────────────────────────────
    el.append(Paragraph("SEVK EDİLEN MAL", sec))
    _mal = [["Sıra", "Stok Kodu", "Ürün Adı", "Miktar", "Birim"],
            ["1", _k("sku"), _k("urun_adi"), str(hareket.get("adet") or "—"), "Adet"]]
    mt = Table([[Paragraph(f"<b>{c}</b>" if i == 0 else str(c), styles["Normal"])
                 for c in satir] for i, satir in enumerate(_mal)],
               colWidths=[14 * mm, 32 * mm, 79 * mm, 20 * mm, 20 * mm])
    mt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(mt)

    # ── Sipariş / bakiye durumu ───────────────────────────────────────
    _fat = int(kayit.get("fatura_adet") or 0)
    _sev = int(kayit.get("sevk_edilen") or 0)
    el.append(Paragraph("SİPARİŞ DURUMU (bu sevk sonrası)", sec))
    el.append(_tablo([
        ("Faturalanan Toplam", f"{_fat} adet"),
        ("Bugüne Kadar Sevk Edilen", f"{_sev} adet"),
        ("Bekleyen (kalan)", f"{max(0, _fat - _sev)} adet"),
    ]))

    # ── Belge referansları ────────────────────────────────────────────
    el.append(Paragraph("BELGE BİLGİLERİ", sec))
    el.append(_tablo([
        ("e-İrsaliye No", _h("e_irsaliye_no")),
        ("Fatura / Belge No", _h("belge_no")),
        ("Açıklama", _h("aciklama")),
        ("Düzenleyen", _h("kullanici")),
    ]))

    # ── İmza ──────────────────────────────────────────────────────────
    el.append(Spacer(1, 20))
    imza = Table([[Paragraph("Teslim Eden<br/>Ad Soyad / İmza<br/><br/>_______________", styles["Normal"]),
                   Paragraph("Teslim Alan<br/>Ad Soyad / İmza<br/><br/>_______________", styles["Normal"])]],
                 colWidths=[82 * mm, 82 * mm])
    imza.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9),
                              ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    el.append(imza)

    el.append(Spacer(1, 10))
    el.append(Paragraph(
        "Bu belge sevkin depo/müşteri nüshasıdır, resmî sevk irsaliyesi yerine geçmez. "
        "Resmî e-İrsaliye ayrıca düzenlenir.", kucuk))

    doc.build(el)
    return buf.getvalue()

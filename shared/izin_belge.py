# -*- coding: utf-8 -*-
"""İzin belgeleri — antetli, imzalı çıktılar (Ekim 2026).

  · İzin formu (her izin için): çalışanın yazılı izin talebi ve işverenin onayı. Yıllık Ücretli İzin
    Yönetmeliği md. 8'deki talep bilgileri (adı soyadı, sicil no, izin tarihleri, yol izni isteği)
    ve imza alanları: izni isteyen çalışan · birim yöneticisi · işveren / işveren vekili.
  · Yıllık izin kayıt belgesi (her çalışan için): Yönetmelik md. 20 — adı soyadı, sicil numarası, işe
    giriş tarihi, yıllık izne hak kazanılan tarih, işyerindeki çalışma süresi, izin günleri sayısı, yol
    izni günleri sayısı, iznin başlama ve sona erme tarihi; her satırda işçinin imzası.
Antet: shared/logo/sirket_logo.png + şirket künyesi (kişi menüsü › Şirket belgeleri).

İçerik saf fonksiyonlarda (form_icerik, kayit_belgesi_icerik — test edilir); PDF çizimi reportlab ile.
"""
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO

from shared import izin_hesap as H

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "sirket_logo.png")
LOGO_ORAN = 386 / 900                     # yükseklik / genişlik (logo dosyası 900 × 386)
LACIVERT, TURUNCU, GRI, ACIK = "#1B2632", "#E5870B", "#64748B", "#F1F5F9"


def belge_no(talep):
    return f"IZN-{str(talep.get('baslangic') or '')[:4] or '0000'}-{int(talep.get('id') or 0):05d}"


def _buyuk(s):
    """Türkçe büyük harf ('izni' → 'İZNİ'; Python .upper() noktasız I yapar)."""
    return str(s or "").replace("i", "İ").replace("ı", "I").upper()


def _ad(personel):
    return personel.get("ad") or personel.get("kod") or ""


def _kisi(k):
    from shared.tasarim import kisi_adi
    return kisi_adi(k) if k else ""


def donus_gunu(bitis, cumartesi=False, yol_izni=0):
    """İzin (ve varsa yol izni) bittikten sonraki ilk iş günü."""
    g = bitis + timedelta(days=1 + int(yol_izni or 0))
    for _ in range(40):
        if H.gun_degeri(g, cumartesi) > 0:
            return g
        g += timedelta(days=1)
    return g


def calisma_suresi(ise_giris, gun):
    y, a = H.kidem(ise_giris, gun)
    return f"{y} yıl {a} ay"


# ── İçerik (saf) ────────────────────────────────────────────────────
def form_icerik(talep, personel, kisi_talepleri, bugun, cumartesi=False):
    """İzin formunun bütün metni: {baslik, no, calisan[], izin[], bakiye[] | None, beyan, onay, imzalar[]}."""
    tur = talep.get("tur")
    bas, bit = H.tarih(talep.get("baslangic")), H.tarih(talep.get("bitis"))
    giris = H.tarih(personel.get("ise_giris"))
    yol = int(talep.get("yol_izni") or 0)
    yillik = tur == "yillik"
    baslik = "YILLIK ÜCRETLİ İZİN FORMU" if yillik else f"İZİN FORMU · {_buyuk(H.tur_adi(tur))}"
    calisan = [("Adı soyadı", _ad(personel)), ("Sicil no", personel.get("sicil_no") or "—"),
               ("Bölümü", personel.get("departman") or "—"), ("İşe giriş tarihi", H.tr_tarih(giris)),
               ("İşyerindeki çalışma süresi", calisma_suresi(giris, bas) if giris and bas else "—")]
    ek = {"rapor": " (ödeme SGK'dan)", "dogum": " (ödeme SGK'dan)", "ucretsiz": ""}.get(
        tur, "" if H.TURLER.get(tur, {}).get("ucretli") else " (ücretsiz)")
    izin = [("İzin türü", H.tur_adi(tur) + ek),
            ("İzin başlangıcı", H.tr_tarih(bas)),
            ("İzin bitişi (son izin günü)", H.tr_tarih(bit) + (" · yarım gün" if talep.get("yarim_gun") else "")),
            ("İzin süresi", f"{H.tr_gun(talep.get('gun'))} (iş günü) · {talep.get('takvim_gunu') or H.takvim_gunu(bas, bit)} takvim günü")]
    if yillik:
        izin.append(("Yol izni (ücretsiz)", f"{yol} gün" if yol else "İstenmedi"))
    izin.append(("İşe başlama tarihi", H.tr_tarih(donus_gunu(bit, cumartesi, yol)) if bit else "—"))
    if talep.get("izin_adresi"):
        izin.append(("İzinde bulunacağı adres / telefon", talep["izin_adresi"]))
    if talep.get("aciklama"):
        izin.append(("Açıklama", talep["aciklama"]))
    bakiye = None
    if yillik and giris:
        # Bu izinden önceki durum: izin başladığı güne kadar doğan haklar − ondan önce başlayan onaylı izinler
        onceki = [t for t in kisi_talepleri if t.get("id") != talep.get("id")
                  and str(t.get("baslangic") or "") < str(talep.get("baslangic") or "")]
        b = H.bakiye(personel, onceki, bas or bugun)
        hak_son = (b["haklar"][-1]["tarih"] if b["haklar"] else None)
        once = b["kalan"]
        bakiye = [("Yıllık izne hak kazanılan son tarih", H.tr_tarih(hak_son) if hak_son else "Henüz doğmadı"),
                  ("Bu izinden önceki kalan", H.tr_gun(once)),
                  ("Bu izin", H.tr_gun(talep.get("gun"))),
                  ("Bu izinden sonra kalan", H.tr_gun(once - float(talep.get("gun") or 0)))]
    if yillik:
        beyan = (f"{H.tr_tarih(bas)} – {H.tr_tarih(bit)} tarihleri arasında {H.tr_gun(talep.get('gun'))} yıllık "
                 "ücretli iznimi kullanmak istiyorum. İzin süresince başka bir işte ücret karşılığı çalışmayacağımı "
                 "beyan ederim.")
    elif tur == "rapor":
        beyan = (f"{H.tr_tarih(bas)} – {H.tr_tarih(bit)} tarihleri arasında hekim raporum bulunmaktadır. "
                 "Rapor aslı ekte sunulmuştur.")
    else:
        beyan = (f"{H.tr_tarih(bas)} – {H.tr_tarih(bit)} tarihleri arasında {H.tur_adi(tur).lower()} kullanmak "
                 "istiyorum.")
    d = talep.get("durum")
    if d == "onaylandi":
        kim = ", ".join(x for x in (_kisi(talep.get("karar_veren")),
                                    str(talep.get("karar_zamani") or "")[:16].replace("T", " ")) if x)
        onay = "Programda onaylandı" + (f": {kim}" if kim else ".")
    elif d == "bekliyor":
        onay = "Programda onay bekliyor."
    else:
        onay = f"Programdaki durum: {H.DURUMLAR.get(d, d)}"
    return {"baslik": baslik, "no": belge_no(talep), "calisan": calisan, "izin": izin, "bakiye": bakiye,
            "beyan": beyan, "onay": onay,
            "imzalar": [("İzni isteyen çalışan", _ad(personel)), ("Birim yöneticisi", ""),
                        ("İşveren / işveren vekili", "")]}


def kayit_belgesi_icerik(personel, kisi_talepleri, bugun):
    """Yıllık izin kayıt belgesi: {kunye[], haklar[], izinler[], toplam[]} — yalnız onaylı yıllık izinler."""
    giris = H.tarih(personel.get("ise_giris"))
    b = H.bakiye(personel, kisi_talepleri, bugun)
    haklar = [{"Hizmet yılı": h["kidem"], "Yıllık izne hak kazanılan tarih": H.tr_tarih(h["tarih"]),
               "İşyerindeki çalışma süresi": f"{h['kidem']} yıl", "Hak edilen izin (gün)": h["gun"]}
              for h in H.hak_edisler(giris, H.tarih(personel.get("dogum_tarihi")), bugun,
                                     cikis=H.tarih(personel.get("cikis_tarihi")))]
    izinler = []
    for t in sorted((t for t in kisi_talepleri if t.get("tur") == "yillik" and t.get("durum") == "onaylandi"),
                    key=lambda t: str(t.get("baslangic"))):
        izinler.append({"Belge no": belge_no(t), "İznin başlama tarihi": H.tr_tarih(t.get("baslangic")),
                        "İznin sona ereceği tarih": H.tr_tarih(t.get("bitis")),
                        "İzin günleri sayısı": float(t.get("gun") or 0),
                        "Yol izni günleri sayısı": int(t.get("yol_izni") or 0)})
    kunye = [("Adı soyadı", _ad(personel)), ("Sicil no", personel.get("sicil_no") or "—"),
             ("İşe giriş tarihi", H.tr_tarih(giris)), ("Bölümü", personel.get("departman") or "—"),
             ("İşyerindeki çalışma süresi", calisma_suresi(giris, bugun) if giris else "—")]
    if personel.get("cikis_tarihi"):
        kunye.append(("İşten ayrılış tarihi", H.tr_tarih(personel.get("cikis_tarihi"))))
    toplam = []
    if b["devir"]:
        toplam.append((f"Devreden izin ({H.tr_tarih(personel.get('devir_tarihi'))} itibarıyla)", H.tr_gun(b["devir"])))
    toplam += [("Devirden sonra hak edilen" if b["devir"] else "Hak edilen toplam", H.tr_gun(b["hak_edilen"])),
               ("Kullanılan (onaylı)", H.tr_gun(b["kullanilan"] + b["planlanan"])),
               (f"Kalan ({H.tr_tarih(bugun)})", H.tr_gun(b["kalan"]))]
    return {"kunye": kunye, "haklar": haklar, "izinler": izinler, "toplam": toplam,
            "devir_tarihi": personel.get("devir_tarihi")}


# ── PDF ─────────────────────────────────────────────────────────────
def _stiller():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from shared.utils import pdf_stilleri_turkcele, pdf_turkce_font
    s = getSampleStyleSheet()
    n, b = pdf_turkce_font()
    pdf_stilleri_turkcele(s, n, b)
    return {
        "n": n, "b": b,
        "metin": ParagraphStyle("metin", parent=s["Normal"], fontName=n, fontSize=9.5, leading=13),
        "kalin": ParagraphStyle("kalin", parent=s["Normal"], fontName=b, fontSize=9.5, leading=13),
        "kucuk": ParagraphStyle("kucuk", parent=s["Normal"], fontName=n, fontSize=7.5, leading=10,
                                textColor=colors.HexColor(GRI)),
        "baslik": ParagraphStyle("baslik", parent=s["Normal"], fontName=b, fontSize=15, leading=19,
                                 textColor=colors.HexColor(LACIVERT), spaceBefore=2),
        "bolum": ParagraphStyle("bolum", parent=s["Normal"], fontName=b, fontSize=9.5, leading=15,
                                textColor=colors.white, backColor=colors.HexColor(LACIVERT), leftIndent=0,
                                borderPadding=(2, 6, 2, 6), spaceBefore=9, spaceAfter=3),
    }


def _antet(sirket, st, genislik):
    """Logo solda, künye sağda; altında turuncu çizgi."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, Table, TableStyle
    import html as _h
    satir = [f"<b>{_h.escape(sirket.get('unvan') or '')}</b>"]
    if sirket.get("adres"):
        satir.append(_h.escape(sirket["adres"]))
    vd = " · ".join(x for x in (f"V.D.: {sirket['vd']}" if sirket.get("vd") else "",
                                f"VKN: {sirket['vkn']}" if sirket.get("vkn") else "",
                                f"MERSİS: {sirket['mersis']}" if sirket.get("mersis") else "") if x)
    if vd:
        satir.append(vd)
    il = " · ".join(x for x in (sirket.get("tel"), sirket.get("mail"), sirket.get("web")) if x)
    if il:
        satir.append(_h.escape(il))
    from reportlab.lib.styles import ParagraphStyle
    sag = Paragraph("<br/>".join(satir), ParagraphStyle("antet", parent=st["kucuk"], fontSize=8, leading=10.5,
                                                         alignment=2, textColor=colors.HexColor(LACIVERT)))
    logo = ""
    if os.path.exists(LOGO):
        logo = Image(LOGO, width=34 * mm, height=34 * mm * LOGO_ORAN)
    t = Table([[logo, sag]], colWidths=[50 * mm, genislik - 50 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "LEFT"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("LINEBELOW", (0, 0), (-1, 0), 1.6, colors.HexColor(TURUNCU)),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _ikili(satirlar, st, genislik, sol=58):
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle
    import html as _h
    t = Table([[Paragraph(_h.escape(str(a)), st["kalin"]), Paragraph(_h.escape(str(b)), st["metin"])]
               for a, b in satirlar], colWidths=[sol * mm, genislik - sol * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(ACIK)),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
    return t


def _alt_bilgi(metin, font):
    def ciz(canvas, doc):
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor(GRI))
        canvas.drawString(doc.leftMargin, 9 * mm, metin)
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 9 * mm, f"Sayfa {doc.page}")
        canvas.restoreState()
    return ciz


def _simdi():
    return datetime.now(timezone(timedelta(hours=3)))


def izin_formu_pdf(talep, personel, kisi_talepleri, bugun, cumartesi=False, sirket=None):
    """Tek izin için A4 antetli izin formu (bytes)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    import html as _h
    if sirket is None:
        from shared.sirket import sirket_bilgi
        sirket = sirket_bilgi()
    ic = form_icerik(talep, personel, kisi_talepleri, bugun, cumartesi)
    st = _stiller()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=12 * mm, bottomMargin=16 * mm, leftMargin=16 * mm,
                            rightMargin=16 * mm, title=f"{ic['no']} {ic['baslik']}",
                            author=sirket.get("unvan") or "")
    g = A4[0] - 32 * mm
    el = [_antet(sirket, st, g), Spacer(1, 7)]
    ust = Table([[Paragraph(ic["baslik"], st["baslik"]),
                  Paragraph(f"Belge no: <b>{ic['no']}</b><br/>Düzenleme: {_simdi().strftime('%d.%m.%Y %H:%M')}",
                            st["kucuk"])]], colWidths=[g - 52 * mm, 52 * mm])
    ust.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    el += [ust, Paragraph("ÇALIŞAN BİLGİLERİ", st["bolum"]), _ikili(ic["calisan"], st, g),
           Paragraph("İZİN BİLGİLERİ", st["bolum"]), _ikili(ic["izin"], st, g)]
    if ic["bakiye"]:
        el += [Paragraph("YILLIK İZİN DURUMU", st["bolum"]), _ikili(ic["bakiye"], st, g)]
    el += [Spacer(1, 8), Paragraph(_h.escape(ic["beyan"]), st["metin"]), Spacer(1, 4),
           Paragraph(_h.escape(ic["onay"]), st["kucuk"]), Spacer(1, 10)]
    kutu = []
    for rol, ad in ic["imzalar"]:
        kutu.append([Paragraph(f"<b>{_h.escape(rol)}</b>", st["metin"]),
                     Paragraph(f"Adı soyadı: {_h.escape(ad) if ad else '.' * 30}", st["kucuk"]),
                     Paragraph("Tarih: ....../....../..........", st["kucuk"]),
                     Spacer(1, 26), Paragraph("İmza", st["kucuk"])])
    imza = Table([kutu], colWidths=[g / 3] * 3)
    imza.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                              ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    el.append(KeepTogether([Paragraph("ONAY", st["bolum"]), imza]))
    alt = f"{ic['no']} · İş Kanunu md. 53–60 ve Yıllık Ücretli İzin Yönetmeliği uyarınca · özlük dosyasında saklanır"
    doc.build(el, onFirstPage=_alt_bilgi(alt, st["n"]), onLaterPages=_alt_bilgi(alt, st["n"]))
    return buf.getvalue()


def kayit_belgesi_pdf(personel, kisi_talepleri, bugun, sirket=None):
    """Çalışanın yıllık izin kayıt belgesi (A4 yatay, bytes) — Yönetmelik md. 20."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    import html as _h
    if sirket is None:
        from shared.sirket import sirket_bilgi
        sirket = sirket_bilgi()
    ic = kayit_belgesi_icerik(personel, kisi_talepleri, bugun)
    st = _stiller()
    buf = BytesIO()
    sayfa = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=sayfa, topMargin=9 * mm, bottomMargin=14 * mm, leftMargin=14 * mm,
                            rightMargin=14 * mm, title=f"Yıllık izin kayıt belgesi · {_ad(personel)}",
                            author=sirket.get("unvan") or "")
    g = sayfa[0] - 28 * mm
    el = [_antet(sirket, st, g), Spacer(1, 6), Paragraph("YILLIK ÜCRETLİ İZİN KAYIT BELGESİ", st["baslik"]),
          Paragraph("Yıllık Ücretli İzin Yönetmeliği md. 20 uyarınca tutulur.", st["kucuk"]), Spacer(1, 4)]
    # Künye solda, özet (devir · hak · kullanılan · kalan) sağda
    el.append(Table([[_ikili(ic["kunye"], st, g / 2 - 4 * mm, 50), _ikili(ic["toplam"], st, g / 2 - 4 * mm, 62)]],
                    colWidths=[g / 2, g / 2], style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
                                                       ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                                       ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                                                       ("VALIGN", (0, 0), (-1, -1), "TOP")]))

    def _tablo(satirlar, kolonlar, genislikler, imza=False):
        bas = [Paragraph(f"<b>{_h.escape(k)}</b>", st["kucuk"]) for k in kolonlar] + \
              ([Paragraph("<b>İşçinin imzası</b>", st["kucuk"])] if imza else [])
        govde = [[Paragraph(_h.escape(H.tr_gun(r[k]).replace(" gün", "") if isinstance(r[k], float)
                                     else str(r[k])), st["metin"]) for k in kolonlar] + ([""] if imza else [])
                 for r in satirlar] or [[Paragraph("Kayıt yok", st["kucuk"])] + [""] * (len(kolonlar) - 1 + imza)]
        t = Table([bas] + govde, colWidths=genislikler, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ACIK)),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 3 if not imza else 7),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3 if not imza else 7)]))
        return t
    el.append(Paragraph("YILLIK İZNE HAK KAZANMA", st["bolum"]))
    k1 = ["Hizmet yılı", "Yıllık izne hak kazanılan tarih", "İşyerindeki çalışma süresi", "Hak edilen izin (gün)"]
    el.append(_tablo(ic["haklar"], k1, [g / 4] * 4))
    el.append(Paragraph("KULLANILAN YILLIK İZİNLER", st["bolum"]))
    k2 = ["Belge no", "İznin başlama tarihi", "İznin sona ereceği tarih", "İzin günleri sayısı",
          "Yol izni günleri sayısı"]
    el.append(_tablo(ic["izinler"], k2, [g * 0.16, g * 0.16, g * 0.16, g * 0.14, g * 0.14, g * 0.24], imza=True))
    imza = Table([[Paragraph("<b>İşveren / işveren vekili</b><br/>Adı soyadı, tarih, imza", st["kucuk"]),
                   Paragraph("<b>Çalışan</b><br/>Okudum, kayıtlar doğrudur. Tarih, imza", st["kucuk"])]],
                 colWidths=[g / 2, g / 2], rowHeights=[16 * mm])
    imza.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                              ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                              ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [Spacer(1, 5), KeepTogether([imza])]
    alt = (f"{_ad(personel)} · yıllık izin kayıt belgesi · {_simdi().strftime('%d.%m.%Y %H:%M')} · "
           "Yalnız onaylı yıllık izinler; mazeret, rapor ve ücretsiz izinler bu belgeye girmez.")
    doc.build(el, onFirstPage=_alt_bilgi(alt, st["n"]), onLaterPages=_alt_bilgi(alt, st["n"]))
    return buf.getvalue()

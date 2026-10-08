# -*- coding: utf-8 -*-
"""Çalışan izinleri — saf hesaplar (Ekim 2026). Streamlit'e ve veritabanına bağlı değil; tamamı test edilir.

Yasal dayanak (4857 sayılı İş Kanunu):
  · md. 53 — yıllık ücretli izin: hizmeti 1–5 yıl (5 dahil) 14, 5'ten fazla 15'ten az 20, 15 yıl ve
    üstü 26 gün. 18 yaş ve küçükler ile 50 yaş ve büyüklere 20 günden az verilemez. Hak, her işe
    giriş yıl dönümünde doğar (deneme süresi dahil).
  · md. 56 — izin süresine rastlayan hafta tatili ve resmi tatil günleri izinden sayılmaz. Cumartesi
    çalışılan iş yerinde Cumartesi iş günüdür (şirket ayarı: cumartesi).
  · Ek md. 2 — mazeret izinleri (ücretli): evlilik, evlat edinme, yakın ölümü 3 gün; babalık 5 gün;
    engelli / süreğen hastalığı olan çocuğun tedavisi yılda 10 güne kadar. Yıllık izinden düşülmez.
Kullanılmayan yıllık izin yanmaz, birikir. Arife ve 28 Ekim öğleden sonra yarım gün tatildir: izne
denk gelirse 0,5 gün sayılır.

Tutarlar talep anında hesaplanıp kayda yazılır (kayıt "gun"); ayar sonradan değişse de eski kayıt
değişmez. Bakiye = devir + hak edilen − onaylı yıllık izinler.
"""
from datetime import date, timedelta

from shared import tatil as T

# ── İzin türleri ────────────────────────────────────────────────────
# kod → ad, yıllıktan düşer mi, ücretli mi, yasal üst sınır (iş günü; None sınırsız),
#        sınır olay başına mı yıllık mı, açıklama
TURLER = {
    "yillik":       dict(ad="Yıllık izin", duser=True, ucretli=True, sinir=None, kapsam=None,
                         aciklama="Yıllık ücretli izin; bakiyeden düşer."),
    "evlilik":      dict(ad="Evlilik izni", duser=False, ucretli=True, sinir=3, kapsam="olay",
                         aciklama="Çalışanın evlenmesi: 3 gün ücretli."),
    "babalik":      dict(ad="Babalık izni", duser=False, ucretli=True, sinir=5, kapsam="olay",
                         aciklama="Eşin doğum yapması: 5 gün ücretli."),
    "olum":         dict(ad="Vefat izni", duser=False, ucretli=True, sinir=3, kapsam="olay",
                         aciklama="Anne, baba, eş, kardeş veya çocuğun ölümü: 3 gün ücretli."),
    "evlat_edinme": dict(ad="Evlat edinme izni", duser=False, ucretli=True, sinir=3, kapsam="olay",
                         aciklama="3 yaşından küçük çocuğu evlat edinme: 3 gün ücretli."),
    "engelli_cocuk": dict(ad="Engelli çocuk tedavi izni", duser=False, ucretli=True, sinir=10, kapsam="yil",
                          aciklama="Engelli ya da süreğen hastalığı olan çocuğun tedavisi: yılda 10 güne kadar."),
    "rapor":        dict(ad="Sağlık raporu", duser=False, ucretli=False, sinir=None, kapsam=None,
                         aciklama="Hekim raporu; ödeme SGK'dan. Tanı yazılmaz, yalnız tarih."),
    "dogum":        dict(ad="Doğum izni", duser=False, ucretli=False, sinir=None, kapsam=None,
                         aciklama="Doğum öncesi ve sonrası analık izni (16 hafta; ödeme SGK'dan)."),
    "idari":        dict(ad="İdari izin", duser=False, ucretli=True, sinir=None, kapsam=None,
                         aciklama="Şirket kararıyla verilen ücretli izin; bakiyeden düşmez."),
    "ucretsiz":     dict(ad="Ücretsiz izin", duser=False, ucretli=False, sinir=None, kapsam=None,
                         aciklama="Ücret ödenmez; bordroda eksik gün olarak bildirilir."),
}
TUR_SIRA = list(TURLER)

DURUMLAR = {"bekliyor": "Onay bekliyor", "onaylandi": "Onaylandı", "reddedildi": "Reddedildi",
            "iptal": "İptal edildi"}
ETKIN = ("bekliyor", "onaylandi")          # çakışma ve bakiye hesabına giren durumlar


def tur_adi(kod):
    return TURLER.get(kod, {}).get("ad", str(kod or ""))


# ── Tarih yardımcıları ──────────────────────────────────────────────
def tarih(v):
    """date | 'YYYY-MM-DD…' | None → date | None."""
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def yildonumu(d, n):
    """d'den n yıl sonrası; 29 Şubat artık olmayan yılda 28 Şubat."""
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def yas(dogum, gun):
    """gun tarihinde tamamlanmış yaş."""
    return gun.year - dogum.year - ((gun.month, gun.day) < (dogum.month, dogum.day))


def kidem(ise_giris, gun):
    """(tam yıl, kalan ay) — gun tarihinde."""
    if not ise_giris or gun < ise_giris:
        return 0, 0
    ay = (gun.year - ise_giris.year) * 12 + gun.month - ise_giris.month - (gun.day < ise_giris.day)
    return ay // 12, ay % 12


# ── Gün sayımı ──────────────────────────────────────────────────────
def gun_degeri(gun, cumartesi=False):
    """Bir günün izinden düşen değeri: 0 (Pazar / çalışılmayan Cumartesi / resmi tatil), 0,5 (yarım
    gün tatil: arife, 28 Ekim) ya da 1."""
    if gun.weekday() == 6 or (gun.weekday() == 5 and not cumartesi):
        return 0.0
    t = T.tatil(gun)
    if t:
        return max(0.0, 1.0 - t[1])
    return 1.0


def gun_dokumu(bas, bit, cumartesi=False):
    """[(tarih, değer, not)] — her takvim günü için neden sayıldığı / sayılmadığı."""
    out = []
    g = bas
    while g <= bit:
        t = T.tatil(g)
        if g.weekday() == 6:
            n = "Pazar"
        elif g.weekday() == 5 and not cumartesi:
            n = "Cumartesi"
        elif t:
            n = t[0]
        else:
            n = ""
        out.append((g, gun_degeri(g, cumartesi), n))
        g += timedelta(days=1)
    return out


def izin_gunu(bas, bit, cumartesi=False, yarim=False):
    """İzinden düşecek iş günü. yarim: tek günlük yarım gün izin (en çok 0,5)."""
    if not bas or not bit or bit < bas:
        return 0.0
    if yarim:
        return min(0.5, gun_degeri(bas, cumartesi)) if bas == bit else 0.0
    return sum(v for _g, v, _n in gun_dokumu(bas, bit, cumartesi))


def takvim_gunu(bas, bit):
    return (bit - bas).days + 1 if bas and bit and bit >= bas else 0


def bilinmeyen_yillar(bas, bit):
    """Dini bayram tarihleri tanımlı olmayan yıllar (sayım eksik olabilir)."""
    if not bas or not bit:
        return []
    return [y for y in range(bas.year, bit.year + 1) if not T.bilinen_yil(y)]


# ── Yıllık izin hakkı ───────────────────────────────────────────────
def yillik_hak(kidem_yil, yas_=None):
    """Tamamlanan hizmet yılına göre yıllık izin günü (md. 53)."""
    if kidem_yil < 1:
        return 0
    gun = 14 if kidem_yil <= 5 else 20 if kidem_yil < 15 else 26
    if yas_ is not None and (yas_ <= 18 or yas_ >= 50):
        gun = max(gun, 20)
    return gun


def hak_edisler(ise_giris, dogum=None, son=None, sonra=None, cikis=None):
    """İşe giriş yıl dönümlerinde doğan haklar: [{tarih, kidem, yas, gun}].
    sonra < tarih <= son (sonra None ise baştan); işten çıkış tarihinden sonrakiler alınmaz."""
    out = []
    if not ise_giris or not son:
        return out
    n = 1
    while True:
        t = yildonumu(ise_giris, n)
        if t > son or (cikis and t > cikis):
            break
        if sonra is None or t > sonra:
            y = yas(dogum, t) if dogum else None
            out.append({"tarih": t, "kidem": n, "yas": y, "gun": yillik_hak(n, y)})
        n += 1
    return out


def sonraki_hak(ise_giris, dogum, bugun):
    """Bugünden sonraki ilk hak ediş: {tarih, kidem, gun}."""
    if not ise_giris:
        return None
    n = max(1, kidem(ise_giris, bugun)[0] + 1)
    t = yildonumu(ise_giris, n)
    while t <= bugun:
        n += 1
        t = yildonumu(ise_giris, n)
    y = yas(dogum, t) if dogum else None
    return {"tarih": t, "kidem": n, "gun": yillik_hak(n, y)}


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def bakiye(personel, talepler, bugun):
    """Yıllık izin bakiyesi.
    personel: {ise_giris, dogum_tarihi, devir_tarihi, devir_gun, cikis_tarihi}
    talepler: bu kişinin talepleri ({tur, durum, baslangic, gun})
    Döner: devir, hak_edilen, kullanilan (başlamış), planlanan (ileri tarihli onaylı), bekleyen,
           kalan (= devir + hak − kullanılan − planlanan), kullanilabilir (= kalan − bekleyen),
           hak_basladi, sonraki, kidem (yıl, ay), bu_yil_hak."""
    giris = tarih(personel.get("ise_giris"))
    dogum = tarih(personel.get("dogum_tarihi"))
    devir_t = tarih(personel.get("devir_tarihi"))
    cikis = tarih(personel.get("cikis_tarihi"))
    devir = _f(personel.get("devir_gun")) if devir_t else 0.0
    son = min(bugun, cikis) if cikis else bugun
    haklar = hak_edisler(giris, dogum, son, sonra=devir_t, cikis=cikis)
    hak = float(sum(h["gun"] for h in haklar))
    kullanilan = planlanan = bekleyen = 0.0
    for t in talepler or []:
        if t.get("tur") != "yillik":
            continue
        b = tarih(t.get("baslangic"))
        if not b or (devir_t and b <= devir_t):
            continue                                  # devir bakiyesine zaten yansımış
        g = _f(t.get("gun"))
        if t.get("durum") == "onaylandi":
            if b <= bugun:
                kullanilan += g
            else:
                planlanan += g
        elif t.get("durum") == "bekliyor":
            bekleyen += g
    kalan = devir + hak - kullanilan - planlanan
    ky = kidem(giris, son) if giris else (0, 0)
    bu_yil = yillik_hak(ky[0], yas(dogum, son) if dogum else None) if giris else 0
    return {"devir": devir, "hak_edilen": hak, "kullanilan": kullanilan, "planlanan": planlanan,
            "bekleyen": bekleyen, "kalan": kalan, "kullanilabilir": kalan - bekleyen,
            "hak_basladi": bool(giris and ky[0] >= 1), "kidem": ky, "bu_yil_hak": bu_yil,
            "sonraki": None if cikis else sonraki_hak(giris, dogum, bugun), "haklar": haklar}


# ── Talep denetimi ──────────────────────────────────────────────────
def cakisanlar(bas, bit, talepler, haric_id=None):
    """Aynı kişinin bu aralıkla kesişen etkin (bekleyen / onaylı) talepleri."""
    out = []
    for t in talepler or []:
        if t.get("durum") not in ETKIN or (haric_id is not None and t.get("id") == haric_id):
            continue
        b, e = tarih(t.get("baslangic")), tarih(t.get("bitis"))
        if b and e and b <= bit and bas <= e:
            out.append(t)
    return out


def denetle(tur, bas, bit, gun, personel, kisi_talepleri, bugun, yarim=False, ayni_bolum=None):
    """Kaydetmeden önce: (hatalar, uyarılar). Hata varsa kaydedilmez; uyarı gösterilir, kayıt serbest.
    ayni_bolum: aynı departmandaki diğer kişilerin etkin talepleri [{personel_ad, baslangic, bitis}]."""
    hatalar, uyarilar = [], []
    if tur not in TURLER:
        hatalar.append("İzin türü seçilmedi.")
        return hatalar, uyarilar
    if not bas or not bit:
        hatalar.append("Başlangıç ve bitiş tarihi gerekli.")
        return hatalar, uyarilar
    if bit < bas:
        hatalar.append("Bitiş tarihi başlangıçtan önce olamaz.")
        return hatalar, uyarilar
    if yarim and bas != bit:
        hatalar.append("Yarım gün izin tek bir gün için seçilebilir.")
    if gun <= 0 and TURLER[tur]["duser"] and not (yarim and bas != bit):
        hatalar.append("Seçilen günlerin hepsi hafta sonu ya da resmi tatil; izinden düşecek gün yok.")
    giris = tarih(personel.get("ise_giris"))
    if giris and bas < giris:
        hatalar.append(f"İşe giriş tarihinden ({tr_tarih(giris)}) önce izin olamaz.")
    cikis = tarih(personel.get("cikis_tarihi"))
    if cikis and bit > cikis:
        hatalar.append(f"İşten çıkış tarihinden ({tr_tarih(cikis)}) sonra izin olamaz.")
    for c in cakisanlar(bas, bit, kisi_talepleri):
        hatalar.append(f"Bu tarihlerde zaten {DURUMLAR[c['durum']].lower()} bir izin var: "
                       f"{tur_adi(c.get('tur'))}, {tr_tarih(c.get('baslangic'))} – {tr_tarih(c.get('bitis'))}.")
    if hatalar:
        return hatalar, uyarilar

    bil = bilinmeyen_yillar(bas, bit)
    if bil:
        uyarilar.append(f"{', '.join(map(str, bil))} yılının bayram tarihleri programda henüz yok; "
                        "bayrama denk gelen günler izinden düşülmüş olabilir.")
    if TURLER[tur]["duser"]:
        if not giris:
            uyarilar.append("Personel kartında işe giriş tarihi yok; bakiye hesaplanamıyor.")
        else:
            b = bakiye(personel, kisi_talepleri, bugun)
            if not b["hak_basladi"] and b["devir"] <= 0:
                s = b["sonraki"]
                uyarilar.append("Yıllık izin hakkı henüz doğmadı"
                                + (f" (ilk hak {tr_tarih(s['tarih'])}, {s['gun']} gün)" if s else "")
                                + "; onaylanırsa avans izin olur.")
            elif gun > b["kullanilabilir"] + 1e-9:
                uyarilar.append(f"Kalan izin {tr_gun(b['kullanilabilir'])}; bu talep {tr_gun(gun)}. "
                                f"Onaylanırsa {tr_gun(gun - b['kullanilabilir'])} avans izin olur.")
    sinir, kapsam = TURLER[tur]["sinir"], TURLER[tur]["kapsam"]
    if sinir:
        if kapsam == "olay" and gun > sinir:
            uyarilar.append(f"{tur_adi(tur)} yasal olarak {sinir} gün; bu talep {tr_gun(gun)}.")
        elif kapsam == "yil":
            onceki = sum(_f(t.get("gun")) for t in kisi_talepleri or []
                         if t.get("tur") == tur and t.get("durum") in ETKIN
                         and (tarih(t.get("baslangic")) or bas).year == bas.year)
            if onceki + gun > sinir:
                uyarilar.append(f"{tur_adi(tur)} yılda en çok {sinir} gün; bu yıl {tr_gun(onceki)} kullanıldı, "
                                f"bu talep {tr_gun(gun)}.")
    if bas < bugun:
        uyarilar.append("Geçmiş tarihli izin: kayıt amaçlı giriliyor.")
    for d in ayni_bolum or []:
        uyarilar.append(f"Aynı bölümden {d.get('personel_ad')} da izinli: "
                        f"{tr_tarih(d.get('baslangic'))} – {tr_tarih(d.get('bitis'))}.")
    return hatalar, uyarilar


def ayni_bolumdekiler(bas, bit, kisi, bolum, personeller, talepler):
    """Aynı departmandaki diğer kişilerin bu aralıkla kesişen etkin talepleri (ad eklenmiş)."""
    if not bolum:
        return []
    ad = {p["kod"]: p.get("ad") or p["kod"] for p in personeller or []}
    ayni = {p["kod"] for p in personeller or [] if p.get("departman") == bolum and p["kod"] != kisi}
    out = []
    for t in talepler or []:
        if t.get("personel") in ayni and cakisanlar(bas, bit, [t]):
            out.append(dict(t, personel_ad=ad.get(t["personel"], t["personel"])))
    return out


# ── Takvim ve rapor ─────────────────────────────────────────────────
def ay_gunleri(yil, ay):
    g = date(yil, ay, 1)
    out = []
    while g.month == ay:
        out.append(g)
        g += timedelta(days=1)
    return out


def takvim(yil, ay, personeller, talepler):
    """Ay takvimi: [{kod, ad, gunler: {date: (tur, durum)}}] — yalnız etkin talepler; aynı güne
    iki kayıt düşmez (çakışma denetimi engeller)."""
    gunler = ay_gunleri(yil, ay)
    ilk, son = gunler[0], gunler[-1]
    satirlar = []
    for p in personeller:
        harita = {}
        for t in talepler or []:
            if t.get("personel") != p["kod"] or t.get("durum") not in ETKIN:
                continue
            b, e = tarih(t.get("baslangic")), tarih(t.get("bitis"))
            if not b or not e or e < ilk or b > son:
                continue
            g = max(b, ilk)
            while g <= min(e, son):
                harita[g] = (t.get("tur"), t.get("durum"))
                g += timedelta(days=1)
        satirlar.append({"kod": p["kod"], "ad": p.get("ad") or p["kod"], "gunler": harita})
    return satirlar


def donem_dokumu(talepler, bas, bit, personel_ad, cumartesi=False):
    """Bordro dökümü: dönemle kesişen ONAYLI izinlerin dönem içine düşen kısmı.
    [{Personel, Tür, Başlangıç, Bitiş, İş günü, Takvim günü, Ücretli, Yol izni (ücretsiz)}] — İş günü dönem içinden
    yeniden sayılır (dönem sınırını aşan izin ikiye bölünür)."""
    out = []
    for t in talepler or []:
        if t.get("durum") != "onaylandi":
            continue
        b, e = tarih(t.get("baslangic")), tarih(t.get("bitis"))
        if not b or not e or e < bas or b > bit:
            continue
        kb, ke = max(b, bas), min(e, bit)
        yarim = bool(t.get("yarim_gun"))
        out.append({"Personel": personel_ad.get(t.get("personel"), t.get("personel")),
                    "Tür": tur_adi(t.get("tur")), "Başlangıç": kb, "Bitiş": ke,
                    "İş günü": _f(t.get("gun")) if (b == kb and e == ke) else izin_gunu(kb, ke, cumartesi, yarim),
                    "Takvim günü": takvim_gunu(kb, ke),
                    "Ücretli": "Evet" if TURLER.get(t.get("tur"), {}).get("ucretli") else "Hayır",
                    # yol izni iznin bitişinden sonra kullanılır: bitişin düştüğü dönemde yazılır
                    "Yol izni (ücretsiz)": int(t.get("yol_izni") or 0) if e <= bit else 0})
    out.sort(key=lambda r: (str(r["Personel"]), r["Başlangıç"]))
    return out


# ── Biçim ───────────────────────────────────────────────────────────
_ALFABE = "0123456789aâbcçdefgğhıiîjklmnoöprsştuüûvyz"


def tr_sira(s):
    """Türkçe alfabe sırası için anahtar ('İbrahim' Ç'den sonra değil I'dan sonra gelir)."""
    k = str(s or "").replace("İ", "i").replace("I", "ı").lower()
    return [_ALFABE.find(ch) if ch in _ALFABE else 100 + ord(ch) for ch in k]


_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
          "Kasım", "Aralık"]


def ay_adi(ay):
    return _AYLAR[ay - 1]


def tr_tarih(v):
    d = tarih(v)
    return d.strftime("%d.%m.%Y") if d else "—"


def tr_gun(g):
    """3 → '3 gün', 2.5 → '2,5 gün', -1.5 → '-1,5 gün'."""
    g = round(float(g or 0) * 2) / 2
    s = str(int(g)) if g == int(g) else f"{g:.1f}".replace(".", ",")
    return f"{s} gün"


# ── Bildirim metinleri ──────────────────────────────────────────────
def talep_ozeti(t):
    """'Yıllık izin · 12.10.2026 – 16.10.2026 · 5 gün' (yarım gün izinde '(yarım gün)')."""
    ara = tr_tarih(t.get("baslangic")) if t.get("baslangic") == t.get("bitis") else \
        f"{tr_tarih(t.get('baslangic'))} – {tr_tarih(t.get('bitis'))}"
    return f"{tur_adi(t.get('tur'))} · {ara} · {tr_gun(t.get('gun'))}" + (" (yarım gün)" if t.get("yarim_gun") else "")


def bildirim_yeni(ad, t):
    return f"{ad} izin talebi gönderdi: {talep_ozeti(t)}. Onay için İzinler sayfası."


def bildirim_karar(t, onay, kim_ad, notu=""):
    s = "onaylandı" if onay else "reddedildi"
    return f"İzin talebin {s}: {talep_ozeti(t)}" + (f". Not: {notu}" if notu else "") + f" ({kim_ad})"


def bildirim_iptal(t, kim_ad, notu=""):
    return f"İznin iptal edildi: {talep_ozeti(t)}" + (f". Not: {notu}" if notu else "") + f" ({kim_ad})"


def mail_yeni(ad, t):
    """(konu, html) — izin yöneticilerine."""
    from shared.eposta import _e, baglanti, sablon
    govde = (f"<p><b>{_e(ad)}</b> izin talebi gönderdi.</p>"
             f"<p style='margin:2px 0'><b>İzin:</b> {_e(talep_ozeti(t))}</p>"
             + (f"<p style='margin:2px 0'><b>Açıklama:</b> {_e(t.get('aciklama'))}</p>" if t.get("aciklama") else ""))
    return (f"[KAYRAN İzin] {ad} · {tur_adi(t.get('tur'))}",
            sablon("Yeni izin talebi", govde, "Talebi aç", baglanti("izin")))


def mail_karar(t, onay, kim_ad, notu=""):
    """(konu, html) — talep sahibine."""
    from shared.eposta import _e, baglanti, sablon
    s = "onaylandı" if onay else "reddedildi"
    govde = (f"<p>İzin talebin <b>{s}</b>.</p>"
             f"<p style='margin:2px 0'><b>İzin:</b> {_e(talep_ozeti(t))}</p>"
             f"<p style='margin:2px 0'><b>Karar veren:</b> {_e(kim_ad)}</p>"
             + (f"<p style='margin:2px 0'><b>Not:</b> {_e(notu)}</p>" if notu else ""))
    return (f"[KAYRAN İzin] Talebin {s}", sablon(f"İzin talebin {s}", govde, "İzinlerimi aç", baglanti("izin")))


# ── Bakiye raporu ───────────────────────────────────────────────────
def bakiye_tablosu(personeller, talepler, bugun):
    """Rapor satırları (çıkmış personel en altta)."""
    out = []
    for p in sorted(personeller or [], key=lambda p: (bool(p.get("cikis_tarihi")), tr_sira(p.get("ad") or p["kod"]))):
        kt = [t for t in talepler or [] if t.get("personel") == p["kod"]]
        b = bakiye(p, kt, bugun)
        s = b["sonraki"]
        yil = date(bugun.year, 1, 1)
        diger = sum(_f(t.get("gun")) for t in kt if t.get("durum") == "onaylandi" and t.get("tur") != "yillik"
                    and (tarih(t.get("baslangic")) or yil) >= yil)
        ad = (p.get("ad") or p["kod"]) + (" (ayrıldı)" if p.get("cikis_tarihi") else "")
        out.append({"_id": p["kod"], "Personel": ad, "Bölüm": p.get("departman") or "",
                    "İşe giriş": tr_tarih(p.get("ise_giris")),
                    "Kıdem": f"{b['kidem'][0]} yıl {b['kidem'][1]} ay" if p.get("ise_giris") else "—",
                    "Yıllık hak": b["bu_yil_hak"], "Devir": b["devir"], "Hak edilen": b["hak_edilen"],
                    "Kullanılan": b["kullanilan"], "Planlanan": b["planlanan"], "Bekleyen": b["bekleyen"],
                    "Kalan": b["kalan"], f"Diğer izin {bugun.year}": diger,
                    "Sonraki hak": f"{tr_tarih(s['tarih'])} · {s['gun']} gün" if s else "—"})
    return out


# ── Kart bilgilendirme e-postası (Ekim 2026) ────────────────────────
# Kart ilk açıldığında çalışana kendiliğinden gider; o an adresi yoksa karta adres ilk eklendiğinde.
# Bir kez gider (personel.bilgi_zamani); sonraki düzeltmelerde gitmez, kartta "tekrar gönder" vardır.
def bilgi_adresi(personel, adresler):
    """Kartın e-postası; yoksa Kullanıcı yönetiminde kayıtlı adres; geçersizse ''."""
    from shared.eposta import adres_gecerli_mi
    for a in (personel.get("eposta"), (adresler or {}).get(str(personel.get("kod") or "").lower())):
        a = str(a or "").strip()
        if adres_gecerli_mi(a):
            return a
    return ""


def bilgi_gerekli(personel, adresler):
    """Kaydedilen kart için bilgilendirme e-postası şimdi gitmeli mi: daha önce gitmemiş, çalışıyor ve
    adres var."""
    return (not personel.get("bilgi_zamani") and not personel.get("cikis_tarihi")
            and bool(bilgi_adresi(personel, adresler)))


def bilgi_durumu(personel, adresler):
    """Personel listesinde: 'Gönderildi 08.10.2026' · 'Adres yok' · 'Gönderilmedi' · 'Ayrıldı'."""
    if personel.get("bilgi_zamani"):
        return "Gönderildi " + tr_tarih(personel["bilgi_zamani"])
    if personel.get("cikis_tarihi"):
        return "Ayrıldı"
    return "Gönderilmedi" if bilgi_adresi(personel, adresler) else "Adres yok"


LOGO_CID = "g5f-logo"


def mail_bilgilendirme(personel, kisi_talepleri, bugun, yonetici_ad=""):
    """(konu, html) — çalışana: kartındaki bilgiler, izin bakiyesi ve İzinler sayfasını kullanma adımları.
    Logo gövdeye gömülü (cid); parola yazılmaz."""
    from shared.eposta import _e, baglanti
    b = bakiye(personel, kisi_talepleri, bugun)
    s = b["sonraki"]
    ad = personel.get("ad") or personel.get("kod")
    satirlar = [("Adı soyadı", ad), ("Sicil no", personel.get("sicil_no") or "—"),
                ("Bölümü", personel.get("departman") or "—"), ("İşe giriş tarihi", tr_tarih(personel.get("ise_giris"))),
                ("Kıdem", f"{b['kidem'][0]} yıl {b['kidem'][1]} ay"), ("Yıllık izin hakkı", f"{b['bu_yil_hak']} gün"),
                ("Kalan yıllık izin", tr_gun(b["kalan"]) + f" ({tr_tarih(bugun)} itibarıyla)"),
                ("Sonraki hak ediş", f"{tr_tarih(s['tarih'])} · {s['gun']} gün" if s else "—")]
    tablo = "".join(
        f"<tr><td style='padding:6px 10px;background:#F1F5F9;border:1px solid #E2E8F0;font-weight:600;"
        f"white-space:nowrap'>{_e(a)}</td><td style='padding:6px 10px;border:1px solid #E2E8F0'>{_e(v)}</td></tr>"
        for a, v in satirlar)
    adimlar = "".join(f"<li style='margin:3px 0'>{x}</li>" for x in (
        "Programa giriş yapın (kullanıcı adınız ve parolanız size ayrıca iletildi).",
        "Sağ üstte adınıza, telefonda alttaki <b>Ben</b> düğmesine dokunun ve <b>İzinler</b>'i seçin.",
        "İzin türünü ve tarihleri seçin; program izinden düşecek günü ve işe dönüş tarihinizi gösterir. "
        "<b>Talep gönder</b>'e basın.",
        "Onaylanınca bildirim alırsınız. Onaylı iznin yanındaki <b>İzin formu</b> ile antetli formu yazdırıp "
        "imzalayın."))
    kim = f"{_e(yonetici_ad)} ile görüşün" if yonetici_ad else "yöneticinize bildirin"
    url = baglanti("izin")
    html = (
        "<div style='font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#0f172a;line-height:1.55;"
        "max-width:620px'>"
        f"<img src='cid:{LOGO_CID}' alt='G5F' width='120' style='display:block;margin:0 0 14px'>"
        f"<h2 style='margin:0 0 12px;font-size:20px;color:#1B2632'>Personel izin kartınız açıldı</h2>"
        f"<p>Merhaba {_e(ad)},</p>"
        "<p>Yıllık izinleriniz ve izin talepleriniz artık şirket programı üzerinden takip ediliyor. "
        "Kartınıza işlenen bilgiler aşağıdadır:</p>"
        f"<table style='border-collapse:collapse;font-size:14px;margin:6px 0 12px'>{tablo}</table>"
        f"<p style='font-size:13px;color:#475569'>Bilgilerde hata varsa {kim}; düzeltildikten sonra "
        "bakiyeniz kendiliğinden güncellenir.</p>"
        "<h3 style='margin:18px 0 6px;font-size:16px;color:#1B2632'>İzin nasıl istenir?</h3>"
        f"<ol style='margin:0 0 6px;padding-left:20px'>{adimlar}</ol>"
        f"<p style='margin:20px 0 6px'><a href='{_e(url)}' style='background:#E5870B;color:#fff;text-decoration:none;"
        "padding:10px 18px;border-radius:8px;font-weight:600;display:inline-block'>İzinler sayfasını aç</a></p>"
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:18px 0 10px'>"
        "<div style='font-size:12px;color:#94a3b8'>Bu e-posta personel kartınız açıldığı için bir kez gönderildi. "
        "Yıllık izin hakları 4857 sayılı İş Kanunu md. 53'e göre hesaplanır.</div></div>")
    return "[G5F] Personel izin kartınız açıldı", html

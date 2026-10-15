# -*- coding: utf-8 -*-
"""Teknik Servis — LİSTE MASALARI (Ekim 2026, tüm program yeni tasarım — ortak masa shared/masa.py).

  kayit_masa_verisi()  Teknik Servis / İade arayüzü listesi: görünüm = durum (Aktif, Tümü, her durum),
                       seçim = fatura · firma · gönderim sonucu, SLA sütunu kademe renginde (16+ iş günü kırmızı)
  depo_masa_verisi()   Depolar listesi: özet bandı (transfer adetleri), görünüm = stok durumu,
                       seçim = ürün grubu · firma · kaynak · fatura · giriş şekli, depo bazında gruplu
  kayit_yurutucu() / depo_yurutucu()
                       satıra tıklanınca BUGÜNKÜ sayfa içi ayrıntı (ts_ekran.sec → kontrol paneli /
                       depo ayrıntısı, tüm pencereleriyle); "Toplu sat" bugünkü Toplu Satış formunu
                       seçilenlerle açar (durum_guncelle + stok çıkışı + satış kaydı aynı kod);
                       "Excel'e aktar" seçilenlerin bugünkü raporunu hazırlar.

Süzgeç kuralları eski ekranla aynı (durum_uyar: "sorunsuz" seçilince sorunsuz olarak GÖNDERİLMİŞLER de
görünür); sıra eski varsayılanla aynı (Teknik servis: SLA kademesi en acil önce, kademe içinde yeni → eski;
Depolar: depo sırası, depo içinde son transfer en üstte). Diğer sıralamalar sütun başlığından.

Geri almak için: teknikservis/main.py → TS_MASASI_YENI = False / DEPO_MASASI_YENI = False.
"""
from datetime import date, timedelta

from .database import ARAYUZ_ETIKET, BITMIS_DURUMLAR, DURUMLAR
from .ts_hesap import sla_kademe, sla_gruplari, depo_gruplari, konum, satis_disi_neden, gorunen_durum

AKTIF = "Aktif (bitmemiş)"
TUMU = "Tümü"
SONUCLAR = ["sorunsuz", "tamir edildi", "ürün değişimi", "iade alındı"]
# ts_hesap.sla_kademe rengi → masanın renk sınıfı (masada turuncu yok: 11–15 iş günü amber)
SLA_RENK = {"kirmizi": "kirmizi", "kirmizi2": "amber", "amber": "amber", "yesil": "yesil", "silik": "silik"}
DEPO_DURUM_RENK = {"satışa hazır": "yesil", "satıldı": "mor", "hurda": "kirmizi", "gönderildi": "cyan",
                   "merkeze aktarıldı": "mavi"}
DEPO_DURUMLARI = {"Satışa hazır": "satışa hazır", "Satıldı": "satıldı", "Hurda": "hurda"}
EXCEL_KAYIT = "_ts_excel_ids_{}"          # seçilenlerin kimlikleri (Excel'e aktar) — sayfa indirme düğmesi çizer
TOPLU_AC = "_ts_toplu_ac"                 # Toplu Satış penceresini aç


# ── Saf yardımcılar ─────────────────────────────────────────────────
def fatura_var(k):
    """Kayıtta fatura var mı? (fatura_mevcut alanı yoksa fatura no dolu mu) — main._fatura_var bunu kullanır."""
    v = k.get("fatura_mevcut")
    return bool((k.get("fatura_no") or "").strip()) if v is None else bool(v)


def durum_uyar(k, durum_f):
    """Teknik Servis listesinin durum süzgeci (eski _liste._uyar'ın durum kısmı, aynen)."""
    if durum_f == TUMU:
        return True
    if durum_f == AKTIF:
        return k.get("mevcut_durum") not in BITMIS_DURUMLAR
    if k.get("mevcut_durum") != durum_f:
        # "sorunsuz" seçilince sorunsuz olarak GÖNDERİLMİŞLER de görünsün
        return k.get("mevcut_durum") == "gönderildi" and (k.get("sonuc_durumu") or "") == durum_f
    return True


def ara_kat(s):
    """Arama için Türkçe katlama: 'İSMAİL' = 'ismail' = 'ISMAIL' ('İ'/'I'/'ı' → i)."""
    return str(s or "").replace("İ", "i").replace("I", "i").lower().replace("ı", "i").replace("i̇", "i")


def ara_uyar(k, metin, alanlar):
    """Metin araması (Türkçe katlanmış, içinde geçiyor mu) — okutulan seri no da burada süzülür."""
    metin = str(metin or "").strip()
    if not metin:
        return True
    blob = ara_kat(" ".join(str(k.get(a, "") or "") for a in alanlar))
    return all(p in blob for p in ara_kat(metin).split())


# Teknik servisin en sık aradığı alanlar (Ekim 2026, teknik servis bildirimi): seri no, stok kodu, irsaliye no,
# fatura no, geliş / gidiş takip no, müşteri şikâyeti (arıza), son kullanıcının adı soyadı. Takip no ve
# Depolar'da müşteri adı aranmıyordu.
TS_ARA_ALANLARI = ("servis_form_no", "stok_kodu", "stok_adi", "seri_no", "fatura_no", "irsaliye_no",
                   "firma_servis_form_no", "firma_bilgisi", "musteri_adi", "gelis_kargo_no", "gidis_kargo_no",
                   "sevk_kargo_bilgisi", "ariza", "musteri_tel", "degisim_seri_no")
DEPO_ARA_ALANLARI = TS_ARA_ALANLARI


def tek_arama(kayitlar, metin, depodaki_idler, sinir=30):
    """Teknik servis + İade + Depolar'da TEK arama (Ekim 2026): bütün kayıtlarda (işlemi bitmiş, depoda olanlar
    dahil) arar; her sonucun nerede açılacağı ('teknik' / 'iade' / 'depo'). Eskiden üç listede ayrı ayrı
    arayıp 'depodaki kayıtları da göster' anahtarını açmak gerekiyordu."""
    metin = str(metin or "").strip()
    if len(metin) < 2:
        return []
    out = []
    for k in kayitlar or []:
        if not ara_uyar(k, metin, TS_ARA_ALANLARI):
            continue
        yer = "depo" if k.get("id") in depodaki_idler else ("iade" if k.get("arayuz") == "iade" else "teknik")
        out.append((yer, k))
        if len(out) >= sinir:
            break
    return out


def _gun_metni(v):
    s = str(v or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
    return s[:10] or "—"


def _kisa(v, n):
    s = str(v or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _firma_ad(v):
    from shared.utils import firma_kisa_ad
    return firma_kisa_ad(v)


def _tr_bas(s):
    s = str(s or "")
    return ({"i": "İ", "ı": "I"}.get(s[0], s[0].upper()) + s[1:]) if s else s


def _kaynak(k):
    return ARAYUZ_ETIKET.get(k.get("arayuz", ""), "evraksız").split(" ", 1)[-1]


def _secenek(satirlar, alan, ad_fn=None):
    return [{"k": v, "ad": (ad_fn(v) if ad_fn else v) or v} for v in sorted({s[alan] for s in satirlar if s.get(alan)})]


def _ortak_metin(k):
    return {a: str(k.get(a) or "") for a in set(TS_ARA_ALANLARI) | set(DEPO_ARA_ALANLARI)}


# ── Teknik Servis / İade listesi ────────────────────────────────────
def kayit_masa_verisi(kayitlar, gunler, salt=False):
    """kayitlar: get_kayitlar sırası (yeni → eski); gunler: {id: SLA iş günü} (sla_is_gunu + tek sorguluk harita).
    Görünüm 'Aktif (bitmemiş)' varsayılan; yalnız kaydı olan durumlar çip olur."""
    from shared.tasarim import tr_sayi
    gun_of = lambda k: gunler.get(k.get("id"), 0)                       # noqa: E731
    bitmis_of = lambda k: k.get("mevcut_durum") in BITMIS_DURUMLAR       # noqa: E731
    satirlar = []
    for grup_ad, grup in sla_gruplari(kayitlar or [], gun_of, bitmis_of):
        for k in grup:
            gun, bitmis = int(gun_of(k) or 0), bitmis_of(k)
            _ad, renk, _s = sla_kademe(gun, bitmis)
            durum = str(k.get("mevcut_durum") or "")
            sonuc = (k.get("sonuc_durumu") or "").strip() if durum == "gönderildi" else ""
            fv = fatura_var(k)
            firma = (k.get("firma_bilgisi") or "").strip()
            r = dict(_ortak_metin(k))
            r.update({
                "id": k.get("id"), "sfn": str(k.get("servis_form_no") or "") or "—",
                "kabul_m": _gun_metni(k.get("mal_kabul_tarihi")), "kabul_m__s": str(k.get("mal_kabul_tarihi") or ""),
                "urun": str(k.get("stok_adi") or k.get("stok_kodu") or "") or "—",
                "urun_alt": " · ".join(x for x in (str(k.get("stok_kodu") or "").strip(),
                                                   f"seri {k.get('seri_no')}" if k.get("seri_no") else "",
                                                   _kisa(k.get("musteri_adi"), 28)) if x),
                "firma": firma, "firma_m": _firma_ad(firma) or "—",
                "durum": durum, "durum_m": durum + (f" · {sonuc}" if sonuc else ""),
                "sonuc_g": sonuc, "aktif": not bitmis,
                "fatura": "Mevcut" if fv else "Yok", "fatura_etk": "" if fv else "fatura yok",
                "sla": "tamamlandı" if bitmis else f"{tr_sayi(gun)} iş günü", "sla__s": gun, "sla_grup": grup_ad,
                "_durum": {"ad": "tamamlandı" if bitmis else f"{tr_sayi(gun)} iş günü", "renk": SLA_RENK.get(renk, "silik")},
            })
            for i, d in enumerate(DURUMLAR):
                if durum_uyar(k, d):
                    r[f"d{i}"] = True
            satirlar.append(r)
    gor = [{"k": "aktif", "ad": AKTIF, "f": [["aktif", "eq", True]]}, {"k": "tum", "ad": TUMU, "f": []}]
    gor += [{"k": f"d{i}", "ad": d, "f": [[f"d{i}", "eq", True]]}
            for i, d in enumerate(DURUMLAR) if any(s.get(f"d{i}") for s in satirlar)]
    return {
        "gorunumler": gor,
        "secimler": [{"alan": "fatura", "ad": "Fatura: tümü", "secenekler": [{"k": "Mevcut", "ad": "Fatura mevcut"},
                                                                             {"k": "Yok", "ad": "Fatura yok"}]},
                     {"alan": "firma", "ad": "Tüm firmalar", "secenekler": _secenek(satirlar, "firma", _firma_ad)},
                     {"alan": "sonuc_g", "ad": "Gönderim sonucu: tümü",
                      "secenekler": [{"k": s, "ad": s} for s in SONUCLAR if any(x["sonuc_g"] == s for x in satirlar)]}],
        "ara": {"alanlar": list(TS_ARA_ALANLARI), "ipucu": "Seri, stok, servis no, fatura, irsaliye, takip no, müşteri, arıza"},
        "sutunlar": [{"alan": "sfn", "ad": "Servis no", "gen": "116px", "dar": "alt"},
                     {"alan": "kabul_m", "ad": "Kabul", "gen": "96px", "genis": True},
                     {"alan": "urun", "ad": "Ürün", "tip": "ana", "alt": "urun_alt"},
                     {"alan": "firma_m", "ad": "Firma", "gen": "170px", "genis": True},
                     {"alan": "durum_m", "ad": "Durum", "tip": "etiket", "gen": "136px"},
                     {"alan": "fatura_etk", "ad": "Fatura", "tip": "etiket", "gen": "92px", "genis": True},
                     {"alan": "sla", "ad": "SLA", "tip": "durum", "gen": "124px"}],
        "grup": {"alan": "sla_grup", "birim": "kayıt"},
        "satirlar": satirlar,
        "islemler": [{"k": "ac", "ad": "Kaydı aç", "okuma": True},
                     {"k": "excel", "ad": "Excel'e aktar", "okuma": True, "yalniz_toplu": True,
                      "toplu": {"ad": "Seçilenleri Excel'e aktar", "alanlar": []}}],
        "tik": "ac",
        "bos": {"liste": "Kayıt yok.", "suzgec": "Filtreyle eşleşen kayıt yok."},
        "baslik_ipucu": "Servis kayıtları",
        "salt": bool(salt),
    }


def kayit_yurutucu(on_ek, arayuz, sec, durum):
    """sec: ts_ekran.sec (sayfa içi ayrıntı); durum: st.session_state (testte sözlük)."""
    def yurut(temiz):
        if temiz["islem"] == "ac":
            sec(on_ek, temiz["ids"][0])
            return {"ok": True, "mesaj": "", "sessiz": True, "onbellek": False}
        if temiz["islem"] == "excel":
            durum[EXCEL_KAYIT.format(arayuz)] = list(temiz["ids"])
            return {"ok": True, "onbellek": False,
                    "mesaj": f"{len(temiz['ids'])} kayıt Excel'e hazır: listenin altındaki düğmeyle indir."}
        return {"ok": False, "mesaj": "Bilinmeyen işlem."}
    return yurut


# ── Depolar ─────────────────────────────────────────────────────────
def transfer_gunu(k):
    """Kaydın depoya transfer edildiği GÜN (date) — yoksa None (main._transfer_gunu ile aynı)."""
    s = str(k.get("depo_tarihi") or "").strip()[:10]
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def donem_baslangic(donem, bugun):
    if donem == "Bugün":
        return bugun
    if donem == "Bu hafta":
        return bugun - timedelta(days=bugun.weekday())
    if donem == "Bu ay":
        return bugun.replace(day=1)
    return date.min


def depo_ozeti(tum, bugun):
    """Eski 'İşlem özeti' kartları (main._ozet_serit) tek bantta: dönem seçici yerine üç dönem yan yana."""
    aktif = [k for k in tum or [] if k.get("mevcut_durum") not in BITMIS_DURUMLAR and not (k.get("depo") or "").strip()]
    transferli = [k for k in tum or [] if transfer_gunu(k) is not None]
    say = {d: sum(1 for k in transferli if transfer_gunu(k) >= donem_baslangic(d, bugun))
           for d in ("Bugün", "Bu hafta", "Bu ay")}
    return [{"k": "bugun", "et": "Depoya transfer · bugün", "dg": f"{say['Bugün']} adet", "renk": "cyan" if say["Bugün"] else "silik"},
            {"k": "hafta", "et": "Depoya transfer · bu hafta", "dg": f"{say['Bu hafta']} adet", "renk": ""},
            {"k": "ay", "et": "Depoya transfer · bu ay", "dg": f"{say['Bu ay']} adet", "renk": ""},
            {"k": "aktif", "et": "Aktif (işlemi bitmemiş)", "dg": f"{len(aktif)} adet", "renk": "amber" if aktif else "silik"},
            {"k": "toplam", "et": "Toplam transfer (tüm zaman)", "dg": f"{len(transferli)} adet", "renk": ""}]


def transfer_anahtari(k):
    """Varsayılan sıra: son transfer en üstte; transfer tarihi yoksa mal kabul; eşitlikte kayıt id'si."""
    t = str(k.get("depo_tarihi") or "").strip() or str(k.get("mal_kabul_tarihi") or "").strip()[:10]
    try:
        i = int(k.get("id") or 0)
    except (TypeError, ValueError):
        i = 0
    return (t, i)


def toplu_etiket(k):
    """Toplu Satış listesindeki ürün etiketi (eski expander ile aynı)."""
    return (f'{k.get("servis_form_no","")} · {k.get("stok_kodu","")} · '
            f'{(k.get("stok_adi") or "")[:32]} · Seri {k.get("seri_no","")} '
            f'· [{konum(k)}]')


def depo_masa_verisi(goster, tum, depo_sirasi, bugun, giris_fn, salt=False, grup_ad=None, depo_ad=None):
    """goster: depolar_kayitlari (sayfadaki çoklu depo seçimiyle süzülmüş); tum: get_kayitlar() (özet bandı için).
    grup_ad: ürün grubunun tek yazımı ('kasa' → 'Kasa'; database.ts_grup_ad) — süzgeçte 'Kasa'/'kasa' tek seçenek.
    depo_ad: depo adının Depo modülündeki karşılığı ('merkez' → 'MERKEZ DEPO'; stok.ts_depo_ad)."""
    from shared.tasarim import tr_sayi
    sirali = sorted(goster or [], key=transfer_anahtari, reverse=True)
    satirlar = []
    for depo, grup in depo_gruplari(sirali, depo_sirasi):
        for k in grup:
            durum = gorunen_durum(k)                  # merkezdeki ürün: 'merkeze aktarıldı'
            satildi = durum == "satıldı"
            fiyat = ""
            if satildi:
                if k.get("bedelsiz"):
                    fiyat = "bedelsiz"
                else:
                    try:
                        f = float(k.get("satis_fiyati") or 0)
                    except (TypeError, ValueError):
                        f = 0.0
                    fiyat = f"${tr_sayi(f, 2)}" if f else ""
            t, _i = transfer_anahtari(k)
            r = dict(_ortak_metin(k))
            r.update({
                "id": k.get("id"), "sfn": str(k.get("servis_form_no") or "") or "—",
                "transfer_m": _gun_metni(k.get("depo_tarihi") or k.get("mal_kabul_tarihi")),
                "transfer_m__s": f"{t}|{_i:012d}",
                "urun": str(k.get("stok_adi") or k.get("stok_kodu") or "") or "—",
                "urun_alt": " · ".join(x for x in (str(k.get("stok_kodu") or "").strip(),
                                                   f"seri {k.get('seri_no')}" if k.get("seri_no") else "",
                                                   _kisa(k.get("depo_aciklama"), 40)) if x),
                "depo_ad": (depo_ad or _tr_bas)(depo), "konum": konum(k),
                "grup": (grup_ad or str.strip)(str(k.get("urun_grubu") or "")).strip(), "firma": (k.get("firma_bilgisi") or "").strip(),
                "kaynak": _kaynak(k), "fatura": "Mevcut" if fatura_var(k) else "Yok", "giris": giris_fn(k),
                "satis_m": fiyat, "satis_m__s": str(k.get("satis_tarihi") or ""),
                "satis_alt": _gun_metni(k.get("satis_tarihi")) if satildi and k.get("satis_tarihi") else "",
                "durum": durum, "hazir": 1 if durum == "satışa hazır" else 0, "satilabilir": not satis_disi_neden(k),
                "_durum": {"ad": durum or "—", "renk": DEPO_DURUM_RENK.get(durum, "silik")},
            })
            satirlar.append(r)
    return {
        "ozet": depo_ozeti(tum, bugun),
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}]
                      + [{"k": d, "ad": et, "f": [["durum", "eq", d]]} for et, d in DEPO_DURUMLARI.items()],
        "secimler": [{"alan": "grup", "ad": "Tüm ürün grupları", "secenekler": _secenek(satirlar, "grup")},
                     {"alan": "firma", "ad": "Tüm firmalar", "secenekler": _secenek(satirlar, "firma", _firma_ad)},
                     {"alan": "kaynak", "ad": "Tüm kaynaklar", "secenekler": _secenek(satirlar, "kaynak")},
                     {"alan": "fatura", "ad": "Fatura: tümü", "secenekler": [{"k": "Mevcut", "ad": "Fatura mevcut"},
                                                                             {"k": "Yok", "ad": "Fatura yok"}]},
                     {"alan": "giris", "ad": "Giriş şekli: tümü", "secenekler": _secenek(satirlar, "giris")}],
        "ara": {"alanlar": list(DEPO_ARA_ALANLARI), "ipucu": "Seri, stok, servis no, fatura, irsaliye, takip no, müşteri, arıza"},
        "sutunlar": [{"alan": "sfn", "ad": "Servis no", "gen": "116px", "dar": "alt"},
                     {"alan": "transfer_m", "ad": "Transfer", "gen": "100px", "genis": True},
                     {"alan": "urun", "ad": "Ürün", "tip": "ana", "alt": "urun_alt"},
                     {"alan": "kaynak", "ad": "Kaynak", "tip": "etiket", "gen": "120px", "genis": True},
                     {"alan": "satis_m", "ad": "Satış", "sag": True, "alt": "satis_alt", "gen": "112px", "genis": True},
                     {"alan": "durum", "ad": "Durum", "tip": "durum", "gen": "124px"}],
        "grup": {"alan": "depo_ad", "birim": "ürün",
                 "toplamlar": [{"alan": "hazir", "ondalik": 0, "son": " satışa hazır"}]},
        "satirlar": satirlar,
        "islemler": [{"k": "ac", "ad": "Ürünü aç", "okuma": True},
                     {"k": "sat", "ad": "Toplu sat", "yalniz_toplu": True, "birincil": True,
                      "f": [["satilabilir", "eq", True]], "toplu": {"ad": "Toplu sat…", "alanlar": []}},
                     {"k": "excel", "ad": "Excel'e aktar", "okuma": True, "yalniz_toplu": True,
                      "toplu": {"ad": "Seçilenleri Excel'e aktar", "alanlar": []}}],
        "tik": "ac",
        "bos": {"liste": "Henüz depoya aktarılmış ürün yok.", "suzgec": "Filtreyle eşleşen ürün yok."},
        "baslik_ipucu": "Depodaki ürünler",
        "salt": bool(salt),
    }


def depo_yurutucu(kayitlar, sec, durum):
    """ac → sayfa içi ayrıntı (ts_ekran.sec("ts_depo", id)); sat → Toplu Satış formu seçilenlerle açılır
    (aynı sayfa çalıştırmasında; satış bugünkü kodla yapılır); excel → seçilenlerin raporu."""
    sozluk = {k.get("id"): k for k in kayitlar or []}

    def yurut(temiz):
        ids = temiz["ids"]
        if temiz["islem"] == "ac":
            sec("ts_depo", ids[0])
            return {"ok": True, "mesaj": "", "sessiz": True, "onbellek": False}
        if temiz["islem"] == "sat":
            secilen = [sozluk[i] for i in ids if i in sozluk and sozluk[i].get("mevcut_durum") != "satıldı"]
            if not secilen:
                return {"ok": False, "mesaj": "Seçilenler arasında satılabilir ürün yok."}
            durum["ts_toplu_sec"] = [toplu_etiket(k) for k in secilen]
            durum[TOPLU_AC] = True
            return {"ok": True, "mesaj": "", "yenileme": False, "sessiz": True}
        if temiz["islem"] == "excel":
            durum[EXCEL_KAYIT.format("depo")] = list(ids)
            return {"ok": True, "onbellek": False,
                    "mesaj": f"{len(ids)} ürün Excel'e hazır: listenin altındaki düğmeyle indir."}
        return {"ok": False, "mesaj": "Bilinmeyen işlem."}
    return yurut

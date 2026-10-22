# -*- coding: utf-8 -*-
"""İthalat › Geçmiş ithalatlar ve Masraf detayları — ORTAK LİSTE MASASI (Ekim 2026).

Liste, süzgeç, arama, yan detay paneli ve toplu işlem ortak masada (shared/masa.py). Bu modül yalnız
masanın tanımını (masa_verisi, masraf_masa_verisi) ve yürütmeyi (islem_uygula, yurutucu) verir.
Rakamlar bugünkü hesapla aynı: dosya_hesapla (net mal bedeli, toplam masraf, % maliyet) ve
masraf_dokumu (masraf kalemleri). Yazma işlemleri BUGÜNKÜ veritabanı fonksiyonlarıyla, eski ekrandaki
argümanlarla yapılır (set_dosya_durum + set_dosya_teslim, set_dosya_teslim, set_dosya_takip_no).

Masa dışında kalanlar (ithalat/main.py):
  - satıra tıklayıp "Ayrıntı" → bugünkü çok sekmeli detay penceresi (_dlg_dosya_detay: masraf, düzenleme,
    çoklu ürün grubu, silme) aynen açılır.
  - ortak masrafı FOB payına göre dağıtma (dagit_ortak_masraf) kendi kutularıyla "Toplu işlem" görünümünde.

Geri almak için: ithalat/main.py → ITHALAT_MASASI_YENI = False (eski ekran aynen duruyor).
"""
from datetime import date

ASAMA_RENK = {"Üretimde": "silik", "Yolda": "cyan", "Gümrükte": "amber", "Antrepoda": "mor",
              "Teslim Alındı": "yesil"}
AY = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
      "Ekim", "Kasım", "Aralık"]
TESLIM = "Teslim Alındı"
_SEMBOL = {"USD": "$", "EUR": "€", "TRY": "₺", "TL": "₺"}


# ── Biçim ───────────────────────────────────────────────────────────
def _f(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return f if f == f else 0.0


def _tr(v, ondalik=2):
    from shared.tasarim import tr_sayi
    return tr_sayi(v, ondalik)


def _kisa(metin):
    """Büyük özet rakamı: 1.000 ve üstünde kuruşsuz (kartlarla aynı kural)."""
    from shared.tasarim import kart_degeri_kisa
    return kart_degeri_kisa(metin)[0]


def _para(v, doviz="USD"):
    """Satır tutarı tam (2 ondalık), dosyanın kendi para biriminde."""
    d = str(doviz or "USD").upper()
    s = _SEMBOL.get(d)
    return f"{s}{_tr(v)}" if s else f"{_tr(v)} {d}"


def _tarih(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _gay(v):
    t = _tarih(v)
    return t.strftime("%d.%m.%Y") if t else ""


def _ay_basligi(v):
    t = _tarih(v)
    return f"{AY[t.month]} {t.year}" if t else "Tarihsiz"


def varis_metni(d, bugun):
    """Tahmini varışa kalan gün (ithalat_ekran.varis_metni ile aynı metin)."""
    from .ithalat_ekran import varis_metni as _vm
    return _vm(d, bugun)


def _depo_secenekleri():
    from .main import DEPO_SECENEKLER
    return [{"k": d, "ad": d} for d in DEPO_SECENEKLER if not str(d).startswith("(")]


# ── Geçmiş ithalatlar: ekrana giden veri (saf) ──────────────────────
def masa_verisi(dosyalar, hesap_map, bugun=None, salt=False, depolar=None, mikro_acik=False):
    """dosyalar: ithalat_mi ile süzülmüş dosyalar. hesap_map: {id: (dosya, kalemler, dosya_hesapla)}.
    Sıra: sipariş tarihi yeniden eskiye, aya göre gruplu (eski Liste görünümü).
    mikro_acik: Mikro ithalat eşitlemesi açık — Mikro'ya bağlı dosyada (mikro_kodu) aşama ve teslim deposu Mikro'dan
    gelir: "Teslim alındı" / "Depo ata" yok (kullanıcı, 22.10.2026). Bağsız (yoldaki) dosyada eskisi gibi."""
    from .database import IN_TRANSIT_DURUMLAR, DURUM_SECENEKLER
    bugun = bugun or date.today()
    depolar = depolar if depolar is not None else _depo_secenekleri()
    sirali = sorted(dosyalar or [], key=lambda d: str(d.get("tarih") or ""), reverse=True)
    satirlar = []
    for d in sirali:
        _d, kal, h = hesap_map[d["id"]]
        asama = str(d.get("durum") or "").strip() or "—"
        depo = str(d.get("teslim_deposu") or "").strip()
        doviz = str(d.get("doviz") or "USD")
        belge = str(d.get("pi_no") or d.get("dosya_no") or "").strip()
        ted = str(d.get("tedarikci") or "").strip()
        takip = str(d.get("ithalat_takip_no") or "").strip()
        sas = str(d.get("sas_no") or "").strip()
        mal, masraf, yuzde = _f(h["net_mal_bedeli"]), _f(h["toplam_masraf"]), _f(h["maliyet_yuzde"])
        teslim_t = str(d.get("teslim_tarihi") or "")[:10]
        if asama == TESLIM:
            var, var_alt, var_renk, var_s = _gay(teslim_t) or "—", "teslim", "silik", teslim_t or "0000"
        elif asama in IN_TRANSIT_DURUMLAR:
            vm, vr = varis_metni(d, bugun)
            var, var_alt, var_renk = _gay(d.get("tahmini_varis")) or "—", vm, vr
            var_s = str(d.get("tahmini_varis") or "")[:10] or "9999"
        else:
            var, var_alt, var_renk, var_s = "—", "", "silik", "9999"
        depo_eksik = asama == TESLIM and not depo
        kalem = int(h.get("kalem_sayisi") or 0)
        detay = [["Sipariş tarihi", _gay(d.get("tarih")) or "—"],
                 ["Takip no", takip or "—"], ["SAS no", sas or "—"],
                 ["Aşama", asama]]
        if asama in IN_TRANSIT_DURUMLAR:
            detay.append(["Tahmini varış", f"{_gay(d.get('tahmini_varis')) or '—'} · {var_alt}"])
        detay += [["Teslim tarihi", _gay(teslim_t) or "—"],
                  ["Teslim deposu", depo or ("SEÇİLMEDİ" if asama == TESLIM else "—")],
                  ["Teslim şekli", str(d.get("teslim_sekli") or "").strip() or "—"],
                  ["Ülke", str(d.get("mense_ulke") or "").strip() or "—"],
                  ["Kalem", f"{kalem} kalem"],
                  ["Masraf", f"{_para(masraf, doviz)} · %{_tr(yuzde)}"]]
        if _f(h.get("indirim")) > 0:
            detay.append(["Brüt / indirim", f"{_para(h['mal_bedeli'], doviz)} − {_para(h['indirim'], doviz)}"])
        notlar = []
        if depo_eksik:
            notlar.append("Teslim alındı ama teslim deposu seçilmedi.")
        if masraf <= 0:
            notlar.append("Masraf girilmedi: Ayrıntı › Düzenle ile girilir.")
        satirlar.append({
            "id": d["id"], "belge": belge or "—", "ted": ted or "—", "takip": takip, "sas": sas,
            "mikro": bool(mikro_acik and str(d.get("mikro_kodu") or "").strip()),
            "tarih": _gay(d.get("tarih")) or "—", "tarih__s": str(d.get("tarih") or "")[:10] or "0000",
            "ay": _ay_basligi(d.get("tarih")),
            "ted_alt": " · ".join(x for x in (takip, f"{kalem} kalem") if x),
            "asama": asama, "depo": depo, "depo_eksik": depo_eksik,
            "depo_m": depo or ("SEÇİLMEDİ" if asama == TESLIM else ""),
            "var": var, "var_alt": var_alt, "var_renk": var_renk, "var__s": var_s,
            "doviz": doviz, "mal": mal, "masraf": masraf, "yuzde": yuzde,
            "mal_m": _para(mal, doviz), "mal_m__s": mal,
            "masraf_m": _para(masraf, doviz) if masraf > 0 else "", "masraf_m__s": masraf,
            "yuzde_m": f"%{_tr(yuzde)}" if masraf > 0 else "masraf yok",
            "masraf_var": masraf > 0, "kalem": kalem,
            "skus": " ".join(str(k.get("sku") or "") for k in kal),
            "_durum": {"ad": asama, "renk": ASAMA_RENK.get(asama, "soluk")},
            "_baslik": belge or "—", "_alt": ted,
            "_buyuk": _para(mal, doviz), "_buyuk_alt": "net mal bedeli",
            "_detay": detay, "_not": " ".join(notlar),
        })

    # Özet bandı — eski kpi_serit ile aynı formüller (toplamlar dövizden bağımsız $ yazılır, eski ekran gibi)
    toplam_mal = sum(s["mal"] for s in satirlar)
    toplam_masraf = sum(s["masraf"] for s in satirlar)
    ort = (toplam_masraf / toplam_mal * 100) if toplam_mal > 0 else 0
    yolda = [s for s in satirlar if s["asama"] in IN_TRANSIT_DURUMLAR]
    yolda_fob = sum(s["mal"] for s in yolda)
    bekleyen = sum(1 for s in satirlar if not s["masraf_var"])
    ozet = [
        {"k": "yolda", "et": "Yoldaki dosya", "dg": _tr(len(yolda), 0), "renk": "cyan", "suz": "yolda",
         "al": f"{_kisa('$' + _tr(yolda_fob))} mal bedeli", "ipucu": f"${_tr(yolda_fob)}"},
        {"k": "mal", "et": "Toplam mal bedeli", "dg": _kisa(f"${_tr(toplam_mal)}"), "renk": "yesil", "suz": "tum",
         "al": f"{_tr(len(satirlar), 0)} dosya", "ipucu": f"${_tr(toplam_mal)}"},
        {"k": "masraf", "et": "Toplam masraf", "dg": _kisa(f"${_tr(toplam_masraf)}"), "renk": "amber",
         "suz": "masrafsiz" if bekleyen else None, "ipucu": f"${_tr(toplam_masraf)}",
         "al": f"{bekleyen} dosyada masraf bekliyor" if bekleyen else "tüm dosyalarda masraf girildi"},
        {"k": "oran", "et": "Ort. masraf oranı", "dg": f"%{_tr(ort)}", "renk": "mor", "nokta": False,
         "al": "masraf ÷ net mal bedeli"},
    ]
    var_asama = [a for a in DURUM_SECENEKLER if any(s["asama"] == a for s in satirlar)]
    if any(s["asama"] == "—" for s in satirlar):
        var_asama.append("—")
    teslim_degil = [["asama", "ne", TESLIM]]
    return {
        "ozet": ozet,
        "gorunumler": [
            {"k": "tum", "ad": "Tümü", "f": []},
            {"k": "yolda", "ad": "Yolda", "f": [["asama", "in", sorted(IN_TRANSIT_DURUMLAR)]]},
            {"k": "teslim", "ad": "Teslim alındı", "f": [["asama", "eq", TESLIM]]},
            {"k": "masrafsiz", "ad": "Masraf bekleyen", "f": [["masraf_var", "yok", None]]},
            {"k": "deposuz", "ad": "Depo seçilmedi", "f": [["depo_eksik", "var", None]]},
        ],
        "secimler": [
            {"alan": "ted", "ad": "Tüm tedarikçiler",
             "secenekler": [{"k": t, "ad": t} for t in sorted({s["ted"] for s in satirlar if s["ted"] != "—"})]},
            {"alan": "asama", "ad": "Tüm aşamalar", "secenekler": [{"k": a, "ad": a} for a in var_asama]},
        ],
        "ara": {"alanlar": ["belge", "takip", "sas", "ted", "skus"],
                "ipucu": "Belge, takip, SAS no, tedarikçi ya da SKU"},
        "sutunlar": [
            {"alan": "belge", "ad": "Belge", "tip": "metin", "alt": "tarih", "gen": "130px", "dar": "alt"},
            {"alan": "ted", "ad": "Tedarikçi", "tip": "ana", "alt": "ted_alt"},
            {"alan": "asama", "ad": "Aşama", "tip": "durum", "gen": "124px"},
            {"alan": "var", "ad": "Varış / teslim", "alt": "var_alt", "alt_renk": "var_renk", "gen": "132px",
             "genis": True},
            {"alan": "mal_m", "ad": "Mal bedeli", "sag": True, "gen": "128px", "dar": "sag"},
            {"alan": "masraf_m", "ad": "Masraf", "sag": True, "alt": "yuzde_m", "gen": "118px", "genis": True},
            {"alan": "depo_m", "ad": "Teslim deposu", "tip": "etiket", "gen": "120px", "genis": True},
        ],
        "grup": {"alan": "ay", "birim": "dosya", "toplamlar": [{"alan": "mal", "on": "$", "ondalik": 0}]},
        "toplu_toplam": [{"alan": "mal", "on": "$"}],
        "satirlar": satirlar,
        "islemler": [
            {"k": "ac", "ad": "Ayrıntı", "dugme": "Ayrıntı · masraf · düzenle", "okuma": True, "birincil": True},
            {"k": "teslim", "ad": "Teslim alındı", "dugme": "Teslim alındı yap",
             "f": teslim_degil + [["mikro", "ne", True]],
             "ipucu": "Yalnız aşama ve teslim deposu güncellenir; teslim tarihine dokunulmaz. Teslim deposu "
                      "zorunlu: deposuz dosya 'Teslim Alındı' yapılamaz.",
             "toplu": {"ad": "Teslim alındı yap", "alanlar": ["depo"]},
             "alanlar": [{"ad": "depo", "et": "Teslim deposu", "tip": "secim", "zorunlu": True, "tam": True,
                          "bos": "Depo seç…", "secenekler": depolar}]},
            {"k": "depo", "ad": "Depo ata", "dugme": "Depoyu ata",
             "f": [["asama", "eq", TESLIM], ["depo", "yok", None], ["mikro", "ne", True]],
             "ipucu": "Teslim alınmış ama deposu boş dosyaya teslim deposu yazılır.",
             "toplu": {"ad": "Depoyu ata", "alanlar": ["depo"]},
             "alanlar": [{"ad": "depo", "et": "Atanacak depo", "tip": "secim", "zorunlu": True, "tam": True,
                          "bos": "Depo seç…", "secenekler": depolar}]},
            {"k": "takip", "ad": "Takip no", "dugme": "Takip no ata",
             "ipucu": "Seçili belgelerin hepsine aynı İthalat Takip No yazılır (masraf dağıtımı takibe göre "
                      "yapılır). Takip no'yu silmek için Toplu işlem görünümü.",
             "toplu": {"ad": "Takip no ata", "alanlar": ["takip"]},
             "alanlar": [{"ad": "takip", "et": "İthalat takip no", "tip": "metin", "zorunlu": True,
                          "varsayilan_alan": "takip", "en_uzun": 60}]},
        ],
        "bos": {"liste": "Henüz ithalat kaydı yok.",
                "suzgec": "Bu süzgece uyan dosya yok. Bütün dosyalar için 'Tümü'."},
        "baslik_ipucu": "İthalat dosyaları",
        "salt": bool(salt),
    }


# ── Yürütme (veritabanı) ────────────────────────────────────────────
def islem_uygula(temiz, dosyalar):
    """shared.masa.istek_al'dan geçmiş isteği bugünkü veritabanı fonksiyonlarıyla, eski ekranın
    argümanlarıyla yürütür. Döner: {"ok", "mesaj"} (+ "ac" için masa bayrakları)."""
    from shared import bilesen as B
    from . import database as D
    islem, ids, deg = temiz["islem"], temiz["ids"], temiz["degerler"]
    sozluk = {d.get("id"): d for d in dosyalar or []}
    if islem == "ac":
        B.detay_ac("ith", ids[0])
        return {"ok": True, "mesaj": "", "yenileme": False, "sessiz": True}
    if islem == "teslim":
        depo = deg.get("depo") or ""
        if not depo:
            return {"ok": False, "mesaj": "Teslim deposu seçin."}
        bekleyen = [i for i in ids if str((sozluk.get(i) or {}).get("durum") or "").strip() != TESLIM]
        if not bekleyen:
            return {"ok": False, "mesaj": "Seçilenlerin hepsi zaten 'Teslim Alındı'."}
        ok = 0
        for i in bekleyen:                       # eski toplu işlemle aynı sıra ve argümanlar
            if D.set_dosya_durum(i, "Teslim Alındı"):
                ok += 1
                D.set_dosya_teslim(i, teslim_deposu=depo)
        return {"ok": ok > 0, "mesaj": f"{ok} belge 'Teslim Alındı' olarak işaretlendi. Teslim deposu: {depo}."}
    if islem == "depo":
        depo = deg.get("depo") or ""
        ok = sum(1 for i in ids if D.set_dosya_teslim(i, teslim_deposu=depo))
        return {"ok": ok > 0, "mesaj": f"{ok} dosyaya '{depo}' teslim deposu atandı."}
    if islem == "takip":
        takip = str(deg.get("takip") or "").strip()
        if not takip:
            return {"ok": False, "mesaj": "Takip no girin."}
        ok = sum(1 for i in ids if D.set_dosya_takip_no(i, takip))
        return {"ok": ok > 0, "mesaj": f"{ok} belgeye '{takip}' takip no'su atandı."}
    return {"ok": False, "mesaj": "Bilinmeyen işlem."}


def yurutucu(dosyalar):
    """shared.masa.calistir için: temiz istek → veritabanı → bildirim."""
    def yurut(temiz):
        return islem_uygula(temiz, dosyalar)
    return yurut


# ── Masraf detayları: ekrana giden veri (saf, salt-okur) ────────────
def masraf_masa_verisi(satirlar):
    """satirlar: ithalat/main._masraf_detaylari'nin bugünkü satırları (masraf_dokumu; % = tutar / brüt FOB).
    Masraf kalemleri masası. Varsayılan sıra eski ekranla aynı: (Belge No, Masraf Türü); belgeye göre gruplu."""
    sirali = sorted(satirlar or [], key=lambda x: (x["Belge No"], x["Masraf Türü"]))
    rows = []
    for n, s in enumerate(sirali):
        dov = s["Döviz"]
        rows.append({
            "id": n + 1, "belge": s["Belge No"], "takip": s["Takip No"], "ted": s["Tedarikçi"] or "—",
            "tarih": _gay(s["Tarih"]) or "—", "tarih__s": s["Tarih"] or "0000",
            "tur": s["Masraf Türü"], "tutar": round(s["Tutar"], 2), "doviz": dov,
            "tutar_m": f"{_tr(s['Tutar'])} {dov}", "tutar_m__s": s["Tutar"],
            "yuzde": round(s["% (belge)"], 2), "yuzde_m": f"%{_tr(s['% (belge)'])}", "yuzde_m__s": s["% (belge)"],
            "grup": f"{s['Belge No']} · {dov}",
            "_baslik": s["Masraf Türü"], "_alt": f"{s['Belge No']} · {s['Tedarikçi']}",
            "_buyuk": f"{_tr(s['Tutar'])} {dov}", "_buyuk_alt": f"belgenin %{_tr(s['% (belge)'])}'i",
            "_detay": [["Belge no", s["Belge No"]], ["Takip no", s["Takip No"]],
                       ["Tarih", _gay(s["Tarih"]) or "—"], ["Tedarikçi", s["Tedarikçi"] or "—"]],
        })
    toplam = sum(s["Tutar"] for s in sirali)
    dovizler = {s["Döviz"] for s in sirali}
    dov_lbl = list(dovizler)[0] if len(dovizler) == 1 else "karışık"
    tam = f"${_tr(toplam)}" if dov_lbl == "USD" else f"{_tr(toplam)} {dov_lbl}"
    turler = sorted({s["Masraf Türü"] for s in sirali})
    takipler = sorted({s["Takip No"] for s in sirali if s["Takip No"] != "—"})
    return {
        "ozet": [
            {"k": "toplam", "et": "Toplam masraf", "dg": _kisa(tam), "renk": "amber", "ipucu": tam,
             "al": "farklı para birimleri toplandı" if dov_lbl == "karışık" else ""},
            {"k": "kalem", "et": "Masraf kalemi", "dg": _tr(len(sirali), 0), "renk": "mor",
             "al": f"{len(turler)} farklı tür"},
            {"k": "belge", "et": "Belge", "dg": _tr(len({s['Belge No'] for s in sirali}), 0), "renk": "yesil"},
        ],
        "gorunumler": [{"k": "tum", "ad": "Tümü", "f": []}],
        "secimler": [{"alan": "tur", "ad": "Tüm masraf türleri", "secenekler": [{"k": t, "ad": t} for t in turler]},
                     {"alan": "takip", "ad": "Tüm takip no'lar", "secenekler": [{"k": t, "ad": t} for t in takipler]}],
        "ara": {"alanlar": ["belge", "takip", "ted", "tur"], "ipucu": "Belge, takip no, tedarikçi ya da masraf türü"},
        "sutunlar": [
            {"alan": "tur", "ad": "Masraf türü", "tip": "ana", "alt": "ted"},
            {"alan": "belge", "ad": "Belge", "tip": "metin", "alt": "tarih", "gen": "130px", "dar": "alt"},
            {"alan": "takip", "ad": "Takip no", "gen": "110px", "genis": True},
            {"alan": "tutar_m", "ad": "Tutar", "sag": True, "gen": "140px", "dar": "sag"},
            {"alan": "yuzde_m", "ad": "% (belge)", "sag": True, "gen": "96px", "genis": True},
        ],
        "grup": {"alan": "grup", "birim": "kalem", "toplamlar": [{"alan": "tutar"}]},
        "satirlar": rows,
        "islemler": [],
        "bos": {"liste": "Henüz hiçbir ithalatta masraf girilmemiş.",
                "suzgec": "Filtre/aramayla eşleşen masraf kalemi yok."},
        "baslik_ipucu": "Masraf kalemleri",
    }

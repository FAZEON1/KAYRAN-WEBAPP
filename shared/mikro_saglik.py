# -*- coding: utf-8 -*-
"""Mikro bağlantısının sağlığı: sorun tespiti, Telegram uyarı kararı, eşitleme günlüğü (Ekim 2026).

Kullanıcı: "Sağlık paneli, Telegram uyarısı ve eşitlemenin aktarımın hemen ardından çalışması."
21.10.2026'da iki sorun ancak elle bakınca fark edildi: (1) satış eşitlemesi kopya okuma yüzünden
16:26'dan 18:51'e kadar sessizce yazmadı; (2) saatlik GitHub işi kendi zamanında hiç çalışmadı (GitHub'ın
zamanlanmış işleri bu depoda saatlerce gecikiyor: 02:00'lık gece yedeği 06:51–08:48'de çalışıyor).

Akış:
  aktarıcı (sunucu, 15 dk) ── yeni veri getirdiyse ──► Supabase fonksiyonu mikro-tetik ──► GitHub işi
  Supabase zamanlayıcısı (pg_cron, 30 dk) ── aktarıcı 45 dk'dır yazmadıysa ──► mikro-tetik ──► GitHub işi
  GitHub işi (otonom/mikro_esitle.py): eşitlemeler → günlüğe yazar → sorunlar() → bildirim_karari() → Telegram

Saf fonksiyonlar burada (test edilir); okuma / yazma en altta.
"""
from datetime import datetime, timedelta, timezone

AKTARICI_GECIKME_DK = 45        # aktarıcı 15 dakikada bir yazar; 3 tur kaçarsa durmuş sayılır
SATIS_BEKLEME_DK = 30           # Mikro'dan gelmiş ama satışa yazılmamış veri bu kadar beklerse uyarı
TEKRAR_SAAT = 6                 # aynı sorun sürerken hatırlatma aralığı
GUNLUK_GUN = 14                 # eşitleme günlüğü bu kadar gün tutulur
BILDIRIM_ANAHTAR = "mikro_saglik_bildirim"
GUNLUK_TABLO = "mikro_esitle_gunluk"

KRITIK, UYARI = "kritik", "uyari"


def zaman(v):
    """ISO metin / datetime → UTC datetime; okunamazsa None."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        t = v
    else:
        try:
            t = datetime.fromisoformat(str(v).strip().replace("Z", "+00:00").replace(" ", "T", 1))
        except ValueError:
            return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def dakika_once(t, simdi):
    t = zaman(t)
    return None if t is None else max(0, int((simdi - t).total_seconds() // 60))


def sure_metni(dk):
    """Dakika → '12 dk', '3 sa 5 dk', '2 gün'."""
    if dk is None:
        return "hiç"
    if dk < 60:
        return f"{dk} dk"
    if dk < 48 * 60:
        s, d = divmod(dk, 60)
        return f"{s} sa" + (f" {d} dk" if d else "")
    return f"{dk // 1440} gün"


def is_durumu(sonuc_metni):
    """otonom/mikro_esitle.calistir metni → 'yazdi' | 'yok' | 'uyari' | 'hata'."""
    m = str(sonuc_metni or "")
    if m.startswith("HATA"):
        return "hata"
    if m.startswith("UYARI"):
        return "uyari"
    if m.startswith("tamam"):
        return "yazdi"
    return "yok"


# ── sorun tespiti ───────────────────────────────────────────────────
def sorunlar(senk, son_tur, satis, simdi):
    """senk: mikro_senk_durum satırları [{tablo, son_cekim, son_hata, guncelleme}].
    son_tur: son eşitleme turunun işleri [{ad, durum, metin}] (None: hiç tur yok).
    satis: {acik, son_calisma, son_veri} — son_veri: satış / sipariş satırlarının en yeni senk_zamani.
    Döner: [{kod, seviye, metin}] — kod aynı sorun için sabit (uyarı tekrarını ayırt etmek için)."""
    out = []
    son_yazim = max((t for t in (zaman(r.get("guncelleme")) for r in senk or []) if t), default=None)
    if son_yazim is None:
        out.append({"kod": "aktarici_yok", "seviye": UYARI,        # kurulmamış: kesinti değil
                    "metin": "Aktarıcıdan hiç veri gelmemiş (mikro_senk_durum boş)."})
    else:
        dk = dakika_once(son_yazim, simdi)
        if dk >= AKTARICI_GECIKME_DK:
            out.append({"kod": "aktarici_durdu", "seviye": KRITIK,
                        "metin": f"Aktarıcı son kez {sure_metni(dk)} önce yazdı; Mikro'dan veri gelmiyor "
                                 "(sunucu 10.0.1.11)."})
    hatali = sorted(str(r.get("tablo")) for r in senk or [] if str(r.get("son_hata") or "").strip())
    if hatali:
        out.append({"kod": "aktarici_hata", "seviye": UYARI,
                    "metin": "Aktarıcı bazı tabloları okuyamadı: " + ", ".join(hatali) + "."})
    if son_tur:
        hata = [i["ad"] for i in son_tur if i.get("durum") == "hata"]
        uyari = [i["ad"] for i in son_tur if i.get("durum") == "uyari"]
        if hata:
            out.append({"kod": "esitleme_hata", "seviye": KRITIK,
                        "metin": "Eşitleme hata verdi: " + ", ".join(hata) + "."})
        if uyari:
            out.append({"kod": "esitleme_uyari", "seviye": UYARI,
                        "metin": "Eşitleme yazmadı (koruma devrede): " + ", ".join(uyari) + "."})
    if (satis or {}).get("acik"):
        son_veri, son_cal = zaman(satis.get("son_veri")), zaman(satis.get("son_calisma"))
        if son_veri and (son_cal is None or son_veri - son_cal > timedelta(minutes=SATIS_BEKLEME_DK)):
            bekleme = dakika_once(son_veri, simdi)
            if bekleme is not None and bekleme >= SATIS_BEKLEME_DK:
                out.append({"kod": "satis_geride", "seviye": KRITIK,
                            "metin": f"Mikro'dan {sure_metni(bekleme)} önce gelen satış / sipariş verisi "
                                     "satışlara henüz yazılmadı."})
    return out


# ── Telegram uyarı kararı ───────────────────────────────────────────
def bildirim_karari(sorun_listesi, onceki, simdi, tekrar_saat=TEKRAR_SAAT):
    """Döner: (metin ya da None, yeni durum {kodlar, zaman}). Yeni sorun / değişen sorun → hemen; aynı
    sorun sürüyorsa tekrar_saat'te bir hatırlatma; hepsi düzelince bir kez "düzeldi"."""
    onceki = onceki or {}
    kodlar = sorted({s["kod"] for s in sorun_listesi})
    eski = sorted(onceki.get("kodlar") or [])
    son = zaman(onceki.get("zaman"))
    yeni = {"kodlar": kodlar, "zaman": simdi.isoformat()}
    if kodlar:
        if kodlar != eski or son is None or simdi - son >= timedelta(hours=tekrar_saat):
            baslik = "KAYRAN · Mikro bağlantısı: sorun" if kodlar != eski else "KAYRAN · Mikro bağlantısı: sorun sürüyor"
            satirlar = [f"{'KRİTİK' if s['seviye'] == KRITIK else 'Uyarı'}: {s['metin']}" for s in sorun_listesi]
            return baslik + "\n" + "\n".join(satirlar) + "\nAyrıntı: Sistem › Mikro bağlantısı", yeni
        return None, dict(onceki)
    if eski:
        return "KAYRAN · Mikro bağlantısı düzeldi: aktarım ve eşitleme normal.", yeni
    return None, dict(onceki)


# ── okuma / yazma ───────────────────────────────────────────────────
def _cli():
    from satis.database import _get_client
    return _get_client()


def senk_oku():
    return _cli().table("mikro_senk_durum").select("tablo,son_cekim,son_kayit_sayisi,son_hata,guncelleme") \
        .order("tablo").execute().data or []


def satis_durumu():
    """{acik, son_calisma, son_veri}: satış / sipariş satırlarının en yeni senk_zamani."""
    from satis.mikro_esitle import durum
    d = durum() or {}
    cli = _cli()
    son_veri = None
    for tablo in ("mikro_satis_satir", "mikro_siparis"):
        try:
            r = cli.table(tablo).select("senk_zamani").order("senk_zamani", desc=True).limit(1).execute().data
            t = zaman((r or [{}])[0].get("senk_zamani"))
            son_veri = t if son_veri is None or (t and t > son_veri) else son_veri
        except Exception:  # noqa: BLE001
            pass
    return {"acik": bool(d.get("acik")), "son_calisma": d.get("son_calisma"),
            "son_veri": son_veri.isoformat() if son_veri else None}


def gunluk_oku(limit=30):
    try:
        return _cli().table(GUNLUK_TABLO).select("*").order("zaman", desc=True).limit(limit).execute().data or []
    except Exception:  # noqa: BLE001
        return []


def gunluk_yaz(kaynak, isler, sorun_listesi, simdi=None):
    """Bir eşitleme turunu günlüğe yazar; GUNLUK_GUN'den eskileri siler. Hata fırlatmaz."""
    simdi = simdi or datetime.now(timezone.utc)
    try:
        cli = _cli()
        cli.table(GUNLUK_TABLO).insert({"zaman": simdi.isoformat(), "kaynak": str(kaynak or ""),
                                        "isler": isler, "sorunlar": sorun_listesi}).execute()
        cli.table(GUNLUK_TABLO).delete().lt("zaman", (simdi - timedelta(days=GUNLUK_GUN)).isoformat()).execute()
    except Exception as e:  # noqa: BLE001
        from shared.kayit import sessiz
        sessiz("shared.mikro_saglik.gunluk_yaz", e)


def tetik_durumu():
    """Supabase fonksiyonu mikro-tetik'in son tetiklemesi {zaman, mod, durum, neden} (yoksa {})."""
    try:
        from kayranacc.database import get_ayar
        return get_ayar("mikro_tetik_son", {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def denetle_ve_bildir(isler, kaynak="github", simdi=None, gonder=None):
    """Bir turdan sonra: sorunları bul, günlüğe yaz, gerekiyorsa Telegram'a yaz. Döner: (sorunlar, mesaj)."""
    from kayranacc.database import get_ayar, set_ayar
    simdi = simdi or datetime.now(timezone.utc)
    try:
        s = sorunlar(senk_oku(), isler, satis_durumu(), simdi)
    except Exception as e:  # noqa: BLE001
        s = [{"kod": "denetim_hata", "seviye": UYARI, "metin": f"Sağlık denetimi okunamadı: {type(e).__name__}"}]
    gunluk_yaz(kaynak, isler, s, simdi)
    metin, yeni = bildirim_karari(s, get_ayar(BILDIRIM_ANAHTAR, {}), simdi)
    if metin:
        if gonder is None:
            from shared.telegram_gonder import gonder as gonder
        ok, _m = gonder(metin)
        if ok:
            set_ayar(BILDIRIM_ANAHTAR, yeni)
    elif yeni != get_ayar(BILDIRIM_ANAHTAR, {}):
        set_ayar(BILDIRIM_ANAHTAR, yeni)
    return s, metin

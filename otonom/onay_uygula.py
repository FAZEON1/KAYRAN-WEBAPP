# -*- coding: utf-8 -*-
"""Onaylı Yayınlama — Telegram'dan gelen onayla hazır yamayı uygular.

KADEMELİ OTONOMİ · 2. AŞAMA (A yolu)

AKIŞ:
  1. Bir değişiklik hazırlanır → bekleyen/<ad>.json olarak repoya konur
  2. Bu görev 15 dakikada bir Telegram mesajlarını okur
  3. "/onayla <ad>" görürse yamayı uygular, test koşar, commit'ler
  4. "/reddet <ad>" görürse yamayı arşive taşır
  5. Sonucu Telegram'a bildirir

GÜVENLİK:
  • Yalnız YETKILI_CHAT listesindeki kişiler onaylayabilir
  • YASAK_DOSYA listesine dokunan yama ASLA uygulanmaz (para/stok/yetki)
  • Yama uygulanmadan önce Python sözdizimi kontrol edilir
  • Her adım Telegram'a raporlanır; sessiz başarısızlık yok

BU GÖREV KOD YAZMAZ. Yalnız İNSANIN yazdığı hazır yamayı uygular.

Ortam değişkenleri:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   — zorunlu
  YETKILI_CHAT                            — onay verebilecek chat id'ler (virgüllü)
"""

import json
import os
import pathlib
import py_compile
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

TR = timezone(timedelta(hours=3))
KOK = pathlib.Path(__file__).resolve().parent.parent
BEKLEYEN = KOK / "bekleyen"
ARSIV = KOK / "bekleyen" / "arsiv"

# ═══════════════════════════════════════════════════════════════════
#  YASAK DOSYALAR — bu dosyalara dokunan yama ASLA otomatik uygulanmaz.
#  Para, stok, maliyet ve yetki hesapları burada. Bir hata sessizce
#  yanlış rakam üretir ve aylar sonra fark edilir.
# ═══════════════════════════════════════════════════════════════════
YASAK_DOSYA = [
    "satis/database.py",        # satış, kâr, stok düşümü
    "kayranpm/database.py",     # stok hareketi, depo kırılımı
    "ithalat/database.py",      # maliyet, paçal
    "kayranacc/database.py",    # ödeme, bakiye, cari
    "app.py",                   # yetkilendirme, giriş, oturum
    "shared/audit.py",          # denetim kaydı
]
YASAK_UZANTI = [".sql", ".yml", ".yaml", ".toml"]   # şema ve iş akışı


def _log(m):
    print(f"[{datetime.now(TR):%H:%M:%S}] {m}", flush=True)


def tg_gonder(metin):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        _log("(Telegram yok — atlandı)")
        return
    import requests
    for c in [x.strip() for x in chat.split(",") if x.strip()]:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": c, "text": f"<pre>{metin}</pre>",
                                "parse_mode": "HTML"}, timeout=20)
        except Exception as e:
            _log(f"Telegram hata: {e}")


def tg_komutlar():
    """Son mesajları okur, /onayla ve /reddet komutlarını çıkarır.

    getUpdates offset'i repoda tutulur (bekleyen/.offset) — aynı komut
    iki kez işlenmesin.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return []
    import requests
    off_dosya = BEKLEYEN / ".offset"
    try:
        offset = int(off_dosya.read_text().strip())
    except Exception:
        offset = 0
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                         params={"offset": offset + 1, "timeout": 5}, timeout=25)
        veri = r.json()
    except Exception as e:
        _log(f"getUpdates hata: {e}")
        return []
    if not veri.get("ok"):
        _log(f"getUpdates başarısız: {veri}")
        return []

    yetkili = {x.strip() for x in
               (os.environ.get("YETKILI_CHAT")
                or os.environ.get("TELEGRAM_CHAT_ID") or "").split(",") if x.strip()}
    komutlar, son = [], offset
    for u in veri.get("result", []):
        son = max(son, int(u.get("update_id", 0)))
        msg = u.get("message") or u.get("channel_post") or {}
        metin = str(msg.get("text") or "").strip()
        kim = str((msg.get("chat") or {}).get("id") or "")
        if not metin.startswith("/"):
            continue
        parca = metin.split()
        eylem = parca[0].lstrip("/").lower()
        if eylem not in ("onayla", "reddet"):
            continue
        if yetkili and kim not in yetkili:
            _log(f"YETKİSİZ onay denemesi: chat={kim}")
            tg_gonder(f"⛔ Yetkisiz onay denemesi engellendi (chat {kim}).")
            continue
        komutlar.append({"eylem": eylem,
                         "ad": parca[1] if len(parca) > 1 else "",
                         "kim": kim})
    try:
        BEKLEYEN.mkdir(parents=True, exist_ok=True)
        off_dosya.write_text(str(son))
    except Exception:
        pass
    return komutlar


def yama_oku(ad):
    d = BEKLEYEN / f"{ad}.json"
    if not d.exists():
        return None, f"'{ad}' bulunamadı."
    try:
        y = json.loads(d.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"'{ad}' okunamadı: {e}"
    if not isinstance(y.get("degisiklikler"), list) or not y["degisiklikler"]:
        return None, f"'{ad}' içinde değişiklik yok."
    return y, ""


def yasak_mi(yol):
    y = str(yol).replace("\\", "/").strip().lstrip("./")
    if y in YASAK_DOSYA:
        return f"{y} — para/stok/yetki dosyası"
    if any(y.endswith(u) for u in YASAK_UZANTI):
        return f"{y} — şema/iş akışı dosyası"
    return ""


def yama_uygula(y):
    """Değişiklikleri diske yazar. Döner: (basarili, mesaj, degisen_dosyalar).

    Her dosya için önce YEDEK alınır; bir adım patlarsa HEPSİ geri alınır.
    Yarım uygulanmış yama, hiç uygulanmamış yamadan daha tehlikelidir.
    """
    yedek, degisen = {}, []
    try:
        for d in y["degisiklikler"]:
            yol = KOK / d["dosya"]
            if not yol.exists():
                raise RuntimeError(f"{d['dosya']} yok")
            eski = yol.read_text(encoding="utf-8")
            yedek[yol] = eski
            if d.get("tip") == "degistir":
                if d["eski"] not in eski:
                    raise RuntimeError(
                        f"{d['dosya']}: aranan metin bulunamadı "
                        f"(dosya değişmiş olabilir)")
                if eski.count(d["eski"]) > 1:
                    raise RuntimeError(
                        f"{d['dosya']}: aranan metin {eski.count(d['eski'])} kez "
                        f"geçiyor, hangisi belirsiz")
                yeni = eski.replace(d["eski"], d["yeni"], 1)
            elif d.get("tip") == "tam":
                yeni = d["yeni"]
            else:
                raise RuntimeError(f"bilinmeyen tip: {d.get('tip')}")
            yol.write_text(yeni, encoding="utf-8")
            degisen.append(d["dosya"])

        # Sözdizimi kontrolü — bozuk kod commit'lenmesin
        for f in degisen:
            if f.endswith(".py"):
                py_compile.compile(str(KOK / f), doraise=True)
        return True, "", degisen

    except Exception as e:
        for yol, icerik in yedek.items():
            try:
                yol.write_text(icerik, encoding="utf-8")
            except Exception:
                pass
        return False, str(e)[:200], []


def testler_gecti():
    """Repoda test varsa koşar. Yoksa (True, 'test yok') döner."""
    t = KOK / "tests"
    if not t.exists():
        return True, "test klasörü yok — atlandı"
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(t)],
                           capture_output=True, text=True, timeout=600, cwd=str(KOK))
        return r.returncode == 0, (r.stdout or r.stderr)[-500:]
    except Exception as e:
        return False, f"test koşulamadı: {e}"


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, cwd=str(KOK))


def commitle(y, degisen, ad):
    git("config", "user.name", "KAYRAN Otonom")
    git("config", "user.email", "otonom@kayran.local")
    for f in degisen:
        git("add", f)
    git("add", "bekleyen")
    mesaj = (f"{y.get('baslik', ad)}\n\n"
             f"Telegram onayıyla uygulandı.\n"
             f"Talep: {y.get('talep', '—')}\n"
             f"Dosyalar: {', '.join(degisen)}")
    r = git("commit", "-m", mesaj)
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
        return False, (r.stdout + r.stderr)[-300:]
    p = git("push")
    if p.returncode != 0:
        return False, (p.stdout + p.stderr)[-300:]
    return True, ""


def islem(k):
    ad = k["ad"]
    if not ad:
        tg_gonder("Kullanım:  /onayla <ad>   ·   /reddet <ad>")
        return

    y, hata = yama_oku(ad)
    if not y:
        tg_gonder(f"❌ {hata}")
        return

    if k["eylem"] == "reddet":
        ARSIV.mkdir(parents=True, exist_ok=True)
        shutil.move(str(BEKLEYEN / f"{ad}.json"),
                    str(ARSIV / f"{ad}.reddedildi.json"))
        git("add", "bekleyen")
        git("commit", "-m", f"reddedildi: {ad}")
        git("push")
        tg_gonder(f"🗑️ '{ad}' reddedildi, arşive taşındı.")
        return

    # ── ONAY ──
    engel = [yasak_mi(d["dosya"]) for d in y["degisiklikler"]]
    engel = [e for e in engel if e]
    if engel:
        tg_gonder("⛔ UYGULANMADI — yasak dosya:\n" + "\n".join(f"• {e}" for e in engel)
                  + "\n\nBu dosyalar elle değiştirilmeli.")
        return

    ok, hata, degisen = yama_uygula(y)
    if not ok:
        tg_gonder(f"❌ '{ad}' uygulanamadı:\n{hata}\n\nHiçbir dosya değişmedi.")
        return

    gecti, cikti = testler_gecti()
    if not gecti:
        for d in y["degisiklikler"]:
            git("checkout", "--", d["dosya"])
        tg_gonder(f"❌ '{ad}' TESTTEN GEÇMEDİ — geri alındı.\n\n{cikti[-300:]}")
        return

    ARSIV.mkdir(parents=True, exist_ok=True)
    shutil.move(str(BEKLEYEN / f"{ad}.json"),
                str(ARSIV / f"{ad}.uygulandi.json"))

    ok2, hata2 = commitle(y, degisen, ad)
    if not ok2:
        tg_gonder(f"⚠️ '{ad}' uygulandı ama YÜKLENEMEDİ:\n{hata2}")
        return

    tg_gonder(f"✅ '{ad}' uygulandı ve yüklendi.\n\n"
              f"{y.get('baslik', '')}\n"
              f"Dosyalar: {', '.join(degisen)}\n"
              f"Test: {cikti[:80]}\n\n"
              f"Streamlit birkaç dakikada yeni sürümü alır.")


def bekleyenleri_duyur():
    """Bekleyen yama varsa hatırlat (günde bir kez yeterli)."""
    if not BEKLEYEN.exists():
        return
    liste = sorted(p.stem for p in BEKLEYEN.glob("*.json"))
    if not liste:
        _log("duyurulacak yama yok")
        return
    s = ["BEKLEYEN DEĞİŞİKLİKLER", "=" * 34]
    for ad in liste:
        y, _ = yama_oku(ad)
        if not y:
            continue
        dosyalar = [d["dosya"] for d in y["degisiklikler"]]
        engel = [e for e in (yasak_mi(f) for f in dosyalar) if e]
        s.append(f"\n• {ad}")
        s.append(f"  {y.get('baslik','(başlıksız)')}")
        s.append(f"  dosya: {', '.join(dosyalar)}")
        if engel:
            s.append("  ⛔ YASAK DOSYA — onaylansa da uygulanmaz")
        else:
            s.append(f"  onay:  /onayla {ad}")
    tg_gonder("\n".join(s))


def main():
    BEKLEYEN.mkdir(parents=True, exist_ok=True)

    # Tanı: hangi ortamda çalışıyoruz, ne bulundu — körlemesine bakmayalım
    _log(f"kök: {KOK}")
    _log(f"telegram token: {'var' if os.environ.get('TELEGRAM_BOT_TOKEN') else 'YOK'} · "
         f"chat: {'var' if os.environ.get('TELEGRAM_CHAT_ID') else 'YOK'}")
    bek = sorted(p.stem for p in BEKLEYEN.glob("*.json"))
    _log(f"bekleyen yama: {len(bek)} → {bek}")

    komutlar = tg_komutlar()
    _log(f"{len(komutlar)} komut bulundu")
    for k in komutlar:
        _log(f"işleniyor: /{k['eylem']} {k['ad']}")
        islem(k)

    # DUYUR=1 ZORUNLU DEĞİL: bekleyen yama varsa ve bu çalıştırmada işlenen
    # komut yoksa, hatırlatma gönderilir. Elle tetiklemede kutuyu doldurmayı
    # unutmak duyuruyu tamamen susturuyordu.
    _duyur = os.environ.get("DUYUR", "").strip() == "1"
    if _duyur or (bek and not komutlar):
        _log("bekleyenler duyuruluyor")
        bekleyenleri_duyur()
    else:
        _log("duyuru yok (bekleyen yama yok ya da komut işlendi)")


if __name__ == "__main__":
    main()

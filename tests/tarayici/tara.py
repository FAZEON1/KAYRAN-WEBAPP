# -*- coding: utf-8 -*-
"""TARAYICI TARAMASI (Ekim 2026): her sayfa gerçek tarayıcıda, bilgisayar ve telefon boyutunda açılır.

Sayfa testi (tests/duman) Python tarafını dener; bu tarama ekranda görünen hataları yakalar:
  hata      sayfada kırmızı hata kutusu (stException)
  ust       içeriğin üstünde görünmez bir katman (tıklama / tekerlek yutar — Ekim 2026 sol menü örtüsü)
  tasma     sayfa yatay taşıyor (telefonda sağa kayıyor)
  kaymiyor  içerik uzun ama fare tekerleği sayfayı kaydırmıyor (sayı kutusu tekerleği yutuyordu)
  konsol    tarayıcı konsolunda JavaScript hatası
  zaman     sayfa 40 sn'de bitmedi

Çalıştırma (CI: "Tarayıcı taraması"):
    streamlit run tests/tarayici/vitrin.py --server.port 8601 --server.headless true &
    python tests/tarayici/tara.py --cihaz pc tel --cikti tarama.json

Sorun varsa çıkış kodu 1; sorunlu sayfanın ekran görüntüsü tarama_goruntu/ klasörüne yazılır.
Bilinen ve kabul edilmiş durum IZINLI'ye gerekçesiyle eklenir (boş tutulması hedeflenir)."""
import argparse
import asyncio
import json
import os
import sys
import urllib.parse as U

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

CIHAZLAR = {"pc": (1300, 900), "tel": (390, 844)}
ESZAMANLI = 4                     # aynı anda açılan sayfa
BEKLEME_MS = 40000                # sayfa en çok bu kadar çalışır
SON_BEKLEME_MS = 1500             # çalışma bitince bileşenlerin (masa, menü) çizilmesi için
# {(sayfa adı, cihaz, sorun türü): gerekçe}
IZINLI = {}
# Konsolda sorun sayılmayanlar: sahte ortamda olmayan kaynaklar (favicon, ağ)
KONSOL_GURULTU = ("favicon", "net::ERR", "Failed to load resource")


def sayfa_listesi():
    """[(modül, oturum anahtarı, sayfa seçeneği, ad)] — sol menüdeki her sayfa + sistem sayfaları."""
    from shared.gezinme import MODULLER, SISTEM
    out = [("anasayfa", None, None, "anasayfa")]
    for m in MODULLER:
        if m["kod"] == "anasayfa":
            continue
        if not m.get("sayfalar"):
            out.append((m["kod"], None, None, m["kod"]))
            continue
        for sec, kod, _ad, _kosul in m["sayfalar"]:
            out.append((m["kod"], m["anahtar"], sec, f"{m['kod']}/{kod}"))
    for kod, *_ in SISTEM:
        out.append((kod, None, None, f"sistem/{kod}"))
    return out


def adres(taban, mod, anahtar, sec):
    a = f"{taban.rstrip('/')}/?mod={U.quote(mod)}"
    if anahtar:
        a += f"&anahtar={U.quote(anahtar)}&sec={U.quote(sec or '')}"
    return a


def sorunlari_ayikla(ad, cihaz, ham, izinli=None):
    """Ham ölçümden gerçek sorunlar: konsol gürültüsü ve gerekçeli izinler düşülür. Boş sözlük = temiz."""
    izinli = IZINLI if izinli is None else izinli
    ham = dict(ham or {})
    ham["konsol"] = [k for k in ham.get("konsol") or [] if not any(g in k for g in KONSOL_GURULTU)][:3]
    return {k: v for k, v in ham.items() if v and (ad, cihaz, k) not in izinli}


def rapor(sonuclar):
    """[(ad, cihaz, sorunlar)] → okunur özet (CI günlüğü)."""
    sorunlu = [(a, c, s) for a, c, s in sonuclar if s]
    satir = [f"{len(sonuclar)} sayfa açıldı, {len(sorunlu)} sorunlu."]
    for a, c, s in sorunlu:
        satir.append(f"  {a} [{c}]: " + "; ".join(f"{k}: {v}" for k, v in s.items()))
    return "\n".join(satir)


# Görünmez katman + yatay taşma: ana alanda ızgara noktalarında en üstteki öğe ana alana mı ait?
_ORT_JS = r"""([w, h]) => { if (!document.documentElement) throw new Error("belge null");
  const r = { ust: [], tasma: document.documentElement.scrollWidth > window.innerWidth + 2 };
  const main = document.querySelector('[data-testid=stMain]'); if (!main) throw new Error("stMain null"); const mb = main.getBoundingClientRect();
  for (let x = mb.x + 20; x < w - 10; x += 90) for (let y = 90; y < h - 20; y += 90) {
    const e = document.elementFromPoint(x, y); if (!e) continue;
    if (!main.contains(e) && !e.closest('[data-testid=stBottom],.st-key-alt_menu,[role=dialog],.st-key-ustnav')) {
      const t = (e.closest('[data-testid]') || e);
      r.ust.push(Math.round(x) + ',' + y + ':' + (t.getAttribute('data-testid') || t.tagName) + ' ' + String(t.className).slice(0, 30)); } }
  r.ust = r.ust.slice(0, 4); return r; }"""
_MAIN = "document.querySelector('[data-testid=stMain]')"


async def _bekle(pg):
    """Sayfa çalışması bitene kadar bekler. Döner: zaman aşımı oldu mu."""
    try:
        await pg.wait_for_selector("[data-testid=stMain]", timeout=BEKLEME_MS)
        await pg.wait_for_timeout(800)
        await pg.wait_for_selector('[data-testid=stApp][data-test-script-state="notRunning"]', timeout=BEKLEME_MS)
    except Exception:  # noqa: BLE001
        return True
    await pg.wait_for_timeout(SON_BEKLEME_MS)
    return False


async def _tekerlek(pg, w, h):
    """İçerik uzunsa üç noktada tekerlek: sayfa kaymayan noktaların x'i."""
    kay = []
    if await pg.evaluate(f"() => {{ const m = {_MAIN}; return !!m && m.scrollHeight > m.clientHeight + 50; }}"):
        for x in ((300, 700, 1200) if w > 800 else (60, 200, 330)):
            await pg.evaluate(f"() => {_MAIN}.scrollTo(0, 0)")
            await pg.mouse.move(x, h // 2)
            await pg.mouse.wheel(0, 300)
            await pg.wait_for_timeout(300)
            if await pg.evaluate(f"() => {_MAIN}.scrollTop") < 50:
                kay.append(x)
    return kay


async def _olc(pg, w, h):
    ham = {"zaman": await _bekle(pg)}
    ham["hata"] = [x[:120] for x in await pg.locator("[data-testid=stException]").all_inner_texts()]
    r = await pg.evaluate(_ORT_JS, [w, h])
    ham["ust"], ham["tasma"] = r["ust"], r["tasma"]
    ham["kaymiyor"] = await _tekerlek(pg, w, h)
    return ham


async def _bir_sayfa(tarayici, taban, sayfa, cihaz, goruntu_dizini):
    mod, anahtar, sec, ad = sayfa
    w, h = CIHAZLAR[cihaz]
    ctx = await tarayici.new_context(viewport={"width": w, "height": h})
    pg = await ctx.new_page()
    konsol = []
    pg.on("console", lambda m: konsol.append(m.text[:160]) if m.type == "error" else None)
    pg.on("pageerror", lambda e: konsol.append("JS: " + str(e)[:160]))
    ham = {}
    try:
        await pg.goto(adres(taban, mod, anahtar, sec))
        for deneme in range(3):          # sayfa ölçüm sırasında yeniden yüklenirse (adres güncellenir) tekrar
            try:
                ham = await _olc(pg, w, h)
                break
            except Exception as ex:  # noqa: BLE001
                if deneme == 2:
                    raise
                if "context was destroyed" not in str(ex) and "null" not in str(ex):
                    raise
                await pg.wait_for_timeout(1500)
        if ham.get("kaymiyor"):          # ilk ölçümde çizim sürüyor olabilir: bir kez daha dene
            await pg.wait_for_timeout(2000)
            ham["kaymiyor"] = await _tekerlek(pg, w, h)
    except Exception as ex:  # noqa: BLE001
        ham["hata"] = [f"tarama: {str(ex)[:120]}"]
    ham["konsol"] = konsol
    sorun = sorunlari_ayikla(ad, cihaz, ham)
    if sorun and goruntu_dizini:
        try:
            os.makedirs(goruntu_dizini, exist_ok=True)
            await pg.screenshot(path=os.path.join(goruntu_dizini, f"{ad.replace('/', '_')}_{cihaz}.png"))
        except Exception:  # noqa: BLE001
            pass
    await ctx.close()
    return ad, cihaz, sorun


async def tara(taban, cihazlar, tarayici_yolu=None, goruntu_dizini=None, sayfalar=None):
    from playwright.async_api import async_playwright
    sayfalar = sayfalar or sayfa_listesi()
    kapi = asyncio.Semaphore(ESZAMANLI)
    async with async_playwright() as p:
        b = await p.chromium.launch(**({"executable_path": tarayici_yolu} if tarayici_yolu else {}))

        async def is_(s, c):
            async with kapi:
                return await _bir_sayfa(b, taban, s, c, goruntu_dizini)

        sonuc = await asyncio.gather(*(is_(s, c) for c in cihazlar for s in sayfalar))
        await b.close()
    return list(sonuc)


def main(argv=None):
    a = argparse.ArgumentParser(description="Her sayfayı gerçek tarayıcıda açıp ekran hatalarını arar.")
    a.add_argument("--adres", default="http://localhost:8601")
    a.add_argument("--cihaz", nargs="+", default=["pc", "tel"], choices=sorted(CIHAZLAR))
    a.add_argument("--cikti", default="tarama.json")
    a.add_argument("--goruntu", default="tarama_goruntu")
    a.add_argument("--tarayici", default=os.environ.get("TARAYICI_YOLU") or None,
                   help="chromium yolu (verilmezse Playwright'ın kendi tarayıcısı)")
    a.add_argument("--sadece", nargs="*", default=None, help="yalnız adında bunlardan biri geçen sayfalar")
    g = a.parse_args(argv)
    sayfalar = [s for s in sayfa_listesi() if not g.sadece or any(x in s[3] for x in g.sadece)]
    sonuc = asyncio.run(tara(g.adres, g.cihaz, g.tarayici, g.goruntu, sayfalar))
    with open(g.cikti, "w", encoding="utf-8") as f:
        json.dump([{"sayfa": s, "cihaz": c, "sorun": o} for s, c, o in sonuc], f, ensure_ascii=False, indent=1)
    print(rapor(sonuc))
    return 1 if any(o for _, _, o in sonuc) else 0


if __name__ == "__main__":
    sys.exit(main())

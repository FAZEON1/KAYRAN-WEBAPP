"""KAYRAN WEBAPP uyanık tutucu (v2 — inatçı sürüm).

GitHub Actions günde birkaç kez çalıştırır:
1. Uygulamayı headless tarayıcıyla açar (websocket trafiği = ziyaret sayılır).
2. Uyku ekranı varsa "wake up" butonuna basar.
3. Uygulama kalkana kadar 3 tur dener (tur başına 4 dk bekleme + sayfa yenileme).
4. Yine olmadıysa ekran görüntüsü bırakır (Actions artifact) ve hata döner.
"""
import os
import sys
import time

URL = os.environ.get("STREAMLIT_APP_URL", "https://kayran-corporate.streamlit.app")
FOTO = os.environ.get("EKRAN_FOTO", "uyandir_son_durum.png")
UYANDIR_KALIPLARI = ["get this app back up", "wake this app", "back up", "wake up"]


def _uyku_butonuna_bas(page) -> bool:
    """Uyku ekranı butonunu birden çok stratejiyle arar; bastıysa True."""
    # 1) rol=button + metin filtresi
    for kalip in UYANDIR_KALIPLARI:
        try:
            btn = page.get_by_role("button").filter(has_text=kalip).first
            if btn.count() and btn.is_visible():
                print(f"😴 Uyku ekranı → '{kalip}' butonuna basılıyor (rol)")
                btn.click()
                return True
        except Exception:
            pass
    # 2) tüm butonları tek tek gez (metin farklı sarmalanmış olabilir)
    try:
        for btn in page.locator("button").all():
            try:
                t = (btn.inner_text() or "").strip().lower()
            except Exception:
                continue
            if any(k in t for k in UYANDIR_KALIPLARI):
                print(f"😴 Uyku ekranı → '{t[:40]}' butonuna basılıyor (tarama)")
                btn.click()
                return True
    except Exception:
        pass
    return False


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        print(f"→ {URL}")

        uyandirildi = False
        for tur in range(1, 4):                      # 3 tur × ~4 dk
            print(f"— Tur {tur}/3 —")
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
            except Exception as e:
                print(f"  sayfa açılamadı: {type(e).__name__} — tekrar denenecek")
                time.sleep(15)
                continue
            time.sleep(10)                           # yönlendirme/iframe otursun

            if _uyku_butonuna_bas(page):
                uyandirildi = True

            try:                                     # uygulama kabı gelsin
                page.wait_for_selector('[data-testid="stApp"], .stApp, section.main',
                                       timeout=240_000)
                time.sleep(12)                       # websocket otursun
                print("✅ Uygulama ayakta — ziyaret tamamlandı"
                      + (" (uyandırıldı)" if uyandirildi else ""))
                browser.close()
                return 0
            except Exception:
                print("  ⏳ bu turda yüklenmedi; sayfa yenilenip tekrar denenecek")

        # ── 3 tur da olmadı: kanıt bırak ──
        try:
            page.screenshot(path=FOTO, full_page=True)
            print(f"📸 Son durum fotoğrafı kaydedildi: {FOTO}")
        except Exception:
            pass
        print("❌ Uygulama ~12 dakikada ayağa kalkmadı. Muhtemel sebep: konteyner "
              "kaynak sınırında asılı (Manage app → Reboot gerekebilir).")
        browser.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())

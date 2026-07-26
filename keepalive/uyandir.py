"""KAYRAN WEBAPP uyanık tutucu.

GitHub Actions tarafından günde birkaç kez çalıştırılır:
1. Uygulamayı gerçek (headless) tarayıcıyla açar — Streamlit'in websocket
   trafiği oluşur, "ziyaret" sayılır, uyku sayacı sıfırlanır.
2. Uygulama uyumuşsa Streamlit'in "get this app back up" butonunu bulup
   TIKLAR ve tam uyanana kadar bekler.

Yerel makinede test: STREAMLIT_APP_URL ortam değişkeniyle çalıştır.
"""
import os
import sys
import time

URL = os.environ.get("STREAMLIT_APP_URL", "https://kayran-corporate.streamlit.app")

# Uyku ekranındaki buton metinleri (Streamlit zaman içinde değiştirdi; hepsi denenir)
UYANDIR_KALIPLARI = [
    "get this app back up", "wake this app", "back up", "wake up",
]


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        print(f"→ {URL} açılıyor…")
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        time.sleep(8)  # yönlendirme/iframe otursun

        # ── Uyku ekranı mı? Butonu bul, tıkla ──
        tiklandi = False
        for kalip in UYANDIR_KALIPLARI:
            try:
                btn = page.get_by_role("button").filter(has_text=kalip).first
                if btn.is_visible(timeout=2_000):
                    print(f"😴 Uyku ekranı yakalandı → '{kalip}' butonuna basılıyor")
                    btn.click()
                    tiklandi = True
                    break
            except Exception:
                continue

        # ── Uygulamanın gerçekten yüklenmesini bekle ──
        # stApp: Streamlit ana kabı. Ağır uygulamada soğuk başlangıç dakikalar sürebilir.
        bekleme = 300_000 if tiklandi else 180_000
        try:
            page.wait_for_selector('[data-testid="stApp"], .stApp, section.main',
                                   timeout=bekleme)
            time.sleep(10)  # websocket otursun, ziyaret "gerçek" sayılsın
            print("✅ Uygulama ayakta — ziyaret tamamlandı"
                  + (" (uyandırıldı)" if tiklandi else " (zaten uyanıktı)"))
            browser.close()
            return 0
        except Exception:
            print("⚠️ Uygulama verilen sürede yüklenmedi — konteyner çok yavaş "
                  "kalkıyor ya da kaynak sınırına takılıyor olabilir. "
                  "(Bu tur başarısız; bir sonraki zamanlanmış tur tekrar deneyecek.)")
            browser.close()
            return 1


if __name__ == "__main__":
    sys.exit(main())

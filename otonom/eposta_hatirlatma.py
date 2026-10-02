# -*- coding: utf-8 -*-
"""Her sabah (GitHub Actions, telegram-brifing.yml): dönemsel yükleme hatırlatmalarını
SORUMLULARA e-postayla gönderir. Kurallar shared/eposta.py'de (testli):
son günden 2 gün önce, son gün, gecikmede her iş günü; 5 iş günü sonrası yöneticiye kopya.
Kişi başına günde en çok bir mail; iş aynı gün tekrar çalışırsa ikinci mail gitmez.

Ortam: SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS (GitHub sırları) +
.streamlit/secrets.toml (Supabase erişimi — iş akışı oluşturur).
SMTP yoksa hiçbir şey göndermez, durumu yazar ve başarıyla biter (brifingi bozmaz).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from shared.utils import tr_now
    from shared.yukleme_takvimi import durumlar
    from shared import eposta as E
    from kayranacc.database import get_ayar, set_ayar

    bugun = tr_now().date()
    dl = durumlar(bugun)
    adr = E.adresler()
    planlar = E.hatirlatma_mailleri(dl, bugun, adr)
    eksik = E.adressizler(dl, bugun, adr)
    if eksik:
        print("UYARI: e-posta adresi girilmemiş sorumlular (Kullanıcı Yönetimi):", ", ".join(eksik))
    son = get_ayar(E.GONDERIM_ANAHTAR, {}) or {}
    gidecek = E.gonderilecekler(planlar, son, bugun)
    print(f"{bugun} · bildirilecek {len(planlar)} kişi · bugün henüz gönderilmemiş {len(gidecek)}")
    if gidecek and not (E.ayarlar()["user"] and E.ayarlar()["pass"]):
        print("SMTP yapılandırılmamış (SMTP_USER / SMTP_PASS) — mail gönderilmedi.")
        return
    hata = 0
    for p in gidecek:
        ok, kod = E.gonder(p["kime"], p["konu"], p["html"], cc=p["cc"])
        print(("gönderildi" if ok else "HATA"), "→", p["kullanici"], p["kime"], ("cc " + ", ".join(p["cc"])) if p["cc"] else "",
              "·", p["konu"], "" if ok else f"· {kod}")
        if ok:
            son[p["kullanici"]] = bugun.isoformat()
        else:
            hata += 1
    if gidecek:
        set_ayar(E.GONDERIM_ANAHTAR, son)
    if hata:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

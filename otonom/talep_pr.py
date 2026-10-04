# -*- coding: utf-8 -*-
"""Talep PR'ı açıldı / birleşti / kapandı → talep kaydını güncelle, mail at (Ekim 2026).

GitHub Actions: .github/workflows/talep-pr.yml (başlığı "Talep #<id>" içeren PR'larda).
Ortam: PR_BASLIK, PR_OLAY (opened / reopened / closed), PR_BIRLESTI ("true"), PR_URL.
Akışın tamamı: shared/claude_talep.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from shared import claude_talep as C
    from shared import eposta as E
    from shared.utils import tr_now
    from kayranpm.database import get_client

    baslik, olay = os.environ.get("PR_BASLIK", ""), os.environ.get("PR_OLAY", "")
    birlesti = os.environ.get("PR_BIRLESTI", "").lower() == "true"
    url = os.environ.get("PR_URL", "")
    tid = C.baslik_talep_id(baslik)
    if tid is None:
        print("Başlıkta 'Talep #<id>' yok — atlandı:", baslik)
        return
    db = get_client()
    satir = (db.table("talepler").select("*").eq("id", tid).execute().data or [None])[0]
    if not satir:
        print(f"Talep #{tid} bulunamadı.")
        return
    alanlar = C.pr_guncellemesi(olay, birlesti, url, tr_now())
    if not alanlar:
        print("Olay işlenmez:", olay)
        return
    db.table("talepler").update(alanlar).eq("id", tid).execute()
    print(f"Talep #{tid} → {alanlar['claude_durum']}")
    if not (E.ayarlar()["user"] and E.ayarlar()["pass"]):
        print("SMTP yapılandırılmamış — mail gönderilmedi.")
        return
    adr = E.adresler()
    for kisi, konu, govde in C.pr_mailleri(satir, alanlar["claude_durum"], url):
        if not adr.get(kisi):
            print("UYARI: e-posta adresi yok →", kisi)
            continue
        ok, kod = E.gonder([adr[kisi]], konu, govde)
        print(("gönderildi" if ok else "HATA"), "→", kisi, "" if ok else kod)


if __name__ == "__main__":
    main()

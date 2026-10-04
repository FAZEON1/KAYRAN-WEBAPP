# -*- coding: utf-8 -*-
"""Haftalık yaşlı stok maili (Ekim 2026) — GitHub Actions, telegram-brifing.yml (her sabah çalışır,
yalnız PAZARTESİ gönderir; elle denemede YASLI_STOK_ZORLA=1).

Her kişiye yalnız sorumlu olduğu kategorilerin yaşlı stoğu (eşikten yaşlı, FIFO, depoya giriş
tarihinden), tek mail + Excel eki (ürünler ve elde kalan partiler). Yaşlı stoğu olmayana mail gitmez;
aynı gün ikinci kez gitmez. Kategori sorumluları, eşik ve istisna kategoriler (yedek parça) sistem
ayarında: kayranpm/stok_yasi.VARSAYILAN_AYAR + Stok yaşı sayfasındaki ayar bölümü.
SMTP yoksa hiçbir şey göndermez, durumu yazar ve başarıyla biter.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from shared.utils import tr_now
    from shared import eposta as E
    from kayranacc.database import get_ayar, set_ayar
    import kayranpm.stok_yasi as Y

    bugun = tr_now().date()
    if bugun.weekday() != 0 and not os.environ.get("YASLI_STOK_ZORLA"):
        print(f"{bugun}: pazartesi değil — yaşlı stok maili gönderilmedi.")
        return
    v = Y.hesapla()
    ayar = v.get("ayar") or Y.ayar_oku()
    try:
        from satis.database import get_pacal_map
        pacal = get_pacal_map() or {}
    except Exception:  # noqa: BLE001
        pacal = {}
    esik = ayar["esik_gun"]
    satirlar = Y.yasli_satirlar(v["bizim"], pacal, v["bugun"], esik)
    listeler = Y.kisi_listeleri(satirlar, ayar)
    adr = E.adresler()
    son = get_ayar(Y.MAIL_SON_ANAHTAR, {}) or {}
    print(f"{bugun} · {esik}+ gün yaşlı ürün {len(satirlar)} · alıcı {len(listeler)}")
    if listeler and not (E.ayarlar()["user"] and E.ayarlar()["pass"]):
        print("SMTP yapılandırılmamış — mail gönderilmedi.")
        return
    hata = 0
    for kisi, rows in sorted(listeler.items()):
        if son.get(kisi) == bugun.isoformat():
            print("bugün zaten gönderildi →", kisi)
            continue
        if not adr.get(kisi):
            print("UYARI: e-posta adresi yok →", kisi)
            continue
        idler = {r["_id"] for r in rows}
        xlsx = Y.excel_bytes({"Yaşlı stok": rows,
                              "Partiler": [p for p in Y.parti_satirlari(v["bizim"], v["bugun"], skular=idler)
                                           if (p["Yaş (gün)"] or 0) > esik]})
        ok, kod = E.gonder([adr[kisi]], f"KAYRAN · Yaşlı stok ({len(rows)} ürün) · {bugun:%d.%m.%Y}",
                           Y.mail_html(rows, esik, bugun),
                           ekler=[(f"yasli_stok_{bugun}.xlsx", xlsx,
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")])
        print(("gönderildi" if ok else "HATA"), "→", kisi, adr[kisi], f"{len(rows)} ürün", "" if ok else kod)
        if ok:
            son[kisi] = bugun.isoformat()
        else:
            hata += 1
    if listeler:
        set_ayar(Y.MAIL_SON_ANAHTAR, son)
    if hata:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

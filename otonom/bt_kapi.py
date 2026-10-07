# -*- coding: utf-8 -*-
"""Bilgi işlem PR'ları için otomatik birleştirme kapısı (Ekim 2026).

Kullanıcı kararı: bilgi işlem elemanının küçük düzeltmeleri kendisi birleşsin. Karar elemana
bırakılmaz: bu betik GitHub Actions'ta (.github/workflows/bt-birlestir.yml) çalışır, kuralları
shared/bt_hesap.kapi_karari ile denetler. Uyan PR birleşir; uymayan PR kullanıcıya kalır ve PR'a
nedenini yazan tek bir yorum bırakılır.

Ortam: GITHUB_TOKEN, GITHUB_REPOSITORY (sahip/repo), DAL (PR'ın baş dalı) ya da PR_NO.
İsteğe bağlı: SUPABASE_URL, SUPABASE_KEY — birleşen PR'ın bt_rapor kaydı 'otomatik_birlesti' yapılır.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.bt_hesap import BASLIK_ONEKI, DAL_ONEKI, ETIKET, kapi_karari  # noqa: E402

GEREKEN_KONTROLLER = ("pytest", "Sayfa testi")
YORUM_ISARETI = "<!-- bt-kapi -->"


def _gh(yontem, yol, govde=None):
    url = "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + yol
    r = urllib.request.Request(url, method=yontem, data=None if govde is None else json.dumps(govde).encode(),
                               headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                                        "Accept": "application/vnd.github+json",
                                        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(r, timeout=30) as y:
        return json.loads(y.read() or b"null")


def testler_yesil(kontroller):
    """Her gereken kontrolün EN SON koşusu başarılı mı? (Aynı ad birden çok kez koşabilir.)"""
    son = {}
    for c in kontroller or []:
        ad = c.get("name")
        if ad in GEREKEN_KONTROLLER:
            if ad not in son or str(c.get("started_at") or "") > str(son[ad].get("started_at") or ""):
                son[ad] = c
    return all(ad in son and son[ad].get("status") == "completed" and son[ad].get("conclusion") == "success"
               for ad in GEREKEN_KONTROLLER)


def _pr_bul():
    if os.environ.get("PR_NO"):
        return _gh("GET", f"/pulls/{int(os.environ['PR_NO'])}")
    dal = os.environ.get("DAL", "")
    if not dal.startswith(DAL_ONEKI):
        return None
    sahip = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    prs = _gh("GET", "/pulls?state=open&head=" + urllib.parse.quote(f"{sahip}:{dal}"))
    prs = [p for p in prs or [] if str(p.get("title") or "").startswith(BASLIK_ONEKI)]
    return prs[0] if prs else None


def _rapor_isaretle(pr_url):
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")):
        return
    try:
        key = os.environ["SUPABASE_KEY"]
        url = (os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/bt_rapor?pr_url=eq."
               + urllib.parse.quote(pr_url, safe=""))
        r = urllib.request.Request(url, method="PATCH", data=json.dumps({"durum": "otomatik_birlesti"}).encode(),
                                   headers={"apikey": key, "Authorization": f"Bearer {key}",
                                            "Content-Type": "application/json"})
        urllib.request.urlopen(r, timeout=30).read()
    except Exception as e:  # noqa: BLE001
        print(f"bt_rapor güncellenemedi: {e}")


def _yorum(pr_no, metin):
    """Kapının yorumu PR başına bir kez yazılır; sonraki denemelerde güncellenir."""
    govde = f"{YORUM_ISARETI}\n{metin}\n\n---\n_Bilgi işlem kapısı (otonom/bt_kapi.py)_"
    for y in _gh("GET", f"/issues/{pr_no}/comments?per_page=100") or []:
        if YORUM_ISARETI in (y.get("body") or ""):
            _gh("PATCH", f"/issues/comments/{y['id']}", {"body": govde})
            return
    _gh("POST", f"/issues/{pr_no}/comments", {"body": govde})


def main():
    pr = _pr_bul()
    if not pr:
        print("Bilgi işlem PR'ı yok; çıkılıyor.")
        return 0
    no, dal = pr["number"], pr["head"]["ref"]
    etiketler = [e["name"] for e in pr.get("labels") or []]
    if ETIKET not in etiketler:
        print(f"#{no}: '{ETIKET}' etiketi yok — kullanıcı birleştirecek.")
        return 0
    dosyalar = _gh("GET", f"/pulls/{no}/files?per_page=100") or []
    kontroller = (_gh("GET", f"/commits/{pr['head']['sha']}/check-runs?per_page=100") or {}).get("check_runs", [])
    yesil = testler_yesil(kontroller)
    if not yesil and any(c.get("status") != "completed" for c in kontroller
                         if c.get("name") in GEREKEN_KONTROLLER):
        print(f"#{no}: testler sürüyor; bitince yeniden denenecek.")
        return 0
    ok, sebepler = kapi_karari(dosyalar, dal, etiketler, yesil, pr.get("title", ""))
    if not ok:
        print(f"#{no} otomatik birleşmez: " + "; ".join(sebepler))
        _yorum(no, "Bu PR otomatik birleştirilmedi, karar sende:\n" + "\n".join(f"- {s}" for s in sebepler))
        return 0
    _gh("PUT", f"/pulls/{no}/merge", {"merge_method": "squash",
                                      "commit_title": f"{pr['title']} (#{no}, bilgi işlem otomatik)"})
    print(f"#{no} otomatik birleştirildi.")
    _rapor_isaretle(pr["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

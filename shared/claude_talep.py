# -*- coding: utf-8 -*-
"""Talepten Claude'a — onaylı geliştirme akışı (Ekim 2026, seçenek A: tek onay).

  1. Çalışan Talep Merkezi'nden talep gönderir (bugünkü gibi).
  2. Onaycı (İbrahim) talebi açar, isterse not yazar, "Claude'a gönder"e basar
     → claude_durum = 'onaylandi'. Onaysız talebe Claude dokunmaz.
  3. claude.ai'deki zamanlanmış görev (hafta içi 09–18, saat başı) en eski onaylı talebi alır
     ('calisiyor'), otonom/claude_talep_gorevi.md'deki kurallarla kodlar, PR açar. Rakam değiştiren
     ya da belirsiz işte kod yazmaz, soru yazar ('soru'); onaycı cevabı nota yazıp yeniden gönderir.
  4. PR açılınca / birleşince GitHub iş akışı (talep-pr.yml → otonom/talep_pr.py) durumu günceller
     ve mail atar: PR hazır → onaycıya; yayında → talep sahibine. PR'ı birleştirmek kullanıcıdadır.

PR başlığı "Talep #<id>: ..." biçimindedir; iş akışı talebi buradan bulur (oturum dalının adı
Claude oturumuna göre değişir, ona güvenilmez).
"""
import re

ONAYCILAR = {"ibrahim"}

CLAUDE_DURUM_AD = {
    "onaylandi": "Claude'a gönderildi",
    "calisiyor": "Claude çalışıyor",
    "soru": "Claude'un sorusu var",
    "pr_hazir": "PR hazır, onay bekliyor",
    "yayinda": "Yayında",
    "kapandi": "PR kapatıldı",
    "hata": "Claude tamamlayamadı",
}

# Bu durumlarda talep yeniden gönderilebilir (cevap / yeni not ile).
YENIDEN_GONDERILIR = {"", "soru", "hata", "kapandi"}

SQL_EKSIK = ("Talepler tablosunda Claude alanları yok — veritabani/19_talep_claude.sql "
             "Supabase SQL Editor'de bir kez çalıştırılmalı.")

_BASLIK = re.compile(r"Talep\s*#\s*(\d+)", re.IGNORECASE)


def onaylayabilir_mi(kullanici, ozel_yetki=None):
    """Talebi Claude'a gönderebilir mi? Sabit onaycılar + (varsa) 'claude_onay' özel yetkisi."""
    k = str(kullanici or "").strip().lower()
    if not k:
        return False
    if k in ONAYCILAR:
        return True
    try:
        return bool(ozel_yetki and ozel_yetki(k, "claude_onay"))
    except Exception:  # noqa: BLE001
        return False


def claude_durumu(talep):
    return str((talep or {}).get("claude_durum") or "").strip()


def gonderilebilir_mi(talep):
    return claude_durumu(talep) in YENIDEN_GONDERILIR


def etiket(talep):
    """Ekranda gösterilecek Claude durumu ('' = Claude'a hiç gönderilmemiş)."""
    d = claude_durumu(talep)
    return CLAUDE_DURUM_AD.get(d, d)


def onay_kaydi(kullanici, not_, simdi):
    return {"claude_durum": "onaylandi", "claude_onay_notu": str(not_ or "").strip(),
            "claude_onaylayan": str(kullanici or "").strip().lower(),
            "claude_onay_tarihi": simdi.isoformat(), "claude_guncelleme": simdi.isoformat(),
            "claude_not": "", "durum": "inceleniyor"}


def onaya_gonder(client, talep_id, kullanici, not_, simdi):
    """Döner (ok, mesaj). Sütunlar yoksa (SQL 19 kurulmamış) anlaşılır uyarı döner."""
    try:
        client.table("talepler").update(onay_kaydi(kullanici, not_, simdi)).eq("id", talep_id).execute()
        return True, "Talep Claude'a gönderildi. Bir saat içinde başlar; PR hazır olunca mail gelir."
    except Exception as e:  # noqa: BLE001
        if "claude_" in str(e):
            return False, SQL_EKSIK
        return False, f"Kaydedilemedi: {type(e).__name__}"


def baslik_talep_id(baslik):
    m = _BASLIK.search(str(baslik or ""))
    return int(m.group(1)) if m else None


def pr_guncellemesi(olay, birlesti, pr_url, simdi):
    """GitHub PR olayı → talep kaydına yazılacak alanlar (None = yapılacak bir şey yok)."""
    t = simdi.isoformat()
    if olay in ("opened", "reopened", "ready_for_review"):
        return {"claude_durum": "pr_hazir", "claude_pr_url": pr_url, "claude_guncelleme": t}
    if olay == "closed" and birlesti:
        return {"claude_durum": "yayinda", "claude_pr_url": pr_url, "claude_guncelleme": t,
                "durum": "tamamlandi"}
    if olay == "closed":
        return {"claude_durum": "kapandi", "claude_guncelleme": t}
    return None


def pr_mailleri(talep, yeni_durum, pr_url):
    """[(kullanici, konu, govde_html)] — PR hazır → onaycıya; yayında → talep sahibine
    (sahibi onaycıysa bir kez); kapandı → onaycıya."""
    from shared import eposta as E
    konu = (talep or {}).get("konu") or "Talep"
    tid = (talep or {}).get("id")
    onayci = str((talep or {}).get("claude_onaylayan") or "ibrahim").strip().lower()
    sahip = str((talep or {}).get("gonderen") or "").strip().lower()
    if yeni_durum == "pr_hazir":
        govde = (f"<p><b>Talep #{tid} · {E._e(konu)}</b> için PR hazır. İnceleyip birleştirdiğinde "
                 f"yayına çıkar.</p><p><a href=\"{E._e(pr_url)}\">{E._e(pr_url)}</a></p>")
        return [(onayci, f"[KAYRAN Talep] PR hazır · {konu}",
                 E.sablon("PR hazır", govde, "PR'ı aç", pr_url))]
    if yeni_durum == "yayinda":
        govde = (f"<p><b>{E._e(konu)}</b> başlıklı talebin geliştirildi ve yayına alındı.</p>"
                 "<p>Uygulamayı yenilediğinde görürsün.</p>")
        return [(k, f"[KAYRAN Talep] {konu} — Yayında",
                 E.sablon("Talebin yayında", govde, "Uygulamayı aç", E.baglanti()))
                for k in dict.fromkeys([sahip, onayci]) if k]
    if yeni_durum == "kapandi":
        govde = f"<p><b>Talep #{tid} · {E._e(konu)}</b> için açılan PR birleştirilmeden kapatıldı.</p>"
        return [(onayci, f"[KAYRAN Talep] PR kapatıldı · {konu}",
                 E.sablon("PR kapatıldı", govde, "Talep Merkezi'ni aç", E.baglanti("anasayfa")))]
    return []
